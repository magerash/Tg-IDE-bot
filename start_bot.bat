@echo off
title TG-IDE-Bot Auto-Restart
:loop
echo Starting bot...
python bot.py
echo Bot exited. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
