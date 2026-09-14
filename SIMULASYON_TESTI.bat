@echo off
cd /d "%~dp0"
echo Fentek Havacilik - Cube simulasyon kabul testi
echo.
py -3.12 simulation_acceptance.py
if errorlevel 1 goto fail
py -3.12 -m unittest discover -s . -p "test_*.py"
if errorlevel 1 goto fail
py -3.12 check_operations.py
if errorlevel 1 goto fail
echo.
echo TUM TANIMLI SIMULASYON TESTLERI BASARILI
pause
exit /b 0
:fail
echo.
echo TEST BASARISIZ - Yukaridaki hatayi kontrol edin.
pause
exit /b 1
