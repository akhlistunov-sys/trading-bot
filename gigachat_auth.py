import os
import aiohttp
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class GigaChatAuth:
    """Класс для авторизации в GigaChat API через Client ID"""
    
    def __init__(self):
        self.client_id = os.getenv("GIGACHAT_CLIENT_ID")  # 019ac4e1-9416-7c5b-8722-fd5b09d85848
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.access_token = None
        self.token_expiry = None
        
    async def get_access_token(self) -> Optional[str]:
        """Получение access token через OAuth 2.0"""
        if self.access_token and self.token_expiry:
            import time
            if time.time() < self.token_expiry - 60:  # Токен ещё жив (минус 60 секунд запаса)
                return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': '6f0b1291-c7f3-434c-9a4c-8344d4f34364',  # Можно оставить или сгенерировать новый
            'Authorization': f'Basic {self.client_id}'  # Basic авторизация с Client ID
        }
        
        payload = {
            'scope': self.scope
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                # ВАЖНО: отключаем SSL проверку для этого endpoint
                async with session.post(url, headers=headers, data=payload, ssl=False) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.access_token = data.get('access_token')
                        expires_in = data.get('expires_in', 1800)  # 30 минут по умолчанию
                        
                        import time
                        self.token_expiry = time.time() + expires_in
                        
                        logger.info("✅ GigaChat: получен новый access token")
                        return self.access_token
                    else:
                        logger.error(f"❌ GigaChat auth ошибка: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Ошибка получения токена GigaChat: {e}")
            return None
    
    async def make_request(self, prompt_data: Dict) -> Optional[Dict]:
        """Выполнение запроса к GigaChat API"""
        access_token = await self.get_access_token()
        if not access_token:
            return None
        
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=prompt_data, ssl=False) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 401:
                        logger.warning("⚠️ GigaChat токен истёк, обновляю...")
                        self.access_token = None  # Сбрасываем токен
                        return await self.make_request(prompt_data)  # Рекурсивно пробуем с новым токеном
                    else:
                        logger.error(f"❌ GigaChat API ошибка: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Ошибка запроса к GigaChat: {e}")
            return None
