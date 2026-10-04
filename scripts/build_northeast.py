"""Build the Northeast abandoned-places layer (Maryland to Maine, plus Quebec and the Maritimes).

Outputs (published):
  data/ne/places.json   compact rows for the map
  data/ne/places.csv    the same rows, readable
  data/ne/rail.json     abandoned / disused rail lines (OpenStreetMap)

Inputs (local, not published; paths via env):
  OSM_OUT   folder of osm_<region>.csv / rail_<region>.json from ne_extract.py
  WD_DIR    Wikidata query results, one JSON per region (see wd.py in README)
  MINES     folder with USGS mrds.csv, MSHA Mines.txt, Quebec INMOA csv, Nova Scotia AMO shapefile
  FCC_DIR   unzipped FCC r_tower.zip
  STATES    us_states.geojson (TIGERweb, 12 states + DC)
Licenses: OpenStreetMap ODbL 1.0; Wikidata CC0; USGS, MSHA, FCC public domain; Quebec MRNF CC BY 4.0;
Nova Scotia Open Government Licence. Owner, operator and contact names are never read into the output.
"""
import csv, glob, json, math, os, re, sys, collections
import shapefile
from shapely.geometry import shape, Point, LineString
from shapely.strtree import STRtree

ROOT = os.path.join(os.path.dirname(__file__), '..')
OUTD = os.path.join(ROOT, 'data', 'ne'); os.makedirs(OUTD, exist_ok=True)
OSM_OUT = os.environ.get('OSM_OUT', '/home/claude/vapwork/osmne/out')
WD_DIR = os.environ.get('WD_DIR', '/home/claude/vapwork/ne/wd')
MINES = os.environ.get('MINES', '/home/claude/vapwork/mines')
FCC_DIR = os.environ.get('FCC_DIR', '/home/claude/vapwork/fcc')
STATES = os.environ.get('STATES', '/home/claude/vapwork/ne/us_states.geojson')

REGIONS = ['MD', 'DE', 'DC', 'PA', 'NJ', 'NY', 'CT', 'RI', 'MA', 'VT', 'NH', 'ME', 'QC', 'NB', 'NS', 'PE']
REGION_NAME = {'MD': 'Maryland', 'DE': 'Delaware', 'DC': 'District of Columbia', 'PA': 'Pennsylvania', 'NJ': 'New Jersey',
               'NY': 'New York', 'CT': 'Connecticut', 'RI': 'Rhode Island', 'MA': 'Massachusetts', 'VT': 'Vermont',
               'NH': 'New Hampshire', 'ME': 'Maine', 'QC': 'Quebec', 'NB': 'New Brunswick', 'NS': 'Nova Scotia',
               'PE': 'Prince Edward Island'}
CA_FILE = {'quebec': 'QC', 'new_brunswick': 'NB', 'nova_scotia': 'NS', 'prince_edward_island': 'PE'}
CATS = ['Mines & quarries', 'Ruins', 'Industrial & power', 'Military & Cold War', 'Rail & transport', 'Institutions',
        'Leisure & lodging', 'Towers & masts', 'Ghost towns', 'Wrecks', 'Brownfields', 'Other buildings & sites', 'Closed businesses']
SRCS = ['OpenStreetMap', 'Wikidata', 'USGS MRDS', 'MSHA', 'Quebec MRNF', 'Nova Scotia DNRR', 'FCC ASR']

# ---------- state lookup ----------
st_feats = json.load(open(STATES))['features']
st_geoms = [shape(f['geometry']) for f in st_feats]
st_codes = [f['properties']['STUSAB'] for f in st_feats]
st_tree = STRtree(st_geoms)
def us_state(lat, lon, slack=0.03):
    p = Point(lon, lat)
    for i in st_tree.query(p):
        if st_geoms[i].contains(p): return st_codes[i]
    for i in st_tree.query(p.buffer(slack)):
        if st_geoms[i].distance(p) <= slack: return st_codes[i]
    return None

ROWS = []
def add(lat, lon, cat, basis, region, src, name, kind, status, ref, note=''):
    ROWS.append([round(float(lon), 5), round(float(lat), 5), cat, basis, region, src, (name or '').strip()[:90],
                 (kind or '').strip()[:60], (status or '').strip()[:70], str(ref), (note or '').strip()[:90]])

def nice(v): return v.replace('_', ' ').replace(';', ', ') if v and v != 'yes' else ''

# ---------- OpenStreetMap ----------
LIFE = ('abandoned:', 'disused:', 'ruins:')
IGNORE_LIFE = re.compile(r'^(abandoned|disused|ruins):(name|old_name|addr|electrified|highway|route|golf|public_transport|'
                         r'barrier|entrance|emergency|natural|operator|brand|ref|website|phone|opening_hours|level|layer|'
                         r'tourism:information|railway:|footway|cycleway|access|bus|traffic|crossing|power:line)', re.I)
DROP_BASE = re.compile(r'^(railway=(level_crossing|crossing|rail|junction|switch|signal|buffer_stop|milestone|crossover|'
                       r'railway_crossing|platform|light_rail|tram|subway|narrow_gauge|preserved|spur|siding|derail|stop)|'
                       r'highway=|public_transport=|golf=|natural=|barrier=|entrance=|emergency=|'
                       r'amenity=(drinking_water|parking|parking_space|bench|waste_basket|telephone|post_box|vending_machine|atm|'
                       r'toilets|bicycle_parking|shelter|charging_station|recycling|fountain|waste_disposal|bbq|clock|'
                       r'parking_entrance|motorcycle_parking|loading_dock|letter_box|grit_bin|watering_place|water_point|hunting_stand)|'
                       r'leisure=(pitch|playground|picnic_table|park|garden|track|dog_park|fitness_station|firepit|slipway|bleachers)|'
                       r'aeroway=(taxiway|apron|windsock|holding_position|navigationaid|parking_position|gate)|'
                       r'man_made=(monitoring_station|survey_point|flagpole|street_cabinet|manhole|pipeline|water_well|embankment|'
                       r'cutline|clearcut|utility_pole|dyke|groyne|breakwater|petroleum_well|surveillance|bollard|marker|cairn)|'
                       r'power=(pole|tower|line|minor_line|portal|switch|transformer|cable|generator|catenary_mast|terminal|insulator)|'
                       r'landuse=(grass|farmland|meadow|recreation_ground|residential|commercial|retail|forest|orchard|farmyard|'
                       r'cemetery|construction|greenfield|landfill|village_green|allotments|basin|religious)|'
                       r'route=|waterway=(ditch|drain|stream|river|culvert|dam|weir)|tourism=(information|picnic_site|viewpoint|artwork)|'
                       r'historic=(tank|mill|watermill|creamery|memorial|monument|milestone|boundary_stone|marker|wayside_cross|'
                       r'railway_car|locomotive|aircraft|ship|cannon|district|citywalls|building|house|heritage|city_gate|church|'
                       r'archaeological_site|manor|farm|tomb|grave|highwater_mark|optical_telegraph|yes))', re.I)
MAIN_KEYS = ('amenity', 'shop', 'building', 'man_made', 'railway', 'military', 'industrial', 'historic', 'leisure', 'tourism',
             'aeroway', 'power', 'landuse', 'office', 'craft', 'healthcare', 'bridge', 'place', 'waterway', 'tower:type', 'mine', 'quarry')

def osm_base(t):
    """Pick (state, base 'key=value') for an OSM tag dict."""
    life = [(k, v) for k, v in t.items() if k.startswith(LIFE) and not IGNORE_LIFE.match(k)]
    for pref in ('abandoned:', 'disused:', 'ruins:'):
        for k, v in life:
            if k.startswith(pref) and k[len(pref):] in MAIN_KEYS:
                return pref.rstrip(':'), f'{k[len(pref):]}={v}'
    if t.get('abandoned') == 'yes' or t.get('disused') == 'yes':
        st = 'abandoned' if t.get('abandoned') == 'yes' else 'disused'
        for k in MAIN_KEYS:
            if k in t and not (k == 'building' and t[k] == 'yes' and any(x in t for x in MAIN_KEYS if x != 'building')):
                return st, f'{k}={t[k]}'
        return st, ''
    return None, ''

def osm_classify(t, why):
    name = t.get('name') or t.get('old_name') or t.get('was:name') or t.get('abandoned:name') or t.get('disused:name') or ''
    h, mm, lu = t.get('historic', ''), t.get('man_made', ''), t.get('landuse', '')
    if h in ('wreck', 'aircraft_wreck'):
        return 'Wrecks', ('aircraft wreck' if h == 'aircraft_wreck' else (nice(t.get('wreck:type', '')) or 'shipwreck')), 'historic wreck', 'mapped', name
    state, base = osm_base(t)
    bk, _, bv = base.partition('=')
    mine_hist = h in ('mine', 'mine_shaft', 'mine_adit', 'adit', 'mining', 'mine_entrance', 'shaft')
    mine_mm = mm in ('adit', 'mineshaft', 'mine', 'mine_shaft') or (bk == 'man_made' and bv in ('adit', 'mineshaft', 'mine', 'mine_shaft'))
    quarry = (lu == 'quarry' and state) or (bk == 'landuse' and bv == 'quarry') or (bk in ('industrial', 'mine', 'quarry') and bv in ('mine', 'quarry', 'yes'))
    if mine_hist or mine_mm or quarry:
        kind = nice(h if mine_hist else (mm or bv)) or 'mine'
        if quarry and not (mine_hist or mine_mm): kind = 'quarry'
        status = f'tagged {state}' if state else ('historic mine' if mine_hist else 'mine opening')
        return 'Mines & quarries', kind, status, 'mapped', name
    if why == 'rail': return None
    if t.get('landuse') == 'brownfield':
        return 'Brownfields', 'brownfield', 'brownfield land', 'mapped', name
    if h == 'ruins' or t.get('ruins') == 'yes' or t.get('building') in ('ruins', 'collapsed') or state == 'ruins':
        what = nice(t.get('ruins:building') or t.get('historic:building') or (bv if state == 'ruins' else '') or
                    (t.get('building') if t.get('building') not in ('ruins', 'yes', 'collapsed') else '') or t.get('man_made', '') or t.get('amenity', ''))
        return 'Ruins', what or 'ruins', 'tagged ruins', 'mapped', name
    if h in ('kiln', 'lime_kiln', 'charcoal_pile', 'furnace', 'blast_furnace', 'iron_works'):
        return 'Ruins', nice(h), 'historic industrial relic', 'mapped', name
    if h in ('abandoned_village', 'ghost_town') or bk == 'place':
        return 'Ghost towns', nice(bv) or 'abandoned settlement', f'tagged {state}' if state else 'historic site', 'mapped', name
    if h in ('fort', 'battery', 'bunker', 'military'):
        return 'Military & Cold War', nice(h), 'historic military site', 'mapped', name
    if h == 'industrial':
        return 'Industrial & power', nice(t.get('industrial') or 'industrial site'), 'historic industrial site', 'mapped', name
    if why == 'military':
        if t.get('military') in ('bunker', 'launchpad', 'battery', 'trench'):
            return 'Military & Cold War', nice(t['military']), 'military site; current use unknown', 'inferred', name
        if not state: return None
    if why == 'vacant_shop':
        return 'Closed businesses', 'storefront', 'vacant storefront', 'mapped', name
    if why == 'name' and not state and t.get('building') not in BUILD_STATES:
        if not name_guess(name): return None
        n = name.lower()
        if re.search(r'nike|missile|launch site|radar site|coast artillery|gun emplacement|battery', n): cat = 'Military & Cold War'
        elif re.search(r'\bmine\b|quarry', n): cat = 'Mines & quarries'
        else: cat = 'Other buildings & sites'
        return cat, 'named site', 'name says former/abandoned', 'inferred', name
    if t.get('building') in BUILD_STATES and not base:
        return 'Other buildings & sites', 'building', f"tagged {t['building']}", 'mapped', name
    if not state: return None
    if base and DROP_BASE.match(base): return None
    st = f'tagged {state}'
    if not base:
        return ('Other buildings & sites', 'site', st, 'mapped', name) if name or 'building' in t else None
    # category by base tag
    if bk in ('shop', 'office', 'craft') or (bk == 'amenity' and bv in BIZ) or (bk == 'healthcare' and bv != 'hospital') or (bk == 'leisure' and bv in ('fitness_centre',)):
        return 'Closed businesses', nice(bv) or bk, st, 'mapped', name
    if (bk == 'amenity' and bv in INST) or (bk == 'building' and bv in INST_B) or (bk == 'healthcare' and bv == 'hospital'):
        return 'Institutions', nice(bv), st, 'mapped', name
    if bk in ('railway', 'aeroway', 'bridge', 'waterway') or (bk == 'amenity' and bv in ('ferry_terminal', 'bus_station')) or \
       (bk == 'man_made' and bv in ('pier', 'bridge', 'lighthouse')) or (bk == 'building' and bv in ('train_station', 'hangar', 'transportation')):
        return 'Rail & transport', nice(bv), st, 'mapped', name
    if (bk == 'man_made' and bv in ('tower', 'mast', 'communications_tower', 'antenna')) or bk == 'tower:type':
        return 'Towers & masts', nice(bv), st, 'mapped', name
    if bk in ('military',) or (bk == 'building' and bv == 'bunker') or (bk == 'landuse' and bv == 'military'):
        return 'Military & Cold War', nice(bv), st, 'mapped', name
    if bk in ('power', 'industrial') or bk == 'man_made' or (bk == 'building' and bv in IND_B) or (bk == 'landuse' and bv in ('industrial', 'railway')):
        return 'Industrial & power', nice(bv), st, 'mapped', name
    if (bk == 'amenity' and bv in LEIS) or bk in ('leisure', 'tourism') or (bk == 'building' and bv in ('hotel', 'stadium', 'grandstand')):
        return 'Leisure & lodging', nice(bv), st, 'mapped', name
    return 'Other buildings & sites', nice(bv) or 'building', st, 'mapped', name

BUILD_STATES = {'abandoned', 'disused'}
NAME_STRONG = re.compile(r'abandoned|derelict|\bruins?\b|\bformer\b|\bsite of\b|\bnike\b|missile|launch site|coast artillery|'
                         r'gun emplacement|\bAN/[FT]PS|\bclosed\b|'
                         r'\bold\b.*\b(mine|quarry|mill|furnace|kiln|hospital|sanatorium|asylum|prison|jail|factory|plant)s?$', re.I)
NAME_PLACEISH = re.compile(r'\b(park|reserve|preserve|trail|road|rd|street|lane|drive|brook|creek|run|pond|lake|estates|farm|'
                           r'apartments|condominiums?|plaza|bridge|museum|district|parking|path|loop|forest|woods|cemetery|marsh|'
                           r'beach|marina|golf|playground|field|pub|tavern|restaurant|inn|cafe|grill|antiques?|shop|store|market|'
                           r'mall|crossing|landing|lofts?|green|woodlands|commons?|bell|sign|marker|monument|memorial)\b', re.I)
NAME_SCHOOL = re.compile(r'\b(elementary|middle|high|intermediate|primary)\b|\bschool\b', re.I)
def name_guess(name):
    """Only trust a bare name when it says the place is gone/closed, and isn't a road, creek, park or working school."""
    if not NAME_STRONG.search(name): return False
    if re.search(r'abandoned|derelict|\bruins?\b|\bclosed\b', name, re.I): return True
    if NAME_PLACEISH.search(name): return False
    if NAME_SCHOOL.search(name) and not re.search(r'\bformer\b|\bsite of\b', name, re.I): return False
    return True
BIZ = {'restaurant', 'fast_food', 'cafe', 'bar', 'pub', 'bank', 'pharmacy', 'fuel', 'car_wash', 'ice_cream', 'dentist', 'doctors',
       'veterinary', 'post_office', 'car_rental', 'marketplace', 'biergarten', 'food_court', 'money_transfer', 'bureau_de_change',
       'driving_school', 'internet_cafe', 'video_rental', 'payment_centre'}
INST = {'hospital', 'school', 'college', 'university', 'place_of_worship', 'fire_station', 'police', 'prison', 'townhall', 'library',
        'courthouse', 'community_centre', 'kindergarten', 'clinic', 'social_facility', 'grave_yard', 'monastery', 'nursing_home', 'orphanage'}
INST_B = {'hospital', 'school', 'church', 'chapel', 'college', 'university', 'civic', 'government', 'fire_station', 'public',
          'cathedral', 'monastery', 'synagogue', 'temple', 'mosque', 'kindergarten', 'prison'}
IND_B = {'industrial', 'factory', 'warehouse', 'storage_tank', 'silo', 'manufacture', 'power', 'transformer_tower', 'hangar_industrial'}
LEIS = {'cinema', 'theatre', 'arts_centre', 'casino', 'nightclub', 'stripclub', 'events_venue', 'swimmingpool'}

seen_osm = set()
rail_all = {}
files = sorted(glob.glob(os.path.join(OSM_OUT, 'osm_*.csv')))
# process the big multi-state file first so per-state files only fill gaps
files.sort(key=lambda f: (0 if 'us-northeast' in f else 1, f))
for fp in files:
    reg = os.path.basename(fp)[4:-4]
    ca = CA_FILE.get(reg)
    for r in csv.DictReader(open(fp, encoding='utf-8')):
        key = (r['osm_type'], r['osm_id'])
        if key in seen_osm: continue
        seen_osm.add(key)
        lat, lon = float(r['lat']), float(r['lon'])
        st = us_state(lat, lon, slack=0.0 if ca else 0.03)
        region = st if st else ca
        if not region: continue
        t = json.loads(r['tags'])
        c = osm_classify(t, r['why'])
        if not c: continue
        cat, kind, status, basis, name = c
        note = ' · '.join(x for x in [f"built {t['start_date']}" if t.get('start_date') else '',
                                      'closed ' + (t.get('end_date') or t.get('abandoned:date') or t.get('disused:date'))
                                      if (t.get('end_date') or t.get('abandoned:date') or t.get('disused:date')) else ''] if x)
        add(lat, lon, cat, basis, region, 'OpenStreetMap', name, kind, status, f"{r['osm_type']}{r['osm_id']}", note)
    rp = os.path.join(OSM_OUT, f'rail_{reg}.json')
    if os.path.exists(rp):
        for w in json.load(open(rp)):
            if w['id'] in rail_all: continue
            mid = w['c'][len(w['c']) // 2]
            st = us_state(mid[1], mid[0], slack=0.0 if ca else 0.03)
            if not (st or ca): continue
            g = LineString(w['c']).simplify(0.0004)  # ~40 m; plenty for a 1:50k-ish view
            pts = [[round(x, 4), round(y, 4)] for x, y in g.coords]
            pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
            if len(pts) < 2 or g.length < 0.0015: continue  # drop stubs shorter than ~150 m
            rail_all[w['id']] = [w['id'], w['n'][:60], 1 if w['s'] == 'abandoned' else 0, pts]
print('osm rows', len(ROWS), 'rail', len(rail_all), flush=True)

# ---------- Wikidata ----------
n0 = len(ROWS)
WD_SKIP = {'protected area', 'museum', 'company', 'business', 'organization', 'restaurant', 'radio station', 'television station',
           'newspaper', 'school district', 'sports team', 'website', 'shopping center'}
for fp in sorted(glob.glob(os.path.join(WD_DIR, '*.json'))):
    region = os.path.basename(fp)[:-5]
    items = {}
    for b in json.load(open(fp))['results']['bindings']:
        q = b['item']['value'].split('/')[-1]
        e = items.setdefault(q, dict(name=b['itemLabel']['value'], state=b.get('stateLabel', {}).get('value', ''), types=set(),
                                     coord=b['coord']['value'], end=b.get('end', {}).get('value', '')[:4]))
        if 'typeLabel' in b: e['types'].add(b['typeLabel']['value'])
    for q, e in items.items():
        ty = ' '.join(e['types'])
        if 'destroyed' in ty or 'demolished' in ty or re.fullmatch(r'Q\d+', e['name']) or (e['types'] & WD_SKIP): continue
        m = re.match(r'Point\(([-\d\.]+) ([-\d\.]+)\)', e['coord'])
        if not m: continue
        lon, lat = float(m.group(1)), float(m.group(2))
        kinds = sorted(e['types'] - {'unincorporated community', 'building', 'structure', 'architectural structure'})
        kind = kinds[0] if kinds else ''
        if re.search(r'ghost town|abandoned village|deserted', ty): cat = 'Ghost towns'
        elif re.search(r'\bmine\b|quarry|colliery', ty): cat = 'Mines & quarries'
        elif re.search(r'ruin', ty): cat = 'Ruins'
        elif re.search(r'station|terminal|bridge|airport|aerodrome|railway|tram|canal|lighthouse|ferry|tunnel', ty): cat = 'Rail & transport'
        elif re.search(r'fort|battery|military|missile|bunker|barracks|arsenal', ty): cat = 'Military & Cold War'
        elif re.search(r'power|plant|factory|mill|works|dam|brewery|distillery|refinery|furnace', ty): cat = 'Industrial & power'
        elif re.search(r'hospital|school|asylum|sanatorium|prison|church|college|seminary|orphanage|library|jail', ty): cat = 'Institutions'
        elif re.search(r'theat|cinema|amusement|park|racing|hotel|resort|stadium|arena|casino|drive-in|camp|ski', ty): cat = 'Leisure & lodging'
        elif re.search(r'store|shop|restaurant|diner|bar\b|bank', ty): cat = 'Closed businesses'
        else: cat = 'Other buildings & sites'
        add(lat, lon, cat, 'mapped', region, 'Wikidata', e['name'], kind, e['state'], q, f"ended {e['end']}" if e['end'] else '')
print('wikidata rows', len(ROWS) - n0, flush=True)

# ---------- USGS MRDS ----------
n0 = len(ROWS)
ST2 = {v: k for k, v in REGION_NAME.items()}
for r in csv.DictReader(open(os.path.join(MINES, 'mrds.csv'), encoding='utf-8', errors='ignore')):
    reg = ST2.get(r['state'])
    if not reg or r['dev_stat'] not in ('Past Producer', 'Prospect'): continue
    try: lat, lon = float(r['latitude']), float(r['longitude'])
    except ValueError: continue
    commod = ', '.join(x.strip().lower() for x in [r['commod1'], r['commod2']] if x.strip())[:50]
    op = r['oper_type'].lower() if r['oper_type'] not in ('', 'Unknown') else ''
    kind = ' '.join(x for x in [op, commod] if x) or 'mine'
    last = r['yr_lst_prd'].strip()
    if r['dev_stat'] == 'Past Producer':
        add(lat, lon, 'Mines & quarries', 'mapped', reg, 'USGS MRDS', r['site_name'], kind, 'past producer', r['dep_id'], f'last production {last}' if last else '')
    else:
        add(lat, lon, 'Mines & quarries', 'inferred', reg, 'USGS MRDS', r['site_name'], kind, 'prospect (exploration workings)', r['dep_id'])
print('mrds rows', len(ROWS) - n0, flush=True)

# ---------- MSHA ----------
n0 = len(ROWS)
with open(os.path.join(MINES, 'Mines.txt'), encoding='latin-1') as f:
    head = [h.strip('"') for h in f.readline().rstrip('\r\n').split('|')]
    for line in f:
        v = [x.strip('"') for x in line.rstrip('\r\n').split('|')]
        if len(v) < len(head): continue
        r = dict(zip(head, v))
        if r['STATE'] not in REGIONS or not r['CURRENT_MINE_STATUS'].startswith('Abandoned'): continue
        try: lat, lon = float(r['LATITUDE']), float(r['LONGITUDE'])
        except ValueError: continue
        if lon > 0: lon = -lon
        if not (37 < lat < 48 and -81 < lon < -66): continue
        kind = ', '.join(x.lower() for x in [r['CURRENT_MINE_TYPE'], r['PRIMARY_SIC']] if x)[:60]
        yr = r['CURRENT_STATUS_DT'][-4:]
        add(lat, lon, 'Mines & quarries', 'mapped', r['STATE'], 'MSHA', r['CURRENT_MINE_NAME'].title(), kind,
            r['CURRENT_MINE_STATUS'].lower(), r['MINE_ID'], f'status since {yr}' if yr.isdigit() else '')
print('msha rows', len(ROWS) - n0, flush=True)

# ---------- Quebec abandoned / orphaned mines ----------
n0 = len(ROWS)
TYPE_FR = {'Puits': 'shaft', 'Surface': 'surface workings', 'Souterrainee': 'underground', 'Souterraine': 'underground',
           "Puits d'exploration": 'exploration shaft', 'Fosse': 'open pit', 'Halde': 'waste pile', 'Tranchée': 'trench'}
qc = collections.OrderedDict()
for r in csv.DictReader(open(glob.glob(os.path.join(MINES, 'qc_*.csv'))[0], encoding='utf-8-sig')):
    try: lat, lon = float(r['Coordonnees_geographiques_Latitude']), -abs(float(r['Coordonnees_geographiques_Longitude']))
    except ValueError: continue
    k = (r['Nom_du_site_minier'], round(lat, 4), round(lon, 4))
    e = qc.setdefault(k, dict(lat=lat, lon=lon, comm=[], type=r['Type_de_mine'], last=r['Derniere_annee_operation'], stat=r['Statut_juridique']))
    if r['Commodite'] and r['Commodite'].lower() not in e['comm']: e['comm'].append(r['Commodite'].lower())
for i, ((nm, _, _), e) in enumerate(qc.items()):
    kind = ', '.join([TYPE_FR.get(e['type'], e['type'].lower())] + e['comm'][:2])
    add(e['lat'], e['lon'], 'Mines & quarries', 'mapped', 'QC', 'Quebec MRNF', nm, kind, (e['stat'] or 'abandonné').lower() + ' (orphaned/abandoned)',
        f'qc{i}', f"last operated {e['last']}" if e['last'] else '')
print('quebec rows', len(ROWS) - n0, flush=True)

# ---------- Nova Scotia abandoned mine openings ----------
n0 = len(ROWS)
shp = glob.glob(os.path.join(MINES, 'ns', '**', 'd010nssh.shp'), recursive=True)[0]
sr = shapefile.Reader(shp, encoding='utf-8', encodingErrors='replace')
fields = [f[0] for f in sr.fields[1:]]
latf = next(f for f in fields if f.lower() in ('lat', 'latitude', 'lat_dd', 'y_dd') or f.lower().startswith('lat'))
lonf = next(f for f in fields if f.lower() in ('long', 'lon', 'longitude', 'long_dd', 'x_dd') or f.lower().startswith('lon'))
urlf = next((f for f in fields if any(isinstance(v, str) and v.startswith('http') for v in [sr.record(0)[fields.index(f)]])), None)
for rec in sr.iterRecords():
    r = dict(zip(fields, rec))
    try: lat, lon = float(r[latf]), float(r[lonf])
    except (TypeError, ValueError): continue
    if not lat: continue
    kind = ', '.join(x.lower() for x in [r.get('Opening_ty') or '', r.get('Commodity') or ''] if x)
    hz = r.get('Degree_Haz') or ''
    add(lat, lon, 'Mines & quarries', 'mapped', 'NS', 'Nova Scotia DNRR', (r.get('Name') or r.get('S_Location') or '').title(), kind,
        'abandoned mine opening', r.get('ShaftID'), f'hazard {hz.lower()}' if hz and hz != 'Not Rated' else '')
print('nova scotia rows', len(ROWS) - n0, flush=True)

# ---------- FCC towers (inferred idle) ----------
n0 = len(ROWS)
def dms(sec, hemi): return (-1 if hemi in ('S', 'W') else 1) * float(sec) / 3600
ra = {}
for line in open(os.path.join(FCC_DIR, 'RA.dat'), encoding='latin-1'):
    f = line.rstrip('\n').split('|')
    if len(f) > 32 and f[25] in REGIONS: ra[f[3]] = f
co = {}
for line in open(os.path.join(FCC_DIR, 'CO.dat'), encoding='latin-1'):
    f = line.rstrip('\n').split('|')
    if len(f) > 15 and f[3] in ra and f[5] == 'T' and f[10] and f[15]:
        co[f[3]] = (dms(f[10], f[9]), dms(f[15], f[14]))
STYPE = {'TOWER': 'tower', 'GTOWER': 'guyed tower', 'LTOWER': 'lattice tower', 'MTOWER': 'monopole', 'POLE': 'pole', 'UPOLE': 'utility pole',
         'MAST': 'mast', 'BTWR': 'building with tower', 'NNTANN': 'antenna'}
def yr(s): return int(s[-4:]) if s and s[-4:].isdigit() else None
for reg, f in ra.items():
    if reg not in co or f[32] in ('BANT', 'B', 'TREE', 'SIGN', 'RIG', 'TANK', ''): continue
    try: hm = float(f[30] or f[28])
    except ValueError: continue
    if hm < 30: continue
    st, last = f[8], f[14]
    if st == 'T': why = 'FCC registration terminated, no dismantle notice'
    elif st == 'C' and yr(last) and yr(last) <= 2006: why = f'FCC registration untouched since {yr(last)}'
    else: continue
    lat, lon = co[reg]
    add(lat, lon, 'Towers & masts', 'inferred', f[25], 'FCC ASR', f'ASR {reg}', STYPE.get(f[32], f[32].lower()), why, f[4],
        ' · '.join(x for x in [f'{hm:.0f} m', f'built {yr(f[12])}' if yr(f[12]) else '', (f[24] or '').title()] if x))
print('fcc rows', len(ROWS) - n0, flush=True)

# ---------- location check for non-OSM sources: the point decides the state; points outside the area are dropped ----------
CA_CODES = set(CA_FILE.values()); kept, moved, dropped = [], 0, 0
for r in ROWS:
    if r[5] != 'OpenStreetMap':
        lon, lat = r[0], r[1]
        if r[4] in CA_CODES:
            if us_state(lat, lon, 0.0) or not (-80 < lon < -52 and 43 < lat < 63): dropped += 1; continue
        else:
            s = us_state(lat, lon, 0.05)
            if not s: dropped += 1; continue
            if s != r[4]: r[4] = s; moved += 1
    kept.append(r)
ROWS = kept
print('location check: moved', moved, 'dropped', dropped, flush=True)

# ---------- de-duplicate across sources: same name within ~200 m (keep the first source in SRCS order) ----------
def cell(lon, lat): return (int(lon * 200), int(lat * 200))
order = {s: i for i, s in enumerate(SRCS)}
ROWS.sort(key=lambda r: (order[r[5]], r[3] != 'mapped'))
grid = collections.defaultdict(list); out = []
for r in ROWS:
    c = cell(r[0], r[1]); dup = False
    if r[6]:
        nm = r[6].lower()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for o in grid[(c[0] + dx, c[1] + dy)]:
                    if o[5] != r[5] and o[6].lower() == nm and abs(o[0] - r[0]) < 0.0026 and abs(o[1] - r[1]) < 0.0018: dup = True; break
                if dup: break
            if dup: break
    if dup: continue
    grid[c].append(r); out.append(r)
print('after dedupe', len(out), 'of', len(ROWS), flush=True)

# ---------- write ----------
kinds = sorted({r[7] for r in out}); kidx = {k: i for i, k in enumerate(kinds)}
stats = sorted({r[8] for r in out}); sidx = {k: i for i, k in enumerate(stats)}
def q(v, f): v = sorted(v); return v[min(len(v) - 1, int(f * len(v)))]
bounds = {}
for reg in REGIONS:
    pts = [(r[0], r[1]) for r in out if r[4] == reg]
    if pts:  # 0.5th-99.5th percentile box so a few stray points don't zoom out to the whole map
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        bounds[reg] = [round(q(xs, .005), 3), round(q(ys, .005), 3), round(q(xs, .995), 3), round(q(ys, .995), 3)]
compact = {'cats': CATS, 'srcs': SRCS, 'regions': REGIONS, 'region_names': REGION_NAME, 'bounds': bounds, 'kinds': kinds, 'statuses': stats,
           'fields': ['lon', 'lat', 'cat', 'guess', 'region', 'src', 'name', 'kind', 'status', 'ref', 'note'],
           'rows': [[r[0], r[1], CATS.index(r[2]), 1 if r[3] == 'inferred' else 0, REGIONS.index(r[4]), SRCS.index(r[5]), r[6],
                     kidx[r[7]], sidx[r[8]], r[9], r[10]] for r in out]}
json.dump(compact, open(os.path.join(OUTD, 'places.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
LINK = {'OpenStreetMap': lambda ref: 'https://www.openstreetmap.org/' + {'n': 'node/', 'w': 'way/', 'r': 'relation/'}[ref[0]] + ref[1:],
        'Wikidata': lambda ref: f'https://www.wikidata.org/wiki/{ref}',
        'USGS MRDS': lambda ref: f'https://mrdata.usgs.gov/mrds/show-mrds.php?dep_id={ref}',
        'MSHA': lambda ref: 'https://www.msha.gov/data-and-reports/mine-data-retrieval-system',
        'Quebec MRNF': lambda ref: 'https://www.donneesquebec.ca/recherche/dataset/initiative-nationale-pour-les-mines-orphelines-ou-abandonnees',
        'Nova Scotia DNRR': lambda ref: f'https://gesner.novascotia.ca/amosearch/singlereport.aspx?ShaftID={ref}',
        'FCC ASR': lambda ref: f'https://wireless2.fcc.gov/UlsApp/AsrSearch/asrRegistration.jsp?regKey={ref}'}
with open(os.path.join(OUTD, 'places.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['region', 'category', 'basis', 'name', 'kind', 'status', 'source', 'source_id', 'link', 'note', 'lat', 'lon'])
    for r in sorted(out, key=lambda r: (REGIONS.index(r[4]), CATS.index(r[2]), r[6])):
        w.writerow([r[4], r[2], r[3], r[6], r[7], r[8], r[5], r[9], LINK[r[5]](r[9]), r[10], r[1], r[0]])
json.dump({'rows': list(rail_all.values())}, open(os.path.join(OUTD, 'rail.json'), 'w'), separators=(',', ':'))
c = collections.Counter((r[2]) for r in out)
print('by category', c.most_common())
print('by region', collections.Counter(r[4] for r in out).most_common())
print('by source', collections.Counter(r[5] for r in out).most_common())
