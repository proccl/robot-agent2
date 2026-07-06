#!/usr/bin/env python3
"""
robot_agent2.py

對照 MATLAB 項目的 robotagent.m：
一鍵啟動文件隊列機械臂代理。
"""
import argparse
import time

import yaml

from sdk.ros_robot_controller_sdk import Board
from src.nexarm_interface import NexArmInterface
from src.process_incoming import CommandExecutor


class DryRunBoard:
    """乾跑模式使用的假 Board，不連接真實串口。"""

    def __init__(self, **kwargs):
        self.calls = []

    def arm_all_reset(self, time_ms=2000):
        self.calls.append(("arm_all_reset", time_ms))

    def set_arm_coords(self, x, y, z, pitch=0, roll=0, claw=0, time_ms=1000, calc_only=False):
        self.calls.append(("set_arm_coords", (x, y, z, time_ms)))

    def arm_move_inc(self, dx, dy, dz, dpitch=0, droll=0, dclaw=0, time_ms=1000):
        self.calls.append(("arm_move_inc", (dx, dy, dz, time_ms)))

    def arm_move_servo_single(self, servo_id, pos, time_ms=1000):
        self.calls.append(("arm_move_servo_single", (servo_id, pos, time_ms)))

    def get_full_state(self):
        return {
            "x": 200, "y": 0, "z": 200,
            "pitch": 0.0, "roll": 0, "claw": 0,
            "servos": [2048] * 6,
        }

    def get_arm_coords(self):
        return (self._state["x"], self._state["y"], self._state["z"])

    def set_buzzer(self, freq, on_time_s, off_time_s, repeat=1):
        self.calls.append(("set_buzzer", (freq, on_time_s, off_time_s, repeat)))


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_interface(cfg: dict, port: str = None, dry_run: bool = False):
    if dry_run:
        board = DryRunBoard()
    else:
        board = Board(device=port or cfg["port"], baudrate=cfg["baudrate"], timeout=cfg.get("timeout", 0.1))
        board.enable_reception(True)

    interface = NexArmInterface(board, cfg)

    if not dry_run:
        warmup_cfg = cfg.get("warmup", {})
        if warmup_cfg.get("enabled", True):
            interface.warmup(
                beep=warmup_cfg.get("beep", True),
                retries=warmup_cfg.get("retries", 5),
                delay=warmup_cfg.get("delay", 1.0),
            )

    return interface


def main():
    parser = argparse.ArgumentParser(description="robot-agent2: Python + NexArm SDK 文件隊列代理")
    parser.add_argument("--config", default="config/config.yaml", help="配置文件路徑")
    parser.add_argument("--port", default=None, help="覆寫串口埠號")
    parser.add_argument("--dry-run", action="store_true", help="乾跑模式，不連接真實硬體")
    parser.add_argument("--once", action="store_true", help="執行一條指令後退出")
    parser.add_argument("--poll-interval", type=float, default=None, help="輪詢間隔（秒）")
    parser.add_argument("--log-level", default=None, help="日誌級別")
    parser.add_argument("--incoming-dir", default="incoming", help="指令隊列目錄")
    parser.add_argument("--history-dir", default="incoming_history", help="執行過的腳本備份目錄")
    parser.add_argument("--failed-dir", default="incoming/failed", help="執行失敗的腳本歸檔目錄")
    parser.add_argument("--logs-dir", default="logs", help="日誌目錄")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.log_level:
        cfg["log_level"] = args.log_level

    print(f"[*] robot-agent2 starting (dry_run={args.dry_run})")
    interface = build_interface(cfg, port=args.port, dry_run=args.dry_run)
    print("[*] Interface ready")

    executor = CommandExecutor(
        interface=interface,
        incoming_dir=args.incoming_dir,
        history_dir=args.history_dir,
        failed_dir=args.failed_dir,
        logs_dir=args.logs_dir,
        poll_interval=args.poll_interval if args.poll_interval is not None else cfg.get("poll_interval", 0.5),
    )

    print("[*] Executor running, press Ctrl+C to stop")
    try:
        if args.once:
            # 等待並執行一條指令後退出
            safety_timeout = cfg.get("safety_timeout", 10)
            if safety_timeout:
                deadline = time.time() + safety_timeout
                while time.time() < deadline:
                    if executor.run_once():
                        print("[*] Executed one command, exiting (--once)")
                        break
                    time.sleep(executor.poll_interval)
                else:
                    print("[*] No command found within timeout, exiting (--once)")
            else:
                # safety_timeout 為 0 或 None，無限等待
                while True:
                    if executor.run_once():
                        print("[*] Executed one command, exiting (--once)")
                        break
                    time.sleep(executor.poll_interval)
        else:
            executor.run()
    except KeyboardInterrupt:
        print("\n[*] Stopped by user")


if __name__ == "__main__":
    main()
