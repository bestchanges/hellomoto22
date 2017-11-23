@echo off

:START
echo start bestminer
python_win\scripts\python bestminer-client.py
IF ERRORLEVEL 200 GOTO INSTALL_UPDATE
echo Normal exit
GOTO END

:INSTALL_UPDATE
echo install update
robocopy /e update .
echo install update finish. Going to restart
GOTO START


:END
echo end
pause
