#!/usr/bin/env bash
# sync/dump.bin(가린 모음집 글자)이 바뀌면 GitHub Actions가 실행: 모음집 글자 -> characters.json
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
[ -f "$ROOT/sync/dump.bin" ] || { echo "sync/dump.bin 없음: 할 일 없음"; exit 0; }
W=$(mktemp -d)
python3 "$ROOT/tools/unseal.py" "$ROOT/sync/dump.bin" "$W/dump.txt"
python3 "$ROOT/tools/split.py" "$W/dump.txt" "$W"
python3 "$ROOT/tools/parse.py" "$W"
python3 "$ROOT/tools/match.py" "$W" > "$W/match.log"
python3 "$ROOT/tools/xlsx.py" "$W" "$W/summary.xlsx"
python3 "$ROOT/tools/merge.py" "$W" "$ROOT"
