# news_fetcher.py - ПОЛНЫЙ ОБНОВЛЕННЫЙ С НОВЫМИ ИСТОЧНИКАМИ
import os
import aiohttp
import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)

class NewsFetcher:
    """Сборщик новостей с улучшенной фильтрацией и новыми API"""
    
    def __init__(self):
        # API ключи
        self.newsapi_key = os.getenv("NewsAPI")  # a9e56dc34399435e84a0492db880fbbf
        self.mediastack_key = os.getenv("mediastackAPI")  # 661a4c645e9a74be9bc6343c639eba1d
        self.zenserp_key = os.getenv("ZENSEPTAPI")  # d7207660-d210-11f0-9fa2-b34c09889c77
        
        # Улучшенные RSS источники (работающие)
        self.rss_feeds = {
            "investing_russia": "https://ru.investing.com/rss/news.rss",
            "finam_news": "https://www.finam.ru/international/analysis/conews/rsspoint/",
            "quote_rbc": "https://quote.rbc.ru/rss/news.rss",
            "banki_news": "https://www.banki.ru/xml/news.rss",
            "moex_simple": "https://www.moex.com/export/news.aspx?lang=ru"
        }
        
        # Фильтр ключевых слов ДЛЯ ФИНАНСОВЫХ новостей
        self.financial_keywords = [
            # Русские
            'акци', 'акций', 'акциями', 'дивиденд', 'дивиденды',
            'отчет', 'квартал', 'прибыль', 'выручка', 'убыток',
            'сбербанк', 'газпром', 'лукойл', 'норникель', 'ростелеком',
            'мосбиржа', 'втб', 'тинькофф', 'яндекс', 'озон',
            'бирж', 'котировк', 'инвест', 'трейд', 'портфел',
            'рубл', 'доллар', 'евро', 'нефт', 'газ', 'золот',
            'эмисси', 'облигац', 'фонд', 'рынок', 'экономик',
            'санкц', 'регулятор', 'цб', 'минфин', 'правительств',
            'покупк', 'продаж', 'сделка', 'слияни', 'поглощен',
            'рекоменду', 'аналитик', 'прогноз', 'ожидан', 'целев',
            # Английские (для investing.com)
            'stock', 'share', 'dividend', 'earnings', 'profit',
            'revenue', 'quarter', 'financial', 'deal', 'merger',
            'acquisition', 'growth', 'decline', 'bank', 'company',
            'market', 'exchange', 'invest', 'trade', 'russian',
            'moscow', 'moex', 'sberbank', 'gazprom', 'lukoil'
        ]
        
        logger.info("📰 NewsFetcher инициализирован с новыми API")
        logger.info(f"🔑 NewsAPI: {'✅' if self.newsapi_key else '❌'}")
        logger.info(f"🔑 MediaStack: {'✅' if self.mediastack_key else '❌'}")
        logger.info(f"🔑 RSS источников: {len(self.rss_feeds)}")
    
    def _is_financial_news(self, text: str) -> bool:
        """Фильтрация ТОЛЬКО финансовых новостей"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.financial_keywords)
    
    async def fetch_rss_feed(self, url: str, source_name: str) -> List[Dict]:
        """Получение новостей из RSS с фильтрацией"""
        articles = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10, ssl=False) as response:
                    if response.status == 200:
                        xml_content = await response.text()
                        
                        try:
                            root = ET.fromstring(xml_content)
                        except:
                            # Попробуем другой парсер если XML битый
                            return articles
                        
                        for item in root.findall('.//item'):
                            title_elem = item.find('title')
                            description_elem = item.find('description')
                            link_elem = item.find('link')
                            pub_date_elem = item.find('pubDate')
                            
                            if title_elem is not None:
                                title = title_elem.text or ''
                                description = description_elem.text if description_elem is not None else ''
                                
                                # Объединяем текст для фильтрации
                                full_text = f"{title} {description}".lower()
                                
                                # Фильтруем ТОЛЬКО финансовые новости
                                if self._is_financial_news(full_text):
                                    articles.append({
                                        'id': f"{source_name}_{pub_date_elem.text if pub_date_elem else ''}_{len(articles)}",
                                        'source': source_name,
                                        'title': title,
                                        'description': description,
                                        'content': description,
                                        'url': link_elem.text if link_elem is not None else '',
                                        'published_at': pub_date_elem.text if pub_date_elem else '',
                                        'source_name': source_name,
                                        'fetched_at': datetime.now().isoformat(),
                                        'is_financial': True
                                    })
                        
                        logger.debug(f"   ✅ {source_name}: {len(articles)} финансовых новостей")
            
        except asyncio.TimeoutError:
            logger.warning(f"⏰ {source_name}: таймаут")
        except Exception as e:
            logger.debug(f"🔧 {source_name} ошибка: {str(e)[:50]}")
        
        return articles
    
    async def fetch_newsapi(self) -> List[Dict]:
        """Получение новостей через NewsAPI (новое!)"""
        if not self.newsapi_key:
            logger.debug("⚠️ NewsAPI ключ не настроен")
            return []
        
        articles = []
        
        try:
            # Параметры для российских финансовых новостей
            params = {
                'apiKey': self.newsapi_key,
                'q': '(Russia OR Russian OR Moscow) AND (stocks OR shares OR market OR finance OR investment)',
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 20,
                'from': (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
            }
            
            url = "https://newsapi.org/v2/everything"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('status') == 'ok':
                            for article in data.get('articles', []):
                                title = article.get('title', '')
                                description = article.get('description', '')
                                content = article.get('content', '')
                                
                                full_text = f"{title} {description} {content}".lower()
                                
                                if self._is_financial_news(full_text):
                                    articles.append({
                                        'id': f"newsapi_{article.get('publishedAt', '')}_{len(articles)}",
                                        'source': 'newsapi',
                                        'title': title,
                                        'description': description,
                                        'content': content or description,
                                        'url': article.get('url', ''),
                                        'published_at': article.get('publishedAt', ''),
                                        'source_name': article.get('source', {}).get('name', 'newsapi'),
                                        'fetched_at': datetime.now().isoformat(),
                                        'is_financial': True,
                                        'api_source': 'newsapi'
                                    })
                            
                            logger.info(f"✅ NewsAPI: {len(articles)} финансовых новостей")
                        else:
                            logger.warning(f"⚠️ NewsAPI ошибка: {data.get('message', '')}")
                    else:
                        logger.warning(f"⚠️ NewsAPI HTTP ошибка: {response.status}")
            
        except asyncio.TimeoutError:
            logger.warning("⏰ NewsAPI: таймаут")
        except Exception as e:
            logger.error(f"❌ NewsAPI ошибка: {str(e)[:50]}")
        
        return articles
    
    async def fetch_mediastack(self) -> List[Dict]:
        """Получение новостей через MediaStack (новое!)"""
        if not self.mediastack_key:
            logger.debug("⚠️ MediaStack ключ не настроен")
            return []
        
        articles = []
        
        try:
            # Параметры для финансовых новостей
            params = {
                'access_key': self.mediastack_key,
                'keywords': 'finance,stocks,market,investment',
                'countries': 'ru',
                'languages': 'en,ru',
                'limit': 15,
                'sort': 'published_desc'
            }
            
            url = "http://api.mediastack.com/v1/news"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('data'):
                            for article in data.get('data', []):
                                title = article.get('title', '')
                                description = article.get('description', '')
                                
                                full_text = f"{title} {description}".lower()
                                
                                if self._is_financial_news(full_text):
                                    articles.append({
                                        'id': f"mediastack_{article.get('published_at', '')}_{len(articles)}",
                                        'source': 'mediastack',
                                        'title': title,
                                        'description': description,
                                        'content': description,
                                        'url': article.get('url', ''),
                                        'published_at': article.get('published_at', ''),
                                        'source_name': article.get('source', 'mediastack'),
                                        'fetched_at': datetime.now().isoformat(),
                                        'is_financial': True,
                                        'api_source': 'mediastack'
                                    })
                            
                            logger.info(f"✅ MediaStack: {len(articles)} финансовых новостей")
                        else:
                            logger.warning(f"⚠️ MediaStack ошибка: {data.get('error', {}).get('message', '')}")
                    else:
                        logger.warning(f"⚠️ MediaStack HTTP ошибка: {response.status}")
            
        except asyncio.TimeoutError:
            logger.warning("⏰ MediaStack: таймаут")
        except Exception as e:
            logger.error(f"❌ MediaStack ошибка: {str(e)[:50]}")
        
        return articles
    
    async def fetch_all_news(self) -> List[Dict]:
        """Получение ВСЕХ новостей из ВСЕХ источников параллельно"""
        logger.info("📥 Сбор финансовых новостей из всех источников...")
        
        all_articles = []
        
        # 1. RSS источники (работающие)
        rss_tasks = []
        for source_name, url in self.rss_feeds.items():
            rss_tasks.append(self.fetch_rss_feed(url, source_name))
        
        rss_results = await asyncio.gather(*rss_tasks, return_exceptions=True)
        
        for i, result in enumerate(rss_results):
            source_name = list(self.rss_feeds.keys())[i]
            if isinstance(result, list):
                all_articles.extend(result)
                logger.info(f"   📊 {source_name}: {len(result)} финансовых новостей")
            elif isinstance(result, Exception):
                logger.warning(f"   ⚠️ {source_name}: ошибка")
        
        # 2. NewsAPI (если есть ключ)
        if self.newsapi_key:
            newsapi_articles = await self.fetch_newsapi()
            all_articles.extend(newsapi_articles)
        
        # 3. MediaStack (если есть ключ)
        if self.mediastack_key:
            mediastack_articles = await self.fetch_mediastack()
            all_articles.extend(mediastack_articles)
        
        # Удаляем дубликаты по заголовку
        unique_articles = []
        seen_titles = set()
        
        for article in all_articles:
            title_key = article['title'][:80].lower().strip()
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_articles.append(article)
        
        removed = len(all_articles) - len(unique_articles)
        if removed > 0:
            logger.info(f"🔄 Удалено {removed} дубликатов")
        
        # Сортируем по времени (новые сначала)
        unique_articles.sort(
            key=lambda x: x.get('published_at', ''),
            reverse=True
        )
        
        logger.info(f"📊 ИТОГО: {len(unique_articles)} финансовых новостей")
        logger.info(f"   📰 Источники: RSS, {'NewsAPI, ' if self.newsapi_key else ''}{'MediaStack' if self.mediastack_key else ''}")
        
        return unique_articles[:30]  # Ограничиваем 30 новостями
    
    def get_source_stats(self) -> Dict:
        """Статистика по источникам"""
        return {
            'rss_feeds_count': len(self.rss_feeds),
            'newsapi_configured': bool(self.newsapi_key),
            'mediastack_configured': bool(self.mediastack_key),
            'zenserp_configured': bool(self.zenserp_key),
            'financial_keywords': len(self.financial_keywords),
            'total_sources': len(self.rss_feeds) + (1 if self.newsapi_key else 0) + (1 if self.mediastack_key else 0)
        }
