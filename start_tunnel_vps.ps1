# Persistent reverse SSH tunnel: VPS localhost:18080 -> this PC localhost:8080
# Caddy on VPS proxies https://bot.magerash.com:8443 -> localhost:18080
# Auto-reconnects every 5s on drop. Registered as scheduled task "TgBotTunnel".
while ($true) {
    ssh -N -R 18080:127.0.0.1:8080 `
        -o ServerAliveInterval=30 `
        -o ServerAliveCountMax=3 `
        -o ExitOnForwardFailure=yes `
        -o StrictHostKeyChecking=accept-new `
        root@45.150.33.106
    Start-Sleep -Seconds 5
}
