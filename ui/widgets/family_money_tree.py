"""Interactive, animated family → person → account → FD money tree."""
from __future__ import annotations
from math import log10
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, QElapsedTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont, QFontMetricsF
from PySide6.QtWidgets import (QGraphicsView,QGraphicsScene,QGraphicsObject,QGraphicsPathItem,
                              QGraphicsEllipseItem,QGraphicsItem)
from core.session import session
from ui.theme import Theme
from ui.widgets.money_label import format_inr


def money(value):
    if value is None:return 'Not supplied'
    return '₹ ••••' if session.privacy_mode else format_inr(value)


def short_bank(name):
    return name.replace(' Small Finance Bank','').replace('State Bank of India','SBI').replace('Rajkot Nagarik Sahakari Bank','RNSB')


class MoneyNode(QGraphicsObject):
    clicked=Signal(object)
    def __init__(self,record,width=208,accent=None):
        super().__init__()
        self.record=record;self.width=width;self.accent=accent or Theme.PRIMARY
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable,True)
        self.setAcceptHoverEvents(True)
        self.hovered=False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(record.get('detail','') if not session.privacy_mode else record.get('title',''))
    def boundingRect(self):return QRectF(0,0,self.width,100)
    def paint(self,painter,option,widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(Theme.SURFACE))
        painter.setPen(QPen(QColor(self.accent if self.hovered or self.record.get('selected') else Theme.BORDER),2 if self.record.get('selected') else 1))
        painter.drawRoundedRect(self.boundingRect(),12,12)
        painter.setBrush(QColor(self.accent));painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(0,15,4,70),2,2)
        for y,text,size,bold,color in [(24,self.record.get('title',''),10,True,Theme.TEXT_PRIMARY),
                                       (52,money(self.record.get('amount',0)),14,True,self.accent),
                                       (75,self.record.get('subtitle',''),9,False,Theme.TEXT_SECONDARY),
                                       (92,self.record.get('foot',''),8,False,Theme.TEXT_SECONDARY)]:
            font=QFont('Segoe UI',size);font.setBold(bold);painter.setFont(font);painter.setPen(QColor(color))
            metrics=QFontMetricsF(font)
            text=metrics.elidedText(str(text),Qt.TextElideMode.ElideRight,self.width-28)
            painter.drawText(QPointF(14,y),text)
    def hoverEnterEvent(self,event):self.hovered=True;self.update()
    def hoverLeaveEvent(self,event):self.hovered=False;self.update()
    def mousePressEvent(self,event):self.clicked.emit(self.record);event.accept()
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter,Qt.Key.Key_Space):
            self.clicked.emit(self.record);event.accept()
        else:super().keyPressEvent(event)


class FamilyMoneyTree(QGraphicsView):
    nodeSelected=Signal(dict)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.scene_graph=QGraphicsScene(self);self.setScene(self.scene_graph)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setMinimumHeight(280)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
        self.setAccessibleName('Family money flow. Select a person to see accounts and FD tenures.')
        self._data=None;self._plan=None;self._selected=None;self._show_all=False;self._edges=[];self._coins=[]
        self._animate=True;self._auto_fit=True;self.clock=QElapsedTimer();self.clock.start()
        self.timer=QTimer(self);self.timer.setInterval(40);self.timer.timeout.connect(self._tick)
    def set_data(self,data,plan=None):
        self._data=data;self._plan=plan;self._auto_fit=True
        active=[p['id'] for p in data.people if p['tax_kind']!='joint'] if data else []
        if self._selected not in active:self._selected=active[0] if active else None
        self._draw()
    def set_animation(self,enabled):
        self._animate=enabled
        for coin,_,_ in self._coins:coin.setVisible(enabled)
        self.timer.start() if enabled and self.isVisible() else self.timer.stop()
    def showEvent(self,event):
        super().showEvent(event)
        if self._animate:self.timer.start()
    def hideEvent(self,event):self.timer.stop();super().hideEvent(event)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self._data:self._draw()
    def _node(self,record,x,y,width,accent):
        item=MoneyNode(record,width,accent);item.setPos(x,y);item.clicked.connect(self._choose)
        self.scene_graph.addItem(item);return item
    def _edge(self,parent,child,amount):
        start=parent.pos()+QPointF(parent.width/2,100);end=child.pos()+QPointF(child.width/2,0)
        path=QPainterPath(start);mid=(start.y()+end.y())/2
        path.cubicTo(start.x(),mid,end.x(),mid,end.x(),end.y())
        line=QGraphicsPathItem(path);color=QColor(Theme.PRIMARY);color.setAlpha(80)
        line.setPen(QPen(color,min(5,1.5+max(0,log10(max(1,amount))-3)*.6)))
        line.setZValue(-1);self.scene_graph.addItem(line)
        for phase in (0,.5):
            if amount<=.01:continue
            coin=QGraphicsEllipseItem(-4,-4,8,8);coin.setBrush(QColor(Theme.PRIMARY));coin.setPen(QPen(Qt.PenStyle.NoPen))
            coin.setZValue(2);coin.setVisible(self._animate);self.scene_graph.addItem(coin)
            self._coins.append((coin,path,phase+len(self._coins)*.083))
    def _choose(self,record):
        if record.get('kind')=='person':
            self._selected=record['id'];self._show_all=False;QTimer.singleShot(0,self._draw)
        elif record.get('kind')=='more_accounts':
            self._show_all=not self._show_all;QTimer.singleShot(0,self._draw)
        self.nodeSelected.emit(record)
    def _draw(self):
        self.scene_graph.clear();self._coins=[]
        data=self._data
        if not data:return
        people=[p for p in data.people if p['tax_kind']!='joint']
        selected_accounts=[a for a in data.accounts if a['person_id']==self._selected and a['eligible']]
        plan=self._plan
        fdrows=plan.allocations if plan else []
        cashrows=plan.cash_allocations if plan else []
        def account_total(a):
            if plan:return sum(r['amount'] for r in fdrows if r['account_id']==a['id'])+sum(r['amount'] for r in cashrows if r['account_id']==a['id'])
            return a['cash']+a['existing_fd']
        selected_accounts.sort(key=lambda a:(-account_total(a),a['bank']))
        hidden=[]
        if not self._show_all and len(selected_accounts)>5:
            selected_accounts,hidden=selected_accounts[:4],selected_accounts[4:]
        slots=len(selected_accounts)+bool(hidden)
        width=max(self.viewport().width()-24,slots*220,len(people)*235,900)
        root_amount=(plan.invested+plan.liquid) if plan else sum(account_total(a) for a in data.accounts if a['eligible'])
        root=self._node(dict(kind='family',title='Family investment plan' if plan else 'Recorded family deposits',amount=root_amount,
                             subtitle='FDs + ready cash' if plan else 'Cash + FD value estimates',foot='Select a person below'),width/2-125,10,250,Theme.PRIMARY)
        persons={}
        for index,person in enumerate(people):
            owned=[a for a in data.accounts if a['person_id']==person['id']]
            amount=sum(account_total(a) for a in owned)
            node=self._node(dict(kind='person',id=person['id'],title=person['name'],amount=amount,
                                 subtitle=f'{len(owned)} bank accounts',foot='Viewing accounts' if person['id']==self._selected else 'Click to view accounts',
                                 selected=person['id']==self._selected),
                            (index+.5)*width/max(1,len(people))-104,150,208,Theme.PRIMARY)
            persons[person['id']]=node;self._edge(root,node,amount)
        max_bottom=500
        for index,account in enumerate(selected_accounts):
            x=(index+.5)*width/max(1,slots)-100
            if plan:
                deposits=[r for r in fdrows if r['account_id']==account['id']]
                ready=sum(r['amount'] for r in cashrows if r['account_id']==account['id'])
                subtitle=f'{len(deposits)} FD placements · {money(ready)} ready cash'
            else:
                deposits=[d for d in account['details'] if d['active']]
                ready=account['cash'];subtitle=f'Savings {money(ready if account.get("cash_known",True) else None)}'
            bank=self._node(dict(kind='account',id=account['id'],title=short_bank(account['bank']),amount=account_total(account),
                                 subtitle=subtitle,foot='Planned destination' if plan else 'Recorded savings + FD values',
                                 detail=account['label']),x,290,200,Theme.INFO)
            if self._selected in persons:self._edge(persons[self._selected],bank,account_total(account))
            leaves=[]
            for d in deposits:
                amount=d['amount'] if plan else d['principal']
                days=d['days'] if plan else (date_from(d['maturity_date'])-date_from(d['start'])).days
                leaves.append(dict(kind='fd',title=f'{days} days · {d["rate"]:g}%',amount=amount,
                                   subtitle=f'Matures {d["maturity_date"]}',foot=f'Interest {money(d["interest"])}' if plan else 'Existing booked FD',
                                   detail=(f'Principal {money(amount)}\nMaturity {money(d["maturity_amount"])}\n{d["maturity_date"]}')))
            if not plan and account['unknown_fds']:
                leaves.append(dict(kind='fd_summary',title=f'{account["unknown_fds"]} FDs · terms missing',
                                   amount=max(0,account['existing_fd']-sum(d['maturity_amount'] for d in deposits)),
                                   subtitle='Aggregate recorded balance',foot='Maturity dates not supplied'))
            if plan and ready>.01:
                leaves.append(dict(kind='cash',title='Ready cash',amount=ready,subtitle='Available without breaking an FD',foot='Savings rate can change'))
            for j,record in enumerate(leaves):
                leaf=self._node(record,x+8,430+j*130,184,Theme.SUCCESS if record['kind']=='fd' else Theme.INFO)
                self._edge(bank,leaf,record['amount']);max_bottom=max(max_bottom,530+j*130)
        if hidden:
            total=sum(account_total(a) for a in hidden)
            more=self._node(dict(kind='more_accounts',title=f'{len(hidden)} more bank accounts',amount=total,
                                 subtitle='Grouped to keep the tree clear',foot='Click to expand all accounts'),
                            (slots-.5)*width/slots-100,290,200,Theme.INFO)
            if self._selected in persons:self._edge(persons[self._selected],more,total)
        self.scene_graph.setSceneRect(-10,0,width+20,max_bottom+30)
        if self._auto_fit:self._fit_overview()
        self.centerOn(width/2,0)
        self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())
        self._tick()
    def _tick(self):
        if not self._animate:return
        t=self.clock.elapsed()/2800
        for coin,path,phase in self._coins:coin.setPos(path.pointAtPercent((t+phase)%1))
    def zoom(self,factor):
        current=self.transform().m11()
        if .55<=current*factor<=1.8:self._auto_fit=False;self.scale(factor,factor)
    def _fit_overview(self):
        self.resetTransform()
        scale=max(.75,min(1,(self.viewport().height()-10)/550,self.viewport().width()/max(1,self.sceneRect().width())))
        self.scale(scale,scale)
    def reset_zoom(self):
        self._auto_fit=True;self._fit_overview()
        self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())
        self.centerOn(self.sceneRect().center().x(),0)


def date_from(value):
    from datetime import date
    return date.fromisoformat(value)
