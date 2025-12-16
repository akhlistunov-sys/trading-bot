# virtual_portfolio.py - TRAILING STOP IMPLEMENTATION
import datetime
import logging
import json
import os
from typing import Dict, List

logger = logging.getLogger(__name__)

class VirtualPortfolioPro:
    def __init__(self, initial_capital: float = 100000):
        self.state_file = 'portfolio_state.json'
        self.cash = initial_capital
        self.positions = {} 
        self.trade_history = []
        self.total_profit = 0
        self.load_state()
        
    def execute_trade(self, signal: Dict, price: float) -> Dict:
        t = signal['ticker']
        qty = int(signal.get('position_size', 1))
        if qty <= 0: return {'status': 'ERR'}
        
        comm = (price * qty) * 0.0005
        ts = datetime.datetime.now().strftime("%H:%M")
        
        if signal['action'] == 'BUY':
            cost = (price * qty) + comm
            if self.cash >= cost:
                self.cash -= cost
                if t in self.positions:
                    p = self.positions[t]
                    total = (p['size'] * p['avg']) + cost
                    p['size'] += qty
                    p['avg'] = total / p['size']
                else:
                    # high_water_mark - это максимум цены, который мы видели (для трейлинга)
                    self.positions[t] = {'size': qty, 'avg': price, 'high_water_mark': price}
                
                self._log_trade(ts, 'BUY', t, price, signal.get('reason', 'Signal'), 0)
                return {'status': 'EXECUTED', 'profit': 0}
                
        elif signal['action'] == 'SELL':
            if t in self.positions:
                p = self.positions[t]
                rev = (price * qty) - comm
                prof = rev - (p['avg'] * qty)
                self.cash += rev
                self.total_profit += prof
                
                p['size'] -= qty
                if p['size'] == 0: del self.positions[t]
                
                self._log_trade(ts, 'SELL', t, price, signal.get('reason', 'Exit'), prof)
                return {'status': 'EXECUTED', 'profit': prof}
                
        return {'status': 'FAIL'}

    def check_exit_conditions(self, prices):
        exits = []
        for t, p in self.positions.items():
            if t not in prices: continue
            curr = prices[t]
            
            # --- TRAILING STOP LOGIC ---
            # 1. Обновляем максимум цены
            p['high_water_mark'] = max(p.get('high_water_mark', p['avg']), curr)
            
            # Процент прибыли от входа
            profit_pct = (curr - p['avg']) / p['avg']
            
            # Если прибыль > 1%, включаем трейлинг
            if profit_pct > 0.01:
                # Стоп на 1.5% ниже МАКСИМУМА
                trailing_stop = p['high_water_mark'] * 0.985
                # Но не ниже безубытка (+0.1%)
                breakeven = p['avg'] * 1.001
                effective_stop = max(trailing_stop, breakeven)
                
                if curr < effective_stop:
                    exits.append({'action': 'SELL', 'ticker': t, 'position_size': p['size'], 'reason': 'Trailing Stop'})
            
            # Обычный Хард Стоп (-2%), если трейлинг еще не включился
            elif profit_pct < -0.02:
                exits.append({'action': 'SELL', 'ticker': t, 'position_size': p['size'], 'reason': 'Stop Loss'})
                
        return exits

    def _log_trade(self, ts, act, tick, pr, reas, prof):
        self.trade_history.insert(0, {
            'timestamp': ts, 'action': act, 'ticker': tick, 
            'price': pr, 'reason': reas, 'profit': prof
        })
        self.save_state()

    def save_state(self):
        try:
            state = {
                'cash': self.cash, 'positions': self.positions, 
                'total_profit': self.total_profit, 'history': self.trade_history[:50]
            }
            with open(self.state_file, 'w') as f: json.dump(state, f)
        except: pass

    def load_state(self):
        if not os.path.exists(self.state_file): return
        try:
            with open(self.state_file, 'r') as f:
                d = json.load(f)
                self.cash = d.get('cash', 100000)
                self.positions = d.get('positions', {})
                self.total_profit = d.get('total_profit', 0)
                self.trade_history = d.get('history', [])
        except: pass

    def get_stats(self):
        val = self.cash + sum([p['size'] * p.get('high_water_mark', p['avg']) for p in self.positions.values()])
        return {'current_value': val, 'cash': self.cash, 'total_profit': self.total_profit, 'trade_history': self.trade_history}
