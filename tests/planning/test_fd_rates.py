from datetime import date,datetime,timedelta,timezone
import pytest
from engines.fd_rates import RateCard


def sample(**overrides):
    values=dict(id='one',bank='A',min_days=7,max_days=90,rate=7.5,customer='general',
                effective_from=date.today().isoformat(),checked_at=datetime.now(timezone.utc).isoformat(),
                source_url='https://bank.example/rates',verified=True,bank_insured=True)
    values.update(overrides)
    return RateCard(**values)


def test_freshness_distinguishes_fetch_from_confirmation():
    assert sample().usable(date.today())
    assert not sample(verified=False).usable(date.today())
    assert not sample(checked_at=(datetime.now(timezone.utc)-timedelta(hours=25)).isoformat()).usable(date.today())
    assert not sample(checked_at=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()).usable(date.today())
    assert not sample().usable(date.today()+timedelta(days=1))


@pytest.mark.parametrize('fields',[{'rate':float('nan')},{'rate':25},{'min_days':100,'max_days':7},
                                    {'source_url':'file:///rates'},{'checked_at':'2026-10-25T12:00:00'}])
def test_invalid_quotes_fail_closed(fields):
    with pytest.raises(ValueError): sample(**fields)
