"""
nexarm_interface.py

對照 MATLAB 項目的 Arm7R.m：
封裝 NexArm SDK 的 Board 類，提供 robot-agent 風格的高層運動 API 與安全限位。
"""
from typing import Dict, List, Optional, Tuple
import math
import time

from src.natural_language import NaturalLanguagePlanner


class SafetyError(ValueError):
    """目標位置或參數超出安全範圍。"""
    pass


class NexArmInterface:
    """
    將底層 Board 協議映射成 robot-agent2 指令語義。

    Parameters
    ----------
    board : object
        NexArm SDK 的 Board 實例（或測試用的 mock）。
    config : dict, optional
        包含 workspace_limits、servo_limits、default_speed、log_level 等。
    """

    def __init__(self, board, config: Optional[dict] = None):
        self.board = board
        self.config = config or {}
        self.default_speed = self.config.get("default_speed", 1000)
        self.workspace_limits = self.config.get("workspace_limits", {})
        self.servo_limits = self.config.get("servo_limits", {"pulse_min": 0, "pulse_max": 4095})
        self._last_status = None
        self._planner: Optional[NaturalLanguagePlanner] = None

    # ------------------------------------------------------------------ #
    # 工具方法
    # ------------------------------------------------------------------ #
    def _duration(self, duration: Optional[float] = None) -> int:
        """返回毫秒級時間，預設使用 default_speed（秒）。"""
        duration_sec = duration if duration is not None else self.default_speed
        return int(duration_sec * 1000)

    def _check_workspace(self, x: float, y: float, z: float, pitch: float = 0,
                         roll: float = 0, claw: float = 0):
        """檢查目標座標/姿態是否在工作空間軟限位內。"""
        checks = {
            "x": x,
            "y": y,
            "z": z,
            "pitch": pitch,
            "roll": roll,
            "claw": claw,
        }
        for axis, value in checks.items():
            limit = self.workspace_limits.get(axis)
            if limit is None:
                continue
            if not (limit["min"] <= value <= limit["max"]):
                raise SafetyError(
                    f"{axis}={value} 超出安全限位 [{limit['min']}, {limit['max']}]"
                )

    def _check_servo(self, servo_id: int, pos: int):
        if not (1 <= servo_id <= 6):
            raise SafetyError(f"servo_id={servo_id} 必須在 1~6 之間")
        if not (self.servo_limits["pulse_min"] <= pos <= self.servo_limits["pulse_max"]):
            raise SafetyError(
                f"servo {servo_id} 目標脈衝 {pos} 超出限位 "
                f"[{self.servo_limits['pulse_min']}, {self.servo_limits['pulse_max']}]"
            )

    def _maybe_wait(self, duration: float, wait: bool):
        """若 wait=True，等待動作完成。"""
        if wait and duration > 0:
            time.sleep(duration)

    # ------------------------------------------------------------------ #
    # 高層運動 API
    # ------------------------------------------------------------------ #
    def home(self, duration: Optional[float] = None, wait: bool = True):
        """回零位。"""
        duration_sec = duration if duration is not None else self.default_speed
        self.board.arm_all_reset(time_ms=self._duration(duration))
        self._maybe_wait(duration_sec, wait)

    def move_to(self, x: float, y: float, z: float, duration: Optional[float] = None,
                pitch: float = 0, roll: float = 0, claw: float = 0, wait: bool = True):
        """絕對座標移動。"""
        duration_sec = duration if duration is not None else self.default_speed
        self._check_workspace(x, y, z, pitch, roll, claw)
        self.board.set_arm_coords(
            x=x, y=y, z=z,
            pitch=pitch, roll=roll, claw=claw,
            time_ms=self._duration(duration)
        )
        self._maybe_wait(duration_sec, wait)

    def relative_move(self, dx: float, dy: float, dz: float,
                      duration: Optional[float] = None,
                      dpitch: float = 0, droll: float = 0, dclaw: float = 0,
                      wait: bool = True):
        """相對座標移動。"""
        duration_sec = duration if duration is not None else self.default_speed
        # 若要更嚴謹，可先讀取狀態計算目標再檢查；這裡先交給 SDK 處理
        self.board.arm_move_inc(
            dx=dx, dy=dy, dz=dz,
            dpitch=dpitch, droll=droll, dclaw=dclaw,
            time_ms=self._duration(duration)
        )
        self._maybe_wait(duration_sec, wait)

    def joint_move(self, servo_id: int, pos: int, duration: Optional[float] = None,
                   wait: bool = True):
        """單個舵機移動到指定脈衝位置。"""
        duration_sec = duration if duration is not None else self.default_speed
        self._check_servo(servo_id, pos)
        self.board.arm_move_servo_single(
            servo_id=servo_id,
            pos=pos,
            time_ms=self._duration(duration)
        )
        self._maybe_wait(duration_sec, wait)

    def line(self, target: Tuple[float, float, float], duration: Optional[float] = None,
             steps: int = 10, wait: bool = True):
        """
        從當前末端位置直線插值移動到 target。
        target : (x, y, z)
        """
        duration_sec = duration if duration is not None else self.default_speed
        status = self.get_status()
        start = (status["x"], status["y"], status["z"])
        tx, ty, tz = target
        for i in range(1, steps + 1):
            t = i / steps
            x = start[0] + (tx - start[0]) * t
            y = start[1] + (ty - start[1]) * t
            z = start[2] + (tz - start[2]) * t
            self._check_workspace(x, y, z)
            self.board.set_arm_coords(x=x, y=y, z=z, time_ms=self._duration(duration) // steps)
        self._maybe_wait(duration_sec, wait)

    def circle(self, center: Tuple[float, float, float], radius: float,
               duration: Optional[float] = None, steps: int = 20, wait: bool = True):
        """
        在 XY 平面畫圓。
        center : (x, y, z)
        radius : 圓半徑
        """
        duration_sec = duration if duration is not None else self.default_speed
        cx, cy, cz = center
        step_duration = self._duration(duration) // steps
        for i in range(steps + 1):
            theta = 2 * math.pi * i / steps
            x = cx + radius * math.cos(theta)
            y = cy + radius * math.sin(theta)
            z = cz
            self._check_workspace(x, y, z)
            self.board.set_arm_coords(x=x, y=y, z=z, time_ms=step_duration)
        self._maybe_wait(duration_sec, wait)

    def get_status(self) -> Dict:
        """取得並快取當前機械臂狀態。"""
        state = self.board.get_full_state()

        # 若 get_full_state 失敗，嘗試用 get_arm_coords 構造狀態
        if state is None and hasattr(self.board, "get_arm_coords"):
            coords = self.board.get_arm_coords()
            if coords is not None and len(coords) >= 3:
                state = {
                    "x": coords[0],
                    "y": coords[1],
                    "z": coords[2],
                    "pitch": 0.0,
                    "roll": 0,
                    "claw": 0,
                    "servos": [],
                }

        if state is None:
            if self._last_status is not None:
                return self._last_status
            return {
                "x": 0, "y": 0, "z": 0,
                "pitch": 0.0, "roll": 0, "claw": 0,
                "servos": [],
            }

        self._last_status = state
        return state

    def warmup(self, beep: bool = True, retries: int = 5, delay: float = 1.0):
        """
        真機啟動後的初始化握手。

        流程：
        1. 若 beep=True，發送短促蜂鳴器指令喚醒通訊。
        2. 多次嘗試讀取狀態，直到成功或達到最大重試次數。

        此方法不強制要求成功，失敗僅打印警告。
        """
        if beep and hasattr(self.board, "set_buzzer"):
            try:
                self.board.set_buzzer(freq=2500, on_time_s=0.1, off_time_s=0.0, repeat=1)
                print("[*] Warmup beep sent")
            except Exception as e:
                print(f"[!] Warmup beep failed: {e}")

        print("[*] Warming up, waiting for arm to respond...")
        for i in range(retries):
            try:
                status = self.get_status()
                if status and status.get("z", 0) > 0:
                    print(f"[*] Warmup OK: x={status['x']}, y={status['y']}, z={status['z']}")
                    return
            except Exception as e:
                print(f"[!] Warmup retry {i + 1}/{retries} failed: {e}")
            if i < retries - 1:
                time.sleep(delay)

        print("[!] Warmup finished but could not read a valid status (arm may still work)")

    def attach_planner(self, planner: NaturalLanguagePlanner):
        """Attach a NaturalLanguagePlanner for ask_llm()."""
        self._planner = planner

    def ask_llm(self, instruction: str, execute: bool = False, save: bool = True,
                planner: Optional[NaturalLanguagePlanner] = None) -> str:
        """
        使用 LLM 將自然語言指令轉換為 Python 腳本。

        Parameters
        ----------
        instruction : str
            自然語言指令，例如 "move forward 50 mm"。
        execute : bool
            是否立即執行生成的腳本。
        save : bool
            是否將腳本保存到 incoming/ 目錄。
        planner : NaturalLanguagePlanner, optional
            可覆蓋已附加的 planner。

        Returns
        -------
        str
            生成的 Python 腳本內容。
        """
        active = planner or self._planner
        if active is None:
            active = NaturalLanguagePlanner.from_config()
            self._planner = active

        script = active.generate_script(instruction)
        if save:
            path = active.save_script(instruction, script)
            print(f"[*] LLM script saved to {path}")
        if execute:
            state = self.get_status()
            script_globals = {
                "__name__": "__main__",
                "interface": self,
                "state": state,
            }
            exec(script, script_globals)
        return script
