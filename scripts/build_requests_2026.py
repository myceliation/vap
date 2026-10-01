"""Build the 2026 OPRA request ledger from exported Gmail search pages.

Inputs (not published; contain correspondence metadata):
  work/gmail/sent_p*.json  - pages of `in:sent subject:"Vacant and Abandoned Properties Records"`
  work/gmail/resp_p*.json  - pages of `label:OPRA_Responses -from:me`
  work/in/GRC_filing_tracker.xlsx - non-responder tracker kept during the project
Output: rows for data/requests.csv (round=2026)
"""
import json, glob, re, collections, datetime as dt, sys, os, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from munis import match, BYCODE, MUNIS

# the requester's own addresses (set OPRA_SENDERS='a@x.com,b@y.com'); kept out of the repo
ME = tuple(x.strip().lower() for x in os.environ.get('OPRA_SENDERS', '').split(',') if x.strip()) or ('@gmail.com',)
# clerk addresses on free-mail providers, stored as sha1[:12] so no address is published
HASHED_ADDR = {'578be784e7e5':'0606'}
PORTALS = ('nextrequest.com', 'govpilot.com', 'justfoia.com', 'mycusthelp.net', 'govqa.us', 'mycivicrequests', 'civicplus')
# clerk-domain disambiguation for names shared by several NJ municipalities
DOMAIN_CODE = {
 'fairfieldnj.org':'0707','fairfieldtownshipnj.org':'0605',
 'franklin-twp.org':'1010','franklintwpwarren.org':'2105',
 'greenwichtwp.com':'0807','greenwichtownship.org':'2107',
 'hamiltonnj.com':'1103','townshipofhamilton.com':'0112',
 'hopewelltwp-nj.com':'0607','hopewelltwp.org':'1106','hopewellboro-nj.us':'1105',
 'lawrencetwp.com':'1107','lawrtwp.com':'0608',
 'mansfieldtownship-nj.gov':'2116','mansfieldtwp.com':'0318',
 'monroetownshipnj.org':'0811','monroetwp.com':'1212',
 'twpoceannj.gov':'1521','oceantwp.org':'1337',
 'springfieldtownshipnj.org':'0334','springfield-nj.us':'2017',
 'uniontwp-hcnj.org':'1025','uniontownship.com':'2019',
 'twp.washington.nj.us':'0818','twpofwashington.us':'0266','wtmorris.net':'1438','wtbcnj.org':'0336','washington-twp-warren.org':'2122',
}
EXTRA_DOMAIN = {'berlintwp.com':'0406','paramusborough.gov':'0246','hardyston.com':'1911'}
REF_CODE = {'OPRA-2026-00286':None,'OPRA-2026-00134':None,'South Orange Village':None}
NAME_FIX = {'bordentown borough':'Bordentown City','parsippany township':'Parsippany-Troy Hills Township','bordentown':'Bordentown City','parsippany':'Parsippany-Troy Hills Township'}

def _init_refs():
    REF_CODE['OPRA-2026-00286']=match('Leonia Borough')['code']
    REF_CODE['OPRA-2026-00134']=match('Point Pleasant Beach Borough')['code']
    REF_CODE['South Orange Village']=match('South Orange Village Township')['code']
_init_refs()

def ambiguous(name):
    from munis import MUNIS, norm
    n=norm(NAME_FIX.get(name.lower().strip(), name))
    return sum(1 for m in MUNIS if m['n']==n)>1

def is_me(s): return any(x in s.lower() for x in ME)
def dom(addr): return addr.lower().split('@')[-1].strip('> ')
def d(s): return dt.date.fromisoformat(s[:10])

def resolve(name, to_addrs):
    for a in to_addrs:
        a=a.lower()
        hh=hashlib.sha1(a.encode()).hexdigest()[:12]
        if hh in HASHED_ADDR: return BYCODE[HASHED_ADDR[hh]]
        if a in DOMAIN_CODE: return BYCODE[DOMAIN_CODE[a]]
        if dom(a) in DOMAIN_CODE: return BYCODE[DOMAIN_CODE[dom(a)]]
    n = NAME_FIX.get(name.lower(), name)
    return match(n)

def load(pattern):
    out=[]
    for f in sorted(glob.glob(pattern)): out += json.load(open(f))['threads']
    return out

AUTO = re.compile(r'automatic reply|out of (the )?office|no longer (with|work|being monitored)|not being monitored|retired|change of contact|auto.?reply', re.I)
BOUNCE = re.compile(r'delivery status notification|undeliverable|address not found|mail delivery', re.I)

def build(workdir):
    sent = load(f'{workdir}/gmail/sent_p*.json')
    resp = load(f'{workdir}/gmail/resp_p*.json')
    ledger = {}
    dom2codes = collections.defaultdict(set)
    seen_threads=set()
    for t in sent:
        m0=t['messages'][0]; s=m0['subject']
        mm=re.search(r'Records\s*[–-]\s*(.+)$', s)
        if not (mm and s.startswith('OPRA Request')): continue
        to=[x for x in m0.get('toRecipients',[]) if not is_me(x)]
        if not to: continue  # test sends to self
        mu=resolve(mm.group(1).strip(), to)
        if not mu: print('UNMATCHED', s, to); continue
        e=ledger.setdefault(mu['code'], dict(muni=mu, sends=[], msgs=[], to=set()))
        e['sends'].append(d(m0['date'])); e['to'].update(x.lower() for x in to)
        for a in to: dom2codes[dom(a)].add(mu['code'])
        for m in t['messages'][1:]:
            if not is_me(m['sender']): e['msgs'].append(m)
        seen_threads.add(t['id'])
    # name index for portal / subject matching
    unmatched=[]
    for t in resp:
        if t['id'] in seen_threads: continue
        msgs=[m for m in t['messages'] if not is_me(m['sender'])]
        if not msgs: continue
        code=None
        for m in msgs:
            if dom(m['sender']) in DOMAIN_CODE: code=DOMAIN_CODE[dom(m['sender'])]; break
        # subject naming the muni (unambiguous names only)
        for m in t['messages']:
            mm=re.search(r'Records\s*[–-]\s*(.+?)\s*$', m.get('subject',''))
            if mm and not code:
                to=[x for x in t['messages'][0].get('toRecipients',[]) if not is_me(x)]
                mu=resolve(mm.group(1), to) if (to or not ambiguous(mm.group(1))) else None
                if mu: code=mu['code']; break
        if not code:
            for m in msgs:
                ds=dom(m['sender'])
                if ds in dom2codes and len(dom2codes[ds])==1: code=next(iter(dom2codes[ds])); break
                for a in m.get('ccRecipients',[])+m.get('toRecipients',[]):
                    da=dom(a)
                    if da in dom2codes and len(dom2codes[da])==1: code=next(iter(dom2codes[da])); break
                if code: break
        if not code:
            txt=' '.join((m.get('subject','')+' '+m.get('snippet','')) for m in msgs)
            pm=re.search(r'(?:Township|Borough|City|Town|Village) of ([A-Z][A-Za-z\.\- ]+?)(?=[,\.:;\s](?:Open|OPRA|Public|Records|has|received|Request|Reference|Dear|NJ|New)|\s*$)', txt)
            if pm:
                kind=re.search(r'(Township|Borough|City|Town|Village) of', pm.group(0)).group(1)
                mu=match(f'{pm.group(1).strip()} {kind}')
                if mu: code=mu['code']
        if not code:
            txt=' '.join(m.get('subject','')+' || '+m.get('snippet','') for m in msgs)
            for rx in [r'Your (.+?)(?:, (?:NJ|New Jersey))? (?:OPRA Portal )?public records request',
                       r'\] (.+?)(?:, (?:NJ|New Jersey))? (?:OPRA Portal )?public rec',
                       r'^\s*([A-Z][A-Za-z\.\- ]+? (?:Township|Borough|City|Town)) Open Records Request',
                       r'\|\|\s*([A-Z][A-Za-z\.\- ]+? (?:Township|Borough|City|Town)) Open Records Request',
                       r'(?:The )?((?:Township|Borough|City|Town) of [A-Z][A-Za-z\.\- ]+?) (?:received|Open|has)']:
                pm=re.search(rx, txt)
                if pm:
                    nm=pm.group(1).strip()
                    k=re.match(r'(Township|Borough|City|Town|Village) of (.+)', nm, re.I)
                    if k: nm=f'{k.group(2)} {k.group(1)}'
                    nm=re.sub(r'\bOPRA Portal\b','',nm).strip()
                    mu=match(nm) or match(nm.title())
                    if mu: code=mu['code']; break
        if not code:
            for m in msgs:
                dm=dom(m['sender']); 
                if any(p in dm for p in PORTALS) or 'dca.nj.gov' in dm or 'googlemail' in dm: continue
                tok=re.sub(r'\.(gov|org|com|net|us|nj\.us)$','',dm).split('.')[-1]
                tok=re.sub(r'(nj|twp|township|boro|borough|cityof|city|townof|town|-|_)','',tok)
                cands=[mu for mu in MUNIS if mu['base'].replace(' ','')==tok]
                if len(cands)==1: code=cands[0]['code']; break
        if not code:
            for m in msgs:
                lp=m['sender'].split('@')[0]
                if any(p in dom(m['sender']) for p in ('justfoia.com','mycusthelp.net','govqa.us')):
                    nm=re.sub(r'NJ$','',lp); nm=re.sub(r'(?<=[a-z])(?=[A-Z])',' ',nm)
                    nm={'jerseycity':'Jersey City','franklintwpnj':'Franklin Township'}.get(lp.lower(), nm)
                    mu=match(nm, 'Somerset' if lp.lower()=='franklintwpnj' else None)
                    if mu: code=mu['code']; break
                if dom(m['sender']) in EXTRA_DOMAIN: code=EXTRA_DOMAIN[dom(m['sender'])]; break
                for ref,c in REF_CODE.items():
                    if ref in m.get('snippet','')+m.get('subject',''): code=c
                if code: break
                sm=re.search(r'Mansfield Township Burlington', m.get('subject',''))
                if sm: code='0318'; break
        if not code:
            unmatched.append(t); continue
        if code not in ledger:
            ledger[code]=dict(muni=BYCODE[code], sends=[], msgs=[], to=set(), via_portal_or_other=True)
        ledger[code]['msgs'] += msgs
    return ledger, unmatched

DENY = re.compile(r'\bdeni(ed|al)\b|exempt|gilleran|security information|cannot be (provided|released)|not (a )?government record|unable to fulfill|overly broad|invalid request', re.I)
NONE_ = re.compile(r'no (responsive )?(records|documents)|no records responsive|not responsive|does not (maintain|have|keep)|do not (maintain|have|keep)|not maintain|no such (list|records?)|there (is|are) no|don.t have (a|any)|no vacant|not have a (list|registry|vacant)|no list|has not adopted|not keep (a )?record|nothing responsive|no registry|none on file|no document|no longer require|not require (a )?registration|no records exist', re.I)
ADDR  = re.compile(r'\b\d{1,5}[A-Z]? [A-Z][a-z]+(?: [A-Z][a-z]+)? (?:Ave|Avenue|St|Street|Rd|Road|Dr|Drive|Trl|Trail|Ln|Lane|Ct|Court|Blvd|Pl|Place|Way|Cir|Circle|Ter|Terrace|Pike|Hwy)\b\.?')
LIST  = re.compile(r'\.xlsx?\b|\.csv\b|VPR|registry (is )?attached|list (is )?attached|attached (is|please find) (the|a) (list|registry|spreadsheet)|spreadsheet|below is a list|vacant/(abandoned|foreclosed) properties|houses listed|one house on|registration attached|listing', re.I)
FORM  = re.compile(r'(submit|use|fill out|complete).{0,40}(portal|form|nextrequest|govpilot|online)|must be submitted|request form|official form', re.I)
FULL  = re.compile(r'attached|attachment|please (find|see)|enclosed|fulfilled|provided in (their )?entirety|completed|documents? (are )?(attached|available)|responsive (records|documents)|released', re.I)
PART  = re.compile(r'redact|partial|in part|some of the records', re.I)
ACK   = re.compile(r'received your|in receipt|acknowledg|has been received|is being processed|extension|additional time|business days|reference (#|number)|been submitted|been published', re.I)

def classify(e):
    msgs=sorted(e['msgs'], key=lambda m:m['date'])
    def txt(m): return m.get('subject','')+' '+m.get('snippet','')
    real=[m for m in msgs if not AUTO.search(txt(m)) and not BOUNCE.search(txt(m)) and 'mailer-daemon' not in m['sender'].lower()]
    bounced=any('mailer-daemon' in m['sender'].lower() or BOUNCE.search(m.get('subject','')) for m in msgs)
    autos=[m for m in msgs if AUTO.search(txt(m))]
    if not real:
        return 'no_response', None, ('bounced' if bounced else ('auto-reply only' if autos else ''))
    text=' || '.join(txt(m) for m in real)
    big=any(int(m.get('sizeEstimate',0) or 0)>120000 for m in real)
    first_real=d(real[0]['date'])
    if LIST.search(text): out,note='fulfilled',''
    elif NONE_.search(text): out,note='no_records',''
    elif DENY.search(re.sub(r'not denied','',text,flags=re.I)): out,note='denied',''
    elif FORM.search(text) and not big: out,note='denied','required portal or form'
    elif PART.search(text): out,note='partial','redacted or partial'
    elif big or FULL.search(text): out,note='fulfilled',''
    elif ACK.search(text): out,note='pending','acknowledged, never completed'
    else: out,note='pending','replied, outcome unclear'
    if out=='fulfilled':
        delivered=[m for m in real if int(m.get('sizeEstimate',0) or 0)>120000 or FULL.search(m.get('snippet','')) or LIST.search(txt(m))]
        rd=d(delivered[0]['date']) if delivered else first_real
    else:
        hits=[m for m in real if (out=='denied' and (DENY.search(txt(m)) or FORM.search(txt(m)))) or (out=='no_records' and NONE_.search(txt(m)))]
        rd=d(hits[0]['date']) if hits else first_real
    return out, rd, note
