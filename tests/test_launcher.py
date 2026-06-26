import subprocess
import sys
from pathlib import Path


def run_launcher(args, cwd, timeout=10):
    cmd = [sys.executable, "robot_agent2.py"] + args
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)


def test_help():
    root = Path(__file__).resolve().parent.parent
    result = run_launcher(["--help"], root)
    assert result.returncode == 0
    assert "robot-agent2" in result.stdout


def test_dry_run_once_processes_command(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parent.parent
    # 用臨時 incoming 目錄避免污染項目
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    script = incoming / "cmd_20260626_120000_001_dry.py"
    script.write_text("interface.home(duration=1, wait=False)\nprint('[Done] dry home')", encoding="utf-8")

    history = tmp_path / "incoming_history"
    failed = tmp_path / "failed"
    logs = tmp_path / "logs"
    result = run_launcher(
        [
            "--dry-run", "--once",
            "--config", str(root / "config" / "config.yaml"),
            "--incoming-dir", str(incoming),
            "--history-dir", str(history),
            "--failed-dir", str(failed),
            "--logs-dir", str(logs),
            "--poll-interval", "0.1",
        ],
        root,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "Executed one command" in result.stdout or "[Done] dry home" in result.stdout
