# nlp_engine.py - DUAL ENGINE (GEMINI PRIMARY + GIGACHAT BACKUP)
import logging
import json
import os
import asyncio
import httpx
import time
import uuid
import re
from datetime import datetime
from typing import Dict, Optional
import google.generativeai as genai

logger = logging.getLogger(__name__)

class NlpEngine:
    """Двойной NLP движок: Gemini (Primary) -> GigaChat (Backup)"""
    
    def __init__(self):
        self.stats = {
            'gemini_requests': 0,
            'gigachat_requests': 0,
            'errors': 0,
            'current_model': 'None'
        }
        
        # 1. Настройка Google Gemini
        self.gemini_key = os.getenv('GEMINI_API_KEY')
        self.gemini_available = False
        
        if self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key)
                # Используем Flash 1.5 - она самая быстрая и дешевая (бесплатная)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                self.gemini_available = True
                self.stats['current_model'] = 'Gemini 1.5 Flash'
                logger.info("✅ Gemini 1.5 Flash подключен (Primary)")
            except Exception as e:
                logger.error(f"❌ Ошибка настройки Gemini: {e}")
        
        # 2. Настройка GigaChat (Backup)
        self.gigachat_key = os.getenv('GIGACHAT_CLIENT_SECRET')
        self.gigachat_available = bool(self.gigachat_key)
        self.gigachat_token = None
        self.token_expires_at = 0
        
        if self.gigachat_available:
            logger.info("✅ GigaChat подключен (Backup)")
        
        self.enabled = self.gemini_available or self.gigachat_available

    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """Анализ новости: Сначала Gemini, если сбой - GigaChat"""
        if not self.enabled:
            return None
            
        # Попытка 1: Google Gemini
        if self.gemini_available:
            try:
                self.stats['gemini_requests'] += 1
                result = await self._analyze_with_gemini(news_item)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"⚠️ Сбой Gemini, переключаюсь на GigaChat: {e}")
                self.stats['errors'] += 1

        # Попытка 2: GigaChat (Fallback)
        if self.gigachat_available:
            try:
                self.stats['gigachat_requests'] += 1
                return await self._analyze_with_gigachat(news_item)
            except Exception as e:
                logger.error(f"❌ Сбой GigaChat: {e}")
                self.stats['errors'] += 1
        
        return None

    def _create_prompt(self, news_item: Dict) -> str:
        return f"""
        Ты финансовый аналитик РФ рынка (MOEX).
        Проанализируй новость и верни JSON.
        
        НОВОСТЬ:
        Заголовок: {news_item.get('title', '')}
        Текст: {news_item.get('description', '')}
        
        ЗАДАЧА:
        1. Найди тикеры MOEX (SBER, GAZP, LKOH и т.д.).
        2. Оцени влияние (-10 до +10).
        3. Дай краткую причину.
        
        ФОРМАТ ОТВЕТА (JSON):
        {{
            "tickers": ["SBER"],
            "sentiment": "positive",  // positive, negative, neutral
            "impact_score": 7,        // 1-10
            "confidence": 0.85,       // 0.0-1.0
            "is_tradable": true,
            "reason": "Краткое пояснение"
        }}
        """

    async def _analyze_with_gemini(self, news_item: Dict) -> Optional[Dict]:
        """Асинхронный запрос к Gemini"""
        prompt = self._create_prompt(news_item)
        
        # Gemini поддерживает асинхронность через generate_content_async
        response = await self.gemini_model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json" # Гарантирует JSON
            )
        )
        
        if response.text:
            logger.info(f"✨ Gemini analyzed: {news_item.get('title')[:30]}...")
            data = json.loads(response.text)
            return self._format_result(data, news_item, 'gemini')
        return None

    async def _analyze_with_gigachat(self, news_item: Dict) -> Optional[Dict]:
        """Асинхронный запрос к GigaChat"""
        token = await self._get_gigachat_token()
        if not token: return None
        
        prompt = self._create_prompt(news_item) + "\nВерни ТОЛЬКО JSON."
        
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
            'X-Request-ID': str(uuid.uuid4())
        }
        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                # Чистим markdown если есть
                content = re.sub(r'```json\s*|\s*```', '', content)
                data = json.loads(content)
                logger.info(f"🤖 GigaChat analyzed: {news_item.get('title')[:30]}...")
                return self._format_result(data, news_item, 'gigachat')
            return None

    async def _get_gigachat_token(self):
        if self.gigachat_token and time.time() < self.token_expires_at:
            return self.gigachat_token
            
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            'Authorization': f'Basic {self.gigachat_key}',
            'RqUID': str(uuid.uuid4()),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(url, headers=headers, data={'scope': 'GIGACHAT_API_PERS'})
            if resp.status_code == 200:
                data = resp.json()
                self.gigachat_token = data['access_token']
                self.token_expires_at = data['expires_at'] / 1000 - 60
                return self.gigachat_token
        return None

    def _format_result(self, data: Dict, news_item: Dict, provider: str) -> Dict:
        """Приведение ответа к единому формату"""
        # Валидация тикеров
        tickers = [t.upper() for t in data.get('tickers', []) if isinstance(t, str) and 2 <= len(t) <= 5]
        
        return {
            'ticker': tickers[0] if tickers else None,
            'tickers': tickers,
            'sentiment': data.get('sentiment', 'neutral'),
            'impact_score': data.get('impact_score', 5),
            'confidence': data.get('confidence', 0.5),
            'reason': data.get('reason', ''),
            'is_tradable': data.get('is_tradable', False),
            'ai_provider': provider,
            'news_id': news_item.get('id'),
            'event_type': 'ai_analysis'
        }

    def get_stats(self):
        return self.stats
