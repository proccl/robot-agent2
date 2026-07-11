import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import yaml

from robot_agent2 import build_interface, DryRunBoard, build_llm_client


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


def test_dry_run_build_interface_skips_warmup(config):
    """乾跑模式下 build_interface 不應調用 warmup（不會連接真實串口）。"""
    interface = build_interface(config, dry_run=True)
    assert isinstance(interface.board, DryRunBoard)
    calls = [call for call, _ in interface.board.calls]
    assert "set_buzzer" not in calls


def test_chat_mode_requires_api_key():
    """--chat 在缺少 API key 時應報錯退出。"""
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env.pop("SJTU_API_KEY", None)
    result = run_launcher(
        ["--config", str(root / "config" / "config.yaml"), "--chat"],
        root,
        timeout=10,
    )
    assert result.returncode != 0
    assert "SJTU_API_KEY" in result.stderr or "API key" in result.stderr


def test_build_llm_client_reads_config(monkeypatch):
    """build_llm_client 應根據 config 創建 LLMClient。"""
    root = Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load((root / "config" / "config.yaml").read_text(encoding="utf-8"))
    monkeypatch.setenv("SJTU_API_KEY", "test-key")
    client = build_llm_client(cfg)
    assert client.model == cfg["llm"]["model"]
    assert client.base_url == cfg["llm"]["base_url"].rstrip("/")


def test_with_chat_starts_chat_thread_and_queues_script(tmp_path, monkeypatch, capsys):
    """--with-chat 應啟動 chat 線程並將生成的腳本寫入 incoming 後執行歸檔。"""
    root = Path(__file__).resolve().parent.parent
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    history = tmp_path / "incoming_history"

    def fake_chat_loop(planner):
        planner.save_script("go home", "interface.home()\nprint('done')")

    monkeypatch.setenv("SJTU_API_KEY", "test-key")
    monkeypatch.setattr("robot_agent2.chat_loop_for_arm", fake_chat_loop)
    monkeypatch.setattr(
        "sys.argv",
        [
            "robot_agent2.py",
            "--dry-run", "--once",
            "--config", str(root / "config" / "config.yaml"),
            "--incoming-dir", str(incoming),
            "--history-dir", str(history),
            "--failed-dir", str(tmp_path / "failed"),
            "--logs-dir", str(tmp_path / "logs"),
            "--poll-interval", "0.1",
            "--with-chat",
        ],
    )

    from robot_agent2 import main
    main()

    captured = capsys.readouterr()
    assert "Chat thread started" in captured.out
    archived = list(history.glob("cmd_*.py"))
    assert len(archived) >= 1
