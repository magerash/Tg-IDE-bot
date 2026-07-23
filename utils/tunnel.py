"""Tunnel watchdog: keeps the TgBotTunnel scheduled task (reverse SSH) alive."""
import asyncio
import logging
import subprocess

logger = logging.getLogger("bot.tunnel")

TASK_NAME = "TgBotTunnel"
CHECK_INTERVAL = 60  # seconds


def _task_exists() -> bool:
    proc = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME],
        capture_output=True, timeout=15,
    )
    return proc.returncode == 0


def _ssh_running() -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq ssh.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, timeout=15,
    ).stdout
    return "ssh.exe" in out


def _start_task():
    subprocess.run(["schtasks", "/run", "/tn", TASK_NAME], capture_output=True, timeout=15)


async def tunnel_watchdog():
    """Background loop: if reverse-SSH tunnel is down, restart its scheduled task."""
    if not await asyncio.to_thread(_task_exists):
        logger.info("Task %s not found — tunnel watchdog disabled", TASK_NAME)
        return
    logger.info("Tunnel watchdog active (task %s, every %ds)", TASK_NAME, CHECK_INTERVAL)
    while True:
        try:
            if not await asyncio.to_thread(_ssh_running):
                logger.warning("Tunnel ssh not running — starting task %s", TASK_NAME)
                await asyncio.to_thread(_start_task)
        except Exception as e:
            logger.error("Tunnel watchdog error: %s", e)
        await asyncio.sleep(CHECK_INTERVAL)
