"""Match NYC DOE charter records to NYSED 2024-25 BEDS-day enrollment.

Usage: python3 -I match_enr.py <ENROLL2025.accdb> <charters.json> <out.csv>
Needs the access-parser and scipy packages. Output: one row per matched school.
Matching is by name (with abbreviations expanded) inside each borough, then checked by hand.
"""
import csv, difflib, json, re, sys
import numpy as np
import pandas as pd
from access_parser import AccessParser
from scipy.optimize import linear_sum_assignment

acc, charters_json, out_csv = sys.argv[1:4]
D = json.load(open(charters_json))
E = pd.DataFrame(AccessParser(acc).parse_table("BEDS Day Enrollment"))
E = E[(E.ENTITY_CD.str[0] == "3") & (E.ENTITY_CD.str[6:8] == "86") & (E.YEAR.str.startswith("2025"))].reset_index(drop=True)
GR = ["PKHALF", "PKFULL", "PK", "KHALF", "KFULL"] + [str(i) for i in range(1, 13)] + ["UGE", "UGS", "K12"]
for k in GR:
    E[k] = pd.to_numeric(E[k], errors="coerce").fillna(0).astype(int)
BORO = {"31": "Manhattan", "32": "Bronx", "33": "Brooklyn", "34": "Queens", "35": "Staten Island"}
E["b"] = E.ENTITY_CD.str[:2].map(BORO)

ABB = {"cs": "charter school", "chs": "charter high school", "hs": "high school", "chtr": "charter", "acad": "academy",
       "hgts": "heights", "ms": "middle school", "prep": "preparatory", "&": "and", "int": "international", "comm": "community",
       "sch": "school", "adv": "advanced", "ma": "math", "sci": "science", "sciece": "science", "csd": "", "nyc": "new york city"}
def norm(s):
    s = s.lower().replace(".", " ").replace("'", "").replace("/", " ")
    s = re.sub(r"[^a-z0-9& ]+", " ", s)
    s = " ".join(ABB.get(x, x) for x in s.split())
    s = re.sub(r"success academy charter school|success academy", "success", s)
    s = re.sub(r"\b(the|of|for|at|a|and|charter|school|schools|new york city)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()
def sim(a, b):
    r = difflib.SequenceMatcher(None, a, b).ratio()
    ta, tb = set(a.split()), set(b.split())
    j = len(ta & tb) / max(1, min(len(ta), len(tb)))
    return max(r, 0.9 * j if len(ta & tb) >= 2 else 0)
E["nn"] = E.ENTITY_NAME.map(norm)

# Reviewed by hand. Ambiguous cases (several state schools could be the same city record) are left unmatched.
MANUAL = {  # DOE ats -> NYSED code
    "84K733": "333200861059", "84K357": "331700860882", "84X395": "320700860926", "84K406": "331600860975",
    "84K593": "331600860860", "84K608": "331800860908", "84K355": "331400860885", "84K724": "331800860943",
    "84M065": "321200861001", "84Q373": "342700861052", "84X208": "320800861018", "84X553": "321000860704",
    "84X202": "320800861017", "84X539": "321000860999", "84K738": "332200861053", "84Q320": "342700861054",
    "84K752": "332200861039",  # city file says Fort Greene; the state's code 861039 is now Success Academy Sheepshead Bay
}
REJECT = {"84X487", "84M330", "84M380", "84M357", "84K739"}

res = {}
for boro in BORO.values():
    ds = [d for d in D if d["b"] == boro and d["id"] not in MANUAL and d["id"] not in REJECT]
    es = E[(E.b == boro) & ~E.ENTITY_CD.isin(MANUAL.values())]
    M = np.array([[sim(norm(d["n"]), r.nn) for _, r in es.iterrows()] for d in ds])
    for i, j in zip(*linear_sum_assignment(-M)):
        if M[i, j] >= 0.75:
            res[ds[i]["id"]] = es.iloc[j].ENTITY_CD
res.update(MANUAL)
# A code may be used once.
seen = {}
for k, v in res.items():
    seen.setdefault(v, []).append(k)
assert all(len(v) == 1 for v in seen.values()), {k: v for k, v in seen.items() if len(v) > 1}

def grades(r):
    g = []
    if r["KHALF"] + r["KFULL"] > 0: g.append(0)
    g += [i for i in range(1, 13) if r[str(i)] > 0]
    return g
rows = []
byid = {d["id"]: d for d in D}
Ei = E.set_index("ENTITY_CD")
for ats, code in sorted(res.items()):
    r = Ei.loc[code]
    g = grades(r)
    if not g:
        continue
    lo, hi = min(g), max(g)
    gaps = [i for i in range(lo, hi + 1) if i not in g]
    rows.append({"ats": ats, "doe_name": byid[ats]["n"], "nysed_code": code, "nysed_name": r.ENTITY_NAME,
                 "enrollment": int(r.K12), "grade_low": lo, "grade_high": hi, "grades_served": ";".join(map(str, g)), "gaps": ";".join(map(str, gaps))})
with open(out_csv, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print("matched", len(rows), "of", len(D), "| unmatched DOE:", len(D) - len(rows))
print("NYSED schools not used:", [(c, n) for c, n in zip(E.ENTITY_CD, E.ENTITY_NAME) if c not in res.values()])
print("grade gaps:", [(r["doe_name"], r["gaps"]) for r in rows if r["gaps"]])
