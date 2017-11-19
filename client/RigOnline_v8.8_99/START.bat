@echo off
title RigOnline

:: пауза перед началом работы, чтобы сеть прогрузилась
timeout /t 30

:: перехода в каталог приложения
cd /d %~dp0

echo.
echo START

:loop
call RigOnline.bat
goto :loop