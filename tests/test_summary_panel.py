import pytest
from PyQt6.QtWidgets import QLabel
from ui.widgets.summary_panel import SummaryPanel


@pytest.mark.parametrize("scrollable", [False, True])
def test_clear_stats_removes_widgets(qapp, scrollable):
    """Test that clear_stats() properly removes widgets and prevents ghost rendering.

    Before the fix: After 3 cycles, 3 QLabel widgets with the marker text remain.
    After the fix: Only 1 QLabel widget with the marker text exists.
    """
    panel = SummaryPanel(title="Test Panel", scrollable=scrollable)
    marker = "UNIQUE-MARKER-VALUE"

    # Run 3 cycles of clear + add
    for cycle in range(3):
        panel.clear_stats()
        panel.add_stat(key=f"stat_{cycle}", label="Test Stat", value=marker)

    # Process pending deleteLater() calls
    qapp.processEvents()

    # Find all QLabel descendants
    labels = panel.findChildren(QLabel)

    # Count labels with the marker text
    marker_labels = [lbl for lbl in labels if lbl.text() == marker]

    # After the fix, exactly ONE label should have the marker text
    # (the others were properly deleted via setParent(None))
    assert len(marker_labels) == 1, (
        f"Expected 1 label with marker text, but found {len(marker_labels)}. "
        f"This indicates ghost widgets were not properly removed."
    )
