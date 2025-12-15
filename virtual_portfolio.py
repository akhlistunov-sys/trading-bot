# virtual_portfolio.py - С СОХРАНЕНИЕМ СОСТОЯНИЯ (PERSISTENCE)
import datetime
import logging
import json
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class VirtualPortfolioPro:
    """Виртуальный портфель с сохранением состояния на диск"""
    
    def __init__(self, initial_capital: float = 100000):
        self.state_file = 'portfolio_state.json'
        self.history_file = 'trade_history.json'
        self.initial_capital = initial_capital
        
        # Пытаемся загрузить состояние, если файла нет - создаем новое
        if not self.load_state():
            self.cash = initial_capital
            self.positions = {} # {ticker: {size, avg_price, ...}}
            self.trade_history = []
            self.total_trades = 0
            self.winning_trades = 0
            self.total_profit = 0
            self.max_drawdown = 0
            self.peak_value = initial_capital
            logger.info(f"💰 Новый портфель создан: {initial_capital:,.2f} руб.")
        else:
            logger.info(f"📂 Портфель загружен с диска. Баланс: {self.cash:,.2f} руб., Позиций: {len(self.positions)}")

    def save_state(self):
        """Сохранение состояния в JSON"""
        try:
            state = {
                'cash': self.cash,
                'positions': self.positions,
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'total_profit': self.total_profit,
                'peak_value': self.peak_value,
                'max_drawdown': self.max_drawdown,
                'updated_at': datetime.datetime.now().isoformat()
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4, ensure_ascii=False)
            
            # Отдельно сохраняем историю
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.trade_history, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения портфеля: {e}")

    def load_state(self) -> bool:
        """Загрузка состояния из JSON"""
        if not os.path.exists(self.state_file):
            return False
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                self.cash = state.get('cash', 100000)
                self.positions = state.get('positions', {})
                self.total_trades = state.get('total_trades', 0)
                self.winning_trades = state.get('winning_trades', 0)
                self.total_profit = state.get('total_profit', 0)
                self.peak_value = state.get('peak_value', 100000)
                self.max_drawdown = state.get('max_drawdown', 0)
            
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.trade_history = json.load(f)
            
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки портфеля (создаем новый): {e}")
            return False

    def execute_trade(self, signal: Dict, current_price: float) -> Dict:
        """Исполнение сделки с комиссией и записью"""
        ticker = signal['ticker']
        action = signal['action']
        size = int(signal.get('position_size', 1))
        
        if size <= 0: return {'status': 'ERROR', 'message': 'Size is 0'}
        
        # Комиссия брокера (симуляция 0.05%)
        commission_rate = 0.0005
        trade_amount = current_price * size
        commission = trade_amount * commission_rate
        
        timestamp = datetime.datetime.now().isoformat()
        
        result = {
            'timestamp': timestamp,
            'action': action,
            'ticker': ticker,
            'price': current_price,
            'size': size,
            'commission': commission,
            'status': 'PENDING'
        }

        try:
            if action == 'BUY':
                total_cost = trade_amount + commission
                if total_cost <= self.cash:
                    self.cash -= total_cost
                    
                    # Логика усреднения позиции
                    if ticker in self.positions:
                        pos = self.positions[ticker]
                        old_cost = pos['size'] * pos['avg_price']
                        new_cost = old_cost + trade_amount
                        new_size = pos['size'] + size
                        pos['avg_price'] = new_cost / new_size
                        pos['size'] = new_size
                    else:
                        self.positions[ticker] = {
                            'size': size,
                            'avg_price': current_price,
                            'entry_time': timestamp
                        }
                    
                    result['status'] = 'EXECUTED'
                    result['message'] = f"Куплено {size} {ticker}"
                    logger.info(f"🟢 BUY {ticker}: {size} шт по {current_price:.2f}. Ком: {commission:.2f}")
                    
                else:
                    result['status'] = 'NO_FUNDS'
                    logger.warning(f"❌ Не хватает средств на {ticker}")

            elif action == 'SELL':
                if ticker in self.positions and self.positions[ticker]['size'] >= size:
                    pos = self.positions[ticker]
                    total_revenue = trade_amount - commission
                    
                    # Считаем прибыль
                    buy_price = pos['avg_price']
                    profit = (current_price - buy_price) * size - commission
                    
                    self.cash += total_revenue
                    self.total_profit += profit
                    self.total_trades += 1
                    if profit > 0: self.winning_trades += 1
                    
                    result['profit'] = profit
                    
                    # Уменьшаем позицию
                    pos['size'] -= size
                    if pos['size'] == 0:
                        del self.positions[ticker]
                    
                    result['status'] = 'EXECUTED'
                    logger.info(f"🔴 SELL {ticker}: {size} шт по {current_price:.2f}. P&L: {profit:+.2f}")
                else:
                    result['status'] = 'NO_POSITION'

        except Exception as e:
            logger.error(f"Trade Error: {e}")
            result['status'] = 'ERROR'
        
        if result['status'] == 'EXECUTED':
            self.trade_history.append(result)
            self.save_state() # СОХРАНЯЕМ СРАЗУ ПОСЛЕ СДЕЛКИ
            
        return result

    def get_stats(self) -> Dict:
        """Статистика для Dashboard"""
        current_holdings_value = 0
        for ticker, pos in self.positions.items():
            # Здесь мы пока берем цену покупки, но в идеале нужно обновлять по рынку
            # В app.py мы будем передавать актуальные цены для точного расчета
            current_holdings_value += pos['size'] * pos['avg_price']
            
        total_value = self.cash + current_holdings_value
        return {
            'current_value': total_value,
            'cash': self.cash,
            'total_profit': self.total_profit,
            'total_trades': self.total_trades,
            'positions_count': len(self.positions),
            'portfolio_return': ((total_value - self.initial_capital) / self.initial_capital) * 100,
            # Для графика пока заглушка, реальный график требует накопления истории
            'chart_labels': [], 
            'chart_values': []
        }
        
    def check_exit_conditions(self, current_prices):
        """Проверка выходов (Stop Loss / Take Profit)"""
        exits = []
        # Простая логика: если есть цена и она на 2% ниже покупки - стоп, на 6% выше - тейк
        for ticker, pos in self.positions.items():
            if ticker in current_prices:
                curr = current_prices[ticker]
                avg = pos['avg_price']
                pct_diff = (curr - avg) / avg * 100
                
                if pct_diff <= -2.0: # Stop Loss
                    exits.append({'action': 'SELL', 'ticker': ticker, 'position_size': pos['size'], 'reason': 'Stop Loss'})
                elif pct_diff >= 6.0: # Take Profit
                    exits.append({'action': 'SELL', 'ticker': ticker, 'position_size': pos['size'], 'reason': 'Take Profit'})
        return exits
