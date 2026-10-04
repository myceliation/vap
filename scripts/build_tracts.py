"""Census tracts with 'other vacant' housing for New Jersey -> data/vacancy_tracts.geojson.

Source: ACS 2018-2022 5-year table B25004 via Esri Living Atlas
(ACS_Housing_Units_Vacancy_Status_Boundaries, tract layer). 'Other vacant' (B25004_008) counts homes that are
vacant but not for rent, for sale, seasonal or migrant use. Responses are cached in data/cache/acs/.
"""
import glob, json, os, time, urllib.parse, urllib.request
from shapely.geometry import shape

ROOT = os.path.join(os.path.dirname(__file__), '..')
CACHE = os.path.join(ROOT, 'data', 'cache', 'acs'); os.makedirs(CACHE, exist_ok=True)
URL = 'https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/ACS_Housing_Units_Vacancy_Status_Boundaries/FeatureServer/2/query'

off = 0
while True:
    fp = os.path.join(CACHE, f'tracts_{off:05d}.geojson')
    if not os.path.exists(fp):
        qs = urllib.parse.urlencode({'where': "GEOID LIKE '34%'", 'outFields': 'GEOID,NAME,B25002_001E,B25004_001E,B25004_006E,B25004_008E,B25004_008M',
                                     'returnGeometry': 'true', 'outSR': '4326', 'maxAllowableOffset': '0.0012', 'geometryPrecision': '4',
                                     'resultOffset': off, 'resultRecordCount': 50, 'orderByFields': 'GEOID', 'f': 'geojson'})
        with urllib.request.urlopen(URL + '?' + qs, timeout=120) as r: open(fp, 'wb').write(r.read())
        time.sleep(0.3)
    n = len(json.load(open(fp)).get('features', []))
    if n < 50: break
    off += 50

feats = []
for fp in sorted(glob.glob(os.path.join(CACHE, 'tracts_*.geojson'))):
    for f in json.load(open(fp))['features']:
        p = f['properties']; u = p.get('B25002_001E') or 0; ov = p.get('B25004_008E') or 0
        g = shape(f['geometry']).simplify(0.0018, preserve_topology=True)
        gj = json.loads(json.dumps(g.__geo_interface__), parse_float=lambda x: round(float(x), 4))
        feats.append({'type': 'Feature', 'geometry': gj, 'properties': {
            'geoid': p['GEOID'], 'units': u, 'other_vacant': ov, 'moe': p.get('B25004_008M'), 'seasonal': p.get('B25004_006E') or 0,
            'pct': round(100 * ov / u, 1) if u else None}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(ROOT, 'data', 'vacancy_tracts.geojson'), 'w'), separators=(',', ':'))
print('tracts', len(feats))
