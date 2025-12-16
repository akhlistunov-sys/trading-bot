# nlp_engine.py - GIGACHAT PRIMARY (QUEUED) + GEMINI BACKUP
import logging
import json
import os
import asyncio
import httpx
import time
import uuid
import re
from typing import Dict, Optional
import google.generativeai as genai

logger = logging.getLogger(__name__)

class NlpEngine:
    """
    NLP Движок:
    1. GigaChat (Primary) - строго 1 запрос за раз (Free Tier limitation).
    2. Gemini (Backup) - если GigaChat недоступен.
    """
    
    def __init__(self):
        self.stats = {'gigachat_requests': 0, 'gemini_requests': 0, 'errors': 0}
        
        # --- GIGACHAT SETUP (PRIMARY) ---
        # Очищаем от возможных кавычек в .env
        self.gigachat_id = os.getenv('GIGACHAT_CLIENT_ID', '').strip('"').strip("'")
        self.gigachat_secret = os.getenv('GIGACHAT_CLIENT_SECRET', '').strip('"').strip("'")
        self.gigachat_scope = os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')
        
        self.gigachat_token = None
        self.token_expires_at = 0
        # ВАЖНО: GigaChat Free ограничен 1 потоком. Используем Lock для очереди.
        self.gigachat_lock = asyncio.Lock() 
        
        self.gigachat_available = bool(self.gigachat_id and self.gigachat_secret)
        if self.gigachat_available:
            logger.info("🟢 GigaChat: PRIMARY (Configured with Queue Lock)")
        else:
            logger.warning("Qq GigaChat: Not Configured")

        # --- GEMINI SETUP (BACKUP) ---
        self.gemini_key = os.getenv('GEMINI_API_KEY', '').strip('"').strip("'")
        self.gemini_available = False
        self.gemini_model = None
        
        if self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                self.gemini_available = True
                logger.info("🟡 Gemini: BACKUP (Standby)")
            except Exception as e:
                logger.error(f"❌ Gemini Setup Error: {e}")

        self.enabled = self.gigachat_available or self.gemini_available

    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        if not self.enabled: 
            return None
        
        # 1. GigaChat (Primary)
        if self.gigachat_available:
            try:
                # Используем lock, чтобы не спамить (1 запрос за раз)
                async with self.gigachat_lock:
                    self.stats['gigachat_requests'] += 1
                    result = await self._analyze_with_gigachat(news_item)
                    if result:
                        return result
                    # Если GigaChat вернул None (ошибка), идем к Gemini
            except Exception as e:
                logger.warning(f"⚠️ GigaChat Fail: {e}")
                self.stats['errors'] += 1

        # 2. Gemini (Backup)
        if self.gemini_available:
            try:
                logger.info("🔄 Switching to Backup (Gemini)...")
                self.stats['gemini_requests'] += 1
                return await self._analyze_with_gemini(news_item)
            except Exception as e:
                logger.error(f"❌ Gemini Fail: {e}")
                self.stats['errors'] += 1
        
        return None

    def _create_prompt(self, news_item: Dict) -> str:
        # Укорачиваем текст, чтобы влезть в лимиты токенов
        text = f"{news_item.get('title', '')} {news_item.get('description', '')}"[:1000]
        
        return f"""
        Ты финансовый аналитик MOEX. Проанализируй новость.
        Текст: {text}
        
        Ответь ТОЛЬКО валидным JSON без Markdown. Формат:
        {{
            "tickers": ["SBER"], (только ликвидные акции РФ, если нет - пустой список)
            "sentiment": "positive" | "negative" | "neutral",
            "impact_score": (от 1 до 10),
            "confidence": (от 0.0 до 1.0),
            "is_tradable": true/false, (true только если новость важная и есть тикер)
            "reason": "Краткое обоснование на русском (макс 10 слов)"
        }}
        """

    async def _analyze_with_gigachat(self, news_item: Dict) -> Optional[Dict]:
        token = await self._get_gigachat_token()
        if not token: 
            logger.warning("⚠️ No GigaChat Token")
            return None
        
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            'Authorization': f'Bearer {token}', 
            'Content-Type': 'application/json',
            'X-Request-ID': str(uuid.uuid4())
        }
        
        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": self._create_prompt(news_item)}],
            "temperature": 0.1, # Минимальная креативность для строгого JSON
            "max_tokens": 300
        }
        
        # Отключаем проверку SSL для российских сертификатов (частая проблема на Render)
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            
            if resp.status_code == 200:
                try:
                    content = resp.json()['choices'][0]['message']['content']
                    # Очистка от ```json ... ```
                    content = re.sub(r'```json|```', '', content).strip()
                    data = json.loads(content)
                    
                    if data.get('tickers') and data.get('is_tradable'):
                        logger.info(f"🤖 GigaChat Signal: {data['tickers']} ({data['sentiment']})")
                    return self._format_result(data, news_item, 'gigachat')
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ GigaChat JSON Error. Raw: {content[:50]}...")
            else:
                logger.warning(f"⚠️ GigaChat HTTP {resp.status_code}: {resp.text[:100]}")
        return None

    async def _get_gigachat_token(self):
        # Если токен есть и не протух (с запасом 60 сек)
        if self.gigachat_token and time.time() < self.token_expires_at - 60:
            return self.gigachat_token
            
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4()),
            'Authorization': f'Basic {self._get_auth_header()}'
        }
        data = {'scope': self.gigachat_scope}
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                resp = await client.post(url, headers=headers, data=data)
                if resp.status_code == 200:
                    json_data = resp.json()
                    self.gigachat_token = json_data['access_token']
                    # expires_at приходит в миллисекундах
                    self.token_expires_at = json_data['expires_at'] / 1000 
                    logger.info("🔑 GigaChat Token Updated")
                    return self.gigachat_token
                else:
                    logger.error(f"❌ Auth Fail: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"❌ Token Request Error: {e}")
            
        return None

    def _get_auth_header(self):
        import base64
        auth_str = f"{self.gigachat_id}:{self.gigachat_secret}"
        return base64.b64encode(auth_str.encode()).decode()

    async def _analyze_with_gemini(self, news_item: Dict) -> Optional[Dict]:
        prompt = self._create_prompt(news_item)
        try:
            response = await self.gemini_model.generate_content_async(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            if response.text:
                data = json.loads(response.text)
                return self._format_result(data, news_item, 'gemini')
        except Exception as e:
            logger.warning(f"⚠️ Gemini processing error: {e}")
        return None

    def _format_result(self, data: Dict, news_item: Dict, provider: str) -> Dict:
        tickers = [t.upper() for t in data.get('tickers', []) if isinstance(t, str)]
        return {
            'ticker': tickers[0] if tickers else None,
            'tickers': tickers,
            'sentiment': data.get('sentiment', 'neutral'),
            'impact_score': data.get('impact_score', 5),
            'confidence': data.get('confidence', 0.5),
            'reason': data.get('reason', 'AI Analysis'),
            'is_tradable': data.get('is_tradable', False),
            'ai_provider': provider,
            'news_id': news_item.get('id'),
            'event_type': 'news_analysis'
        }
