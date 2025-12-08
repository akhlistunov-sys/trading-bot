import logging
import json
import os
import asyncio
import httpx
import time
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== GIGACHAT OAUTH 2.0 КЛАСС ====================
class GigaChatAuth:
    """Класс для авторизации в GigaChat API через OAuth 2.0"""
    
    def __init__(self, client_id: str, client_secret: str, scope: str = "GIGACHAT_API_PERS"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.access_token = None
        self.token_expiry = 0
        
    async def get_access_token(self) -> Optional[str]:
        """Получение access token через OAuth 2.0"""
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4()),
        }
        
        payload = {
            'scope': self.scope,
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            logger.info("🔑 Запрашиваю новый токен GigaChat...")
            
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, headers=headers, data=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get('access_token')
                    expires_in = data.get('expires_in', 1800)
                    
                    self.token_expiry = time.time() + expires_in
                    
                    logger.info(f"✅ GigaChat: получен новый access token")
                    return self.access_token
                else:
                    logger.error(f"❌ GigaChat auth ошибка {response.status_code}: {response.text[:100]}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения токена GigaChat: {str(e)[:100]}")
            return None

# ==================== ОСНОВНОЙ NLP КЛАСС ====================
class NlpEngine:
    """Гибридный ИИ-движок с поддержкой GigaChat и OpenRouter"""
    
    def __init__(self):
        logger.info("🔧 Инициализация гибридного NLP-движка...")
        
        gigachat_client_id = os.getenv('GIGACHAT_CLIENT_ID')
        gigachat_client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
        gigachat_scope = os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')
        
        self.gigachat_auth = None
        if gigachat_client_id and gigachat_client_secret:
            self.gigachat_auth = GigaChatAuth(gigachat_client_id, gigachat_client_secret, gigachat_scope)
            logger.info(f"🔑 GigaChat OAuth настроен")
        else:
            logger.warning("⚠️ GigaChat отключен: нет Client ID или Client Secret")
        
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
                'priority': 2
            }
        }
        
        self.provider_priority = sorted(
            [p for p in self.providers.keys() if self.providers[p]['enabled']],
            key=lambda x: self.providers[x]['priority']
        )
        
        self.model_indices = {provider: 0 for provider in self.provider_priority}
        self.analysis_cache = {}
        
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'by_provider': {p: {'requests': 0, 'success': 0} for p in self.provider_priority},
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        logger.info(f"🤖 Гибридный NLP-движок инициализирован")
        logger.info(f"📊 Доступные провайдеры: {', '.join(self.provider_priority)}")
    
    # ==================== ИСПРАВЛЕННЫЕ МЕТОДЫ ====================
    
    def _create_prompt_for_provider(self, news_item: Dict, provider: str) -> Dict:
        """Создание промпта в зависимости от провайдера (ИСПРАВЛЕНО)"""
        
        title = news_item.get('title', '')
        description = news_item.get('description', '')
        content = news_item.get('content', '') or description[:500]
        
        if provider == 'gigachat':
            # OpenAI-совместимый формат для GigaChat
            return {
                "model": "GigaChat",
                "messages": [
                    {
                        "role": "user", 
                        "content": f"""Анализируй новость: '{title}'
                        Задача: найди упоминания российских компаний и их биржевые тикеры.
                        Примеры: Сбербанк -> SBER, Газпром -> GAZP, Лукойл -> LKOH.
                        Верни ТОЛЬКО JSON в формате: {{"tickers": ["SBER", "GAZP"]}}
                        Если тикеров нет, верни: {{"tickers": []}}
                        Только JSON, никакого текста!"""
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 300
            }
        else:
            # OpenRouter
            system_prompt = """You MUST return ONLY JSON: {"tickers": ["SBER", "GAZP"]}"""
            
            return {
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"News: {title}\n\nFind Russian stock tickers."}
                ],
                "temperature": 0.1,
                "max_tokens": 200,
                "response_format": {"type": "json_object"}
            }
    
    async def _make_gigachat_request(self, prompt_data: Dict) -> Optional[Dict]:
        """Запрос к GigaChat API (ИСПРАВЛЕНО)"""
        if not self.gigachat_auth:
            return None
        
        access_token = await self.gigachat_auth.get_access_token()
        if not access_token:
            return None
        
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Логируем запрос для отладки
        logger.debug(f"📨 GigaChat запрос: {json.dumps(prompt_data, ensure_ascii=False)[:150]}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, headers=headers, json=prompt_data)
                
                logger.debug(f"📨 GigaChat ответ: {response.status_code}")
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 400:
                    logger.error(f"❌ GigaChat 400: {response.text[:200]}")
                    return None
                elif response.status_code == 401:
                    logger.warning("⚠️ GigaChat токен истёк, обновляю...")
                    self.gigachat_auth.access_token = None
                    return None
                else:
                    logger.error(f"❌ GigaChat ошибка {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка запроса к GigaChat: {str(e)[:100]}")
            return None
    
    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """Анализ новости с использованием доступных провайдеров"""
        
        self.stats['total_requests'] += 1
        cache_key = self._create_cache_key(news_item)
        
        if cache_key in self.analysis_cache:
            self.stats['cache_hits'] += 1
            return self.analysis_cache[cache_key]
        
        self.stats['cache_misses'] += 1
        
        if not self.provider_priority:
            return None
        
        for provider in self.provider_priority:
            if not self.providers[provider]['enabled']:
                continue
            
            logger.info(f"📡 Пробую провайдер: {provider.upper()}")
            self.stats['by_provider'][provider]['requests'] += 1
            
            for attempt in range(2):  # 2 попытки
                try:
                    prompt_data = self._create_prompt_for_provider(news_item, provider)
                    
                    if provider == 'gigachat':
                        response_data = await self._make_gigachat_request(prompt_data)
                    else:
                        headers = {
                            "Authorization": f"Bearer {self.providers['openrouter']['token']}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://github.com"
                        }
                        
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            response = await client.post(
                                url=self.providers[provider]['url'],
                                headers=headers,
                                json=prompt_data
                            )
                            response_data = response.json() if response.status_code == 200 else None
                    
                    if response_data:
                        ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        if ai_response:
                            analysis_result = self._parse_ai_response(ai_response, news_item, provider)
                            
                            if analysis_result:
                                self.stats['successful_requests'] += 1
                                self.stats['by_provider'][provider]['success'] += 1
                                
                                self.analysis_cache[cache_key] = analysis_result
                                if len(self.analysis_cache) > 50:
                                    self.analysis_cache.pop(next(iter(self.analysis_cache)))
                                
                                logger.info(f"   ✅ {provider}: успешный анализ")
                                return analysis_result
                    
                except Exception as e:
                    logger.debug(f"   ⚠️ {provider} попытка {attempt+1}: {str(e)[:50]}")
                    await asyncio.sleep(1)
            
            await asyncio.sleep(0.5)
        
        logger.info("ℹ️ Все ИИ-провайдеры недоступны")
        return None
    
    def _parse_ai_response(self, response: str, news_item: Dict, provider: str) -> Optional[Dict]:
        """Парсинг ответа ИИ"""
        try:
            response = response.strip()
            
            # Ищем JSON
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start == -1 or end == 0:
                return None
            
            json_str = response[start:end]
            data = json.loads(json_str)
            
            tickers = data.get('tickers', [])
            
            if not isinstance(tickers, list):
                return None
            
            # Создаем простой результат
            result = {
                'news_id': news_item.get('id', ''),
                'news_title': news_item.get('title', ''),
                'tickers': tickers,
                'event_type': 'market_update',
                'impact_score': 5 if tickers else 3,
                'relevance_score': 70 if tickers else 30,
                'sentiment': 'neutral',
                'summary': f"Найдено {len(tickers)} тикеров",
                'ai_provider': provider,
                'confidence': 0.7 if tickers else 0.3
            }
            
            logger.info(f"   📊 {provider}: найдено {len(tickers)} тикеров")
            return result
            
        except:
            return None
    
    def _create_cache_key(self, news_item: Dict) -> str:
        title = news_item.get('title', '')[:50].replace(' ', '_').lower()
        source = news_item.get('source', '')[:20].replace(' ', '_').lower()
        return f"{source}_{title}"
    
    def get_current_provider(self) -> str:
        return self.provider_priority[0] if self.provider_priority else "simple"
    
    def get_stats(self) -> Dict:
        success_rate = (self.stats['successful_requests'] / self.stats['total_requests'] * 100) if self.stats['total_requests'] > 0 else 0
        
        provider_stats = {}
        for provider in self.providers:
            req = self.stats['by_provider'].get(provider, {}).get('requests', 0)
            succ = self.stats['by_provider'].get(provider, {}).get('success', 0)
            rate = (succ / req * 100) if req > 0 else 0
            provider_stats[provider] = {
                'requests': req,
                'success': succ,
                'success_rate': round(rate, 1),
                'enabled': self.providers[provider]['enabled']
            }
        
        return {
            'total_requests': self.stats['total_requests'],
            'successful_requests': self.stats['successful_requests'],
            'success_rate': round(success_rate, 1),
            'current_provider': self.get_current_provider(),
            'providers': provider_stats
        }
