"""Fetch Wikidata items in each Northeast region that are closed, decommissioned, abandoned or out of service,
plus ghost towns, ruins and abandoned villages. Demolished items and items marked in use are excluded.

    python wd.py [outdir]        # writes <outdir>/<REGION>.json (default: ./wd)

Wikidata is CC0. Results feed build_northeast.py via WD_DIR.
"""
import json, os, sys, time, urllib.parse, urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else 'wd'
R = {'MD': 'Q1391', 'DE': 'Q1393', 'DC': 'Q61', 'PA': 'Q1400', 'NJ': 'Q1408', 'NY': 'Q1384', 'CT': 'Q779', 'RI': 'Q1387',
     'MA': 'Q771', 'VT': 'Q16551', 'NH': 'Q759', 'ME': 'Q724', 'QC': 'Q176', 'NB': 'Q1965', 'NS': 'Q1952', 'PE': 'Q1978'}
# P5817 state of use: permanently closed, decommissioned, abandoned, out of service.
# P31 instance of: ghost town, ruins, abandoned village. Excluded: demolished (Q56556915), in use (Q55654238).
Q = '''SELECT DISTINCT ?item ?itemLabel ?stateLabel ?typeLabel ?coord ?end WHERE {
  { VALUES ?state { wd:Q104664889 wd:Q11639308 wd:Q63065035 wd:Q56651571 } ?item wdt:P5817 ?state . }
  UNION { VALUES ?type0 { wd:Q74047 wd:Q109607 wd:Q15641138 } ?item wdt:P31 ?type0 . BIND(?type0 AS ?state) }
  ?item wdt:P131* wd:%s ; wdt:P625 ?coord .
  FILTER NOT EXISTS { ?item wdt:P5817 wd:Q56556915 }
  FILTER NOT EXISTS { ?item wdt:P5817 wd:Q55654238 }
  OPTIONAL { ?item wdt:P31 ?type . }
  OPTIONAL { ?item wdt:P576 ?end . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr". } }'''

os.makedirs(OUT, exist_ok=True)
for code, q in R.items():
    fp = os.path.join(OUT, f'{code}.json')
    if os.path.exists(fp): continue
    for attempt in range(3):
        try:
            req = urllib.request.Request('https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': Q % q}),
                                         headers={'Accept': 'application/sparql-results+json',
                                                  'User-Agent': 'vap-archive/1.0 (github.com/myceliation/vap)'})
            data = urllib.request.urlopen(req, timeout=180).read()
            open(fp, 'wb').write(data)
            print(code, len(json.loads(data)['results']['bindings']), flush=True)
            break
        except Exception as e:
            print(code, 'retry', e, flush=True); time.sleep(10)
    time.sleep(2)
