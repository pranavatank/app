r"""tools/real_ui_tests/rebuild_p3_12_fd_planner.py — Phase 3.12 FD Planner (R only).

Walks the family planner with the real database in read-only mode. Rate
availability is reported as observed; unavailable banks are never treated as
valid inputs or as proof of a guaranteed optimum.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PySide6.QtWidgets import QApplication, QPushButton
from tools.real_ui_test_harness import pyautogui

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click_widget, os_select_combo, wait_until,
)


def _button(page, text):
    return next((button for button in page.findChildren(QPushButton)
                 if button.text().strip() == text), None)


def _nodes(tree, kind):
    return [item for item in tree.scene_graph.items()
            if hasattr(item, "record") and item.record.get("kind") == kind]


def _click_node(p, tree, node):
    # QGraphicsItems are not QWidget children, so click their actual visible
    # position in the view using the harness's OS-level coordinate helper.
    # Account groups can sit below the clipped viewport, so bring the item
    # into view before translating its scene position to screen coordinates.
    p.harness.scroll_into_view(tree.viewport())
    tree.ensureVisible(node)
    # ensureVisible may leave a node at the viewport edge, where the planner's
    # detail label can overlap it. Center it so the OS hit target is unobscured.
    tree.centerOn(node)
    p.harness.settle(0.3)
    scene_point = node.mapToScene(node.boundingRect().center())
    viewport_point = tree.mapFromScene(scene_point)
    if not tree.viewport().visibleRegion().contains(viewport_point):
        raise AssertionError(f"tree node center is outside visible viewport: {viewport_point}")
    global_point = tree.viewport().mapToGlobal(viewport_point)
    hit_item = tree.itemAt(viewport_point)
    hit_record = getattr(hit_item, "record", {})
    hit_widget = QApplication.widgetAt(global_point)
    if hit_widget is None or not (hit_widget is tree.viewport() or tree.viewport().isAncestorOf(hit_widget)):
        raise AssertionError(f"tree node OS hit target is obscured by {type(hit_widget).__name__ if hit_widget else None}")
    print("tree-click-before",
          f"target={node.record.get('kind')}",
          f"hit={hit_record.get('kind')}",
          f"widget={type(hit_widget).__name__}",
          f"show_all={tree._show_all}",
          f"accounts={len(_nodes(tree, 'account'))}")
    selected_kinds = []
    tree.nodeSelected.connect(lambda record: selected_kinds.append(record.get("kind")))
    px, py = p.harness.to_physical(global_point)
    pyautogui.moveTo(px, py, duration=0.15)
    pyautogui.click()
    p.harness.settle(0.5)
    print("tree-click-after",
          f"selected_kinds={selected_kinds}",
          f"show_all={tree._show_all}",
          f"accounts={len(_nodes(tree, 'account'))}")


def _select_tab(p, page, index):
    tab_bar = page.tabs.tabBar()
    p.harness.click_at_via_os(tab_bar, tab_bar.tabRect(index).center(), wait=0.4)
    p.harness.settle(0.2)


def run_r(p):
    page = p.nav("FD Planner")

    from ui.fd_planner_screen import FDPlannerScreen
    is_page = isinstance(page, FDPlannerScreen)
    p.checks.check("FD Planner page loaded", is_page)
    if not is_page:
        return

    # The constructor may start an official-rate refresh. Let its QThread
    # finish through the normal event loop before teardown or further actions.
    p.wait_for_page_jobs("initial FD Planner refresh")
    p.checks.check("initial planner refresh settled", not page._busy)

    required = [
        ("cash reserve input", page.reserve),
        ("planning horizon selector", page.horizon),
        ("Build my plan button", page.make_plan),
        ("flow animation toggle", page.animate),
        ("money flow tree", page.tree),
    ]
    for label, control in required:
        p.checks.check(f"{label} visible", control.isVisible())

    p.checks.check("family workbook data loaded", page._data is not None,
                   "planner reports a load issue" if page._data is None else "")
    p.checks.check("source is marked read-only", "Read-only source" in page.source_label.text(),
                   page.source_label.text())
    p.checks.check("money tree has family nodes", bool(_nodes(page.tree, "family")))
    p.checks.check("money tree has person nodes", bool(_nodes(page.tree, "person")))
    p.observe("FD Planner", f"loaded={page._data is not None}; people={len(page._data.people) if page._data else 0}; "
                            f"accounts={len(page._data.accounts) if page._data else 0}")
    p.harness.shot("fd_planner_overview")

    # Exercise user-visible controls and restore their original values. These
    # only alter the in-memory planning inputs and must clear any prior plan.
    original_reserve = page.reserve.value()
    original_horizon = page.horizon.currentText()
    p.harness.click_via_os(page.reserve, wait=0.2)
    pyautogui.press("up")
    p.harness.settle(0.3)
    changed_reserve = page.reserve.value()
    p.checks.check("reserve input accepts change", changed_reserve != original_reserve)
    pyautogui.press("down")
    p.harness.settle(0.3)
    p.checks.check("reserve input restores", page.reserve.value() == original_reserve)

    other_horizon = next((page.horizon.itemText(i) for i in range(page.horizon.count())
                          if page.horizon.itemText(i) != original_horizon), None)
    if other_horizon:
        os_select_combo(p.harness, page.horizon, other_horizon)
        p.checks.check("planning horizon changes", page.horizon.currentText() == other_horizon)
        os_select_combo(p.harness, page.horizon, original_horizon)
        p.checks.check("planning horizon restores", page.horizon.currentText() == original_horizon)

    animate_before = page.animate.isChecked()
    os_click_widget(p.harness, page.animate, wait=0.3)
    p.checks.check("animation pauses", page.animate.isChecked() != animate_before and not page.tree._animate)
    os_click_widget(p.harness, page.animate, wait=0.3)
    p.checks.check("animation resumes", page.animate.isChecked() == animate_before and
                   page.tree._animate == animate_before)

    plus = _button(page, "+")
    reset = _button(page, "Reset view")
    p.checks.check("zoom and reset controls found", plus is not None and reset is not None)
    if plus and reset:
        zoom_before = page.tree.transform().m11()
        os_click_widget(p.harness, plus, wait=0.3)
        zoomed = page.tree.transform().m11()
        p.checks.check("zoom control changes scale", abs(zoomed - zoom_before) > 0.001)
        os_click_widget(p.harness, reset, wait=0.3)
        p.checks.check("reset view restores overview", page.tree._auto_fit)

    people = _nodes(page.tree, "person")
    if len(people) > 1:
        selected_before = page.tree._selected
        candidate = next((node for node in people if node.record.get("id") != selected_before), None)
        if candidate:
            _click_node(p, page.tree, candidate)
            p.harness.settle(0.5)
            p.checks.check("tree person selection changes accounts",
                           page.tree._selected == candidate.record.get("id"))
    else:
        p.observe("tree person selection", "one person node available; initial selection shown")

    more_nodes = _nodes(page.tree, "more_accounts")
    if more_nodes:
        visible_before = len(_nodes(page.tree, "account"))
        _click_node(p, page.tree, more_nodes[0])
        p.harness.settle(0.5)
        p.checks.check("tree grouped accounts expand",
                       len(_nodes(page.tree, "account")) > visible_before)
    else:
        p.observe("tree grouped accounts", "no grouped accounts in the selected person's view")

    if p.part == "tree":
        return

    # Read the visible official-rate coverage. A bank without a current,
    # usable FD quote remains unavailable and is never counted as covered.
    _select_tab(p, page, 1)
    p.checks.check("bank rates tab opens", page.tabs.currentIndex() == 1 and page.rates_table.isVisible())
    p.harness.shot("fd_planner_rates")
    bundles = page._bundles
    bank_names = list(page._data.banks) if page._data else []
    covered = [name for name in bank_names if name in bundles and bundles[name].usable() and
               any(rate.customer == "general" and rate.usable(date.today())
                   for rate in bundles[name].fd_rates)]
    unavailable = [name for name in bank_names if name not in covered]
    p.checks.check("bank rate table shows loaded banks",
                   page.rates_table.rowCount() == len(bank_names),
                   f"rows={page.rates_table.rowCount()}, banks={len(bank_names)}")
    p.observe("official FD rate coverage", f"covered={covered}; unavailable_or_expired={unavailable}")
    if bank_names:
        p.checks.check("official rate coverage is explicitly displayed",
                       page.rates_table.rowCount() == len(bank_names))

    _select_tab(p, page, 2)
    p.checks.check("upcoming money tab opens", page.tabs.currentIndex() == 2 and page.timeline.isVisible())
    _select_tab(p, page, 3)
    p.checks.check("plan details tab opens", page.tabs.currentIndex() == 3 and page.plan_table.isVisible())
    _select_tab(p, page, 4)
    p.checks.check("transfers tab opens", page.tabs.currentIndex() == 4 and page.transfer_table.isVisible())
    _select_tab(p, page, 0)

    # The optimizer supports partial official coverage. Run it when at least
    # one selected bank has a current FD quote or a supported progressive
    # savings quote; unavailable banks must receive no new FD allocation.
    savings_covered = [name for name in bank_names
                       if name in bundles and bundles[name].usable() and bundles[name].savings and
                       bundles[name].savings_method == "progressive"]
    supported = sorted(set(covered) | set(savings_covered))
    unavailable = [name for name in bank_names if name not in supported]
    p.observe("supported planning rate coverage",
              f"fd={covered}; progressive_savings={savings_covered}; unavailable={unavailable}")

    if supported:
        revision_before = page._revision
        status_before = page.status.text()
        # A usable cached bundle may skip the constructor's refresh job, so
        # _job has not necessarily created _task_payload yet.
        payload_before = getattr(page, "_task_payload", None)
        p.harness.click_via_os(page.make_plan, wait=0)
        # click_via_os(wait=0) sends the OS click but does not pump Qt events.
        # Observe the job start (or its completed payload for a very fast job)
        # before the normal drain can make a missed click look like success.
        start_observed = wait_until(
            p.harness,
            lambda: page._busy or getattr(page, "_task_payload", None) is not payload_before,
            timeout=5,
            interval=0.05,
        )
        p.wait_for_page_jobs("FD Planner plan calculation")
        status_after = page.status.text()
        payload_after = getattr(page, "_task_payload", None)
        payload_changed = payload_after is not None and payload_after is not payload_before
        fresh_error = (payload_changed and payload_after[0] is False and status_after != status_before)
        fresh_error_type = type(payload_after[1]).__name__ if fresh_error else ""
        actual_job_transition = start_observed and (payload_changed or page._plan is not None)
        p.checks.check("plan action started an actual job or returned a fresh error",
                       actual_job_transition,
                       f"start_or_completion_observed={start_observed}; plan_created={page._plan is not None}; "
                       f"payload_changed={payload_changed}; fresh_error_type={fresh_error_type}")
        p.checks.check("plan worker settled", not page._busy)
        p.checks.check("plan calculation produced a result", page._plan is not None,
                       "worker completed with a fresh UI error" if fresh_error else "no plan or fresh error transition")
        p.checks.check("plan job preserved settings revision", page._revision == revision_before)
        p.observe("plan result", f"plan_created={page._plan is not None}; fresh_error={fresh_error}; "
                                  f"fresh_error_type={fresh_error_type}; "
                                  f"revision_unchanged={page._revision == revision_before}")
        if page._plan is not None:
            unavailable_allocations = [row["bank"] for row in page._plan.allocations
                                       if row["bank"] not in covered]
            p.checks.check("unavailable banks receive no new FD allocations",
                           not unavailable_allocations,
                           f"unavailable allocation banks={unavailable_allocations}")
            _select_tab(p, page, 3)
            p.checks.check("plan result details are visible",
                           page.tabs.currentIndex() == 3 and page.plan_table.isVisible())
    else:
        p.observe("plan calculation", "UNVERIFIED: no usable official FD or supported savings coverage")
        p.checks.check("plan calculation unverified without official rate coverage", False,
                       "no current usable FD or progressive savings rates")
    p.harness.shot("fd_planner_result")


def run_s(p):
    p.checks.check("S mode not used for FD Planner", True, "R-only read-only walkthrough")


if __name__ == "__main__":
    main_wrapper("12", "FD Planner", run_r, run_s)
