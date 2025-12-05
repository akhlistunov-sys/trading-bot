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
        """Проверка условий выхода из позиций (тейк-профит, стоп-лосс)"""
        
        exit_signals = []
        
        for ticker, pos_info in list(self.positions.items()):
            if ticker in current_prices:
                current_price = current_prices[ticker]
                avg_price = pos_info['avg_price']
                size = pos_info['size']
                
                profit_per_share = current_price - avg_price
                total_profit = profit_per_share * size
                profit_percent = (profit_per_share / avg_price) * 100
                
                # Проверка тейк-профита
                if 'take_profit' in pos_info and current_price >= pos_info['take_profit']:
                    exit_signals.append({
                        'action': 'SELL',
                        'ticker': ticker,
                        'price': current_price,
                        'size': size,
                        'strategy': 'Take Profit',
                        'reason': f"✅ ТЕЙК-ПРОФИТ {pos_info.get('take_profit_percent', 2.5)}% достигнут",
                        'profit': total_profit,
                        'profit_percent': profit_percent,
                        'position_type': 'full_exit'
                    })
                
                # Проверка стоп-лосса
                elif 'stop_loss' in pos_info and current_price <= pos_info['stop_loss']:
                    exit_signals.append({
                        'action': 'SELL',
                        'ticker': ticker,
                        'price': current_price,
                        'size': size,
                        'strategy': 'Stop Loss',
                        'reason': f"🚨 СТОП-ЛОСС {pos_info.get('stop_loss_percent', 1.5)}% сработал",
                        'profit': total_profit,
                        'profit_percent': profit_percent,
                        'position_type': 'full_exit'
                    })
                
                # Частичный выход при хорошей прибыли (опционально)
                elif profit_percent >= 5.0 and 'ai_generated' in pos_info and pos_info['ai_generated']:
                    # Продаем половину позиции для фиксации прибыли
                    exit_size = int(size * 0.5)
                    if exit_size > 0:
                        exit_signals.append({
                            'action': 'SELL',
                            'ticker': ticker,
                            'price': current_price,
                            'size': exit_size,
                            'strategy': 'Partial Profit Taking',
                            'reason': f"⚡ Частичный выход при {profit_percent:.1f}% прибыли",
                            'profit': total_profit * 0.5,
                            'profit_percent': profit_percent,
                            'position_type': 'partial_exit'
                        })
        
        return exit_signals
    
    def execute_trade(self, signal: Dict, current_price: float) -> Dict:
        """Исполнение виртуальной сделки"""
        
        ticker = signal['ticker']
        action = signal['action']
        size = signal.get('size', 1)
        
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
            'ai_generated': signal.get('ai_generated', False),
            'confidence': signal.get('confidence', 0.5),
            'take_profit': signal.get('take_profit'),
            'stop_loss': signal.get('stop_loss'),
            'take_profit_percent': signal.get('take_profit_percent', 2.5),
            'stop_loss_percent': signal.get('stop_loss_percent', 1.5)
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
                            'take_profit': signal.get('take_profit', current_price * 1.025),
                            'stop_loss': signal.get('stop_loss', current_price * 0.985),
                            'take_profit_percent': signal.get('take_profit_percent', 2.5),
                            'stop_loss_percent': signal.get('stop_loss_percent', 1.5),
                            'entry_time': timestamp.isoformat(),
                            'ai_generated': signal.get('ai_generated', False)
                        }
                    else:
                        # Новая позиция
                        self.positions[ticker] = {
                            'size': size,
                            'avg_price': current_price,
                            'take_profit': signal.get('take_profit', current_price * 1.025),
                            'stop_loss': signal.get('stop_loss', current_price * 0.985),
                            'take_profit_percent': signal.get('take_profit_percent', 2.5),
                            'stop_loss_percent': signal.get('stop_loss_percent', 1.5),
                            'entry_time': timestamp.isoformat(),
                            'ai_generated': signal.get('ai_generated', False)
                        }
                    
                    trade_result['status'] = "EXECUTED"
                    trade_result['message'] = f"Куплено {size} {ticker}"
                    
                    logger.info(f"🟢 ВИРТУАЛЬНАЯ ПОКУПКА: {size} {ticker} по {current_price:.2f}")
                    
                else:
                    trade_result['status'] = "INSUFFICIENT_FUNDS"
                    trade_result['message'] = f"Недостаточно средств: {trade_cost:.2f} > {self.cash:.2f}"
                    
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
                        trade_result['message'] = f"Продано {size} {ticker}. Осталось: {position['size']}."
                    
                    trade_result['status'] = "EXECUTED"
                    
                    # Логирование
                    profit_color = "🟢" if profit > 0 else "🔴"
                    logger.info(f"{profit_color} ВИРТУАЛЬНАЯ ПРОДАЖА: {size} {ticker} по {current_price:.2f}")
                    logger.info(f"   📊 Прибыль: {profit:+.2f} руб. ({profit_percent:+.1f}%)")
                    
                else:
                    trade_result['status'] = "NO_POSITION"
                    trade_result['message'] = f"Нет позиции {ticker} для продажи"
        
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
        
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': round(win_rate, 1),
            'total_profit': round(self.total_profit, 2),
            'avg_profit': round(avg_profit, 2),
            'current_positions': len(self.positions),
            'cash': round(self.cash, 2),
            'max_drawdown': round(self.max_drawdown, 2),
            'positions': self.positions.copy()
        }
