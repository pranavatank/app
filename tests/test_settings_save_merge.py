import os
import subprocess
import sys


def test_save_settings_merges_existing_values_without_deadlock(tmp_path):
    settings_path = tmp_path / "settings.json"
    code = r'''
import core.settings as settings
settings._PATH = r"%s"
settings.save_settings({"custom": "kept", "scheduled_backups_enabled": False})
assert settings.get_setting("custom") == "kept"
assert settings.get_setting("scheduled_backups_enabled") is False
assert settings.get_setting("show_onboarding_on_startup") is True
settings.save_settings({"second": 42})
assert settings.get_setting("custom") == "kept"
assert settings.get_setting("second") == 42
''' % str(settings_path).replace("\\", "\\\\")
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.getcwd(),
        capture_output=True,
        text=True,
        timeout=8,
    )
    assert result.returncode == 0, result.stdout + result.stderr
