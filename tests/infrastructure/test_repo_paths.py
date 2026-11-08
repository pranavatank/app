import pytest

from tests.support.repo_paths import NATIVE_ARTIFACTS, REPO_ROOT, artifact_path


def test_repo_root_is_anchored_to_support_module():
    assert (REPO_ROOT / "pytest.ini").is_file()
    assert (REPO_ROOT / "tests" / "support" / "repo_paths.py").is_file()


def test_artifact_path_stays_under_native_artifacts():
    expected = NATIVE_ARTIFACTS / "rebuild" / "example.json"
    assert artifact_path("rebuild", "example.json") == expected


@pytest.mark.parametrize("parts", [("..", "outside.txt"), ("rebuild", "..", "..", "outside.txt")])
def test_artifact_path_rejects_traversal(parts):
    with pytest.raises(ValueError, match="inside artifacts/native"):
        artifact_path(*parts)
