"""Thin cached client for the NJOGIS 'Parcels and MOD-IV Composite of NJ' feature service.

Only parcel PIN, block/lot, location and centroid are requested. Owner fields are never requested.
Every response is cached under data/cache/parcels/ so nothing is fetched twice.
"""
import json, hashlib, os, time, urllib.parse, urllib.request
URL='https://services2.arcgis.com/XVOqAjTOJ5P6ngMu/ArcGIS/rest/services/Parcels_Composite_NJ_WM/FeatureServer/0/query'
CACHE=os.path.join(os.path.dirname(__file__),'..','data','cache','parcels')
FIELDS='PAMS_PIN,PCL_MUN,PCLBLOCK,PCLLOT,PCLQCODE,PROP_LOC,PROP_CLASS'
_last=[0.0]
def query(where, n=50):
    key=hashlib.sha1(where.encode()).hexdigest()[:20]
    fp=os.path.join(CACHE,key+'.json')
    if os.path.exists(fp): return json.load(open(fp))
    wait=0.35-(time.time()-_last[0])
    if wait>0: time.sleep(wait)
    qs=urllib.parse.urlencode(dict(where=where,outFields=FIELDS,returnGeometry='false',returnCentroid='true',outSR='4326',f='json',resultRecordCount=n))
    for attempt in range(4):
        try:
            with urllib.request.urlopen(URL+'?'+qs, timeout=60) as r: d=json.load(r)
            break
        except Exception as e:
            time.sleep(2*(attempt+1)); d={'error':str(e)}
    _last[0]=time.time()
    out=[dict(f['attributes'], lon=(f.get('centroid') or {}).get('x'), lat=(f.get('centroid') or {}).get('y')) for f in d.get('features',[])]
    res={'where':where,'features':out,'error':d.get('error')}
    if not d.get('error'): json.dump(res,open(fp,'w'))
    return res
def q(s): return s.replace("'","''")
def by_pin(pin): return query(f"PAMS_PIN='{q(pin)}'")
def by_block_lot(mun, block, lot, qual=''):
    w=f"PCL_MUN='{mun}' AND PCLBLOCK='{q(block)}' AND PCLLOT='{q(lot)}'"
    if qual: w+=f" AND PCLQCODE='{q(qual)}'"
    return query(w)
def by_address(addr, mun=None):
    w=f"PROP_LOC='{q(addr.upper())}'"
    if mun: w+=f" AND PCL_MUN='{mun}'"
    return query(w)
