from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NATIVE_ARTIFACTS = REPO_ROOT / "artifacts" / "native"


def artifact_path(*parts: str) -> Path:
    """Return a stable path beneath the ignored native evidence directory."""
    path = NATIVE_ARTIFACTS.joinpath(*parts).resolve()
    if not path.is_relative_to(NATIVE_ARTIFACTS.resolve()):
        raise ValueError("Native artifact path must remain inside artifacts/native")
    return path
