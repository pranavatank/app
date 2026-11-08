"""Regression coverage for the isolated pytest runner's exit handling."""

import subprocess
import sys
from unittest.mock import patch

import pytest

from tools import run_full_tests


@pytest.mark.parametrize(
    ("returncode", "expected"),
    [(0, "PASS"), (1, "FAIL"), (5, "NO TESTS"),
     (2, "CRASH"), (3, "CRASH"), (4, "CRASH")],
)
def test_classify_result_preserves_pytest_exit_codes(returncode, expected):
    assert run_full_tests.classify_result(returncode, None) == expected


@pytest.mark.parametrize("returncode", [3221225477, -1073741819])
def test_native_crash_after_clean_summary_is_still_crash(returncode):
    assert run_full_tests.classify_result(returncode, "1 passed in 0.01s") == "CRASH"


def test_manifest_cannot_select_native_or_support_scripts():
    manifest = {"features": {"bad": ["tests/native/test_ui.py"]}}
    with pytest.raises(ValueError, match="not headless test targets"):
        run_full_tests.discover_tests(features=["bad"], manifest=manifest)


def test_directory_discovery_skips_native_and_support(tmp_path, monkeypatch):
    native = tmp_path / "tests" / "native"
    support = tmp_path / "tests" / "support"
    native.mkdir(parents=True)
    support.mkdir()
    (native / "test_native.py").write_text("", encoding="utf-8")
    (support / "test_helper.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(run_full_tests, "ROOT", tmp_path)
    manifest = {"features": {}}
    with pytest.raises(ValueError, match="contains no test_"):
        run_full_tests.discover_tests(inputs=["tests/native"], manifest=manifest)
    with pytest.raises(ValueError, match="not headless test targets"):
        run_full_tests.discover_tests(inputs=["tests/support/test_helper.py"], manifest=manifest)


def test_default_discovery_excludes_native_and_support_tree():
    paths = run_full_tests.discover_tests()
    assert paths
    assert all("/native/" not in rel and "/support/" not in rel for rel, _ in paths)


def _run_main(tmp_path, monkeypatch, test_files, run_side_effect):
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_full_tests.py", "--log-dir", str(log_dir), *test_files],
    )
    with patch.object(run_full_tests.subprocess, "run", side_effect=run_side_effect):
        result = run_full_tests.main()
    return result


def _completed_process(returncode, output=""):
    def run(*_args, **kwargs):
        if output:
            kwargs["stdout"].write(output)
        return subprocess.CompletedProcess(args=[], returncode=returncode)

    return run


@pytest.mark.parametrize(
    ("returncode", "summary", "expected_status", "expected_exit"),
    [
        (0, "1 passed in 0.01s\n", "PASS", 0),
        (1, "1 failed in 0.01s\n", "FAIL", 1),
        (5, "", "NO TESTS", 0),
        (2, "", "CRASH", 1),
        (3, "", "CRASH", 1),
        (4, "", "CRASH", 1),
        (3221225477, "1 passed in 0.01s\n", "CRASH", 1),
        (-1073741819, "1 passed in 0.01s\n", "CRASH", 1),
        (3221225477, "", "CRASH", 1),
    ],
)
def test_main_reports_process_exit_and_aggregate(
    tmp_path, monkeypatch, capsys, returncode, summary, expected_status, expected_exit
):
    exit_code = _run_main(
        tmp_path,
        monkeypatch,
        ["tests/test_example.py"],
        _completed_process(returncode, summary),
    )

    output = capsys.readouterr().out
    assert exit_code == expected_exit
    assert expected_status in output
    log_content = (tmp_path / "logs" / "tests__test_example.py.log").read_text(
        encoding="utf-8"
    )
    assert f"[run_full_tests] process exit code: {returncode}" in log_content
    if expected_status == "CRASH" and summary:
        assert summary.strip() in output
        assert summary.strip() in log_content


def test_main_mixed_pass_and_crash_fails_aggregate(tmp_path, monkeypatch, capsys):
    def run(args, **kwargs):
        test_file = args[3]
        if test_file.endswith("test_pass.py"):
            kwargs["stdout"].write("1 passed in 0.01s\n")
            return subprocess.CompletedProcess(args=args, returncode=0)
        kwargs["stdout"].write("1 passed in 0.01s\n")
        return subprocess.CompletedProcess(args=args, returncode=3221225477)

    exit_code = _run_main(
        tmp_path,
        monkeypatch,
        ["tests/test_pass.py", "tests/test_crash.py"],
        run,
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "PASS" in output
    assert "CRASH" in output


def test_main_timeout_is_nonzero_and_reported(tmp_path, monkeypatch, capsys):
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=120)

    exit_code = _run_main(
        tmp_path, monkeypatch, ["tests/test_timeout.py"], timeout
    )

    assert exit_code == 1
    assert "TIMEOUT" in capsys.readouterr().out


def test_main_subprocess_launch_error_is_nonzero_and_reported(
    tmp_path, monkeypatch, capsys
):
    def launch_error(*_args, **_kwargs):
        raise OSError("cannot launch pytest")

    exit_code = _run_main(
        tmp_path, monkeypatch, ["tests/test_launch_error.py"], launch_error
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "ERROR" in output
    assert "cannot launch pytest" in output
