# nlp_engine.py - STRICT RELEVANCE CHECK
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

class GigaChatAuth:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id.strip('"').strip("'")
        self.client_secret = client_secret.strip('"').strip("'")
        self.access_token = None
        self.token_expiry = 0
        
    def _get_auth_header(self):
        if len(self.client_secret) > 50 and '=' in self.client_secret:
            return f'Basic {self.client_secret}'
        auth = f"{self.client_id}:{self.client_secret}"
        return f'Basic {base64.b64encode(auth.encode()).decode()}'

    async def get_token(self):
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'RqUID': str(uuid.uuid4()), 'Authorization': self._get_auth_header()}
        try:
            async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
                resp = await client.post(url, headers=headers, data={'scope': 'GIGACHAT_API_PERS'})
                if resp.status_code == 200:
                    data = resp.json()
                    self.access_token = data['access_token']
                    self.token_expiry = (data['expires_at'] / 1000)
                    return self.access_token
        except: pass
        return None

class NlpEngine:
    def __init__(self):
        self.gc_id = os.getenv('GIGACHAT_CLIENT_ID', '')
        self.gc_secret = os.getenv('GIGACHAT_CLIENT_SECRET', '')
        self.auth = None
        self.sem = asyncio.Semaphore(1)
        if self.gc_id: self.auth = GigaChatAuth(self.gc_id, self.gc_secret)

    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        if not self.auth: return None
        async with self.sem: return await self._call_gigachat(news_item)

    def _create_prompt(self, news_item: Dict) -> str:
        # Убрал примеры, добавил строгое ограничение по теме
        return f"""Ты строгий финансовый аналитик MOEX (Мосбиржа).
Новость: {news_item.get('title', '')} {news_item.get('description', '')[:300]}

Задача:
1. Если новость НЕ про российские публичные компании (Сбер, Газпром, Яндекс, Лукойл и т.д.) -> ВЕРНИ "tickers": [].
2. Если новость про иностранные рынки, сушилки, химикаты, погоду -> ВЕРНИ "tickers": [].
3. Если новость важная для РФ рынка -> укажи тикер и sentiment.

Ответь ТОЛЬКО JSON:
{{
    "tickers": ["SBER"], 
    "sentiment": "positive",
    "impact_score": 8,
    "confidence": 0.9,
    "is_tradable": true,
    "reason": "Краткая причина"
}}"""

    async def _call_gigachat(self, news_item):
        token = await self.auth.get_token()
        if not token: return None
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Authorization': f'Bearer {token}', 'X-Request-ID': str(uuid.uuid4())}
        payload = {"model": "GigaChat", "messages": [{"role": "user", "content": self._create_prompt(news_item)}], "temperature": 0.1}
        try:
            async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200: return self._parse(resp.json()['choices'][0]['message']['content'], news_item)
        except: pass
        return None

    def _parse(self, text, item):
        try:
            text = re.sub(r'```json|```', '', text).strip()
            if '{' in text: text = text[text.find('{'):text.rfind('}')+1]
            data = json.loads(text)
            tickers = [t.upper() for t in data.get('tickers', []) if isinstance(t, str)]
            return {
                'ticker': tickers[0] if tickers else None,
                'sentiment': data.get('sentiment', 'neutral'),
                'impact_score': data.get('impact_score', 5),
                'confidence': data.get('confidence', 0.5),
                'reason': data.get('reason', 'AI'),
                'is_tradable': data.get('is_tradable', False) and bool(tickers),
                'ai_provider': 'GigaChat',
                'title': item.get('title', '')
            }
        except: return None
