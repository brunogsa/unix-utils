import os
import subprocess
import sys
from pathlib import Path

SCRIPT_UNDER_TEST = Path(__file__).resolve().parent.parent / "get-enabled-modules.py"

BOTH_PRESENT = (
    '{"enabledPlugins":{"core@arco-ai-plugins":true,'
    '"audit@arco-ai-plugins":false,'
    '"linear@claude-plugins-official":true}}'
)
MALFORMED = '{"enabledPlugins": {"core@arco-ai-plugins": tru'


def run_script(env_overrides):
    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [sys.executable, str(SCRIPT_UNDER_TEST)],
        env=env,
        capture_output=True,
        text=True,
    )


def run_against(settings_path):
    return run_script({"CLAUDE_SETTINGS": str(settings_path)})


def write_fixture(tmp_path, name, body):
    fixture = tmp_path / name
    fixture.write_text(body + "\n")
    return fixture


def test_reports_both_modules_present_when_both_plugins_are_enabled(tmp_path):
    fixture = write_fixture(tmp_path, "both-present.json", BOTH_PRESENT)
    result = run_against(fixture)
    assert result.stdout == "arco=true\nlinear=true\n"
    assert result.returncode == 0


def test_reports_only_arco_present_when_one_arco_plugin_is_enabled_among_disabled_ones(tmp_path):
    fixture = write_fixture(
        tmp_path,
        "arco-only.json",
        '{"enabledPlugins":{"audit@arco-ai-plugins":false,"sdk@arco-ai-plugins":true}}',
    )
    assert run_against(fixture).stdout == "arco=true\nlinear=false\n"


def test_reports_only_linear_present_when_only_the_linear_plugin_is_enabled(tmp_path):
    fixture = write_fixture(
        tmp_path,
        "linear-only.json",
        '{"enabledPlugins":{"linear@claude-plugins-official":true}}',
    )
    assert run_against(fixture).stdout == "arco=false\nlinear=true\n"


def test_reads_the_settings_file_under_home_when_claude_settings_is_unset(tmp_path):
    claude_dir = tmp_path / "home" / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text(
        '{"enabledPlugins":{"core@arco-ai-plugins":true}}\n'
    )
    result = run_script({"HOME": str(tmp_path / "home"), "CLAUDE_SETTINGS": ""})
    assert result.stdout == "arco=true\nlinear=false\n"


def test_reports_both_absent_when_neither_module_key_exists(tmp_path):
    fixture = write_fixture(
        tmp_path,
        "neither-key.json",
        '{"enabledPlugins":{"frontend-design@claude-plugins-official":true}}',
    )
    result = run_against(fixture)
    assert result.stdout == "arco=false\nlinear=false\n"
    assert result.returncode == 0


def test_reports_both_absent_when_every_module_key_is_disabled(tmp_path):
    fixture = write_fixture(
        tmp_path,
        "all-false.json",
        '{"enabledPlugins":{"core@arco-ai-plugins":false,'
        '"sdd@arco-ai-plugins":false,'
        '"linear@claude-plugins-official":false}}',
    )
    assert run_against(fixture).stdout == "arco=false\nlinear=false\n"


def test_reports_both_absent_when_enabled_plugins_is_missing(tmp_path):
    fixture = write_fixture(tmp_path, "no-enabled-plugins.json", '{"model":"sonnet"}')
    result = run_against(fixture)
    assert result.stdout == "arco=false\nlinear=false\n"
    assert result.returncode == 0


def test_reports_both_absent_when_the_settings_file_is_missing(tmp_path):
    result = run_against(tmp_path / "does-not-exist.json")
    assert result.stdout == "arco=false\nlinear=false\n"
    assert result.returncode == 0


def test_reports_both_absent_when_the_settings_file_is_malformed_json(tmp_path):
    fixture = write_fixture(tmp_path, "malformed.json", MALFORMED)
    result = run_against(fixture)
    assert result.stdout == "arco=false\nlinear=false\n"
    assert result.returncode == 0


def test_reports_both_absent_when_the_settings_file_is_unreadable(tmp_path):
    fixture = write_fixture(
        tmp_path,
        "unreadable.json",
        '{"enabledPlugins":{"core@arco-ai-plugins":true}}',
    )
    fixture.chmod(0o000)
    try:
        result = run_against(fixture)
    finally:
        fixture.chmod(0o600)
    assert result.stdout == "arco=false\nlinear=false\n"
    assert result.returncode == 0


def test_warns_on_stderr_when_the_settings_file_is_malformed_json(tmp_path):
    fixture = write_fixture(tmp_path, "malformed.json", MALFORMED)
    assert run_against(fixture).stderr.rstrip("\n") == (
        f"get-enabled-modules.py: cannot read {fixture}"
        " - reporting both modules absent"
    )


def test_warns_on_stderr_when_the_settings_path_is_a_directory(tmp_path):
    settings_dir = tmp_path / "settings-dir.json"
    settings_dir.mkdir()
    assert run_against(settings_dir).stderr.rstrip("\n") == (
        f"get-enabled-modules.py: cannot read {settings_dir}"
        " - reporting both modules absent"
    )


def test_stays_silent_on_stderr_when_the_settings_file_is_readable(tmp_path):
    fixture = write_fixture(tmp_path, "both-present.json", BOTH_PRESENT)
    assert run_against(fixture).stderr == ""


def test_stays_silent_on_stderr_when_the_settings_file_does_not_exist(tmp_path):
    assert run_against(tmp_path / "does-not-exist.json").stderr == ""
