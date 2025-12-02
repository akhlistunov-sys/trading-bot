# check_connections.py
import os
import asyncio
import httpx
from tinkoff.invest import Client
from dotenv import load_dotenv

load_dotenv()

async def check_all():
    print("🔍 Проверка всех подключений...")
    
    # 1. Проверка Tinkoff API
    print("\n1. Проверяем Tinkoff API...")
    tinkoff_token = os.getenv("TINKOFF_API_TOKEN")
    try:
        with Client(tinkoff_token) as client:
            accounts = client.users.get_accounts()
            print(f"   ✅ Успех! Доступно счетов: {len(accounts.accounts)}")
    except Exception as e:
        print(f"   ❌ Ошибка Tinkoff: {e}")
    
    # 2. Проверка OpenRouter API
    print("\n2. Проверяем OpenRouter API...")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    
    async with httpx.AsyncClient() as client:
        # Проверка баланса
        try:
            balance_resp = await client.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {openrouter_key}"},
                timeout=10.0
            )
            if balance_resp.status_code == 200:
                data = balance_resp.json()
                credits = data.get("data", {}).get("credits", 0)
                print(f"   ✅ Баланс: {credits} кредитов")
            else:
                print(f"   ❌ Ошибка проверки баланса: {balance_resp.status_code}")
        except Exception as e:
            print(f"   ❌ Ошибка запроса баланса: {e}")
        
        # Тестовый запрос к модели
        print("\n3. Тест DeepSeek R1T Chimera...")
        try:
            test_resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "tngtech/deepseek-r1t-chimera:free",
                    "messages": [{"role": "user", "content": "Ответь числом: 2+2=?"}],
                    "max_tokens": 10
                },
                timeout=30.0
            )
            
            if test_resp.status_code == 200:
                result = test_resp.json()
                answer = result["choices"][0]["message"]["content"]
                print(f"   ✅ Модель отвечает: {answer}")
            else:
                print(f"   ❌ Ошибка модели: {test_resp.status_code}")
                print(f"   Ответ: {test_resp.text[:200]}")
                
        except Exception as e:
            print(f"   ❌ Ошибка запроса: {e}")

if __name__ == "__main__":
    asyncio.run(check_all())
