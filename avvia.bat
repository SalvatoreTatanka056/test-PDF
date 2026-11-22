@echo off
title PDF Sign & Edit Studio
cd /d "%~dp0"
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Si e verificato un errore durante l'avvio del programma.
    pause
)
