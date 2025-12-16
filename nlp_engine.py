# nlp_engine.py - GIGACHAT (OLD ROBUST LOGIC) + GEMINI PRO
import logging
import json
import os
import asyncio
import httpx
import time
import uuid
import base64
import re
from typing import Dict, Optional
import google.generativeai as genai

logger = logging.getLogger(__name__)

# ==================== AUTH CLASS (ИЗ СТАРОЙ ВЕРСИИ) ====================
class GigaChatAuth:
    """Авторизация GigaChat (Ручная сборка заголовка, без SSL)"""
    
    def __init__(self, client_id: str, client_secret: str, scope: str = "GIGACHAT_API_PERS"):
        self.client_id = client_id
        # Чистим секрет от кавычек жестко
        self.client_secret = client_secret.strip('"').strip("'")
        self.scope = scope
        self.access_token = None
        self.token_expiry = 0
        
    async def get_access_token(self) -> Optional[str]:
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        rquid = str(uuid.uuid4())
        
        # Ручная сборка заголовка Basic Auth (Самый надежный метод)
        auth_str = f"{self.client_id}:{self.client_secret}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': rquid,
            'Authorization': f'Basic {b64_auth}'
        }
        
        try:
            # verify=False критически важен для Render
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, headers=headers, data={'scope': self.scope})
                
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get('access_token')
                    # Конвертируем expires_at из мс в секунды
                    expires_at = data.get('expires_at', 0)
                    self.token_expiry = (expires_at / 1000) if expires_at > 2000000000000 else (time.time() + 1800)
                    logger.info("✅ GigaChat: Token Refreshed")
                    return self.access_token
                else:
                    logger.error(f"❌ GigaChat Auth Fail {response.status_code}: {response.text[:50]}")
                    return None
        except Exception as e:
            logger.error(f"❌ GigaChat Connection Error: {e}")
            return None

# ==================== ГЛАВНЫЙ ДВИЖОК ====================
class NlpEngine:
    def __init__(self):
        # 1. GigaChat Setup
        self.gc_id = os.getenv('GIGACHAT_CLIENT_ID', '')
        self.gc_secret = os.getenv('GIGACHAT_CLIENT_SECRET', '')
        
        self.gigachat_available = bool(self.gc_id and self.gc_secret)
        self.gigachat_auth = None
        
        if self.gigachat_available:
            self.gigachat_auth = GigaChatAuth(self.gc_id, self.gc_secret)
            # Семафор как в старой версии (1 поток)
            self.gc_semaphore = asyncio.Semaphore(1)
            logger.info("🟢 GigaChat: ENABLED (Legacy Mode)")
        
        # 2. Gemini Setup (PRO Model)
        self.gemini_key = os.getenv('GEMINI_API_KEY', '').strip('"')
        self.gemini_available = False
        
        if self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key)
                # Меняем на gemini-pro (стабильная версия)
                self.gemini_model = genai.GenerativeModel('gemini-pro')
                self.gemini_available = True
                logger.info("🟡 Gemini: Configured (Model: gemini-pro)")
            except Exception as e:
                logger.error(f"❌ Gemini Setup Fail: {e}")

    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        # Приоритет: GigaChat -> Gemini
        
        if self.gigachat_available:
            async with self.gc_semaphore:
                res = await self._analyze_gigachat(news_item)
                if res: return res
                
        if self.gemini_available:
            return await self._analyze_gemini(news_item)
            
        return None

    def _create_prompt(self, news_item: Dict) -> str:
        # Тот самый промпт из старой версии
        title = news_item.get('title', '')
        desc = news_item.get('description', '') or ''
        
        return f"""Ты финансовый аналитик MOEX. Проанализируй новость.
Новость: {title} {desc[:200]}

ВАЖНО: Найди тикеры MOEX (SBER, GAZP, LKOH, VTBR, YNDX, и т.д.).
Если новость позитивная для компании - sentiment: positive.
Если негативная - sentiment: negative.

Верни JSON:
{{
    "tickers": ["SBER"],
    "sentiment": "positive",
    "impact_score": 7,
    "confidence": 0.9,
    "is_tradable": true,
    "reason": "Коротко причина"
}}

Если тикеров нет - is_tradable: false. Верни только JSON."""

    async def _analyze_gigachat(self, news_item: Dict) -> Optional[Dict]:
        token = await self.gigachat_auth.get_access_token()
        if not token: return None
        
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'X-Request-ID': str(uuid.uuid4())
        }
        
        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": self._create_prompt(news_item)}],
            "temperature": 0.1
        }
        
        try:
            async with httpx.AsyncClient(timeout=20.0, verify=False) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    return self._parse_json(content, news_item, 'GigaChat')
                else:
                    logger.warning(f"⚠️ GigaChat Error {resp.status_code}")
        except Exception as e:
            logger.error(f"❌ GigaChat Request Error: {e}")
        return None

    async def _analyze_gemini(self, news_item: Dict) -> Optional[Dict]:
        try:
            # Gemini Pro не поддерживает json_mode нативно в старых либах, просим текстом
            resp = await self.gemini_model.generate_content_async(
                self._create_prompt(news_item)
            )
            return self._parse_json(resp.text, news_item, 'Gemini')
        except Exception as e:
            logger.warning(f"⚠️ Gemini Error: {e}")
        return None

    def _parse_json(self, raw_text: str, news_item: Dict, provider: str) -> Optional[Dict]:
        try:
            # Очистка от маркдауна
            clean_text = re.sub(r'```json|```', '', raw_text).strip()
            # Поиск JSON скобок
            start = clean_text.find('{')
            end = clean_text.rfind('}') + 1
            if start != -1 and end != 0:
                clean_text = clean_text[start:end]
                
            data = json.loads(clean_text)
            
            tickers = [t.upper() for t in data.get('tickers', []) if isinstance(t, str)]
            
            return {
                'ticker': tickers[0] if tickers else None,
                'tickers': tickers,
                'sentiment': data.get('sentiment', 'neutral'),
                'impact_score': data.get('impact_score', 5),
                'confidence': data.get('confidence', 0.5),
                'reason': data.get('reason', 'AI Analysis'),
                'is_tradable': data.get('is_tradable', False) and bool(tickers),
                'ai_provider': provider,
                'title': news_item.get('title', '')
            }
        except Exception:
            # logger.debug(f"JSON Parse Error ({provider}): {raw_text[:50]}...")
            return None
