@echo off

echo.
echo ---------------------------
echo --- %date% %time:~0,8% ---
echo ---------------------------

set error=0

:: если первый вызов
if "%restart%"=="" (

	:: берем настройки
	if exist "config.ini" for /f "tokens=*" %%A in ('type "config.ini"') do set %%A
	if exist "rig.ini" for /f "tokens=*" %%A in ('type "rig.ini"') do set %%A
	if exist "secret.ini" for /f "tokens=*" %%A in ('type "secret.ini"') do set %%A

	set restart=1

	echo.
	echo ---------------------------
	echo SEND RESTART TO RIGONLINE.RU ...

) else (

	:: исключение видеокарты
	set exclude=99
	if exist "exclude.ini" for /f "tokens=*" %%A in ('type "exclude.ini"') do set %%A

	:: майнер
	set miner_name=0
	if exist "miner.ini" for /f "tokens=*" %%A in ('type "miner.ini"') do set %%A
	
	:: проверка майнера
	echo.
	echo ---------------------------
	echo CHECK MINER ...
	for /f "tokens=*" %%A in ('powershell.exe -ExecutionPolicy Bypass -File Miner.ps1 -Verb RunAs') do echo %%A

	:: берем настройки
	if exist "rig.ini" for /f "tokens=*" %%A in ('type "rig.ini"') do set %%A
	if exist "secret.ini" for /f "tokens=*" %%A in ('type "secret.ini"') do set %%A

	:: обновление конфига
	echo.
	echo ---------------------------
	echo UPDATE CONFIG FROM RIGONLINE.RU ...
	for /f "tokens=*" %%A in ('powershell.exe -ExecutionPolicy Bypass -File Config.ps1 -Verb RunAs') do echo %%A

	:: берем настройки
	if exist "config.ini" for /f "tokens=*" %%A in ('type "config.ini"') do set %%A

	echo.
	echo ---------------------------
	echo GET DATA AND SEND TO RIGONLINE.RU ...

)

:: вызываем скрипт powershell для сбора и отправки данных
for /f "tokens=*" %%A in ('powershell.exe -ExecutionPolicy Bypass -File RigOnline.ps1 -Verb RunAs') do echo %%A

:: если первый вызов
if %restart%==1 (

	set restart=0

) else (

	:: обновление сервиса
	echo.
	echo ---------------------------
	echo CHECK UPDATE FROM RIGONLINE.RU ...
	for /f "tokens=*" %%A in ('powershell.exe -ExecutionPolicy Bypass -File Update.ps1 -Verb RunAs') do echo %%A

	:: проверка заданий
	echo.
	echo ---------------------------
	echo CHECK TASKS FROM RIGONLINE.RU ...
	for /f "tokens=*" %%A in ('powershell.exe -ExecutionPolicy Bypass -File Tasks.ps1 -Verb RunAs') do echo %%A
	
	:: пауза
	echo.
	if exist "p.txt" (
		echo PAUSE 10
		timeout /t 10
	) else (
		echo PAUSE %pause%
		timeout /t %pause%
	)

)
