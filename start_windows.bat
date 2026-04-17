@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo 未检测到 Python，请先安装 Python 3。
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo 未检测到 ffmpeg，无法保存 MP4。
  echo 请安装 ffmpeg，或后续使用打包版内置 ffmpeg。
  pause
  exit /b 1
)

python webcam_web.py --host 127.0.0.1 --port 8765 %*
pause
