from datetime import date,datetime,timedelta,timezone
import pytest
from engines.official_bank_rates import (BankRates,SavingsSlab,parse_html,parse_savings_rows,tenure_days,
                                         effective_date,load_bundles,save_bundles)


@pytest.mark.parametrize('label,bounds',[('7 - 14 days',(7,14)),('6 months to < 1 year',(182,364)),
                                        ('>2 Years < 3 Years',(731,1094)),('3 Years (1095 Days)',(1095,1095)),
                                        ('>1 Year - 2 Years (730 Days)',(366,730))])
def test_tenor_syntax_and_published_days_override_calendar(label,bounds):
    assert tenure_days(label,date(2026,10,26),year_days=365 if 'Years' in label else None)==bounds


def test_calendar_months_use_booking_date_instead_of_thirty_day_guess():
    assert tenure_days('6 months 1 day <=9 months',date(2026,10,26))==(183,273)


def test_savings_is_progressive_not_peak_rate_on_whole_balance():
    rows=[['Up to Rs. 1 Lakh','2.50%'],['More than Rs. 1 Lakh and Up to Rs. 5 Lakhs','3.50%'],
          ['More than Rs. 5 Lakhs','4.50%']]
    savings=parse_savings_rows(rows,0,1)
    b=BankRates('Bank','https://bank.example',datetime.now(timezone.utc).isoformat(),savings=savings)
    assert b.annual_savings(150000)==pytest.approx(4250)


def test_expired_savings_is_not_a_live_projection():
    b=BankRates('Bank','https://bank.example',(datetime.now(timezone.utc)-timedelta(days=2)).isoformat(),savings=[SavingsSlab(0,None,8)])
    with pytest.raises(ValueError):b.annual_savings(100000)


def jana_html():
    rows=[('7 Days - 14 Days','3.50%'),('15 Days - 60 Days','4.25%'),('61 Days - 90 Days','4.75%'),
          ('91 Days - 120 Days','5.00%'),('121 Days - 180 Days','6.00%')]
    table='<h4>Interest Rates for Retail Fixed Deposits for Domestic Customers: Effective from 22<sup>nd</sup> October 2026</h4><table><tr><th>Tenure</th><th>Regular FD Interest Rate(p.a.)</th><th>Sr. Citizen Interest Rate</th></tr>'
    table+=''.join(f'<tr><td>{label}</td><td>{rate}</td><td>9.99%</td></tr>' for label,rate in rows)+'</table>'
    return table


def test_duplicate_mobile_desktop_tables_do_not_break_official_fetch():
    bundle=parse_html('Jana Small Finance Bank',jana_html()*2,'https://www.jana.bank.in/interest-rates/')
    assert len(bundle.fd_rates)==5
    assert max(r.rate for r in bundle.fd_rates)==6
    assert all(r.customer=='general' for r in bundle.fd_rates)
    assert bundle.fd_effective=='2026-10-22'


def test_fd_plus_is_not_mistaken_for_callable_retail_table():
    html=jana_html().replace('Retail Fixed Deposits for Domestic Customers','FD Plus no premature withdrawal')
    with pytest.raises(ValueError):parse_html('Jana Small Finance Bank',html,'https://www.jana.bank.in/interest-rates/')


def test_future_effective_date_does_not_establish_current_rates():
    with pytest.raises(ValueError):effective_date('Effective from 1 January 2099')


def test_rate_cache_keeps_source_effective_and_checked_dates_separate(tmp_path):
    bundle=parse_html('Jana Small Finance Bank',jana_html(),'https://www.jana.bank.in/interest-rates/')
    path=tmp_path/'rates.json';save_bundles(path,{bundle.bank:bundle})
    loaded=load_bundles(path)[bundle.bank]
    assert loaded.fd_effective=='2026-10-22'
    assert loaded.checked_at==bundle.checked_at
    assert loaded.evidence_hash==bundle.evidence_hash


def test_failed_download_is_not_considered_a_usable_publication():
    bundle=BankRates('Bank','https://bank.example',datetime.now(timezone.utc).isoformat(),error='Blocked')
    assert not bundle.usable()


def test_savings_parser_rejects_a_missing_balance_band():
    rows=[['Up to Rs. 1 Lakh','2.50%'],['Above Rs. 5 Lakh up to Rs. 10 Lakh','4.50%']]
    with pytest.raises(ValueError):parse_savings_rows(rows,0,1)


@pytest.mark.parametrize('payload',[[],{'schema_version':1},{'schema_version':1,'banks':{'Bank':None}},
                                    {'schema_version':1,'banks':{'Bank':{'bank':'Different'}}}])
def test_malformed_cache_is_rejected_without_a_key_error(tmp_path,payload):
    import json
    path=tmp_path/'rates.json';path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):load_bundles(path)


def test_unity_retains_retail_column_date_instead_of_newer_bulk_date(monkeypatch):
    from types import SimpleNamespace
    from engines.official_bank_rates import parse_unity_pdf
    import pypdf
    text=('A. FIXED DEPOSIT RATE: Individual/Retail/NRE/NRO Depositors\n'
          +' '*41+'W.E.F\n'+' '*40+'15th July,\n'
          +' '*13+'Tenure'+' '*23+'2026'+' '*35+'W.E.F 02nd Oct, 2026\n'
          +' '*41+'< ₹ 3 cr\n'
          +'7 - 14 Days                         4.00%       6.00%\n'
          +'15 - 45 Days                        4.00%       6.00%\n'
          +'46 - 60 Days                        4.75%       6.00%\n'
          +'B. FIXED DEPOSIT RATE: Senior Citizen Depositors\n'
          +'C. SAVING DEPOSIT RATE:\nThe Saving deposit interest rate stands revised from 01st Aug, 2026\n'
          +'Upto 1 lakh                          4.50%\n>1 lakh-5 lakh                        6.00%\n>5 lakh                              7.00%\n')
    monkeypatch.setattr(pypdf,'PdfReader',lambda *args,**kwargs:SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda **kwargs:text)]))
    result=parse_unity_pdf(b'demo','https://unity.bank.in/disclosure.pdf',datetime.now(timezone.utc).isoformat())
    assert result.fd_effective=='2026-07-15'
    assert result.fd_rates[0].rate==4
    assert result.savings_effective=='2026-08-01'
    assert result.savings_method=='unverified'
