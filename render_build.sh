#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Build started..."

# 1. Обновляем pip до последней версии
pip install --upgrade pip

# 2. Устанавливаем зависимости
pip install -r requirements.txt

echo "Build complete."

# 1. Обновляем pip и устанавливаем зависимости
python -m pip install --upgrade pip
pip install setuptools wheel

# 2. Устанавливаем Python зависимости
pip install -r requirements.txt

# 3. Создаем .env файл
echo "🔧 Создание .env файла..."
cat > .env << EOF
# Python
PYTHONPATH=.

# GigaChat
GIGACHAT_CLIENT_ID=${GIGACHAT_CLIENT_ID:-}
GIGACHAT_CLIENT_SECRET=${GIGACHAT_CLIENT_SECRET:-}
GIGACHAT_SCOPE=${GIGACHAT_SCOPE:-GIGACHAT_API_PERS}

# Gemini
GEMINI_API_KEY=${GEMINI_API_KEY:-}

# Tinkoff (опционально)
TINKOFF_API_TOKEN=${TINKOFF_API_TOKEN:-}

# OpenRouter (опционально)
OPENROUTER_API_TOKEN=${OPENROUTER_API_TOKEN:-}

# Finam
FINAM_API_TOKEN=${FINAM_API_TOKEN:-}
FINAM_CLIENT_ID=${FINAM_CLIENT_ID:-621971R9IP3}

# Trading
RISK_PER_TRADE=${RISK_PER_TRADE:-1.5}
STOP_LOSS_PCT=${STOP_LOSS_PCT:-1.5}
TAKE_PROFIT_PCT=${TAKE_PROFIT_PCT:-3.0}
MIN_CONFIDENCE=${MIN_CONFIDENCE:-0.6}
MIN_IMPACT_SCORE=${MIN_IMPACT_SCORE:-5}
CHECK_INTERVAL_MINUTES=${CHECK_INTERVAL_MINUTES:-15}
TRADING_MODE=${TRADING_MODE:-AGGRESSIVE_TEST}
PORT=${PORT:-10000}
EOF

echo "✅ Сборка завершена!"
