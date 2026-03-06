@echo off
:: Creates a Windows Task Scheduler task that runs AutoTrader every weekday at 07:00
set TASKNAME=AutoTrader_Daily
set SCRIPTDIR=%~dp0
set BATFILE=%SCRIPTDIR%run_daily.bat

echo Creating scheduled task: %TASKNAME%
schtasks /create /tn "%TASKNAME%" /tr ""%BATFILE%"" /sc WEEKLY /d MON,TUE,WED,THU,FRI /st 07:00 /f

if %ERRORLEVEL%==0 (
    echo Task created successfully.
    echo It will run every weekday at 07:00.
) else (
    echo Failed to create task. Try running as Administrator.
)
pause
