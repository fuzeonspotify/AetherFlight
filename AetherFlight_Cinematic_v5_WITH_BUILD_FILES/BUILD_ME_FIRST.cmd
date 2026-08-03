@echo off
setlocal
title Aether Flight - Build Editor Module

set "AETHER_ENGINE="
if exist "C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" set "AETHER_ENGINE=C:\Program Files\Epic Games\UE_5.8"

if not defined AETHER_ENGINE (
    echo Unreal Engine 5.8 was not found at:
    echo C:\Program Files\Epic Games\UE_5.8
    echo.
    echo If UE 5.8 is installed elsewhere, edit AETHER_ENGINE in this file.
    pause
    exit /b 2
)

echo Using %AETHER_ENGINE%
echo Building AetherFlightEditor Win64 Development...
echo Complete output: Build_AetherFlight.log
echo.

call "%AETHER_ENGINE%\Engine\Build\BatchFiles\Build.bat" AetherFlightEditor Win64 Development -Project="%~dp0AetherFlight.uproject" -WaitMutex -NoHotReloadFromIDE > "%~dp0Build_AetherFlight.log" 2>&1
set "AETHER_RESULT=%ERRORLEVEL%"

type "%~dp0Build_AetherFlight.log"
echo.
if "%AETHER_RESULT%"=="0" (
    echo BUILD SUCCEEDED. Open AetherFlight.uproject.
) else (
    echo BUILD FAILED. Upload Build_AetherFlight.log.
)
echo.
pause
exit /b %AETHER_RESULT%
