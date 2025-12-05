import logging
import json
import os
import httpx
from typing import Dict, List
import statistics
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class AICore:
    """СПЕЦИАЛИЗИРОВАННОЕ ИИ-ядро для парного арбитража SBER/VTBR"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_TOKEN")  # ИСПРАВЛЕНО: API_TOKEN вместо API_KEY
        if not self.api_key:
            raise ValueError("❌ OPENROUTER_API_TOKEN не найден в переменных окружения")
        
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "google/gemini-2.0-flash-exp:free"
        self.decision_cache = {}
        self.total_requests = 0
        self.successful_requests = 0
        
    async def get_trading_decision(self, market_data: Dict) -> List[Dict]:
        """Получает торговые решения от ИИ для парного арбитража"""
        
        self.total_requests += 1
        cache_key = self._create_cache_key(market_data)
        if cache_key in self.decision_cache:
            logger.info(f"🔄 Использую кэшированное решение ИИ (всего кэш: {len(self.decision_cache)})")
            return self.decision_cache[cache_key]
        
        prompt = self._create_optimized_prompt(market_data)
        
        try:
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
                                Специализируешься на паре SBER (Сбербанк) и VTBR (ВТБ).
                                Нормализация: 1 акция SBER ≈ 1000 акций VTBR по стоимости.
                                
                                Анализируй Z-score отклонения, ликвидность, время дня, общий тренд рынка.
                                
                                ВОЗВРАЩАЙ ТОЛЬКО JSON формата:
                                {
                                    "signals": [
                                        {
                                            "action": "BUY/SELL/HOLD",
                                            "ticker": "SBER или VTBR",
                                            "reason": "подробное объяснение на русском",
                                            "confidence": 0.0-1.0,
                                            "size": 1-1000,
                                            "take_profit_percent": 2.5-3.5,
                                            "stop_loss_percent": 1.5-2.0
                                        }
                                    ],
                                    "market_analysis": "краткий анализ ситуации"
                                }
                                Никакого текста вне JSON!"""
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.15,
                        "max_tokens": 800
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result["choices"][0]["message"]["content"]
                    
                    logger.info(f"📨 ИИ ответ получен ({len(ai_response)} символов)")
                    
                    signals = self._parse_ai_response(ai_response)
                    
                    if signals:
                        self.successful_requests += 1
                        success_rate = (self.successful_requests / self.total_requests) * 100
                        logger.info(f"📊 Статистика ИИ: {self.successful_requests}/{self.total_requests} успешно ({success_rate:.1f}%)")
                    
                    self.decision_cache[cache_key] = signals
                    if len(self.decision_cache) > 20:
                        oldest_key = next(iter(self.decision_cache))
                        del self.decision_cache[oldest_key]
                    
                    return signals
                else:
                    logger.error(f"❌ Ошибка OpenRouter API {response.status_code}: {response.text[:200]}")
                    return []
                    
        except Exception as e:
            logger.error(f"❌ Ошибка связи с ИИ: {str(e)[:100]}")
            return []
    
    def _create_optimized_prompt(self, market_data: Dict) -> str:
        """Создаёт ОПТИМИЗИРОВАННЫЙ промпт для парного арбитража"""
        
        trading_mode = os.getenv("TRADING_MODE", "AGGRESSIVE_TEST")
        
        prompt = f"""
        ===== ДАННЫЕ ДЛЯ ПАРНОГО АРБИТРАЖА SBER/VTBR =====
        
        📊 ЦЕНЫ НА {market_data.get('timestamp', datetime.now().isoformat())}:
        - SBER: {market_data.get('prices', {}).get('SBER', 0):.2f} руб.
        - VTBR: {market_data.get('prices', {}).get('VTBR', 0):.3f} руб.
        - VTBR (нормализованный x1000): {market_data.get('vtbr_normalized', 0):.2f} руб.
        
        🔢 КЛЮЧЕВЫЕ МЕТРИКИ:
        - Соотношение SBER/VTBR: {market_data.get('current_ratio', 0):.4f}
        - Историческое среднее: {market_data.get('mean_ratio', 0):.4f}
        - Z-score отклонение: {market_data.get('z_score', 0):.2f}σ
        - Волатильность (σ): {market_data.get('std_ratio', 0):.4f}
        
        📈 ИСТОРИЯ СООТНОШЕНИЙ (последние {market_data.get('history_length', 0)} точек):
        {market_data.get('ratio_history_preview', 'Нет данных')}
        
        💰 ВИРТУАЛЬНЫЙ ПОРТФЕЛЬ:
        - Баланс: {market_data.get('balance', 100000):.0f} руб.
        - Текущие позиции: {json.dumps(market_data.get('positions', {}), ensure_ascii=False)}
        - Свободные средства: {market_data.get('available_cash', market_data.get('balance', 100000)):.0f} руб.
        
        ⚡ РЕЖИМ ТОРГОВЛИ: {trading_mode}
        
        🎯 ЦЕЛИ ДЛЯ РЕЖИМА {trading_mode}:
        - Take Profit: 2.5-3.5%
        - Stop Loss: 1.5-2.0%
        - Макс. позиция: 5-10% портфеля
        - Confidence для входа: >0.7
        
        📅 КОНТЕКСТ РЫНКА:
        - Время: {market_data.get('time_of_day', 'N/A')}
        - Активность: {market_data.get('market_hours', 'Основная сессия')}
        - Торговый день: {market_data.get('trading_day', 'Будний день')}
        
        🔍 АНАЛИЗИРУЙ:
        1. Текущее отклонение от исторической нормы
        2. Силу сигнала (|Z-score| > 2.0 = сильный)
        3. Направление арбитража:
           • Z-score < -2.0: VTBR недооценен → BUY VTBR / SELL SBER
           • Z-score > 2.0: VTBR переоценен → SELL VTBR / BUY SBER
        4. Риск-менеджмент (не более 10% портфеля в сделке)
        5. Время суток (пиковая ликвидность 10:00-17:00)
        
        🚨 ПРАВИЛА БЕЗОПАСНОСТИ:
        - Не открывать позиции если |Z-score| < 1.5
        - Всегда устанавливай TP и SL
        - Учитывай комиссии (0.05% Tinkoff)
        - Избегай торговли в первые/последние 30 минут
        
        🤔 РЕШЕНИЕ:
        Какие торговые сигналы генерируешь? Верни JSON с сигналами или пустой массив если нет возможностей.
        """
        return prompt
    
    def _parse_ai_response(self, response: str) -> List[Dict]:
        """Парсит ответ ИИ в структурированные сигналы с валидацией"""
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning("❌ ИИ не вернул JSON, ответ: " + response[:100])
                return []
            
            json_str = response[start_idx:end_idx]
            data = json.loads(json_str)
            
            signals = []
            for signal in data.get("signals", []):
                if all(key in signal for key in ['action', 'ticker', 'reason']):
                    
                    ticker = signal['ticker']
                    if ticker not in ['SBER', 'VTBR']:
                        logger.warning(f"⚠️ ИИ указал неизвестный тикер: {ticker}")
                        continue
                    
                    confidence = float(signal.get('confidence', 0.5))
                    if confidence < 0.7:
                        logger.info(f"⚠️ ИИ сигнал с low confidence {confidence:.2f}: {signal.get('reason', '')[:50]}")
                        continue
                    
                    action = signal['action'].upper()
                    if action not in ['BUY', 'SELL']:
                        continue
                    
                    price = signal.get('price', 0)
                    size = signal.get('size', 100 if ticker == 'VTBR' else 1)
                    
                    take_profit_percent = float(signal.get('take_profit_percent', 2.5))
                    stop_loss_percent = float(signal.get('stop_loss_percent', 1.5))
                    
                    take_profit = price * (1 + take_profit_percent/100) if action == 'BUY' else price * (1 - take_profit_percent/100)
                    stop_loss = price * (1 - stop_loss_percent/100) if action == 'BUY' else price * (1 + stop_loss_percent/100)
                    
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
                        'take_profit_percent': take_profit_percent,
                        'stop_loss_percent': stop_loss_percent,
                        'ai_generated': True,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    signals.append(validated_signal)
                    logger.info(f"✅ ИИ сигнал: {action} {ticker} x{size} (conf: {confidence:.2f}, TP: {take_profit_percent}%, SL: {stop_loss_percent}%)")
            
            market_analysis = data.get("market_analysis", "")
            if market_analysis:
                logger.info(f"🧠 Анализ ИИ: {market_analysis[:150]}...")
            
            return signals
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ ИИ вернул невалидный JSON. Ответ: {response[:200]}... Ошибка: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга ответа ИИ: {e}")
            return []
    
    def _create_cache_key(self, market_data: Dict) -> str:
        """Создаёт ключ для кэша на основе данных"""
        prices = market_data.get('prices', {})
        ratio = market_data.get('current_ratio', 0)
        z_score = market_data.get('z_score', 0)
        hour = datetime.now().hour
        
        return f"{hour}_{prices.get('SBER', 0):.1f}_{prices.get('VTBR', 0):.3f}_{ratio:.4f}_{z_score:.1f}"
