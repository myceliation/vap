# NJ Vacant & Abandoned Property (VAP) records — archive

**Status: archived (October 1, 2026). Not maintained.**
Live page: <https://myceliation.github.io/vap/>

A snapshot of what New Jersey municipalities sent back when asked, under the Open Public Records Act (OPRA), for their lists of vacant, abandoned and foreclosed properties. The page maps two things: how each town answered, and the properties on the lists that came back.

Being on a list does not mean a property is vacant today. Many entries are foreclosure registrations on occupied homes, and lists go stale fast. Don't trespass.

## Counts

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
| Properties in `properties.csv` | 2,509 | 63 | 2,572 (30 municipalities) |
| Properties with a map point | | | 2,416 |

Median time to a substantive reply in 2026: 6 days.

## Method

1. **Requests.** Spring 2025: requests sent by hand, mostly to South Jersey towns, tracked in a spreadsheet without dates. May–June 2026: an automated email to nearly every municipal clerk asking for (1) the vacant/abandoned/foreclosed-property registry, (2) unsafe-structure and condemnation orders from the last 24 months, and (3) residential water shutoffs of 12+ months.
2. **Outcomes.** 2026 outcomes were classified from the subject and preview text of every reply (`scripts/build_requests_2026.py`), then corrected using the written-denial and portal-refusal calls recorded during the project. 2025 outcomes come from the hand-kept tracker.
3. **Lists.** Spreadsheets, text PDFs, Word files and reply-email bodies were parsed (`scripts/parse_lists.py`). Scanned PDFs got one OCR pass (tesseract). Block and lot were normalized: leading zeros stripped, all-zero decimals dropped, condo qualifiers (e.g. `C0214`) kept in their own column.
4. **Location.** Each property was joined to the NJOGIS *Parcels and MOD-IV Composite of NJ* layer on `PAMS_PIN` = `muni_code_block_lot[_qualifier]` and placed at the parcel centroid. Rows without block/lot were matched by street address inside the same municipality; the rest went to the US Census batch geocoder and were kept only if they landed within 12 km of the town (`scripts/geocode.py`). Responses are cached and requests throttled.
5. **Privacy.** Only the normalized CSVs are published. Owner names, registrant/servicer names, custodian names, emails, phone numbers and correspondence text are dropped. Raw PDFs and spreadsheets are not in this repo.

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
| abandonment_score | Likelihood call carried over from the project's review (Barnegat only): `Very likely`, `Likely`, `Possible`, `Unlikely` |
| listed_status | What kind of list and what it said (e.g. `foreclosure registration: Registered`, `abandoned structure list; aband`) |
| geocode_method | `njogis_parcel`, `njogis_address`, `census`, or `unresolved` |
| round | Request round the list came from |
| lat, lon | WGS84 point (blank when unresolved) |

`data/properties.geojson` holds the same rows that have a point. `data/municipalities.json` holds municipal centroids (NJOGIS) for the request layer.

## Known gaps

- **2026 attachments weren't processed.** About 200 towns sent their 2026 records as attachments (`notes` = `records attached, not parsed`). Those lists were never downloaded or parsed, so 2026 contributes only lists that came in the email body plus the Barnegat registry.
- **2026 outcomes are approximate.** They come from reply previews, not full reads. `fulfilled` means records came back, not that they were a vacancy list; several are code-enforcement or water reports.
- **2025 round has no dates** and was sent from several email accounts, so the tracker is incomplete; 7 towns with a 2025 list on file have no tracker row, and 10 towns the tracker marks as having sent a list don't have that list among the saved files.
- **One-pass OCR.** Atlantic City's scanned abandoned-property list yielded 73 parcels (some rows unreadable; addresses come from the parcel layer). Commercial Township's scanned registration wasn't parsed. A rotated Bergenfield scan yielded 8 addresses.
- **156 properties have no point**, mostly South Brunswick commercial suites and Franklin Township structures listed by street only.
- **Barnegat** rows keep the source block/lot as written, including suspected transcription errors flagged during the original review.
- **Left out on purpose:** tax-delinquency reports, code-violation and incident logs, 2017–2022 registration logs, files from an unrelated 2020 request, and requests to state agencies.
- Pine Valley (merged into Pine Hill in 2022) is dropped from the 2025 ledger.

## Rebuilding

Raw inputs aren't published. With them in local folders:

```
RAW=/path/to/responses OCR=/path/to/ocr_text python scripts/parse_lists.py
python scripts/geocode.py
OPRA_SENDERS=you@example.com WORK=/path/to/work python scripts/build_requests.py
```

## License

Data (`data/`): CC0 1.0. Code: MIT (see `LICENSE`). Parcel geometry: NJOGIS. Basemap: © OpenStreetMap contributors.
