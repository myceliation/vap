"""NJ municipality lookup (names, 4-digit MUN_CODE, county, centroid) from NJOGIS Municipal Centroids."""
import json, re, os
HERE=os.path.dirname(__file__)
SRC=os.environ.get('MUNI_JSON', os.path.join(HERE,'..','data','cache','muni_centroids.json'))
def norm(s):
    s=s.lower().replace('&','and')
    s=re.sub(r'[^a-z0-9 ]',' ',s)
    s=re.sub(r'\bboro\b','borough',s); s=re.sub(r'\btwp\b','township',s)
    s=re.sub(r'\bmt\b','mount',s); s=re.sub(r'\bst\b','saint',s)
    return re.sub(r'\s+',' ',s).strip()
TYPES=['township','borough','city','town','village']
def _load():
    d=json.load(open(SRC)); out=[]
    for f in d['features']:
        a=f['attributes']
        out.append(dict(code=a['MUN_CODE'],name=a['MUN_LABEL'],county=a['COUNTY'].title(),
            lon=round(f['geometry']['x'],5),lat=round(f['geometry']['y'],5),n=norm(a['MUN_LABEL']),
            base=re.sub(r'\s+',' ',re.sub(r'\b(township|borough|city|town|village|of)\b','',norm(a['MUN_LABEL']))).strip()))
    return out
MUNIS=_load()
BYN={m['n']:m for m in MUNIS}
BYCODE={m['code']:m for m in MUNIS}
def match(name, county=None):
    n=norm(name)
    if n in BYN and (county is None or BYN[n]['county'].lower().startswith(county.lower()[:4])): return BYN[n]
    for alt in [n.replace('city of ','')+' city','city of '+n,n.replace(' township',''),n+' township',n+' borough',n+' city',n+' town']:
        if alt in BYN and (county is None or BYN[alt]['county'].lower().startswith(county.lower()[:4])): return BYN[alt]
    base=re.sub(r'\s+',' ',re.sub(r'\b(township|borough|city|town|village|of)\b','',n)).strip()
    cands=[m for m in MUNIS if m['base']==base]
    if county: cands=[m for m in cands if m['county'].lower().startswith(county.lower()[:4])]
    if len(cands)==1: return cands[0]
    for t in TYPES:
        if re.search(r'\b'+t+r'\b',n):
            cc=[m for m in cands if m['n'].endswith(t)]
            if len(cc)==1: return cc[0]
    return None
