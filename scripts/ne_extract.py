"""Low-memory extractor: abandoned / disused / ruined / closed places, mines and abandoned rail
from one Geofabrik .osm.pbf extract.

    python ne_extract.py <file.osm.pbf> <region-name> <outdir>

Writes <outdir>/osm_<region>.csv (one row per feature, point = node or centroid of a way/relation)
and <outdir>/rail_<region>.json (simplified abandoned/disused rail lines).
Three passes keep memory small: tagged objects, then member ways of matching relations, then only
the nodes needed for geometry. Data (c) OpenStreetMap contributors, ODbL 1.0.
"""
import csv, json, os, re, sys, time
import osmium
from osmium.filter import EmptyTagFilter, IdFilter

PBF, REGION, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)

LIFE = ('abandoned:', 'disused:', 'ruins:')
SKIP_LIFE = ('abandoned:highway', 'disused:highway', 'abandoned:route', 'disused:route', 'abandoned:power', 'disused:power',
             'abandoned:barrier', 'disused:barrier', 'abandoned:addr', 'disused:addr', 'abandoned:name', 'disused:name')
HIST = {'ruins', 'mine', 'mine_shaft', 'mine_adit', 'adit', 'wreck', 'aircraft_wreck', 'fort', 'battery', 'bunker', 'military',
        'kiln', 'lime_kiln', 'charcoal_pile', 'furnace', 'blast_furnace', 'industrial', 'quarry', 'tank', 'abandoned_village',
        'ghost_town', 'mill', 'watermill', 'creamery', 'iron_works', 'mining', 'mine_entrance', 'shaft'}
BUILD = {'ruins', 'abandoned', 'disused', 'collapsed'}
MANMADE = {'adit', 'mineshaft', 'mine', 'mine_shaft'}
MIL = {'bunker', 'launchpad', 'battery', 'trench', 'barracks', 'range', 'checkpoint', 'obstacle_course'}
NAME_RX = re.compile(r'\b(abandoned|derelict|ruins?|old .*(hospital|sanatorium|asylum|prison|school|mill|factory|mine|quarry)|'
                     r'former .*(base|plant|hospital|school|prison|mine|quarry|factory|mill)|nike|missile|launch site|radar site|'
                     r'coast artillery|gun emplacement)\b', re.I)
GOLF = re.compile(r'fairway|greenside|\bhole\b|\bsand trap\b|\bgolf\b|\btee\b', re.I)
DROP_KEYS = ('addr:', 'source', 'tiger:', 'gnis:', 'note', 'fixme', 'FIXME', 'NHD', 'nhd', 'massgis', 'lacounty', 'ref:', 'check_date',
             'wikipedia', 'canvec', 'geobase', 'osak:', 'it:fvg', 'yh:', 'NJDOT', 'nysgissam')

def why(t):
    """Return a short reason string if this object should be kept, else None."""
    if 'highway' in t and not any(k in t for k in ('building', 'historic', 'man_made', 'ruins', 'military')):
        return None
    if t.get('golf') or t.get('natural') == 'sand':
        return None
    r = t.get('railway')
    if r in ('abandoned', 'disused'): return 'rail'
    for k in t:
        if k.startswith(LIFE) and not k.startswith(SKIP_LIFE): return 'life'
    if t.get('abandoned') == 'yes' or t.get('disused') == 'yes' or t.get('ruins') == 'yes': return 'flag'
    if t.get('historic') in HIST: return 'historic'
    if t.get('building') in BUILD: return 'building'
    if t.get('man_made') in MANMADE: return 'mine'
    if t.get('landuse') == 'brownfield': return 'brownfield'
    if t.get('military') in MIL: return 'military'
    if t.get('shop') == 'vacant': return 'vacant_shop'
    n = t.get('name', '')
    if n and NAME_RX.search(n) and not GOLF.search(n) and 'shop' not in t and 'brand' not in t: return 'name'
    return None

def keep_tags(t):
    return {k: v[:120] for k, v in t.items() if not k.startswith(DROP_KEYS)}

t0 = time.time()
nodes, ways, rels = [], {}, {}
for o in osmium.FileProcessor(PBF).with_filter(EmptyTagFilter()):
    tags = o.tags
    # cheap pre-check before building a dict
    hit = False
    for tg in tags:
        k = tg.k
        if (k.startswith(LIFE) or k in ('railway', 'abandoned', 'disused', 'ruins', 'historic', 'building', 'man_made', 'landuse',
                                        'military', 'shop', 'name')):
            hit = True; break
    if not hit: continue
    t = {tg.k: tg.v for tg in tags}
    w = why(t)
    if not w: continue
    if o.is_node():
        if w == 'rail' and t.get('railway') in ('abandoned', 'disused') and len(t) <= 2: continue
        nodes.append((o.id, o.location.lat, o.location.lon, w, t))
    elif o.is_way():
        refs = [n.ref for n in o.nodes]
        ways[o.id] = (refs, w, t, refs[0] == refs[-1])
    elif o.is_relation():
        mem = [m.ref for m in o.members if m.type == 'w']
        if mem: rels[o.id] = (mem, w, t)
print(REGION, 'pass1', len(nodes), len(ways), len(rels), f'{time.time()-t0:.0f}s', flush=True)

need_w = set(m for v in rels.values() for m in v[0][:60]) - set(ways)
member = {}
if need_w:
    for o in osmium.FileProcessor(PBF, osmium.osm.WAY).with_filter(IdFilter(need_w)):
        member[o.id] = [n.ref for n in o.nodes]

def sample(refs, k):
    if len(refs) <= k: return refs
    step = len(refs) / k
    return [refs[int(i * step)] for i in range(k)] + [refs[-1]]

need_n = set()
for wid, (refs, w, t, closed) in ways.items():
    need_n.update(sample(refs, 40 if w == 'rail' else 16))
for mem, w, t in rels.values():
    for m in mem[:60]:
        refs = ways[m][0] if m in ways else member.get(m, [])
        need_n.update(sample(refs, 6))
loc = {}
if need_n:
    for o in osmium.FileProcessor(PBF, osmium.osm.NODE).with_filter(IdFilter(need_n)):
        if o.location.valid(): loc[o.id] = (o.location.lat, o.location.lon)
print(REGION, 'pass3 nodes', len(loc), f'{time.time()-t0:.0f}s', flush=True)

def centroid(refs):
    pts = [loc[r] for r in refs if r in loc]
    if not pts: return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

rows, rail = [], []
for nid, lat, lon, w, t in nodes:
    rows.append(('n', nid, w, f'{lat:.6f}', f'{lon:.6f}', json.dumps(keep_tags(t), ensure_ascii=False)))
for wid, (refs, w, t, closed) in ways.items():
    if w == 'rail' and not closed:
        pts = [loc[r] for r in sample(refs, 40) if r in loc]
        if len(pts) >= 2:
            rail.append({'n': t.get('name', ''), 's': t.get('railway'), 'id': wid, 'c': [[round(p[1], 5), round(p[0], 5)] for p in pts]})
        continue
    c = centroid(sample(refs, 16))
    if c: rows.append(('w', wid, w, f'{c[0]:.6f}', f'{c[1]:.6f}', json.dumps(keep_tags(t), ensure_ascii=False)))
for rid, (mem, w, t) in rels.items():
    refs = []
    for m in mem[:60]:
        refs += sample(ways[m][0] if m in ways else member.get(m, []), 6)
    c = centroid(refs)
    if c: rows.append(('r', rid, w, f'{c[0]:.6f}', f'{c[1]:.6f}', json.dumps(keep_tags(t), ensure_ascii=False)))

with open(os.path.join(OUT, f'osm_{REGION}.csv'), 'w', newline='', encoding='utf-8') as f:
    cw = csv.writer(f); cw.writerow(['osm_type', 'osm_id', 'why', 'lat', 'lon', 'tags']); cw.writerows(rows)
json.dump(rail, open(os.path.join(OUT, f'rail_{REGION}.json'), 'w'), separators=(',', ':'))
print(REGION, 'done', len(rows), 'features', len(rail), 'rail', f'{time.time()-t0:.0f}s', flush=True)
