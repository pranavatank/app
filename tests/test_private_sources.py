from pathlib import Path

from tools.private_sources import get_personal_data_dir


def test_current_private_data_location_is_preferred(tmp_path: Path):
    current = tmp_path / "data" / "data" / "Pranav"
    legacy = tmp_path / "data" / "PersonalData" / "Pranav"
    current.mkdir(parents=True)
    legacy.mkdir(parents=True)

    assert get_personal_data_dir(tmp_path) == current


def test_legacy_private_data_location_is_fallback(tmp_path: Path):
    legacy = tmp_path / "data" / "PersonalData" / "Pranav"
    legacy.mkdir(parents=True)

    assert get_personal_data_dir(tmp_path) == legacy


def test_missing_private_data_returns_canonical_current_location(tmp_path: Path):
    assert get_personal_data_dir(tmp_path) == tmp_path / "data" / "data" / "Pranav"
