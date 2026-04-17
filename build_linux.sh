#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! python3 -m PyInstaller --version >/dev/null 2>&1; then
  echo "未检测到 PyInstaller。安装命令：python3 -m pip install pyinstaller"
  exit 1
fi

python3 -m PyInstaller --clean --distpath dist/linux --workpath build/linux packaging/camera_collector.spec
echo "构建完成：dist/linux/camera_collector"
