"""Parse the vacant/abandoned-property lists that came back from OPRA requests into one normalized table.

Raw inputs are NOT published (they carry owner names and correspondence). Point RAW at a local folder holding them:
    RAW=/path/to/raw python scripts/parse_lists.py
Writes data/work/properties_parsed.csv (no coordinates yet; see geocode.py).

Kept: registries/lists of vacant, abandoned, foreclosed or unsafe properties.
Skipped on purpose: tax-delinquency reports, code-violation logs, fire/police incident logs,
blank request forms, and 2020-era files from an earlier, unrelated request.
"""
import csv, os, re, glob, zipfile, datetime as dt
import pandas as pd

RAW = os.environ.get('RAW', '../in/docume-20260218T190106Z-1-001/docume/bando')
OCR = os.environ.get('OCR', '../ocr/full')
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'work', 'properties_parsed.csv')
FIELDS = ['round', 'muni_code', 'block', 'lot', 'qualifier', 'address', 'source_file', 'list_date',
          'pogodata_verified', 'abandonment_score', 'listed_status']

def norm_num(x):
    """Normalize a block or lot: trim, drop leading zeros, drop an all-zero decimal part."""
    if x is None or (isinstance(x, float) and pd.isna(x)): return ''
    s = str(x).strip().replace(',', '.')
    if isinstance(x, float) and x.is_integer(): s = str(int(x))
    s = re.sub(r'\s+', '', s)
    m = re.fullmatch(r'0*(\d+)(?:\.(\d+))?', s)
    if not m: return s
    i, d = m.group(1), m.group(2)
    if d is None or set(d) == {'0'}: return i
    return f'{i}.{d}'

def clean_addr(a):
    if a is None or (isinstance(a, float) and pd.isna(a)): return ''
    a = re.sub(r'\s+', ' ', str(a)).strip(' ,.-')
    return a

ROWS = []
def add(rnd, code, src, block='', lot='', qual='', addr='', date='', status='', verified='', score=''):
    ROWS.append(dict(round=rnd, muni_code=code, block=norm_num(block), lot=norm_num(lot),
                     qualifier=(qual or '').strip(), address=clean_addr(addr), source_file=src,
                     list_date=date, pogodata_verified=verified, abandonment_score=score,
                     listed_status=status))

def x(name, **kw):
    return pd.read_excel(os.path.join(RAW, name), header=None, **kw)

def split_pin(pin):
    p = str(pin).strip().split('_')
    if len(p) < 3: return None
    return p[0], p[1], p[2], (p[3] if len(p) > 3 else '')

# ---------- 2025 round (manual requests, spring 2025) ----------
def paterson():
    d = pd.read_excel(os.path.join(RAW, '1466000098_14904.xlsx'))
    for _, r in d.iterrows():
        if pd.isna(r.get('ADDRESS')): continue
        add('2025', '1608', '1466000098_14904.xlsx', r['BLOCK'], r['LOT'], '', r['ADDRESS'], '',
            'abandoned property list (RAP)')

def prochamps(name, date):
    d = pd.read_excel(os.path.join(RAW, name))
    d = d[d['Address'].notna()]
    for _, r in d.iterrows():
        sp = split_pin(r['Parcel']) if pd.notna(r.get('Parcel')) else None
        status = 'foreclosure registration'
        if 'Program' in d and pd.notna(r.get('Program')): status = f"{str(r['Program']).lower()} registration"
        if 'Status' in d and pd.notna(r.get('Status')): status += f": {str(r['Status']).split('->')[0].strip()}"
        if sp: add('2025', sp[0], name, sp[1], sp[2], sp[3], r['Address'], date, status)

def eht_otr():
    d = pd.read_excel(os.path.join(RAW, 'Evidence OTR 04172025.xlsx'))
    for _, r in d.iterrows():
        sp = split_pin(r['Parcel']) if pd.notna(r.get('Parcel')) else None
        if not sp: continue
        occ = str(r.get('Occupancy Status') or '').strip()
        st = 'foreclosure registration'
        if occ and occ.lower() != 'nan': st += f'; occupancy: {occ.lower()}'
        add('2025', sp[0], 'Evidence OTR 04172025.xlsx', sp[1], sp[2], sp[3], r['Address'], '2025-04-17', st)

def pilesgrove():
    d = x('2025 Vacant Abandoned Lots.xlsx')
    for _, r in d.iloc[1:].iterrows():
        if pd.isna(r[2]): continue
        note = str(r[3] or '').lower()
        st = 'vacant/abandoned list'
        if 'occupied' in note: st += '; noted currently occupied'
        elif 'still vacant' in note or 'vacant' in note: st += '; noted still vacant'
        elif 'unsafe' in note: st += '; unsafe structure notice'
        elif 'foreclos' in note: st += '; foreclosure'
        lots = re.split(r'\s*&\s*', str(r[1]))
        add('2025', '1710', '2025 Vacant Abandoned Lots.xlsx', r[0], lots[0], '', r[2], '2025', st)

def dennis():
    d = x('Abandon properties List 03 24 2025.xlsx')
    for _, r in d.iloc[3:].iterrows():
        if pd.isna(r[2]) or pd.isna(r[0]): continue
        st = 'abandoned property registration' + ('; deregistered' if pd.notna(r[13]) else '')
        add('2025', '0504', 'Abandon properties List 03 24 2025.xlsx', r[0], r[1], '', r[2], '2025-03-24', st)

def oldmans():
    d = x('Abandoned Properties Registration Spreadsheet Autosaved.xlsx')
    for _, r in d.iloc[2:].iterrows():
        if pd.isna(r[2]) or pd.isna(r[0]): continue
        add('2025', '1707', 'Abandoned Properties Registration Spreadsheet Autosaved.xlsx', r[0], r[1], '', r[2], '2025',
            'abandoned property registration')

def franklin_structures():
    d = x('Abandoned_Structure_List_-_Updated_4-17-25.xlsx')
    seen = set()
    for _, r in d.iloc[1:].iterrows():
        if pd.isna(r[1]) or pd.isna(r[2]): continue
        num = int(r[1]) if isinstance(r[1], float) and r[1].is_integer() else r[1]
        addr = f'{num} {r[2]}'
        if addr in seen: continue
        seen.add(addr)
        st = 'abandoned structure list'
        if pd.notna(r[4]): st += f'; {str(r[4]).strip().lower()}'
        if pd.notna(r[5]): st += f'; {str(r[5]).strip().lower()}'
        add('2025', '1808', 'Abandoned_Structure_List_-_Updated_4-17-25.xlsx', '', '', '', addr, '2025-04-17', st)

def north_wildwood():
    d = x('Copy of VPR LOG 2025.xlsx')
    for _, r in d.iloc[2:].iterrows():
        if pd.isna(r[2]) or str(r[0]).strip().lower() == 'number': continue
        ren = str(r[3]).strip().upper()
        st = 'vacant property registration' + ('; renewed' if ren.startswith('Y') else ('; not renewed' if ren.startswith('N') else ''))
        add('2025', '0507', 'Copy of VPR LOG 2025.xlsx', '', '', '', r[2], '2025', st)

def salem_city():
    d = x('Copy of Vacate-Abandoned Property OPRA Request List.xlsx')
    for _, r in d.iloc[1:].iterrows():
        if pd.isna(r[2]) or pd.isna(r[0]): continue
        add('2025', '1713', 'Copy of Vacate-Abandoned Property OPRA Request List.xlsx', r[0], r[1], '', r[2], '',
            'vacant/abandoned property list')

def middle():
    d = x('d672c6cb-42025423966_Vacant_Properties_-_OPRA.xlsx')
    for _, r in d.iloc[2:].iterrows():
        if pd.isna(r[0]) or pd.isna(r[1]): continue
        add('2025', '0506', 'd672c6cb-42025423966_Vacant_Properties_-_OPRA.xlsx', '', '', '', f'{int(r[0]) if isinstance(r[0], float) else r[0]} {r[1]}',
            '2025', 'vacant property registration')

def middlesex():
    d = x('Copy of OPRA 014 25.xlsx')
    for _, r in d.iloc[1:].iterrows():
        if pd.isna(r[1]): continue
        add('2025', '1210', 'Copy of OPRA 014 25.xlsx', '', '', '', r[1], '2025', 'property list (type not stated)')

def winslow():
    d = x('property list.xlsx')
    for _, r in d.iterrows():
        if pd.isna(r[1]): continue
        add('2025', '0436', 'property list.xlsx', '', '', '', f'{r[0]} {r[1]}', '2025-04-25', 'property list (type not stated)')

def jersey_city():
    import pdfplumber
    with pdfplumber.open(os.path.join(RAW, 'VACANT BUILDING LIST.pdf')) as p:
        for page in p.pages:
            for line in (page.extract_text() or '').splitlines():
                m = re.match(r'^(.+?)\s+(\d{2,5})\s+(\d+(?:\.\d+)?)(?:Building|Lot|Land|Vacant)', line)
                if m: add('2025', '0906', 'VACANT BUILDING LIST.pdf', m.group(2), m.group(3), '', m.group(1), '', 'vacant building registration')

def franklin_assessments():
    import pdfplumber
    seen = set()
    with pdfplumber.open(os.path.join(RAW, 'VACANT_LIST_4-22-25.pdf')) as p:
        lines = [l for pg in p.pages for l in (pg.extract_text() or '').splitlines()]
    for i, l in enumerate(lines):
        if 'Last Installment Billed' in l and i >= 2:
            b = re.match(r'^(\d+(?:\.\d+)?)\s', lines[i - 2]); lt = re.match(r'^(\d+(?:\.\d+)?)\s', lines[i - 1])
            if b and lt and (b.group(1), lt.group(1)) not in seen:
                seen.add((b.group(1), lt.group(1)))
                add('2025', '1808', 'VACANT_LIST_4-22-25.pdf', b.group(1), lt.group(1), '', '', '2025-04-22', 'vacant property registration fee')

def quinton():
    add('2025', '1712', 'Vacant Property List.pdf', '24', '32', '', '23 Lake Avenue', '2025-04-17', 'vacant property list')
    add('2025', '1712', 'Vacant Property List.pdf', '3', '29', '', '60 Newbridge Road', '2025-04-17', 'vacant property list')

def beachwood():
    t = zipfile.ZipFile(os.path.join(RAW, 'OPRA REQUEST RESPONSE.docx')).read('word/document.xml').decode('utf8', 'ignore')
    t = re.sub(r'<w:p[ >]', '\n<w:p ', t); t = re.sub(r'<[^>]+>', '', t)
    year = ''
    for line in [l.strip() for l in t.splitlines() if l.strip()]:
        y = re.match(r'(20\d\d) Vacant/Abandoned List', line)
        if y: year = y.group(1); continue
        m = re.match(r'^(\d+[A-Z]? [A-Za-z][A-Za-z \.]+?)(?:\s+Block\s+([\d\.]+)\s+Lot\s+([\d\.]+))?(?:\s+[\d\-/]+)?(?:\s+PROPERTY REMOVED.*)?$', line)
        if m and year:
            st = 'vacant/abandoned list' + ('; removed from list' if 'REMOVED' in line.upper() else '')
            add('2025', '1505', 'OPRA REQUEST RESPONSE.docx', m.group(2) or '', m.group(3) or '', '', m.group(1), year, st)

def south_brunswick():
    d = x('Vacant Abandoned Property list 2024 final.xlsx')
    for _, r in d.iloc[5:].iterrows():
        if pd.isna(r[1]) or pd.isna(r[0]): continue
        num = re.split(r'[,\.]', str(r[0]))[0].strip().lstrip('0') or str(r[0]).strip()
        unit = re.sub(r'^[^,\.]*[,\.]\s*', '', str(r[0])).strip() if re.search(r'[,\.]', str(r[0])) else ''
        kind = 'commercial' if str(r[2]).strip().upper() == 'X' else ('residential' if str(r[3]).strip().upper() == 'X' else '')
        va = 'vacant' if str(r[4]).strip().upper() == 'X' else ('abandoned' if str(r[5]).strip().upper() == 'X' else '')
        addr = f'{num} {r[1]}' + (f' {unit}' if unit else '')
        add('2025', '1221', 'Vacant Abandoned Property list 2024 final.xlsx', '', '', '', addr, '2024',
            '; '.join(s for s in ['vacant/abandoned list', kind, va] if s))

def aberdeen():
    d = x('Vacant List.xlsx')
    for _, r in d.iloc[1:].iterrows():
        if pd.isna(r[0]) or pd.isna(r[1]): continue
        tail = ' '.join(str(v) for v in r[3:].tolist() if pd.notna(v)).lower()
        st = 'vacant property registration' + ('; later sold' if 'bought' in tail else '')
        add('2025', '1301', 'Vacant List.xlsx', '', '', '', f'{r[1]} {r[0]}', '2025', st)   # street names only; geocoded within Aberdeen

def atlantic_city():
    seen = set()
    for f in sorted(glob.glob(os.path.join(OCR, 'OPRA_Response_Ben_Abandoned_Property_List-*.txt'))):
        for line in open(f):
            m = re.search(r'\|\s*([0-9]{1,4})\s*\|\s*([0-9]{1,4}(?:\.[0-9]{1,2})?)\s*\|\s*[xX]\b', line)
            if m and m.groups() not in seen:
                seen.add(m.groups())
                add('2025', '0102', 'Atlantic City abandoned property list (scanned PDF)', m.group(1), m.group(2), '', '', '2025',
                    'abandoned property list (OCR)')

def maurice_river():
    f = os.path.join(OCR, 'vpr150.txt')
    for line in open(f):
        m = re.match(r'^(\d+(?:\.\d+)?)/(\d+(?:[\.,]\d+)?)\s+(.+)$', line.strip())
        if m:
            add('2025', '0609', 'VPR List as of 4 15 25.pdf', m.group(1), m.group(2).replace(',', '.'), '', m.group(3).replace('Carlilse', 'Carlisle').replace('Carlislse', 'Carlisle'),
                '2025-04-15', 'vacant property registration (OCR)')

def bergenfield():
    seen = set()
    for f in sorted(glob.glob(os.path.join(OCR, 'r90_Vacant_Properties_2-*.txt'))):
        for line in open(f):
            m = re.match(r'^(\d{1,5}[A-Z]?) ([A-Z][A-Z \.]+? (?:STREET|AVENUE|ROAD|DRIVE|PLACE|TERRACE|LANE|COURT|WAY|BOULEVARD))\b', line.strip())
            if m and m.group(0) not in seen:
                seen.add(m.group(0))
                add('2025', '0203', 'Vacant Properties 2.pdf', '', '', '', m.group(0), '2024', 'vacant property registration (OCR)')

# ---------- 2026 round (automated requests, May-June 2026) ----------
BARNEGAT = [  # carried over from the May 2026 registry review: (source block/lot, address, verified, likelihood)
 ('142.05', '6', '127 Alexander Dr', 'no', 'Unlikely'), ('92.55', '4', '3 Adrift Ave', 'no', 'Possible'),
 ('114.2', '17', '6 Anchor Rd', 'no', 'Likely'), ('114.26', '11', '18 Anchor Rd', 'no', 'Possible'),
 ('114.27', '32', '19 Anchor Rd', 'yes', 'Unlikely'), ('114.26', '9', '22 Anchor Rd', 'yes', 'Possible'),
 ('114.27', '34', '23 Anchor Rd', 'no', 'Possible'), ('114.27', '42', '39 Anchor Rd', 'no', 'Possible'),
 ('116.26', '5', '9 Aspen Cir', 'no', 'Likely'), ('114.15', '8', '95 Barnegat Blvd', 'no', 'Very likely'),
 ('114.05', '1', '102 Barnegat Blvd', 'no', 'Possible'), ('114.14', '100', '137 Barnegat Blvd', 'no', 'Possible'),
 ('114.03', '1', '7 Bayside Ave', 'yes', 'Very likely'), ('114.02', '16', '14 Bayside Ave', 'no', 'Possible'),
 ('114', '16', '50 Bayside Ave', 'no', 'Likely'), ('', '', '179 Bay Shore Dr', 'no', 'Possible'),
 ('128', '1.01', '148 Bengal Blvd', 'no', 'Likely'), ('161.10', '17.12', '44 Benjamin Ct', 'no', 'Very likely'),
 ('', '', '10 Bilge Ave', 'no', 'Likely'), ('114.22', '26', '36 Bowline St', 'no', 'Possible'),
 ('114.14', '57', '78 Bowline St', 'no', 'Very likely'), ('114.13', '4', '81 Bowline St', 'no', 'Possible'),
 ('95.31', '7', '2 Breeze Ter', 'no', 'Possible'), ('116.20', '14', '8 Briargrove Rd', 'yes', 'Likely'),
 ('116.18', '7', '4 Bucks Dr', 'yes', 'Likely'), ('116.16', '11', '10 Buxton Ct', 'no', 'Unlikely')]
def barnegat():
    for b, l, a, v, s in BARNEGAT:
        st = 'foreclosure registration' + ('; deregistered 2024' if a == '81 Bowline St' else '')
        add('2026', '1501', 'Barnegat foreclosure registry (OPRA response, May 2026)', b, l, '', a, '2026-05-21', st, v, s)

INLINE = [  # lists given in the body of 2026 reply emails (address only)
 ('0321', '2026-05-21', 'vacant/abandoned list', ['96 Lenape Trl', '64 Mohave Trl']),
 ('0807', '2026-05-27', 'vacant/foreclosed list', ['130 Thompson Ave', '113 S Poplar St', '653 Allen Ave', '163 Tomlin Station Rd', '43 E Broad St',
   '28 S Orchard St', '19 Casperson St', '476 Lock Ave', '1164 Berkley Rd', '79 Bramell Ln', '971 Ladner Ave', '307 Kirkbride Dr', '418 Swedesboro Rd']),
 ('0807', '2026-05-27', 'water off 12+ months; unoccupied', ['725 E Broad St', '371 W Broad St', '215 Democrat Rd', '172 S Forrest St', '10 Lough Ln',
   '18 Pine St', '116 Swedesboro Ave', '1025 Willow Dr']),
 ('1206', '2026-05-21', 'vacant/abandoned residential list (2024)', ['34J Locust Dr', '1311 Stone Ridge Cir']),
 ('1206', '2026-05-21', 'vacant/abandoned residential list (2024-2025)', ['3 Park Pl']),
 ('1206', '2026-05-21', 'vacant/abandoned residential list (2026)', ['1 Johns Pl']),
 ('1303', '2026-05-21', 'foreclosure/vacant list', ['10 Probasco Dr']),
 ('0264', '2026-05-21', 'unsafe structure notice', ['99 Crescent Ave', '101 E Prospect St']),
 ('0904', '2026-05-26', 'vacant list', ['16 N Third St', '114 Seventh St']),
 ('0904', '2026-05-26', 'vacant list; under renovation', ['304 Frank E Rodgers Blvd N', '307 Ann St']),
 ('0210', '2026-05-28', 'vacant', ['1 Short St']),
 ('0210', '2026-05-28', 'foreclosed', ['17 Garden St', '16 Seminole Ave']),
]
def inline_2026():
    for code, date, st, addrs in INLINE:
        for a in addrs: add('2026', code, 'reply email body', '', '', '', a, date, st)

def main():
    for fn in [paterson, lambda: prochamps('2025 54 Registration Export 04 21 2025.xlsx', '2025-04-21'),
               lambda: prochamps('Registration Export 04 16 2025.xlsx', '2025-04-16'),
               lambda: prochamps('Registration Export 04 21 2025.xlsx', '2025-04-21'),
               eht_otr, pilesgrove, dennis, oldmans, franklin_structures, north_wildwood, salem_city, middle, middlesex,
               winslow, jersey_city, franklin_assessments, quinton, beachwood, south_brunswick, aberdeen, atlantic_city,
               maurice_river, bergenfield, barnegat, inline_2026]:
        n0 = len(ROWS); fn(); print(f'{getattr(fn, "__name__", "?"):22} +{len(ROWS) - n0}')
    # de-duplicate exact repeats within a source
    seen, out = set(), []
    for r in ROWS:
        k = (r['muni_code'], r['block'], r['lot'], r['qualifier'], r['address'].upper(), r['source_file'])
        if k in seen: continue
        seen.add(k); out.append(r)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(out)
    print('rows', len(out))

if __name__ == '__main__':
    main()
