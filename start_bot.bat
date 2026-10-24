@echo off
chcp 65001 > nul
title Telegram Media & Shazam Bot
cd /d "%~dp0"
echo ======================================================
echo       Telegram Media & Shazam Bot Ishga Tushmoqda...
echo ======================================================
echo.
".\.venv\Scripts\python.exe" main.py
pause
