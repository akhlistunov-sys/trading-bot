import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class SimpleAnalyzer:
    """УЛУЧШЕННЫЙ анализатор с расширенным словарем тикеров"""
    
    # ==================== РАСШИРЕННЫЙ СЛОВАРЬ ТИКЕРОВ ====================
    TICKER_MAP = {
        # === БАНКИ ===
        'сбербанк': 'SBER', 'сбер': 'SBER', 'сбербанка': 'SBER', 'сбербанке': 'SBER',
        'sberbank': 'SBER', 'sber': 'SBER', 'сбера': 'SBER',
        'втб': 'VTBR', 'втб банк': 'VTBR', 'банк втб': 'VTBR', 'втб банка': 'VTBR',
        'vtb': 'VTBR', 'vtb bank': 'VTBR',
        'тинькофф': 'TCSG', 'тинькофф банк': 'TCSG', 'tinkoff': 'TCSG', 'tcs': 'TCSG',
        'tinkoff bank': 'TCSG', 'тинькоффа': 'TCSG',
        'альфа банк': 'ALFA', 'альфа-банк': 'ALFA', 'альфабанк': 'ALFA',
        'альфа банка': 'ALFA', 'alfa bank': 'ALFA',
        'открытие': 'FCIT', 'банк открытие': 'FCIT', 'открытия': 'FCIT',
        'россельхозбанк': 'RUGR', 'рсхб': 'RUGR', 'сельхозбанк': 'RUGR',
        'совкомбанк': 'SVCB', 'совком': 'SVCB',
        
        # === НЕФТЬ И ГАЗ ===
        'газпром': 'GAZP', 'газ': 'GAZP', 'газпрома': 'GAZP', 'газпроме': 'GAZP',
        'gazprom': 'GAZP', 'газпрому': 'GAZP',
        'лукойл': 'LKOH', 'лук': 'LKOH', 'лукойла': 'LKOH', 'lukoil': 'LKOH',
        'роснефть': 'ROSN', 'роспефть': 'ROSN', 'роснефти': 'ROSN',
        'rosneft': 'ROSN', 'нефтяная компания': 'ROSN',
        'новатэк': 'NVTK', 'novatek': 'NVTK', 'новатека': 'NVTK',
        'татнефть': 'TATN', 'tatneft': 'TATN', 'татнефти': 'TATN',
        'башнефть': 'BANE', 'bashneft': 'BANE', 'башнефти': 'BANE',
        'сургутнефтегаз': 'SNGS', 'сургут': 'SNGS', 'сургутнефтегаза': 'SNGS',
        'surgutneftegas': 'SNGS',
        
        # === МЕТАЛЛУРГИЯ И ГОРН. ДОБЫЧА ===
        'норильский никель': 'GMKN', 'норникель': 'GMKN', 'норникеля': 'GMKN',
        'nornickel': 'GMKN', 'никель': 'GMKN',
        'алроса': 'ALRS', 'алросы': 'ALRS', 'алросу': 'ALRS', 'alrosa': 'ALRS',
        'полиметалл': 'POLY', 'polymetal': 'POLY', 'полиметалла': 'POLY',
        'северсталь': 'CHMF', 'severstal': 'CHMF', 'северстали': 'CHMF',
        'нлмк': 'NLMK', 'nlmk': 'NLMK', 'нлмка': 'NLMK',
        'мечел': 'MTLR', 'mechel': 'MTLR', 'мечела': 'MTLR',
        'ммк': 'MAGN', 'магнитогорск': 'MAGN', 'магнитка': 'MAGN',
        'распадская': 'RASP', 'распадской': 'RASP',
        
        # === РИТЕЙЛ И ПОТРЕБ. СЕКТОР ===
        'магнит': 'MGNT', 'магнита': 'MGNT', 'magnit': 'MGNT',
        'х5 ритейл': 'FIVE', 'x5': 'FIVE', 'x5 ритейла': 'FIVE', 'x5 retail': 'FIVE',
        'пятерочка': 'FIVE', 'перекресток': 'FIVE', 'карусель': 'FIVE',
        'лэнта': 'LNTA', 'lenta': 'LNTA', 'лента': 'LNTA', 'ленты': 'LNTA',
        'озон': 'OZON', 'ozon': 'OZON', 'озона': 'OZON',
        'яндекс': 'YNDX', 'yandex': 'YNDX', 'яндекса': 'YNDX',
        'м.видео': 'MVID', 'мвидео': 'MVID', 'мвидео': 'MVID', 'эльдорадо': 'MVID',
        'wildberries': 'WB', 'вайлдбериз': 'WB', 'wildberry': 'WB',
        'детский мир': 'DSKY', 'детского мира': 'DSKY',
        'черкизово': 'GCHE', 'черкизова': 'GCHE',
        
        # === ТЕЛЕКОМ И ТЕХНОЛОГИИ ===
        'мтс': 'MTSS', 'mts': 'MTSS', 'мтс': 'MTSS',
        'мосбиржа': 'MOEX', 'moex': 'MOEX', 'мосбиржи': 'MOEX',
        'ростелеком': 'RTKM', 'rostelecom': 'RTKM', 'ростелекома': 'RTKM',
        'билайн': 'BEEL', 'beeline': 'BEEL', 'вымпелком': 'BEEL',
        'мегафон': 'MFON', 'megafon': 'MFON', 'мегафона': 'MFON',
        
        # === ХИМИЯ И УДОБРЕНИЯ ===
        'фосагро': 'PHOR', 'phosagro': 'PHOR', 'фосагро': 'PHOR',
        'акрон': 'AKRN', 'akron': 'AKRN', 'акрона': 'AKRN',
        'куйбышевазот': 'KAZT', 'kuybyshevazot': 'KAZT',
        'уралкалий': 'URKA', 'uralkali': 'URKA', 'уралкалия': 'URKA',
        
        # === ЭНЕРГЕТИКА ===
        'россети': 'RSTI', 'rosseti': 'RSTI', 'россетей': 'RSTI',
        'интер рао': 'IRAO', 'inter rao': 'IRAO', 'интер рао': 'IRAO',
        'фск': 'FEES', 'fsk': 'FEES', 'фск еэс': 'FEES',
        'русгидро': 'HYDR', 'rushydro': 'HYDR', 'русгидро': 'HYDR',
        'эн+': 'ENPL', 'енплюс': 'ENPL', 'en+': 'ENPL',
        
        # === ТРАНСПОРТ И ЛОГИСТИКА ===
        'аэрофлот': 'AFLT', 'aeroflot': 'AFLT', 'аэрофлота': 'AFLT',
        'новатэк': 'NVTK',  # уже есть, но для логистики
        'globaltrans': 'GLTR', 'глобалтранс': 'GLTR',
        
        # === ФИНАНСОВЫЕ ТЕРМИНЫ (ОБЩИЕ) ===
        'акция': 'SBER', 'акций': 'SBER', 'акциями': 'SBER',
        'дивиденд': 'SBER', 'дивиденды': 'SBER', 'дивидендов': 'SBER',
        'отчетность': 'SBER', 'квартал': 'SBER', 'прибыль': 'SBER',
        'выручка': 'SBER', 'убыток': 'SBER', 'ebitda': 'SBER',
        'рынок': 'MOEX', 'фондовый': 'MOEX', 'бирж': 'MOEX',
        'инвестор': 'SBER', 'инвестиции': 'SBER', 'инвестицион': 'SBER',
        'трейдер': 'MOEX', 'трейдинг': 'MOEX', 'торговля': 'MOEX',
        'портфель': 'SBER', 'котировки': 'MOEX', 'листинг': 'MOEX',
        'эмиссия': 'SBER', 'облигации': 'SBER', 'купон': 'SBER',
        'дивидендная': 'SBER', 'дивидендную': 'SBER',
        
        # === РЕГУЛЯТОРЫ И ПРАВИТЕЛЬСТВО ===
        'цб': 'SBER', 'центральный банк': 'SBER', 'банк россии': 'SBER',
        'минфин': 'SBER', 'министерство финансов': 'SBER',
        'правительство': 'SBER', 'правительства': 'SBER',
        'санкции': 'SBER', 'санкцион': 'SBER', 'ограничен': 'SBER',
        
        # === МЕДИЦИНА И ФАРМА ===
        'фармацевт': 'PHOR', 'лекарств': 'PHOR', 'вакцин': 'PHOR',
        'биотехнологи': 'PHOR', 'медицинск': 'PHOR', 'здравоохран': 'PHOR',
        'аптек': 'MGNT', 'лечени': 'MGNT', 'здоровь': 'MGNT',
        'диагностик': 'MGNT', 'больниц': 'MGNT', 'поликлиник': 'MGNT',
        
        # === СТРОИТЕЛЬСТВО И НЕДВИЖИМОСТЬ ===
        'пик': 'PIKK', 'pikk': 'PIKK', 'пика': 'PIKK',
        'лср': 'LSRG', 'lsr': 'LSRG', 'лср групп': 'LSRG',
        'эталон': 'ETLN', 'etalon': 'ETLN', 'эталона': 'ETLN',
        'самолет': 'SMLT', 'samolyot': 'SMLT', 'самолета': 'SMLT',
        
        # === АВТОМОБИЛИ ===
        'автоваз': 'AVAZ', 'lada': 'AVAZ', 'ваз': 'AVAZ', 'лада': 'AVAZ',
        'газ': 'GAZ', 'газ группа': 'GAZ', 'газа': 'GAZ',
        'соллерс': 'SVAV', 'sollers': 'SVAV', 'соллерса': 'SVAV',
    }
    
    # Ключевые слова для быстрой предфильтрации (РАСШИРЕННЫЕ)
    QUICK_FILTER_KEYWORDS = [
        'акци', 'дивиденд', 'отчет', 'прибыль', 'выручка', 'убыток',
        'квартал', 'годовой', 'финансов', 'результат', 'ebitda',
        'покупк', 'продаж', 'сделка', 'слияни', 'поглощен',
        'рост', 'падение', 'увелич', 'снижен', 'повышен', 'понижен',
        'рекоменду', 'советует', 'предлагает', 'ожидает', 'прогноз',
        'санкц', 'запрет', 'лиценз', 'регулятор', 'правительств',
        'закон', 'постановлен', 'распоряжен',
        'война', 'конфликт', 'политика', 'международн', 'санкци',
        'рынок', 'бирж', 'инвест', 'трейд', 'торговл', 'котировк',
        'рубл', 'доллар', 'евро', 'нефт', 'газ', 'золот', 'серебр',
        'эмисси', 'облигац', 'купон', 'погашен', 'выпуск',
        'дивидендн', 'выплат', 'доходност',
        'банк', 'кредит', 'ипотек', 'вклад', 'депозит',
        'компани', 'корпорац', 'холдинг', 'групп', 'предприят',
        'совет директоров', 'собрание', 'голосование',
        'аналитик', 'эксперт', 'оптимизм', 'пессимизм'
    ]
    
    @staticmethod
    def should_analyze_further(news_item: Dict) -> bool:
        """Быстрая предфильтрация финансовых новостей"""
        title = news_item.get('title', '').lower()
        content = news_item.get('content', '').lower() or news_item.get('description', '').lower()
        text = title + ' ' + content[:300]
        
        # 1. Проверяем наличие финансовых триггеров
        has_keywords = any(keyword in text for keyword in SimpleAnalyzer.QUICK_FILTER_KEYWORDS)
        if not has_keywords:
            return False
        
        # 2. Быстрый поиск тикеров
        has_tickers = any(keyword in text for keyword in SimpleAnalyzer.TICKER_MAP.keys())
        if not has_tickers:
            return False
        
        return True
    
    @staticmethod
    def analyze_news(news_item: Dict) -> Dict:
        """Полный анализ новости"""
        title = news_item.get('title', '').lower()
        content = news_item.get('content', '').lower() or news_item.get('description', '').lower()
        text = title + ' ' + content
        
        # Извлекаем тикеры (РАСШИРЕННЫЙ ПОИСК)
        tickers = []
        for keyword, ticker in SimpleAnalyzer.TICKER_MAP.items():
            if keyword in text:
                tickers.append(ticker)
        
        # Удаляем дубликаты
        tickers = list(set(tickers))
        
        # Более агрессивный анализ тональности
        positive_words = ['рост', 'прибыль', 'увелич', 'повыш', 'рекорд', 'успех', 
                         'прогресс', 'улучшен', 'позитив', 'оптимизм', 'сильн', 'стабильн']
        negative_words = ['падение', 'убыток', 'снижен', 'сокращен', 'проблем', 'риск',
                         'сложност', 'кризис', 'негатив', 'ухудшен', 'слаб', 'нестабильн']
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            sentiment = 'positive'
            impact_score = min(8, 5 + positive_count)
        elif negative_count > positive_count:
            sentiment = 'negative'
            impact_score = min(8, 5 + negative_count)
        else:
            sentiment = 'neutral'
            impact_score = 5
        
        # Определяем тип события
        event_type = 'market_update'
        if 'дивиденд' in text:
            event_type = 'dividend'
        elif 'отчет' in text or 'квартал' in text:
            event_type = 'earnings_report'
        elif 'слияни' in text or 'поглощен' in text:
            event_type = 'merger_acquisition'
        elif 'санкц' in text or 'регулятор' in text:
            event_type = 'regulatory'
        
        # Релевантность и confidence
        relevance_score = 70 if tickers else 40
        if tickers and (positive_count > 0 or negative_count > 0):
            relevance_score = 85
        
        confidence = 0.4 + min(0.4, (positive_count + negative_count) * 0.05)
        if tickers:
            confidence += 0.3
        confidence = min(0.9, confidence)  # Ограничиваем
        
        # Summary
        if tickers:
            tickers_str = ', '.join(tickers[:3])
            summary = f"Найдены тикеры: {tickers_str}, тональность: {sentiment}"
        else:
            summary = f"Тикеры не найдены, тональность: {sentiment}"
        
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
