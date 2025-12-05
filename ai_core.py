import logging
import json
import os
import httpx
import asyncio
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class AICore:
    """ИИ-ядро для нефтяного арбитража LKOH/ROSN"""
    
    def __init__(self):
        logger.info("🔧 [AICore] Инициализация для нефтяной пары LKOH/ROSN...")
        
        # Получаем API ключ из окружения Render
        self.api_key = os.getenv("OPENROUTER_API_TOKEN")
        if not self.api_key:
            raise ValueError("❌ OPENROUTER_API_TOKEN не найден в окружении Render")
        
        logger.info(f"✅ [AICore] Ключ получен ({len(self.api_key)} символов)")
        
        # ПРАВИЛЬНЫЙ список моделей (исправленные названия)
        self.model_priority = [
            "google/gemini-2.0-flash-exp:free",            # 1. Основная (работала)
            "meta-llama/llama-3.3-70b-instruct:free",      # 2. Meta-Llama 3.3 70B
            "meta-llama/llama-3.2-3b-instruct:free",       # 3. Meta-Llama 3.2 3B
            "qwen/qwen3-235b-a22b:free",                   # 4. Qwen 235B
            "google/gemma-3-27b:free",                     # 5. Google Gemma 3 27B
        ]
        
        self.current_model_idx = 0
        self.model = self.model_priority[self.current_model_idx]
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Кэш и статистика
        self.decision_cache = {}
        self.total_requests = 0
        self.successful_requests = 0
        self.model_switches = 0
        self.rate_limit_hits = 0
        
        logger.info(f"🤖 [AICore] Модель по умолчанию: {self.model}")
        logger.info(f"🎯 [AICore] Специализация: Нефтяной арбитраж LKOH/ROSN")
        logger.info(f"📊 [AICore] Нормализация: 1 LKOH ≈ 3.5 ROSN")
        logger.info(f"📋 [AICore] Всего моделей: {len(self.model_priority)}")
        
        # Логируем все доступные модели
        for i, model in enumerate(self.model_priority):
            logger.info(f"   {i+1}. {model}")
    
    def _switch_to_next_model(self):
        """Переключаемся на следующую модель"""
        old_model = self.model
        self.current_model_idx = (self.current_model_idx + 1) % len(self.model_priority)
        self.model = self.model_priority[self.current_model_idx]
        self.model_switches += 1
        
        logger.info(f"🔄 [AICore] Смена модели: {old_model} → {self.model}")
        return self.model
    
    async def get_trading_decision(self, market_data: Dict) -> List[Dict]:
        """Получает торговые решения для нефтяной пары"""
        
        self.total_requests += 1
        request_id = self.total_requests
        
        logger.info(f"🧠 [AICore] Запрос #{request_id} для LKOH/ROSN, модель: {self.model}")
        
        # Проверяем кэш
        cache_key = self._create_cache_key(market_data)
        if cache_key in self.decision_cache:
            logger.info(f"🔄 [AICore] Использую кэшированное решение")
            return self.decision_cache[cache_key]
        
        # Пробуем разные модели при ошибках
        max_retries = min(3, len(self.model_priority))
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"📨 [AICore] Попытка {attempt+1}/{max_retries} с моделью: {self.model}")
                
                # Формируем промпт для нефтяной пары
                prompt = self._create_oil_trading_prompt(market_data)
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        url=self.api_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://github.com",
                            "X-Title": "LKOH-ROSN Oil Pairs Trading AI"
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": """Ты — эксперт по парному арбитражу в нефтегазовом секторе.
                                    Специализация: LKOH (Лукойл) vs ROSN (Роснефть).
                                    Нормализация: 1 акция LKOH ≈ 3.5 акции ROSN по стоимости.
                                    
                                    Анализируй Z-score, корреляцию нефтяных компаний, макро-факторы.
                                    
                                    ВОЗВРАЩАЙ ТОЛЬКО JSON:
                                    {
                                        "signals": [
                                            {
                                                "action": "BUY/SELL",
                                                "ticker": "LKOH или ROSN",
                                                "reason": "подробное объяснение на русском",
                                                "confidence": 0.0-1.0,
                                                "size": число (LKOH: 1-2, ROSN: 10-20),
                                                "take_profit_percent": 2.5-3.5,
                                                "stop_loss_percent": 1.5-2.0
                                            }
                                        ],
                                        "analysis": "краткий анализ нефтяной пары"
                                    }
                                    Только JSON, без других текстов!"""
                                },
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.15,
                            "max_tokens": 600
                        }
                    )
                
                logger.info(f"📥 [AICore] Ответ: статус {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result["choices"][0]["message"]["content"]
                    
                    self.successful_requests += 1
                    success_rate = (self.successful_requests / self.total_requests) * 100
                    
                    logger.info(f"✅ [AICore] Успешный запрос #{self.successful_requests}")
                    logger.info(f"📊 [AICore] Успешность: {success_rate:.1f}%")
                    
                    # Парсим ответ
                    signals = self._parse_oil_ai_response(ai_response)
                    
                    if signals:
                        logger.info(f"🎯 [AICore] Найдено сигналов для нефтяной пары: {len(signals)}")
                        # Кэшируем успешный результат
                        self.decision_cache[cache_key] = signals
                        if len(self.decision_cache) > 20:
                            oldest = next(iter(self.decision_cache))
                            del self.decision_cache[oldest]
                    
                    return signals
                
                elif response.status_code in [400, 404, 429]:
                    # Проблема с моделью или rate limit
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                    
                    logger.warning(f"⚠️ [AICore] Ошибка модели {self.model}: {error_msg[:100]}")
                    
                    if attempt < max_retries - 1:
                        # Переключаем модель перед следующей попыткой
                        next_model = self._switch_to_next_model()
                        logger.info(f"⏳ [AICore] Задержка 2 сек перед моделью {next_model}...")
                        await asyncio.sleep(2)
                        continue
                    else:
                        last_error = f"Все модели недоступны: {error_msg}"
                        break
                
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:100]}"
                    break
                    
            except httpx.TimeoutException:
                last_error = "Таймаут 30с"
                logger.error(f"⏰ [AICore] Таймаут на модели {self.model}")
                if attempt < max_retries - 1:
                    self._switch_to_next_model()
                    await asyncio.sleep(3)
                    continue
                break
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ [AICore] Ошибка: {str(e)[:100]}")
                break
        
        if last_error:
            logger.error(f"❌ [AICore] Все попытки failed: {last_error}")
        
        return []
    
    def _create_oil_trading_prompt(self, market_data: Dict) -> str:
        """Создаёт промпт для нефтяного арбитража LKOH/ROSN"""
        
        prices = market_data.get('prices', {})
        lkoh_price = prices.get('LKOH', 0)
        rosneft_price = prices.get('ROSN', 0)
        rosneft_normalized = market_data.get('rosneft_normalized', 0)
        
        prompt = f"""
        ===== ДАННЫЕ ДЛЯ НЕФТЯНОГО АРБИТРАЖА LKOH/ROSN =====
        
        🏭 СЕКТОР: Нефтегазовый
        🎯 ПАРА: LKOH (Лукойл) vs ROSN (Роснефть)
        📊 НОРМАЛИЗАЦИЯ: 1 акция LKOH ≈ 3.5 акции ROSN по стоимости
        
        📈 ТЕКУЩИЕ ЦЕНЫ:
        - LKOH (Лукойл): {lkoh_price:.0f} руб.
        - ROSN (Роснефть): {rosneft_price:.0f} руб.
        - ROSN (нормализованный ×3.5): {rosneft_normalized:.0f} руб.
        
        🔢 МЕТРИКИ АРБИТРАЖА:
        - Соотношение LKOH/ROSN: {market_data.get('current_ratio', 0):.4f}
        - Историческое среднее: {market_data.get('mean_ratio', 0):.4f}
        - Z-score отклонение: {market_data.get('z_score', 0):.2f}σ
        - Волатильность (σ): {market_data.get('std_ratio', 0):.4f}
        
        📈 ИСТОРИЯ (последние {market_data.get('history_length', 0)} точек):
        {market_data.get('ratio_history_preview', 'Нет данных')}
        
        💰 ВИРТУАЛЬНЫЙ ПОРТФЕЛЬ:
        - Баланс: {market_data.get('balance', 100000):.0f} руб.
        - Свободные средства: {market_data.get('available_cash', 100000):.0f} руб.
        
        ⚡ РЕЖИМ ТОРГОВЛИ: АГРЕССИВНОЕ ТЕСТИРОВАНИЕ
        
        🎯 ПАРАМЕТРЫ:
        - Take Profit: 2.5-3.5%
        - Stop Loss: 1.5-2.0%
        - Confidence для входа: >0.7
        - Размер позиции: LKOH 1-2 акции, ROSN 10-20 акций
        
        📅 КОНТЕКСТ:
        - Время: {market_data.get('time_of_day', 'N/A')}
        - Активность: {market_data.get('market_hours', 'Основная сессия')}
        - Сектор: Нефтегазовый
        
        🔍 АНАЛИЗИРУЙ НЕФТЯНУЮ ПАРУ:
        1. Обе компании в нефтегазовом секторе - высокая корреляция
        2. Историческое соотношение: 1 LKOH ≈ 3.5 ROSN
        3. Текущее отклонение Z-score:
           • |Z| < 1.5: Нет сигнала
           • 1.5 < |Z| < 2.0: Слабый сигнал
           • |Z| > 2.0: Сильный сигнал
        
        4. НАПРАВЛЕНИЕ АРБИТРАЖА:
           • Z-score < -2.0: ROSN недооценен → BUY ROSN / SELL LKOH
           • Z-score > 2.0: ROSN переоценен → SELL ROSN / BUY LKOH
        
        5. РАЗМЕР ПОЗИЦИИ:
           - LKOH: 1-2 акции (дорогая)
           - ROSN: 10-20 акций
        
        6. РИСК-МЕНЕДЖМЕНТ:
           - Не более 5% портфеля в сделке
           - Всегда устанавливай TP и SL
           - Учитывай комиссии (0.05% Tinkoff)
        
        🚨 ПРАВИЛА БЕЗОПАСНОСТИ:
        - Не открывать позиции если |Z-score| < 1.5
        - Избегать торговли в первые/последние 30 минут
        - Принудительный выход при |Z-score| < 0.5
        
        ВЕРНИ JSON С СИГНАЛАМИ ДЛЯ НЕФТЯНОЙ ПАРЫ ИЛИ ПУСТОЙ МАССИВ [] ЕСЛИ НЕТ ВОЗМОЖНОСТЕЙ.
        """
        
        return prompt
    
    def _parse_oil_ai_response(self, response: str) -> List[Dict]:
        """Парсит ответ ИИ для нефтяной пары"""
        try:
            # Ищем JSON в ответе
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning(f"⚠️ [AICore] ИИ не вернул JSON: {response[:100]}...")
                return []
            
            json_str = response[start_idx:end_idx]
            data = json.loads(json_str)
            
            signals = []
            for signal in data.get("signals", []):
                # Валидация обязательных полей
                if not all(key in signal for key in ['action', 'ticker', 'reason']):
                    continue
                
                ticker = signal['ticker']
                # ТОЛЬКО нефтяные тикеры
                if ticker not in ['LKOH', 'ROSN']:
                    logger.warning(f"⚠️ [AICore] ИИ указал не нефтяной тикер: {ticker}")
                    continue
                
                action = signal['action'].upper()
                if action not in ['BUY', 'SELL']:
                    continue
                
                confidence = float(signal.get('confidence', 0.5))
                if confidence < 0.7:
                    logger.info(f"⚠️ [AICore] Низкий confidence {confidence:.2f}, пропускаю")
                    continue
                
                # Размеры позиций для нефтяной пары
                if ticker == 'LKOH':
                    size = signal.get('size', 1)  # LKOH: 1-2 акции
                else:  # ROSN
                    size = signal.get('size', 10)  # ROSN: 10-20 акций
                
                price = signal.get('price', 0)
                
                tp_percent = float(signal.get('take_profit_percent', 3.0))
                sl_percent = float(signal.get('stop_loss_percent', 1.8))
                
                # Рассчитываем TP/SL
                if action == 'BUY':
                    take_profit = price * (1 + tp_percent/100) if price > 0 else 0
                    stop_loss = price * (1 - sl_percent/100) if price > 0 else 0
                else:
                    take_profit = price * (1 - tp_percent/100) if price > 0 else 0
                    stop_loss = price * (1 + sl_percent/100) if price > 0 else 0
                
                validated_signal = {
                    'action': action,
                    'ticker': ticker,
                    'reason': signal['reason'],
                    'confidence': confidence,
                    'strategy': 'AI Oil Pairs Trading Pro',
                    'price': price,
                    'size': size,
                    'take_profit': round(take_profit, 2),
                    'stop_loss': round(stop_loss, 2),
                    'take_profit_percent': tp_percent,
                    'stop_loss_percent': sl_percent,
                    'ai_generated': True,
                    'sector': 'oil',
                    'timestamp': datetime.now().isoformat()
                }
                
                signals.append(validated_signal)
                logger.info(f"✅ [AICore] Нефтяной сигнал: {action} {ticker} x{size} (conf: {confidence:.2f})")
            
            # Логируем анализ если есть
            analysis = data.get("analysis", "")
            if analysis:
                logger.info(f"🧠 [AICore] Анализ нефтяной пары: {analysis[:120]}...")
            
            return signals
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ [AICore] Невалидный JSON: {str(e)[:50]}")
            return []
        except Exception as e:
            logger.error(f"❌ [AICore] Ошибка парсинга: {str(e)[:50]}")
            return []
    
    def _create_cache_key(self, market_data: Dict) -> str:
        """Создаёт ключ для кэша нефтяной пары"""
        prices = market_data.get('prices', {})
        ratio = market_data.get('current_ratio', 0)
        z_score = market_data.get('z_score', 0)
        hour = datetime.now().hour
        
        # Ключ включает нефтяные тикеры
        return f"oil_{hour}_{prices.get('LKOH', 0):.0f}_{prices.get('ROSN', 0):.0f}_{ratio:.4f}_{z_score:.1f}"
    
    def get_stats(self) -> Dict:
        """Статистика работы ИИ для нефтяной пары"""
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'success_rate': (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0,
            'current_model': self.model,
            'model_index': self.current_model_idx,
            'model_switches': self.model_switches,
            'cache_size': len(self.decision_cache),
            'specialization': 'LKOH/ROSN Oil Pairs Trading'
        }
