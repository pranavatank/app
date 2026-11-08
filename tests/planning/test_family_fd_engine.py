from datetime import date,datetime,timezone
from itertools import product
import pytest
from engines.family_workbook import FamilyData
from engines.official_bank_rates import BankRates,SavingsSlab
from engines.fd_rates import RateCard
from engines.family_fd_engine import build_family_plan,family_tax,year_fractions,contract_curve


def source(cash=100000):
    people=[dict(id=1,name='A',birth_date=date(1990,1,1),tax_kind='individual',income_by_fy={},tax_complete=True),
            dict(id=2,name='B',birth_date=date(1998,1,1),tax_kind='individual',income_by_fy={},tax_complete=True)]
    accounts=[dict(id=1,person_id=1,person='A',bank='One',label='One · A',cash=cash,cash_known=True,
                   existing_fd=0,terms_complete=True,eligible=True,details=[],unknown_fds=0),
              dict(id=2,person_id=2,person='B',bank='Two',label='Two · B',cash=0,cash_known=True,
                   existing_fd=0,terms_complete=True,eligible=True,details=[],unknown_fds=0)]
    return FamilyData(people=people,accounts=accounts)


def bundle(bank,fd=8,savings=2,minimum=1000,maximum=29999999):
    today=date.today();stamp=datetime.now(timezone.utc).isoformat()
    rate=RateCard(id=bank,bank=bank,min_days=365,max_days=365,rate=fd,customer='general',
                  effective_from=today.isoformat(),checked_at=stamp,source_url='https://bank.example/rates',
                  verified=True,bank_insured=True,min_amount=minimum,max_amount=maximum)
    return BankRates(bank,'https://bank.example/rates',stamp,fd_rates=[rate],savings=[SavingsSlab(0,None,savings,'All balances')])


def solve(data,rates,**options):
    defaults=dict(reserve=20000,months=12,bank_percent=100,insurance=False,tax_limits=False)
    defaults.update(options);return build_family_plan(data,rates,**defaults)


def test_pooled_cash_can_fund_a_different_family_member():
    data=source();rates={'One':bundle('One',6),'Two':bundle('Two',9)}
    plan=solve(data,rates)
    assert plan.invested==80000
    assert {r['person'] for r in plan.allocations}=={'B'}
    assert any(t['from_person']=='A' and t['to_person']=='B' for t in plan.transfers)
    assert plan.invested+plan.liquid==pytest.approx(100000,abs=.02)


def test_pooling_can_be_disabled_without_leaking_funds():
    plan=solve(source(),{'One':bundle('One',6),'Two':bundle('Two',9)},family_pool=False)
    assert {r['person'] for r in plan.allocations}=={'A'}
    assert not any(t['from_person']!=t['to_person'] for t in plan.transfers)


def test_savings_is_an_actual_competing_investment_choice():
    plan=solve(source(),{'One':bundle('One',4,8),'Two':bundle('Two',4,7)})
    assert plan.invested==0
    assert plan.liquid==pytest.approx(100000,abs=.02)
    assert plan.savings_interest>7000


def test_liquid_reserve_is_not_invested_even_with_high_fd_rates():
    plan=solve(source(),{'One':bundle('One',10),'Two':bundle('Two',9)},reserve=45000)
    assert plan.invested<=55000
    assert plan.liquid>=45000-.02


def test_insured_new_fds_include_retained_cash_and_existing_fds():
    data=source(200000);data.accounts[0]['existing_fd']=450000
    plan=solve(data,{'One':bundle('One',10),'Two':bundle('Two',8)},reserve=20000,insurance=True)
    for account in data.accounts:
        deposits=[r for r in plan.allocations if r['account_id']==account['id']]
        if deposits:
            total=account['existing_fd']+sum(r['maturity_amount'] for r in deposits)
            total+=sum(r['amount']+r['interest'] for r in plan.cash_allocations if r['account_id']==account['id'])
            assert total<=500000+.03


def test_huf_does_not_get_the_individual_rebate():
    assert family_tax(1200000,'individual')==0
    assert family_tax(1200000,'huf')==pytest.approx(62400)
    assert family_tax(400000,'huf')==0


def test_solver_matches_small_exhaustive_fd_and_savings_choices():
    data=source(6000);rates={'One':bundle('One',6,1,2000,4000),'Two':bundle('Two',8,2,2000,4000)}
    plan=solve(data,rates,reserve=2000)
    coefficients=[sum(contract_curve(date.today(),365,r)[365].values()) for r in (6,8)]
    duration=sum(year_fractions(date.today(),date.today().fromordinal(date.today().toordinal()+365)).values())
    best=max(sum(x*c for x,c in zip(amounts,coefficients))+(6000-sum(amounts))*.02*duration
             for amounts in product([0,2000,3000,4000],repeat=2) if sum(amounts)<=4000)
    assert plan.gross_interest==pytest.approx(best,abs=.02)


def test_unknown_savings_rates_do_not_attract_new_transfers():
    data=source();rates={'One':bundle('One',8)}
    plan=solve(data,rates)
    assert all(r['account_id']!=2 for r in plan.cash_allocations)


def test_invalid_reserve_does_not_silently_change_the_input():
    with pytest.raises(ValueError):solve(source(),{'One':bundle('One')},reserve=100001)


def test_calendar_quarters_match_bank_style_broken_period_quote():
    profit=sum(contract_curve(date(2026,9,14),501,8,basis='365')[501].values())
    assert profit*99000==pytest.approx(11382.06636,abs=.001)


def test_full_search_timeout_keeps_an_audited_seed_and_its_bound(monkeypatch):
    import scipy.optimize
    from dataclasses import replace
    from types import SimpleNamespace
    original=scipy.optimize.milp;calls=[];bound=[]
    def limited(costs,**kwargs):
        calls.append(len(costs))
        if len(calls)==1:
            result=original(costs,**kwargs);assert result.x is not None
            bound.append(result.fun-100)
            return result
        return SimpleNamespace(x=None,status=1,mip_dual_bound=bound[0])
    monkeypatch.setattr(scipy.optimize,'milp',limited)
    rates={bank:bundle(bank,rate) for bank,rate in [('One',6),('Two',8)]}
    for bank in rates:
        rates[bank].fd_rates=[replace(rates[bank].fd_rates[0],min_days=1,max_days=1096)]
    plan=solve(source(),rates,months=36,time_limit=8)
    assert len(calls)==2 and calls[0]<calls[1]
    assert plan.status=='feasible_frontier'
    assert plan.invested+plan.liquid==pytest.approx(100000,abs=.03)
    assert plan.liquid>=20000-.03
    assert plan.gap==pytest.approx(100/plan.net_interest,rel=.001)
    assert 'Best found plan' in plan.summary
