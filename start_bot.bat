@echo off
REM ===========================================================================
REM  TG-IDE-Bot — single entry point: tunnel first, then the bot.
REM  Put THIS file in shell:startup (or a scheduled task) and everything comes
REM  up after a reboot. Safe to run twice: the keeper self-guards against
REM  duplicates (start_tunnel_vps.ps1) and utils/singleton.py kills stale bots.
REM ===========================================================================
title TG-IDE-Bot
cd /d "%~dp0"

echo [1/2] Tunnel keeper (hidden, reverse SSH to VPS)...
REM wscript, not powershell: -WindowStyle Hidden still flashes a console.
REM Returns immediately — the keeper runs detached and reconnects on its own.
wscript.exe "%~dp0start_tunnel_hidden.vbs"

echo [2/2] Bot (auto-restart loop)...
REM "Restart Bot" from web/Telegram re-execs python inside this same process
REM (os.execv), so it never falls out of this loop.
:loop
python bot.py
echo Bot exited. Restarting in 5 seconds...  (close this window to stop)
timeout /t 5 /nobreak >nul
goto loop
