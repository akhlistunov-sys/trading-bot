# nlp_engine.py - ИСПРАВЛЕННЫЙ OpenRouter
import logging
import json
import os
import asyncio
import httpx
import time
import uuid
import base64
import ssl
import certifi
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== GIGACHAT OAUTH 2.0 ====================
class GigaChatAuth:
    def __init__(self, client_id: str, client_secret: str, scope: str = "GIGACHAT_API_PERS"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.access_token = None
        self.token_expiry = 0
        
    async def get_access_token(self) -> Optional[str]:
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        rquid = "6f0b1291-c7f3-4c4a-9d6a-2d47b5d91e13"
        
        credentials = f"{self.client_id}:{self.client_secret}"
        auth_base64 = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': rquid,
            'Authorization': f'Basic {auth_base64}'
        }
        
        payload = {'scope': self.scope}
        
        # SSL стратегии
        ssl_strategies = ["combined_cert", "sber_cert", "certifi", "insecure"]
        
        for strategy in ssl_strategies:
            try:
                if strategy == "insecure":
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    verify = False
                else:
                    ssl_context = ssl.create_default_context()
                    if strategy == "combined_cert":
                        combined_cert = Path("certs/combined_ca.crt")
                        if combined_cert.exists():
                            ssl_context.load_verify_locations(cafile=str(combined_cert))
                    elif strategy == "sber_cert":
                        sber_cert = Path("certs/sber_root.crt")
                        if sber_cert.exists():
                            ssl_context.load_verify_locations(cafile=str(sber_cert))
                    else:
                        ssl_context.load_verify_locations(cafile=certifi.where())
                    verify = ssl_context
                
                async with httpx.AsyncClient(timeout=30.0, verify=verify) as client:
                    response = await client.post(url, headers=headers, data=payload)
                    
                    if response.status == 200:
                        data = response.json()
                        self.access_token = data.get('access_token')
                        self.token_expiry = time.time() + 1800
                        return self.access_token
            except Exception:
                continue
        
        return None

# ==================== ОСНОВНОЙ NLP КЛАСС ====================
class NlpEngine:
    def __init__(self):
        logger.info("🔧 Инициализация NLP-движка...")
        
        # GigaChat
        gigachat_client_id = os.getenv('GIGACHAT_CLIENT_ID')
        gigachat_client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
        
        self.gigachat_auth = None
        if gigachat_client_id and gigachat_client_secret:
            self.gigachat_auth = GigaChatAuth(gigachat_client_id, gigachat_client_secret)
        
        # OpenRouter - ИСПРАВЛЕННЫЕ МОДЕЛИ (только рабочие)
        self.openrouter_models = [
            'google/gemini-2.0-flash:free',  # ✅ Работает
            'mistralai/mistral-7b-instruct:free',  # ✅ Работает
        ]
        # УБРАНЫ: llama-3.2 (404), zephyr (404)
        
        self.providers = {
            'gigachat': {
                'url': 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                'enabled': bool(gigachat_client_id and gigachat_client_secret),
                'priority': 1,
                'auth': self.gigachat_auth
            },
            'openrouter': {
                'url': 'https://openrouter.ai/api/v1/chat/completions',
                'token': os.getenv('OPENROUTER_API_TOKEN'),
                'enabled': bool(os.getenv('OPENROUTER_API_TOKEN')),
                'priority': 2,
                'models': self.openrouter_models
            }
        }
        
        self.provider_priority = sorted(
            [p for p in self.providers.keys() if self.providers[p]['enabled']],
            key=lambda x: self.providers[x]['priority']
        )
        
        self.stats = {'total_requests': 0, 'successful_requests': 0, 'cache_hits': 0, 'cache_misses': 0}
        logger.info(f"🤖 NLP-движок инициализирован: {', '.join(self.provider_priority)}")
    
    def _create_prompt(self, news_item: Dict, provider: str, model: str = None) -> Dict:
        title = news_item.get('title', '')[:200]
        content = news_item.get('content', '') or news_item.get('description', '')[:300]
        
        if provider == 'gigachat':
            prompt_text = f"""Анализируй финансовую новость для трейдинга на российском рынке.

Новость: {title}

Задача:
1. Найди упоминания российских компаний и их тикеры MOEX.
2. Определи тип события: dividend, earnings_report, merger, regulatory, market_update.
3. Оцени тональность: positive, negative, neutral.
4. Оцени силу влияния на цену (1-10).
5. Краткое обоснование.

Верни ТОЛЬКО JSON:
{{
    "tickers": ["SBER"],
    "event_type": "dividend",
    "sentiment": "positive",
    "impact_score": 7,
    "reason": "..."
}}

Если нет финансового содержания: {{"tickers": [], "reason": "No financial content"}}"""
            
            return {
                "model": "GigaChat",
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": 0.1,
                "max_tokens": 500,
                "stream": False
            }
        else:
            system_prompt = """Ты финансовый аналитик. Анализируй новости российского рынка.
Верни ТОЛЬКО JSON в формате: 
{"tickers": ["SBER"], "event_type": "dividend", "sentiment": "positive", "impact_score": 7, "reason": "..."}
Если нет финансового содержания: {"tickers": [], "reason": "No financial content"}"""
            
            return {
                "model": model or 'google/gemini-2.0-flash:free',
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Новость: {title}\n\n{content[:200]}"}
                ],
                "temperature": 0.1,
                "max_tokens": 400,
                "response_format": {"type": "json_object"}
            }
    
    async def _make_gigachat_request(self, prompt_data: Dict) -> Optional[Dict]:
        if not self.gigachat_auth:
            return None
        
        access_token = await self.gigachat_auth.get_access_token()
        if not access_token:
            return None
        
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Request-ID': '6f0b1291-c7f3-4c4a-9d6a-2d47b5d91e13'
        }
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, headers=headers, json=prompt_data)
                if response.status == 200:
                    return response.json()
        except Exception:
            pass
        return None
    
    async def _try_openrouter_model(self, model: str, news_item: Dict) -> Optional[Dict]:
        try:
            prompt_data = self._create_prompt(news_item, 'openrouter', model)
            headers = {
                "Authorization": f"Bearer {self.providers['openrouter']['token']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com"
            }
            
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    url=self.providers['openrouter']['url'],
                    headers=headers,
                    json=prompt_data
                )
                
                if response.status == 200:
                    return response.json()
                elif response.status == 429:
                    await asyncio.sleep(2)  # Пауза при rate limit
                    return None
                else:
                    return None
                    
        except Exception:
            return None
    
    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        self.stats['total_requests'] += 1
        
        # 1. GigaChat
        if 'gigachat' in self.provider_priority and self.providers['gigachat']['enabled']:
            try:
                prompt_data = self._create_prompt(news_item, 'gigachat')
                response_data = await self._make_gigachat_request(prompt_data)
                
                if response_data:
                    ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if ai_response:
                        analysis_result = self._parse_ai_response(ai_response, news_item, 'gigachat')
                        if analysis_result:
                            self.stats['successful_requests'] += 1
                            return analysis_result
            except Exception:
                pass
        
        # 2. OpenRouter
        if 'openrouter' in self.provider_priority and self.providers['openrouter']['enabled']:
            for model in self.openrouter_models:
                response_data = await self._try_openrouter_model(model, news_item)
                
                if response_data:
                    ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if ai_response:
                        analysis_result = self._parse_ai_response(ai_response, news_item, 'openrouter')
                        if analysis_result:
                            self.stats['successful_requests'] += 1
                            return analysis_result
                
                await asyncio.sleep(1)  # Пауза между запросами
        
        return None
    
    def _parse_ai_response(self, response: str, news_item: Dict, provider: str) -> Optional[Dict]:
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start == -1 or end == 0:
                return None
            
            json_str = response[start:end]
            data = json.loads(json_str)
            
            tickers = data.get('tickers', [])
            if not isinstance(tickers, list):
                tickers = []
            
            valid_tickers = []
            for ticker in tickers:
                if isinstance(ticker, str) and 2 <= len(ticker) <= 5 and ticker.isalpha():
                    valid_tickers.append(ticker.upper())
            
            reason = data.get('reason', '').lower()
            if not valid_tickers or 'no financial' in reason:
                return None
            
            event_type = data.get('event_type', 'market_update')
            sentiment = data.get('sentiment', 'neutral')
            impact_score = min(10, max(1, int(data.get('impact_score', 5))))
            
            confidence = 0.7
            if event_type != 'market_update':
                confidence += 0.1
            if sentiment != 'neutral':
                confidence += 0.1
            if impact_score >= 7:
                confidence += 0.1
            confidence = min(0.9, confidence)
            
            result = {
                'news_id': news_item.get('id', ''),
                'news_title': news_item.get('title', ''),
                'news_source': news_item.get('source', ''),
                'tickers': valid_tickers,
                'event_type': event_type,
                'impact_score': impact_score,
                'relevance_score': 70 if valid_tickers else 30,
                'sentiment': sentiment,
                'summary': data.get('reason', f"Найдено {len(valid_tickers)} тикеров"),
                'confidence': confidence,
                'ai_provider': provider,
                'analysis_timestamp': datetime.now().isoformat(),
                'simple_analysis': False
            }
            
            logger.info(f"   📊 {provider}: {len(valid_tickers)} тикеров, {event_type}, {sentiment}")
            return result
            
        except Exception:
            return None
    
    def get_stats(self) -> Dict:
        success_rate = (self.stats['successful_requests'] / self.stats['total_requests'] * 100) if self.stats['total_requests'] > 0 else 0
        return {
            'total_requests': self.stats['total_requests'],
            'successful_requests': self.stats['successful_requests'],
            'success_rate': round(success_rate, 1),
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'current_provider': self.provider_priority[0] if self.provider_priority else "none",
            'openrouter_models': len(self.openrouter_models),
        }
