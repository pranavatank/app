from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from engines.family_workbook import FamilyData
from ui.widgets.family_money_tree import FamilyMoneyTree


def _grouped_tree():
    data = FamilyData(
        people=[{"id": 1, "name": "Person", "tax_kind": "individual"}],
        accounts=[
            {
                "id": index,
                "person_id": 1,
                "eligible": True,
                "bank": f"Bank {index}",
                "label": f"Account {index}",
                "cash": 1000,
                "existing_fd": 0,
                "details": [],
                "unknown_fds": 0,
            }
            for index in range(6)
        ],
    )
    return data


def test_more_accounts_node_receives_click_with_animation_paused_and_active(qapp):
    for animation_enabled in (False, True):
        tree = FamilyMoneyTree()
        tree.resize(900, 420)
        tree.show()
        tree.set_data(_grouped_tree())
        tree.set_animation(animation_enabled)
        qapp.processEvents()

        more = next(item for item in tree.scene_graph.items()
                    if getattr(item, "record", {}).get("kind") == "more_accounts")
        tree.ensureVisible(more)
        qapp.processEvents()
        if animation_enabled:
            QTest.qWait(300)
            qapp.processEvents()

        point = tree.mapFromScene(more.mapToScene(more.boundingRect().center()))
        top = tree.itemAt(point)
        delivered = []
        tree.nodeSelected.connect(delivered.append)
        print("animation", animation_enabled, "top", type(top).__name__,
              "is_more", top is more, "point", point)
        QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(point))
        QTest.qWait(20)
        qapp.processEvents()
        print("selected", delivered, "show_all", tree._show_all,
              "accounts", sum(getattr(item, "record", {}).get("kind") == "account"
                              for item in tree.scene_graph.items()))
        assert tree._show_all
        assert len([item for item in tree.scene_graph.items()
                    if getattr(item, "record", {}).get("kind") == "account"]) == 6
        tree.close()


def test_compact_canvas_fits_and_can_zoom_in_from_small_fit(qapp):
    tree = FamilyMoneyTree()
    tree.resize(480, 340)
    tree.set_data(_grouped_tree())
    tree.show()
    qapp.processEvents()

    tree.fit_to_view()
    fitted = tree.transform().m11()
    assert fitted < 0.75
    tree.zoom(1.1)
    assert tree.transform().m11() > fitted
    tree.reset_zoom()
    assert tree._auto_fit
    tree.close()


def test_fit_to_view_contains_expanded_banks_and_vertical_fd_stacks(qapp):
    data = _grouped_tree()
    for index in range(6, 10):
        data.accounts.append({
            "id": index, "person_id": 1, "eligible": True, "bank": f"Long Bank Name {index}",
            "label": f"Account {index}", "cash": 1000, "existing_fd": 7000,
            "unknown_fds": 0,
            "details": [
                {"active": True, "principal": 1000, "maturity_amount": 1100,
                 "rate": 7.0, "start": "2026-01-01", "maturity_date": "2027-01-01",
                 "interest": 100}
                for _ in range(7)
            ],
        })
    for account in data.accounts:
        account["details"] = [
            {"active": True, "principal": 1000, "maturity_amount": 1100,
             "rate": 7.0, "start": "2026-01-01", "maturity_date": "2027-01-01",
             "interest": 100}
            for _ in range(7)
        ]

    tree = FamilyMoneyTree()
    tree.resize(480, 340)
    tree.show()
    tree.set_data(data)
    tree._show_all = True
    tree._draw()
    qapp.processEvents()

    tree.fit_to_view()
    qapp.processEvents()
    scene = tree.sceneRect()
    top_left = tree.mapFromScene(scene.topLeft())
    bottom_right = tree.mapFromScene(scene.bottomRight())
    viewport = tree.viewport().rect().adjusted(-1, -1, 1, 1)
    assert tree.transform().m11() < 0.35
    assert viewport.contains(top_left)
    assert viewport.contains(bottom_right)
    fitted = tree.transform().m11()
    tree.zoom(1.1)
    assert tree.transform().m11() > fitted
    tree.close()
