@echo off
rem Run the VRN server at boot on Windows (as SYSTEM, no logon needed).
rem Put vrnserver.exe and vrnserver.yaml in this folder first, then run this file as Administrator.
set DIR=%~dp0
if not exist "%DIR%logs" mkdir "%DIR%logs"
> "%DIR%run.cmd" echo @echo off
>> "%DIR%run.cmd" echo cd /d "%DIR%"
>> "%DIR%run.cmd" echo vrnserver.exe -config vrnserver.yaml ^>^> logs\vrnserver.log 2^>^&1
schtasks /Create /F /TN VRNServer /SC ONSTART /RU SYSTEM /RL HIGHEST /TR "\"%DIR%run.cmd\""
netsh advfirewall firewall add rule name="VRN server" dir=in action=allow protocol=TCP localport=8443
schtasks /Run /TN VRNServer
echo VRN server installed. Logs: %DIR%logs\vrnserver.log   Status: http://127.0.0.1:8090/status
