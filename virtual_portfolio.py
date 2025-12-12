# virtual_portfolio.py - ПОЛНЫЙ ФАЙЛ С МЕТОДОМ get_portfolio_analytics
import datetime
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class VirtualPortfolioPro:
    """Продвинутый виртуальный портфель для тестирования стратегий"""
    
    def __init__(self, initial_capital: float = 100000):
        self.cash = initial_capital
        self.positions = {}
        self.trade_history = []
        self.initial_capital = initial_capital
        self.total_trades = 0
        self.winning_trades = 0
        self.total_profit = 0
        self.max_drawdown = 0
        self.peak_value = initial_capital
        
        logger.info(f"💰 Виртуальный портфель создан: {initial_capital:.2f} руб.")
    
    def check_exit_conditions(self, current_prices: Dict) -> List[Dict]:
        """Проверка условий выхода из позиций (тейк-профит, стоп-лосс, трейлинг)"""
        
        exit_signals = []
        
        for ticker, pos_info in list(self.positions.items()):
            if ticker in current_prices:
                current_price = current_prices[ticker]
                avg_price = pos_info['avg_price']
                size = pos_info['size']
                
                profit_per_share = current_price - avg_price
                total_profit = profit_per_share * size
                profit_percent = (profit_per_share / avg_price) * 100
                
                # Получаем параметры выхода из позиции
                stop_loss = pos_info.get('stop_loss')
                take_profit = pos_info.get('take_profit')
                trailing_start = pos_info.get('trailing_start', 2.0)
                trailing_step = pos_info.get('trailing_step', 0.7)
                
                # Проверка трейлинг-стопа
                if 'trailing_stop' in pos_info and current_price >= pos_info['trailing_stop']:
                    # Обновляем трейлинг-стоп
                    new_trailing_stop = current_price * (1 - trailing_step / 100)
                    if new_trailing_stop > pos_info['trailing_stop']:
                        self.positions[ticker]['trailing_stop'] = new_trailing_stop
                
                # Если прибыль достигла trailing_start, активируем трейлинг-стоп
                elif profit_percent >= trailing_start and 'trailing_stop' not in pos_info:
                    trailing_stop = current_price * (1 - trailing_step / 100)
                    self.positions[ticker]['trailing_stop'] = trailing_stop
                    logger.info(f"📈 Активирован трейлинг-стоп для {ticker}: {trailing_stop:.2f}")
                
                # Проверка тейк-профита
                if take_profit and current_price >= take_profit:
                    exit_signals.append({
                        'action': 'SELL',
                        'ticker': ticker,
                        'price': current_price,
                        'size': size,
                        'strategy': 'Take Profit',
                        'reason': f"✅ ТЕЙК-ПРОФИТ {pos_info.get('take_profit_percent', 3.0)}% достигнут",
                        'profit': total_profit,
                        'profit_percent': profit_percent,
                        'position_type': 'full_exit',
                        'signal_source': 'exit_condition'
                    })
                
                # Проверка стоп-лосса
                elif stop_loss and current_price <= stop_loss:
                    exit_signals.append({
                        'action': 'SELL',
                        'ticker': ticker,
                        'price': current_price,
                        'size': size,
                        'strategy': 'Stop Loss',
                        'reason': f"🚨 СТОП-ЛОСС {pos_info.get('stop_loss_percent', 1.5)}% сработал",
                        'profit': total_profit,
                        'profit_percent': profit_percent,
                        'position_type': 'full_exit',
                        'signal_source': 'exit_condition'
                    })
                
                # Проверка трейлинг-стопа
                elif 'trailing_stop' in pos_info and current_price <= pos_info['trailing_stop']:
                    exit_signals.append({
                        'action': 'SELL',
                        'ticker': ticker,
                        'price': current_price,
                        'size': size,
                        'strategy': 'Trailing Stop',
                        'reason': f"📉 ТРЕЙЛИНГ-СТОП сработал на {profit_percent:.1f}% прибыли",
                        'profit': total_profit,
                        'profit_percent': profit_percent,
                        'position_type': 'full_exit',
                        'signal_source': 'exit_condition'
                    })
                
                # Частичный выход при хорошей прибыли
                elif profit_percent >= 5.0 and size >= 2:
                    # Продаём 1/3 позиции для фиксации прибыли
                    exit_size = int(size * 0.33)
                    if exit_size >= 1:
                        exit_signals.append({
                            'action': 'SELL',
                            'ticker': ticker,
                            'price': current_price,
                            'size': exit_size,
                            'strategy': 'Partial Profit Taking',
                            'reason': f"⚡ Частичный выход при {profit_percent:.1f}% прибыли",
                            'profit': total_profit * (exit_size / size),
                            'profit_percent': profit_percent,
                            'position_type': 'partial_exit',
                            'signal_source': 'profit_taking'
                        })
        
        return exit_signals
    
    def execute_trade(self, signal: Dict, current_price: float) -> Dict:
        """Исполнение виртуальной сделки с учётом сигналов от RiskManager"""
        
        ticker = signal['ticker']
        action = signal['action']
        size = signal.get('position_size', 1)
        
        # Для частичного выхода корректируем размер
        if signal.get('position_type') == 'partial_exit' and ticker in self.positions:
            current_position = self.positions[ticker]['size']
            size = min(size, current_position)
        
        trade_cost = current_price * size
        timestamp = datetime.datetime.now()
        
        trade_result = {
            'timestamp': timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'strategy': signal.get('strategy', 'News NLP Trading'),
            'action': action,
            'ticker': ticker,
            'price': current_price,
            'size': size,
            'virtual': True,
            'status': 'PENDING',
            'profit': 0,
            'reason': signal.get('reason', ''),
            'ai_generated': signal.get('ai_provider') not in ['simple', 'enhanced', 'enhanced_fallback'],
            'ai_provider': signal.get('ai_provider', 'simple'),
            'confidence': signal.get('confidence', 0.5),
            'event_type': signal.get('event_type', 'market_update'),
            'signal_source': signal.get('signal_source', 'pipeline'),
            'take_profit': signal.get('take_profit'),
            'stop_loss': signal.get('stop_loss'),
            'take_profit_percent': signal.get('take_profit_percent', 3.0),
            'stop_loss_percent': signal.get('stop_loss_percent', 1.5),
            'trailing_start': signal.get('trailing_start', 2.0),
            'trailing_step': signal.get('trailing_step', 0.7)
        }
        
        try:
            if action == 'BUY':
                if trade_cost <= self.cash:
                    # Покупка
                    self.cash -= trade_cost
                    
                    if ticker in self.positions:
                        # Усреднение позиции
                        old_pos = self.positions[ticker]
                        total_size = old_pos['size'] + size
                        total_cost = (old_pos['avg_price'] * old_pos['size']) + trade_cost
                        new_avg_price = total_cost / total_size
                        
                        self.positions[ticker] = {
                            'size': total_size,
                            'avg_price': new_avg_price,
                            'take_profit': signal.get('take_profit', current_price * 1.03),
                            'stop_loss': signal.get('stop_loss', current_price * 0.985),
                            'take_profit_percent': signal.get('take_profit_percent', 3.0),
                            'stop_loss_percent': signal.get('stop_loss_percent', 1.5),
                            'trailing_start': signal.get('trailing_start', 2.0),
                            'trailing_step': signal.get('trailing_step', 0.7),
                            'entry_time': timestamp.isoformat(),
                            'last_update': timestamp.isoformat(),
                            'ai_provider': signal.get('ai_provider', 'unknown'),
                            'signal_source': signal.get('signal_source', 'pipeline')
                        }
                    else:
                        # Новая позиция
                        self.positions[ticker] = {
                            'size': size,
                            'avg_price': current_price,
                            'take_profit': signal.get('take_profit', current_price * 1.03),
                            'stop_loss': signal.get('stop_loss', current_price * 0.985),
                            'take_profit_percent': signal.get('take_profit_percent', 3.0),
                            'stop_loss_percent': signal.get('stop_loss_percent', 1.5),
                            'trailing_start': signal.get('trailing_start', 2.0),
                            'trailing_step': signal.get('trailing_step', 0.7),
                            'entry_time': timestamp.isoformat(),
                            'last_update': timestamp.isoformat(),
                            'ai_provider': signal.get('ai_provider', 'unknown'),
                            'signal_source': signal.get('signal_source', 'pipeline')
                        }
                    
                    trade_result['status'] = "EXECUTED"
                    trade_result['message'] = f"Куплено {size} {ticker}"
                    
                    logger.info(f"🟢 ВИРТУАЛЬНАЯ ПОКУПКА: {size} {ticker} по {current_price:.2f}")
                    logger.info(f"   💰 Стоимость: {trade_cost:.0f} руб. | Остаток: {self.cash:.0f} руб.")
                    
                else:
                    trade_result['status'] = "INSUFFICIENT_FUNDS"
                    trade_result['message'] = f"Недостаточно средств: {trade_cost:.2f} > {self.cash:.2f}"
                    logger.warning(f"❌ Недостаточно средств для покупки {ticker}")
                    
            else:  # SELL
                if ticker in self.positions and self.positions[ticker]['size'] >= size:
                    position = self.positions[ticker]
                    
                    # Расчет прибыли
                    profit = (current_price - position['avg_price']) * size
                    profit_percent = ((current_price - position['avg_price']) / position['avg_price']) * 100
                    
                    # Обновление денежных средств
                    self.cash += trade_cost
                    
                    trade_result['profit'] = profit
                    trade_result['profit_percent'] = profit_percent
                    trade_result['avg_entry_price'] = position['avg_price']
                    
                    # Обновление статистики
                    if profit > 0:
                        self.winning_trades += 1
                    
                    self.total_trades += 1
                    self.total_profit += profit
                    
                    # Обновление или удаление позиции
                    if position['size'] == size:
                        # Полный выход
                        del self.positions[ticker]
                        trade_result['message'] = f"Продано {size} {ticker}. Позиция закрыта."
                    else:
                        # Частичный выход
                        position['size'] -= size
                        position['last_update'] = timestamp.isoformat()
                        trade_result['message'] = f"Продано {size} {ticker}. Осталось: {position['size']}."
                    
                    trade_result['status'] = "EXECUTED"
                    
                    # Логирование
                    profit_color = "🟢" if profit > 0 else "🔴"
                    logger.info(f"{profit_color} ВИРТУАЛЬНАЯ ПРОДАЖА: {size} {ticker} по {current_price:.2f}")
                    logger.info(f"   📊 Прибыль: {profit:+.2f} руб. ({profit_percent:+.1f}%)")
                    logger.info(f"   💰 Остаток: {self.cash:.0f} руб.")
                    
                else:
                    trade_result['status'] = "NO_POSITION"
                    trade_result['message'] = f"Нет позиции {ticker} для продажи"
                    logger.warning(f"❌ Нет позиции {ticker} для продажи")
        
        except Exception as e:
            trade_result['status'] = "ERROR"
            trade_result['message'] = str(e)
            logger.error(f"❌ Ошибка исполнения сделки: {e}")
        
        # Добавление в историю
        self.trade_history.append(trade_result)
        
        # Обновление максимальной просадки
        current_value = self.get_total_value({})
        if current_value > self.peak_value:
            self.peak_value = current_value
        
        drawdown = (self.peak_value - current_value) / self.peak_value * 100
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
        
        return trade_result

    def get_portfolio_analytics(self, current_prices: Dict[str, float]) -> Dict:
        """Расчёт детальной аналитики портфеля"""
        total_value = self.cash
        total_pnl = 0.0
        positions_detail = []
        
        for ticker, pos in self.positions.items():
            if ticker in current_prices:
                current_price = current_prices[ticker]
                market_value = current_price * pos['size']
                total_value += market_value
                pnl = (current_price - pos['avg_price']) * pos['size']
                total_pnl += pnl
                
                positions_detail.append({
                    'ticker': ticker,
                    'size': pos['size'],
                    'avg_price': pos['avg_price'],
                    'current_price': current_price,
                    'market_value': market_value,
                    'pnl': pnl,
                    'pnl_percent': (current_price / pos['avg_price'] - 1) * 100 if pos['avg_price'] > 0 else 0,
                    'entry_time': pos.get('entry_time'),
                    'ai_provider': pos.get('ai_provider', 'unknown')
                })
        
        # Рассчитываем доходность
        initial_total = sum(pos['avg_price'] * pos['size'] for pos in self.positions.values()) + self.cash
        total_return_pct = ((total_value - initial_total) / initial_total * 100) if initial_total > 0 else 0
        
        return {
            'total_value': total_value,
            'total_pnl': total_pnl,
            'total_return_pct': total_return_pct,
            'positions_detail': positions_detail,
            'cash': self.cash,
            'positions_count': len(self.positions)
        }
    
    def get_total_value(self, current_prices: Dict) -> float:
        """Расчет общей стоимости портфеля"""
        
        total = self.cash
        
        for ticker, pos in self.positions.items():
            if ticker in current_prices:
                total += current_prices[ticker] * pos['size']
            else:
                # Используем среднюю цену входа если текущая цена неизвестна
                total += pos['avg_price'] * pos['size']
        
        return round(total, 2)
    
    def get_stats(self) -> Dict:
        """Получение статистики портфеля"""
        
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        avg_profit = self.total_profit / self.total_trades if self.total_trades > 0 else 0
        
        # Анализ позиций
        positions_analysis = []
        for ticker, pos in self.positions.items():
            positions_analysis.append({
                'ticker': ticker,
                'size': pos['size'],
                'avg_price': pos['avg_price'],
                'entry_time': pos.get('entry_time'),
                'ai_provider': pos.get('ai_provider', 'unknown'),
                'signal_source': pos.get('signal_source', 'unknown')
            })
        
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': round(win_rate, 1),
            'total_profit': round(self.total_profit, 2),
            'avg_profit': round(avg_profit, 2),
            'current_positions': len(self.positions),
            'cash': round(self.cash, 2),
            'max_drawdown': round(self.max_drawdown, 2),
            'peak_value': round(self.peak_value, 2),
            'current_value': round(self.get_total_value({}), 2),
            'positions': positions_analysis,
            'portfolio_return': round(((self.get_total_value({}) - self.initial_capital) / self.initial_capital * 100), 2)
        }
