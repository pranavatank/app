"""Family-pool FD and liquid savings allocation, solved jointly with HiGHS.

Cash belongs to one planning pool. Recipient account holders remain distinct
tax/insurance buckets; estimates do not override beneficial-ownership law.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass,field
from datetime import date,timedelta
from math import ceil,floor,isfinite
from dateutil.relativedelta import relativedelta

from engines.fd_planner_math import fy_start,fy_label,normal_tax


def contract_curve(start,days,rate,frequency=4,basis='actual'):
    """Calendar coupon compounding; simple daily interest on broken periods.

    Completed quarters earn coupon/4, instead of accidentally varying their
    coupon with quarter length. FY accrual is adjusted on capitalization so
    its sum reconciles to each maturity quote. Bank rounding can still differ.
    """
    if days<1 or frequency not in (1,2,4,12) or basis not in ('actual','365'):
        raise ValueError('Invalid coupon calculation inputs.')
    balance=1.0;stub=0.0;period=1;day=start
    boundary=start+relativedelta(months=12//frequency)
    schedule=defaultdict(float);output={}
    for offset in range(1,days+1):
        denominator=365 if basis=='365' else (date(day.year+1,1,1)-date(day.year,1,1)).days
        accrued=balance*rate/100/denominator;stub+=accrued;schedule[fy_start(day)]+=accrued
        day+=timedelta(days=1)
        if day==boundary:
            coupon=balance*rate/100/frequency
            schedule[fy_start(day-timedelta(days=1))]+=coupon-stub
            balance+=coupon;stub=0;period+=1
            boundary=start+relativedelta(months=period*(12//frequency))
        output[offset]=dict(schedule)
    return output


def family_tax(income,kind='individual'):
    if not 0<=income<=5_000_000:raise ValueError('Tax model supports income between ₹0 and ₹50 lakh.')
    if kind=='individual':return normal_tax(income)
    if kind!='huf':raise ValueError('Tax attribution must be reviewed for joint/other entities.')
    # HUF may use the new-regime slab schedule, but not the individual 87A rebate.
    return sum(max(0,min(income,hi)-lo)*rate for lo,hi,rate in
               [(400000,800000,.05),(800000,1200000,.10),(1200000,1600000,.15),
                (1600000,2000000,.20),(2000000,2400000,.25),(2400000,5000000,.30)])*1.04


def year_fractions(start,end):
    output=defaultdict(float);current=start
    while current<end:
        boundary=min(end,date(current.year+1,1,1))
        denominator=(date(current.year+1,1,1)-date(current.year,1,1)).days
        while current<boundary:
            next_fy=date(fy_start(current)+1,4,1)
            next_day=min(boundary,next_fy)
            output[fy_start(current)]+=(next_day-current).days/denominator
            current=next_day
    return dict(output)


@dataclass
class FamilyPlan:
    status: str
    allocations: list=field(default_factory=list)
    cash_allocations: list=field(default_factory=list)
    transfers: list=field(default_factory=list)
    annual: list=field(default_factory=list)
    invested: float=0
    liquid: float=0
    fd_interest: float=0
    savings_interest: float=0
    gross_interest: float=0
    incremental_tax: float=0
    net_interest: float=0
    gap: float | None=None
    summary: str=''
    messages: list=field(default_factory=list)
    tax_complete: bool=False


def build_family_plan(data,bundles,*,reserve=0,months=36,family_pool=True,insurance=True,
                      tax_limits=True,bank_percent=20,lot_size=1000,time_limit=30,as_of=None,_frontier=False):
    import numpy as np
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import coo_matrix
    as_of=as_of or date.today();end=as_of+relativedelta(months=months);days=(end-as_of).days
    if not 1<=months<=120 or not 0<bank_percent<=100 or lot_size<1 or time_limit<=0:
        raise ValueError('Invalid horizon, bank concentration, allocation step or solver limit.')
    accounts=[a for a in data.accounts if a['eligible']]
    if len({a['id'] for a in accounts})!=len(accounts):raise ValueError('Duplicate account rows in family data.')
    if not accounts:raise ValueError('No eligible household accounts.')
    cash=sum(a['cash'] for a in accounts)
    if not isfinite(reserve) or not 0<=reserve<=cash:raise ValueError('Keep-available amount must be between zero and available family savings.')
    people={p['id']:p for p in data.people if p['tax_kind'] in ('individual','huf')}
    accounts=[a for a in accounts if a['person_id'] in people]
    fractions=year_fractions(as_of,end)
    candidates=[];curves={};coverage_notes=[]
    wealth=cash+sum(a['existing_fd'] for a in accounts)
    fixed_by_bank={bank:sum(a['existing_fd'] for a in accounts if a['bank']==bank) for bank in {a['bank'] for a in accounts}}
    headroom_by_bank={bank:max(0,wealth*bank_percent/100-fixed) for bank,fixed in fixed_by_bank.items()}
    if bank_percent<100:
        for bank,fixed in fixed_by_bank.items():
            if fixed>wealth*bank_percent/100+.03:
                coverage_notes.append(f'{bank}: existing locked FDs already exceed the selected household bank cap; no additional money is allocated there. Existing contracts are not broken.')
    for account in accounts:
        bundle=bundles.get(account['bank'])
        if not bundle or not bundle.usable():continue
        if bank_percent<100 and headroom_by_bank[account['bank']]<lot_size:continue
        if insurance and (not account['terms_complete'] or not account['cash_known']):
            coverage_notes.append(f'{account["person"]} · {account["bank"]}: new insured FDs excluded until existing holdings are complete.')
            continue
        if insurance and account['existing_fd']>=500000:continue
        for rate in bundle.fd_rates:
            if rate.customer!='general' or not rate.usable(as_of) or (insurance and not rate.bank_insured):continue
            last=min(days,rate.max_days)
            if last<rate.min_days:continue
            tenures=range(rate.min_days,last+1)
            if _frontier:
                anchors={rate.min_days,last}
                anchors.update(((as_of+relativedelta(months=m))-as_of).days for m in [3,6,9,12,18,24,36,48,60,84,120])
                for year in fractions:
                    boundary=(date(year+1,4,1)-as_of).days
                    anchors.update([boundary-1,boundary,boundary+1])
                tenures=sorted(d for d in anchors if rate.min_days<=d<=last)
            for tenure in tenures:
                frequency=1 if tenure<=rate.simple_until_days else rate.compounding
                key=(rate.rate,last,frequency,rate.day_basis)
                if key not in curves:curves[key]=contract_curve(as_of,last,rate.rate,frequency,rate.day_basis)
                schedule=curves[key][tenure];profit=sum(schedule.values())
                candidates.append((account,rate,tenure,schedule,profit))
                if len(candidates)>60000:raise ValueError('More than 60,000 tenure choices. Use a shorter horizon or select fewer banks.')
    available_sa=any(b.usable() and b.savings and b.savings_method=='progressive' for b in bundles.values())
    if not candidates and not available_sa:
        raise ValueError('No fresh official FD or savings slabs are available. Refresh bank rates; unavailable rates are excluded.')
    seed=None;seed_seconds=0
    if not _frontier and len(candidates)>1500 and time_limit>=4:
        seed_seconds=min(4,time_limit*.25)
        try:
            seed=build_family_plan(data,bundles,reserve=reserve,months=months,family_pool=family_pool,insurance=insurance,
                                   tax_limits=tax_limits,bank_percent=bank_percent,lot_size=lot_size,
                                   time_limit=seed_seconds,as_of=as_of,_frontier=True)
        except (ValueError,RuntimeError):seed=None
    costs=[];lower=[];upper=[];integer=[];rows=[];lows=[];highs=[]
    def var(cost=0,lo=0,hi=np.inf,whole=False):
        i=len(costs);costs.append(cost);lower.append(lo);upper.append(hi);integer.append(int(whole));return i
    def add(coeffs,lo=-np.inf,hi=np.inf):rows.append(coeffs);lows.append(lo);highs.append(hi)
    xs=[]
    for account,rate,tenure,schedule,profit in candidates:
        available=cash if family_pool else sum(a['cash'] for a in accounts if a['person_id']==account['person_id'])
        maximum=floor(min(available,cash-reserve,rate.max_amount)/lot_size)
        if insurance:
            maximum=min(maximum,floor(max(0,500000-account['existing_fd'])/(1+profit)/lot_size))
        x=var(-profit*lot_size,hi=max(0,maximum),whole=True);xs.append(x)
        if rate.min_amount>lot_size:
            used=var(hi=1,whole=True);add({x:1,used:-maximum},hi=0);add({x:1,used:-ceil(rate.min_amount/lot_size)},lo=0)
    ys={};annual_savings={};usable_sa={}
    # Each account gets a final liquid balance. This explicitly moves source
    # savings away before testing destination insurance; no double counting.
    for account in accounts:
        aid=account['id'];y=var(hi=cash);ys[aid]=y
        bundle=bundles.get(account['bank']);interest=var(cost=-sum(fractions.values()),hi=cash*.20)
        annual_savings[aid]=interest
        if not bundle or not bundle.usable() or not bundle.savings or bundle.savings_method!='progressive':
            # Unknown savings products may retain their original cash, but
            # never attract transfers on an invented zero-return assumption.
            upper[y]=account['cash']
            upper[interest]=0;continue
        usable_sa[aid]=bundle
        cap=bundle.savings[-1].upper
        maximum=min(cash,cap if cap is not None else cash);upper[y]=maximum
        knots=sorted({0.0,maximum,*[s.upper for s in bundle.savings if s.upper is not None and 0<s.upper<maximum]})
        balance_row={y:1};interest_row={interest:1};choose={}
        for lo,hi in zip(knots,knots[1:]):
            on=var(hi=1,whole=True);position=var(hi=hi-lo)
            add({position:1,on:-(hi-lo)},hi=0);choose[on]=1
            first,last=bundle.annual_savings(lo),bundle.annual_savings(hi)
            balance_row[on]=-lo;balance_row[position]=-1
            interest_row[on]=-first;interest_row[position]=-(last-first)/(hi-lo)
        if choose:
            add(choose,lo=1,hi=1);add(balance_row,lo=0,hi=0);add(interest_row,lo=0,hi=0)
        else:upper[interest]=0
    balance={**{x:lot_size for x in xs},**{y:1 for y in ys.values()}}
    add(balance,lo=cash,hi=cash)
    add({x:lot_size for x in xs},hi=max(0,cash-reserve))
    if not family_pool:
        for pid in people:
            row={xs[i]:lot_size for i,c in enumerate(candidates) if c[0]['person_id']==pid}
            row.update({ys[a['id']]:1 for a in accounts if a['person_id']==pid})
            budget=sum(a['cash'] for a in accounts if a['person_id']==pid)
            add(row,lo=budget,hi=budget)
    duration=sum(fractions.values())
    for bank in {a['bank'] for a in accounts}:
        fixed=sum(a['existing_fd'] for a in accounts if a['bank']==bank)
        row={xs[i]:lot_size*(1+c[4]) for i,c in enumerate(candidates) if c[0]['bank']==bank}
        for a in accounts:
            if a['bank']==bank:
                row[ys[a['id']]]=1;row[annual_savings[a['id']]]=duration
        if bank_percent<100:add(row,hi=max(0,wealth*bank_percent/100-fixed))
    prior=defaultdict(float)
    for a in accounts:
        for d in a['details']:
            if not d['active']:continue
            for year,factor in d['interest_by_fy'].items():prior[(a['id'],year)]+=d['principal']*factor
    for account in accounts:
        aid=account['id'];indices=[i for i,c in enumerate(candidates) if c[0]['id']==aid]
        if not indices:continue
        on=var(hi=1,whole=True)
        fd_cap=max(0,500000-account['existing_fd']) if insurance else cash
        add({**{xs[i]:lot_size for i in indices},on:-fd_cap},hi=0)
        if insurance:
            # Existing uninsured savings may stay liquid in a bank, but a NEW
            # FD is called protected only if that account bucket's total fits.
            row={xs[i]:lot_size*(1+candidates[i][4]) for i in indices}
            room=max(0,500000-account['existing_fd'])
            add({xs[i]:lot_size*(1+candidates[i][4]) for i in indices},hi=room)
            cash_bound=headroom_by_bank[account['bank']] if bank_percent<100 else cash*(1+.2*duration)
            big_m=max(0,cash_bound-room)
            row.update({ys[aid]:1,annual_savings[aid]:duration,on:big_m})
            add(row,hi=room+big_m)
        if tax_limits:
            for year in fractions:
                add({xs[i]:lot_size*candidates[i][3].get(year,0) for i in indices},
                    hi=max(0,50000-prior[(aid,year)]))
    for pid,person in people.items():
        own_accounts=[a for a in accounts if a['person_id']==pid]
        kind=person['tax_kind']
        knots=([0,1200000,1200000+60000/.85,1600000,2000000,2400000,5000000] if kind=='individual'
               else [0,400000,800000,1200000,1600000,2000000,2400000,5000000])
        for year in fractions:
            baseline=person['income_by_fy'].get(year,0);family_tax(baseline,kind)
            earnings={xs[i]:lot_size*c[3].get(year,0) for i,c in enumerate(candidates) if c[0]['person_id']==pid and year in c[3]}
            for a in own_accounts:earnings[annual_savings[a['id']]]=fractions[year]
            if tax_limits:
                limit=1200000 if kind=='individual' else 400000
                add(earnings,hi=max(0,limit-baseline))
                if baseline<=limit:
                    continue  # Under this explicit cap, incremental tax is zero.
            tax=var(cost=1);income_row=dict(earnings);tax_row={tax:1};choose={}
            for lo,hi in zip(knots,knots[1:]):
                if hi<baseline:continue
                on=var(hi=1,whole=True);position=var(hi=hi-lo)
                add({position:1,on:-(hi-lo)},hi=0);choose[on]=1
                income_row[on]=-lo;income_row[position]=-1
                tax_row[on]=-family_tax(lo,kind);tax_row[position]=-(family_tax(hi,kind)-family_tax(lo,kind))/(hi-lo)
            add(choose,lo=1,hi=1);add(income_row,lo=-baseline,hi=-baseline);add(tax_row,lo=0,hi=0)
    rr=[];cc=[];vv=[]
    for r,row in enumerate(rows):
        for column,value in row.items():
            if value:rr.append(r);cc.append(column);vv.append(value)
    matrix=coo_matrix((vv,(rr,cc)),shape=(len(rows),len(costs))).tocsc()
    result=milp(np.array(costs),integrality=np.array(integer),bounds=Bounds(lower,upper),
                constraints=LinearConstraint(matrix,lows,highs),options={'time_limit':max(.5,time_limit-seed_seconds),'mip_rel_gap':.0001})
    def bounded_seed():
        seed.status='feasible_frontier'
        dual=getattr(result,'mip_dual_bound',None)
        if dual is not None and isfinite(dual):
            baseline_tax=sum(family_tax(p['income_by_fy'].get(y,0),p['tax_kind']) for p in people.values() for y in fractions)
            upper_net=-float(dual)+baseline_tax
            seed.gap=max(0,(upper_net-seed.net_interest)/max(1,abs(seed.net_interest)))
        else:seed.gap=None
        gap='not yet proven' if seed.gap is None else f'{seed.gap*100:.3f}% search gap'
        seed.summary=f'{len(seed.allocations)} FD placements · {len(seed.transfers)} family transfers · Best found plan ({gap}).'
        if not seed.tax_complete:seed.summary+=' Tax estimates are provisional.'
        seed.messages.append('A feasible plan was audited first using slab endpoints, calendar tenures and FY boundaries; the complete daily-tenure model was then searched within the time budget.')
        return seed
    if result.x is None:
        if seed is not None and result.status!=2:return bounded_seed()
        if result.status==1:raise ValueError('Search time limit reached before finding a plan. Try a shorter horizon; no financial limit was relaxed.')
        raise ValueError('No feasible family plan with these limits. Review missing balances, reserve or bank exposure settings. No limit was relaxed.')
    solution=result.x.copy()
    for i,whole in enumerate(integer):
        if whole:
            if abs(solution[i]-round(solution[i]))>.0001:raise RuntimeError('Non-integral solution; no plan published.')
            solution[i]=round(solution[i])
    checks=matrix@solution
    if np.any(checks>np.array(highs)+.03) or np.any(checks<np.array(lows)-.03):raise RuntimeError('Family allocation failed its constraint audit.')
    complete=data.tax_complete and all(year in p['income_by_fy'] for p in people.values() for year in fractions)
    plan=FamilyPlan('optimal' if result.status==0 else 'feasible_time_limit',tax_complete=complete)
    new_income=defaultdict(float)
    for i,(a,rate,tenure,schedule,profit) in enumerate(candidates):
        amount=float(solution[xs[i]]*lot_size)
        if amount<.01:continue
        plan.allocations.append(dict(person_id=a['person_id'],person=a['person'],bank=a['bank'],account_id=a['id'],
                                     account=a['label'],amount=amount,rate=rate.rate,days=tenure,
                                     maturity_date=(as_of+timedelta(days=tenure)).isoformat(),maturity_amount=amount*(1+profit),
                                     interest=amount*profit,rate_id=rate.id,source_url=rate.source_url))
        for year,factor in schedule.items():new_income[(a['person_id'],year)]+=amount*factor
    for a in accounts:
        amount=float(solution[ys[a['id']]])
        if amount<.01:continue
        annual=float(solution[annual_savings[a['id']]])
        plan.cash_allocations.append(dict(person_id=a['person_id'],person=a['person'],bank=a['bank'],account_id=a['id'],
                                         account=a['label'],amount=amount,annual_interest=annual,interest=annual*duration,
                                         rate_available=a['id'] in usable_sa))
        for year,fraction in fractions.items():new_income[(a['person_id'],year)]+=annual*fraction
    plan.invested=sum(r['amount'] for r in plan.allocations);plan.liquid=sum(r['amount'] for r in plan.cash_allocations)
    plan.fd_interest=sum(r['interest'] for r in plan.allocations);plan.savings_interest=sum(r['interest'] for r in plan.cash_allocations)
    plan.gross_interest=plan.fd_interest+plan.savings_interest
    for (pid,year),interest in sorted(new_income.items()):
        p=people[pid];baseline=p['income_by_fy'].get(year,0)
        tax=family_tax(min(5000000,baseline+interest),p['tax_kind'])-family_tax(baseline,p['tax_kind'])
        plan.incremental_tax+=tax
        plan.annual.append(dict(person=p['name'],financial_year=fy_label(year),baseline=baseline,new_interest=interest,
                                taxable_total=baseline+interest,incremental_tax=tax,tax_kind=p['tax_kind'],complete=p['tax_complete'] and year in p['income_by_fy']))
    plan.net_interest=plan.gross_interest-plan.incremental_tax
    plan.gap=float(result.mip_gap) if getattr(result,'mip_gap',None) is not None else None
    # Net transfers retain money already at the chosen destination account.
    target=defaultdict(float)
    for row in plan.allocations+plan.cash_allocations:target[row['account_id']]+=row['amount']
    surplus=[[a,max(0,a['cash']-target[a['id']])] for a in accounts]
    for dest in accounts:
        needed=max(0,target[dest['id']]-dest['cash'])
        for source in surplus:
            origin,available=source
            if not family_pool and origin['person_id']!=dest['person_id']:continue
            take=min(available,needed)
            if take>.01:
                plan.transfers.append(dict(from_person=origin['person'],from_account=origin['label'],to_person=dest['person'],
                                           to_account=dest['label'],amount=take))
                source[1]-=take;needed-=take
        if needed>.03:raise RuntimeError('Family transfer audit failed.')
    plan.allocations.sort(key=lambda r:(r['person'],r['bank'],r['days']))
    plan.messages=[
        ('Family money is pooled; recipient names are conditional tax-attribution scenarios, not a legal determination.' if family_pool
         else 'Separate owner budgets are enforced; no money is transferred between different family members.'),
        'HUF uses its own slab calculation without the individual ₹12 lakh rebate.',
        'Savings projections hold today’s progressive rates constant on static balances; future rates and income can change.',
        'Future FD maturities and salary receipts are not invested before arrival. No future FD renewal rate is invented.',
        'Missing future income is a scenario input, not a promise of zero income. Account minimum-balance fees and charges require product-specific review.',
        'Exposure includes existing FDs plus new FD maturity values and projected retained savings.',
        'No transfer or FD booking is executed by the planner.',
    ]+coverage_notes
    if not complete:plan.messages.append('Existing FD details or future-year income are incomplete; income/TDS headroom and after-tax results are provisional.')
    unknown_cash=[r['account'] for r in plan.cash_allocations if not r['rate_available']]
    if unknown_cash:plan.messages.append('Unverified savings rates excluded from return estimates: '+', '.join(unknown_cash))
    gap='unavailable' if plan.gap is None else f'{plan.gap*100:.3f}%'
    plan.summary=f'{len(plan.allocations)} FD placements · {len(plan.transfers)} family transfers · {plan.status} (gap {gap}).'
    if not plan.tax_complete:plan.summary+=' Tax estimates provisional: FD terms or future income are incomplete.'
    if _frontier:
        plan.status='feasible_frontier';plan.gap=None
    if seed is not None and seed.net_interest>plan.net_interest+.01:return bounded_seed()
    return plan
