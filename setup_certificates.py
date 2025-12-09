# setup_certificates.py - УПРОЩЕННЫЙ
import os
import certifi
from pathlib import Path

def setup_sber_certificates():
    """Настройка SSL сертификатов для Render"""
    print("🔐 Настройка SSL сертификатов...")
    
    certifi_path = certifi.where()
    print(f"✅ Использую certifi: {certifi_path}")
    
    os.environ['SSL_CERT_FILE'] = certifi_path
    os.environ['REQUESTS_CA_BUNDLE'] = certifi_path
    
    return certifi_path

if __name__ == "__main__":
    setup_sber_certificates()
