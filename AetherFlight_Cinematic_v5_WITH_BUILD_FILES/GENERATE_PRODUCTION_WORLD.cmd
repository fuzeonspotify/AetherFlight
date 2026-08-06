@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher "py" was not found. Install Python 3.11 or newer first.
  pause
  exit /b 1
)

py -c "import numpy, PIL, scipy" >nul 2>nul
if errorlevel 1 (
  echo Installing the terrain generator dependencies...
  py -m pip install --user numpy pillow scipy
  if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
  )
)

echo Generating the 4033 terrain, seven weightmaps, textures, and hydrology plan...
py Tools\generate_production_landscape.py
if errorlevel 1 (
  echo PRODUCTION WORLD GENERATION FAILED.
  pause
  exit /b 1
)

echo.
echo PRODUCTION WORLD SOURCE GENERATED SUCCESSFULLY.
echo Next open Unreal and follow PRODUCTION_WORLD_V2_SETUP.md.
pause
endlocal
