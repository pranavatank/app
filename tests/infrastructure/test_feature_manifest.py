"""Regression checks for the feature manifest and recursive discovery."""
import pytest

from tools import run_full_tests


def test_manifest_covers_every_test_module_once():
    manifest = run_full_tests.load_manifest()
    listed = [path for paths in manifest["features"].values() for path in paths]
    actual = sorted(p.relative_to(run_full_tests.ROOT).as_posix()
                    for p in (run_full_tests.ROOT / "tests").rglob("test_*.py")
                    if p.relative_to(run_full_tests.ROOT / "tests").parts[0]
                    not in {"native", "support"})
    assert sorted(listed) == actual
    assert len(listed) == len(set(listed))
    assert manifest["source_features"]
    assert all(features and all(feature in manifest["features"] for feature in features)
               for features in manifest["source_features"].values())


def test_every_source_mapping_matches_a_repository_file():
    manifest = run_full_tests.load_manifest()
    unmatched = []
    for pattern in manifest["source_features"]:
        file_pattern = pattern + "/*" if pattern.endswith("/**") else pattern
        if not any(path.is_file() for path in run_full_tests.ROOT.glob(file_pattern)):
            unmatched.append(pattern)
    assert not unmatched, f"Source mappings match no files: {unmatched}"


def test_statement_profile_source_mapping_points_to_real_profiles():
    manifest = run_full_tests.load_manifest()
    mapping = manifest["source_features"]["engines/statement/profiles/**"]
    profiles = list((run_full_tests.ROOT / "engines/statement/profiles").glob("*.yaml"))
    assert "statements" in mapping
    assert profiles


def test_discovery_combines_repeated_features_and_deduplicates():
    selected = run_full_tests.discover_tests(
        features=["statements", "planning"],
        manifest=run_full_tests.load_manifest(),
    )
    paths = [relative for relative, _ in selected]
    assert paths
    assert all(path.startswith(("tests/statements/", "tests/planning/")) for path in paths)
    assert len(paths) == len(set(paths))


def test_directory_input_is_recursive(tmp_path):
    selected = run_full_tests.discover_tests(["tests/statements"])
    assert selected
    assert all(path.startswith("tests/statements/") for path, _ in selected)


def test_existing_directory_without_tests_is_rejected():
    with pytest.raises(ValueError, match=r"Directory contains no test_\*\.py files: core"):
        run_full_tests.discover_tests(["core"])


def test_unknown_feature_is_rejected():
    with pytest.raises(ValueError, match="Unknown feature"):
        run_full_tests.discover_tests(features=["unknown-feature"])
