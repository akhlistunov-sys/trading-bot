from dotenv import load_dotenv
import os

load_dotenv()

# ИСПРАВЛЕНО: Используем OPENROUTER_API_TOKEN как в Render
key = os.getenv("OPENROUTER_API_TOKEN")  # ← ИСПРАВЛЕНО

print("=" * 50)
print("🔧 ТЕСТ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ")
print("=" * 50)

if key:
    print(f"✅ OPENROUTER_API_TOKEN найден!")
    print(f"📏 Длина: {len(key)} символов")
    print(f"🔑 Первые 10 символов: {key[:10]}...")
else:
    print("❌ OPENROUTER_API_TOKEN не найден!")
    print("⚠️ Проверьте наличие переменной в Render Environment Variables")

tinkoff_token = os.getenv("TINKOFF_API_TOKEN")
if tinkoff_token:
    print(f"✅ TINKOFF_API_TOKEN найден ({len(tinkoff_token)} символов)")
else:
    print("❌ TINKOFF_API_TOKEN не найден!")

trading_mode = os.getenv("TRADING_MODE", "AGGRESSIVE_TEST")
print(f"⚡ TRADING_MODE: {trading_mode}")

check_interval = os.getenv("CHECK_INTERVAL_MINUTES", "15")
print(f"⏰ CHECK_INTERVAL_MINUTES: {check_interval}")

print("=" * 50)
print("🧪 ВСЕГО ПЕРЕМЕННЫХ ОКРУЖЕНИЯ:")
for key, value in os.environ.items():
    if 'TOKEN' in key or 'KEY' in key or 'MODE' in key:
        masked_value = value[:4] + '*' * (len(value) - 8) + value[-4:] if len(value) > 8 else '****'
        print(f"  {key}: {masked_value}")
print("=" * 50)
