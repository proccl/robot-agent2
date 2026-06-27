"""
process_incoming.py

對照 MATLAB 項目的 processIncomingCommands.m：
掃描 incoming/ 目錄中的 cmd_*.py 腳本，按檔名時間排序執行，
注入 interface 與 state，記錄日誌並歸檔成功/失敗腳本。
"""
import os
import shutil
import glob
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional


class CommandExecutor:
    """
    文件隊列執行器。

    Parameters
    ----------
    interface : NexArmInterface
        用於執行運動指令的高層介面。
    incoming_dir : str
        待執行腳本目錄。
    history_dir : str
        執行過的腳本備份目錄。
    failed_dir : str
        執行失敗的腳本歸檔目錄。
    logs_dir : str
        日誌目錄。
    poll_interval : float
        主循環輪詢間隔（秒）。
    """

    def __init__(self, interface, incoming_dir: str = "incoming",
                 history_dir: str = "incoming_history",
                 failed_dir: str = "incoming/failed",
                 logs_dir: str = "logs",
                 poll_interval: float = 0.5):
        self.interface = interface
        self.incoming_dir = Path(incoming_dir)
        self.history_dir = Path(history_dir)
        self.failed_dir = Path(failed_dir)
        self.logs_dir = Path(logs_dir)
        self.poll_interval = poll_interval
        self._busy = False

        # 確保目錄存在
        for d in (self.incoming_dir, self.history_dir, self.failed_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)

        self._setup_logging()

    def _setup_logging(self):
        """每天一個日誌檔案。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.logs_dir / f"robot_agent2_{timestamp}.log"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler(),
            ],
            force=True,
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("CommandExecutor initialized.")

    def scan(self) -> list:
        """掃描並按檔名排序返回 cmd_*.py 路徑。"""
        pattern = self.incoming_dir / "cmd_*.py"
        files = glob.glob(str(pattern))
        files.sort()
        return files

    @property
    def is_busy(self) -> bool:
        return self._busy

    def _beep(self, repeat: int = 1):
        """發送蜂鳴器提示音；若 board 不支持則靜默跳過。"""
        board = getattr(self.interface, "board", None)
        if board is None or not hasattr(board, "set_buzzer"):
            return
        try:
            board.set_buzzer(freq=2500, on_time_s=0.1, off_time_s=0.1, repeat=repeat)
        except Exception:
            pass

    def execute_script(self, script_path: str):
        """執行單個腳本。"""
        script_path = Path(script_path)
        self._busy = True
        self.logger.info(f"Executing {script_path.name}")

        # 指令開始提示音
        self._beep(repeat=1)

        try:
            state = self.interface.get_status()
            script_globals = {
                "__name__": "__main__",
                "interface": self.interface,
                "state": state,
            }
            with open(script_path, "r", encoding="utf-8") as f:
                source = f.read()
            exec(source, script_globals)
            self.logger.info(f"[Done] {script_path.name}")
            # 指令成功結束提示音
            self._beep(repeat=2)
            self._archive(script_path, success=True)
        except Exception as e:
            self.logger.error(f"[ERR] {script_path.name}: {e}")
            self.logger.error(traceback.format_exc())
            self._archive(script_path, success=False)
        finally:
            self._busy = False

    def _archive(self, script_path: Path, success: bool):
        """歸檔腳本：無論成功與否都備份到 history；失敗時額外移至 failed。"""
        # 備份到 history
        dest_history = self.history_dir / script_path.name
        shutil.copy2(script_path, dest_history)

        if success:
            script_path.unlink(missing_ok=True)
        else:
            dest_failed = self.failed_dir / script_path.name
            shutil.move(str(script_path), str(dest_failed))

    def run_once(self) -> bool:
        """執行一次掃描；若有指令且未忙碌，執行最舊的一個。返回是否執行了指令。"""
        if self._busy:
            return False
        files = self.scan()
        if not files:
            return False
        self.execute_script(files[0])
        return True

    def run(self, stop_event=None):
        """主循環，直到 stop_event 被設置或收到 KeyboardInterrupt。"""
        self.logger.info("CommandExecutor main loop started.")
        try:
            while stop_event is None or not stop_event.is_set():
                self.run_once()
                # 簡單的輪詢休眠
                import time
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            self.logger.info("Received KeyboardInterrupt, stopping.")
