"""Build data/requests.csv: one row per OPRA request (two rounds).

2025 round: manual requests (spring 2025), tracked by hand in a spreadsheet (no dates kept).
2026 round: automated requests (May-June 2026); outcomes classified from Gmail reply metadata
            (see build_requests_2026.py), then corrected with the written-denial / portal-refusal
            calls recorded in the GRC filing tracker.
n_records = rows in data/properties.csv for that municipality and round.
"""
import csv, os, sys, re, collections
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from munis import match, BYCODE
from build_requests_2026 import build, classify

WORK = os.environ.get('WORK', '/home/claude/vapwork')
ROOT = os.path.join(os.path.dirname(__file__), '..')
FIELDS = ['county','municipality','muni_code','request_date','outcome','response_date','days_to_response','n_records','notes','round']

COUNTY_ABBR = {'cape ma':'Cape May','cumland':'Cumberland','atla':'Atlantic','salemi':'Salem','gloces':'Gloucester','camd':'Camden','merc':'Mercer','smerst':'Somerset'}
ALIAS_2025 = {
 'w cape may':'West Cape May Borough','cape may (city)':'Cape May City','lower':'Lower Township','middle':'Middle Township','upper':'Upper Township',
 'n wildwood':'North Wildwood City','w wildwood':'West Wildwood Borough','ww crest':'Wildwood Crest Borough','wildwood':'Wildwood City',
 'eht':'Egg Harbor Township','hamilton':'Hamilton Township','buena':'Buena Borough','buena vista':'Buena Vista Township','salem city':'Salem City',
 'lower alloways crk':'Lower Alloways Creek Township','s harrison':'South Harrison Township','harrison':'Harrison Township','berlin boro':'Berlin Borough',
 'berlin twn':'Berlin Township','gloucester twn':'Gloucester Township','gloucester city':'Gloucester City','mt ephraim':'Mount Ephraim Borough',
 'hopewell boro?':'Hopewell Borough','camden':'Camden City','pine valley':'Pine Valley Borough','sea isle city':'Sea Isle City','ocean city':'Ocean City',
 'cape may point':'Cape May Point Borough','atlantic city':'Atlantic City','egg harbor city':'Egg Harbor City','corbin city':'Corbin City',
 'estell manor':'Estell Manor City','port republic':'Port Republic City','woodbury':'Woodbury City','bridgeton':'Bridgeton City',
 'vineland':'Vineland City','millville':'Millville City','pleasantville':'Pleasantville City','northfield':'Northfield City','linwood':'Linwood City',
 'somers point':'Somers Point City','ventnor':'Ventnor City','brigantine':'Brigantine City','absecon':'Absecon City','margate':'Margate City',
}

def days(a, b):
    return (b - a).days if (a and b) else ''

def outcome_2025(resp, have):
    resp = str(resp).strip().lower(); have = str(have).strip().lower()
    if resp in ('no', 'no, no', 'nan', ''): return 'no_response', ''
    if have.startswith('yes (kind'): return 'partial', 'partial list'
    if have.startswith('yes'): return 'fulfilled', ''
    if 'denied' in have:
        if 'form' in have: return 'denied', 'required their own form'
        if '2020' in have: return 'denied', 'denied; an older 2020 list exists'
        return 'denied', ''
    if have.startswith('waiting'): return 'pending', 'acknowledged, never completed'
    if have == 'no': return 'no_records', 'replied without a list'
    return 'pending', ''

def main():
    props = pd.read_csv(os.path.join(ROOT, 'data', 'properties.csv'), dtype=str).fillna('') if os.path.exists(os.path.join(ROOT,'data','properties.csv')) \
        else pd.read_csv(os.path.join(ROOT, 'data', 'work', 'properties_parsed.csv'), dtype=str).fillna('')
    nrec = collections.Counter(zip(props['muni_code'], props['round']))
    rows = []
    # ---- 2025
    d = pd.read_excel(os.path.join(WORK, 'in', 'da vap.xlsx')); d['county'] = d['county'].ffill()
    d = d[d['sent'].notna()]
    seen25 = set()
    for _, r in d.iterrows():
        cty = COUNTY_ABBR.get(str(r['county']).strip().lower())
        if not cty: continue   # state agencies (Pinelands, OIT, Dept. of State)
        nm = str(r['munic']).strip().lower()
        mu = match(ALIAS_2025.get(nm, nm), cty) or match(ALIAS_2025.get(nm, nm) + ' Township', cty) or match(ALIAS_2025.get(nm, nm) + ' Borough', cty)
        if not mu: print('2025 unmatched', nm, cty); continue
        o, note = outcome_2025(r['responded'], r['have list'])
        n = nrec.get((mu['code'], '2025'), 0)
        if n and o != 'fulfilled': note = (note + '; ' if note else '') + f'list on file ({o} in tracker)'; o = 'fulfilled'
        if o == 'fulfilled' and not n: note = (note + '; ' if note else '') + 'list not among saved files'
        seen25.add(mu['code'])
        rows.append(dict(county=mu['county'], municipality=mu['name'], muni_code=mu['code'], request_date='', outcome=o,
                         response_date='', days_to_response='', n_records=n or '', notes=note, round='2025'))
    for (code, rnd), n in nrec.items():
        if rnd == '2025' and code not in seen25:
            mu = BYCODE[code]
            rows.append(dict(county=mu['county'], municipality=mu['name'], muni_code=code, request_date='', outcome='fulfilled',
                             response_date='', days_to_response='', n_records=n, notes='list on file; request not in tracker', round='2025'))
    # ---- 2026
    L, _ = build(WORK)
    g = pd.read_excel(os.path.join(WORK, 'in', 'GRC_filing_tracker.xlsx'), sheet_name='GRC Filing Tracker')
    grc = {}
    for _, r in g.iterrows():
        nm = str(r['Municipality']).replace('Parsippany', 'Parsippany-Troy Hills')
        mu = match(nm, str(r['County'])) or match(nm + ' Township', str(r['County'])) or match(nm + ' Borough', str(r['County'])) or match(nm + ' City', str(r['County']))
        if mu: grc[mu['code']] = str(r['Type'])
    for code, e in L.items():
        mu = e['muni']
        o, rd, note = classify(e)
        t = grc.get(code, '')
        if t == 'denial' and o != 'fulfilled': o, note = 'denied', note or 'written denial'
        if 'portal' in t and o not in ('fulfilled',): o, note = 'denied', 'required portal or form'
        if t.startswith('non-responder') and o == 'no_response': note = (note + '; ' if note else '') + 'deemed denied'
        req = min(e['sends']) if e['sends'] else None
        n = nrec.get((code, '2026'), 0)
        if o == 'fulfilled' and not n: note = (note + '; ' if note else '') + 'records attached, not parsed'
        rows.append(dict(county=mu['county'], municipality=mu['name'], muni_code=code, request_date=req.isoformat() if req else '',
                         outcome=o, response_date=rd.isoformat() if rd else '', days_to_response=days(req, rd),
                         n_records=n if n else '', notes=note, round='2026'))
    rows.sort(key=lambda r: (r['round'], r['county'], r['municipality']))
    with open(os.path.join(ROOT, 'data', 'requests.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    import json
    codes = sorted({r['muni_code'] for r in rows} | set(props['muni_code']))
    json.dump({c: [BYCODE[c]['lon'], BYCODE[c]['lat']] for c in codes}, open(os.path.join(ROOT, 'data', 'municipalities.json'), 'w'), separators=(',', ':'))
    c = collections.Counter((r['round'], r['outcome']) for r in rows)
    print(len(rows), sorted(c.items()))

if __name__ == '__main__':
    main()
