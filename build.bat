@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Build CounterTranslate

:: === Settings ===
set APP_NAME=CounterTranslate
set APP_EXE_NAME=CounterTranslate_app
set LAUNCHER_SCRIPT=launcher.py
set ENTRY_POINT=app\main.py
set LANG_SRC_DIR=app\lang
set DIST_DIR=dist\%APP_NAME%
set CURRENT_DIR=%DIST_DIR%\current
set NUITKA_BUILD_DIR=.nuitka_build

echo.
echo Building %APP_NAME% with Nuitka...
echo.

:: --------------------------------------------------------------------------------
:: Version: use BUILD_VERSION env var if set (e.g. from CI), otherwise generate from date/time
if defined BUILD_VERSION (
    set _v=!BUILD_VERSION:~0,1!
    if "!_v!"=="v" set BUILD_VERSION=!BUILD_VERSION:~1!
    set CURRENT_VERSION=!BUILD_VERSION!
) else (
    for /f %%A in ('powershell -NoProfile -Command "Get-Date -Format \"yyMMddHHmm\""') do set BUILDNUMBER=%%A
    set CURRENT_VERSION=0.13.%BUILDNUMBER%
)

:: Windows file version always generated from current time (4 parts, each <= 65535)
for /f %%A in ('powershell -NoProfile -Command "Get-Date -Format \"yyMM.ddmm\""') do set WIN_VERSION=0.13.%%A

echo CURRENT_VERSION = %CURRENT_VERSION%
echo WIN_VERSION     = %WIN_VERSION%
:: --------------------------------------------------------------------------------

:: Write version module (imported by app at runtime)
echo CURRENT_VERSION = "%CURRENT_VERSION%" > app\_build_version.py

:: Convert icon.png → icon.ico
python -c "from PIL import Image; img = Image.open('app/icon.png'); img.save('app/icon.ico')"
if %errorlevel% neq 0 (
    echo Icon conversion failed! Make sure Pillow is installed.
    if not defined CI pause
    exit /b %errorlevel%
)

:: Clean old builds
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
rmdir /s /q %NUITKA_BUILD_DIR% 2>nul

:: --------------------------------------------------------------------------------
:: Build main app as standalone into current\ subfolder
echo.
echo Building main app...
python -m nuitka ^
 --standalone ^
 --windows-console-mode=disable ^
 --output-filename=%APP_EXE_NAME%.exe ^
 --output-dir=%NUITKA_BUILD_DIR% ^
 --enable-plugin=tk-inter ^
 --windows-icon-from-ico=app\icon.ico ^
 --windows-company-name="Crankerer" ^
 --windows-product-name="CounterTranslate" ^
 --windows-file-version=%WIN_VERSION% ^
 --windows-product-version=%WIN_VERSION% ^
 --assume-yes-for-downloads ^
 %ENTRY_POINT%

if %errorlevel% neq 0 (
    echo Build failed!
    if not defined CI pause
    exit /b %errorlevel%
)

:: Move Nuitka output (main.dist) to dist\APP_NAME\current
mkdir "%DIST_DIR%" 2>nul
move "%NUITKA_BUILD_DIR%\main.dist" "%CURRENT_DIR%"

:: --------------------------------------------------------------------------------
:: Build launcher as standalone
echo.
echo Building launcher...
python -m nuitka ^
 --standalone ^
 --windows-console-mode=disable ^
 --output-filename=%APP_NAME%.exe ^
 --output-dir=%NUITKA_BUILD_DIR% ^
 --windows-icon-from-ico=app\icon.ico ^
 --windows-company-name="Crankerer" ^
 --windows-product-name="CounterTranslate" ^
 --windows-file-version=%WIN_VERSION% ^
 --windows-product-version=%WIN_VERSION% ^
 --assume-yes-for-downloads ^
 %LAUNCHER_SCRIPT%

if %errorlevel% neq 0 (
    echo Launcher build failed!
    if not defined CI pause
    exit /b %errorlevel%
)

:: Copy launcher standalone contents into root of dist folder
xcopy /Y /E /I "%NUITKA_BUILD_DIR%\launcher.dist\*" "%DIST_DIR%\" >nul

:: --------------------------------------------------------------------------------
:: Copy language files into current\lang
echo.
echo Copying language files to %CURRENT_DIR%\lang ...
if not exist "%CURRENT_DIR%\lang" mkdir "%CURRENT_DIR%\lang"
copy "%LANG_SRC_DIR%\lang_*.json" "%CURRENT_DIR%\lang" >nul

:: Write VERSION.txt into root of dist folder
echo %CURRENT_VERSION% > "%DIST_DIR%\VERSION.txt"

:: Cleanup Nuitka temp build folder
rmdir /s /q %NUITKA_BUILD_DIR% 2>nul

echo.
echo Build completed successfully!
echo Output: %DIST_DIR%
echo Version: %CURRENT_VERSION%
echo.
echo Root:
dir /b "%DIST_DIR%"
echo current\:
dir /b "%CURRENT_DIR%"
echo.

endlocal
