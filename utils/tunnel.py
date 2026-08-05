"""Tunnel watchdog: keeps the reverse-SSH tunnel alive.

Restart path: scheduled task TgBotTunnel if it exists, else the .vbs launcher
directly (so a machine without the task is still covered). Either way the
keeper script refuses to start a second instance, so a spurious start is a
no-op instead of two ssh clients fighting over remote port 18080.
"""
import asyncio
import logging
import os
import subprocess

logger = logging.getLogger("bot.tunnel")

TASK_NAME = "TgBotTunnel"
CHECK_INTERVAL = 60  # seconds
VBS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "start_tunnel_hidden.vbs",
)


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


def _start_tunnel(use_task: bool):
    if use_task:
        subprocess.run(["schtasks", "/run", "/tn", TASK_NAME], capture_output=True, timeout=15)
    elif os.path.isfile(VBS_PATH):
        subprocess.run(["wscript.exe", VBS_PATH], capture_output=True, timeout=15)
    else:
        logger.error("No tunnel task and no %s — cannot restart tunnel", VBS_PATH)


async def tunnel_watchdog():
    """Background loop: if reverse-SSH tunnel is down, start it again."""
    use_task = await asyncio.to_thread(_task_exists)
    logger.info("Tunnel watchdog active (%s, every %ds)",
                f"task {TASK_NAME}" if use_task else "vbs launcher", CHECK_INTERVAL)
    while True:
        try:
            if not await asyncio.to_thread(_ssh_running):
                logger.warning("Tunnel ssh not running — restarting tunnel")
                await asyncio.to_thread(_start_tunnel, use_task)
        except Exception as e:
            logger.error("Tunnel watchdog error: %s", e)
        await asyncio.sleep(CHECK_INTERVAL)
