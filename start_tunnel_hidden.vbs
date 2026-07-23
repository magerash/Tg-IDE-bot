' Launches the tunnel keeper with NO window at all (0 = SW_HIDE).
' Used by scheduled task "TgBotTunnel" instead of calling powershell directly —
' powershell -WindowStyle Hidden still flashes a console; wscript never does.
CreateObject("Wscript.Shell").Run _
  "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File ""C:\Projects\Tg-IDE-bot\start_tunnel_vps.ps1""", 0, False
