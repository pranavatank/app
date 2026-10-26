from types import SimpleNamespace
import pytest
from core.session import session
from engines.family_workbook import FamilyData
from ui.fd_planner_screen import FDPlannerScreen
from ui.widgets.family_money_tree import MoneyNode


@pytest.fixture
def screen(qapp,monkeypatch):
    import ui.fd_planner_screen as module
    data=FamilyData(people=[dict(id=1,name='A',tax_kind='individual'),dict(id=2,name='B',tax_kind='individual')],
                    accounts=[dict(id=11,person_id=1,person='A',bank='Unity Small Finance Bank',cash=100000,existing_fd=0,
                                   eligible=True,unknown_fds=0,label='Unity · A',details=[]),
                              dict(id=22,person_id=2,person='B',bank='Jana Small Finance Bank',cash=0,existing_fd=0,
                                   eligible=True,unknown_fds=0,label='Jana · B',details=[])],
                    source_path='family.xlsx')
    monkeypatch.setattr(module,'read_family_workbook',lambda *args,**kwargs:data)
    monkeypatch.setattr(FDPlannerScreen,'_refresh_rates',lambda self:None)
    monkeypatch.setattr(session,'privacy_mode',False)
    page=FDPlannerScreen();yield page
    page.tree.timer.stop();page.close()


def test_page_is_a_widget_and_main_settings_are_compact(screen):
    from PySide6.QtWidgets import QDialog
    assert not isinstance(screen,QDialog)
    assert not screen.settings_panel.isVisible()
    assert screen.family_pool.isChecked()
    assert screen.reserve.value()==15000
    assert screen.horizon.currentData()==36


def test_family_tree_has_person_and_bank_branches(screen):
    records=[item.record for item in screen.tree.scene().items() if isinstance(item,MoneyNode)]
    assert len([r for r in records if r['kind']=='person'])==2
    assert any(r['kind']=='account' for r in records)


def test_person_selection_changes_visible_account_branches(screen,qapp):
    screen.tree._choose(dict(kind='person',id=2,title='B'));qapp.processEvents()
    records=[item.record for item in screen.tree.scene().items() if isinstance(item,MoneyNode)]
    assert any(r['kind']=='account' and r['id']==22 for r in records)
    assert not any(r['kind']=='account' and r['id']==11 for r in records)


def test_animation_can_be_paused(screen):
    screen.animate.setChecked(False)
    assert not screen.tree.timer.isActive()


def test_many_bank_accounts_are_grouped_until_requested(screen,qapp):
    from copy import deepcopy
    data=deepcopy(screen._data)
    for i in range(6):
        account=dict(data.accounts[0],id=100+i,bank=f'Bank {i}',cash=5000+i)
        data.accounts.append(account)
    screen.tree.set_data(data)
    records=[item.record for item in screen.tree.scene().items() if isinstance(item,MoneyNode)]
    group=next(r for r in records if r['kind']=='more_accounts')
    assert len([r for r in records if r['kind']=='account'])==4
    screen.tree._choose(group);qapp.processEvents()
    records=[item.record for item in screen.tree.scene().items() if isinstance(item,MoneyNode)]
    assert len([r for r in records if r['kind']=='account'])==7


def test_missing_cash_is_never_labelled_as_a_confirmed_zero(screen):
    from copy import deepcopy
    data=deepcopy(screen._data);data.accounts[0]['cash_known']=False
    screen.tree.set_data(data)
    record=next(item.record for item in screen.tree.scene().items() if isinstance(item,MoneyNode) and item.record['kind']=='account')
    assert 'Not supplied' in record['subtitle']


def test_editing_the_reserve_invalidates_old_plan(screen):
    screen._plan=object();screen.reserve.setValue(20000)
    assert screen._plan is None
    assert screen.plan_table.rowCount()==0


def test_reloading_data_clears_previous_results(screen):
    screen._plan=object();screen.plan_table.setRowCount(1);screen.transfer_table.setRowCount(1)
    screen.explanation.setPlainText('Previous plan');screen._load_data()
    assert screen._plan is None
    assert screen.plan_table.rowCount()==screen.transfer_table.rowCount()==0
    assert not screen.explanation.toPlainText()


def test_failed_reload_does_not_keep_old_investable_cash(screen,monkeypatch):
    import ui.fd_planner_screen as module
    def missing(*args,**kwargs):raise OSError('Missing workbook')
    monkeypatch.setattr(module,'read_family_workbook',missing);screen._load_data()
    assert screen._data is None
    assert not screen.tree.scene().items()
    assert 'Missing workbook' in screen.status.text()


def test_fixed_deposit_button_navigates_to_page_without_dialog(qapp,monkeypatch):
    from ui.fixed_deposits_screen import FixedDepositsScreen
    from ui.dashboard_screen import _NAV_ITEMS
    calls=[];owner=SimpleNamespace(parent_window=SimpleNamespace(_navigate=calls.append))
    FixedDepositsScreen._on_open_planner(owner)
    assert _NAV_ITEMS[calls[0]][1]=='fd_planner'


def test_privacy_masks_kpis_and_clears_sensitive_tables(screen,monkeypatch):
    monkeypatch.setattr(session,'privacy_mode',True);screen.refresh()
    assert '100000' not in screen.cash_tile._value_lbl.text()
    assert '••••' in screen.cash_tile._value_lbl.text()
    assert screen.timeline.rowCount()==0


def test_background_task_returns_on_gui_thread_without_a_dialog(screen,qapp):
    from PySide6.QtCore import QEventLoop,QTimer,QThread
    from PySide6.QtWidgets import QDialog
    loop=QEventLoop();results=[]
    def done(value):results.append((value,QThread.currentThread()));loop.quit()
    screen._job(lambda:42,done,'Working')
    QTimer.singleShot(5000,loop.quit);loop.exec()
    assert results==[(42,qapp.thread())]
    assert not screen._busy
    assert not screen.findChildren(QDialog)
