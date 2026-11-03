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
    log_content = (tmp_path / "logs" / "test_example.py.log").read_text(
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
