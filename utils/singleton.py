"""Single-instance guard: kill other bot.py processes before binding the web port.

Needed because web Restart Bot uses os.execv (detached process keeps running) while
start_bot.bat can spawn a second instance — loser crash-loops on port 10048.

Uses psutil (in-process Win32 API calls), NOT taskkill/powershell subprocesses:
on 2026-08-19 a zombie instance survived a 40-minute crash loop because process
*creation* on the box was hanging — `taskkill /F` timed out after 10s and the
WMI enumeration via powershell after 20s, every restart, while an API-level
Stop-Process from an already-running shell killed the same pid instantly.
"""
import logging
import os

import psutil

logger = logging.getLogger("bot.singleton")


def kill_other_instances():
    """Terminate any other python process running bot.py (they are always ours)."""
    my_pid = os.getpid()
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if p.info["pid"] == my_pid:
                continue
            if not (p.info["name"] or "").lower().startswith("python"):
                continue
            cmd = " ".join(p.info["cmdline"] or [])
            if "bot.py" not in cmd:
                continue
            logger.warning("Killing other bot instance pid %s: %s",
                           p.info["pid"], cmd[:100])
            p.kill()                     # TerminateProcess — no child process spawned
            p.wait(timeout=5)            # port is freed only when it's really gone
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except psutil.TimeoutExpired:
            logger.error("Instance pid %s did not die within 5s — web port may "
                         "still be busy", p.info["pid"])
        except Exception as e:
            logger.error("kill_other_instances error on pid %s: %s",
                         p.info.get("pid"), e)
