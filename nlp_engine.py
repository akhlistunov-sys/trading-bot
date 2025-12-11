# nlp_engine.py - ПОЛНЫЙ КОД С DEEPSEEK И АГРЕССИВНЫМ РЕЖИМОМ
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
import re

logger = logging.getLogger(__name__)

# ==================== GIGACHAT OAUTH 2.0 ====================
class GigaChatAuth:
    """Класс для авторизации в GigaChat API"""
    
    def __init__(self, client_id: str, client_secret: str, scope: str = "GIGACHAT_API_PERS"):
        self.client_id = client_id
        self.client_secret = client_secret  # УЖЕ base64
        self.scope = scope
        self.access_token = None
        self.token_expiry = 0
        
    async def get_access_token(self) -> Optional[str]:
        """Получение access token"""
        
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        rquid = str(uuid.uuid4())
        
        # Убираем кавычки если есть
        client_secret_clean = self.client_secret
        if client_secret_clean.startswith('"') and client_secret_clean.endswith('"'):
            client_secret_clean = client_secret_clean[1:-1]
            logger.warning("⚠️ Убрал кавычки из client_secret")
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': rquid,
            'Authorization': f'Basic {client_secret_clean}'  # УЖЕ base64!
        }
        
        data = {'scope': self.scope}
        
        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, headers=headers, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    self.access_token = result.get('access_token')
                    self.token_expiry = time.time() + 1800  # 30 минут
                    
                    logger.info(f"✅ GigaChat токен получен! (RqUID: {rquid[:8]})")
                    return self.access_token
                else:
                    logger.error(f"❌ GigaChat ошибка {response.status_code}: {response.text[:100]}")
                    return None
        except Exception as e:
            logger.error(f"❌ Ошибка запроса GigaChat: {str(e)[:100]}")
            return None

# ==================== ОСНОВНОЙ NLP КЛАСС ====================
class NlpEngine:
    """Гибридный ИИ-движок с GigaChat, DeepSeek, OpenRouter"""
    
    def __init__(self):
        logger.info("🔧 Инициализация гибридного NLP-движка...")
        
        # Настраиваем SSL сертификаты для Render
        self._setup_ssl_for_render()
        
        # Загружаем API ключи
        gigachat_client_id = os.getenv('GIGACHAT_CLIENT_ID')
        gigachat_client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
        deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        openrouter_api_key = os.getenv('OPENROUTER_API_TOKEN')
        
        # GigaChat OAuth
        self.gigachat_auth = None
        if gigachat_client_id and gigachat_client_secret:
            if gigachat_client_secret.startswith('"') and gigachat_client_secret.endswith('"'):
                gigachat_client_secret = gigachat_client_secret[1:-1]
            
            self.gigachat_auth = GigaChatAuth(gigachat_client_id, gigachat_client_secret, 'GIGACHAT_API_PERS')
            logger.info(f"🔑 GigaChat OAuth настроен")
        
        # Семафоры для ограничения 1 одновременного запроса к каждому провайдеру
        self.gigachat_semaphore = asyncio.Semaphore(1)
        self.deepseek_semaphore = asyncio.Semaphore(1)
        self.openrouter_semaphore = asyncio.Semaphore(1)
        
        # Провайдеры
        self.providers = {
            'gigachat': {
                'url': 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                'enabled': bool(gigachat_client_id and gigachat_client_secret),
                'priority': 1,
                'auth': self.gigachat_auth,
                'semaphore': self.gigachat_semaphore
            },
            'deepseek': {
                'url': 'https://api.deepseek.com/v1/chat/completions',
                'token': deepseek_api_key,
                'enabled': False,
                'priority': 2,
                'model': 'deepseek-chat',
                'semaphore': self.deepseek_semaphore
            },
            'openrouter': {
                'url': 'https://openrouter.ai/api/v1/chat/completions',
                'token': openrouter_api_key,
                'enabled': bool(openrouter_api_key),
                'priority': 3,
                'models': ['google/gemini-2.0-flash-001:free', 'mistralai/mistral-7b-instruct:free'],
                'semaphore': self.openrouter_semaphore
            }
        }
        
        # Сортируем провайдеры по приоритету
        self.provider_priority = sorted(
            [p for p in self.providers.keys() if self.providers[p]['enabled']],
            key=lambda x: self.providers[x]['priority']
        )
        
        # Кэш и статистика
        self.analysis_cache = {}
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'by_provider': {p: {'requests': 0, 'success': 0} for p in self.provider_priority},
            'cache_hits': 0,
            'cache_misses': 0,
            'gigachat_queue_waits': 0,
            'deepseek_queue_waits': 0,
            'openrouter_queue_waits': 0,
            'parsing_errors': 0,
            'no_financial_content': 0
        }
        
        logger.info(f"🤖 Гибридный NLP-движок инициализирован")
        logger.info(f"📊 Доступные провайдеры: {', '.join(self.provider_priority)}")
        logger.info(f"🔒 Семафоры: 1 запрос одновременно на каждый провайдер")
    
    def _setup_ssl_for_render(self):
        """Настройка SSL сертификатов для облачного деплоя"""
        try:
            certs_dir = Path("certs")
            certs_dir.mkdir(exist_ok=True)
            
            combined_cert = certs_dir / "combined_ca.crt"
            
            with open(combined_cert, "wb") as outfile:
                with open(certifi.where(), "rb") as certifi_file:
                    outfile.write(certifi_file.read())
            
            logger.info(f"✅ SSL настроен для Render: {combined_cert}")
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка настройки SSL для Render: {e}")
    
    def _create_prompt_for_provider(self, news_item: Dict, provider: str, model: str = None) -> Dict:
        """Создание промпта для финансового анализа - АГРЕССИВНЫЙ РЕЖИМ"""
        
        title = news_item.get('title', '')[:200]
        description = news_item.get('description', '')
        content = news_item.get('content', '') or description[:300]
        
        # Определяем язык новости
        has_russian = any(char in title.lower() for char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя')
        
        # Базовые тикеры MOEX
        moex_tickers = "SBER, GAZP, LKOH, ROSN, NVTK, GMKN, YNDX, OZON, MOEX, VTBR, TCSG, MGNT, FIVE, TATN, ALRS, CHMF, NLMK, SNGS, MTSS, AFKS, RTKM, PHOR"
        
        if provider == 'gigachat':
            if has_russian:
                prompt_text = f"""Найди российские компании и их тикеры MOEX в новости.

Новость: {title}

Тикеры MOEX: {moex_tickers}

Примеры:
- "Сбербанк", "банк", "финансы" → SBER
- "Газпром", "нефть", "газ" → GAZP
- "Рынок", "акции", "биржевые торги" → SBER, GAZP, LKOH
- "Металлы", "горнодобыча" → GMKN, ALRS
- "Технологии", "интернет" → YNDX, OZON

Даже если упоминание косвенное — найди ВОЗМОЖНЫЕ тикеры.

Верни ТОЛЬКО JSON:
{{
    "tickers": ["SBER"],
    "event_type": "market_update",
    "sentiment": "neutral",
    "impact_score": 5,
    "reason": "Упоминание банковского сектора"
}}

Если тикеров НЕТ: {{"tickers": [], "reason": "Тикеры не найдены"}}
Только JSON!"""
            else:
                prompt_text = f"""Find Russian companies and their MOEX tickers in the news.

News: {title}

MOEX tickers: {moex_tickers}

Examples:
- "Sberbank", "bank", "finance" → SBER
- "Gazprom", "oil", "gas" → GAZP
- "Market", "stocks", "exchange trading" → SBER, GAZP, LKOH
- "Metals", "mining" → GMKN, ALRS
- "Technology", "internet" → YNDX, OZON

Even if the mention is indirect — find POSSIBLE tickers.

Return ONLY JSON:
{{
    "tickers": ["SBER"],
    "event_type": "market_update",
    "sentiment": "neutral",
    "impact_score": 5,
    "reason": "Banking sector mentioned"
}}

If NO tickers: {{"tickers": [], "reason": "No tickers found"}}
ONLY JSON!"""
            
            return {
                "model": "GigaChat-2",
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": 0.1,
                "max_tokens": 300,
                "stream": False
            }
        
        elif provider == 'deepseek':
            # DeepSeek промпт
            prompt_text = f"""Find MOEX stock tickers in this news:

{title}

MOEX tickers: {moex_tickers}

Return JSON:
{{
    "tickers": ["SBER"],
    "event_type": "market_update",
    "sentiment": "neutral",
    "impact_score": 5,
    "reason": "Found tickers"
}}

If no tickers: {{"tickers": [], "reason": "No tickers"}}
ONLY JSON!"""
            
            return {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": 0.1,
                "max_tokens": 200,
                "stream": False
            }
        
        else:  # OpenRouter
            system_prompt = """You are a financial analyst. Find MOEX tickers in news. Return ONLY JSON: {"tickers": ["SBER"], "event_type": "market_update", "sentiment": "neutral", "impact_score": 5, "reason": "..."}. If no tickers: {"tickers": [], "reason": "No tickers"}"""
            
            return {
                "model": model or 'google/gemini-2.0-flash:free',
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"News: {title}"}
                ],
                "temperature": 0.1,
                "max_tokens": 200
            }
    
    async def _make_gigachat_request(self, prompt_data: Dict) -> Optional[Dict]:
        """Запрос к GigaChat API"""
        if not self.gigachat_auth:
            return None
        
        access_token = await self.gigachat_auth.get_access_token()
        if not access_token:
            return None
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Request-ID': str(uuid.uuid4())
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(
                    'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                    headers=headers,
                    json=prompt_data
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    logger.warning("⚠️ GigaChat токен истёк, обновляю...")
                    self.gigachat_auth.access_token = None
                    return None
                else:
                    logger.error(f"❌ GigaChat ошибка {response.status_code}: {response.text[:100]}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка запроса к GigaChat: {str(e)[:100]}")
            return None
    
    async def _make_deepseek_request(self, prompt_data: Dict) -> Optional[Dict]:
        """Запрос к DeepSeek API"""
        token = self.providers['deepseek']['token']
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    'https://api.deepseek.com/v1/chat/completions',
                    headers=headers,
                    json=prompt_data
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"❌ DeepSeek ошибка {response.status_code}: {response.text[:100]}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка запроса к DeepSeek: {str(e)[:100]}")
            return None
    
    async def _make_openrouter_request(self, prompt_data: Dict) -> Optional[Dict]:
        """Запрос к OpenRouter API"""
        token = self.providers['openrouter']['token']
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com"
        }
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers=headers,
                    json=prompt_data
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"❌ OpenRouter ошибка {response.status_code}: {response.text[:100]}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка запроса к OpenRouter: {str(e)[:100]}")
            return None
    
    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """Анализ новости - последовательно пробуем провайдеров"""
        
        self.stats['total_requests'] += 1
        cache_key = self._create_cache_key(news_item)
        
        if cache_key in self.analysis_cache:
            self.stats['cache_hits'] += 1
            return self.analysis_cache[cache_key]
        
        self.stats['cache_misses'] += 1
        
        # Пробуем провайдеры по порядку
        for provider_name in self.provider_priority:
            provider = self.providers[provider_name]
            
            if not provider['enabled']:
                continue
            
            logger.debug(f"📡 Пробую {provider_name}: {news_item.get('title', '')[:50]}")
            self.stats['by_provider'][provider_name]['requests'] += 1
            
            # Ожидаем семафор для ограничения 1 запроса
            async with provider['semaphore']:
                # Увеличиваем счетчик ожидания
                if provider_name == 'gigachat':
                    self.stats['gigachat_queue_waits'] += 1
                elif provider_name == 'deepseek':
                    self.stats['deepseek_queue_waits'] += 1
                elif provider_name == 'openrouter':
                    self.stats['openrouter_queue_waits'] += 1
                
                try:
                    # Создаем промпт
                    if provider_name == 'openrouter':
                        model = provider['models'][0] if provider['models'] else None
                        prompt_data = self._create_prompt_for_provider(news_item, provider_name, model)
                    else:
                        prompt_data = self._create_prompt_for_provider(news_item, provider_name)
                    
                    # Отправляем запрос
                    response_data = None
                    if provider_name == 'gigachat':
                        response_data = await self._make_gigachat_request(prompt_data)
                    elif provider_name == 'deepseek':
                        response_data = await self._make_deepseek_request(prompt_data)
                    elif provider_name == 'openrouter':
                        response_data = await self._make_openrouter_request(prompt_data)
                    
                    if response_data:
                        # Извлекаем ответ
                        if provider_name == 'gigachat':
                            ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        elif provider_name == 'deepseek':
                            ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        else:  # openrouter
                            ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        if ai_response:
                            # Логируем сырой ответ
                            logger.debug(f"📥 {provider_name} raw: {ai_response[:100]}")
                            
                            # Парсим ответ
                            analysis_result = self._parse_ai_response(ai_response, news_item, provider_name)
                            
                            if analysis_result:
                                self.stats['successful_requests'] += 1
                                self.stats['by_provider'][provider_name]['success'] += 1
                                self.analysis_cache[cache_key] = analysis_result
                                
                                logger.info(f"✅ {provider_name}: {len(analysis_result['tickers'])} тикеров")
                                return analysis_result
                            else:
                                logger.debug(f"⚠️ {provider_name}: анализ не получен")
                
                except Exception as e:
                    logger.debug(f"⚠️ {provider_name} ошибка: {str(e)[:50]}")
                
                # Пауза между запросами к одному провайдеру
                await asyncio.sleep(1)
        
        logger.debug("ℹ️ Все провайдеры не дали анализа")
        return None
    
    def _parse_ai_response(self, response: str, news_item: Dict, provider: str) -> Optional[Dict]:
        """Парсинг ответа ИИ - АГРЕССИВНЫЙ РЕЖИМ (без фильтрации по финансовому содержанию)"""
        try:
            response = response.strip()
            
            # Логируем ответ для отладки
            logger.debug(f"🔍 {provider} raw response: {response[:200]}...")
            
            # Пытаемся найти JSON
            json_str = None
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start != -1 and end != 0 and end > start:
                json_str = response[start:end]
            
            if not json_str:
                # Пробуем регулярное выражение
                json_pattern = r'\{[^{}]*\}'
                matches = re.findall(json_pattern, response, re.DOTALL)
                if matches:
                    json_str = max(matches, key=len)
            
            if not json_str:
                self.stats['parsing_errors'] += 1
                logger.error(f"❌ {provider}: Не найден JSON в ответе")
                logger.error(f"   Ответ: {response[:200]}...")
                return None
            
            logger.debug(f"✅ {provider} JSON найден: {json_str[:150]}...")
            
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.stats['parsing_errors'] += 1
                logger.error(f"❌ {provider}: Ошибка парсинга JSON: {str(e)}")
                logger.error(f"   JSON строка: {json_str[:200]}...")
                return None
            
            tickers = data.get('tickers', [])
            if not isinstance(tickers, list):
                tickers = []
            
            # ✅ ВАЖНО: УБИРАЕМ ПРОВЕРКУ НА "NO FINANCIAL CONTENT"!
            # В агрессивном режиме принимаем ВСЕ новости с тикерами
            
            if not tickers:
                # Только если вообще нет тикеров
                self.stats['no_financial_content'] += 1
                logger.debug(f"⚠️ {provider}: Нет тикеров")
                return None
            
            valid_tickers = []
            for ticker in tickers:
                if isinstance(ticker, str) and 2 <= len(ticker) <= 6:
                    ticker_upper = ticker.upper()
                    if any(c.isalpha() for c in ticker_upper):
                        valid_tickers.append(ticker_upper)
            
            if not valid_tickers:
                self.stats['no_financial_content'] += 1
                logger.debug(f"⚠️ {provider}: Нет валидных тикеров")
                return None
            
            # Извлекаем остальные поля
            event_type = data.get('event_type', 'market_update')
            sentiment = data.get('sentiment', 'neutral')
            
            impact_score = 5
            try:
                raw_impact = data.get('impact_score')
                if raw_impact is not None:
                    impact_score = int(raw_impact)
            except:
                pass
            
            impact_score = min(10, max(1, impact_score))
            
            # Confidence для агрессивного режима
            confidence = 0.7  # Базовая уверенность
            
            result = {
                'news_id': news_item.get('id', ''),
                'news_title': news_item.get('title', ''),
                'news_source': news_item.get('source', ''),
                'tickers': valid_tickers,
                'event_type': event_type,
                'impact_score': impact_score,
                'relevance_score': 70 if valid_tickers else 30,
                'sentiment': sentiment,
                'horizon': 'short_term',
                'summary': data.get('reason', f"Найдено {len(valid_tickers)} тикеров"),
                'confidence': confidence,
                'ai_provider': provider,
                'analysis_timestamp': datetime.now().isoformat(),
                'simple_analysis': False
            }
            
            logger.info(f"📊 {provider}: {len(valid_tickers)} тикеров ({valid_tickers}), {event_type}, {sentiment}")
            return result
            
        except Exception as e:
            self.stats['parsing_errors'] += 1
            logger.error(f"❌ {provider}: Критическая ошибка парсинга: {str(e)}")
            return None
    
    def _create_cache_key(self, news_item: Dict) -> str:
        """Создание ключа кэша"""
        title = news_item.get('title', '')[:50].replace(' ', '_').lower()
        source = news_item.get('source', '')[:20].replace(' ', '_').lower()
        return f"{source}_{title}"
    
    def get_current_provider(self) -> str:
        return self.provider_priority[0] if self.provider_priority else "none"
    
    def get_stats(self) -> Dict:
        success_rate = (self.stats['successful_requests'] / self.stats['total_requests'] * 100) if self.stats['total_requests'] > 0 else 0
        
        provider_stats = {}
        for provider in self.providers:
            if provider in self.stats['by_provider']:
                req = self.stats['by_provider'][provider].get('requests', 0)
                succ = self.stats['by_provider'][provider].get('success', 0)
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
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'gigachat_queue_waits': self.stats['gigachat_queue_waits'],
            'deepseek_queue_waits': self.stats.get('deepseek_queue_waits', 0),
            'openrouter_queue_waits': self.stats.get('openrouter_queue_waits', 0),
            'parsing_errors': self.stats['parsing_errors'],
            'no_financial_content': self.stats['no_financial_content'],
            'current_provider': self.get_current_provider(),
            'providers': provider_stats,
            'enabled_providers': self.provider_priority
        }
