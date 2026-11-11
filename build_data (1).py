"""Build the cleaned charter-school dataset from the NYC DOE school points shapefile.

Usage: python3 -I build_data.py <shapefile base path (no extension)> <output dir> [enrollment_match.csv]

Writes charters.json (embedded in the page) and charters.csv.
"""
import csv
import json
import re
import sys
from collections import Counter

import shapefile

BOROUGH = {"K": "Brooklyn", "M": "Manhattan", "X": "Bronx", "Q": "Queens", "R": "Staten Island"}

# The DOE file cuts names off at 50 characters. These fixes only finish the cut-off
# words; they do not rename anything.
NAME_FIXES = {
    "84K406": "EMBER Charter School for Mindful Education, Innovation and Transformation",
    "84K517": "Leadership Preparatory Bedford Stuyvesant Charter School",
    "84K593": "Excellence Boys Charter School of Bedford Stuyvesant",
    "84K733": "Math, Engineering, and Science Academy Charter High School",
    "84K784": "Achievement First North Brooklyn Preparatory Charter School",
    "84K792": "Cultural Arts Academy Charter School At Spring Creek",
    "84K807": "Collegiate Academy for Mathematics and Personal Awareness Charter School",
    "84K966": "Bedford Stuyvesant New Beginnings Charter School 2",
    "84K911": "Edmund W. Gordon Brooklyn Laboratory Charter School",
    "84M265": "Success Academy Charter School - Washington Heights",
    "84M284": "Harlem Children's Zone Promise Academy Charter School",
    "84M341": "Harlem Children's Zone Promise Academy II Charter School",
    "84Q339": "Success Academy Charter School - Springfield Gardens",
    "84R070": "Lois and Richard Nicotra Early College Charter School",
    "84X309": "South Bronx Charter School for International Cultures and the Arts",
    "84X389": "Bronx Global Learning Institute for Girls Charter School",
    "84X395": "NYC Charter High School for Architecture, Engineering & Construction Industries",
    "84X482": "Dr. Richard Izquierdo Health and Science Charter School",
    "84X611": "AECI II: NYC Charter High School for Computer Engineering and Innovation",
    "84X635": "Earl Monroe New Renaissance Basketball Charter School",
    # Four schools share this cut-off name; the borough shown beside it tells them apart.
    "84K738": "New Visions Charter High School for Advanced Math and Science",
    "84Q320": "New Visions Charter High School for Advanced Math and Science",
    "84X202": "New Visions Charter High School for Advanced Math and Science",
    "84X539": "New Visions Charter High School for Advanced Math and Science",
    "84K739": "New Visions Charter High School for the Humanities",
    "84Q373": "New Visions Charter High School for the Humanities",
    "84X208": "New Visions Charter High School for the Humanities",
    "84X553": "New Visions Charter High School for the Humanities",
}

# Nothing is left off the map. The city file lists one Success Academy school as "Fort Greene",
# but its coordinates are in Sheepshead Bay and the state's code for it (861039, formerly the
# Fort Greene charter) is now Success Academy Sheepshead Bay, with 2024-25 enrollment.
REMOVE = set()
NAME_FIXES["84K752"] = "Success Academy Charter School - Sheepshead Bay"
RENAMED_NOTE_OK = {"84K752": "Listed as Fort Greene in the city data (August 2024). The state list and the school\u2019s location show it as Success Academy Sheepshead Bay. The 2013 year is the charter\u2019s opening year on the state list."}

# Renamed since the DOE file. Success Academy now calls Harlem 6 "Hamilton Heights"; the
# state list has no entry for it, so it has no confirmed opening year.
NAME_FIXES["84M357"] = "Success Academy Charter School - Hamilton Heights"
RENAMED_NOTE = {"84M357": "Listed as Harlem 6 in the city data. Success Academy now calls it Hamilton Heights. It is not on the NYS Education Department list from October 2025, and its 2017 opening year cannot be confirmed by publicly available information."}
UNCONFIRMED_YEAR = {"84M357": 2017}

# Networks are matched by words in the school name only.
NETWORK_RULES = [
    ("Success Academy", "success academy"),
    ("KIPP", "kipp"),
    ("Achievement First", "achievement first"),
    ("Ascend", "ascend"),
    ("Icahn", "icahn"),
    ("Zeta", "zeta charter"),
    ("Brilla", "brilla"),
    ("Democracy Prep", "democracy prep"),
    ("Harlem Village Academy", "harlem village academy"),
    ("Harlem Children's Zone", "harlem children"),
    ("DREAM", "dream charter"),
    ("Explore Schools", "explore "),
    ("Family Life Academy", "family life academy"),
    ("South Bronx Classical", "south bronx classical"),
    ("Brooklyn Prospect", "brooklyn prospect"),
]
OTHER = "Independent or other"

# Open Success Academy charters on the NYS Education Department list updated
# Oct 2, 2025 (38), with the year each charter opened ("Date Opened" on that list).
NYSED_SA = {
    "Bed Stuy 1": 2011, "Bed Stuy 2": 2012, "Bed-Stuy 3": 2016, "Bensonhurst": 2014,
    "Bergen Beach": 2014, "Bronx 1": 2010, "Bronx 2": 2010, "Bronx 3": 2013, "Bronx 4": 2014,
    "Bronx 5 Lower": 2022, "Bronx 5 Upper": 2022, "Bushwick": 2016, "Cobble Hill": 2012,
    "Crown Heights": 2013, "Far Rockaway": 2016, "Flatbush": 2016, "Harlem 1": 2006,
    "Harlem 2": 2008, "Harlem 3": 2008, "Harlem 4": 2008, "Harlem 5": 2010,
    "Hell's Kitchen": 2013, "Hudson Yards": 2017, "Norwood": 2017, "NYC 12": 2024,
    "NYC 14": 2024, "NYC 5": 2024, "NYC 6": 2024, "NYC 7": 2024, "Prospect Heights": 2013,
    "Rosedale": 2014, "Sheepshead Bay": 2013, "South Jamaica": 2016,
    "Springfield Gardens": 2014, "Union Square": 2013, "Upper West": 2011,
    "Washington Heights": 2014, "Williamsburg": 2012,
}

CHECK_TEXT = {
    "ok": "Name matches NYS list (Oct 2025)",
    "no": "Name not on NYS list (Oct 2025)",
    "na": "Not checked against NYS list",
}


def key(s):
    s = re.sub(r"(?i)^success academy charter school", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def network(name):
    low = name.lower()
    for label, needle in NETWORK_RULES:
        if low.startswith(needle) or needle in low:
            return label
    return OTHER


def grade_label(lo, hi):
    f = lambda g: "K" if g == 0 else str(g)
    return f(lo) if lo == hi else f"{f(lo)}\u2013{f(hi)}"


def load_enrollment(path):
    """enrollment_match.csv comes from match_enr.py (state enrollment, 2024-25)."""
    out = {}
    if not path:
        return out
    with open(path) as f:
        for row in csv.DictReader(f):
            g = [int(x) for x in row["grades_served"].split(";")]
            lv = "".join(c for c, rng in (("e", range(0, 6)), ("m", range(6, 9)), ("h", range(9, 13))) if any(x in rng for x in g))
            out[row["ats"]] = {"en": int(row["enrollment"]), "gr": grade_label(int(row["grade_low"]), int(row["grade_high"])), "lv": lv}
    return out


def main(shp_base, out_dir, enr_path=None):
    enr = load_enrollment(enr_path)
    r = shapefile.Reader(shp_base)
    fields = [f[0] for f in r.fields[1:]]
    rows = [dict(zip(fields, rec)) for rec in r.records()]
    charters = [x for x in rows if str(x["ATS"]).startswith("84")]

    out, problems = [], []
    nysed = {key(n): (n, y) for n, y in NYSED_SA.items()}
    matched_sa = set()
    for x in sorted(charters, key=lambda x: x["ATS"]):
        ats = str(x["ATS"]).strip()
        if ats in REMOVE:
            continue
        name = NAME_FIXES.get(ats, str(x["Name"]).strip())
        if len(str(x["Name"]).strip()) >= 49 and ats not in NAME_FIXES:
            # Reviewed by hand: these are complete names that happen to be 49-50 characters.
            pass
        boro = BOROUGH.get(ats[2])
        lat, lon = float(x["Latitude"]), float(x["Longitude"])
        if boro is None:
            problems.append(f"no borough for {ats}")
        if not (40.45 < lat < 40.95 and -74.3 < lon < -73.65):
            problems.append(f"coords outside NYC: {ats} {lat},{lon}")
        is_sa = name.lower().startswith("success academy")
        note, year, ck = "", None, "na"
        if is_sa:
            k = key(name)
            if k in nysed:
                matched_sa.add(k)
                year, ck = nysed[k][1], "ok"
                note = RENAMED_NOTE_OK.get(ats, "")
            else:
                ck = "no"
                year = UNCONFIRMED_YEAR.get(ats)
                note = RENAMED_NOTE.get(ats, "Name unconfirmed: it is not on the NYS Education Department list from October 2025.")
        out.append({
            "id": ats, "n": name, "b": boro, "d": int(x["Geographic"]),
            "la": round(lat, 6), "lo": round(lon, 6), "sa": is_sa,
            "nw": network(name), "note": note, "y": year, "ck": ck,
            **enr.get(ats, {"en": None, "gr": "", "lv": ""}),
        })

    sa_rows = [o for o in out if o["sa"]]
    unmatched_nysed = [n for k, (n, _) in nysed.items() if k not in matched_sa]

    with open(f"{out_dir}/charters.json", "w") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    with open(f"{out_dir}/charters.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ats_code", "name", "borough", "community_school_district", "latitude",
                    "longitude", "success_academy", "network_by_name", "opened_year",
                    "data_check", "enrollment_2024_25", "grades_served", "note"])
        for o in out:
            w.writerow([o["id"], o["n"], o["b"], o["d"], o["la"], o["lo"],
                        "yes" if o["sa"] else "no", o["nw"], o["y"] if o["y"] else "",
                        CHECK_TEXT[o["ck"]], o["en"] if o["en"] is not None else "", o["gr"], o["note"]])

    by_year = Counter(o["y"] for o in sa_rows if o["y"])
    cumulative, running = {}, 0
    for yr in sorted(by_year):
        running += by_year[yr]
        cumulative[yr] = running
    print("charter records:", len(out))
    print("by borough:", dict(Counter(o["b"] for o in out)))
    print("success academy records:", len(sa_rows))
    print("SA matched to NYSED names:", len(matched_sa), "of", len(NYSED_SA))
    print("SA in DOE file but not on NYSED list:", [o["n"] for o in sa_rows if o["note"]])
    print("NYSED SA names with no DOE record:", unmatched_nysed)
    print("SA opened per year:", dict(sorted(by_year.items())))
    print("SA cumulative open by year:", cumulative)
    print("SA with no year:", sum(1 for o in sa_rows if not o["y"]))
    print("data check counts:", dict(Counter(o["ck"] for o in out)))
    print("duplicate ids:", [k for k, v in Counter(o["id"] for o in out).items() if v > 1])
    print("empty fields:", sum(1 for o in out if not o["n"] or not o["b"]))
    print("problems:", problems or "none")
    have = [o for o in out if o["en"] is not None]
    print("enrollment matched:", len(have), "of", len(out), "| unmatched SA:", [o["n"] for o in out if o["sa"] and o["en"] is None])
    sizes = sorted(o["en"] for o in have)
    print("size bands <300 / 300-599 / 600-999 / 1000+:", sum(s < 300 for s in sizes), sum(300 <= s < 600 for s in sizes), sum(600 <= s < 1000 for s in sizes), sum(s >= 1000 for s in sizes))
    print("levels e/m/h:", [sum(c in o["lv"] for o in have) for c in "emh"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
