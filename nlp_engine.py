# nlp_engine.py - GIGACHAT ONLY (CLEAN LOGS)
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

logger = logging.getLogger(__name__)

class GigaChatAuth:
    """Умная авторизация GigaChat"""
    def __init__(self, client_id: str, client_secret: str, scope: str = "GIGACHAT_API_PERS"):
        self.client_id = client_id.strip('"').strip("'")
        self.client_secret = client_secret.strip('"').strip("'")
        self.scope = scope
        self.access_token = None
        self.token_expiry = 0
        
    def _get_auth_header_value(self) -> str:
        if len(self.client_secret) > 50 and (self.client_secret.endswith('=') or 'MDE5' in self.client_secret):
            return f'Basic {self.client_secret}'
        else:
            auth_str = f"{self.client_id}:{self.client_secret}"
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            return f'Basic {b64_auth}'

    async def get_access_token(self) -> Optional[str]:
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        rquid = str(uuid.uuid4())
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': rquid,
            'Authorization': self._get_auth_header_value()
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, headers=headers, data={'scope': self.scope})
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get('access_token')
                    expires_at = data.get('expires_at', 0)
                    self.token_expiry = (expires_at / 1000) if expires_at > 2000000000000 else (time.time() + 1800)
                    return self.access_token
        except Exception:
            return None
        return None

class NlpEngine:
    def __init__(self):
        self.gc_id = os.getenv('GIGACHAT_CLIENT_ID', '')
        self.gc_secret = os.getenv('GIGACHAT_CLIENT_SECRET', '')
        
        self.gigachat_available = bool(self.gc_id and self.gc_secret)
        self.gigachat_auth = None
        
        if self.gigachat_available:
            self.gigachat_auth = GigaChatAuth(self.gc_id, self.gc_secret)
            self.gc_semaphore = asyncio.Semaphore(1)
            logger.info("🟢 GigaChat: ONLINE (Solo Mode)")
        else:
            logger.warning("⚠️ GigaChat: Not Configured")

        # Gemini отключен специально, чтобы не засорять логи
        self.gemini_available = False

    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        if self.gigachat_available:
            async with self.gc_semaphore:
                return await self._analyze_gigachat(news_item)
        return None

    def _create_prompt(self, news_item: Dict) -> str:
        title = news_item.get('title', '')
        desc = news_item.get('description', '') or ''
        
        return f"""Ты аналитик MOEX.
Новость: {title} {desc[:400]}

Задача:
1. Найди тикеры (SBER, GAZP, LKOH, YNDX, VTBR, MGNT).
2. Оцени влияние: Positive/Negative/Neutral.
3. Оцени силу (1-10).

Верни JSON:
{{
    "tickers": ["SBER"],
    "sentiment": "positive",
    "impact_score": 8,
    "confidence": 0.9,
    "is_tradable": true,
    "reason": "Краткая причина"
}}"""

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
        except Exception:
            pass
        return None

    def _parse_json(self, raw_text: str, news_item: Dict, provider: str) -> Optional[Dict]:
        try:
            clean_text = re.sub(r'```json|```', '', raw_text).strip()
            start = clean_text.find('{')
            end = clean_text.rfind('}') + 1
            if start != -1 and end != 0: clean_text = clean_text[start:end]
            
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
        except: return None
