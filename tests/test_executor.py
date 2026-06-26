import os
import time
from pathlib import Path
import pytest
from src.process_incoming import CommandExecutor


@pytest.fixture
def dirs(tmp_path):
    return {
        "incoming": tmp_path / "incoming",
        "history": tmp_path / "incoming_history",
        "failed": tmp_path / "incoming" / "failed",
        "logs": tmp_path / "logs",
    }


@pytest.fixture
def executor(mock_board, config, dirs):
    from src.nexarm_interface import NexArmInterface
    interface = NexArmInterface(mock_board, config)
    return CommandExecutor(
        interface=interface,
        incoming_dir=str(dirs["incoming"]),
        history_dir=str(dirs["history"]),
        failed_dir=str(dirs["failed"]),
        logs_dir=str(dirs["logs"]),
        poll_interval=0.01,
    )


def test_scan_order(executor, dirs):
    incoming = dirs["incoming"]
    for name in ["cmd_20260626_120005_002_b.py", "cmd_20260626_120000_001_a.py", "cmd_20260626_120010_003_c.py"]:
        (incoming / name).write_text("print('ok')", encoding="utf-8")
    files = executor.scan()
    assert [Path(f).name for f in files] == [
        "cmd_20260626_120000_001_a.py",
        "cmd_20260626_120005_002_b.py",
        "cmd_20260626_120010_003_c.py",
    ]


def test_success_execution_is_archived(executor, dirs):
    incoming = dirs["incoming"]
    script = incoming / "cmd_20260626_120000_001_success.py"
    script.write_text("print('[Done] success')", encoding="utf-8")

    executed = executor.run_once()
    assert executed is True
    assert not script.exists()
    assert (dirs["history"] / script.name).exists()
    assert not (dirs["failed"] / script.name).exists()


def test_failure_execution_moves_to_failed(executor, dirs):
    incoming = dirs["incoming"]
    script = incoming / "cmd_20260626_120001_001_fail.py"
    script.write_text("raise RuntimeError('boom')", encoding="utf-8")

    executed = executor.run_once()
    assert executed is True
    assert not script.exists()
    assert (dirs["history"] / script.name).exists()
    assert (dirs["failed"] / script.name).exists()


def test_busy_lock_skips_new_command(executor, dirs, monkeypatch):
    incoming = dirs["incoming"]
    script = incoming / "cmd_20260626_120002_001_busy.py"
    script.write_text("print('ok')", encoding="utf-8")

    # 強制設置 busy
    executor._busy = True
    executed = executor.run_once()
    assert executed is False
    assert script.exists()  # 仍在 incoming 中
