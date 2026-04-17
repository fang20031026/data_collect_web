#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "未检测到 python3，请先安装 Python 3。"
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "未检测到 ffmpeg，无法保存 MP4。"
  echo "Ubuntu/Debian 可运行：sudo apt install ffmpeg"
  exit 1
fi

if ! command -v zenity >/dev/null 2>&1 && ! command -v kdialog >/dev/null 2>&1; then
  echo "未检测到 zenity/kdialog，将尝试使用 tkinter 打开目录选择窗口。"
fi

python3 webcam_web.py --host 127.0.0.1 --port 8765 "$@"
