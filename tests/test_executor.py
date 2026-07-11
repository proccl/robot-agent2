import os
import time
from pathlib import Path
import pytest
from src.process_incoming import CommandExecutor
from src.natural_language import NaturalLanguagePlanner
from src.skill_context import SkillContext


@pytest.fixture
def dirs(tmp_path):
    return {
        "incoming": tmp_path / "incoming",
        "history": tmp_path / "incoming_history",
        "failed": tmp_path / "incoming" / "failed",
        "logs": tmp_path / "logs",
    }


class MockLLMClient:
    def __init__(self, response="interface.home()\nprint('done')"):
        self.response = response

    def chat(self, messages):
        return self.response


@pytest.fixture
def planner(dirs):
    client = MockLLMClient("interface.home()\nprint('done')")
    skill = SkillContext([])
    return NaturalLanguagePlanner(client, skill, dirs["incoming"])


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


@pytest.fixture
def txt_executor(mock_board, config, dirs, planner):
    from src.nexarm_interface import NexArmInterface
    interface = NexArmInterface(mock_board, config)
    return CommandExecutor(
        interface=interface,
        planner=planner,
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


def test_scan_includes_txt_files(executor, dirs):
    incoming = dirs["incoming"]
    (incoming / "cmd_20260626_120000_001_a.py").write_text("print('ok')", encoding="utf-8")
    (incoming / "cmd_20260626_120000_002_b.txt").write_text("go home", encoding="utf-8")
    files = executor.scan()
    names = [Path(f).name for f in files]
    assert "cmd_20260626_120000_001_a.py" in names
    assert "cmd_20260626_120000_002_b.txt" in names


def test_txt_instruction_is_converted_and_executed(txt_executor, dirs):
    incoming = dirs["incoming"]
    txt = incoming / "cmd_20260626_120000_001_home.txt"
    txt.write_text("return to home", encoding="utf-8")

    executed = txt_executor.run_once()
    assert executed is True
    assert not txt.exists()
    assert (dirs["history"] / txt.name).exists()
    generated = list(dirs["history"].glob("cmd_*.py"))
    assert len(generated) >= 1


def test_txt_without_planner_moves_to_failed(executor, dirs):
    incoming = dirs["incoming"]
    txt = incoming / "cmd_20260626_120000_001_no_planner.txt"
    txt.write_text("go home", encoding="utf-8")

    executed = executor.run_once()
    assert executed is True
    assert not txt.exists()
    assert (dirs["history"] / txt.name).exists()
    assert (dirs["failed"] / txt.name).exists()


def test_execution_beep_on_start_and_done(executor, dirs, mock_board):
    """指令執行開始和成功結束時應調用 set_buzzer。"""
    incoming = dirs["incoming"]
    script = incoming / "cmd_20260626_120003_001_beep.py"
    script.write_text("print('[Done] beep test')", encoding="utf-8")

    executed = executor.run_once()
    assert executed is True

    buzzer_calls = [call for call, _ in mock_board.calls if call == "set_buzzer"]
    assert len(buzzer_calls) == 2  # 開始一聲，結束兩聲（調用兩次）
