#!/usr/bin/env python3
"""
robot_agent2.py

對照 MATLAB 項目的 robotagent.m：
一鍵啟動文件隊列機械臂代理。
"""
import argparse
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import yaml

from sdk.ros_robot_controller_sdk import Board
from src.llm_client import LLMClient, LLMError
from src.nexarm_interface import NexArmInterface
from src.process_incoming import CommandExecutor
from src.natural_language import NaturalLanguagePlanner
from src.skill_context import SkillContext


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


def build_llm_client(cfg: dict) -> LLMClient:
    """根據配置與環境變量創建 LLM 客戶端。"""
    llm_cfg = cfg["llm"]
    api_key = os.environ.get(llm_cfg["api_key_env"])
    if not api_key:
        raise LLMError(
            f"API key environment variable {llm_cfg['api_key_env']} is not set."
        )
    return LLMClient(
        base_url=llm_cfg["base_url"],
        api_key=api_key,
        model=llm_cfg["model"],
        temperature=llm_cfg.get("default_temperature", 0.3),
        max_tokens=llm_cfg.get("default_max_tokens", 2048),
    )


def chat_loop_for_arm(planner: NaturalLanguagePlanner):
    """Chat UI for arm control: generate scripts and queue them to incoming/."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    client = planner.client
    skill_context = planner.skill_context

    messages = []
    base_chunks = skill_context.retrieve(
        "NexArm robot arm general operation", top_k=3
    )
    system_prompt = (
        "You are an assistant for the NexArm 6-DOF robot arm. "
        "Convert the user's request into a Python script using the `interface` object. "
        "Return only the Python script in a markdown fence. "
        "Keep explanations minimal.\n\n"
        "Project context:\n"
        + skill_context.format_chunks(base_chunks)
    )
    messages.append({"role": "system", "content": system_prompt})

    print("[*] Arm chat mode. Type 'exit' or 'quit' to leave.")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue

        chunks = skill_context.retrieve(user_input, top_k=2)
        content = user_input
        if chunks:
            content = (
                "Relevant project context:\n"
                + skill_context.format_chunks(chunks)
                + "\n\nUser request: "
                + user_input
            )
        messages.append({"role": "user", "content": content})

        print("LLM: ", end="", flush=True)
        try:
            response_parts = []
            for token in client.chat_stream(messages):
                print(token, end="", flush=True)
                response_parts.append(token)
            print()
            response = "".join(response_parts)
            messages.append({"role": "assistant", "content": response})

            # Extract and queue the generated script
            script = NaturalLanguagePlanner._clean_script(response)
            if script:
                path = planner.save_script(user_input, script)
                print(f"[*] Queued script: {path.name}")

            # Keep system prompt + recent rounds to avoid context overflow
            if len(messages) > 12:
                messages = [messages[0]] + messages[-10:]
        except LLMError as e:
            print(f"\n[!] LLM error: {e}")


def chat_loop(client: LLMClient, skill_context: Optional[SkillContext] = None):
    """簡易終端 LLM chat，支持流式輸出與項目 Skill 上下文。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    messages = []
    if skill_context is not None:
        base_chunks = skill_context.retrieve(
            "NexArm robot arm general operation", top_k=3
        )
        system_prompt = (
            "You are an assistant for the NexArm 6-DOF robot arm project. "
            "Use the provided project context to answer questions. "
            "When the user asks to move the arm or execute an action, "
            "generate Python code using the `interface` object (NexArmInterface). "
            "Keep responses concise and project-specific.\n\n"
            "Project context:\n"
            + skill_context.format_chunks(base_chunks)
        )
        messages.append({"role": "system", "content": system_prompt})

    print("[*] Chat mode. Type 'exit' or 'quit' to leave.")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue

        content = user_input
        if skill_context is not None:
            chunks = skill_context.retrieve(user_input, top_k=2)
            if chunks:
                content = (
                    "Relevant project context:\n"
                    + skill_context.format_chunks(chunks)
                    + "\n\nUser request: "
                    + user_input
                )
        messages.append({"role": "user", "content": content})

        print("LLM: ", end="", flush=True)
        try:
            response_parts = []
            for token in client.chat_stream(messages):
                print(token, end="", flush=True)
                response_parts.append(token)
            print()
            response = "".join(response_parts)
            messages.append({"role": "assistant", "content": response})
            # 保留 system prompt + 最近若干輪，避免上下文過長
            if len(messages) > 12:
                messages = [messages[0]] + messages[-10:]
        except LLMError as e:
            print(f"\n[!] LLM error: {e}")


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
    parser.add_argument("--interactive", "--chat", action="store_true",
                        dest="chat", help="進入 LLM chat 模式（不連接機械臂）")
    parser.add_argument("--with-chat", action="store_true",
                        help="在機械臂值守模式下同時運行 chat 線程")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.log_level:
        cfg["log_level"] = args.log_level

    if args.chat:
        client = build_llm_client(cfg)
        root = Path(args.config).resolve().parent.parent
        llm_cfg = cfg.get("llm", {})
        skill_context = SkillContext(
            [str(root / p) for p in llm_cfg.get("skill_context", [])]
        )
        chat_loop(client, skill_context=skill_context)
        return

    print(f"[*] robot-agent2 starting (dry_run={args.dry_run})")
    interface = build_interface(cfg, port=args.port, dry_run=args.dry_run)
    print("[*] Interface ready")

    planner = None
    if "llm" in cfg:
        try:
            planner = NaturalLanguagePlanner.from_config(args.config)
        except LLMError as e:
            print(f"[!] LLM planner not available: {e}")

    chat_thread = None
    if args.with_chat and "llm" in cfg:
        try:
            chat_planner = NaturalLanguagePlanner.from_config(
                args.config, incoming_dir=Path(args.incoming_dir)
            )
            chat_thread = threading.Thread(
                target=chat_loop_for_arm,
                args=(chat_planner,),
                daemon=True,
            )
            chat_thread.start()
            print("[*] Chat thread started")
        except LLMError as e:
            print(f"[!] Chat not available: {e}")

    executor = CommandExecutor(
        interface=interface,
        planner=planner,
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
