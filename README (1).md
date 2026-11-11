# NYC charter schools map

An interactive map of New York City charter schools with a Success Academy view and a growth timeline. It is built only from public data and runs as a single static page, with no server.

**Live page:** [https://nayantarachoudhary.github.io/nyc-charter-schools-map/]

## What it does

- Shows 288 charter schools as bubbles. Success Academy schools are indigo and other charters are light blue, and bubble size shows the number of students.
- Filters by All charters or Success Academy, borough, grades served (elementary, middle, high), school size, network (choose as many as you like), and a search box (school name, borough or district). The count and the school list update as you filter. Clicking a school in the list zooms to it.
- **Growth timeline (Success Academy tab):** a slider from 2006 to the present, with a Play button, shows how many Success Academy schools were open each year. Only Success Academy pins move; other charters stay on the map. Schools that opened in the selected year get an amber ring.
- **Share link:** "Copy link to this view" saves the filters and year in the address, for example `#show=sa&boro=Bronx&year=2014`.
- **CSV download:** exports exactly the schools the current filters show.
- **Data confidence:** each popup says whether the school's name matches the state list. Schools that were renamed since the city file say so.
- **Report a data issue:** when the page is hosted on GitHub Pages, links to this repository's Issues.

## Data

| What | Source |
| --- | --- |
| Locations and names | NYC Department of Education school points file dated 2024-08-28 (from NYC Open Data). Charter schools are the 288 records with district code 84 in the school code. |
| Success Academy cross-check | NYS Education Department charter school list, updated 2025-10-02. |
| Opening years | "Date Opened" on the same state list. The exception is Hamilton Heights (2017), which is not on that list; its year cannot be confirmed by publicly available information, and its popup says so. |
| Enrollment and grades served | NYS Education Department enrollment database for 2024-25 (`ENROLL2025`). Matched to the city file by school name. 267 of 288 schools have a match; the rest are left blank and labeled as not verifiable with public sources. Grades served are the grades with students on the count day. |
| Borough | The letter in the school code (K, M, X, Q, R). |
| Network | Matched by words in the school name only. |

`charters.csv` is the cleaned dataset behind the map. `build_data.py` produced it, using `enrollment_match.csv` (the school-by-school match to the state enrollment file, made by `match_enr.py`). The page needs an internet connection for the street map tiles (CARTO) and the font (Google Fonts); the map library is bundled in `index.html`.

## Known gaps

- **Two Success Academy schools are listed under older names in the city file.** "Harlem 6" is now called Hamilton Heights, and the map uses the new name. The state list has no entry for it, so its 2017 opening year cannot be confirmed by publicly available information and it has no enrollment data. "Fort Greene" is shown as Success Academy Sheepshead Bay: the city file's coordinates are in Sheepshead Bay, and the state's code for it is now Sheepshead Bay. The popups say so.
- **Not every school has enrollment and grades.** 21 schools could not be matched to the state file with confidence (for example schools renamed since the city file). The page says the information could not be verified using public sources, and they are hidden while a size or grades filter is on.
- **Four Success Academy charters are not on the map.** NYC 15, NYC 17 and NYC 18 were approved to open in September 2026, and Norwood is on the state list, but neither source gives a matching location.
- **The location data is from August 2024.** Schools that opened, closed or renamed since then may be missing or out of date. Schools other than Success Academy have not been checked against the state list.
- **No test results.** Size and grades are included; test scores are not.

## How this was built

- **Problem:** show where NYC charter schools are, with Success Academy easy to isolate, using only public data.
- **Tools:** built with Claude. Leaflet draws the map. The data is embedded in the page, so it needs no backend.
- **Data work:** found the public sources, extracted the charter records, finished names the file cut off at 50 characters, derived each borough from the school code, cross-checked Success Academy names and opening years against the state list, and matched schools to the state enrollment file by name, reviewing the uncertain matches by hand and leaving ambiguous ones unmatched.
- **Governance:** public data only, with no student-level data. No user data is collected or sent anywhere. The only key in the page is a free map-tile key.
- **Checks:** no duplicate school codes, every record has a name, borough and district, and every coordinate falls inside New York City. In a headless browser, the filters and timeline returned the expected counts (for example 38 Success Academy schools, 17 open by 2013, 85 schools serving high school grades) and the popups, empty state and CSV export worked.
- **What I would measure in a real internal tool:** how often people use each filter, how often they find the school they came for, and how often they report a wrong name or location.
