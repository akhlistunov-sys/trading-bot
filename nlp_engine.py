# nlp_engine.py - УПРОЩЕННЫЙ ТОЛЬКО ДЛЯ GIGACHAT
import logging
import json
import os
import asyncio
import httpx
import time
import uuid
from datetime import datetime
from typing import Dict, Optional
import re
import base64

logger = logging.getLogger(__name__)

class GigaChatAuth:
    """Упрощенная авторизация GigaChat"""
    
    def __init__(self, client_id: str, client_secret: str, scope: str = "GIGACHAT_API_PERS"):
        self.client_id = client_id
        # Убираем кавычки если есть
        if client_secret.startswith('"') and client_secret.endswith('"'):
            client_secret = client_secret[1:-1]
        self.client_secret = client_secret
        self.scope = scope
        self.access_token = None
        self.token_expiry = 0
        self.last_refresh_time = 0
        
    async def get_access_token(self) -> Optional[str]:
        """Получение access token с кэшированием"""
        
        # Если токен есть и не истёк (меньше 25 часов)
        if self.access_token and time.time() - self.last_refresh_time < 90000:  # 25 часов
            return self.access_token
        
        logger.info("🔄 Обновление токена GigaChat...")
        
        # ИСПРАВЛЕННЫЙ URL для авторизации
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        rquid = str(uuid.uuid4())
        
        # Создаем base64 авторизацию
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': rquid,
            'Authorization': f'Basic {auth_base64}'
        }
        
        data = {'scope': self.scope}
        
        try:
            # ВАЖНО: verify=False только для тестов, на проде нужны сертификаты
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, headers=headers, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    self.access_token = result.get('access_token')
                    self.last_refresh_time = time.time()
                    
                    if self.access_token:
                        logger.info(f"✅ Новый токен GigaChat получен! Действует 30 мин.")
                        return self.access_token
                    else:
                        logger.error("❌ Токен не найден в ответе")
                        return None
                else:
                    logger.error(f"❌ GigaChat auth ошибка {response.status_code}: {response.text[:100]}")
                    return None
        except Exception as e:
            logger.error(f"❌ Ошибка запроса GigaChat: {str(e)[:100]}")
            return None

class NlpEngine:
    """Упрощенный NLP движок ТОЛЬКО с GigaChat"""
    
    def __init__(self):
        logger.info("🔧 Инициализация NLP движка (GigaChat-only)...")
        
        # Загружаем ключи
        client_id = os.getenv('GIGACHAT_CLIENT_ID')
        client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            logger.error("❌ GIGACHAT_CLIENT_ID или GIGACHAT_CLIENT_SECRET не настроены")
            self.gigachat_auth = None
            self.enabled = False
        else:
            self.gigachat_auth = GigaChatAuth(client_id, client_secret, 'GIGACHAT_API_PERS')
            self.enabled = True
        
        # Кэш для ускорения
        self.analysis_cache = {}
        
        # Семафор для 1 одновременного запроса
        self.semaphore = asyncio.Semaphore(1)
        
        # Статистика
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'avg_response_time': 0,
            'last_token_refresh': 0
        }
        
        logger.info(f"✅ GigaChat-only движок инициализирован: {'🟢 ВКЛ' if self.enabled else '🔴 ВЫКЛ'}")
    
    def _create_trading_prompt(self, news_item: Dict) -> str:
        """Создание промпта для трейдингового анализа"""
        
        title = news_item.get('title', '')[:200]
        description = news_item.get('description', '')[:300] or news_item.get('content', '')[:300]
        
        # Определяем время дня для контекста
        hour = datetime.now().hour
        if 10 <= hour < 12:
            time_context = "утренние торги (высокая волатильность)"
        elif 15 <= hour < 17:
            time_context = "вечерние торги (возможны закрытия позиций)"
        else:
            time_context = "стандартные торги"
        
        # Основные ликвидные тикеры
        liquid_tickers = "SBER, GAZP, LKOH, ROSN, NVTK, GMKN, YNDX, OZON, MOEX, VTBR, TCSG, MGNT, TATN, ALRS, CHMF, MTSS, SNGS, RTKM, AFLT, DSKY, MTLR, RUAL, MAGN, PIKK, PHOR, TRNFP, FIVE, MVID, LENT, SFIN"
        
        prompt = f"""Ты — алгоритмический трейдер российского рынка. Проанализируй финансовую новость.

КОНТЕКСТ:
- Время: {time_context}
- Ключевые тикеры MOEX: {liquid_tickers}

НОВОСТЬ:
Заголовок: "{title}"
Описание: "{description}"

ИНСТРУКЦИЯ:
1. Определи, является ли новость РЕАЛЬНЫМ ТОРГОВЫМ СИГНАЛОМ (дивиденды, отчетность, сделки, регулятивные решения) или это информационный шум.
2. Если это сигнал — найди ВСЕ тикеры из списка выше, к которым он применим.
3. Оцени влияние на цену: 'positive' (рост), 'negative' (падение), 'neutral' (неопределенно).
4. Оцени силу влияния от 1 (минимально) до 10 (максимально).
5. Если сигнал слабый или не торгуемый — верни is_tradable: false.

ФИНАНСОВЫЕ КРИТЕРИИ СИГНАЛА:
✓ Дивиденды, выплаты
✓ Финансовая отчетность (прибыль/убыток)
✓ Слияния, поглощения, сделки
✓ Регулятивные новости (ЦБ, санкции)
✓ Рекомендации аналитиков
✓ Изменения в руководстве (если значимые)
✓ Судебные разбирательства с финансовыми последствиями
✗ Технические работы, расписания
✗ Корпоративные события без финансового влияния
✗ Пресс-релизы без конкретных цифр

ВЕРНИ ТОЛЬКО JSON:
{{
  "tickers": ["SBER"],
  "sentiment": "positive",
  "impact_score": 7,
  "is_tradable": true,
  "reason": "Краткая причина (1 строка)"
}}

Если НЕ торговый сигнал:
{{
  "is_tradable": false,
  "reason": "Причина (например: 'техническая новость', 'нет тикеров')"
}}

ВАЖНО:
- Тикеры указывай только из списка выше
- impact_score должен быть целым числом от 1 до 10
- sentiment только: positive, negative или neutral"""
        
        return prompt
    
    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """Анализ новости через GigaChat"""
        
        if not self.enabled or not self.gigachat_auth:
            logger.warning("⚠️ GigaChat отключен, пропускаем анализ")
            return None
        
        self.stats['total_requests'] += 1
        
        # Кэширование по заголовку
        cache_key = news_item.get('title', '')[:50].replace(' ', '_').lower()
        if cache_key in self.analysis_cache:
            self.stats['cache_hits'] += 1
            return self.analysis_cache[cache_key]
        
        start_time = time.time()
        
        # Ограничиваем 1 запрос одновременно
        async with self.semaphore:
            try:
                # Получаем токен
                access_token = await self.gigachat_auth.get_access_token()
                if not access_token:
                    self.stats['failed_requests'] += 1
                    logger.error("❌ Не удалось получить токен GigaChat")
                    return None
                
                # Создаем промпт
                prompt_text = self._create_trading_prompt(news_item)
                
                # Подготовка запроса
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-Request-ID': str(uuid.uuid4())
                }
                
                # ИСПРАВЛЕНА МОДЕЛЬ: используем GigaChat-Max или GigaChat-Pro
                payload = {
                    "model": "GigaChat-Max",  # Можно также использовать "GigaChat-Pro"
                    "messages": [{"role": "user", "content": prompt_text}],
                    "temperature": 0.1,
                    "max_tokens": 500,
                    "stream": False
                }
                
                # Отправляем запрос с таймаутом
                async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                    response = await client.post(
                        'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                        headers=headers,
                        json=payload
                    )
                    
                    response_time = time.time() - start_time
                    
                    if response.status_code == 200:
                        result = response.json()
                        ai_response = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        if ai_response:
                            # Парсим ответ
                            analysis = self._parse_ai_response(ai_response, news_item)
                            if analysis:
                                self.stats['successful_requests'] += 1
                                # Обновляем среднее время ответа
                                if self.stats['avg_response_time'] == 0:
                                    self.stats['avg_response_time'] = response_time
                                else:
                                    self.stats['avg_response_time'] = (
                                        self.stats['avg_response_time'] * 0.8 + response_time * 0.2
                                    )
                                
                                # Сохраняем в кэш (макс 100 записей)
                                if len(self.analysis_cache) > 100:
                                    self.analysis_cache.pop(next(iter(self.analysis_cache)))
                                self.analysis_cache[cache_key] = analysis
                                
                                tickers_count = len(analysis.get('tickers', []))
                                impact = analysis.get('impact_score', 0)
                                logger.info(f"✅ GigaChat: {tickers_count} тикеров, impact={impact}, время={response_time:.1f}с")
                                return analysis
                            else:
                                logger.warning("⚠️ Не удалось распарсить ответ GigaChat")
                    
                    # Обработка ошибок
                    if response.status_code == 401:
                        logger.warning("🔄 Токен истёк, сбрасываю...")
                        self.gigachat_auth.access_token = None
                        # Можно попробовать повторно получить токен
                        access_token = await self.gigachat_auth.get_access_token()
                    elif response.status_code == 429:
                        logger.warning("⏰ Слишком много запросов, ждем...")
                        await asyncio.sleep(2)
                    
                    self.stats['failed_requests'] += 1
                    logger.error(f"❌ GigaChat ошибка {response.status_code}: {response.text[:200]}")
                    return None
                    
            except asyncio.TimeoutError:
                self.stats['failed_requests'] += 1
                logger.warning(f"⏰ GigaChat таймаут ({time.time() - start_time:.1f} сек)")
                return None
            except httpx.ConnectError:
                self.stats['failed_requests'] += 1
                logger.error("❌ Ошибка подключения к GigaChat")
                return None
            except Exception as e:
                self.stats['failed_requests'] += 1
                logger.error(f"❌ Неожиданная ошибка GigaChat: {str(e)[:200]}")
                return None
    
    def _parse_ai_response(self, response: str, news_item: Dict) -> Optional[Dict]:
        """Парсинг ответа GigaChat"""
        try:
            response = response.strip()
            
            # Ищем JSON в ответе
            json_str = None
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start != -1 and end != 0 and end > start:
                json_str = response[start:end]
            
            if not json_str:
                # Пробуем найти любой JSON
                json_pattern = r'\{[^{}]*\}'
                matches = re.findall(json_pattern, response, re.DOTALL)
                if matches:
                    json_str = max(matches, key=len)
            
            if not json_str:
                logger.error("❌ Не найден JSON в ответе GigaChat")
                logger.debug(f"Ответ: {response[:200]}")
                return None
            
            # Парсим JSON
            data = json.loads(json_str)
            
            # Если не торгуемый сигнал
            if not data.get('is_tradable', True):
                return {
                    'tickers': [],
                    'is_tradable': False,
                    'reason': data.get('reason', 'Не торговый сигнал'),
                    'ai_provider': 'gigachat',
                    'analysis_timestamp': datetime.now().isoformat(),
                    'news_id': news_item.get('id', ''),
                    'news_title': news_item.get('title', '')[:100]
                }
            
            # Извлекаем тикеры
            tickers = data.get('tickers', [])
            if not isinstance(tickers, list):
                tickers = []
            
            # Валидация тикеров
            valid_tickers = []
            for ticker in tickers:
                if isinstance(ticker, str):
                    ticker_upper = ticker.strip().upper()
                    # Проверяем, что тикер состоит из букв и цифр, длиной 2-6 символов
                    if 2 <= len(ticker_upper) <= 6 and re.match(r'^[A-Z0-9]+$', ticker_upper):
                        valid_tickers.append(ticker_upper)
            
            # Если нет валидных тикеров
            if not valid_tickers:
                return {
                    'tickers': [],
                    'is_tradable': False,
                    'reason': 'Нет валидных тикеров',
                    'ai_provider': 'gigachat',
                    'analysis_timestamp': datetime.now().isoformat(),
                    'news_id': news_item.get('id', ''),
                    'news_title': news_item.get('title', '')[:100]
                }
            
            # Валидация sentiment
            sentiment = data.get('sentiment', 'neutral').lower()
            if sentiment not in ['positive', 'negative', 'neutral']:
                sentiment = 'neutral'
            
            # Валидация impact_score
            try:
                impact_score = int(data.get('impact_score', 5))
                impact_score = max(1, min(10, impact_score))
            except (ValueError, TypeError):
                impact_score = 5
            
            # Собираем результат
            result = {
                'news_id': news_item.get('id', ''),
                'news_title': news_item.get('title', '')[:100],
                'news_source': news_item.get('source', ''),
                'tickers': valid_tickers,
                'event_type': 'ai_analyzed',
                'impact_score': impact_score,
                'sentiment': sentiment,
                'confidence': min(0.95, max(0.3, impact_score / 10)),
                'summary': data.get('reason', f"GigaChat: {len(valid_tickers)} тикеров"),
                'is_tradable': True,
                'ai_provider': 'gigachat',
                'analysis_timestamp': datetime.now().isoformat(),
                'simple_analysis': False,
                'raw_response': response[:500]  # Сохраняем часть сырого ответа для отладки
            }
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON GigaChat: {str(e)}")
            logger.debug(f"Ответ: {response[:500]}")
            return None
        except Exception as e:
            logger.error(f"❌ Критическая ошибка парсинга: {str(e)}")
            return None
    
    def get_stats(self) -> Dict:
        """Получение статистики"""
        total = self.stats['total_requests']
        success = self.stats['successful_requests']
        
        if total > 0:
            success_rate = (success / total) * 100
            avg_time = self.stats['avg_response_time']
        else:
            success_rate = 0
            avg_time = 0
        
        return {
            'engine': 'gigachat_only',
            'enabled': self.enabled,
            'total_requests': total,
            'successful_requests': success,
            'failed_requests': self.stats['failed_requests'],
            'success_rate': round(success_rate, 1),
            'cache_hits': self.stats['cache_hits'],
            'avg_response_time_seconds': round(avg_time, 2),
            'semaphore_queue': self.semaphore._value,
            'cache_size': len(self.analysis_cache)
        }
    
    def clear_cache(self):
        """Очистка кэша"""
        self.analysis_cache.clear()
        logger.info("🗑️ Кэш анализа очищен")

# Пример использования (для тестирования)
async def test_nlp_engine():
    """Тестирование NLP движка"""
    import sys
    
    # Установите переменные окружения для теста
    os.environ['GIGACHAT_CLIENT_ID'] = 'ваш_client_id'
    os.environ['GIGACHAT_CLIENT_SECRET'] = 'ваш_client_secret'
    
    engine = NlpEngine()
    
    if not engine.enabled:
        print("❌ Движок отключен, проверьте переменные окружения")
        return
    
    # Тестовая новость
    test_news = {
        'id': 'test_1',
        'title': 'Сбербанк увеличил дивиденды на 20%',
        'description': 'Совет директоров Сбербанка рекомендовал увеличить дивиденды за прошлый год на 20%',
        'source': 'test',
        'content': 'Полный текст новости о дивидендах Сбербанка'
    }
    
    print("🧪 Тестирование анализа новости...")
    result = await engine.analyze_news(test_news)
    
    if result:
        print(f"✅ Результат анализа:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("❌ Не удалось получить анализ")
    
    # Статистика
    stats = engine.get_stats()
    print(f"\n📊 Статистика: {json.dumps(stats, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    # Для тестирования
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_nlp_engine())
