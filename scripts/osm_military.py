"""Second OpenStreetMap pass: Cold War / military sites and features whose *name* says they're abandoned.

These are leads, not confirmed abandonments: many Nike bases are now parks, schools or DPW yards.
Output: data/work/osm_military.csv. Data (c) OpenStreetMap contributors, ODbL 1.0.
"""
import csv, os, re, sys
import osmium

PBF = sys.argv[1]
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'work', 'osm_military.csv')
NAME_HINT = re.compile(r'\b(abandoned|derelict|ruins?|old .*(hospital|sanatorium|asylum|prison|school|mill|factory)|former .*(base|plant|hospital|school|prison))\b', re.I)
NIKE = re.compile(r'\bnike\b|missile|launch (area|site)|radar site|\bbattery\b|gun emplacement|coast artillery|bunker', re.I)
GOLF = re.compile(r'fairway|greenside|\bhole\b|\bsand\b|\bgolf\b|\btee\b', re.I)

def pick(tags):
    t = dict(tags); name = t.get('name', '')
    if t.get('golf') or t.get('natural') == 'sand': return None
    if t.get('military') in ('bunker', 'launchpad', 'battery', 'trench') or t.get('historic') in ('fort', 'battery', 'bunker', 'military'):
        return 'military', f"military={t.get('military','')}" if 'military' in t else f"historic={t['historic']}"
    if name and GOLF.search(name) or t.get('golf') or t.get('natural') == 'sand': return None
    if name and NIKE.search(name) and ('shop' not in t and 'brand' not in t):
        return 'military', 'name'
    if name and NAME_HINT.search(name) and 'highway' not in t and 'shop' not in t:
        return 'named', 'name'
    return None

class H(osmium.SimpleHandler):
    def __init__(self): super().__init__(); self.rows = []
    def add(self, kind, oid, tags, lat, lon):
        p = pick(tags)
        if not p: return
        t = dict(tags)
        self.rows.append(dict(osm_type=kind, osm_id=oid, group=p[0], why=p[1], name=t.get('name', ''),
                              tags=';'.join(f'{k}={v}' for k, v in tags if k in ('military', 'historic', 'landuse', 'leisure', 'amenity', 'building', 'man_made', 'disused', 'abandoned'))[:160],
                              lat=f'{lat:.6f}', lon=f'{lon:.6f}'))
    def node(self, n):
        if len(n.tags) and n.location.valid(): self.add('node', n.id, [(t.k, t.v) for t in n.tags], n.location.lat, n.location.lon)
    def way(self, w):
        if not len(w.tags): return
        tags = [(t.k, t.v) for t in w.tags]
        if not pick(tags): return
        pts = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
        if pts: self.add('way', w.id, tags, sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

h = H(); h.apply_file(PBF, locations=True, idx='flex_mem')
with open(OUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['osm_type', 'osm_id', 'group', 'why', 'name', 'tags', 'lat', 'lon']); w.writeheader(); w.writerows(h.rows)
print('rows', len(h.rows))
