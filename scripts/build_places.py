"""Build the 'other abandoned places' layers.

  data/places.csv          one row per place: mapped (a public source says abandoned/disused/ruined)
                           or inferred (a signal suggests it might be)
  data/places.geojson      same rows as points
  data/rail.geojson        abandoned / disused rail lines (OpenStreetMap)
  data/vacancy_tracts.geojson  census tracts with 'other vacant' housing (ACS 2018-2022)

Sources
  OpenStreetMap (ODbL 1.0)  -> data/work/osm_places.csv, osm_military.csv, osm_rail.geojson (see osm_*.py)
  Wikidata (CC0)            -> data/cache/wikidata.json (query in this file)
  FCC Antenna Structure Registration (public domain) -> FCC_DIR with RA.dat, CO.dat, HS.dat (r_tower.zip)
  ACS 5-year B25004 via Esri Living Atlas -> data/cache/acs/
  NJOGIS municipal boundaries -> data/cache/munis/
Owner, contact and signature names in the FCC files are never read into the output.
"""
import csv, glob, json, math, os, re, sys, urllib.parse, urllib.request
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

ROOT = os.path.join(os.path.dirname(__file__), '..')
D = lambda *p: os.path.join(ROOT, 'data', *p)
FCC_DIR = os.environ.get('FCC_DIR', '/home/claude/vapwork/fcc')
FIELDS = ['category', 'basis', 'name', 'kind', 'status', 'county', 'municipality', 'source', 'link', 'note', 'lat', 'lon']

# ---------- municipality lookup ----------
munis = []
for fp in sorted(glob.glob(D('cache', 'munis', '*.geojson'))):
    for f in json.load(open(fp))['features']:
        p = f['properties']; munis.append((shape(f['geometry']), p['MUN_LABEL'], p['COUNTY'].title()))
tree = STRtree([m[0] for m in munis])
def where(lat, lon):
    pt = Point(float(lon), float(lat))
    for i in tree.query(pt):
        if munis[i][0].contains(pt): return munis[i][2], munis[i][1]
    return '', ''

ROWS = []
def add(**kw):
    c, m = where(kw['lat'], kw['lon'])
    if not c: return  # outside NJ
    kw.update(county=c, municipality=m)
    ROWS.append({k: kw.get(k, '') for k in FIELDS})

# ---------- OpenStreetMap: tagged abandoned / disused / ruins ----------
DROP_KEYS = ('shop=', 'office=', 'craft=', 'healthcare=', 'tourism=information', 'highway=', 'barrier=', 'entrance=')
DROP = {'amenity=restaurant', 'amenity=fast_food', 'amenity=cafe', 'amenity=bar', 'amenity=pub', 'amenity=bank', 'amenity=pharmacy',
        'amenity=car_wash', 'amenity=atm', 'amenity=vending_machine', 'amenity=post_box', 'amenity=telephone', 'amenity=bench',
        'amenity=toilets', 'amenity=parking', 'amenity=bicycle_rental', 'amenity=ice_cream', 'amenity=dentist', 'amenity=doctors',
        'amenity=veterinary', 'amenity=marketplace', 'amenity=drinking_water', 'amenity=shelter', 'amenity=waste_basket',
        'amenity=car_rental', 'amenity=post_office', 'amenity=clinic', 'amenity=childcare', 'amenity=kindergarten',
        'railway=level_crossing', 'railway=crossing', 'railway=junction', 'railway=switch', 'railway=signal', 'railway=buffer_stop',
        'railway=crossover', 'railway=milestone', 'railway=railway_crossing', 'aeroway=taxiway', 'aeroway=apron', 'aeroway=windsock',
        'man_made=monitoring_station', 'man_made=survey_point', 'man_made=flagpole', 'man_made=street_cabinet', 'man_made=water_well',
        'man_made=manhole', 'man_made=pipeline', 'man_made=embankment', 'man_made=cutline', 'man_made=clearcut',
        'leisure=pitch', 'leisure=playground', 'leisure=picnic_table', 'leisure=park', 'leisure=garden', 'leisure=dog_park',
        'power=pole', 'power=tower', 'power=line', 'power=minor_line', 'power=portal', 'power=switch', 'power=transformer',
        'power=generator', 'power=cable', 'landuse=recreation_ground', 'landuse=grass', 'landuse=farmland', 'landuse=meadow'}

def osm_category(what, name):
    w = what
    if w.startswith(('man_made=tower', 'man_made=mast', 'man_made=communications_tower', 'tower:type')): return 'Towers & masts'
    if w.startswith(('military=', 'building=bunker')): return 'Military & Cold War'
    if w.startswith(('power=', 'man_made=', 'industrial=', 'building=storage_tank', 'building=industrial', 'building=factory',
                     'building=warehouse', 'building=silo', 'landuse=industrial', 'landuse=quarry')) and w != 'man_made=pier': return 'Industrial & utility'
    if w.startswith(('railway=', 'aeroway=', 'bridge', 'man_made=pier', 'amenity=ferry_terminal', 'building=train_station', 'public_transport')):
        return 'Rail & transport'
    if re.search(r'hospital|school|college|university|place_of_worship|church|fire_station|police|prison|townhall|library|courthouse|community_centre|monastery|chapel', w):
        return 'Institutions'
    if re.search(r'cinema|theatre|zoo|amusement|swimming|stadium|sports_centre|leisure=|nightclub|casino|marina|water_park|resort|hotel|motel', w):
        return 'Leisure & lodging'
    return 'Other buildings & sites'

def nice(what):
    if not what: return ''
    k, _, v = what.partition('=')
    return (v if v and v not in ('yes',) else k).replace('_', ' ')

osm = list(csv.DictReader(open(D('work', 'osm_places.csv'))))
for r in osm:
    w = r['what']
    if r['state'] == 'brownfield':
        cat = 'Brownfields'
    else:
        if w in DROP or w.startswith(DROP_KEYS): continue
        if w == '' and not r['name']: continue
        if w == '' and re.search(r'\b(road|rd|drive|dr|lane|ln|street|st|avenue|ave|trail|path|way)\b', r['name'], re.I): continue
        cat = 'Ruins' if r['state'] == 'ruins' else osm_category(w, r['name'])
    status = {'abandoned': 'tagged abandoned', 'disused': 'tagged disused', 'ruins': 'tagged ruins', 'brownfield': 'brownfield land',
              'railway': 'tagged abandoned'}.get(r['state'], r['state'])
    note = ' · '.join(x for x in [f"built {r['start']}" if r['start'] else '', f"closed {r['end']}" if r['end'] else ''] if x)
    add(category=cat, basis='mapped', name=r['name'], kind=nice(w) or ('brownfield' if cat == 'Brownfields' else ''), status=status,
        source='OpenStreetMap', link=f"https://www.openstreetmap.org/{r['osm_type']}/{r['osm_id']}", note=note, lat=r['lat'], lon=r['lon'])

# Cold War / military + names that say abandoned
NOISE = re.compile(r'fairway|greenside|\bhole\b|bunker hill|battery maritime|\b(drive|road|rd|lane|ln|street|st|avenue|ave|trail|path|pond|park|place|court|ct|way)\b$|shoppe|^ye old|old mill pond|environmental center', re.I)
for r in csv.DictReader(open(D('work', 'osm_military.csv'))):
    if r['name'] and NOISE.search(r['name']): continue
    if r['why'] == 'name' and not r['name']: continue
    if r['group'] == 'military':
        add(category='Military & Cold War', basis='inferred', name=r['name'], kind=(r['why'].split('=')[-1] if r['why'] != 'name' else 'named site').replace('_', ' '),
            status='military/Cold War site; current use unknown', source='OpenStreetMap',
            link=f"https://www.openstreetmap.org/{r['osm_type']}/{r['osm_id']}", note=r['tags'].replace(';', ' · '), lat=r['lat'], lon=r['lon'])
    else:
        add(category='Other buildings & sites', basis='inferred', name=r['name'], kind='named site', status='name says former/abandoned',
            source='OpenStreetMap', link=f"https://www.openstreetmap.org/{r['osm_type']}/{r['osm_id']}", note=r['tags'].replace(';', ' · '), lat=r['lat'], lon=r['lon'])

# ---------- Wikidata ----------
WD_QUERY = '''SELECT DISTINCT ?item ?itemLabel ?stateLabel ?typeLabel ?coord ?end WHERE {
  { VALUES ?state { wd:Q104664889 wd:Q11639308 wd:Q63065035 wd:Q56651571 } ?item wdt:P5817 ?state . }
  UNION { VALUES ?type0 { wd:Q74047 wd:Q109607 wd:Q15641138 wd:Q2338524 } ?item wdt:P31 ?type0 . BIND(?type0 AS ?state) }
  ?item wdt:P131* wd:Q1408 ; wdt:P625 ?coord .
  FILTER NOT EXISTS { ?item wdt:P5817 wd:Q56556915 }
  FILTER NOT EXISTS { ?item wdt:P5817 wd:Q55654238 }
  OPTIONAL { ?item wdt:P31 ?type . }
  OPTIONAL { ?item wdt:P576 ?end . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }'''
wdp = D('cache', 'wikidata.json')
if not os.path.exists(wdp):
    req = urllib.request.Request('https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': WD_QUERY}),
                                 headers={'Accept': 'application/sparql-results+json', 'User-Agent': 'vap-archive/1.0 (github.com/myceliation/vap)'})
    with urllib.request.urlopen(req, timeout=180) as r: open(wdp, 'wb').write(r.read())
items = {}
for b in json.load(open(wdp))['results']['bindings']:
    q = b['item']['value'].split('/')[-1]
    e = items.setdefault(q, dict(name=b['itemLabel']['value'], state=b.get('stateLabel', {}).get('value', ''), types=set(),
                                 coord=b['coord']['value'], end=b.get('end', {}).get('value', '')[:4]))
    if 'typeLabel' in b: e['types'].add(b['typeLabel']['value'])
WD_SKIP = {'protected area', 'museum', 'company'}
for q, e in items.items():
    if 'destroyed building or structure' in e['types'] or re.fullmatch(r'Q\d+', e['name']) or (e['types'] & WD_SKIP): continue
    if e['name'] in ('Port Imperial Street Circuit', 'Jukebox Radio'): continue
    m = re.match(r'Point\(([-\d\.]+) ([-\d\.]+)\)', e['coord'])
    if not m: continue
    t = e['types'] - {'unincorporated community'}
    kind = sorted(t)[0] if t else ''
    if 'ghost town' in e['types']: cat = 'Ghost towns'
    elif re.search(r'station|terminal|bridge|airport|aerodrome|railway|tram', ' '.join(e['types'])): cat = 'Rail & transport'
    elif re.search(r'theater|theatre|amusement|racing|concert|shopping', ' '.join(e['types'])): cat = 'Leisure & lodging'
    elif 'nuclear power plant' in e['types']: cat = 'Industrial & utility'
    else: cat = 'Other buildings & sites'
    add(category=cat, basis='mapped', name=e['name'], kind=kind, status=e['state'], source='Wikidata', link=f'https://www.wikidata.org/wiki/{q}',
        note=f"ended {e['end']}" if e['end'] else '', lat=f"{float(m.group(2)):.6f}", lon=f"{float(m.group(1)):.6f}")

# ---------- FCC antenna structures: theorized idle towers ----------
def dms(sec, hemi): return (-1 if hemi in ('S', 'W') else 1) * float(sec) / 3600
ra = {}
for line in open(os.path.join(FCC_DIR, 'RA.dat'), encoding='latin-1'):
    f = line.rstrip('\n').split('|')
    if len(f) > 32 and f[25] == 'NJ': ra[f[3]] = f
co = {}
for line in open(os.path.join(FCC_DIR, 'CO.dat'), encoding='latin-1'):
    f = line.rstrip('\n').split('|')
    if len(f) > 15 and f[3] in ra and f[5] == 'T' and f[10] and f[15]:
        co[f[3]] = (dms(f[10], f[9]), dms(f[15], f[14]))
STYPE = {'TOWER': 'tower', 'GTOWER': 'guyed tower', 'LTOWER': 'lattice tower', 'MTOWER': 'monopole',
         'POLE': 'pole', 'UPOLE': 'utility pole', 'MAST': 'mast', 'TANK': 'water tank', 'BANT': 'building with antenna',
         'B': 'building', 'BTWR': 'building with tower', 'RIG': 'oil/gas rig', 'TREE': 'disguised tree', 'SIGN': 'sign', 'NNTANN': 'antenna'}
def yr(s): return int(s[-4:]) if s and s[-4:].isdigit() else None
for reg, f in ra.items():
    st, built, last = f[8], f[12], f[14]
    if reg not in co: continue
    h = f[30] or f[28]
    try: hm = float(h)
    except: hm = 0
    if f[32] in ('BANT', 'B', 'TREE', 'SIGN', 'RIG') or hm < 30: continue   # only real freestanding structures ≥30 m
    why = None
    if st == 'T':
        why = 'FCC registration terminated; no dismantle notice on file'
    elif st == 'C' and yr(last) and yr(last) <= 2006:
        why = f'registration untouched since {yr(last)}'
    if not why: continue
    lat, lon = co[reg]
    add(category='Towers & masts', basis='inferred', name=f"ASR {reg}", kind=STYPE.get(f[32], f[32].lower() or 'structure'),
        status=why, source='FCC ASR',
        link=f'https://wireless2.fcc.gov/UlsApp/AsrSearch/asrRegistration.jsp?regKey={f[4]}',
        note=' · '.join(x for x in [f'{hm:.0f} m tall', f'built {yr(built)}' if yr(built) else '', (f[24] or '').title()] if x),
        lat=f'{lat:.6f}', lon=f'{lon:.6f}')

# ---------- de-duplicate (same name within ~150 m, or exact same point) ----------
def km(a, b):
    p = math.pi / 180
    return 6371 * 2 * math.asin(math.sqrt(math.sin((b[0] - a[0]) * p / 2) ** 2 + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin((b[1] - a[1]) * p / 2) ** 2))
out, seen = [], []
for r in sorted(ROWS, key=lambda r: (r['basis'] != 'mapped', r['source'] != 'Wikidata')):
    pt = (float(r['lat']), float(r['lon']))
    dup = any((r['name'] and s['name'] and r['name'].lower() == s['name'].lower() and km(pt, sp) < 0.15) or km(pt, sp) < 0.005 for s, sp in seen[-4000:])
    if dup: continue
    seen.append((r, pt)); out.append(r)
out.sort(key=lambda r: (r['county'], r['municipality'], r['category'], r['name']))
with open(D('places.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(out)
json.dump({'type': 'FeatureCollection', 'features': [
    {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [float(r['lon']), float(r['lat'])]},
     'properties': {k: r[k] for k in FIELDS if k not in ('lat', 'lon')}} for r in out]}, open(D('places.geojson'), 'w'), separators=(',', ':'))

# ---------- rail lines ----------
rail = json.load(open(D('work', 'osm_rail.geojson')))
json.dump(rail, open(D('rail.geojson'), 'w'), separators=(',', ':'))

# ---------- vacancy tracts ----------
feats = []
for fp in sorted(glob.glob(D('cache', 'acs', 'tracts_*.geojson'))):
    for f in json.load(open(fp))['features']:
        p = f['properties']; u = p.get('B25002_001E') or 0; ov = p.get('B25004_008E') or 0
        g = shape(f['geometry']).simplify(0.0018, preserve_topology=True)
        gj = json.loads(json.dumps(g.__geo_interface__), parse_float=lambda x: round(float(x), 4))
        feats.append({'type': 'Feature', 'geometry': gj, 'properties': {
            'geoid': p['GEOID'], 'units': u, 'other_vacant': ov, 'moe': p.get('B25004_008M'), 'seasonal': p.get('B25004_006E') or 0,
            'pct': round(100 * ov / u, 1) if u else None}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(D('vacancy_tracts.geojson'), 'w'), separators=(',', ':'))

import collections
print('places', len(out), collections.Counter((r['basis'], r['category']) for r in out).most_common())
print('rail', len(rail['features']), 'tracts', len(feats))
