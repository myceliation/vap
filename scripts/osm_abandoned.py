"""Extract abandoned / disused / ruined places in New Jersey from an OpenStreetMap extract.

Input:  a Geofabrik new-jersey-latest.osm.pbf (not published; ~160 MB)
Output: data/work/osm_places.csv  (one point per feature; ways/areas -> centroid of their nodes)
        data/work/osm_rail.geojson (abandoned/disused rail lines that aren't rail-trails, simplified)

Data (c) OpenStreetMap contributors, ODbL 1.0. Anything derived from this file stays ODbL.
"""
import csv, json, os, sys
import osmium

PBF = sys.argv[1] if len(sys.argv) > 1 else 'new-jersey-latest.osm.pbf'
ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'data', 'work')

LIFECYCLE = ('abandoned:', 'disused:', 'ruins:', 'was:')
KINDKEYS = ('amenity', 'building', 'man_made', 'railway', 'military', 'industrial', 'historic', 'leisure', 'tourism',
            'shop', 'aeroway', 'power', 'landuse', 'office', 'craft', 'healthcare', 'bridge', 'tower:type', 'religion')

def lifecycle_kind(tags):
    for k, v in tags:
        for p in LIFECYCLE[:3]:
            if k.startswith(p) and k[len(p):] in KINDKEYS:
                return p.rstrip(':'), f'{k[len(p):]}={v}'
    return None

def classify(tags):
    t = dict(tags)
    lc = lifecycle_kind(tags)
    if lc: return lc[0], lc[1]
    if t.get('railway') in ('abandoned', 'disused') and 'highway' not in t:
        return t['railway'], 'railway=' + t['railway']
    if t.get('historic') == 'ruins' or t.get('ruins') == 'yes' or t.get('building') == 'ruins':
        what = next((f'{k}={t[k]}' for k in ('ruins:building', 'historic:building', 'building', 'man_made', 'amenity') if k in t and t[k] not in ('yes', 'ruins')), '')
        return 'ruins', what or 'ruins'
    if t.get('building') in ('abandoned', 'disused'):
        return t['building'], 'building'
    if t.get('abandoned') == 'yes' or t.get('disused') == 'yes':
        state = 'abandoned' if t.get('abandoned') == 'yes' else 'disused'
        what = next((f'{k}={t[k]}' for k in KINDKEYS if k in t), '')
        return state, what
    if t.get('landuse') == 'brownfield':
        return 'brownfield', 'landuse=brownfield'
    return None

class H(osmium.SimpleHandler):
    def __init__(self):
        super().__init__(); self.rows = []; self.rail = []
    def _row(self, kind, oid, tags, lat, lon):
        c = classify(tags)
        if not c: return
        t = dict(tags)
        if c[1].startswith('railway=') and kind == 'way':
            return  # rail lines handled separately
        self.rows.append(dict(osm_type=kind, osm_id=oid, state=c[0], what=c[1],
                              name=t.get('name') or t.get('old_name') or t.get('was:name') or '',
                              start=t.get('start_date', ''), end=t.get('end_date', '') or t.get('abandoned:date', '') or t.get('disused:date', ''),
                              lat=f'{lat:.6f}', lon=f'{lon:.6f}'))
    def node(self, n):
        if len(n.tags) and n.location.valid():
            self._row('node', n.id, [(t.k, t.v) for t in n.tags], n.location.lat, n.location.lon)
    def way(self, w):
        if not len(w.tags): return
        tags = [(t.k, t.v) for t in w.tags]
        c = classify(tags)
        if not c: return
        pts = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
        if not pts: return
        if c[1].startswith('railway=') and not w.is_closed():
            step = max(1, len(pts) // 25)
            line = pts[::step] + ([pts[-1]] if pts[-1] != pts[::step][-1] else [])
            t = dict(tags)
            self.rail.append({'type': 'Feature', 'properties': {'name': t.get('name', ''), 'state': c[0], 'osm': f'way/{w.id}'},
                              'geometry': {'type': 'LineString', 'coordinates': [[round(lo, 5), round(la, 5)] for la, lo in line]}})
            return
        lat = sum(p[0] for p in pts) / len(pts); lon = sum(p[1] for p in pts) / len(pts)
        self._row('way', w.id, tags, lat, lon)

h = H()
h.apply_file(PBF, locations=True, idx='flex_mem')
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, 'osm_places.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['osm_type', 'osm_id', 'state', 'what', 'name', 'start', 'end', 'lat', 'lon'])
    w.writeheader(); w.writerows(h.rows)
json.dump({'type': 'FeatureCollection', 'features': h.rail}, open(os.path.join(OUT, 'osm_rail.geojson'), 'w'), separators=(',', ':'))
print('places', len(h.rows), 'rail lines', len(h.rail))
