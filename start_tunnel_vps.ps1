# Persistent reverse SSH tunnel: VPS localhost:18080 -> this PC localhost:8080
# Caddy on VPS proxies https://bot.magerash.com:8443 -> localhost:18080
# Auto-reconnects every 5s on drop. Started by start_bot.bat, by the scheduled
# task "TgBotTunnel", and by the bot's watchdog (utils/tunnel.py).

# --- Single-instance guard --------------------------------------------------
# All three launch paths can fire on the same boot. Two keepers means two ssh
# clients fighting over remote port 18080: the loser dies on
# ExitOnForwardFailure and retries every 5s, and the tunnel flaps. Whoever
# starts first wins; later keepers exit here.
# $PID exclusion matters — this process's own command line contains the pattern.
$others = @(Get-CimInstance Win32_Process -Filter "Name like 'powershell%'" |
    Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -match 'start_tunnel_vps' })
if ($others.Count -gt 0) {
    Write-Host "Tunnel keeper already running (pid $($others[0].ProcessId)) - exiting."
    exit 0
}

while ($true) {
    ssh -N -R 18080:127.0.0.1:8080 `
        -o ServerAliveInterval=30 `
        -o ServerAliveCountMax=3 `
        -o ExitOnForwardFailure=yes `
        -o StrictHostKeyChecking=accept-new `
        root@45.150.33.106
    Start-Sleep -Seconds 5
}
