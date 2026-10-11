#!/bin/bash
cd "$(dirname "$0")"

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "Запуск прогрева аккаунтов..."
python3 -u main.py "$@"
