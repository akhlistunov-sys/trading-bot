"""
Конфигурация AI Новостного Трейдера
"""

import os
from typing import Dict, Any

class Config:
    """Класс конфигурации системы"""
    
    # Режимы работы
    TRADING_MODES = {
        'AGGRESSIVE_TEST': {
            'position_size_multiplier': 1.0,
            'risk_multiplier': 1.0,
            'min_confidence': 0.65,
            'description': 'Агрессивное тестирование стратегии'
        },
        'CONSERVATIVE': {
            'position_size_multiplier': 0.5,
            'risk_multiplier': 0.7,
            'min_confidence': 0.75,
            'description': 'Консервативная торговля'
        },
        'PASSIVE_MONITOR': {
            'position_size_multiplier': 0.0,
            'risk_multiplier': 0.0,
            'min_confidence': 0.0,
            'description': 'Пассивный мониторинг без торговли'
        }
    }
    
    # Настройки источников новостей
    NEWS_SOURCES = {
        'NEWSAPI': {
            'enabled': bool(os.getenv('NewsAPI')),
            'max_articles': 20,
            'timeframe_hours': 24
        },
        'ZENSERP': {
            'enabled': bool(os.getenv('ZENSEPTAPI')),
            'max_articles': 15,
            'timeframe': 'qdr:d'  # За последний день
        },
        'MOEX_RSS': {
            'enabled': True,
            'feeds': {
                'all_news': 'https://moex.com/export/news.aspx?cat=100',
                'main_news': 'https://moex.com/export/news.aspx?cat=101'
            }
        }
    }
    
    # Настройки ИИ
    AI_CONFIG = {
        'model_priority': [
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen3-235b-a22b:free",
            "google/gemma-3-27b:free",
            "meta-llama/llama-3.2-3b-instruct:free"
        ],
        'timeout_seconds': 30,
        'max_retries': 3,
        'temperature': 0.1,
        'max_tokens': 800
    }
    
    # Настройки риск-менеджмента
    RISK_CONFIG = {
        'max_position_size_percent': 10.0,
        'min_position_size_percent': 1.0,
        'max_stop_loss_percent': 5.0,
        'min_stop_loss_percent': 1.0,
        'max_drawdown_percent': 20.0,
        'risk_reward_ratio': 2.0,
        'max_positions_count': 5
    }
    
    # Настройки портфеля
    PORTFOLIO_CONFIG = {
        'initial_capital': 100000,
        'virtual_mode': True,
        'commission_percent': 0.05,
        'min_trade_value': 1000
    }
    
    @classmethod
    def get_current_mode(cls) -> Dict[str, Any]:
        """Получение текущего режима торговли"""
        mode = os.getenv('TRADING_MODE', 'AGGRESSIVE_TEST')
        return cls.TRADING_MODES.get(mode, cls.TRADING_MODES['AGGRESSIVE_TEST'])
    
    @classmethod
    def get_check_interval(cls) -> int:
        """Получение интервала проверки в минутах"""
        return int(os.getenv('CHECK_INTERVAL_MINUTES', 15))
    
    @classmethod
    def is_ai_enabled(cls) -> bool:
        """Проверка доступности ИИ"""
        return bool(os.getenv('OPENROUTER_API_TOKEN'))
    
    @classmethod
    def is_tinkoff_enabled(cls) -> bool:
        """Проверка доступности Tinkoff API"""
        return bool(os.getenv('TINKOFF_API_TOKEN'))
