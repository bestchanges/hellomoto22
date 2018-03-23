@echo off
rem set PYTHONUNBUFFERED=1

timeout 10

:START
echo start bestminer
epython\python bestminer-client.py
IF ERRORLEVEL 200 GOTO INSTALL_UPDATE
echo Exit from miner
echo Going to RE-start
TIMEOUT 5
GOTO START
GOTO END

:INSTALL_UPDATE
echo install update
robocopy /e update . /xf config.txt
echo install update finish. Going to restart
GOTO START


:END
echo end
pause
