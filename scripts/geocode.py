"""Geocode data/work/properties_parsed.csv -> data/properties.csv + data/properties.geojson.

1. NJOGIS parcels (Parcels and MOD-IV Composite of NJ), joined on PAMS_PIN = muni_block_lot[_qualifier].
2. Rows without block/lot: match the street address against PROP_LOC inside the same municipality.
3. Fallback: US Census batch geocoder on the street address (kept only if it lands near the municipality).
4. Anything else stays in the table without a point.
All requests are cached under data/cache/ and throttled.
"""
import csv, io, json, math, os, re, sys, time, hashlib, urllib.request
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from njogis import query
from munis import BYCODE

ROOT = os.path.join(os.path.dirname(__file__), '..')
CACHE = os.path.join(ROOT, 'data', 'cache')
OUT_FIELDS = ['county', 'municipality', 'muni_code', 'block', 'lot', 'qualifier', 'address', 'source_file', 'list_date',
              'pogodata_verified', 'abandonment_score', 'listed_status', 'geocode_method', 'round', 'lat', 'lon']

SUFFIX = {'AVENUE': 'AVE', 'STREET': 'ST', 'ROAD': 'RD', 'DRIVE': 'DR', 'LANE': 'LN', 'COURT': 'CT', 'PLACE': 'PL',
          'TERRACE': 'TER', 'BOULEVARD': 'BLVD', 'CIRCLE': 'CIR', 'TRAIL': 'TRL', 'HIGHWAY': 'HWY', 'PARKWAY': 'PKWY',
          'TERR': 'TER', 'LA': 'LN', 'ROUTE': 'RT', 'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W', 'MOUNTAIN': 'MTN'}
def addr_variants(a):
    a = re.sub(r'[\.,#]', ' ', a.upper()); a = re.sub(r'\s+', ' ', a).strip()
    a = re.sub(r'\b(UNIT|APT|STE|SUITE)\b.*$', '', a).strip()
    short = ' '.join(SUFFIX.get(t, t) for t in a.split())
    longm = {v: k for k, v in SUFFIX.items() if k not in ('TERR', 'LA', 'MOUNTAIN')}
    long_ = ' '.join(longm.get(t, t) for t in short.split())
    v = {a, short, long_, short + '.', re.sub(r'\b(ST|AVE|RD|DR|LN|CT|PL|TER|BLVD|CIR)$', r'\1.', short)}
    return [x for x in v if x]

def chunks(xs, n):
    for i in range(0, len(xs), n): yield xs[i:i + n]

def pin(r):
    p = f"{r['muni_code']}_{r['block']}_{r['lot']}"
    return p + (f"_{r['qualifier']}" if r['qualifier'] else '')

def haversine(lat1, lon1, lat2, lon2):
    R = 6371; p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

def census_batch(rows):
    """rows: list of (id, street, city). Returns {id: (lat, lon, matched_address)}."""
    out = {}
    for part in chunks(rows, 1000):
        body = io.StringIO(); w = csv.writer(body)
        for i, s, c in part: w.writerow([i, s, c, 'NJ', ''])
        payload = body.getvalue().encode()
        key = hashlib.sha1(payload).hexdigest()[:20]
        fp = os.path.join(CACHE, 'census', key + '.csv')
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        if not os.path.exists(fp):
            boundary = 'vapboundary'
            data = (f'--{boundary}\r\nContent-Disposition: form-data; name="benchmark"\r\n\r\nPublic_AR_Current\r\n'
                    f'--{boundary}\r\nContent-Disposition: form-data; name="addressFile"; filename="a.csv"\r\nContent-Type: text/csv\r\n\r\n').encode() \
                   + payload + f'\r\n--{boundary}--\r\n'.encode()
            req = urllib.request.Request('https://geocoding.geo.census.gov/geocoder/locations/addressbatch', data=data,
                                         headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
            with urllib.request.urlopen(req, timeout=600) as r: open(fp, 'wb').write(r.read())
            time.sleep(1)
        for rec in csv.reader(open(fp, encoding='utf8', errors='ignore')):
            if len(rec) >= 6 and rec[2] == 'Match':
                lon, lat = map(float, rec[5].split(','))
                out[rec[0]] = (lat, lon, rec[4])
    return out

def main():
    d = pd.read_csv(os.path.join(ROOT, 'data', 'work', 'properties_parsed.csv'), dtype=str).fillna('')
    d['lat'] = ''; d['lon'] = ''; d['geocode_method'] = ''
    # 1) by PIN, batched per municipality
    has_bl = d[(d.block != '') & (d.lot != '')]
    found = {}
    for code, grp in has_bl.groupby('muni_code'):
        pins = sorted(set(pin(r) for _, r in grp.iterrows()) | set(f"{r['muni_code']}_{r['block']}_{r['lot']}" for _, r in grp.iterrows()))
        for part in chunks(pins, 60):
            inlist = ','.join("'" + p.replace("'", "''") + "'" for p in part)
            for f in query(f"PAMS_PIN IN ({inlist})", n=500)['features']:
                if f.get('lat'): found[f['PAMS_PIN']] = f
    for i, r in d.iterrows():
        if r.block and r.lot:
            f = found.get(pin(r)) or found.get(f"{r['muni_code']}_{r['block']}_{r['lot']}")
            if f:
                d.at[i, 'lat'] = f"{f['lat']:.6f}"; d.at[i, 'lon'] = f"{f['lon']:.6f}"; d.at[i, 'geocode_method'] = 'njogis_parcel'
                if not r.address and f.get('PROP_LOC'): d.at[i, 'address'] = f['PROP_LOC'].strip()
    # 2) by address inside the municipality
    todo = d[(d.geocode_method == '') & (d.address != '')]
    for code, grp in todo.groupby('muni_code'):
        want = {}
        for i, r in grp.iterrows():
            for v in addr_variants(r.address): want.setdefault(v, set()).add(i)
        hits = {}
        for part in chunks(sorted(want), 60):
            inlist = ','.join("'" + v.replace("'", "''") + "'" for v in part)
            for f in query(f"PCL_MUN='{code}' AND PROP_LOC IN ({inlist})", n=1000)['features']:
                hits.setdefault(f['PROP_LOC'].strip().upper(), []).append(f)
        for i, r in grp.iterrows():
            cands = {}
            for v in addr_variants(r.address):
                for f in hits.get(v, []):
                    if f.get('lat') and not (f.get('PCLQCODE') or '').strip().startswith('C'): cands[f['PAMS_PIN']] = f
            if len(cands) == 1:
                f = next(iter(cands.values()))
                d.at[i, 'lat'] = f"{f['lat']:.6f}"; d.at[i, 'lon'] = f"{f['lon']:.6f}"; d.at[i, 'geocode_method'] = 'njogis_address'
                if not r.block:
                    d.at[i, 'block'] = f['PCLBLOCK'].strip(); d.at[i, 'lot'] = f['PCLLOT'].strip()
    # 3) Census fallback
    todo = d[(d.geocode_method == '') & (d.address.str.match(r'^\d'))]
    reqs = [(str(i), re.sub(r'\b(UNIT|APT|STE|SUITE)\b.*$', '', r.address, flags=re.I).strip(),
             re.sub(r'\s+(Township|Borough|City|Town|Village)$', '', BYCODE[r.muni_code]['name'])) for i, r in todo.iterrows()]
    res = census_batch(reqs) if reqs else {}
    for i, r in todo.iterrows():
        g = res.get(str(i))
        if not g: continue
        m = BYCODE[r.muni_code]
        if haversine(g[0], g[1], m['lat'], m['lon']) > 12: continue   # landed outside the town
        d.at[i, 'lat'] = f"{g[0]:.6f}"; d.at[i, 'lon'] = f"{g[1]:.6f}"; d.at[i, 'geocode_method'] = 'census'
    d.loc[d.geocode_method == '', 'geocode_method'] = 'unresolved'
    d['county'] = d.muni_code.map(lambda c: BYCODE[c]['county'])
    d['municipality'] = d.muni_code.map(lambda c: BYCODE[c]['name'])
    d = d.sort_values(['county', 'municipality', 'round', 'address'])
    d[OUT_FIELDS].to_csv(os.path.join(ROOT, 'data', 'properties.csv'), index=False)
    feats = []
    for _, r in d.iterrows():
        if r.lat == '': continue
        props = {k: r[k] for k in OUT_FIELDS if k not in ('lat', 'lon')}
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [float(r.lon), float(r.lat)]}, 'properties': props})
    json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(ROOT, 'data', 'properties.geojson'), 'w'), separators=(',', ':'))
    print(d.geocode_method.value_counts().to_dict(), 'points', len(feats))

if __name__ == '__main__':
    main()
