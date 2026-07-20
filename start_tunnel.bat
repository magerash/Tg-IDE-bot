@echo off
REM Quick Cloudflare tunnel for the Mini App / web dashboard.
REM URL changes on every run — copy it to WEBAPP_URL in .env and restart bot.
REM For a stable URL use a named tunnel: see materials\documentation\miniapp-setup.md
cloudflared tunnel --url http://localhost:8080
