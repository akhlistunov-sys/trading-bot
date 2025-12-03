# ai_core.py - ПОЛНЫЙ МОДУЛЬ AI-ТРЕЙДИНГА
import os
import json
import logging
import asyncio
import httpx
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MarketState:
    """Структура для данных рынка"""
    timestamp: str
    prices: Dict[str, float]
    portfolio_cash: float
    positions: Dict[str, int]
    price_history: Dict[str, List[float]]
    signals: List[Dict] = None

class AITradingCore:
    """Ядро AI-трейдинга с полной автономностью"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("❌ OPENROUTER_API_KEY не найден!")
        
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "google/gemini-2.0-flash-exp:free"  # Работает стабильно, хороша для JSON
        
        # Конфигурация системы
        self.config = {
            "max_risk_per_trade": 0.02,  # 2% риска на сделку
            "min_position_value": 5000,   # Минимальная сумма позиции
            "max_positions": 3,
            "commission": 0.0005,         # 0.05% комиссия
        }
        
        # История для контекста
        self.trade_history = []
        self.performance = {
            "total_trades": 0,
            "total_profit": 0.0,
            "win_rate": 0.0
        }
    
    def collect_market_data(self, tinkoff_client, instruments: Dict) -> MarketState:
        """Собирает ВСЕ данные рынка для AI"""
        prices = {}
        history = {}
        
        for ticker, figi in instruments.items():
            try:
                # Получаем текущую цену
                last_price = tinkoff_client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    current_price = price_obj.units + price_obj.nano / 1e9
                    prices[ticker] = current_price
                    
                    # Сохраняем в историю (симуляция - в реальности нужно хранить в БД)
                    if ticker not in history:
                        history[ticker] = []
                    history[ticker].append(current_price)
                    if len(history[ticker]) > 50:
                        history[ticker].pop(0)
                        
            except Exception as e:
                logger.error(f"Ошибка сбора данных {ticker}: {e}")
                prices[ticker] = 0.0
        
        return MarketState(
            timestamp=datetime.now().isoformat(),
            prices=prices,
            portfolio_cash=100000,  # Заглушка - замени на реальный портфель
            positions={},           # Заглушка
            price_history=history
        )
    
    def _create_ai_prompt(self, market: MarketState) -> str:
        """Создает детальный промпт для AI на основе ВСЕХ данных"""
        
        # Анализ рыночных условий
        price_analysis = []
        for ticker, price in market.prices.items():
            if ticker in market.price_history and len(market.price_history[ticker]) > 5:
                history = market.price_history[ticker]
                change = ((price - history[-5]) / history[-5]) * 100 if history[-5] > 0 else 0
                price_analysis.append(f"{ticker}: {price:.2f} руб. ({change:+.2f}%)")
        
        # Арбитражные пары
        arbitrage_info = []
        pairs = [("SBER", "VTBR"), ("GAZP", "LKOH")]
        for ticker1, ticker2 in pairs:
            if ticker1 in market.prices and ticker2 in market.prices:
                ratio = market.prices[ticker1] / (market.prices[ticker2] * 1000) if ticker2 == "VTBR" else market.prices[ticker1] / market.prices[ticker2]
                arbitrage_info.append(f"{ticker1}/{ticker2}: {ratio:.4f}")
        
        prompt = f"""
        # ТОРГОВАЯ СЕССИЯ - AI CORE
        
        ## КОНТЕКСТ СИСТЕМЫ:
        - Время: {market.timestamp}
        - Баланс: {market.portfolio_cash:.2f} руб.
        - Макс. риск на сделку: {self.config['max_risk_per_trade']*100}%
        - Комиссия: {self.config['commission']*100}%
        
        ## РЫНОЧНЫЕ ДАННЫЕ:
        ### Текущие цены:
        {chr(10).join(f'- {item}' for item in price_analysis)}
        
        ### Арбитражные соотношения:
        {chr(10).join(f'- {item}' for item in arbitrage_info)}
        
        ### Историческая волатильность (последние 20 точек):
        {self._calculate_volatility(market.price_history)}
        
        ## ИСТОРИЯ ПРОИЗВОДИТЕЛЬНОСТИ:
        - Всего сделок: {self.performance['total_trades']}
        - Общая прибыль: {self.performance['total_profit']:.2f} руб.
        - Win Rate: {self.performance['win_rate']:.1%}
        
        ## ТВОЯ ЗАДАЧА:
        1. Проанализируй все данные выше
        2. Определи лучшие торговые возможности
        3. Верни ТОЛЬКО JSON с сигналами
        
        ## ФОРМАТ ОТВЕТА (ТОЛЬКО JSON):
        {{
            "signals": [
                {{
                    "action": "BUY" или "SELL",
                    "ticker": "SBER",
                    "price": 300.50,
                    "size": 3,
                    "confidence": 0.85,
                    "reason": "Краткое логическое обоснование",
                    "meta": {{
                        "take_profit": 305.0,
                        "stop_loss": 298.0,
                        "timeframe": "5min"
                    }}
                }}
            ],
            "market_regime": "trending" или "ranging" или "volatile",
            "risk_level": "low" или "medium" или "high"
        }}
        
        ## ПРАВИЛА:
        - Рискуй не более {self.config['max_risk_per_trade']*100}% капитала на сделку
        - Учитывай комиссию {self.config['commission']*100}%
        - Минимальная сумма позиции: {self.config['min_position_value']} руб.
        - Максимум {self.config['max_positions']} одновременных позиций
        - Для VTBR используй коэффициент 1000 (1 SBER ≈ 1000 VTBR)
        """
        
        return prompt
    
    def _calculate_volatility(self, history: Dict) -> str:
        """Рассчитывает волатильность для отчета"""
        result = []
        for ticker, prices in history.items():
            if len(prices) > 10:
                returns = [(prices[i] - prices[i-1])/prices[i-1] for i in range(1, len(prices))]
                if returns:
                    vol = (sum(r**2 for r in returns) / len(returns)) ** 0.5
                    result.append(f"- {ticker}: {vol*100:.2f}%")
        return chr(10).join(result) if result else "Недостаточно данных"
    
    async def get_ai_decisions(self, market: MarketState) -> Dict:
        """Основная функция: получает решения от AI"""
        
        prompt = self._create_ai_prompt(market)
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    url=self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://trading-bot.ai",  # Опционально
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system", 
                                "content": "Ты — ядро автономной AI-трейдинговой системы. Анализируй данные и возвращай ТОЛЬКО JSON с решениями. Никакого текста кроме JSON."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,  # Низкая температура для консистентности
                        "max_tokens": 2000,
                        "response_format": {"type": "json_object"}
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result["choices"][0]["message"]["content"]
                    
                    try:
                        decisions = json.loads(ai_response)
                        logger.info(f"✅ AI сгенерировал {len(decisions.get('signals', []))} сигналов")
                        return decisions
                    except json.JSONDecodeError:
                        logger.error(f"❌ AI вернул не JSON: {ai_response[:200]}")
                        # Попытка извлечь JSON из текста
                        import re
                        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                        if json_match:
                            return json.loads(json_match.group())
                        return {"signals": [], "error": "invalid_json"}
                        
                else:
                    logger.error(f"❌ OpenRouter ошибка {response.status_code}: {response.text}")
                    return {"signals": [], "error": f"api_{response.status_code}"}
                    
            except Exception as e:
                logger.error(f"❌ Ошибка соединения: {e}")
                return {"signals": [], "error": str(e)}
