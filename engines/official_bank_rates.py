"""Live official savings and callable retail FD rate cards for family banks.

Only bank-hosted HTTPS documents are fetched. Windows system trust verifies
certificates; TLS verification is never disabled. No family data is sent.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import asdict,dataclass,field
from datetime import date,datetime,timezone
import hashlib,io,json,re,ssl
from pathlib import Path
from urllib.parse import urljoin,urlparse
from urllib.request import Request,urlopen
from dateutil.relativedelta import relativedelta
from bs4 import BeautifulSoup

from engines.fd_rates import RateCard


REGISTRY={
 'Unity Small Finance Bank':('https://unity.bank.in/','unity.bank.in'),
 'Jana Small Finance Bank':('https://www.jana.bank.in/interest-rates/','jana.bank.in'),
 'Ujjivan Small Finance Bank':('https://www.ujjivansfb.bank.in/interest-rates','ujjivansfb.bank.in'),
 'Equitas Small Finance Bank':('https://equitas.bank.in/','equitas.bank.in'),
 'IDFC FIRST Bank':('https://www.idfcfirst.bank.in/personal-banking/deposits/fixed-deposit/fd-interest-rates','idfcfirst.bank.in'),
 'HDFC Bank':('https://www.hdfc.bank.in/interest-rates','hdfc.bank.in'),
 'State Bank of India':('https://sbi.bank.in/web/interest-rates/deposit-rates/retail-domestic-term-deposits','sbi.bank.in'),
 'AU Small Finance Bank':('https://www.au.bank.in/interest-rates','au.bank.in'),
 'YES Bank':('https://www.yes.bank.in/personal-banking/yes-individual/deposits/fixed-deposit','yes.bank.in'),
 'Bank of India':('https://bankofindia.bank.in/interest-rate/rupee-term-deposit-rate','bankofindia.bank.in'),
 'Rajkot Nagarik Sahakari Bank':('https://rnsb.bank.in/','rnsb.bank.in'),
}


def fresh(stamp,as_of=None):
    try:
        now=datetime.now(timezone.utc);checked=datetime.fromisoformat(stamp)
        return checked.tzinfo is not None and -300<=(now-checked).total_seconds()<=86400 and (as_of or date.today())==date.today()
    except (ValueError,TypeError):return False


@dataclass(frozen=True)
class SavingsSlab:
    lower: float
    upper: float | None
    rate: float
    label: str=''

    def __post_init__(self):
        from math import isfinite
        if (not isfinite(self.lower) or self.lower<0 or not isfinite(self.rate) or not 0<=self.rate<=20
                or (self.upper is not None and (not isfinite(self.upper) or self.upper<=self.lower))):
            raise ValueError('Invalid savings rate or balance band.')


@dataclass
class BankRates:
    bank: str
    source_url: str
    checked_at: str=''
    fd_rates: list=field(default_factory=list)
    savings: list=field(default_factory=list)
    fd_effective: str=''
    savings_effective: str=''
    evidence_hash: str=''
    error: str=''
    notes: list=field(default_factory=list)
    savings_method: str='progressive'
    savings_source_url: str=''

    def usable(self):return not self.error and bool(self.fd_rates or self.savings) and fresh(self.checked_at)
    def annual_savings(self,balance):
        if not self.usable() or not self.savings:raise ValueError('No fresh official savings rate.')
        if self.savings_method!='progressive':raise ValueError('Savings calculation method needs review.')
        if balance<0:raise ValueError('Savings balance cannot be negative.')
        total=0.0;last=0.0
        for slab in self.savings:
            if slab.lower!=last:raise ValueError('Savings bands must be contiguous from zero.')
            width=max(0,min(balance,slab.upper if slab.upper is not None else balance)-slab.lower)
            total+=width*slab.rate/100
            last=slab.upper
        covered=self.savings[-1].upper
        if covered is not None and balance>covered+.01:raise ValueError('Balance exceeds published savings slabs; contact the bank.')
        return total
    def details_text(self):
        lines=[self.bank,f'Official source: {self.source_url}',f'Checked: {self.checked_at}',
               f'Savings effective: {self.savings_effective or "not available"}',f'FD effective: {self.fd_effective or "not available"}']
        lines.extend(f'{s.label}: {s.rate:g}% on the amount inside this band' for s in self.savings)
        lines.extend(f'{r.tenure_label or str(r.min_days)+"–"+str(r.max_days)+" days"}: {r.rate:g}%' for r in self.fd_rates)
        if self.error:lines.append(self.error)
        return '\n'.join(lines+self.notes)


def fetch_document(url,host):
    if urlparse(url).scheme!='https' or not _host_ok(url,host):raise ValueError('Only the selected official bank host is allowed.')
    try:
        import truststore
        context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:context=ssl.create_default_context()
    request=Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,application/pdf'})
    with urlopen(request,timeout=22,context=context) as response:
        if not _host_ok(response.url,host):raise ValueError('Bank redirected to a different host; review source.')
        content=response.read(5_000_001);final=response.url
    if len(content)>5_000_000:raise ValueError('Official document exceeded the size limit.')
    return content,final


def _host_ok(url,host):
    actual=(urlparse(url).hostname or '').lower()
    return actual==host or actual.endswith('.'+host)


def _clean(text):
    text=re.sub(r'[\u200b-\u200f\xa0]',' ',str(text))
    text=re.sub(r'(\d)\s*(?:st|nd|rd|th)\b',r'\1',text,flags=re.I)
    return ' '.join(text.split())


def effective_date(text):
    text=_clean(text)
    patterns=[r'(\d{1,2}\s+[A-Za-z]+,?\s+20\d{2})',r'([A-Za-z]+\s+\d{1,2},?\s+20\d{2})',r'(\d{1,2}[./-]\d{1,2}[./-]20\d{2})']
    found=[]
    for pattern in patterns:
        for candidate in re.findall(pattern,text):
            for fmt in ['%d %B %Y','%d %b %Y','%B %d %Y','%b %d %Y','%d/%m/%Y','%d.%m.%Y','%d-%m-%Y']:
                try:found.append(datetime.strptime(candidate.replace(',',''),fmt).date());break
                except ValueError:pass
    dates=sorted({d for d in found if d<=date.today()})
    if not dates:raise ValueError('No unambiguous effective date in the selected rate section.')
    return dates[-1].isoformat()


def _tenor_value(text,as_of,year_days=None):
    explicit=re.findall(r'\((\d+)\s*days?\)',text.lower())
    if explicit:return int(explicit[-1])
    text=re.sub(r'\([^)]*\)','',text.lower())
    parts=re.findall(r'(\d+)\s*(years?|yrs?|months?|mos?|days?)',text)
    if not parts:raise ValueError(f'Unsupported tenure {text}')
    residue=re.sub(r'\d+\s*(?:years?|yrs?|months?|mos?|days?)','',text).strip()
    if residue:raise ValueError(f'Ambiguous tenure {text}')
    years=sum(int(n) for n,u in parts if u.startswith(('year','yr')))
    months=sum(int(n) for n,u in parts if u.startswith(('month','mo')))
    days=sum(int(n) for n,u in parts if u.startswith('day'))
    if year_days is not None:
        return years*year_days+((as_of+relativedelta(months=months,days=days))-as_of).days
    return ((as_of+relativedelta(years=years,months=months,days=days))-as_of).days


def tenure_days(label,as_of=None,year_days=None):
    as_of=as_of or date.today();text=_clean(label).lower().replace('–','-').replace('—','-')
    text=text.strip()
    short=re.fullmatch(r'(\d+)\s*-\s*(\d+)\s*(days?|months?|years?)',text)
    if short:text=f'{short[1]} {short[3]} - {short[2]} {short[3]}'
    text=text.replace('and up to','to').replace('upto','to').replace('up to','to')
    if not re.search(r'\bto\b|-|<=',text):
        text=re.sub(r'(?<=[a-z])\s*<\s*(?=\d)',' to < ',text)
    pieces=re.split(r'\bto\b|\s*-\s*|<=',text,maxsplit=1)
    if len(pieces)==1:
        value=_tenor_value(text,as_of,year_days);return value,value
    lower,upper=pieces
    exclude_lower=lower.strip().startswith(('>','above'))
    lower=re.sub(r'^(?:>|above)\s*','',lower.strip())
    exclude_upper=bool(re.match(r'\s*(?:<|less than)',upper))
    upper=re.sub(r'^\s*(?:<|less than)\s*','',upper).strip()
    lo=_tenor_value(lower,as_of,year_days)+(1 if exclude_lower else 0)
    hi=_tenor_value(upper,as_of,year_days)-(1 if exclude_upper else 0)
    if not 1<=lo<=hi<=3653:raise ValueError('Invalid tenure bounds')
    return lo,hi


def _rate(text):
    match=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*%?\s*\*?\s*(?:p\.?a\.?)?\s*',_clean(text),re.I)
    return float(match[1]) if match and 0<float(match[1])<=20 else None


def _context(table):
    heading=table.find_previous(['h1','h2','h3','h4','h5','h6'])
    parts=[]
    if heading:
        for node in heading.next_elements:
            if node is table:break
            if isinstance(node,str):parts.append(str(node))
            if sum(map(len,parts))>7000:break
    return _clean(' '.join(parts))


def _currency_values(text):
    text=_clean(text).lower().replace(',','')
    parts=re.findall(r'(\d+(?:\.\d+)?)\s*(crores?|cr\b|lakhs?|lacs?|lakh\b)?',text)
    values=[]
    for value,unit in parts:
        factor=10_000_000 if unit.startswith(('crore','cr')) else (100_000 if unit else 1)
        values.append(float(value)*factor)
    return values


def parse_savings_rows(rows,label_column,rate_column):
    slabs=[];last=0.0
    for row in rows:
        if len(row)<=max(label_column,rate_column):continue
        label=_clean(row[label_column]);rate=_rate(row[rate_column])
        if rate is None:continue
        amounts=_currency_values(label)
        if len(amounts)>=2 and abs(amounts[0]-last)>.01:
            raise ValueError('Savings bands have a missing or overlapping lower boundary.')
        if len(amounts)==1 and re.search(r'^(above|more than|>)',label,re.I) and abs(amounts[0]-last)>.01:
            raise ValueError('Savings bands have a missing or overlapping lower boundary.')
        if not amounts and re.search('across all|all balances',label,re.I):upper=None
        elif not amounts:continue
        elif len(amounts)>=2:upper=amounts[-1]
        elif re.search(r'^(above|more than|>)',label,re.I):upper=None
        else:upper=amounts[-1]
        if upper is not None and upper<=last:raise ValueError('Savings bands overlap or decrease.')
        slabs.append(SavingsSlab(last,upper,rate,label));last=upper or last
        if upper is None:break
    if not slabs:raise ValueError('No explicit progressive savings bands.')
    return slabs


def _cards_from_rows(bundle,rows,rate_column,context,day_basis='actual'):
    effective=effective_date(context)
    cards=[];seen={};skipped=[]
    for row in rows:
        if len(row)<=rate_column:continue
        rate=_rate(row[rate_column]);label=_clean(row[0])
        if rate is None or not re.search(r'\d',label):continue
        try:lo,hi=tenure_days(label,year_days=365 if bundle.bank=='Jana Small Finance Bank' else None)
        except ValueError:skipped.append(label);continue
        key=(lo,hi)
        if key in seen and seen[key]!=rate:raise ValueError('Conflicting published FD rows.')
        seen[key]=rate
        cards.append(RateCard(id=f'{bundle.bank}:{lo}:{hi}:general',bank=bundle.bank,min_days=lo,max_days=hi,rate=rate,
                              customer='general',effective_from=effective,checked_at=bundle.checked_at,source_url=bundle.source_url,
                              min_amount={'HDFC Bank':5000,'IDFC FIRST Bank':10000}.get(bundle.bank,1000),max_amount=29_999_999,
                              compounding=1 if bundle.bank=='HDFC Bank' and hi<=_tenor_value('6 months',date.today()) else 4,
                              simple_until_days=(_tenor_value('6 months',date.today())-1) if bundle.bank=='Unity Small Finance Bank' else 0,
                              day_basis=day_basis,verified=True,
                              origin='official_page',evidence_hash=bundle.evidence_hash,tenure_label=label,bank_insured=True))
    unique={c.id:c for c in cards}
    if len(unique)<3:raise ValueError('Too few explicit retail FD slabs to use this document.')
    # Overlapping calendar-month and exact-day special tenures are excluded,
    # rather than guessing which offer takes precedence on that booking date.
    ordered=sorted(unique.values(),key=lambda c:(c.min_days,c.max_days))
    for a,b in zip(ordered,ordered[1:]):
        if a.max_days>=b.min_days:raise ValueError('Overlapping FD tenures need bank-specific precedence review.')
    bundle.fd_rates=ordered;bundle.fd_effective=effective
    if skipped:bundle.notes.append('Unsupported FD labels excluded: '+', '.join(skipped))


def parse_html(bank,html,url,checked_at=None):
    checked_at=checked_at or datetime.now(timezone.utc).isoformat()
    bundle=BankRates(bank,url,checked_at,evidence_hash=hashlib.sha256(html.encode()).hexdigest())
    soup=BeautifulSoup(html,'html.parser');tables=[]
    for table in soup.find_all('table'):
        rows=[[_clean(c.get_text(' ',strip=True)) for c in row.find_all(['th','td'])] for row in table.find_all('tr')]
        tables.append((table,rows,_context(table)))
    signatures=set();fd_candidates=[]
    for table,rows,context in tables:
        if not rows:continue
        header=' '.join(rows[0]).lower();tabletext=table.get_text(' ',strip=True).lower()
        fd_col=None
        if bank=='Jana Small Finance Bank' and 'regular fd interest' in header and 'retail fixed' in context.lower():fd_col=1
        elif bank=='Ujjivan Small Finance Bank' and 'domestic fixed deposits and sampoorna nidhi' in context.lower() and 'tenure' in header:fd_col=1
        elif bank=='HDFC Bank' and 'tenure bucket' in header and re.search(r'<\s*3\s*crore',header):fd_col=1
        elif bank=='State Bank of India' and 'revised rates for public' in header:
            fd_col=next(i for i,h in enumerate(rows[0]) if 'revised rates for public' in h.lower());context+=' '+' '.join(rows[0])
        elif bank=='IDFC FIRST Bank' and 'fixed deposits' in header and 'less than' in header and '3 crore' in header:
            fd_col=1;context+=' '+' '.join(rows[0])
        if fd_col is not None:
            signature=json.dumps(rows)
            if signature not in signatures:fd_candidates.append((rows,fd_col,context));signatures.add(signature)
        saving_cols=None
        if bank=='Jana Small Finance Bank' and 'savings account balance' in header:saving_cols=(1,2)
        elif bank=='Ujjivan Small Finance Bank' and 'account balance' in header and context.lower().startswith('savings account'):saving_cols=(0,1)
        elif bank=='HDFC Bank' and 'savings balance' in header:saving_cols=(0,1)
        elif bank=='IDFC FIRST Bank' and ('progressive' in tabletext or 'savings account balance' in header):saving_cols=(0,1)
        elif bank=='State Bank of India' and 'savings' in header and 'interest' in header:saving_cols=(0,1)
        if saving_cols:
            try:
                savings=parse_savings_rows(rows[1:],*saving_cols);effective=effective_date(context+' '+' '.join(rows[0]))
                if bundle.savings and bundle.savings!=savings:raise ValueError('More than one savings product on this page.')
                bundle.savings=savings;bundle.savings_effective=effective;bundle.savings_source_url=url
            except ValueError as exc:bundle.notes.append(f'Savings: {exc}')
    if len(fd_candidates)==1:
        try:_cards_from_rows(bundle,*fd_candidates[0])
        except ValueError as exc:bundle.notes.append(f'FDs: {exc}')
    elif len(fd_candidates)>1:bundle.notes.append('Multiple retail FD tables; no rate chosen automatically.')
    if not bundle.fd_rates and not bundle.savings:raise ValueError('No unambiguous current retail FD or savings table found.')
    return bundle


def parse_unity_pdf(raw,url,stamp):
    from pypdf import PdfReader
    text='\n'.join(page.extract_text(extraction_mode='layout') for page in PdfReader(io.BytesIO(raw)).pages)
    bundle=BankRates('Unity Small Finance Bank',url,stamp,evidence_hash=hashlib.sha256(raw).hexdigest())
    # The first document section is explicitly Individual/Retail. The later
    # senior section and newer bulk-column date must never replace its date.
    match=re.search(r'A\.\s+FIXED DEPOSIT RATE:(.*?)(?=B\.\s+FIXED DEPOSIT RATE:)',text,re.S|re.I)
    if not match:raise ValueError('Unity individual-retail disclosure section is missing.')
    section=match[1];lines=section.splitlines();fd_rows=[]
    header=' '.join(line[:53].replace('Tenure','') for line in lines[:6])
    if '<' not in header or '3 cr' not in header.lower():raise ValueError('Unity retail amount column is not identifiable.')
    for line in lines:
        parts=re.split(r'\s{2,}',line.strip())
        if len(parts)<2 or _rate(parts[1]) is None or not re.search(r'\b(day|days|months?)\b',parts[0],re.I):continue
        if re.fullmatch(r'12 Months [–-] 1 Day',parts[0],re.I):
            bundle.notes.append('Ambiguous 12-month-minus-one-day entry excluded; confirm it with the bank.')
            continue
        if re.fullmatch(r'202 Days [–-] 364 Days',parts[0],re.I):
            bundle.notes.append('202–364-day band excluded because of the ambiguous neighbouring special-tenure entry.')
            continue
        fd_rows.append(parts[:2])
    _cards_from_rows(bundle,fd_rows,1,header,day_basis='365')
    savings=re.search(r'C\.\s+SAVING DEPOSIT RATE:(.*)',text,re.S|re.I)
    if savings:
        sa_rows=[]
        for line in savings[1].splitlines():
            parts=re.split(r'\s{2,}',line.strip())
            if len(parts)>=2 and re.search(r'lakh',parts[0],re.I) and _rate(parts[1]) is not None:sa_rows.append(parts[:2])
        if sa_rows:
            bundle.savings=parse_savings_rows(sa_rows,0,1)
            bundle.savings_effective=effective_date(savings[1][:500]);bundle.savings_source_url=url
            bundle.savings_method='unverified'
            bundle.notes.append('Published Unity savings bands are shown, but their progressive/whole-balance calculation basis must be confirmed before projecting savings income.')
    if not bundle.fd_rates and not bundle.savings:raise ValueError('Unity disclosure layout needs review.')
    return bundle


def refresh_bank(bank):
    if bank not in REGISTRY:return BankRates(bank,'',error='No official bank source configured.')
    url,host=REGISTRY[bank];stamp=datetime.now(timezone.utc).isoformat()
    try:
        raw,final=fetch_document(url,host)
        if bank=='Unity Small Finance Bank':
            soup=BeautifulSoup(raw,'html.parser')
            links=[urljoin(final,a['href']) for a in soup.find_all('a',href=True)
                   if 'interest rates for savings account and fixed deposit' in a.get_text(' ',strip=True).lower()]
            if len(set(links))!=1:raise ValueError('Could not identify the bank current combined disclosure.')
            url=links[0];raw,final=fetch_document(url,host);return parse_unity_pdf(raw,final,stamp)
        bundle=parse_html(bank,raw.decode('utf-8',errors='replace'),final,stamp)
        if bank=='IDFC FIRST Bank' or bank=='State Bank of India':
            # Dedicated current savings page; no old PDF or archive fallback.
            sa_url=('https://www.idfcfirst.bank.in/personal-banking/accounts/savings-account/interest-rate'
                    if bank=='IDFC FIRST Bank' else 'https://sbi.bank.in/web/interest-rates/savings-bank-deposits')
            try:
                sa_raw,sa_final=fetch_document(sa_url,host);sa=parse_html(bank,sa_raw.decode('utf-8',errors='replace'),sa_final,stamp)
                bundle.savings=sa.savings;bundle.savings_effective=sa.savings_effective;bundle.savings_source_url=sa_final
            except Exception as exc:bundle.notes.append(f'Savings page: {exc}')
        return bundle
    except Exception as exc:
        return BankRates(bank,url,stamp,error=str(exc))


def save_bundles(path,bundles):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    payload={bank:{**asdict(bundle),'fd_rates':[asdict(r) for r in bundle.fd_rates]} for bank,bundle in bundles.items()}
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps({'schema_version':1,'banks':payload},indent=2),encoding='utf-8');temp.replace(path)


def load_bundles(path):
    path=Path(path)
    if not path.exists():return {}
    payload=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload,dict) or payload.get('schema_version')!=1 or not isinstance(payload.get('banks'),dict):
        raise ValueError('Unsupported bank-rate cache.')
    output={}
    for bank,values in payload['banks'].items():
        try:
            values=dict(values)
            if values.get('bank')!=bank:raise ValueError('Bank-rate cache key does not match its source.')
            values['fd_rates']=[RateCard(**r) for r in values.get('fd_rates',[])]
            if any(r.bank!=bank for r in values['fd_rates']):raise ValueError('FD quote belongs to a different bank.')
            values['savings']=[SavingsSlab(**r) for r in values.get('savings',[])]
            output[bank]=BankRates(**values)
        except (TypeError,KeyError,AttributeError) as exc:
            raise ValueError('Invalid bank-rate cache fields.') from exc
    return output


def refresh_banks(banks,path):
    result={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(refresh_bank,bank):bank for bank in banks}
        for job in as_completed(jobs):result[jobs[job]]=job.result()
    # Failures replace cached confirmations. An unsuccessful refresh never
    # quietly leaves yesterday's rate presented as current.
    save_bundles(path,result)
    return result
