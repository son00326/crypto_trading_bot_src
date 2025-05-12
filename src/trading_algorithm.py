"""
거래 알고리즘 모듈 - 암호화폐 자동매매 봇

이 모듈은 거래 신호 생성 및 주문 실행을 담당하는 거래 알고리즘을 구현합니다.
다양한 전략을 기반으로 매수/매도 신호를 생성하고 실제 거래를 수행합니다.
"""

import pandas as pd
import numpy as np
import logging
import time
import os
from datetime import datetime, timedelta
import threading
import json

from src.exchange_api import ExchangeAPI
from src.data_manager import DataManager
from src.data_collector import DataCollector
from src.data_analyzer import DataAnalyzer
from src.db_manager import DatabaseManager
from src.strategies import (
    MovingAverageCrossover, RSIStrategy, MACDStrategy, 
    BollingerBandsStrategy, CombinedStrategy
)
from src.config import (
    DEFAULT_EXCHANGE, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME,
    RISK_MANAGEMENT
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('trading_algorithm')

class TradingAlgorithm:
    """암호화폐 자동매매 알고리즘 클래스"""
    
    def __init__(self, exchange_id=DEFAULT_EXCHANGE, symbol=DEFAULT_SYMBOL, timeframe=DEFAULT_TIMEFRAME, 
                 strategy=None, initial_balance=None, test_mode=True, restore_state=True):
        """
        거래 알고리즘 초기화
        
        Args:
            exchange_id (str): 거래소 ID
            symbol (str): 거래 심볼
            timeframe (str): 타임프레임
            strategy: 거래 전략 객체
            initial_balance (float): 초기 자산 (테스트 모드에서만 사용)
            test_mode (bool): 테스트 모드 여부
            restore_state (bool): 이전 상태 복원 여부
        """
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.test_mode = test_mode
        
        # 데이터베이스 관리자 초기화
        self.db = DatabaseManager()
        
        # 거래소 API 및 데이터 관련 객체 초기화
        self.exchange_api = ExchangeAPI(exchange_id=exchange_id, symbol=symbol, timeframe=timeframe)
        self.data_manager = DataManager(exchange_id=exchange_id, symbol=symbol)
        self.data_collector = DataCollector(exchange_id=exchange_id, symbol=symbol, timeframe=timeframe)
        self.data_analyzer = DataAnalyzer(exchange_id=exchange_id, symbol=symbol)
        
        # 테스트 모드 설정
        if test_mode:
            self.exchange_api.exchange.set_sandbox_mode(True)
            logger.info("테스트 모드로 실행합니다.")
        
        # 전략 설정
        if strategy is None:
            # 기본 전략: 이동평균 교차 + RSI
            self.strategy = CombinedStrategy([
                MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema'),
                RSIStrategy(period=14, overbought=70, oversold=30)
            ])
        else:
            self.strategy = strategy
        
        logger.info(f"{self.strategy.name} 전략을 사용합니다.")
        
        # 포트폴리오 초기화 (기본값)
        self.portfolio = {
            'base_currency': symbol.split('/')[0],  # BTC, ETH 등
            'quote_currency': symbol.split('/')[1],  # USDT, USD 등
            'base_balance': 0,
            'quote_balance': initial_balance if initial_balance else 0,
            'positions': [],
            'trade_history': []
        }
        
        # 거래 상태 (기본값)
        self.trading_active = False
        self.last_signal = 0  # 0: 중립, 1: 매수, -1: 매도
        
        # 위험 관리 설정
        self.risk_management = RISK_MANAGEMENT.copy()
        
        # 이전 상태 복원
        if restore_state:
            self._restore_state()
        
        logger.info(f"{exchange_id} 거래소의 {symbol} 거래 알고리즘이 초기화되었습니다.")
    
    def _restore_state(self):
        """데이터베이스에서 이전 상태 복원"""
        try:
            # 봇 상태 불러오기
            saved_state = self.db.load_bot_state()
            if saved_state:
                logger.info("이전 봇 상태를 불러옵니다.")
                
                # 기본 설정 복원
                if 'symbol' in saved_state and saved_state['symbol'] == self.symbol:
                    if 'is_running' in saved_state:
                        self.trading_active = saved_state['is_running']
                    if 'test_mode' in saved_state:
                        self.test_mode = saved_state['test_mode']
                        if self.test_mode:
                            self.exchange_api.exchange.set_sandbox_mode(True)
                    
                    # 전략 파라미터 복원 (필요시)
                    if 'parameters' in saved_state and saved_state['parameters']:
                        logger.info("전략 파라미터를 복원합니다.")
                        # 여기서 전략별 파라미터 적용 코드 추가 가능
                    
                    logger.info("봇 상태 복원 완료")
                else:
                    logger.warning(f"저장된 상태의 심볼({saved_state.get('symbol')})이 현재 심볼({self.symbol})과 일치하지 않습니다.")
            
            # 열린 포지션 복원
            open_positions = self.db.get_open_positions(self.symbol)
            if open_positions:
                logger.info(f"{len(open_positions)}개의 열린 포지션을 복원합니다.")
                self.portfolio['positions'] = open_positions
            
            # 잔액 정보 복원
            latest_balance = self.db.get_latest_balance()
            if latest_balance:
                for currency, bal_info in latest_balance.items():
                    if currency == self.portfolio['base_currency']:
                        self.portfolio['base_balance'] = bal_info['amount']
                    elif currency == self.portfolio['quote_currency']:
                        self.portfolio['quote_balance'] = bal_info['amount']
            
            # 거래 내역 복원 (최근 50개)
            recent_trades = self.db.get_trades(self.symbol, limit=50)
            if recent_trades:
                logger.info(f"{len(recent_trades)}개의 최근 거래 내역을 복원합니다.")
                self.portfolio['trade_history'] = recent_trades
                
                # 마지막 신호 유추
                if recent_trades:
                    last_trade = recent_trades[0]  # 가장 최근 거래
                    if last_trade['side'] == 'buy':
                        self.last_signal = 1
                    elif last_trade['side'] == 'sell':
                        self.last_signal = -1
            
            logger.info("상태 복원 완료")
            return True
        except Exception as e:
            logger.error(f"상태 복원 중 오류 발생: {e}")
            return False
    
    def save_state(self):
        """현재 상태를 데이터베이스에 저장"""
        try:
            # 봇 상태 저장
            bot_state = {
                'exchange_id': self.exchange_id,
                'symbol': self.symbol,
                'timeframe': self.timeframe,
                'strategy': self.strategy.name if hasattr(self.strategy, 'name') else 'unknown',
                'market_type': 'futures' if self.exchange_api.is_futures else 'spot',
                'leverage': self.exchange_api.leverage if hasattr(self.exchange_api, 'leverage') else 1,
                'is_running': self.trading_active,
                'test_mode': self.test_mode,
                'updated_at': datetime.now().isoformat(),
                'parameters': {
                    'risk_management': self.risk_management,
                    'strategy_params': getattr(self.strategy, 'params', {})
                },
                'additional_info': {
                    'last_signal': self.last_signal
                }
            }
            
            self.db.save_bot_state(bot_state)
            logger.info("봇 상태 저장 완료")
            
            # 현재 잔액 저장
            self.db.save_balance(self.portfolio['base_currency'], 
                                self.portfolio['base_balance'],
                                {'source': 'automatic_save'})
            
            self.db.save_balance(self.portfolio['quote_currency'], 
                                self.portfolio['quote_balance'],
                                {'source': 'automatic_save'})
            
            logger.info("잔액 정보 저장 완료")
            return True
        except Exception as e:
            logger.error(f"상태 저장 중 오류 발생: {e}")
            return False
    
    def update_portfolio(self):
        """포트폴리오 정보 업데이트"""
        try:
            if self.test_mode:
                # 테스트 모드에서는 포트폴리오 정보를 시뮬레이션
                return
            
            # 실제 거래소에서 잔고 정보 가져오기
            balance = self.exchange_api.get_balance()
            
            if balance:
                base_currency = self.portfolio['base_currency']
                quote_currency = self.portfolio['quote_currency']
                
                # 기본 통화 잔고 (BTC, ETH 등)
                if base_currency in balance['free']:
                    self.portfolio['base_balance'] = float(balance['free'][base_currency])
                
                # 견적 통화 잔고 (USDT, USD 등)
                if quote_currency in balance['free']:
                    self.portfolio['quote_balance'] = float(balance['free'][quote_currency])
                
                logger.info(f"포트폴리오 업데이트: {base_currency}={self.portfolio['base_balance']}, {quote_currency}={self.portfolio['quote_balance']}")
            else:
                logger.warning("잔고 정보를 가져오지 못했습니다.")
        
        except Exception as e:
            logger.error(f"포트폴리오 업데이트 중 오류 발생: {e}")
    
    def calculate_position_size(self, price):
        """
        위험 관리 설정에 따른 포지션 크기 계산
        
        Args:
            price (float): 현재 가격
        
        Returns:
            float: 매수/매도할 수량
        """
        try:
            # 사용 가능한 자산
            available_balance = self.portfolio['quote_balance']
            
            # 최대 포지션 크기 (계좌 자산의 일정 비율)
            max_position_size = available_balance * self.risk_management['max_position_size']
            
            # 수량 계산 (소수점 8자리까지)
            quantity = round(max_position_size / price, 8)
            
            # 최소 주문 수량 확인 (거래소마다 다름)
            min_quantity = 0.0001  # 예시 값, 실제로는 거래소별로 다름
            
            if quantity < min_quantity:
                logger.warning(f"계산된 수량({quantity})이 최소 주문 수량({min_quantity})보다 작습니다.")
                return 0
            
            return quantity
        
        except Exception as e:
            logger.error(f"포지션 크기 계산 중 오류 발생: {e}")
            return 0
    
    def execute_buy(self, price, quantity):
        """
        매수 주문 실행
        
        Args:
            price (float): 매수 가격
            quantity (float): 매수 수량
        
        Returns:
            dict: 주문 결과
        """
        try:
            order_time = datetime.now()
            if self.test_mode:
                # 테스트 모드에서는 주문을 시뮬레이션
                order = {
                    'id': f"test_buy_{order_time.timestamp()}",
                    'datetime': order_time.isoformat(),
                    'symbol': self.symbol,
                    'type': 'market',
                    'side': 'buy',
                    'price': price,
                    'amount': quantity,
                    'cost': price * quantity,
                    'fee': price * quantity * 0.001,  # 0.1% 수수료 가정
                    'status': 'closed'
                }
                
                # 포트폴리오 업데이트
                self.portfolio['base_balance'] += quantity
                self.portfolio['quote_balance'] -= (price * quantity) + (price * quantity * 0.001)
                
                # 포지션 추가
                position = {
                    'symbol': self.symbol,
                    'side': 'long',
                    'amount': quantity,
                    'entry_price': price,
                    'leverage': self.exchange_api.leverage if hasattr(self.exchange_api, 'leverage') else 1,
                    'opened_at': order_time.isoformat(),
                    'status': 'open',
                    'additional_info': {
                        'order_id': order['id'],
                        'test_mode': True
                    }
                }
                self.portfolio['positions'].append(position)
                
                # 데이터베이스에 포지션 저장
                position_id = self.db.save_position(position)
                
                # 거래 내역 추가
                trade_record = {
                    'symbol': self.symbol,
                    'side': 'buy',
                    'order_type': 'market',
                    'amount': quantity,
                    'price': price,
                    'cost': price * quantity,
                    'fee': price * quantity * 0.001,
                    'timestamp': order_time.isoformat(),
                    'position_id': position_id,
                    'additional_info': {
                        'order_id': order['id'],
                        'test_mode': True
                    }
                }
                self.portfolio['trade_history'].append(trade_record)
                
                # 데이터베이스에 거래 내역 저장
                self.db.save_trade(trade_record)
                
                # 잔액 정보 저장
                self.db.save_balance(self.portfolio['base_currency'], self.portfolio['base_balance'])
                self.db.save_balance(self.portfolio['quote_currency'], self.portfolio['quote_balance'])
                
                # 현재 상태 저장
                self.save_state()
                
                logger.info(f"[테스트] 매수 주문 실행: 가격={price}, 수량={quantity}, 비용={price * quantity}")
                return order
            else:
                # 실제 거래소에 주문 실행
                order = self.exchange_api.create_market_buy_order(amount=quantity)
                
                if order:
                    logger.info(f"매수 주문 성공: {order}")
                    
                    # 포트폴리오 업데이트
                    self.update_portfolio()
                    
                    # 포지션 추가
                    position = {
                        'symbol': self.symbol,
                        'side': 'long',
                        'amount': quantity,
                        'entry_price': price,
                        'leverage': self.exchange_api.leverage if hasattr(self.exchange_api, 'leverage') else 1,
                        'opened_at': order_time.isoformat(),
                        'status': 'open',
                        'additional_info': {
                            'order_id': order['id'],
                            'test_mode': False
                        }
                    }
                    self.portfolio['positions'].append(position)
                    
                    # 데이터베이스에 포지션 저장
                    position_id = self.db.save_position(position)
                    
                    # 거래 내역 추가
                    trade_record = {
                        'symbol': self.symbol,
                        'side': 'buy',
                        'order_type': 'market',
                        'amount': quantity,
                        'price': price,
                        'cost': price * quantity,
                        'fee': order.get('fee', {}).get('cost', 0),
                        'timestamp': order_time.isoformat(),
                        'position_id': position_id,
                        'additional_info': {
                            'order_id': order['id'],
                            'test_mode': False
                        }
                    }
                    self.portfolio['trade_history'].append(trade_record)
                    
                    # 데이터베이스에 거래 내역 저장
                    self.db.save_trade(trade_record)
                    
                    # 잔액 정보 저장
                    self.db.save_balance(self.portfolio['base_currency'], self.portfolio['base_balance'])
                    self.db.save_balance(self.portfolio['quote_currency'], self.portfolio['quote_balance'])
                    
                    # 현재 상태 저장
                    self.save_state()
                    
                    return order
                else:
                    logger.error("매수 주문 실패")
                    return None
        
        except Exception as e:
            logger.error(f"매수 주문 실행 중 오류 발생: {e}")
            return None
    
    def execute_sell(self, price, quantity):
        """
        매도 주문 실행
        
        Args:
            price (float): 매도 가격
            quantity (float): 매도 수량
        
        Returns:
            dict: 주문 결과
        """
        try:
            order_time = datetime.now()
            if self.test_mode:
                # 테스트 모드에서는 주문을 시뮬레이션
                order = {
                    'id': f"test_sell_{order_time.timestamp()}",
                    'datetime': order_time.isoformat(),
                    'symbol': self.symbol,
                    'type': 'market',
                    'side': 'sell',
                    'price': price,
                    'amount': quantity,
                    'cost': price * quantity,
                    'fee': price * quantity * 0.001,  # 0.1% 수수료 가정
                    'status': 'closed'
                }
                
                # 포트폴리오 업데이트
                self.portfolio['base_balance'] -= quantity
                self.portfolio['quote_balance'] += (price * quantity) - (price * quantity * 0.001)
                
                # 포지션 업데이트 및 데이터베이스 저장
                position_id = None
                for i, position in enumerate(self.portfolio['positions']):
                    if position['status'] == 'open' and position['side'] == 'long':
                        # 포트폴리오 업데이트
                        self.portfolio['positions'][i]['closed_at'] = order_time.isoformat()
                        self.portfolio['positions'][i]['status'] = 'closed'
                        self.portfolio['positions'][i]['pnl'] = (price - position['entry_price']) * position['amount']
                        
                        # 데이터베이스 업데이트
                        update_data = {
                            'closed_at': order_time.isoformat(),
                            'status': 'closed',
                            'pnl': (price - position['entry_price']) * position['amount'],
                            'additional_info': {
                                'exit_price': price,
                                'profit_pct': (price - position['entry_price']) / position['entry_price'] * 100,
                                'exit_order_id': order['id']
                            }
                        }
                        
                        # 현재 포지션에 ID가 있는 경우 사용
                        if 'id' in position:
                            position_id = position['id']
                            self.db.update_position(position_id, update_data)
                        # 데이터베이스에서 포지션 찾기
                        else:
                            open_positions = self.db.get_open_positions(self.symbol)
                            for op in open_positions:
                                if op['status'] == 'open' and op['side'] == 'long':
                                    position_id = op['id']
                                    self.db.update_position(position_id, update_data)
                                    break
                        break
                
                # 거래 내역 추가
                trade_record = {
                    'symbol': self.symbol,
                    'side': 'sell',
                    'order_type': 'market',
                    'amount': quantity,
                    'price': price,
                    'cost': price * quantity,
                    'fee': price * quantity * 0.001,
                    'timestamp': order_time.isoformat(),
                    'position_id': position_id,
                    'additional_info': {
                        'order_id': order['id'],
                        'test_mode': True
                    }
                }
                self.portfolio['trade_history'].append(trade_record)
                
                # 데이터베이스에 거래 내역 저장
                self.db.save_trade(trade_record)
                
                # 잔액 정보 저장
                self.db.save_balance(self.portfolio['base_currency'], self.portfolio['base_balance'])
                self.db.save_balance(self.portfolio['quote_currency'], self.portfolio['quote_balance'])
                
                # 현재 상태 저장
                self.save_state()
                
                logger.info(f"[테스트] 매도 주문 실행: 가격={price}, 수량={quantity}, 수익={price * quantity}")
                return order
            else:
                # 실제 거래소에 주문 실행
                order = self.exchange_api.create_market_sell_order(amount=quantity)
                
                if order:
                    logger.info(f"매도 주문 성공: {order}")
                    
                    # 포트폴리오 업데이트
                    self.update_portfolio()
                    
                    # 포지션 업데이트 및 데이터베이스 저장
                    position_id = None
                    for i, position in enumerate(self.portfolio['positions']):
                        if position['status'] == 'open' and position['side'] == 'long':
                            # 포트폴리오 업데이트
                            self.portfolio['positions'][i]['closed_at'] = order_time.isoformat()
                            self.portfolio['positions'][i]['status'] = 'closed'
                            self.portfolio['positions'][i]['pnl'] = (price - position['entry_price']) * position['amount']
                            
                            # 데이터베이스 업데이트
                            update_data = {
                                'closed_at': order_time.isoformat(),
                                'status': 'closed',
                                'pnl': (price - position['entry_price']) * position['amount'],
                                'additional_info': {
                                    'exit_price': price,
                                    'profit_pct': (price - position['entry_price']) / position['entry_price'] * 100,
                                    'exit_order_id': order['id']
                                }
                            }
                            
                            # 현재 포지션에 ID가 있는 경우 사용
                            if 'id' in position:
                                position_id = position['id']
                                self.db.update_position(position_id, update_data)
                            # 데이터베이스에서 포지션 찾기
                            else:
                                open_positions = self.db.get_open_positions(self.symbol)
                                for op in open_positions:
                                    if op['status'] == 'open' and op['side'] == 'long':
                                        position_id = op['id']
                                        self.db.update_position(position_id, update_data)
                                        break
                            break
                    
                    # 거래 내역 추가
                    trade_record = {
                        'symbol': self.symbol,
                        'side': 'sell',
                        'order_type': 'market',
                        'amount': quantity,
                        'price': price,
                        'cost': price * quantity,
                        'fee': order.get('fee', {}).get('cost', 0),
                        'timestamp': order_time.isoformat(),
                        'position_id': position_id,
                        'additional_info': {
                            'order_id': order['id'],
                            'test_mode': False
                        }
                    }
                    self.portfolio['trade_history'].append(trade_record)
                    
                    # 데이터베이스에 거래 내역 저장
                    self.db.save_trade(trade_record)
                    
                    # 잔액 정보 저장
                    self.db.save_balance(self.portfolio['base_currency'], self.portfolio['base_balance'])
                    self.db.save_balance(self.portfolio['quote_currency'], self.portfolio['quote_balance'])
                    
                    # 현재 상태 저장
                    self.save_state()
                    
                    return order
                else:
                    logger.error("매도 주문 실패")
                    return None
        
        except Exception as e:
            logger.error(f"매도 주문 실행 중 오류 발생: {e}")
            return None
    
    def check_stop_loss_take_profit(self, current_price):
        """
        손절매 및 이익실현 조건 확인
        
        Args:
            current_price (float): 현재 가격
        
        Returns:
            int: 신호 (0: 중립, -1: 매도)
        """
        try:
            # 열린 포지션이 없으면 중립
            open_positions = [p for p in self.portfolio['positions'] if p['status'] == 'open']
            if not open_positions:
                return 0
            
            for position in open_positions:
                if position['side'] == 'long':
                    # 손절매 조건 확인
                    stop_loss_price = position['entry_price'] * (1 - self.risk_management['stop_loss_pct'])
                    if current_price <= stop_loss_price:
                        logger.info(f"손절매 조건 충족: 진입가={position['entry_price']}, 현재가={current_price}, 손절가={stop_loss_price}")
                        return -1
                    
                    # 이익실현 조건 확인
                    take_profit_price = position['entry_price'] * (1 + self.risk_management['take_profit_pct'])
                    if current_price >= take_profit_price:
                        logger.info(f"이익실현 조건 충족: 진입가={position['entry_price']}, 현재가={current_price}, 이익실현가={take_profit_price}")
                        return -1
            
            return 0
        
        except Exception as e:
            logger.error(f"손절매/이익실현 확인 중 오류 발생: {e}")
            return 0
    
    def process_trading_signals(self, df):
        """
        거래 신호 처리
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            int: 처리된 신호 (1: 매수, 0: 중립, -1: 매도)
        """
        try:
            # 전략에 따른 신호 생성
            df_with_signals = self.strategy.generate_signals(df)
            
            # 마지막 신호 가져오기
            current_signal = df_with_signals['signal'].iloc[-1]
            
            # 현재 가격
            current_price = df['close'].iloc[-1]
            
            # 손절매/이익실현 확인
            sl_tp_signal = self.check_stop_loss_take_profit(current_price)
            
            # 손절매/이익실현 신호가 있으면 우선 처리
            if sl_tp_signal == -1:
                return -1
            
            # 신호가 변경된 경우에만 처리
            if current_signal != self.last_signal:
                logger.info(f"신호 변경: {self.last_signal} -> {current_signal}")
                self.last_signal = current_signal
                return current_signal
            
            return 0  # 신호 없음
        
        except Exception as e:
            logger.error(f"거래 신호 처리 중 오류 발생: {e}")
            return 0
    
    def execute_trading_cycle(self):
        """단일 거래 사이클 실행"""
        try:
            # 최근 데이터 가져오기
            df = self.data_collector.fetch_recent_data(limit=100)
            
            if df is None or df.empty:
                logger.warning("거래 데이터를 가져오지 못했습니다.")
                return
            
            # 현재 가격
            current_price = df['close'].iloc[-1]
            
            # 거래 신호 처리
            signal = self.process_trading_signals(df)
            
            # 포트폴리오 업데이트
            self.update_portfolio()
            
            # 매수 신호
            if signal == 1:
                # 이미 포지션이 있는지 확인
                open_positions = [p for p in self.portfolio['positions'] if p['status'] == 'open']
                if open_positions:
                    logger.info("이미 열린 포지션이 있어 매수 신호를 무시합니다.")
                    return
                
                # 매수 수량 계산
                quantity = self.calculate_position_size(current_price)
                
                if quantity > 0:
                    # 매수 주문 실행
                    self.execute_buy(current_price, quantity)
                else:
                    logger.warning("매수 수량이 0이하입니다.")
            
            # 매도 신호
            elif signal == -1:
                # 열린 포지션 확인
                open_positions = [p for p in self.portfolio['positions'] if p['status'] == 'open']
                
                if not open_positions:
                    logger.info("열린 포지션이 없어 매도 신호를 무시합니다.")
                    return
                
                # 총 보유 수량 계산
                total_quantity = sum(p['quantity'] for p in open_positions)
                
                if total_quantity > 0:
                    # 매도 주문 실행
                    self.execute_sell(current_price, total_quantity)
                else:
                    logger.warning("매도할 수량이 0이하입니다.")
        
        except Exception as e:
            logger.error(f"거래 사이클 실행 중 오류 발생: {e}")
    
    def start_trading(self, interval=60):
        """
        자동 거래 시작
        
        Args:
            interval (int): 거래 사이클 간격 (초)
        """
        try:
            if self.trading_active:
                logger.warning("이미 거래가 활성화되어 있습니다.")
                return
            
            self.trading_active = True
            logger.info(f"자동 거래를 시작합니다. (간격: {interval}초)")
            
            # 포트폴리오 초기화
            self.update_portfolio()
            
            # 거래 루프
            while self.trading_active:
                try:
                    # 거래 사이클 실행
                    self.execute_trading_cycle()
                    
                    # 거래 기록 저장
                    self.save_trade_history()
                    
                    # 다음 사이클까지 대기
                    time.sleep(interval)
                
                except Exception as e:
                    logger.error(f"거래 루프 중 오류 발생: {e}")
                    time.sleep(10)  # 오류 발생 시 10초 대기
        
        except KeyboardInterrupt:
            logger.info("사용자에 의해 거래가 중단되었습니다.")
            self.stop_trading()
        
        except Exception as e:
            logger.error(f"거래 시작 중 오류 발생: {e}")
            self.stop_trading()
    
    def start_trading_thread(self, interval=60):
        """
        별도 스레드에서 자동 거래 시작
        
        Args:
            interval (int): 거래 사이클 간격 (초)
        """
        try:
            if self.trading_active:
                logger.warning("이미 거래가 활성화되어 있습니다.")
                return
            
            # 거래 스레드 시작
            trading_thread = threading.Thread(target=self.start_trading, args=(interval,))
            trading_thread.daemon = True
            trading_thread.start()
            
            logger.info("별도 스레드에서 자동 거래를 시작했습니다.")
            return trading_thread
        
        except Exception as e:
            logger.error(f"거래 스레드 시작 중 오류 발생: {e}")
            return None
    
    def stop_trading(self):
        """자동 거래 중지"""
        self.trading_active = False
        logger.info("자동 거래를 중지합니다.")
    
    def save_trade_history(self):
        """거래 기록 저장"""
        try:
            # 거래 기록이 없으면 저장하지 않음
            if not self.portfolio['trade_history']:
                return
            
            # 거래 기록 저장
            self.data_manager.save_trade_history(
                self.portfolio['trade_history'],
                strategy_name=self.strategy.name
            )
            
            logger.info(f"거래 기록 저장 완료 (총 {len(self.portfolio['trade_history'])}개)")
        
        except Exception as e:
            logger.error(f"거래 기록 저장 중 오류 발생: {e}")
    
    def get_portfolio_summary(self):
        """
        포트폴리오 요약 정보 반환
        
        Returns:
            dict: 포트폴리오 요약 정보
        """
        try:
            # 현재 가격 가져오기
            ticker = self.exchange_api.get_ticker()
            current_price = ticker['last'] if ticker else 0
            
            # 열린 포지션
            open_positions = [p for p in self.portfolio['positions'] if p['status'] == 'open']
            
            # 닫힌 포지션
            closed_positions = [p for p in self.portfolio['positions'] if p['status'] == 'closed']
            
            # 총 수익/손실
            total_profit = sum(p.get('profit', 0) for p in closed_positions)
            total_profit_pct = sum(p.get('profit_pct', 0) for p in closed_positions) / len(closed_positions) if closed_positions else 0
            
            # 미실현 수익/손실
            unrealized_profit = sum((current_price - p['entry_price']) * p['quantity'] for p in open_positions)
            unrealized_profit_pct = sum((current_price - p['entry_price']) / p['entry_price'] * 100 for p in open_positions) / len(open_positions) if open_positions else 0
            
            # 총 자산 가치
            total_base_value = self.portfolio['base_balance'] * current_price
            total_value = self.portfolio['quote_balance'] + total_base_value
            
            # 거래 통계
            total_trades = len(self.portfolio['trade_history'])
            buy_trades = len([t for t in self.portfolio['trade_history'] if t['type'] == 'buy'])
            sell_trades = len([t for t in self.portfolio['trade_history'] if t['type'] == 'sell'])
            
            return {
                'timestamp': datetime.now().isoformat(),
                'base_currency': self.portfolio['base_currency'],
                'quote_currency': self.portfolio['quote_currency'],
                'base_balance': self.portfolio['base_balance'],
                'quote_balance': self.portfolio['quote_balance'],
                'current_price': current_price,
                'total_base_value': total_base_value,
                'total_value': total_value,
                'open_positions': len(open_positions),
                'closed_positions': len(closed_positions),
                'total_profit': total_profit,
                'total_profit_pct': total_profit_pct,
                'unrealized_profit': unrealized_profit,
                'unrealized_profit_pct': unrealized_profit_pct,
                'total_trades': total_trades,
                'buy_trades': buy_trades,
                'sell_trades': sell_trades,
                'strategy': self.strategy.name,
                'test_mode': self.test_mode
            }
        
        except Exception as e:
            logger.error(f"포트폴리오 요약 정보 생성 중 오류 발생: {e}")
            return {}

# 테스트 코드
if __name__ == "__main__":
    # 거래 알고리즘 초기화 (테스트 모드)
    algorithm = TradingAlgorithm(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='1h',
        initial_balance=10000,  # 10,000 USDT
        test_mode=True
    )
    
    # 최근 데이터 가져오기
    df = algorithm.data_collector.fetch_recent_data(limit=100)
    
    if df is not None and not df.empty:
        # 단일 거래 사이클 테스트
        algorithm.execute_trading_cycle()
        
        # 포트폴리오 요약 정보 출력
        summary = algorithm.get_portfolio_summary()
        print("\n포트폴리오 요약 정보:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
    else:
        print("테스트할 데이터가 없습니다.")
