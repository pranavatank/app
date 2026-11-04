"""Locate private source documents for local development tools and tests."""

from pathlib import Path


def get_personal_data_dir(base_dir: str | Path | None = None) -> Path:
    """Return the active personal-document directory for this repository.

    The current location is ``data/data/Pranav``. Older checkouts may still
    keep the files in ``data/PersonalData/Pranav``. If neither exists, return
    the canonical current location so callers can preserve their normal
    missing-file handling.

    ``base_dir`` is the repository root and is primarily useful for isolated
    tests and tools operating on a chosen checkout.
    """
    repo_root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent.parent
    current = repo_root / "data" / "data" / "Pranav"
    legacy = repo_root / "data" / "PersonalData" / "Pranav"
    if current.is_dir():
        return current
    if legacy.is_dir():
        return legacy
    return current
