@echo off

echo Starting AllMiner

:: timeout /t 5

if exist "id.ini" for /f "tokens=*" %%A in ('type "id.ini"') do set %%A
if exist "config.ini" for /f "tokens=*" %%A in ('type "config.ini"') do set %%A

set first_run=Y

:loop
echo UPDATE CONFIG  ...
powershell.exe -ExecutionPolicy Bypass -File Config.ps1 -Verb RunAs
echo UPDATE CONFIG DONE ...

if "%first_run%"=="Y" (
	set first_run=N
	call scripts\runMiner.bat
) else (
    echo TODO check if miner is up
)

echo CHECK TASKS ...
powershell.exe -ExecutionPolicy Bypass -File GetTask.ps1 -Verb RunAs
echo CHECK TASKS DONE ...
if exist "task.ini" for /f "tokens=*" %%A in ('type "task.ini"') do set %%A
if NOT "%anyminer_task%" == "" (
	echo GOT TASK %anyminer_task%
)

if "%anyminer_task%" == "restart_miner" (
	call scripts\runMiner.bat
) else if "%anyminer_task%" == "reboot" (
	call scripts\reboot.bat
) else (
	echo NO TASK
) 

timeout 10
goto :loop