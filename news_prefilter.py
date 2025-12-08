@app.route('/test_prefilter')
async def test_prefilter():
    """Тест префильтра на реальных новостях"""
    all_news = await news_fetcher.fetch_all_news()
    
    test_results = []
    for i, news in enumerate(all_news[:10]):
        title = news.get('title', '')[:80]
        result = {
            'index': i,
            'title': title,
            'source': news.get('source'),
            'tradable': news_prefilter.is_tradable(news),
            'analysis': news_prefilter._analyze_rejection(news) if i < 3 else []
        }
        test_results.append(result)
    
    return jsonify({
        "prefilter_test": "v2.0",
        "total_news": len(all_news),
        "sample_size": 10,
        "results": test_results,
        "stats": news_prefilter.get_filter_stats(all_news[:10])
    })
