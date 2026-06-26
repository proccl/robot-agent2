import pytest
from src.nexarm_interface import NexArmInterface


class MockBoard:
    """模擬 NexArm SDK 的 Board 類，用於單元測試。"""

    def __init__(self):
        self.calls = []
        self._state = {
            "x": 200,
            "y": 0,
            "z": 200,
            "pitch": 0.0,
            "roll": 0,
            "claw": 0,
            "servos": [2048] * 6,
        }

    def arm_all_reset(self, time_ms=2000):
        self.calls.append(("arm_all_reset", {"time_ms": time_ms}))

    def set_arm_coords(self, x, y, z, pitch=0, roll=0, claw=0, time_ms=1000, calc_only=False):
        self.calls.append(("set_arm_coords", {
            "x": x, "y": y, "z": z,
            "pitch": pitch, "roll": roll, "claw": claw,
            "time_ms": time_ms,
        }))

    def arm_move_inc(self, dx, dy, dz, dpitch=0, droll=0, dclaw=0, time_ms=1000):
        self.calls.append(("arm_move_inc", {
            "dx": dx, "dy": dy, "dz": dz,
            "dpitch": dpitch, "droll": droll, "dclaw": dclaw,
            "time_ms": time_ms,
        }))

    def arm_move_servo_single(self, servo_id, pos, time_ms=1000):
        self.calls.append(("arm_move_servo_single", {
            "servo_id": servo_id, "pos": pos, "time_ms": time_ms,
        }))

    def get_full_state(self):
        return self._state


@pytest.fixture
def config():
    return {
        "default_speed": 1.5,
        "workspace_limits": {
            "x": {"min": 0, "max": 350},
            "y": {"min": -250, "max": 250},
            "z": {"min": 50, "max": 450},
            "pitch": {"min": -90, "max": 90},
            "roll": {"min": -90, "max": 90},
            "claw": {"min": -90, "max": 90},
        },
        "servo_limits": {"pulse_min": 0, "pulse_max": 4095},
    }


@pytest.fixture
def mock_board():
    return MockBoard()


@pytest.fixture
def interface(mock_board, config):
    return NexArmInterface(mock_board, config)
