from dotenv import load_dotenv
import os

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")

print("✅ Ключ загружен!") if key else print("❌ Ключ не найден")
print(f"Длина: {len(key) if key else 0} символов")
