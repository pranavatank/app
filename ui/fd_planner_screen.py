"""A full-page family FD planner with a readable money-flow tree."""
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QObject,QThread,Signal,Slot
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QDoubleSpinBox,QComboBox,
                              QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,QCheckBox,
                              QToolButton,QGridLayout,QSpinBox,QFileDialog,QTextBrowser)
import config
from core.session import session
from core.settings import get_setting,set_setting
from engines.family_workbook import read_family_workbook
from ui.theme import Theme
from ui.widgets.kpi_tile import KpiTile
from ui.widgets.family_money_tree import FamilyMoneyTree


class _PlanningTask(QObject):
    finished=Signal(object)
    error=Signal(object)
    def __init__(self,fn):super().__init__();self.fn=fn
    @Slot()
    def run(self):
        try:self.finished.emit(self.fn())
        except Exception as exc:self.error.emit(exc)


class FDPlannerScreen(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self._data=None;self._plan=None;self._bundles={};self._busy=False;self._loading=True;self._revision=0
        self._build();self._load_data();self._loading=False
        try:
            from engines.official_bank_rates import load_bundles
            self._bundles=load_bundles(Path(config.DATA_DIR)/'family_bank_rates.json');self._populate_rates()
        except (ImportError,ValueError,OSError,TypeError):pass
        self.refresh()
        if self._data and not any(bundle.usable() for bundle in self._bundles.values()):QTimer.singleShot(350,self._refresh_rates)
    def _button(self,label,slot,primary=False):
        button=Theme.btn(label,'primary' if primary else 'secondary',height=38)
        button.clicked.connect(slot);return button
    def _build(self):
        self.setObjectName('familyPlannerPage')
        self.setStyleSheet('QWidget#familyPlannerPage QLabel#plannerTitle {font-size:24px; font-weight:700;}'
                           'QWidget#familyPlannerPage QLabel#kpiValue {font-size:24px; font-weight:700;}'
                           'QWidget#familyPlannerPage QToolButton#plannerSettings {border:0; padding:4px;}')
        outer=QVBoxLayout(self);outer.setContentsMargins(22,16,22,14);outer.setSpacing(10)
        header=QHBoxLayout();title=QLabel('Family FD planner');title.setObjectName('plannerTitle');header.addWidget(title)
        header.addStretch();self.refresh_rates=self._button('Refresh my bank rates',self._refresh_rates);header.addWidget(self.refresh_rates)
        outer.addLayout(header)
        self.source_label=QLabel('Your family accounts, current bank rates and one investment plan.');self.source_label.setWordWrap(True);outer.addWidget(self.source_label)
        kpis=QHBoxLayout()
        self.cash_tile=KpiTile('Family savings',0,accent='primary')
        self.fd_tile=KpiTile('Plan in FDs',0,accent='success')
        self.return_tile=KpiTile('Projected interest',0,accent='info')
        for tile in [self.cash_tile,self.fd_tile,self.return_tile]:tile.setFixedHeight(88);kpis.addWidget(tile)
        outer.addLayout(kpis)
        controls=QHBoxLayout()
        controls.addWidget(QLabel('Keep available'))
        self.reserve=QDoubleSpinBox();self.reserve.setRange(0,1e11);self.reserve.setDecimals(0);self.reserve.setPrefix('₹ ');self.reserve.setSingleStep(100000)
        self.reserve.setFixedHeight(40)
        self.reserve.setMinimumWidth(145);controls.addWidget(self.reserve)
        controls.addSpacing(12);controls.addWidget(QLabel('Plan up to'))
        self.horizon=QComboBox()
        self.horizon.setFixedHeight(40)
        for label,months in [('1 year',12),('2 years',24),('3 years',36),('5 years',60)]:self.horizon.addItem(label,months)
        self.horizon.setCurrentIndex(2);controls.addWidget(self.horizon)
        controls.addStretch();self.make_plan=self._button('Build my plan',self._build_plan,True);controls.addWidget(self.make_plan)
        outer.addLayout(controls)
        settings_line=QHBoxLayout()
        self.settings_toggle=QToolButton();self.settings_toggle.setObjectName('plannerSettings');self.settings_toggle.setText('Plan settings');self.settings_toggle.setCheckable(True)
        self.settings_toggle.setArrowType(Qt.ArrowType.RightArrow);self.settings_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.settings_toggle.toggled.connect(self._toggle_settings);settings_line.addWidget(self.settings_toggle)
        self.pooling_label=QLabel('Family transfers enabled · general-customer rates');self.pooling_label.setProperty('textrole','secondary')
        settings_line.addWidget(self.pooling_label);settings_line.addStretch()
        settings_line.addWidget(self._button('Reload data',self._load_data));settings_line.addWidget(self._button('Choose workbook',self._choose_workbook))
        outer.addLayout(settings_line)
        self.settings_panel=QWidget();grid=QGridLayout(self.settings_panel);grid.setContentsMargins(0,0,0,0)
        self.family_pool=QCheckBox('Allow transfers across family accounts');self.family_pool.setChecked(True)
        self.insurance=QCheckBox('Keep new FDs within ₹5 lakh bank cover');self.insurance.setChecked(True)
        self.insurance.setToolTip('For each holder and legal bank, include existing FDs, new maturity values and retained savings. Incomplete buckets are excluded from new insured FDs.')
        self.tax_limit=QCheckBox('Enforce annual interest / income limits');self.tax_limit.setChecked(True)
        self.tax_limit.setToolTip('Known annual FD interest up to ₹50,000 per holder/bank; ordinary taxable income up to ₹12 lakh for individuals or ₹4 lakh for HUF. Incomplete income makes the estimate provisional.')
        self.concentration=QSpinBox();self.concentration.setRange(5,100);self.concentration.setValue(20);self.concentration.setSuffix(' %')
        grid.addWidget(self.family_pool,0,0);grid.addWidget(self.insurance,0,1);grid.addWidget(self.tax_limit,1,0)
        grid.addWidget(QLabel('Maximum family exposure to one bank'),1,1);grid.addWidget(self.concentration,1,2)
        self.settings_panel.hide();outer.addWidget(self.settings_panel)
        self.status=QLabel('');self.status.setWordWrap(True);outer.addWidget(self.status)
        self.tabs=QTabWidget();outer.addWidget(self.tabs,1)
        flow=QWidget();flow_layout=QVBoxLayout(flow);flow_layout.setContentsMargins(0,5,0,0)
        toolbar=QHBoxLayout();self.flow_hint=QLabel('Select a person to see their bank accounts and FD branches.');toolbar.addWidget(self.flow_hint,1)
        self.animate=QCheckBox('Animate flow');self.animate.setChecked(True);toolbar.addWidget(self.animate)
        for label,factor in [('−',.9),('+',1.1)]:
            button=self._button(label,lambda checked=False,f=factor:self.tree.zoom(f));button.setFixedWidth(38)
            button.setStyleSheet(button.styleSheet()+'QPushButton {padding:0px;}');toolbar.addWidget(button)
        toolbar.addWidget(self._button('Reset view',lambda:self.tree.reset_zoom()));flow_layout.addLayout(toolbar)
        self.tree=FamilyMoneyTree();self.tree.nodeSelected.connect(self._selected_node);self.animate.toggled.connect(self.tree.set_animation)
        flow_layout.addWidget(self.tree,1);self.detail=QLabel('');self.detail.setWordWrap(True);flow_layout.addWidget(self.detail)
        self.tabs.addTab(flow,'Money flow')
        rates=QWidget();rates_layout=QVBoxLayout(rates)
        self.rates_table=self._table(['My bank','Savings slabs','FD rate range','Effective / checked','Status'])
        self.rates_table.currentCellChanged.connect(self._rate_details);rates_layout.addWidget(self.rates_table,1)
        self.rate_source_label=QLabel('Select a bank for its exact savings and FD slabs.');self.rate_source_label.setWordWrap(True);rates_layout.addWidget(self.rate_source_label)
        self.rate_source_label.setOpenExternalLinks(True)
        self.slab_table=self._table(['Product','Balance / tenure slab','Rate p.a.','Effective from','Basis'])
        rates_layout.addWidget(self.slab_table,1);self.tabs.addTab(rates,'My bank rates')
        self.timeline=self._table(['Date','Person','Bank','Expected receipt','Amount']);self.tabs.addTab(self.timeline,'Upcoming money')
        self.plan_table=self._table(['Person','Bank / account','Amount','Tenure','Rate','Maturity date','Expected interest'])
        plan_page=QWidget();plan_layout=QVBoxLayout(plan_page);plan_layout.addWidget(self.plan_table,1)
        self.explain_toggle=QToolButton();self.explain_toggle.setText('Why these allocations');self.explain_toggle.setCheckable(True)
        self.explanation=QTextBrowser();self.explanation.setMaximumHeight(190);self.explanation.hide()
        self.explain_toggle.toggled.connect(self.explanation.setVisible)
        plan_layout.addWidget(self.explain_toggle);plan_layout.addWidget(self.explanation)
        self.tabs.addTab(plan_page,'Plan details')
        self.transfer_table=self._table(['From person / account','To person / account','Transfer amount'])
        self.tabs.addTab(self.transfer_table,'Transfers')
        self.note=QLabel('Animation shows a plan, not executed transfers. Savings rates can change.');self.note.setProperty('textrole','secondary');self.note.setWordWrap(True);outer.addWidget(self.note)
        for control in [self.reserve,self.horizon,self.family_pool,self.insurance,self.tax_limit,self.concentration]:
            signal=control.currentIndexChanged if isinstance(control,QComboBox) else (control.toggled if isinstance(control,QCheckBox) else control.valueChanged)
            signal.connect(self._invalidate)
    def _table(self,headers):
        table=QTableWidget(0,len(headers));table.setHorizontalHeaderLabels(headers);table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True);return table
    def _fill(self,table,rows):
        table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            for c,value in enumerate(row):table.setItem(r,c,QTableWidgetItem(str(value)))
    def _path(self):
        configured=get_setting('family_planner_workbook','')
        if configured:return Path(configured)
        return Path(config.DATA_DIR)/'data'/'Data 26-27.xlsx'
    def _load_data(self):
        if self._busy:return
        self._invalidate()
        try:
            from models.person import get_all_persons
            from models.bank_account import get_all_accounts
            from models.fixed_deposit import get_all_fds
            from models.income_expectation import get_income_expectations
            self._data=read_family_workbook(self._path(),ledger_people=get_all_persons(),ledger_accounts=get_all_accounts(),
                                          ledger_fds=get_all_fds(),ledger_expected=get_income_expectations())
            self._loading=True;self.reserve.setValue(round(self._data.cash*.15));self._loading=False
            self._plan=None;self.tree.set_data(self._data);self._refresh_amounts()
            self.source_label.setText(f'{Path(self._data.source_path).name} · {len(self._data.people)} family entries · {len(self._data.banks)} banks · Read-only source')
            self._fill(self.timeline,[(r['date'],r['person'],r['bank'],r['kind'],session.mask(r['amount'])) for r in self._data.receipts])
            self._populate_rates()
            missing=sum(a['unknown_fds'] for a in self._data.accounts)
            self.status.setText(f'Family cash is pooled for planning. {missing} existing FDs still need detailed terms.' if missing else 'Family cash is pooled for planning. Refresh rates, then build your plan.')
        except Exception as exc:
            self._data=None;self.tree.set_data(None);self._refresh_amounts()
            self.timeline.setRowCount(0);self.rates_table.setRowCount(0);self.slab_table.setRowCount(0)
            self.source_label.setText('No workbook loaded.')
            self.status.setText(f'Could not load family data: {exc}')
    def _choose_workbook(self):
        if self._busy:return
        path,_=QFileDialog.getOpenFileName(self,'Choose family workbook',str(self._path()),'Excel workbooks (*.xlsx)')
        if path:set_setting('family_planner_workbook',path);self._load_data()
    def _populate_rates(self):
        if not self._data:return
        rows=[]
        for bank in self._data.banks:
            bundle=self._bundles.get(bank)
            if not bundle:
                rows.append((bank,'Refresh needed','Refresh needed','—','Not verified yet'));continue
            fresh=bundle.usable()
            saving='Unavailable';fd='Unavailable'
            if bundle.savings:
                rates=[s.rate for s in bundle.savings]
                basis='progressive' if bundle.savings_method=='progressive' else 'basis needs confirmation'
                saving=f'{min(rates):g}–{max(rates):g}% · {basis}'
            if bundle.fd_rates:
                rates=[r.rate for r in bundle.fd_rates];fd=f'{min(rates):g}–{max(rates):g}%'
            status=('Official · checked' if fresh and (bundle.fd_rates or bundle.savings) else 'Unavailable')
            if not fresh:status='Expired — refresh'
            checked=bundle.checked_at[:16].replace('T',' ')+' UTC' if bundle.checked_at else 'Not checked'
            rows.append((bank,saving if fresh else 'Expired',fd if fresh else 'Expired',checked,status))
        self.rates_table.blockSignals(True);self._fill(self.rates_table,rows);self.rates_table.blockSignals(False)
    def _refresh_rates(self):
        try:
            from engines.official_bank_rates import refresh_banks
            if not self._data:return
            self._job(lambda:refresh_banks(self._data.banks,Path(config.DATA_DIR)/'family_bank_rates.json'),self._rates_done,'Reading official bank rates…')
        except ImportError:
            self.status.setText('Official bank-rate adapters are being updated. Existing values are not presented as live rates.')
    def _rates_done(self,bundles):
        self._bundles=bundles;self._populate_rates();self._invalidate()
        ready=sum(bool(b.fd_rates or b.savings) and b.usable() for b in bundles.values())
        self.status.setText(f'Official rates available for {ready} of {len(bundles)} selected banks. Unavailable banks are clearly marked; no comparison-site rates are substituted.')
    def _build_plan(self):
        try:
            from engines.family_fd_engine import build_family_plan
            if not self._data:return
            data=self._data;bundles=dict(self._bundles)
            if not bundles:self.status.setText('Refresh your bank rates first.');self.tabs.setCurrentIndex(1);return
            options=dict(reserve=self.reserve.value(),months=self.horizon.currentData(),family_pool=self.family_pool.isChecked(),
                         insurance=self.insurance.isChecked(),tax_limits=self.tax_limit.isChecked(),bank_percent=self.concentration.value())
            revision=self._revision
            self._job(lambda:build_family_plan(data,bundles,**options),
                      lambda plan:self._plan_done(plan) if revision==self._revision else None,
                      'Finding the best family allocation…')
        except ImportError:self.status.setText('The family optimizer is being updated; the tree currently shows your source balances.')
    def _plan_done(self,plan):
        self._plan=plan;self.tree.set_data(self._data,plan);self._refresh_amounts()
        self.status.setText(plan.summary);self.tabs.setCurrentIndex(0)
        self._fill(self.plan_table,[(r['person'],r['bank'],session.mask(r['amount']),f"{r['days']} days",f"{r['rate']:g}%",r['maturity_date'],session.mask(r['interest'])) for r in plan.allocations])
        self._fill(self.transfer_table,[(r['from_account'],r['to_account'],session.mask(r['amount'])) for r in plan.transfers])
        lines=[f"FD interest: {session.mask(plan.fd_interest)}. Savings projection: {session.mask(plan.savings_interest)}.",
               f"Estimated incremental tax: {session.mask(plan.incremental_tax)}. Estimated net interest: {session.mask(plan.net_interest)}."]
        lines += [f"{r['person']} · {r['financial_year']}: total taxable income {session.mask(r['taxable_total'])}; extra tax {session.mask(r['incremental_tax'])}." for r in plan.annual]
        self.explanation.setPlainText('\n'.join(lines+plan.messages))
        self.note.setText('Tax estimates assume the named account holder is the taxable owner. HUF has separate rules. Savings projections hold current rates constant; nothing is booked or transferred.')
    def _job(self,fn,done,message):
        if self._busy:return
        self._busy=True;self.make_plan.setEnabled(False);self.refresh_rates.setEnabled(False)
        self.status.setText(message);self._task_callback=done;self._task_payload=None
        self._thread=QThread(self);self._worker=_PlanningTask(fn);self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._task_success,Qt.ConnectionType.QueuedConnection)
        self._worker.error.connect(self._task_error,Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit);self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._task_finished,Qt.ConnectionType.QueuedConnection)
        self._thread.start()
    @Slot(object)
    def _task_success(self,value):self._task_payload=(True,value)
    @Slot(object)
    def _task_error(self,error):self._task_payload=(False,error)
    @Slot()
    def _task_finished(self):
        self._busy=False;self.make_plan.setEnabled(True);self.refresh_rates.setEnabled(True)
        thread=self._thread;self._thread=None;self._worker=None;thread.deleteLater()
        payload=self._task_payload
        if payload is None:self.status.setText('The calculation ended without a result.');return
        try:
            if payload[0]:self._task_callback(payload[1])
            else:self.status.setText(str(payload[1]))
        except Exception as exc:self.status.setText(f'Could not display the plan: {exc}')
    def closeEvent(self,event):
        if self._busy:
            self.status.setText('Please wait for the current rate refresh or calculation to finish.')
            event.ignore();return
        self.tree.timer.stop();super().closeEvent(event)
    def _invalidate(self,*args):
        if self._loading:return
        self._revision+=1;self._plan=None;self.plan_table.setRowCount(0);self.transfer_table.setRowCount(0);self.explanation.clear();self.detail.clear();self._refresh_amounts()
        self.pooling_label.setText(('Family transfers enabled' if self.family_pool.isChecked() else 'Separate owner budgets')+' · general-customer rates')
        if self._data:self.tree.set_data(self._data)
        self.status.setText('Settings changed. Build the plan again.')
    def _toggle_settings(self,shown):self.settings_panel.setVisible(shown);self.settings_toggle.setArrowType(Qt.ArrowType.DownArrow if shown else Qt.ArrowType.RightArrow)
    def _selected_node(self,node):self.detail.setText(node.get('detail','') if not session.privacy_mode else node.get('title',''))
    def _rate_details(self,row,column,*args):
        self.slab_table.setRowCount(0)
        self.rate_source_label.setText('No verified publication loaded for this bank. Use Refresh my bank rates.')
        if self._data and 0<=row<len(self._data.banks):
            bundle=self._bundles.get(self._data.banks[row])
            if bundle:
                import html
                url=html.escape(bundle.source_url,quote=True)
                savings_url=html.escape(bundle.savings_source_url or bundle.source_url,quote=True)
                status=bundle.error or '; '.join(bundle.notes)
                if not bundle.usable():status='Unavailable or expired — refresh before using these slabs. '+status
                self.rate_source_label.setText(f'<a href="{url}">Official FD source</a> · <a href="{savings_url}">Savings source</a> · {html.escape(status or "Current bank publication; confirm on the booking screen.")}')
                rows=[('Savings',s.label,f'{s.rate:g}%',bundle.savings_effective,'Progressive balance bands' if bundle.savings_method=='progressive' else 'Calculation basis needs confirmation') for s in bundle.savings]
                rows += [('FD',r.tenure_label,f'{r.rate:g}%',r.effective_from,f'{r.min_amount:g}–{r.max_amount:g} INR; {r.compounding} compounds/year') for r in bundle.fd_rates]
                self._fill(self.slab_table,rows)
    def refresh(self):
        if self._data:self.tree.set_data(self._data,self._plan);self._refresh_amounts()
        self.reserve.setVisible(not session.privacy_mode)
        if session.privacy_mode:
            self.detail.clear();self.explanation.clear();self.plan_table.setRowCount(0);self.transfer_table.setRowCount(0);self.timeline.setRowCount(0)
        elif self._data:
            self._fill(self.timeline,[(r['date'],r['person'],r['bank'],r['kind'],session.mask(r['amount'])) for r in self._data.receipts])
            if self._plan:self._plan_done(self._plan)
    def _refresh_amounts(self):
        values=[self._data.cash if self._data else 0,self._plan.invested if self._plan else 0,self._plan.gross_interest if self._plan else 0]
        for tile,value in zip([self.cash_tile,self.fd_tile,self.return_tile],values):
            tile.set_value('₹ ••••' if session.privacy_mode else value,is_currency=not session.privacy_mode)
    def refresh_theme(self):
        for tile in [self.cash_tile,self.fd_tile,self.return_tile]:tile.refresh_theme()
        if self._data:self.tree.set_data(self._data,self._plan)
