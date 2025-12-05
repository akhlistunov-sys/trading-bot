from dotenv import load_dotenv
import os

load_dotenv()

print("=" * 60)
print("🔧 ТЕСТ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ RENDER")
print("=" * 60)

# Проверяем OpenRouter
openrouter_key = os.getenv("OPENROUTER_API_TOKEN")
if openrouter_key:
    print(f"✅ OPENROUTER_API_TOKEN: НАЙДЕН ({len(openrouter_key)} символов)")
    print(f"   Начинается с: {openrouter_key[:10]}...")
else:
    print("❌ OPENROUTER_API_TOKEN: НЕ НАЙДЕН")

# Проверяем Tinkoff
tinkoff_key = os.getenv("TINKOFF_API_TOKEN")
if tinkoff_key:
    print(f"✅ TINKOFF_API_TOKEN: НАЙДЕН ({len(tinkoff_key)} символов)")
    print(f"   Начинается с: {tinkoff_key[:10]}...")
else:
    print("❌ TINKOFF_API_TOKEN: НЕ НАЙДЕН")

# Другие переменные
print(f"⚡ TRADING_MODE: {os.getenv('TRADING_MODE', 'AGGRESSIVE_TEST')}")
print(f"⏰ CHECK_INTERVAL: {os.getenv('CHECK_INTERVAL_MINUTES', '15')} минут")

print("=" * 60)
print("📋 ВСЕ ПЕРЕМЕННЫЕ С 'API', 'TOKEN', 'KEY':")
for key, value in sorted(os.environ.items()):
    if any(word in key.upper() for word in ['API', 'TOKEN', 'KEY', 'MODE', 'INTERVAL']):
        masked = value[:4] + '*' * max(0, len(value)-8) + value[-4:] if len(value) > 8 else '****'
        print(f"  {key}: {masked}")

print("=" * 60)
