@echo off
echo Adding Windows Firewall inbound rule (requires Administrator)...
echo Rule: allow TCP ports 8000-8200 inbound for phone access on the same LAN.
netsh advfirewall firewall add rule name="LanFileShare" dir=in action=allow protocol=TCP localport=8000-8200
if errorlevel 1 (
    echo Failed. Right-click this script and choose "Run as administrator", then retry.
) else (
    echo Success. Phones on the same LAN can now reach the shared ports.
)
pause
