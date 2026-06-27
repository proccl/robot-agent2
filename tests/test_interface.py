import pytest
import math
from src.nexarm_interface import SafetyError


def test_home_calls_arm_all_reset(interface, mock_board):
    interface.home(duration=2, wait=False)
    assert len(mock_board.calls) == 1
    call, args = mock_board.calls[0]
    assert call == "arm_all_reset"
    assert args["time_ms"] == 2000


def test_home_uses_default_speed(interface, mock_board):
    interface.home(wait=False)
    _, args = mock_board.calls[0]
    assert args["time_ms"] == 1500  # default_speed=1.5s


def test_move_to_calls_set_arm_coords(interface, mock_board):
    interface.move_to(x=250, y=50, z=300, duration=2, pitch=10, wait=False)
    assert len(mock_board.calls) == 1
    call, args = mock_board.calls[0]
    assert call == "set_arm_coords"
    assert args["x"] == 250
    assert args["y"] == 50
    assert args["z"] == 300
    assert args["pitch"] == 10
    assert args["time_ms"] == 2000


def test_move_to_out_of_range_raises(interface):
    with pytest.raises(SafetyError):
        interface.move_to(x=500, y=0, z=300, wait=False)


def test_relative_move_calls_arm_move_inc(interface, mock_board):
    interface.relative_move(dx=10, dy=0, dz=-20, duration=1.2, wait=False)
    call, args = mock_board.calls[0]
    assert call == "arm_move_inc"
    assert args["dx"] == 10
    assert args["dz"] == -20
    assert args["time_ms"] == 1200


def test_joint_move(interface, mock_board):
    interface.joint_move(servo_id=2, pos=1500, duration=0.8, wait=False)
    call, args = mock_board.calls[0]
    assert call == "arm_move_servo_single"
    assert args["servo_id"] == 2
    assert args["pos"] == 1500
    assert args["time_ms"] == 800


def test_joint_move_invalid_servo_raises(interface):
    with pytest.raises(SafetyError):
        interface.joint_move(servo_id=7, pos=1500, wait=False)


def test_joint_move_invalid_pulse_raises(interface):
    with pytest.raises(SafetyError):
        interface.joint_move(servo_id=1, pos=5000, wait=False)


def test_get_status(interface, mock_board):
    status = interface.get_status()
    assert status["x"] == 200
    assert status["servos"] == [2048] * 6


def test_get_status_fallback_to_arm_coords(interface, mock_board):
    """當 get_full_state 返回 None 時，應能從 get_arm_coords 構造狀態。"""
    mock_board.get_full_state = lambda: None
    status = interface.get_status()
    assert status["x"] == 200
    assert status["y"] == 0
    assert status["z"] == 200


def test_get_status_returns_cached_state(interface, mock_board):
    """當兩種讀取都失敗時，應返回上一次快取的狀態。"""
    # 先讀取一次成功，建立快取
    interface.get_status()
    # 再讓兩種讀取都失敗
    mock_board.get_full_state = lambda: None
    mock_board.get_arm_coords = lambda: None
    # 再次讀取，應返回快取
    status = interface.get_status()
    assert status["x"] == 200


def test_warmup_calls_get_status(interface, mock_board):
    """warmup 應調用 get_status 嘗試讀取狀態。"""
    interface.warmup(beep=False, retries=2, delay=0.01)
    # MockBoard 的 get_full_state 會被調用
    assert mock_board._state["z"] > 0


def test_warmup_beep_when_enabled(interface, mock_board):
    """warmup 在 beep=True 時應調用 set_buzzer。"""
    interface.warmup(beep=True, retries=1, delay=0.01)
    calls = [c for c, _ in mock_board.calls]
    assert "set_buzzer" in calls


def test_circle_produces_correct_points(interface, mock_board):
    interface.circle(center=(200, 0, 200), radius=50, duration=2, steps=4, wait=False)
    calls = [c for c, _ in mock_board.calls]
    assert all(c == "set_arm_coords" for c in calls)
    assert len(calls) == 5  # steps + 1
    # 第一點應在 (250, 0, 200)
    first = mock_board.calls[0][1]
    assert math.isclose(first["x"], 250, abs_tol=1e-9)
    assert math.isclose(first["y"], 0, abs_tol=1e-9)


def test_line_interpolates(interface, mock_board):
    interface.line(target=(300, 0, 300), duration=2, steps=5, wait=False)
    assert len(mock_board.calls) == 5
    last = mock_board.calls[-1][1]
    assert last["x"] == 300
    assert last["z"] == 300


def test_wait_blocks(interface, mock_board):
    import time
    start = time.time()
    interface.relative_move(dx=10, dy=0, dz=0, duration=0.3, wait=True)
    elapsed = time.time() - start
    assert elapsed >= 0.25, f"wait 應至少阻塞 duration 時間，實際只等了 {elapsed:.3f}s"
