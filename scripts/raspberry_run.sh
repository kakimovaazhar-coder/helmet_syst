#!/usr/bin/env bash
set -e

SERVER_URL="${1:-http://172.20.10.8:8000}"
CAMERA_BACKEND="${2:-opencv}"
shift || true
shift || true

cd "$(dirname "$0")/../yolo"
source .venv/bin/activate

export HELMET_SERVER_URL="$SERVER_URL"
python pi_detector.py --server "$SERVER_URL" --camera-backend "$CAMERA_BACKEND" "$@"
