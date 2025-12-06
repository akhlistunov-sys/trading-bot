import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class SimpleAnalyzer:
    """Простой анализатор новостей без ИИ с быстрой предфильтрацией"""
    
    # Расширенный словарь тикеров
    TICKER_MAP = {
        # Банки
        'сбербанк': 'SBER', 'сбер': 'SBER', 'sber': 'SBER',
        'втб': 'VTBR', 'втб банк': 'VTBR', 'vtb': 'VTBR',
        'тинькофф': 'TCSG', 'tinkoff': 'TCSG', 'tcs': 'TCSG',
        'альфа банк': 'ALFA', 'альфа-банк': 'ALFA',
        
        # Нефтегаз
        'газпром': 'GAZP', 'газ': 'GAZP', 'gazprom': 'GAZP',
        'лукойл': 'LKOH', 'лук': 'LKOH', 'lukoil': 'LKOH',
        'роснефть': 'ROSN', 'роспефть': 'ROSN', 'rosneft': 'ROSN',
        'новатэк': 'NVTK', 'novatek': 'NVTK',
        'татнефть': 'TATN', 'tatneft': 'TATN',
        'башнефть': 'BANE', 'bashneft': 'BANE',
        'сургутнефтегаз': 'SNGS', 'сургут': 'SNGS',
        
        # Металлы и добыча
        'норильский никель': 'GMKN', 'норникель': 'GMKN', 'nornickel': 'GMKN',
        'алроса': 'ALRS', 'алроса': 'ALRS', 'alrosa': 'ALRS',
        'поллиметалл': 'POLY', 'polymetal': 'POLY',
        'северсталь': 'CHMF', 'severstal': 'CHMF',
        'нлмк': 'NLMK', 'nlmk': 'NLMK',
        'мечел': 'MTLR', 'mechel': 'MTLR',
        
        # Ритейл
        'магнит': 'MGNT', 'магнит': 'MGNT', 'magnit': 'MGNT',
        'х5 ритейл': 'FIVE', 'x5': 'FIVE', 'x5 retail': 'FIVE',
        'лэнта': 'LNTA', 'lenta': 'LNTA',
        'озон': 'OZON', 'ozon': 'OZON',
        'яндекс': 'YNDX', 'yandex': 'YNDX',
        'м.видео': 'MVID', 'мвидео': 'MVID',
        
        # Телеком и технологии
        'мтс': 'MTSS', 'mts': 'MTSS',
        'мосбиржа': 'MOEX', 'moex': 'MOEX',
        'ростелеком': 'RTKM', 'rostelecom': 'RTKM',
        
        # Химия и удобрения
        'фосагро': 'PHOR', 'phosagro': 'PHOR',
        'акрон': 'AKRN', 'akron': 'AKRN',
        'куйбышевазот': 'KAZT', 'kuybyshevazot': 'KAZT',
        
        # Авто
        'автоваз': 'AVAZ', 'lada': 'AVAZ',
        
        # Энергетика
        'россети': 'RSTI', 'rosseti': 'RSTI',
        'интер рао': 'IRAO', 'inter rao': 'IRAO',
        'фск': 'FEES', 'fsk': 'FEES',
    }
    
    # Ключевые слова для анализа тональности
    POSITIVE_WORDS = [
        'рост', 'прибыль', 'увеличил', 'повысил', 'дивиденды', 'рекомендует', 'успех',
        'рекорд', 'прогресс', 'улучшение', 'позитивный', 'оптимизм', 'сильный', 'стабильный',
        'выше ожиданий', 'превысил', 'улучшил', 'восстановление', 'процветание'
    ]
    
    NEGATIVE_WORDS = [
        'падение', 'убыток', 'снизил', 'сократил', 'проблемы', 'риски', 'сложности',
        'кризис', 'снижение', 'негативный', 'ухудшение', 'слабый', 'нестабильный',
        'ниже ожиданий', 'упал', 'провал', 'увольнения', 'банкротство', 'санкции'
    ]
    
    # Ключевые слова для типов событий
    EVENT_KEYWORDS = {
        'earnings_report': ['отчет', 'прибыль', 'выручка', 'квартал', 'финансовые результаты', 'ebitda'],
        'dividend': ['дивиденд', 'дивиденды', 'выплата', 'доходность'],
        'merger_acquisition': ['слияние', 'поглощение', 'покупка', 'продажа', 'сделка', 'активы'],
        'regulatory': ['регулятор', 'закон', 'правительство', 'санкции', 'запрет', 'лицензия'],
        'geopolitical': ['война', 'конфликт', 'политика', 'международный', 'санкции'],
        'corporate_action': ['совет директоров', 'собрание', 'голосование', 'эмиссия']
    }
    
    # Финансовые триггеры для быстрой предфильтрации
    FINANCIAL_TRIGGERS = [
        'дивиденд', 'отчет', 'прибыль', 'выручка', 'квартал', 'доход', 'убыток',
        'продаж', 'рост', 'падение', 'инвестиц', 'акци', 'облигац', 'дивиденд',
        'слияние', 'поглощение', 'дивиденд', 'выплата', 'совет директоров'
    ]
    
    # Приоритетные источники
    PRIORITY_SOURCES = ['MOEX', 'Интерфакс', 'РБК', 'Ведомости', 'Коммерсант']
    
    @staticmethod
    def should_process(news_item: Dict) -> bool:
        """Быстрая предфильтрация: стоит ли обрабатывать новость дальше?"""
        title = news_item.get('title', '').lower()
        source = news_item.get('source_name', '').lower()
        
        # 1. Проверка финансовых триггеров в заголовке
        has_trigger = any(trigger in title for trigger in SimpleAnalyzer.FINANCIAL_TRIGGERS)
        
        # 2. Проверка на наличие хотя бы одного тикера
        has_ticker = any(keyword in title for keyword in SimpleAnalyzer.TICKER_MAP.keys())
        
        # 3. Быстрая проверка тональности (хотя бы одна эмоциональная окраска)
        text = title
        has_sentiment = (any(word in text for word in SimpleAnalyzer.POSITIVE_WORDS) or 
                         any(word in text for word in SimpleAnalyzer.NEGATIVE_WORDS))
        
        # Решение: обрабатываем, если есть триггер И (тикер ИЛИ тональность)
        # Это позволяет пропускать общие рыночные обзоры, но ловить важные события
        return has_trigger and (has_ticker or has_sentiment)
    
    @staticmethod
    def analyze_news(news_item: Dict) -> Dict:
        """Простой анализ новости без ИИ"""
        
        # Быстрая предфильтрация
        if not SimpleAnalyzer.should_process(news_item):
            return {
                'tickers': [],
                'event_type': 'other',
                'impact_score': 1,
                'relevance_score': 10,
                'sentiment': 'neutral',
                'horizon': 'short_term',
                'summary': 'Не прошла предфильтрацию',
                'confidence': 0.1,
                'simple_analysis': True,
                'filtered_out': True
            }
        
        title = news_item.get('title', '').lower()
        content = news_item.get('content', '').lower() or news_item.get('description', '').lower()
        text = title + ' ' + content
        
        # Извлекаем тикеры
        tickers = []
        for keyword, ticker in SimpleAnalyzer.TICKER_MAP.items():
            if keyword in text:
                tickers.append(ticker)
        
        # Удаляем дубликаты
        tickers = list(set(tickers))
        
        # Анализ тональности
        positive_count = sum(1 for word in SimpleAnalyzer.POSITIVE_WORDS if word in text)
        negative_count = sum(1 for word in SimpleAnalyzer.NEGATIVE_WORDS if word in text)
        
        if positive_count > negative_count:
            sentiment = 'positive'
            impact_score = min(8, 4 + positive_count)
        elif negative_count > positive_count:
            sentiment = 'negative'
            impact_score = min(8, 4 + negative_count)
        else:
            sentiment = 'neutral'
            impact_score = 4
        
        # Определяем тип события
        event_type = 'market_update'
        max_keyword_count = 0
        
        for event_type_name, keywords in SimpleAnalyzer.EVENT_KEYWORDS.items():
            keyword_count = sum(1 for word in keywords if word in text)
            if keyword_count > max_keyword_count:
                max_keyword_count = keyword_count
                event_type = event_type_name
        
        # Релевантность
        relevance_score = 60 if tickers else 30
        if tickers and (positive_count > 0 or negative_count > 0):
            relevance_score = 75
        
        # Создаем summary
        if tickers:
            tickers_str = ', '.join(tickers[:3])
            summary = f"Локальный анализ: найдены {len(tickers)} тикеров ({tickers_str}), тональность: {sentiment}"
        else:
            summary = f"Локальный анализ: тикеры не найдены, тональность: {sentiment}"
        
        return {
            'tickers': tickers,
            'event_type': event_type,
            'impact_score': impact_score,
            'relevance_score': relevance_score,
            'sentiment': sentiment,
            'horizon': 'short_term',
            'summary': summary,
            'confidence': 0.6 if tickers else 0.3,
            'simple_analysis': True,
            'filtered_out': False
        }
