#!/bin/bash
# install_certificates.sh

echo "🔐 Установка сертификатов Sberbank для GigaChat API"

# Создаем директорию для сертификатов
mkdir -p certs
cd certs

echo "1. Скачивание корневого сертификата Sberbank..."
curl -s -o sber_root.crt https://storage.yandexcloud.net/cloud-certs/CA.pem

if [ $? -eq 0 ]; then
    echo "✅ Сертификат скачан"
    
    # Проверяем содержимое
    if [ -s sber_root.crt ]; then
        echo "📄 Содержимое сертификата:"
        head -5 sber_root.crt
        
        # Копируем в системные сертификаты (требует sudo)
        echo "2. Копирование в системную директорию..."
        sudo cp sber_root.crt /usr/local/share/ca-certificates/sberbank.crt
        sudo update-ca-certificates
        
        echo "✅ Сертификаты обновлены"
    else
        echo "❌ Файл сертификата пустой"
    fi
else
    echo "❌ Не удалось скачать сертификат"
    
    echo "3. Попытка получить сертификат через openssl..."
    openssl s_client -connect ngw.devices.sberbank.ru:9443 -showcerts < /dev/null 2>/dev/null | \
        sed -n '/BEGIN/,/END/p' > sber_chain.pem
    
    if [ -s sber_chain.pem ]; then
        echo "✅ Сертификат получен через openssl"
        cp sber_chain.pem sber_root.crt
    fi
fi

echo "📁 Сертификаты находятся в: $(pwd)/"
ls -la *.crt *.pem 2>/dev/null || echo "Файлы не найдены"
