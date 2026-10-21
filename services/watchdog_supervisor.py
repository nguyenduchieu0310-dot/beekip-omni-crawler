import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from core.config import BASE_DIR, DATA_DIR, LOGS_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / "watchdog.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("beekip.watchdog")

PID_FILE = DATA_DIR / "omni_agent.pid"

class WatchdogSupervisor:
    """Supervises the Omni-Agent scheduler daemon, providing self-healing auto-restart within 10s."""

    def __init__(self):
        self.running = True
        self.process: subprocess.Popen = None
        self.python_exe = sys.executable

    def start_scheduler_process(self) -> subprocess.Popen:
        """Spawn the scheduler daemon process."""
        cmd = [self.python_exe, "-m", "services.omni_scheduler", "--daemon"]
        logger.info("Spawning Omni-Agent process: %s", " ".join(cmd))

        proc = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        logger.info("Omni-Agent process spawned with PID: %s", proc.pid)
        return proc

    def stop_child_process(self) -> None:
        """Gracefully terminate child process."""
        if self.process and self.process.poll() is None:
            logger.info("Terminating child process PID %s...", self.process.pid)
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)

    def run(self) -> None:
        logger.info("Watchdog Supervisor started. Monitoring Omni-Agent 24/7...")
        self.process = self.start_scheduler_process()

        def handle_signal(sig, frame):
            logger.info("Shutdown signal received. Stopping supervisor...")
            self.running = False
            self.stop_child_process()
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self.running:
            try:
                ret_code = self.process.poll()
                if ret_code is not None:
                    logger.warning(
                        "Omni-Agent process exited unexpectedly with code %s! Self-healing in 10s...",
                        ret_code
                    )
                    time.sleep(10)
                    if self.running:
                        self.process = self.start_scheduler_process()
                time.sleep(5)
            except Exception as e:
                logger.error("Supervisor loop error: %s", e)
                time.sleep(5)

if __name__ == "__main__":
    supervisor = WatchdogSupervisor()
    supervisor.run()
