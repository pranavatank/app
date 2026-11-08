"""P5 must compare the current P0 scope and exclude prior-run audit evidence."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from tools.real_ui_tests import rebuild_p5_collect as collector


@pytest.fixture
def source_scope(tmp_path, monkeypatch):
    source = tmp_path / "data" / "data" / "Pranav"
    source.mkdir(parents=True)
    results = tmp_path / "results"
    results.mkdir()
    baseline_file = results / "P0_personaldata_hashes.json"
    document = source / "statement.pdf"
    document.write_bytes(b"synthetic document")
    baseline = {str(document.relative_to(tmp_path)): hashlib.sha256(document.read_bytes()).hexdigest()}
    baseline_file.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(collector, "BASE", tmp_path)
    monkeypatch.setattr(collector, "PERSONAL_DATA_DIR", source)
    monkeypatch.setattr(collector, "REBUILD_DIR", results)
    monkeypatch.setattr(collector, "P0_HASHES_FILE", baseline_file)
    return source, results, baseline_file, document


def test_current_source_scope_matches_and_never_reads_password(source_scope, monkeypatch):
    source, _, _, _ = source_scope
    password = source / "Password.txt"
    password.write_bytes(b"synthetic excluded content")
    original_read = Path.read_bytes

    def guarded_read(path):
        assert path.name.casefold() != "password.txt"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    result = collector.compare_personaldata_integrity()
    assert result == {"added": [], "removed": [], "changed": [], "matches": True, "errors": []}


def test_changed_added_and_missing_sources_fail_integrity(source_scope):
    source, _, _, document = source_scope
    document.write_bytes(b"changed document")
    (source / "new.pdf").write_bytes(b"new document")
    result = collector.compare_personaldata_integrity()
    assert not result["matches"]
    assert result["changed"] == [str(document.relative_to(collector.BASE))]
    assert result["added"] == [str((source / "new.pdf").relative_to(collector.BASE))]
    document.unlink()
    result = collector.compare_personaldata_integrity()
    assert result["removed"] == [str(document.relative_to(collector.BASE))]
    assert result["errors"]


@pytest.mark.parametrize("content", [None, "{}", "[]", "not JSON"])
def test_missing_or_invalid_baseline_cannot_pass(source_scope, content):
    _, _, baseline_file, _ = source_scope
    if content is None:
        baseline_file.unlink()
    else:
        baseline_file.write_text(content, encoding="utf-8")
    result = collector.compare_personaldata_integrity()
    assert not result["matches"]
    assert result["errors"]


def test_unreadable_source_is_reported_as_integrity_failure(source_scope, monkeypatch):
    _, _, _, document = source_scope
    original_read = Path.read_bytes

    def unreadable(path):
        if path == document:
            raise PermissionError("synthetic access denial")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", unreadable)
    result = collector.compare_personaldata_integrity()
    assert not result["matches"]
    assert any("PermissionError" in error for error in result["errors"])


def test_only_p3_results_since_current_p0_are_aggregated(source_scope):
    _, results, baseline_file, _ = source_scope
    old = results / "P3_old_default.json"
    current = results / "P3_current_default.json"
    old.write_text(json.dumps({"results": [{"name": "old failure", "ok": False}]}), encoding="utf-8")
    current.write_text(json.dumps({"results": [{"name": "current failure", "ok": False}]}), encoding="utf-8")
    boundary = 1_700_000_000_000_000_000
    os.utime(baseline_file, ns=(boundary, boundary))
    os.utime(old, ns=(boundary - 1_000_000_000, boundary - 1_000_000_000))
    os.utime(current, ns=(boundary + 1_000_000_000, boundary + 1_000_000_000))
    result = collector.load_p3_results()
    assert result["p3_files"] == [current.name]
    assert result["excluded_older_files"] == [old.name]
    assert [failure["name"] for failure in result["fails"]] == ["current failure"]
    assert result["source_dates_utc"][current.name].startswith("2023-11-14T")
    assert not result["errors"]


def test_missing_p0_boundary_cannot_inherit_old_p3_results(source_scope):
    _, results, baseline_file, _ = source_scope
    result_file = results / "P3_old_default.json"
    result_file.write_text('{"results": [{"ok": true}]}', encoding="utf-8")
    baseline_file.unlink()
    result = collector.load_p3_results()
    assert result["p3_files"] == []
    assert result["excluded_older_files"] == [result_file.name]
    assert result["errors"]


@pytest.mark.parametrize("payload", [
    {}, {"results": []}, {"results": [{}]}, {"results": [{"ok": 1}]},
    {"results": "invalid"},
])
def test_p3_empty_or_malformed_results_are_collection_errors(source_scope, payload):
    _, results, _, _ = source_scope
    result_file = results / "P3_invalid_default.json"
    result_file.write_text(json.dumps(payload), encoding="utf-8")
    result = collector.load_p3_results()
    assert result["p3_files"] == [result_file.name]
    assert result["errors"]
    assert not result["fails"]


def test_fingerprint_comparison_detects_content_and_table_set_changes():
    digest_a = "a" * 64
    digest_b = "b" * 64
    before = {"edited": {"count": 1, "sha256": digest_a}, "removed": {"count": 0, "sha256": digest_a}}
    after = {"edited": {"count": 1, "sha256": digest_b}, "added": {"count": 1, "sha256": digest_a}}
    assert collector.compare_fingerprints(before, after) == ["added", "edited", "removed"]
    assert collector.compare_fingerprints(before, after, allowed=("edited",)) == ["added", "removed"]


@pytest.mark.parametrize("baseline_content", [None, "{}", "not json", '{"t": {"count": 1}}'])
def test_requested_missing_or_invalid_fingerprint_baseline_exits_nonzero(
    source_scope, monkeypatch, tmp_path, baseline_content
):
    _, results, _, _ = source_scope
    (results / "P3_ok_default.json").write_text('{"results": [{"ok": true}]}', encoding="utf-8")
    if baseline_content is not None:
        (results / "FP_case.json").write_text(baseline_content, encoding="utf-8")
    monkeypatch.setattr(collector, "OUTPUT_FILE", tmp_path / "collected.md")
    monkeypatch.setattr(collector, "read_progress", lambda: [])
    monkeypatch.setattr(collector, "list_p4_logs", lambda: {"json": [], "text": []})
    monkeypatch.setattr(collector, "compare_personaldata_integrity", lambda: {
        "matches": True, "errors": [], "added": [], "removed": [], "changed": []
    })
    monkeypatch.setattr(collector, "check_git_status", lambda: [])
    monkeypatch.setattr(collector, "fingerprint_real_db", lambda: {"t": {"count": 1, "sha256": "a" * 64}})
    monkeypatch.setattr(collector, "read_theme_prefs_bytes", lambda: b"prefs")
    monkeypatch.setattr("sys.argv", ["rebuild_p5_collect.py", "--baseline", "case"])
    assert collector.main() == 1


@pytest.mark.parametrize("prefs_exists,current", [(False, b"prefs"), (True, None)])
def test_requested_missing_theme_baseline_or_current_prefs_exits_nonzero(
    source_scope, monkeypatch, tmp_path, prefs_exists, current
):
    _, results, _, _ = source_scope
    (results / "P3_ok_default.json").write_text('{"results": [{"ok": true}]}', encoding="utf-8")
    if prefs_exists:
        (results / "theme_prefs_case.json").write_bytes(b"prefs")
    monkeypatch.setattr(collector, "OUTPUT_FILE", tmp_path / "collected.md")
    monkeypatch.setattr(collector, "read_progress", lambda: [])
    monkeypatch.setattr(collector, "list_p4_logs", lambda: {"json": [], "text": []})
    monkeypatch.setattr(collector, "compare_personaldata_integrity", lambda: {
        "matches": True, "errors": [], "added": [], "removed": [], "changed": []
    })
    monkeypatch.setattr(collector, "check_git_status", lambda: [])
    monkeypatch.setattr(collector, "fingerprint_real_db", lambda: {"t": {"count": 1, "sha256": "a" * 64}})
    monkeypatch.setattr(collector, "read_theme_prefs_bytes", lambda: current)
    monkeypatch.setattr("sys.argv", ["rebuild_p5_collect.py", "--prefs-baseline", "case"])
    assert collector.main() == 1


def test_requested_fingerprint_unavailable_exits_nonzero(source_scope, monkeypatch, tmp_path):
    _, results, _, _ = source_scope
    (results / "P3_ok_default.json").write_text('{"results": [{"ok": true}]}', encoding="utf-8")
    monkeypatch.setattr(collector, "OUTPUT_FILE", tmp_path / "collected.md")
    monkeypatch.setattr(collector, "read_progress", lambda: [])
    monkeypatch.setattr(collector, "list_p4_logs", lambda: {"json": [], "text": []})
    monkeypatch.setattr(collector, "compare_personaldata_integrity", lambda: {
        "matches": True, "errors": [], "added": [], "removed": [], "changed": []
    })
    monkeypatch.setattr(collector, "check_git_status", lambda: [])
    monkeypatch.setattr(collector, "fingerprint_real_db", lambda: None)
    monkeypatch.setattr(collector, "read_theme_prefs_bytes", lambda: b"prefs")
    monkeypatch.setattr("sys.argv", ["rebuild_p5_collect.py", "--baseline", "case"])
    assert collector.main() == 1
