"""
거래 알고리즘 모듈 - 암호화폐 자동매매 봇

이 모듈은 거래 신호 생성 및 주문 실행을 담당하는 거래 알고리즘을 구현합니다.
다양한 전략을 기반으로 매수/매도 신호를 생성하고 실제 거래를 수행합니다.
"""

import os
import sys
import json
import time
import random
import threading
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

from src.exchange_api import ExchangeAPI
from src.data_manager import DataManager
from src.data_collector import DataCollector
from src.data_analyzer import DataAnalyzer
from src.db_manager import DatabaseManager
from src.auto_position_manager import AutoPositionManager
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
        
        # 자동 포지션 관리자 초기화
        self.auto_position_manager = AutoPositionManager(self)
        self.auto_sl_tp_enabled = False  # 자동 손절매/이익실현 활성화 여부
        self.partial_tp_enabled = False  # 부분 이익실현 활성화 여부
        
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
    
    def test_connection(self):
        """
        거래소 API 연결 테스트
        """
        try:
            # 시장 정보 가져오기 시도
            markets = self.exchange.load_markets()
            if self.symbol in markets:
                return True
            return False
        except Exception as e:
            logger.error(f"거래소 연결 테스트 중 오류 발생: {e}")
            return False
            
    def _get_min_order_qty(self):
        """
        심볼에 대한 최소 주문 수량을 가져온다.
        
        Returns:
            float: 최소 주문 수량, 가져오기 실패 시 0.001 기본값 사용
        """
        try:
            # 시장 정보 업데이트
            markets = self.exchange.load_markets()
            
            # 해당 시장에서 최소 주문 수량 가져오기
            if self.symbol in markets:
                market = markets[self.symbol]
                limits = market.get('limits', {})
                amount = limits.get('amount', {})
                min_amount = amount.get('min', 0.001)  # 기본값 0.001
                return min_amount
            else:
                logger.warning(f"심볼 정보를 찾을 수 없음: {self.symbol}, 기본값 사용")
                return 0.001
        except Exception as e:
            logger.error(f"최소 주문 수량 가져오기 실패: {e}")
            return 0.001  # 오류 발생 시 기본값 사용
    
    def execute_sell(self, price, quantity, additional_exit_info=None, percentage=1.0, position_id=None):
        """
        매도 주문 실행
        
        Args:
            price (float): 매도 가격
            quantity (float): 매도 수량 (총 수량)
            additional_exit_info (dict, optional): 추가 종료 정보 (자동 손절매/이익실현 등)
                                                   예: {'exit_type': 'stop_loss', 'exit_reason': '...', 'level_index': 0}
            percentage (float): 청산할 포지션의 비율 (0~1 사이 값, 기본값 1.0은 전체 청산)
            position_id (str, optional): 포지션 ID (지정되지 않으면 찾아서 사용)
        
        Returns:
            dict: 주문 결과
        """
        try:
            order_time = datetime.now()
            
            # 백분율 범위 검증 (0~1 사이로 제한)
            percentage = max(0.0, min(1.0, percentage))  # 0.0~1.0 범위로 제한
            
            # 실제 매도할 수량 계산 (percentage에 따라 조정)
            actual_quantity = quantity * percentage
            
            # 유효한 매도 수량인지 확인
            if actual_quantity <= 0:
                logger.warning(f"유효하지 않은 매도 수량: {actual_quantity}")
                return None
            
            # 최소 주문 수량 검증
            min_order_qty = self._get_min_order_qty()
            if actual_quantity < min_order_qty:
                if percentage < 1.0:
                    logger.warning(f"부분 청산 수량이 최소 주문 수량보다 작음. 전량 청산으로 변경: {actual_quantity} < {min_order_qty}")
                    actual_quantity = quantity
                    percentage = 1.0
                else:
                    logger.warning(f"주문 수량이 최소 주문 수량보다 작음: {actual_quantity} < {min_order_qty}")
                    if actual_quantity < min_order_qty * 0.5:  # 최소 주문의 절반보다 작으면 주문 취소
                        logger.error(f"주문 수량이 너무 작아 주문 취소: {actual_quantity}")
                        return None
            
            # 부분 청산 로깅
            is_partial = (percentage < 1.0)
            if is_partial:
                logger.info(f"부분 청산 실행: {percentage:.1%} ({actual_quantity}/{quantity})")
                
                # 부분 청산 시 청산 이력 업데이트 (중복 청산 방지)
                if position_id and additional_exit_info and additional_exit_info.get('exit_type') == 'partial_tp':
                    # 어떤 TP 레벨에서 청산되었는지 확인
                    level_idx = additional_exit_info.get('level_index')
                    if level_idx is not None:
                        # RiskManager의 tp_executed_levels 업데이트
                        if position_id in self.exchange_api.risk_manager.tp_executed_levels:
                            try:
                                self.exchange_api.risk_manager.tp_executed_levels[position_id][level_idx] = True
                                logger.info(f"청산 이력 업데이트 성공: position_id={position_id}, level={level_idx}")
                            except (IndexError, TypeError) as e:
                                logger.error(f"tp_executed_levels 업데이트 실패: {e}")
            
            # 포지션 잔여량 검증
            remaining = quantity - actual_quantity
            if 0 < remaining < min_order_qty:
                logger.warning(f"잔여량이 최소 주문 수량보다 작음. 전량 청산으로 변경: {remaining} < {min_order_qty}")
                actual_quantity = quantity
                percentage = 1.0
                is_partial = False
        except Exception as e:
            logger.error(f"매도 주문 실행 중 오류 발생: {e}")
            return None
        
        if self.test_mode:
            # 테스트 모드에서는 주문을 시ミュ레이션
            order = {
                'id': f"test_sell_{order_time.timestamp()}",
                'datetime': order_time.isoformat(),
                'symbol': self.symbol,
                'type': 'market',
                'side': 'sell',
                'price': price,
                'amount': actual_quantity,  # 조정된 수량 사용
                'cost': price * actual_quantity,
                'fee': price * actual_quantity * 0.001,  # 0.1% 수수료 가정
                'status': 'closed',
                'percentage_sold': percentage  # 청산 비율 추가
            }
            
            # 포트폴리오 업데이트
            self.portfolio['base_balance'] -= actual_quantity
            self.portfolio['quote_balance'] += (price * actual_quantity) - (price * actual_quantity * 0.001)
            
            # 실제 주문 실행 완료 상태를 리턴
            return order
            
        else:
            # 실제 거래소 주문 실행
            try:
                # 거래소 API를 통한 실제 매도 주문
                order = self.exchange_api.create_order(
                    symbol=self.symbol,
                    type='market',
                    side='sell',
                    amount=actual_quantity
                )
                
                logger.info(f"매도 주문 성공: {order['id']}, 가격: {price}, 수량: {actual_quantity}")
                return order
            except Exception as e:
                logger.error(f"매도 주문 실행 중 추가 오류 발생: {e}")
                return None
        
        # 포지션 잔여량 검증
        remaining = quantity - actual_quantity
        if 0 < remaining < min_order_qty:
            logger.warning(f"잔여량이 최소 주문 수량보다 작음. 전량 청산으로 변경: {remaining} < {min_order_qty}")
            actual_quantity = quantity
            percentage = 1.0
            is_partial = False
        
        if self.test_mode:
            # 테스트 모드에서는 주문을 시뮬레이션
            order = {
                'id': f"test_sell_{order_time.timestamp()}",
                'datetime': order_time.isoformat(),
                'symbol': self.symbol,
                'type': 'market',
                'side': 'sell',
                'price': price,
                'amount': actual_quantity,  # 조정된 수량 사용
                'cost': price * actual_quantity,
                'fee': price * actual_quantity * 0.001,  # 0.1% 수수료 가정
                'status': 'closed',
                'percentage_sold': percentage  # 청산 비율 추가
            }
            
            # 포트폴리오 업데이트
            self.portfolio['base_balance'] -= actual_quantity
            self.portfolio['quote_balance'] += (price * actual_quantity) - (price * actual_quantity * 0.001)
            
            # 포지션 업데이트 및 데이터베이스 저장
            target_position_id = position_id
            found_position = False
            
            for i, position in enumerate(self.portfolio['positions']):
                if position['status'] == 'open' and position['side'] == 'long':
                    found_position = True
                    
                    # 지정된 position_id가 있으면 해당 포지션만 처리
                    if target_position_id and position.get('id') != target_position_id:
                        continue
                        
                    # 수익/손실 계산
                    pnl = (price - position['entry_price']) * actual_quantity
                    profit_pct = (price - position['entry_price']) / position['entry_price'] * 100
                    
                    # 부분 청산인 경우
                    if percentage < 1.0:
                        # 수량 및 평균 진입가 조정
                        remaining_amount = position['amount'] - actual_quantity
                        logger.info(f"포지션 부분 청산: {actual_quantity} 청산, {remaining_amount} 남음")
                        
                        # 포트폴리오 업데이트 - 남은 수량 반영
                        self.portfolio['positions'][i]['amount'] = remaining_amount
                        self.portfolio['positions'][i]['partial_exits'] = self.portfolio['positions'][i].get('partial_exits', []) + [{
                            'time': order_time.isoformat(),
                            'price': price,
                            'amount': actual_quantity,
                            'percentage': percentage,
                            'pnl': pnl,
                            'profit_pct': profit_pct
                        }]
                    else:
                        # 전체 청산인 경우
                        self.portfolio['positions'][i]['closed_at'] = order_time.isoformat()
                        self.portfolio['positions'][i]['status'] = 'closed'
                        self.portfolio['positions'][i]['pnl'] = pnl
                        self.portfolio['positions'][i]['exit_price'] = price
                    
                    # 추가 종료 정보 처리
                    exit_info = {
                        'exit_price': price,
                        'profit_pct': (price - position['entry_price']) / position['entry_price'] * 100,
                        'exit_order_id': order['id']
                    }
                    
                    # 자동 종료(손절매/이익실현) 정보가 있는 경우 추가
                    if additional_exit_info:
                        exit_info.update({
                            'exit_type': additional_exit_info.get('exit_type', 'manual'),
                            'exit_reason': additional_exit_info.get('exit_reason', ''),
                            'auto_exit': additional_exit_info.get('auto_exit', False)
                        })
                        
                        # 로그 추가
                        exit_type = additional_exit_info.get('exit_type', 'manual')
                        logger.info(f"자동 종료 실행: {exit_type}, 이유: {additional_exit_info.get('exit_reason', '')}")
                    
                    # 데이터베이스 업데이트 데이터 준비
                    # 포지션 ID 가져오기
                    pos_id = None
                    if 'id' in position:
                        pos_id = position['id']
                    
                    # 데이터베이스 업데이트 데이터 구성
                    update_data = {
                        'additional_info': exit_info
                    }
                    
                    # 부분 청산이냐 전체 청산이냐에 따라 다른 데이터 추가
                    if percentage < 1.0:
                        # 부분 청산인 경우
                        partial_exit_data = {
                            'time': order_time.isoformat(),
                            'price': price,
                            'amount': actual_quantity,
                            'percentage': percentage,
                            'pnl': (price - position['entry_price']) * actual_quantity,
                            'exit_type': additional_exit_info.get('exit_type', 'manual'),
                            'exit_reason': additional_exit_info.get('exit_reason', '')
                        }
                        
                        # 기존 부분 청산 이력 업데이트
                        update_data['partial_exits'] = position.get('partial_exits', []) + [partial_exit_data]
                        update_data['amount'] = position['amount'] - actual_quantity
                        logger.info(f"부분 청산 정보 업데이트: {percentage:.1%}, 남은 수량: {update_data['amount']}")
                    else:
                        # 전체 청산인 경우
                        update_data.update({
                            'closed_at': order_time.isoformat(),
                            'status': 'closed',
                            'pnl': (price - position['entry_price']) * position['amount'],
                            'exit_price': price
                        })
                        logger.info(f"포지션 전체 청산 정보 업데이트")
                    
                    # 데이터베이스에 업데이트
                    if pos_id:
                        # 이미 ID가 있는 경우
                        self.db.update_position(pos_id, update_data)
                    else:
                        # 데이터베이스에서 포지션 찾기
                        open_positions = self.db.get_open_positions(self.symbol)
                        for op in open_positions:
                            if op['status'] == 'open' and op['side'] == 'long':
                                self.db.update_position(op['id'], update_data)
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
    
    def check_stop_loss_take_profit(self, current_price):
        """
        손절매 및 이익실현 조건 확인
        
        Args:
            current_price (float): 현재 가격
        
        Returns:
            tuple: (exit_signal, exit_info)
                  exit_signal (bool): 청산 신호 여부
                  exit_info (dict): 청산 관련 정보 (reason, type, percentage 등)
        """
        try:
            # 열린 포지션이 없으면 중립
            open_positions = [p for p in self.portfolio['positions'] if p['status'] == 'open']
            if not open_positions:
                return False, None
            
            for position in open_positions:
                # 포지션 ID 가져오기 (부분 청산 추적용)
                # 기본적으로 DB ID 사용, 없으면 포지션 고유 식별자 생성
                position_id = None
                
                # 1. 포지션에 ID가 있는 경우
                if 'id' in position:
                    position_id = position['id']
                # 2. 포지션에 ID가 없으면 고유한 식별자 생성 (entry_time + entry_price)
                elif 'entry_time' in position and 'entry_price' in position:
                    # 진입 시간과 가격으로 더 안정적인 ID 생성
                    entry_time_str = position.get('entry_time', '')
                    entry_price_str = str(position.get('entry_price', 0))
                    position_id = f"{entry_time_str}_{entry_price_str}_{position.get('side', 'unknown')}"
                # 3. 그래도 없으면 현재 시간 + 난수 사용
                else:
                    position_id = f"pos_{int(time.time())}_{random.randint(1000, 9999)}"
                    logger.warning(f"포지션 ID가 없어 임시 ID 생성함: {position_id}")
                
                # 안전성 검사 - entry_price가 0이면 오류 방지
                if position.get('entry_price', 0) <= 0:
                    logger.error(f"유효하지 않은 진입가격: {position.get('entry_price')}")
                    continue
                    
                # 손절매 가격 계산
                stop_loss_price = position['entry_price'] * (1 - self.risk_management['stop_loss_pct'])
                # 이익실현 가격 계산
                take_profit_price = position['entry_price'] * (1 + self.risk_management['take_profit_pct'])
                
                # RiskManager의 check_exit_conditions 메서드 활용 (부분 청산 지원 형식)
                exit_type, exit_reason, exit_percentage = self.exchange_api.risk_manager.check_exit_conditions(
                    current_price=current_price,
                    position_type=position['side'],
                    entry_price=position['entry_price'],
                    stop_loss_price=stop_loss_price,
                    take_profit_price=take_profit_price,
                    position_id=position_id,
                    check_partial=True
                )
                
                if exit_type:
                    logger.info(f"{exit_type} 조건 충족: {exit_reason}, 청산비율: {exit_percentage:.1%}")
                    
                    # 종료 정보 구성
                    exit_info = {
                        'type': exit_type,
                        'reason': exit_reason,
                        'percentage': exit_percentage,
                        'position_id': position_id
                    }
                    
                    # 부분 청산인지 확인
                    is_partial = (exit_type == 'partial_tp' and exit_percentage < 1.0)
                    if is_partial:
                        logger.info(f"부분 청산 신호 발견: {exit_percentage:.1%}")
                    
                    # 청산 신호 반환
                    return True, exit_info
            
            return False, None
        
        except Exception as e:
            logger.error(f"손절매/이익실현 확인 중 오류 발생: {e}")
            return False, None
    
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
            
            # 손절매/이익실현 확인 (튜플 반환: 신호, 종료 이유)
            sl_tp_signal, exit_reason = self.check_stop_loss_take_profit(current_price)
            
            # 손절매/이익실현 신호가 있으면 우선 처리
            if sl_tp_signal == -1:
                logger.info(f"자동 종료 신호 처리: {exit_reason}")
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
            
            # 거래 신호 처리 (특수 신호 정보를 저장하기 위해 추가 정보 가져오기)
            signal = 0  # 기본값 초기화: 중립
            exit_info = None
            is_auto_exit = False
            
            # 자동 손절매/이익실현 확인 (변경된 형식)
            exit_signal, exit_details = self.check_stop_loss_take_profit(current_price)
            
            if exit_signal and exit_details:
                # 자동 종료(손절매/이익실현) 처리
                signal = -1  # 매도 신호 설정
                is_auto_exit = True
                exit_info = exit_details
                
                # 종료 정보 추출
                exit_type = exit_info.get('type')
                exit_reason = exit_info.get('reason')
                exit_percentage = exit_info.get('percentage', 1.0)
                position_id = exit_info.get('position_id')
                
                # 부분 청산 여부 확인
                is_partial = (exit_type == 'partial_tp' and exit_percentage < 1.0)
                
                if is_partial:
                    logger.info(f"자동 부분 청산 실행: {exit_type}, 비율: {exit_percentage:.1%}, 이유: {exit_reason}")
                else:
                    logger.info(f"자동 포지션 종료: {exit_type}, 이유: {exit_reason}")
            else:
                # 그 외 신호 처리(일반 매매)
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
                total_quantity = sum(p['amount'] for p in open_positions if 'amount' in p)
                if not total_quantity > 0:
                    total_quantity = sum(p['quantity'] for p in open_positions if 'quantity' in p)
                
                if total_quantity > 0:
                    # 자동 청산인 경우
                    if is_auto_exit and exit_info:
                        # 부분 청산 여부 확인
                        exit_type = exit_info.get('type')
                        exit_reason = exit_info.get('reason')
                        exit_percentage = exit_info.get('percentage', 1.0)
                        position_id = exit_info.get('position_id')
                        
                        # 추가 정보 구성
                        additional_exit_info = {
                            'exit_type': exit_type,
                            'exit_reason': exit_reason,
                            'auto_exit': True
                        }
                        
                        # 매도 주문 실행 (부분 청산 지원)
                        self.execute_sell(
                            price=current_price, 
                            quantity=total_quantity, 
                            additional_exit_info=additional_exit_info,
                            percentage=exit_percentage,
                            position_id=position_id
                        )
                        
                        # 부분 청산 로깅
                        if exit_percentage < 1.0:
                            logger.info(f"부분 청산 실행 완료: {exit_percentage:.1%}, 유형: {exit_type}")
                    else:
                        # 일반 매도 주문 실행 (전체 청산)
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
    
    def start_trading_thread(self, interval=60, auto_sl_tp=False, partial_tp=False):
        """
        별도 스레드에서 자동 거래 시작
        
        Args:
            interval (int): 거래 사이클 간격 (초)
            auto_sl_tp (bool): 자동 손절매/이익실현 활성화 여부
            partial_tp (bool): 부분 이익실현 활성화 여부
        """
        try:
            if self.trading_active:
                logger.warning("이미 거래가 활성화되어 있습니다.")
                return
            
            # 자동 손절매/이익실현 설정
            self.auto_sl_tp_enabled = auto_sl_tp
            self.partial_tp_enabled = partial_tp
            self.auto_position_manager.set_auto_sl_tp(auto_sl_tp)
            self.auto_position_manager.set_partial_tp(partial_tp)
            
            # 포지션 모니터링 시작
            if auto_sl_tp:
                self.auto_position_manager.start_monitoring()
                logger.info(f"자동 손절매/이익실현 기능 활성화 (부분 청산: {partial_tp})")
            
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
        
        # 자동 포지션 모니터링 중지
        self.auto_position_manager.stop_monitoring()
        logger.info("자동 거래를 중지합니다. 자동 포지션 관리 기능도 중지되었습니다.")
    
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
