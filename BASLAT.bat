@echo off
cd /d "%~dp0"
py -3.12 flight_pro.py
if errorlevel 1 pause
