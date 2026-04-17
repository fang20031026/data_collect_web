@echo off
setlocal
cd /d "%~dp0"

python -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo 未检测到 PyInstaller，正在安装...
  python -m pip install -r requirements-build.txt
  if errorlevel 1 (
    echo PyInstaller 安装失败。
    pause
    exit /b 1
  )
)

if not exist third_party\ffmpeg\windows\ffmpeg.exe (
  echo.
  echo 警告：未找到 third_party\ffmpeg\windows\ffmpeg.exe
  echo 构建仍会继续，但生成的程序需要 Windows 系统 PATH 中已有 ffmpeg。
  echo 为了真正无门槛使用，请把 Windows 版 ffmpeg.exe 放到：
  echo third_party\ffmpeg\windows\ffmpeg.exe
  echo.
)

python -m PyInstaller --clean --distpath dist\windows --workpath build\windows packaging\camera_collector_windows.spec
if errorlevel 1 (
  echo 构建失败。
  pause
  exit /b 1
)

if not exist release mkdir release
if exist release\camera_collector_windows rmdir /s /q release\camera_collector_windows
mkdir release\camera_collector_windows
copy dist\windows\camera_collector.exe release\camera_collector_windows\camera_collector.exe >nul
copy README_WINDOWS.txt release\camera_collector_windows\README_WINDOWS.txt >nul

echo.
echo 构建完成：
echo release\camera_collector_windows\camera_collector.exe
echo.
echo 采集人员双击 camera_collector.exe 即可打开浏览器界面。
pause
