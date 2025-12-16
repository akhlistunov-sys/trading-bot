# virtual_portfolio.py - СОХРАНЯЕТ ПРИЧИНУ СДЕЛКИ
import datetime
import logging
import json
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class VirtualPortfolioPro:
    def __init__(self, initial_capital: float = 100000):
        self.state_file = 'portfolio_state.json'
        self.history_file = 'trade_history.json'
        self.initial_capital = initial_capital
        
        if not self.load_state():
            self.cash = initial_capital
            self.positions = {} 
            self.trade_history = []
            self.total_trades = 0
            self.winning_trades = 0
            self.total_profit = 0
            
    def execute_trade(self, signal: Dict, current_price: float) -> Dict:
        ticker = signal['ticker']
        action = signal['action']
        reason = signal.get('reason', 'Signal') # Причина сделки
        size = int(signal.get('position_size', 1))
        
        if size <= 0: return {'status': 'ERROR', 'profit': 0}
        
        commission = (current_price * size) * 0.0005
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        trade_record = {
            'timestamp': timestamp,
            'ticker': ticker,
            'action': action,
            'size': size,
            'price': current_price,
            'reason': reason, # <--- ВАЖНО: Новость или тех. индикатор
            'profit': 0.0
        }

        if action == 'BUY':
            cost = (current_price * size) + commission
            if self.cash >= cost:
                self.cash -= cost
                if ticker in self.positions:
                    # Усреднение
                    p = self.positions[ticker]
                    total_cost = (p['size'] * p['avg_price']) + cost
                    p['size'] += size
                    p['avg_price'] = total_cost / p['size']
                else:
                    self.positions[ticker] = {'size': size, 'avg_price': current_price}
                
                self.total_trades += 1
                self.trade_history.insert(0, trade_record) # Добавляем в начало списка
                self.save_state()
                return {'status': 'EXECUTED', 'profit': 0}
                
        elif action == 'SELL':
            if ticker in self.positions and self.positions[ticker]['size'] >= size:
                p = self.positions[ticker]
                revenue = (current_price * size) - commission
                profit = revenue - (p['avg_price'] * size)
                
                self.cash += revenue
                self.total_profit += profit
                self.total_trades += 1
                if profit > 0: self.winning_trades += 1
                
                p['size'] -= size
                if p['size'] == 0: del self.positions[ticker]
                
                trade_record['profit'] = profit
                self.trade_history.insert(0, trade_record)
                self.save_state()
                return {'status': 'EXECUTED', 'profit': profit}

        return {'status': 'FAILED', 'profit': 0}

    def save_state(self):
        try:
            state = {
                'cash': self.cash,
                'positions': self.positions,
                'total_profit': self.total_profit,
                'total_trades': self.total_trades,
                'trade_history': self.trade_history[:50] # Храним последние 50
            }
            with open(self.state_file, 'w') as f: json.dump(state, f, indent=4)
        except: pass

    def load_state(self) -> bool:
        if not os.path.exists(self.state_file): return False
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.cash = state.get('cash', 100000)
                self.positions = state.get('positions', {})
                self.total_profit = state.get('total_profit', 0)
                self.total_trades = state.get('total_trades', 0)
                self.trade_history = state.get('trade_history', [])
            return True
        except: return False

    def get_stats(self) -> Dict:
        # Оценка стоимости портфеля
        equity = self.cash
        # Примечание: тут используются цены покупки. В идеале нужно передавать текущие цены.
        for t, p in self.positions.items():
            equity += p['size'] * p['avg_price']
            
        return {
            'current_value': equity,
            'cash': self.cash,
            'total_profit': self.total_profit,
            'total_trades': self.total_trades,
            'trade_history': self.trade_history
        }

    def check_exit_conditions(self, current_prices):
        exits = []
        for ticker, pos in self.positions.items():
            if ticker in current_prices:
                price = current_prices[ticker]
                # Stop Loss 2%, Take Profit 5%
                pnl_pct = (price - pos['avg_price']) / pos['avg_price'] * 100
                
                if pnl_pct <= -2.0:
                    exits.append({'action': 'SELL', 'ticker': ticker, 'position_size': pos['size'], 'reason': f'Stop Loss ({pnl_pct:.1f}%)'})
                elif pnl_pct >= 5.0:
                    exits.append({'action': 'SELL', 'ticker': ticker, 'position_size': pos['size'], 'reason': f'Take Profit ({pnl_pct:.1f}%)'})
        return exits
