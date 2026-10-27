@echo off
title Job Hunt Bot
echo ========================================================
echo  Running Job Hunt Bot...
echo ========================================================
cd /d " %~dp0\
python pipeline.py %*
echo.
echo ========================================================
echo Execution Complete. Press any key to exit.
echo ========================================================
pause
