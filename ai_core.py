import logging
import json
import os
import httpx
import asyncio
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class AICore:
    """Оптимизированное ИИ-ядро для парного арбитража с автопереключением моделей"""
    
    def __init__(self):
        logger.info("🔧 [AICore] Инициализация...")
        
        # Получаем API ключ из окружения Render
        self.api_key = os.getenv("OPENROUTER_API_TOKEN")
        if not self.api_key:
            raise ValueError("❌ OPENROUTER_API_TOKEN не найден в окружении Render")
        
        logger.info(f"✅ [AICore] Ключ получен ({len(self.api_key)} символов)")
        
        # Приоритетный список РАБОЧИХ моделей из твоего списка
        self.model_priority = [
            "google/gemini-2.0-flash-exp:free",          # 1. Основная
            "meta/llama-3.3-70b-instruct:free",         # 2. Мощная
            "google/gemma-3-27b:free",                  # 3. Стабильная
            "meta/llama-3.2-3b-instruct:free",          # 4. Быстрая
            "qwen/qwen3-235b-a22b:free",                # 5. Большая
        ]
        
        self.current_model_idx = 0
        self.model = self.model_priority[self.current_model_idx]
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Кэш и статистика
        self.decision_cache = {}
        self.total_requests = 0
        self.successful_requests = 0
        self.model_switches = 0
        
        logger.info(f"🤖 [AICore] Модель по умолчанию: {self.model}")
        logger.info(f"📊 [AICore] Всего моделей в ротации: {len(self.model_priority)}")
    
    def _switch_to_next_model(self):
        """Переключаемся на следующую модель в списке"""
        old_model = self.model
        self.current_model_idx = (self.current_model_idx + 1) % len(self.model_priority)
        self.model = self.model_priority[self.current_model_idx]
        self.model_switches += 1
        
        logger.info(f"🔄 [AICore] Смена модели: {old_model} → {self.model}")
        logger.info(f"📊 [AICore] Всего переключений: {self.model_switches}")
        
        return self.model
    
    async def get_trading_decision(self, market_data: Dict) -> List[Dict]:
        """Получает торговые решения с автоматическим переключением моделей"""
        
        self.total_requests += 1
        request_id = self.total_requests
        
        logger.info(f"🧠 [AICore] Запрос #{request_id}, модель: {self.model}")
        
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
                
                # Формируем оптимизированный промпт для трейдинга
                prompt = self._create_trading_prompt(market_data)
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        url=self.api_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://github.com",
                            "X-Title": "SBER-VTBR Pairs Trading AI"
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": """Ты — эксперт по парному арбитражу на Московской бирже. 
                                    Специализация: SBER (Сбербанк) vs VTBR (ВТБ). 
                                    Нормализация: 1 акция SBER ≈ 1000 акций VTBR по стоимости.
                                    
                                    Анализируй Z-score, ликвидность, время дня, рыночные тренды.
                                    
                                    ВОЗВРАЩАЙ ТОЛЬКО JSON:
                                    {
                                        "signals": [
                                            {
                                                "action": "BUY/SELL",
                                                "ticker": "SBER или VTBR",
                                                "reason": "объяснение",
                                                "confidence": 0.0-1.0,
                                                "size": число,
                                                "take_profit_percent": 2.5-3.5,
                                                "stop_loss_percent": 1.5-2.0
                                            }
                                        ],
                                        "analysis": "краткий анализ"
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
                    signals = self._parse_ai_response(ai_response)
                    
                    if signals:
                        logger.info(f"🎯 [AICore] Найдено сигналов: {len(signals)}")
                        # Кэшируем успешный результат
                        self.decision_cache[cache_key] = signals
                        if len(self.decision_cache) > 20:
                            # Очищаем старые записи
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
    
    def _create_trading_prompt(self, market_data: Dict) -> str:
        """Создаёт оптимизированный промпт для трейдинга"""
        
        prices = market_data.get('prices', {})
        sber_price = prices.get('SBER', 0)
        vtbr_price = prices.get('VTBR', 0)
        vtbr_normalized = vtbr_price * 1000 if vtbr_price else 0
        
        prompt = f"""
        ===== ДАННЫЕ ДЛЯ ПАРНОГО АРБИТРАЖА SBER/VTBR =====
        
        📊 ТЕКУЩИЕ ЦЕНЫ:
        - SBER: {sber_price:.2f} руб.
        - VTBR: {vtbr_price:.3f} руб.
        - VTBR (нормализованный x1000): {vtbr_normalized:.2f} руб.
        
        🔢 МЕТРИКИ АРБИТРАЖА:
        - Соотношение SBER/VTBR: {market_data.get('current_ratio', 0):.4f}
        - Историческое среднее: {market_data.get('mean_ratio', 0):.4f}
        - Z-score отклонение: {market_data.get('z_score', 0):.2f}σ
        - Волатильность (σ): {market_data.get('std_ratio', 0):.4f}
        
        📈 ИСТОРИЯ (последние {market_data.get('history_length', 0)} точек):
        {market_data.get('ratio_history_preview', 'Нет данных')}
        
        ⚡ РЕЖИМ ТОРГОВЛИ: АГРЕССИВНОЕ ТЕСТИРОВАНИЕ
        
        🎯 ПАРАМЕТРЫ:
        - Take Profit: 2.5-3.5%
        - Stop Loss: 1.5-2.0%
        - Confidence для входа: >0.7
        - Макс. позиция: 10% портфеля
        
        📅 КОНТЕКСТ:
        - Время: {market_data.get('time_of_day', 'N/A')}
        - Активность: {market_data.get('market_hours', 'Основная сессия')}
        
        🔍 АНАЛИЗИРУЙ:
        1. Отклонение Z-score: |Z| > 2.0 = сильный сигнал
        2. Направление арбитража:
           • Z < -2.0: VTBR недооценен → BUY VTBR / SELL SBER
           • Z > 2.0: VTBR переоценен → SELL VTBR / BUY SBER
        3. Размер позиции (1-2% риска)
        4. Время суток (10:00-17:00 = лучшая ликвидность)
        
        🚨 БЕЗОПАСНОСТЬ:
        - Не торговать если |Z| < 1.5
        - Всегда указывай TP и SL
        - Учитывай комиссии 0.05%
        
        ВЕРНИ JSON С СИГНАЛАМИ ИЛИ ПУСТОЙ МАССИВ [] ЕСЛИ НЕТ ВОЗМОЖНОСТЕЙ.
        """
        
        return prompt
    
    def _parse_ai_response(self, response: str) -> List[Dict]:
        """Парсит ответ ИИ с валидацией"""
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
                if ticker not in ['SBER', 'VTBR']:
                    continue
                
                action = signal['action'].upper()
                if action not in ['BUY', 'SELL']:
                    continue
                
                confidence = float(signal.get('confidence', 0.5))
                if confidence < 0.7:
                    logger.info(f"⚠️ [AICore] Низкий confidence {confidence:.2f}, пропускаю")
                    continue
                
                size = signal.get('size', 100 if ticker == 'VTBR' else 1)
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
                    'strategy': 'AI Pairs Trading Pro',
                    'price': price,
                    'size': size,
                    'take_profit': round(take_profit, 2),
                    'stop_loss': round(stop_loss, 2),
                    'take_profit_percent': tp_percent,
                    'stop_loss_percent': sl_percent,
                    'ai_generated': True,
                    'timestamp': datetime.now().isoformat()
                }
                
                signals.append(validated_signal)
                logger.info(f"✅ [AICore] Валидный сигнал: {action} {ticker} x{size} (conf: {confidence:.2f})")
            
            # Логируем анализ если есть
            analysis = data.get("analysis", "")
            if analysis:
                logger.info(f"🧠 [AICore] Анализ ИИ: {analysis[:120]}...")
            
            return signals
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ [AICore] Невалидный JSON: {str(e)[:50]}")
            return []
        except Exception as e:
            logger.error(f"❌ [AICore] Ошибка парсинга: {str(e)[:50]}")
            return []
    
    def _create_cache_key(self, market_data: Dict) -> str:
        """Создаёт ключ для кэша"""
        prices = market_data.get('prices', {})
        ratio = market_data.get('current_ratio', 0)
        z_score = market_data.get('z_score', 0)
        hour = datetime.now().hour
        
        return f"{hour}_{prices.get('SBER', 0):.1f}_{prices.get('VTBR', 0):.3f}_{ratio:.4f}_{z_score:.1f}"
    
    def get_stats(self) -> Dict:
        """Статистика работы ИИ"""
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'success_rate': (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0,
            'current_model': self.model,
            'model_index': self.current_model_idx,
            'model_switches': self.model_switches,
            'cache_size': len(self.decision_cache)
        }
