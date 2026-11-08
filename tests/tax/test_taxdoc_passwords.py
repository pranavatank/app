"""Password-file parsing tests using synthetic values only."""

import pytest

from tools.taxdoc_import import read_ais_tis_password, read_equitas_password


@pytest.mark.parametrize("label", ["AIS/TIS", "AIS", "TIS"])
def test_ais_tis_password_keeps_colons_after_label(tmp_path, label):
    password_file = tmp_path / "Password.txt"
    password_file.write_text(f"{label}: alpha:beta:gamma\n", encoding="utf-8")

    assert read_ais_tis_password(str(password_file)) == "alpha:beta:gamma"


def test_equitas_password_keeps_colons_after_label(tmp_path):
    password_file = tmp_path / "Password.txt"
    password_file.write_text("Equitas: alpha:beta:gamma\n", encoding="utf-8")

    assert read_equitas_password(str(password_file)) == "alpha:beta:gamma"


@pytest.mark.parametrize("reader,label,unrelated", [
    (read_ais_tis_password, "AIS", "Paisabazaar"),
    (read_ais_tis_password, "TIS", "Statistics"),
    (read_equitas_password, "Equitas", "NotEquitas"),
])
def test_password_reader_ignores_unrelated_labels_and_values(tmp_path, reader, label, unrelated):
    password_file = tmp_path / "Password.txt"
    password_file.write_text(
        f"{unrelated}: wrong\nOther: AIS:TIS:Equitas\n{label}: intended:secret\n", encoding="utf-8"
    )
    assert reader(str(password_file)) == "intended:secret"
