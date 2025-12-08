# setup_certificates.py
import os
import ssl
import certifi
import requests
from pathlib import Path

def setup_sber_certificates():
    """Настройка SSL сертификатов для Render/GitHub"""
    
    cert_dir = Path("certs")
    cert_dir.mkdir(exist_ok=True)
    
    cert_paths = [
        cert_dir / "sber_root.crt",
        Path("sber_root.crt"),
        Path("/etc/ssl/certs/ca-certificates.crt"),  # Системные
        certifi.where()  # Certifi
    ]
    
    print("🔐 Настройка SSL сертификатов для Render...")
    
    # 1. Пробуем скачать сертификат Sber
    try:
        print("1. Скачиваю сертификат Sber...")
        response = requests.get(
            "https://storage.yandexcloud.net/cloud-certs/CA.pem",
            timeout=10
        )
        
        if response.status_code == 200:
            with open(cert_dir / "sber_root.crt", "w") as f:
                f.write(response.text)
            print(f"✅ Сертификат сохранён: {cert_dir/'sber_root.crt'}")
        else:
            print(f"⚠️ Не удалось скачать (статус: {response.status_code})")
    except Exception as e:
        print(f"⚠️ Ошибка скачивания: {e}")
    
    # 2. Используем системные сертификаты + certifi
    print("2. Использую системные сертификаты + certifi...")
    
    # Создаем объединённый файл сертификатов
    combined_cert = cert_dir / "combined_ca.crt"
    
    with open(combined_cert, "wb") as outfile:
        # Добавляем certifi сертификаты
        with open(certifi.where(), "rb") as certifi_file:
            outfile.write(certifi_file.read())
        
        # Добавляем Sber сертификат если есть
        sber_cert = cert_dir / "sber_root.crt"
        if sber_cert.exists():
            with open(sber_cert, "rb") as sber_file:
                outfile.write(b"\n")  # Разделитель
                outfile.write(sber_file.read())
    
    print(f"✅ Объединённый файл создан: {combined_cert}")
    
    # 3. Создаем SSL контекст
    ssl_context = ssl.create_default_context()
    ssl_context.load_verify_locations(cafile=str(combined_cert))
    
    # 4. Устанавливаем переменную окружения для SSL
    os.environ['SSL_CERT_FILE'] = str(combined_cert)
    os.environ['REQUESTS_CA_BUNDLE'] = str(combined_cert)
    
    print(f"✅ SSL переменные установлены:")
    print(f"   SSL_CERT_FILE={os.environ.get('SSL_CERT_FILE')}")
    print(f"   REQUESTS_CA_BUNDLE={os.environ.get('REQUESTS_CA_BUNDLE')}")
    
    return combined_cert

if __name__ == "__main__":
    setup_sber_certificates()
