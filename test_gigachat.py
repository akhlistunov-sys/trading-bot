#!/usr/bin/env python3
# test_gigachat.py - Тестирование GigaChat API

import os
import asyncio
import sys
from dotenv import load_dotenv

# Добавляем путь к текущей директории
sys.path.append('.')

load_dotenv()

async def test_gigachat():
    """Тестирование GigaChat API"""
    
    print("🧪 Тестирование GigaChat API")
    print("=" * 50)
    
    # Проверяем переменные окружения
    client_id = os.getenv('GIGACHAT_CLIENT_ID')
    client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("❌ Не найдены GIGACHAT_CLIENT_ID или GIGACHAT_CLIENT_SECRET")
        print("   Установите в .env файле или переменных окружения")
        return False
    
    print(f"✅ Client ID: {client_id[:8]}...")
    print(f"✅ Client Secret: {client_secret[:8]}...")
    
    # Тестируем напрямую через curl (если установлен)
    import subprocess
    import uuid
    
    print("\n1. Тестирование OAuth токена через curl...")
    
    auth_base64 = f"{client_id}:{client_secret}"
    import base64
    auth_encoded = base64.b64encode(auth_base64.encode()).decode()
    
    curl_command = [
        'curl', '-X', 'POST',
        'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
        '-H', 'Content-Type: application/x-www-form-urlencoded',
        '-H', f'Accept: application/json',
        '-H', f'RqUID: {str(uuid.uuid4())}',
        '-H', f'Authorization: Basic {auth_encoded}',
        '-d', 'scope=GIGACHAT_API_PERS',
        '--silent',
        '--show-error'
    ]
    
    try:
        result = subprocess.run(curl_command, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Curl запрос выполнен успешно")
            
            try:
                import json
                response = json.loads(result.stdout)
                if 'access_token' in response:
                    print(f"✅ Токен получен: {response['access_token'][:20]}...")
                    print(f"✅ Срок действия: {response.get('expires_at', 'не указан')}")
                    return True
                else:
                    print(f"❌ Ответ без токена: {response}")
            except:
                print(f"❌ Невалидный JSON: {result.stdout[:100]}")
        else:
            print(f"❌ Ошибка curl (код {result.returncode}):")
            print(f"   Стандартный вывод: {result.stdout[:100]}")
            print(f"   Ошибка: {result.stderr[:100]}")
            
    except subprocess.TimeoutExpired:
        print("❌ Таймаут запроса")
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
    
    return False

async def test_with_ssl_cert():
    """Тестирование с разными SSL опциями"""
    
    print("\n2. Тестирование SSL сертификатов...")
    
    cert_paths = [
        'certs/sber_root.crt',
        'sber_root.crt',
        '/etc/ssl/certs/sberbank-root-ca.pem',
        '/usr/local/share/ca-certificates/sberbank.crt'
    ]
    
    for cert_path in cert_paths:
        if os.path.exists(cert_path):
            print(f"✅ Найден сертификат: {cert_path}")
            return cert_path
    
    print("❌ Сертификат Sber не найден")
    print("   Запустите: bash install_certificates.sh")
    return None

if __name__ == "__main__":
    print("🚀 Тестирование GigaChat API")
    print("=" * 50)
    
    # Проверяем сертификаты
    cert_path = asyncio.run(test_with_ssl_cert())
    
    # Тестируем OAuth
    success = asyncio.run(test_gigachat())
    
    if success:
        print("\n🎉 GigaChat API должен работать!")
        print("\nСледующие шаги:")
        print("1. Запустите приложение: python app.py")
        print("2. Перейдите на: http://localhost:10000")
        print("3. Нажмите 'Тест GigaChat' на странице тестирования провайдеров")
    else:
        print("\n🔧 Для устранения проблем:")
        print("1. Проверьте Client ID и Client Secret")
        print("2. Установите сертификат: bash install_certificates.sh")
        print("3. Попробуйте временно отключить SSL проверку для тестов")
        print("\nВременное решение (ТОЛЬКО ДЛЯ ТЕСТОВ):")
        print("   В nlp_engine.py измените verify=ssl_context на verify=False")
