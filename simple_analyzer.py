import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class SimpleAnalyzer:
    """Простой анализатор новостей с быстрой предфильтрацией"""
    
    # Расширенный словарь тикеров
        # Расширенный словарь тикеров (добавлены синонимы и общие термины)
    TICKER_MAP = {
        # Банки и фин. организации
        'сбербанк': 'SBER', 'сбер': 'SBER', 'sber': 'SBER', 'сбербанка': 'SBER', 'сбербанке': 'SBER',
        'втб': 'VTBR', 'втб банк': 'VTBR', 'втб банка': 'VTBR', 'vtb': 'VTBR', 'банк втб': 'VTBR',
        'тинькофф': 'TCSG', 'tinkoff': 'TCSG', 'tcs': 'TCSG', 'тинькофф банк': 'TCSG', 'tinkoff bank': 'TCSG',
        'альфа банк': 'ALFA', 'альфа-банк': 'ALFA', 'альфабанк': 'ALFA', 'альфа банка': 'ALFA',
        'банк': 'SBER',  # Общий термин
        'кредит': 'SBER',  # Общий финансовый термин
        
        # Нефтегазовый сектор
        'газпром': 'GAZP', 'газ': 'GAZP', 'gazprom': 'GAZP', 'газпрома': 'GAZP', 'газпроме': 'GAZP',
        'нефть': 'GAZP', 'нефти': 'GAZP', 'нефтяной': 'GAZP',  # Общие термины
        'лукойл': 'LKOH', 'лук': 'LKOH', 'lukoil': 'LKOH', 'лукойла': 'LKOH',
        'роснефть': 'ROSN', 'роспефть': 'ROSN', 'rosneft': 'ROSN', 'роснефти': 'ROSN',
        'нефтяная компания': 'ROSN',  # Общий термин
        'новатэк': 'NVTK', 'novatek': 'NVTK', 'новатека': 'NVTK',
        'татнефть': 'TATN', 'tatneft': 'TATN', 'татнефти': 'TATN',
        'башнефть': 'BANE', 'bashneft': 'BANE',
        'сургутнефтегаз': 'SNGS', 'сургут': 'SNGS', 'сургутнефтегаза': 'SNGS',
        'газовая компания': 'GAZP',  # Общий термин
        
        # Металлургия и добыча
        'норильский никель': 'GMKN', 'норникель': 'GMKN', 'nornickel': 'GMKN', 'норникеля': 'GMKN',
        'никель': 'GMKN',  # Общий термин
        'алроса': 'ALRS', 'алроса': 'ALRS', 'alrosa': 'ALRS', 'алросы': 'ALRS',
        'бриллиант': 'ALRS', 'алмаз': 'ALRS',  # Общие термины
        'поллиметалл': 'POLY', 'polymetal': 'POLY', 'полиметалл': 'POLY',
        'золото': 'POLY', 'золотодобыча': 'POLY',  # Общие термины
        'северсталь': 'CHMF', 'severstal': 'CHMF', 'северстали': 'CHMF',
        'сталь': 'CHMF', 'металлург': 'CHMF',  # Общие термины
        'нлмк': 'NLMK', 'nlmk': 'NLMK',
        'мечел': 'MTLR', 'mechel': 'MTLR', 'мечела': 'MTLR',
        
        # Ритейл и потребительский сектор
        'магнит': 'MGNT', 'магнит': 'MGNT', 'magnit': 'MGNT', 'магнита': 'MGNT',
        'супермаркет': 'MGNT', 'ритейл': 'MGNT',  # Общие термины
        'х5 ритейл': 'FIVE', 'x5': 'FIVE', 'x5 retail': 'FIVE', 'х5': 'FIVE', 'х5 ритейла': 'FIVE',
        'пятерочка': 'FIVE', 'перекресток': 'FIVE',  # Магазины сети X5
        'лэнта': 'LNTA', 'lenta': 'LNTA', 'лента': 'LNTA',
        'озон': 'OZON', 'ozon': 'OZON', 'озона': 'OZON',
        'яндекс': 'YNDX', 'yandex': 'YNDX', 'яндекса': 'YNDX',
        'м.видео': 'MVID', 'мвидео': 'MVID', 'м.видео': 'MVID',
        'эльдорадо': 'MVID',  # Входит в ту же группу
        
        # Телеком и технологии
        'мтс': 'MTSS', 'mts': 'MTSS', 'мтс': 'MTSS',
        'мосбиржа': 'MOEX', 'moex': 'MOEX', 'мосбиржи': 'MOEX',
        'биржа': 'MOEX',  # Общий термин
        'ростелеком': 'RTKM', 'rostelecom': 'RTKM', 'ростелекома': 'RTKM',
        'интернет': 'RTKM', 'телеком': 'RTKM',  # Общие термины
        
        # Химия и удобрения
        'фосагро': 'PHOR', 'phosagro': 'PHOR', 'фосагро': 'PHOR',
        'акрон': 'AKRN', 'akron': 'AKRN', 'акрона': 'AKRN',
        'куйбышевазот': 'KAZT', 'kuybyshevazot': 'KAZT',
        'удобрени': 'PHOR',  # Общий термин
        
        # Автомобилестроение
        'автоваз': 'AVAZ', 'lada': 'AVAZ', 'ваз': 'AVAZ', 'лада': 'AVAZ',
        'автомобил': 'AVAZ',  # Общий термин
        
        # Энергетика
        'россети': 'RSTI', 'rosseti': 'RSTI', 'россетей': 'RSTI',
        'интер рао': 'IRAO', 'inter rao': 'IRAO', 'интер рао': 'IRAO',
        'фск': 'FEES', 'fsk': 'FEES',
        'электроэнерг': 'FEES',  # Общий термин
        
        # Общие финансовые термины (добавлены для увеличения coverage)
        'акция': 'SBER', 'акций': 'SBER', 'акциями': 'SBER',
        'дивиденд': 'SBER', 'дивиденды': 'SBER', 'дивидендов': 'SBER',
        'отчетность': 'SBER', 'квартал': 'SBER', 'прибыль': 'SBER',
        'рынок': 'MOEX', 'фондовый рынок': 'MOEX',
        'инвестор': 'SBER', 'инвестиции': 'SBER',
        'котировки': 'MOEX', 'торги': 'MOEX',
    }
    
    # Ключевые слова для БЫСТРОЙ предфильтрации - новость должна содержать хотя бы одно из этих слов
    QUICK_FILTER_KEYWORDS = [
        # Финансовые триггеры
        'дивиденд', 'отчет', 'прибыль', 'выручка', 'квартал', 'годовой',
        'продаж', 'покупк', 'сделка', 'актив', 'акции', 'облигац',
        # Действия
        'рост', 'падение', 'увеличил', 'снизил', 'повысил', 'понизил',
        'рекомендует', 'советует', 'предлагает', 'ожидает',
        # События
        'слияние', 'поглощение', 'банкротство', 'санкц', 'запрет',
        'лиценз', 'регулятор', 'правительств', 'закон',
        # Общие рыночные
        'рынок', 'бирж', 'инвест', 'трейд', 'торговл', 'котировк'
    ]
    
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
    
    @staticmethod
    def should_analyze_further(news_item: Dict) -> bool:
        """Быстрая предфильтрация: стоит ли анализировать новость глубже?"""
        title = news_item.get('title', '').lower()
        content = news_item.get('content', '').lower() or news_item.get('description', '').lower()
        text = title + ' ' + content[:200]  # Смотрим только начало для скорости
        
        # 1. Проверяем наличие финансовых триггеров
        has_keywords = any(keyword in text for keyword in SimpleAnalyzer.QUICK_FILTER_KEYWORDS)
        if not has_keywords:
            logger.debug(f"⏩ Пропускаем новость (нет ключевых слов): {title[:50]}...")
            return False
        
        # 2. Быстрый поиск тикеров
        has_tickers = any(keyword in text for keyword in SimpleAnalyzer.TICKER_MAP.keys())
        if not has_tickers:
            logger.debug(f"⏩ Пропускаем новость (нет тикеров): {title[:50]}...")
            return False
        
        # 3. Проверяем источник (опционально)
        source = news_item.get('source', '').lower()
        if 'блог' in source or 'форум' in source:
            logger.debug(f"⚠️ Новость из ненадежного источника: {source}")
            return False  # или можно возвращать True, но с пониженным приоритетом
        
        return True
    
    @staticmethod
    def analyze_news(news_item: Dict) -> Dict:
        """Полный анализ новости после предфильтрации"""
        
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
        
        # Confidence (уверенность) зависит от количества найденных триггеров
        confidence = 0.3 + min(0.4, (positive_count + negative_count) * 0.05)
        if tickers:
            confidence += 0.3
        
        # Создаем summary
        if tickers:
            tickers_str = ', '.join(tickers[:3])
            summary = f"Локальный анализ: найдены {len(tickers)} тикеров ({tickers_str}), тональность: {sentiment}, уверенность: {confidence:.1f}"
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
            'confidence': confidence,
            'simple_analysis': True
        }
