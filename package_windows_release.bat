@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Package prebuilt Windows executable into release zip for one-click startup.
REM Run this script on Windows after build_windows.bat succeeds.

set "DIST_DIR=release\camera_collector_windows"
set "EXE_PATH=%DIST_DIR%\camera_collector.exe"
set "OUT_ZIP=release\camera_collector_windows.zip"
set "DOC_SRC=README_WINDOWS.txt"
set "DOC_DST=%DIST_DIR%\README_WINDOWS.txt"

if not exist "%EXE_PATH%" (
  echo [ERROR] 未找到 %EXE_PATH%
  echo 请先在 Windows 上运行 build_windows.bat 生成可执行文件。
  exit /b 1
)

if exist "%DOC_SRC%" (
  copy /Y "%DOC_SRC%" "%DOC_DST%" >nul
)

where powershell >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 未检测到 PowerShell，无法创建 zip。
  exit /b 1
)

if exist "%OUT_ZIP%" del /f /q "%OUT_ZIP%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%DIST_DIR%\\*' -DestinationPath '%OUT_ZIP%' -Force"
if errorlevel 1 (
  echo [ERROR] 打包失败。
  exit /b 1
)

echo [OK] 已生成 %OUT_ZIP%
echo [OK] 采集人员解压后双击 camera_collector.exe 即可启动。
exit /b 0
