#!/bin/bash
# render_build.sh - Build Command для Render.com

echo "🚀 Начало сборки на Render..."

# 1. Устанавливаем Python зависимости
pip install -r requirements.txt

# 2. Настраиваем SSL сертификаты
python setup_certificates.py

# 3. Создаем .env файл из переменных окружения Render
if [ -n "$GIGACHAT_CLIENT_ID" ]; then
    echo "GIGACHAT_CLIENT_ID=$GIGACHAT_CLIENT_ID" > .env
    echo "GIGACHAT_CLIENT_SECRET=$GIGACHAT_CLIENT_SECRET" >> .env
    echo "GIGACHAT_SCOPE=$GIGACHAT_SCOPE" >> .env
    echo "OPENROUTER_API_TOKEN=$OPENROUTER_API_TOKEN" >> .env
    echo "FINAM_API_TOKEN=$FINAM_API_TOKEN" >> .env
    
    # Trading parameters
    echo "RISK_PER_TRADE=${RISK_PER_TRADE:-1.5}" >> .env
    echo "STOP_LOSS_PCT=${STOP_LOSS_PCT:-1.5}" >> .env
    echo "TAKE_PROFIT_PCT=${TAKE_PROFIT_PCT:-3.0}" >> .env
    echo "MIN_CONFIDENCE=${MIN_CONFIDENCE:-0.6}" >> .env
    echo "MIN_IMPACT_SCORE=${MIN_IMPACT_SCORE:-5}" >> .env
    echo "CHECK_INTERVAL_MINUTES=${CHECK_INTERVAL_MINUTES:-15}" >> .env
    echo "TRADING_MODE=${TRADING_MODE:-AGGRESSIVE_TEST}" >> .env
    
    echo "✅ .env файл создан"
else
    echo "⚠️ Переменные окружения не настроены"
fi

echo "✅ Сборка завершена!"
