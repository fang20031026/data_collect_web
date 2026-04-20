@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python is required.
  pause
  exit /b 1
)

python -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo [INFO] PyInstaller not found, installing from requirements-build.txt ...
  python -m pip install -r requirements-build.txt
  if errorlevel 1 (
    echo [ERROR] Failed to install build dependencies.
    pause
    exit /b 1
  )
)

if not exist third_party\ffmpeg\windows\ffmpeg.exe (
  echo [ERROR] Missing third_party\ffmpeg\windows\ffmpeg.exe
  echo         Please place Windows x64 ffmpeg.exe in that location first.
  pause
  exit /b 1
)

python -m PyInstaller --clean --distpath dist\windows --workpath build\windows packaging\camera_collector_windows.spec
if errorlevel 1 (
  echo [ERROR] Build failed.
  pause
  exit /b 1
)

if not exist release mkdir release
if exist release\camera_collector_windows rmdir /s /q release\camera_collector_windows
mkdir release\camera_collector_windows
mkdir release\camera_collector_windows\ffmpeg

copy /y dist\windows\camera_collector.exe release\camera_collector_windows\camera_collector.exe >nul
if errorlevel 1 (
  echo [ERROR] Failed to copy camera_collector.exe
  pause
  exit /b 1
)

copy /y third_party\ffmpeg\windows\ffmpeg.exe release\camera_collector_windows\ffmpeg\ffmpeg.exe >nul
if errorlevel 1 (
  echo [ERROR] Failed to copy ffmpeg.exe
  pause
  exit /b 1
)

if exist third_party\ffmpeg\windows\ffprobe.exe (
  copy /y third_party\ffmpeg\windows\ffprobe.exe release\camera_collector_windows\ffmpeg\ffprobe.exe >nul
)

copy /y README_WINDOWS.txt release\camera_collector_windows\README_WINDOWS.txt >nul
if errorlevel 1 (
  echo [ERROR] Failed to copy README_WINDOWS.txt
  pause
  exit /b 1
)

if exist start_windows.bat (
  copy /y start_windows.bat release\camera_collector_windows\start_windows.bat >nul
)

echo.
echo [OK] Build finished:
echo      release\camera_collector_windows\camera_collector.exe
echo.
echo Distribute the folder as a zip package.
pause
