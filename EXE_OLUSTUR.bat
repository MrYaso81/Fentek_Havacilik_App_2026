@echo off
setlocal
cd /d "%~dp0"
title Fentek Havacilik EXE Olusturucu

echo [1/3] Derleme araci kontrol ediliyor...
py -3.12 -m pip install --disable-pip-version-check --target ".build_tools" "pyinstaller>=6.11,<7"
if errorlevel 1 goto :error

echo [2/3] Windows uygulamasi olusturuluyor...
set "PYTHONPATH=%CD%\.build_tools"
py -3.12 -m PyInstaller --clean --noconfirm FentekHavacilik.spec
if errorlevel 1 goto :error

echo [3/3] Tamamlandi.
echo Uygulama: dist\Fentek Havacilik\Fentek Havacilik.exe
echo Klasoru baska bir Windows bilgisayara tamamen kopyalayin.
pause
exit /b 0

:error
echo EXE olusturulamadi. Yukaridaki hata mesajini kontrol edin.
pause
exit /b 1
