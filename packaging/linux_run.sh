#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -x "./ffmpeg/ffmpeg" ]; then
  export FFMPEG_PATH="$PWD/ffmpeg/ffmpeg"
fi

chmod +x ./camera_collector 2>/dev/null || true
exec ./camera_collector "$@"
