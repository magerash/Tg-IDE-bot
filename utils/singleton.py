"""Single-instance guard: kill other bot.py processes before binding the web port.

Needed because web Restart Bot uses os.execv (detached process keeps running) while
start_bot.bat can spawn a second instance — loser crash-loops on port 10048.
"""
import json
import logging
import os
import subprocess

logger = logging.getLogger("bot.singleton")


def kill_other_instances():
    """Terminate any other python process running bot.py (they are always ours)."""
    my_pid = os.getpid()
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" "
             "| Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
        if not out:
            return
        procs = json.loads(out)
        if isinstance(procs, dict):
            procs = [procs]
        for p in procs:
            pid = p.get("ProcessId")
            cmd = p.get("CommandLine") or ""
            if pid and pid != my_pid and "bot.py" in cmd:
                logger.warning("Killing other bot instance pid %s: %s", pid, cmd[:100])
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, timeout=10)
    except Exception as e:
        logger.error("kill_other_instances error: %s", e)
