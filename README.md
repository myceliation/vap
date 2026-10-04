# NJ Vacant & Abandoned Property (VAP) records — archive

**Status: archived (October 1, 2026). Not maintained.**
Live page: <https://myceliation.github.io/vap/>

The page has two tabs.

- **NJ records** is a snapshot of what New Jersey municipalities sent back when asked, under the Open Public Records Act (OPRA), for their lists of vacant, abandoned and foreclosed properties. It maps how each town answered and the properties on the lists that came back.
- **Northeast places** maps about 55,000 abandoned, disused, ruined, closed or no-longer-producing places from Maryland to Maine, plus Quebec and the Maritimes. It draws on open map data, government mine inventories and a few labelled guesses.

Being on a list does not mean a property is vacant today; lists go stale fast. Most of the Northeast places are private land, mine openings can kill, and brownfields can be contaminated. Don't trespass.

## Publishing

On Windows, double-click `push_to_github.bat` (or the `Publish VAP map` shortcut on the Desktop, which runs it). The first run does the following:

1. Installs Git and the GitHub CLI if they're missing.
2. Opens a browser once so you can log in.
3. Creates `myceliation/vap`, pushes, and turns on GitHub Pages.

Later runs commit whatever changed and push it. `data/raw/` and the caches are never uploaded. The site is live a minute or two after a push.

## Counts

### NJ records

| | 2025 round | 2026 round | Total |
|---|---|---|---|
| Requests sent | 137 | 554 | 691 (562 municipalities) |
| Answered (any reply) | 65 | 395 | 460 |
| Records provided | 32 | 208 | 240 |
| No records held | 17 | 116 | 133 |
| Denied | 3 | 24 | 27 |
| Partial | 1 | 2 | 3 |
| Acknowledged, never completed | 12 | 45 | 57 |
| No response | 72 | 159 | 231 |
| Properties in `properties.csv` | 2,332 | 60 | 2,392 (30 municipalities) |
| Properties with a map point | | | 2,236 |

Median time to a substantive reply in 2026: 6 days. Census tracts in `vacancy_tracts.geojson`: 2,175.

### Northeast places (`data/ne/places.csv`)

| Category | Mapped | Guesses |
|---|---|---|
| Mines & quarries | 24,498 | 1,039 |
| Closed businesses (off by default) | 10,807 | |
| Ruins | 4,751 | |
| Brownfields | 4,236 | |
| Other buildings & sites | 1,756 | 323 |
| Rail & transport | 1,911 | |
| Towers & masts | 105 | 1,792 |
| Military & Cold War | 303 | 1,050 |
| Institutions (schools, hospitals, churches, prisons) | 858 | |
| Leisure & lodging | 500 | |
| Wrecks | 446 | |
| Industrial & power | 348 | |
| Ghost towns | 104 | |
| **Total** | **50,623** | **4,204** |

By source: OpenStreetMap 27,964 · USGS MRDS 10,172 · Nova Scotia abandoned mine openings 8,470 · MSHA 5,210 · FCC 1,792 · Wikidata 1,004 · Quebec orphaned mines 215. By place: NY 11,674 · PA 11,096 · NS 8,915 · QC 4,312 · MD 4,018 · MA 3,182 · NJ 2,995 · CT 2,446 · ME 1,953 · NH 1,346 · VT 1,096 · DC 628 · NB 470 · RI 348 · DE 281 · PE 67.

Abandoned or disused rail line segments (`data/ne/rail.json`): 22,770, of which 18,511 are tagged abandoned (track lifted) and the rest disused (track in place, no service).

## Method

### OPRA records

1. **Requests.** Spring 2025: requests sent by hand, mostly to South Jersey towns, tracked in a spreadsheet without dates. May–June 2026: an automated email to nearly every municipal clerk asking for (1) the vacant/abandoned/foreclosed-property registry, (2) unsafe-structure and condemnation orders from the last 24 months, and (3) residential water shutoffs of 12+ months.
2. **Outcomes.** 2026 outcomes were classified from the subject and preview text of every reply (`scripts/build_requests_2026.py`), then corrected using the written-denial and portal-refusal calls recorded during the project. 2025 outcomes come from the hand-kept tracker.
3. **Lists.** Spreadsheets, text PDFs, Word files and reply-email bodies were parsed (`scripts/parse_lists.py`). Scanned PDFs got one OCR pass (tesseract). Block and lot were normalized: leading zeros stripped, all-zero decimals dropped, condo qualifiers (e.g. `C0214`) kept in their own column.
4. **Location.** Each property was joined to the NJOGIS *Parcels and MOD-IV Composite of NJ* layer on `PAMS_PIN` = `muni_code_block_lot[_qualifier]` and placed at the parcel centroid. Rows without block/lot were matched by street address inside the same municipality; the rest went to the US Census batch geocoder and were kept only if they landed within 12 km of the town (`scripts/geocode.py`).
5. **Privacy.** Only the normalized CSVs are published. Owner names, registrant/servicer names, custodian names, emails, phone numbers and correspondence text are dropped. Homes the source list itself marks as owner- or tenant-occupied (181 rows, mostly Egg Harbor Township foreclosure registrations) are left out: those are households in foreclosure, not abandoned places. Raw PDFs and spreadsheets are not in this repo.

### Census layer (NJ tab)

Each tract is shaded by the share of housing units vacant for reasons other than rent, sale, seasonal or migrant use ("other vacant", ACS 2018–2022 table B25004_008, via Esri Living Atlas; `scripts/build_tracts.py`). Excluding summer homes makes it the closest census measure to long-empty houses. The NJ tract median is 1.7%, and 286 tracts are at 5% or higher.

### Northeast places

"Mapped" means a public source says the place is abandoned, disused, ruined, closed or no longer producing. "Guess" means a weaker signal points that way; guesses draw as hollow rings and can be hidden.

| Source | What was taken | Basis |
|---|---|---|
| OpenStreetMap (extracts from download.openstreetmap.fr, October 2026) | Features with `abandoned:*`, `disused:*` or `ruins:*` lifecycle tags, `abandoned=yes`, `disused=yes`, `ruins=yes`, `building=abandoned/disused/ruins/collapsed`, `historic=ruins/mine/mine_shaft/adit/wreck/fort/battery/kiln/furnace/ghost_town` and similar, `man_made=adit/mineshaft`, `landuse=brownfield`, `shop=vacant` | mapped |
| OpenStreetMap | `military=bunker/battery/launchpad/trench` with no lifecycle tag | guess |
| OpenStreetMap | Untagged features whose name says "abandoned", "derelict", "ruins", "former …", "site of …", "Nike", "missile" or "old … mine/mill/quarry/hospital"; roads, creeks, parks and working schools named "Old …" are excluded | guess |
| OpenStreetMap | `railway=abandoned` and `railway=disused` lines, simplified to about 40 m; stubs under about 150 m dropped | rail layer |
| Wikidata | Items whose state of use is permanently closed, decommissioned, abandoned or out of service, plus ghost towns, ruins and abandoned villages; demolished items and items marked in use are left out (`scripts/wd.py`) | mapped |
| USGS Mineral Resources Data System | Sites with development status "Past Producer" | mapped |
| USGS Mineral Resources Data System | "Prospect" sites (exploration pits, trenches, test shafts) | guess |
| MSHA Mines data set | Mines whose current status is "Abandoned" or "Abandoned and Sealed" | mapped |
| Quebec MRNF, orphaned and abandoned mines inventory | All sites, one point per site | mapped |
| Nova Scotia DNRR, Abandoned Mine Openings database | All openings, with hazard rating and a link to the province's report | mapped |
| FCC Antenna Structure Registration | Towers 30 m and taller (no antennas on buildings, trees, signs or tanks) whose registration was **terminated with no dismantle notice** (887), or is still "constructed" but **untouched since 2006 or earlier** (905) | guess |

How the rows were cleaned (`scripts/ne_extract.py`, `scripts/build_northeast.py`):

- Ways and relations are placed at the average of a sample of their nodes.
- Each point gets its state from TIGER state outlines; Canadian extracts keep their province. When another source's point falls in a different state from the one it was filed under, the point wins (72 rows moved); points outside the area were dropped (34).
- Level crossings, platforms, power poles, parking, benches, memorials, plaques, historic markers, golf-course bunkers and road segments were filtered out of the OpenStreetMap results.
- Places from different sources with the same name within about 200 m were merged, keeping OpenStreetMap, then Wikidata, then the mine inventories.
- Owner, operator and contact names are never read from any source. Tower rows carry only the registration number, height, build year and city.

Not scraped: Urbexology and similar urbex sites. Their terms forbid copying their content, their curated database is a paid product, and the free pins they show come from OpenStreetMap, which is used directly here.

## Data dictionary

### `data/requests.csv` — one row per OPRA request

| column | meaning |
|---|---|
| county | County |
| municipality | Municipality name (NJOGIS label) |
| muni_code | NJ 4-digit municipal code |
| request_date | Date sent (2026 only; 2025 dates weren't kept) |
| outcome | `fulfilled` (records provided), `partial`, `no_records` (town says it holds none), `pending` (acknowledged, never completed), `denied`, `no_response` |
| response_date | First reply carrying the outcome |
| days_to_response | response_date − request_date |
| n_records | Properties from this request that made it into `properties.csv` |
| notes | Short qualifier (e.g. `deemed denied`, `records attached, not parsed`, `bounced`) |
| round | `2025` or `2026` |

`no_records` is an addition to the original four-outcome plan: many towns answered that they keep no such list, which is neither a denial nor a fulfilled request.

### `data/properties.csv` — one row per listed property

| column | meaning |
|---|---|
| county, municipality, muni_code | Where the property is |
| block, lot, qualifier | Tax parcel identifiers as normalized (blank when the list gave only an address and no parcel matched) |
| address | Street address as listed, or the parcel's MOD-IV location when the list gave only block/lot |
| source_file | The response file or channel it came from |
| list_date | Date of the list, when stated (year only when that's all the list gave) |
| pogodata_verified | `yes` / `no` where a block/lot was checked against pogodata.org during the project; blank = not checked |
| abandonment_score | Likelihood call carried over from the project's review (Barnegat only): `Very likely`, `Likely`, `Possible` |
| listed_status | What kind of list and what it said (e.g. `foreclosure registration: Registered`, `abandoned structure list; aband`) |
| geocode_method | `njogis_parcel`, `njogis_address`, `census`, or `unresolved` |
| round | Request round the list came from |
| lat, lon | WGS84 point (blank when unresolved) |

### `data/ne/places.csv` — one row per Northeast place

| column | meaning |
|---|---|
| region | Two-letter state or province code |
| category | One of the 13 categories in the counts table |
| basis | `mapped` (a public source says so) or `inferred` (a guess; see Method) |
| name | Name in the source; FCC towers are named by registration number; blank when the source has none |
| kind | Feature type from the source (e.g. `adit`, `railway station`, `guyed tower`, `underground, coal`) |
| status | What the source says (e.g. `tagged disused`, `past producer`, `abandoned and sealed`), or the reason for a guess |
| source, source_id, link | Where the row came from, its ID there, and a link to the record |
| note | Dates where known (`built`, `closed`, `last production`), hazard rating for Nova Scotia openings, height for towers |
| lat, lon | WGS84 point |

`data/ne/places.json` holds the same rows in the compact form the page loads: `rows` are `[lon, lat, category, guess, region, source, name, kind, status, source_id, note]`, with category, region, source, kind and status as indexes into the lists of the same name, plus a `bounds` box per region. `data/ne/rail.json` holds `rows` of `[osm_way_id, name, abandoned (1) or disused (0), [[lon, lat], …]]`.

`data/properties.geojson` holds the NJ property rows as points. `data/vacancy_tracts.geojson` has simplified tract outlines with `units`, `other_vacant`, `moe`, `seasonal` and `pct`. `data/municipalities.json` holds municipal centroids for the request layer.

## Known gaps

- **2026 attachments weren't processed.** About 200 towns sent their 2026 records as attachments (`notes` = `records attached, not parsed`). Those lists were never downloaded or parsed, so 2026 contributes only lists that came in the email body plus the Barnegat registry.
- **2026 outcomes are approximate.** They come from reply previews, not full reads. `fulfilled` means records came back, not that they were a vacancy list; several are code-enforcement or water reports.
- **2025 round has no dates** and was sent from several email accounts, so the tracker is incomplete; 7 towns with a 2025 list on file have no tracker row, and 10 towns the tracker marks as having sent a list don't have that list among the saved files.
- **One-pass OCR.** Atlantic City's scanned abandoned-property list yielded 73 parcels (some rows unreadable; addresses come from the parcel layer). Commercial Township's scanned registration wasn't parsed. A rotated Bergenfield scan yielded 8 addresses.
- **156 properties have no point**, mostly South Brunswick commercial suites and Franklin Township structures listed by street only.
- **Barnegat** rows keep the source block/lot as written, including suspected transcription errors flagged during the original review.
- **Northeast places are uneven.** OpenStreetMap coverage depends on who mapped where: brownfields cluster in a few cities, closed storefronts in places with active mappers, and Quebec and the Maritimes have far fewer tagged features than New York or Pennsylvania. Nova Scotia's count is high because the province publishes every known mine opening.
- **Sources lag.** Some places have since been reused, restored or demolished. Wikidata and OpenStreetMap are edited by volunteers, and MRDS was last updated in 2011.
- **Guesses are guesses.** An FCC registration going quiet is a weak signal, and plenty of those towers are still in service. Many military bunkers and batteries are now in parks. MRDS prospects are often just a pit or trench.
- **Mine points are approximate.** MRDS and MSHA coordinates are often rounded or placed at the claim rather than the opening.
- **No Canadian tower data.** The FCC guesses cover the US only, and so does the aerial imagery.
- **Left out on purpose (NJ):** tax-delinquency reports, code-violation and incident logs, 2017–2022 registration logs, files from an unrelated 2020 request, and requests to state agencies.
- Pine Valley (merged into Pine Hill in 2022) is dropped from the 2025 ledger.

## Rebuilding

Raw inputs aren't published. With them in local folders:

```
# NJ records
RAW=/path/to/responses OCR=/path/to/ocr_text python scripts/parse_lists.py
python scripts/geocode.py
OPRA_SENDERS=you@example.com WORK=/path/to/work python scripts/build_requests.py
python scripts/build_tracts.py

# Northeast places
python scripts/ne_extract.py us-northeast.osm.pbf us-northeast osm_out   # repeat per extract:
#   maryland, delaware, district-of-columbia, new-jersey, quebec, new_brunswick, nova_scotia, prince_edward_island
python scripts/wd.py wd_out
OSM_OUT=osm_out WD_DIR=wd_out MINES=/path/to/mines FCC_DIR=/path/to/r_tower \
  STATES=us_states.geojson python scripts/build_northeast.py
```

Inputs for `build_northeast.py`:

- OpenStreetMap extracts: <https://download.openstreetmap.fr/extracts/north-america/> (`us-northeast`, the four smaller US extracts, and `canada/quebec`, `canada/new_brunswick`, `canada/nova_scotia`, `canada/prince_edward_island`).
- `MINES/mrds.csv`: USGS MRDS CSV, <https://mrdata.usgs.gov/mrds/>.
- `MINES/Mines.txt`: MSHA Mines data set, <https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp>.
- `MINES/qc_*.csv`: Quebec orphaned and abandoned mines, <https://www.donneesquebec.ca/recherche/dataset/initiative-nationale-pour-les-mines-orphelines-ou-abandonnees>.
- `MINES/ns/…/d010nssh.shp`: Nova Scotia Abandoned Mine Openings, <https://novascotia.ca/natr/meb/download/dp010dds.asp>.
- `FCC_DIR`: unzipped `r_tower.zip` (Antenna Structure Registration full database), <https://www.fcc.gov/uls/transactions/daily-weekly>.
- `STATES`: TIGERweb state outlines for MD, DE, DC, PA, NJ, NY, CT, RI, MA, VT, NH and ME as GeoJSON with a `STUSAB` property.

Python packages: `pandas`, `openpyxl`, `pdfplumber`, `osmium`, `shapely`, `pyshp`.

## License

- NJ records data (`data/requests.csv`, `data/properties.*`, `data/vacancy_tracts.geojson`, `data/municipalities.json`): CC0 1.0.
- `data/ne/places.*` and `data/ne/rail.json` contain OpenStreetMap data and are under the Open Database License (ODbL) 1.0, © OpenStreetMap contributors. Rows from other sources keep their own terms: Wikidata CC0; USGS MRDS, MSHA and FCC public domain; Quebec rows © Gouvernement du Québec, CC BY 4.0; Nova Scotia rows contain information licensed under the Open Government Licence – Nova Scotia.
- Code: MIT (see `LICENSE`).
- Parcel geometry and municipal boundaries: NJOGIS. Census figures: US Census Bureau ACS. Basemap: OpenFreeMap, © OpenMapTiles, © OpenStreetMap contributors. Aerial imagery: USGS The National Map.
