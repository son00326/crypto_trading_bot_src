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
from src.error_handlers import (
    simple_error_handler, safe_execution, api_error_handler,
    network_error_handler, db_error_handler, trade_error_handler
)

from src.exchange_api import ExchangeAPI
from src.data_manager import DataManager
from src.data_collector import DataCollector
from src.data_analyzer import DataAnalyzer
from src.db_manager import DatabaseManager
from src.auto_position_manager import AutoPositionManager
from src.risk_manager import RiskManager
from src.portfolio_manager import PortfolioManager
from src.order_executor import OrderExecutor
from src.models import Position, Order, Trade, TradeSignal
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
        
        # 포트폴리오 매니저 초기화
        self.portfolio_manager = PortfolioManager(
            exchange_api=self.exchange_api,
            db_manager=self.db,
            symbol=symbol,
            initial_balance=initial_balance,
            test_mode=test_mode
        )
        
        # 주문 실행자 초기화
        self.order_executor = OrderExecutor(
            exchange_api=self.exchange_api,
            db_manager=self.db,
            test_mode=test_mode
        )
        
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
        
        # 이전 버전과의 호환성을 위해 포트폴리오 객체 유지 (향후 리팩토링 시 제거 예정)
        self.portfolio = self.portfolio_manager.portfolio
        
        # 거래 상태 (기본값)
        self.trading_active = False
        self.last_signal = 0  # 0: 중립, 1: 매수, -1: 매도
        
        # 자동 포지션 관리자 초기화
        self.auto_position_manager = AutoPositionManager(self)
        self.auto_sl_tp_enabled = False  # 자동 손절매/이익실현 활성화 여부
        self.partial_tp_enabled = False  # 부분 이익실현 활성화 여부
        
        # 위험 관리 설정
        self.risk_management = RISK_MANAGEMENT.copy()
        
        # 위험 관리자 초기화
        self.risk_manager = RiskManager(exchange_id=exchange_id, symbol=symbol, risk_config=self.risk_management)
        
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
            
            # 봇 상태 저장
            self.db.save_bot_state(bot_state)
            logger.info("봇 상태 저장 완료")
            
            # PortfolioManager를 통한 포트폴리오 상태 저장
            portfolio_saved = self.portfolio_manager.save_state()
            
            if portfolio_saved:
                logger.info("포트폴리오 상태 저장 완료")
            else:
                logger.warning("포트폴리오 상태 저장 실패")
                
            # 이전 버전과의 호환성을 위해 추가 저장 작업 수행
            # 현재 잔액 저장
            self.db.save_balance(self.portfolio['base_currency'], 
                                self.portfolio['base_balance'],
                                {'source': 'automatic_save'})
            
            self.db.save_balance(self.portfolio['quote_currency'], 
                                self.portfolio['quote_balance'],
                                {'source': 'automatic_save'})
            
            return True
        except Exception as e:
            logger.error(f"상태 저장 중 오류 발생: {e}")
            return False
    
    def update_portfolio(self):
        """포트폴리오 정보 업데이트"""
        try:
            # PortfolioManager를 통해 포트폴리오 업데이트
            self.portfolio_manager.update_portfolio()
            
            # 이전 버전과의 호환성을 위해 포트폴리오 참조 업데이트
            self.portfolio = self.portfolio_manager.portfolio
            
            # 로깅
            base_currency = self.portfolio['base_currency']
            quote_currency = self.portfolio['quote_currency']
            logger.info(f"포트폴리오 업데이트: {base_currency}={self.portfolio['base_balance']}, {quote_currency}={self.portfolio['quote_balance']}")
            
        except Exception as e:
            logger.error(f"포트폴리오 업데이트 중 오류 발생: {e}")
            return False
        
        return True
    
    @simple_error_handler(default_return=False)
    def update_portfolio_after_trade(self, trade_type, price, quantity, fee=None, is_test=None):
        """
        거래 후 포트폴리오 업데이트
        
        Args:
            trade_type (str): 거래 유형 ('buy' 또는 'sell')
            price (float): 거래 가격
            quantity (float): 거래 수량
            fee (float, optional): 수수료, None인 경우 기본값 사용
            is_test (bool, optional): 테스트 모드 여부, None인 경우 현재 객체 상태 사용
        """
        # PortfolioManager를 통해 포트폴리오 업데이트
        result = self.portfolio_manager.update_portfolio_after_trade(
            trade_type=trade_type,
            price=price,
            quantity=quantity,
            fee=fee,
            is_test=is_test
        )
        
        # 이전 버전과의 호환성을 위해 포트폴리오 참조 업데이트
        self.portfolio = self.portfolio_manager.portfolio
        
        logger.info(f"거래 후 포트폴리오 업데이트: {trade_type}, 가격={price}, 수량={quantity}, 수수료={fee if fee else '기본값'}")
        return result
    
    def calculate_position_size(self, price):
        """
        위험 관리 설정에 따른 포지션 크기 계산
        RiskManager의 계산 로직을 활용합니다.
        
        Args:
            price (float): 현재 가격
        
        Returns:
            float: 매수/매도할 수량
        """
        try:
            # PortfolioManager를 통해 사용 가능한 잔고 확인
            available_balance = self.portfolio_manager.get_available_balance(self.portfolio['quote_currency'])
            
            # RiskManager를 통한 포지션 크기 계산
            quantity = self.risk_manager.calculate_position_size(available_balance, price)
            
            # OrderExecutor에서 최소 주문 수량 확인
            min_quantity = self.order_executor.min_order_qty
            
            if quantity < min_quantity:
                logger.warning(f"계산된 수량({quantity})이 최소 주문 수량({min_quantity})보다 작습니다.")
                return 0
            
            return quantity
        
        except Exception as e:
            logger.error(f"포지션 크기 계산 중 오류 발생: {e}")
            return 0
    
    @trade_error_handler(retry_count=2, max_delay=10)
    def execute_buy(self, price, quantity, additional_info=None, close_position=False, position_id=None):
        """
        매수 주문 실행
        
        Args:
            price (float): 매수 가격
            quantity (float): 매수 수량
            additional_info (dict, optional): 추가 정보 (자동 손절매/이익실현 등에 의한 포지션 종료 정보)
            close_position (bool, optional): 숏 포지션 종료를 위한 매수인지 여부
            position_id (str, optional): 포지션 ID (종료 시 사용)
        
        Returns:
            dict: 주문 결과
        """
        if quantity <= 0:
            logger.warning(f"유효하지 않은 주문 수량: {quantity}")
            return None
            
        try:
            # OrderExecutor를 사용하여 주문 실행
            order = self.order_executor.execute_buy(
                price=price,
                quantity=quantity,
                portfolio=self.portfolio,  # 이전 버전과의 호환성을 위해 전달
                additional_info=additional_info,
                close_position=close_position,
                position_id=position_id
            )
            
            if order:
                # 포트폴리오 업데이트
                self.portfolio_manager.update_portfolio_after_trade('buy', price, quantity)
                
                # 자동 손절매/이익실현 설정
                if not close_position and self.auto_sl_tp_enabled and order.get('id'):
                    position_id = order.get('id')
                    stop_loss_price = self.risk_manager.calculate_stop_loss_price(
                        price, 'long', self.risk_management['stop_loss_percentage']
                    )
                    take_profit_price = self.risk_manager.calculate_take_profit_price(
                        price, 'long', self.risk_management['take_profit_percentage']
                    )
                    
                    logger.info(f"자동 SL/TP 설정: SL={stop_loss_price}, TP={take_profit_price}")
                    
                    # 포지션 객체 가져오기
                    open_positions = self.portfolio_manager.get_open_positions(self.symbol)
                    for position in open_positions:
                        if position.get('id') == position_id:
                            # 데이터베이스에 SL/TP 저장
                            self.db.update_position(position_id, {
                                'stop_loss': stop_loss_price,
                                'take_profit': take_profit_price,
                                'auto_sl_tp': True
                            })
                            break
                
                # 새 포트폴리오 상태를 참조하도록 업데이트 (이전 버전과의 호환성을 위해)
                self.portfolio = self.portfolio_manager.portfolio
                
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
    
    @trade_error_handler(retry_count=2, max_delay=10)
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
        if quantity <= 0:
            logger.warning(f"유효하지 않은 매도 수량: {quantity}")
            return None
            
        try:
            # 백분율 범위 검증 (0~1 사이로 제한)
            percentage = max(0.0, min(1.0, percentage))  # 0.0~1.0 범위로 제한
            
            # OrderExecutor를 사용하여 주문 실행
            order = self.order_executor.execute_sell(
                price=price,
                quantity=quantity,
                portfolio=self.portfolio,  # 이전 버전과의 호환성을 위해 전달
                additional_exit_info=additional_exit_info,
                percentage=percentage,
                position_id=position_id
            )
            
            if order:
                # 포트폴리오 업데이트
                actual_quantity = quantity * percentage
                self.portfolio_manager.update_portfolio_after_trade('sell', price, actual_quantity)
                
                # 포지션 종료 처리
                order_time = datetime.now()
                self.portfolio_manager.update_position_after_exit(
                    order=order, 
                    order_time=order_time, 
                    price=price, 
                    actual_quantity=actual_quantity, 
                    percentage=percentage, 
                    position_id=position_id, 
                    additional_exit_info=additional_exit_info
                )
                
                # 새 포트폴리오 상태를 참조하도록 업데이트 (이전 버전과의 호환성을 위해)
                self.portfolio = self.portfolio_manager.portfolio
                
                # 매도 정보 로깅
                if additional_exit_info and additional_exit_info.get('exit_type'):
                    exit_type = additional_exit_info.get('exit_type')
                    exit_reason = additional_exit_info.get('exit_reason', '')
                    logger.info(f"매도 실행 ({exit_type}): 가격={price}, 수량={actual_quantity}, 이유={exit_reason}")
                else:
                    logger.info(f"매도 실행: 가격={price}, 수량={actual_quantity}")
                
                # 현재 상태 저장
                self.save_state()
                
                return order
            else:
                logger.error("매도 주문 실패")
                return None
                
        except Exception as e:
            logger.error(f"매도 주문 실행 중 오류 발생: {e}")
            return None
        
        if self.test_mode:
            # 테스트 모드에서는 주문을 시뮬레이션
            order = self._simulate_order(order_time, 'sell', price, actual_quantity, percentage)
            
            # 포트폴리오 업데이트
            self.portfolio['base_balance'] -= actual_quantity
            self.portfolio['quote_balance'] += (price * actual_quantity) - (price * actual_quantity * 0.001)
            
            # 포지션 업데이트 및 데이터베이스 저장
            self._update_position_after_exit(order, order_time, price, actual_quantity, percentage, position_id, additional_exit_info)
            
            # 잔액 정보는 update_portfolio_after_trade에서 자동으로 저장됨
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
    
    @safe_execution(retry_count=0, log_level="info")
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
                    
                # RiskManager를 통한 손절매/이익실현 가격 계산
                stop_loss_price = self.risk_manager.calculate_stop_loss_price(
                    position['entry_price'], 
                    position['side']
                )
                take_profit_price = self.risk_manager.calculate_take_profit_price(
                    position['entry_price'], 
                    position['side']
                )
                
                # RiskManager의 check_exit_conditions 메서드 활용 (부분 청산 지원 형식)
                # 이제 자체 risk_manager 인스턴스를 사용
                exit_type, exit_reason, exit_percentage = self.risk_manager.check_exit_conditions(
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
    
    @safe_execution(retry_count=1)
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
    
    @safe_execution(retry_count=2, log_level="error")
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
    
    def start_trading_thread(self, interval=60, auto_sl_tp=False, partial_tp=False, sl_percentage=None, tp_percentage=None):
        """
        별도 스레드에서 자동 거래 시작
        
        Args:
            interval (int): 거래 사이클 간격 (초)
            auto_sl_tp (bool): 자동 손절매/이익실현 활성화 여부
            partial_tp (bool): 부분 이익실현 활성화 여부
            sl_percentage (float): 손절매 비율 (기본값: 0.05)
            tp_percentage (float): 이익실현 비율 (기본값: 0.1)
        """
        try:
            if self.trading_active:
                logger.warning("이미 거래가 활성화되어 있습니다.")
                return
            
            # 자동 손절매/이익실현 설정
            self.auto_sl_tp_enabled = auto_sl_tp
            self.partial_tp_enabled = partial_tp
            
            # 위험 관리 설정에 손절매/이익실현 비율 설정
            if sl_percentage is not None and sl_percentage > 0:
                self.risk_management['stop_loss_pct'] = sl_percentage
            
            if tp_percentage is not None and tp_percentage > 0:
                self.risk_management['take_profit_pct'] = tp_percentage
            
            # auto_position_manager가 있는지 확인
            if not hasattr(self, 'auto_position_manager') or self.auto_position_manager is None:
                logger.warning("자동 포지션 관리자가 초기화되지 않음 - 새로 생성중...")
                try:
                    self.auto_position_manager = AutoPositionManager(self)
                    logger.info("자동 포지션 관리자 새로 초기화 성공")
                except Exception as e:
                    logger.error(f"자동 포지션 관리자 초기화 실패: {e}")
                    # 자동 손절매/이익실현 비활성화
                    auto_sl_tp = False
            
            if auto_sl_tp and hasattr(self, 'auto_position_manager') and self.auto_position_manager is not None:
                try:
                    # 자동 포지션 관리 설정 적용 - 새로 추가한 set_auto_sl_tp 메서드 사용
                    self.auto_position_manager.set_auto_sl_tp(
                        enabled=auto_sl_tp,
                        partial_tp=partial_tp,
                        sl_percentage=self.risk_management.get('stop_loss_pct', 0.05),
                        tp_percentage=self.risk_management.get('take_profit_pct', 0.1)
                    )
                    
                    # 포지션 모니터링이 자동으로 시작됨 (set_auto_sl_tp 안에서 처리)
                    logger.info(f"자동 손절매/이익실현 기능 활성화 (부분 청산: {partial_tp}, 손절: {self.risk_management.get('stop_loss_pct', 0.05):.1%}, 이익실현: {self.risk_management.get('take_profit_pct', 0.1):.1%})")
                except Exception as e:
                    logger.error(f"자동 포지션 관리 시작 중 오류: {e}")
            elif auto_sl_tp:
                logger.warning("자동 포지션 관리자가 없어 자동 손절매/이익실현 기능을 사용할 수 없습니다")
            elif auto_sl_tp:
                logger.warning("자동 포지션 관리자가 없어 자동 손절매/이익실현 기능을 사용할 수 없습니다")
            
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
        """자동 거래 중지 및 자동 포지션 관리 중지"""
        self.trading_active = False
        
        # 자동 포지션 모니터링 중지 (안전하게 처리)
        if hasattr(self, 'auto_position_manager') and self.auto_position_manager is not None:
            try:
                self.auto_position_manager.stop_monitoring()
                logger.info("자동 포지션 모니터링이 중지되었습니다.")
            except Exception as e:
                logger.error(f"자동 포지션 모니터링 중지 중 오류 발생: {e}")
        
        # 자동 손절매/이익실현 상태 초기화
        self.auto_sl_tp_enabled = False
        self.partial_tp_enabled = False
        
        # 최종 상태 저장
        try:
            self.save_state()
            logger.info("현재 거래 상태가 저장되었습니다.")
        except Exception as e:
            logger.error(f"거래 상태 저장 중 오류 발생: {e}")
        
        logger.info("자동 거래를 중지했습니다.")
    
    def _simulate_order(self, order_time, side, price, quantity, percentage=1.0):
        """
        주문 시뮬레이션 통합 메서드
        
        Args:
            order_time (datetime): 주문 시간
            side (str): 주문 유형 ('buy' 또는 'sell')
            price (float): 가격
            quantity (float): 수량
            percentage (float, optional): 포지션 청산 비율 (매도 시에만 사용)
            
        Returns:
            dict: 시뮬레이션된 주문 객체
        """
        order_id = f"test_{side.lower()}_{order_time.timestamp()}"
        
        order = {
            'id': order_id,
            'datetime': order_time.isoformat(),
            'symbol': self.symbol,
            'type': 'market',
            'side': side.lower(),
            'price': price,
            'amount': quantity,
            'cost': price * quantity,
            'fee': price * quantity * 0.001,  # 0.1% 수수료 가정
            'status': 'closed'
        }
        
        # 매도 주문인 경우 청산 비율 추가
        if side.lower() == 'sell':
            order['percentage_sold'] = percentage
            
        return order
        
    @db_error_handler(retry_count=3)
    def _update_position_after_exit(self, order, order_time, price, actual_quantity, percentage, position_id=None, additional_exit_info=None):
        """
        포지션 청산 후 포지션 정보 업데이트
        
        Args:
            order (dict): 주문 정보
            order_time (datetime): 주문 시간
            price (float): 종료 가격
            actual_quantity (float): 실제 청산된 수량
            percentage (float): 포지션 청산 비율 (0.0-1.0)
            position_id (str, optional): 특정 포지션 ID
            additional_exit_info (dict, optional): 추가 종료 정보 (자동 손절매/이익실현 관련)
        """
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
                        'exit_type': additional_exit_info.get('exit_type', 'manual') if additional_exit_info else 'manual',
                        'exit_reason': additional_exit_info.get('exit_reason', '') if additional_exit_info else ''
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
            'amount': actual_quantity,
            'price': price,
            'cost': price * actual_quantity,
            'fee': price * actual_quantity * 0.001,
            'timestamp': order_time.isoformat(),
            'position_id': position_id,
            'additional_info': {
                'order_id': order['id'],
                'test_mode': self.test_mode
            }
        }
        self.portfolio['trade_history'].append(trade_record)
        
        # 데이터베이스에 거래 내역 저장
        self.db.save_trade(trade_record)
        
        # 현재 상태 저장
        self.save_state()
        
        if self.test_mode:
            logger.info(f"[테스트] 매도 주문 실행: 가격={price}, 수량={actual_quantity}, 수익={price * actual_quantity}")
        
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
    
    @simple_error_handler(default_return=None)
    @api_error_handler(retry_count=3, max_delay=20)
    def get_current_price(self, symbol=None):
        """현재 가격 조회"""
        # OrderExecutor 클래스 활용
        return self.order_executor.get_current_price(symbol or self.symbol)
    
    @simple_error_handler(default_return=[])
    def get_open_positions(self, symbol=None):
        """
        현재 열린 포지션 목록 조회
        
        Args:
            symbol (str, optional): 특정 심볼에 대한 포지션만 조회. None이면 모든 포지션 조회
        
        Returns:
            list: 포지션 정보 목록
        """
        # PortfolioManager를 통해 포지션 정보 조회
        try:
            positions = self.portfolio_manager.get_open_positions(symbol)
            
            # 이전 버전과의 호환성을 위해 포트폴리오 참조 업데이트
            self.portfolio['positions'] = positions
            
            return positions
        except Exception as e:
            logger.error(f"포지션 조회 과정에서 예상치 못한 오류: {e}")
            return []
    
    @api_error_handler(retry_count=1, max_delay=5)
    def close_position(self, position_id, symbol=None, side=None, amount=None, reason=None):
        """
        포지션 청산
        
        Args:
            position_id (str): 청산할 포지션 ID
            symbol (str, optional): 거래 심볼, None이면 현재 설정된 심볼 사용
            side (str, optional): 포지션 방향 ('long' 또는 'short'), None이면 포지션 ID로 자동 찾기
            amount (float, optional): 청산할 수량, None이면 전체 포지션 청산
            reason (str, optional): 청산 이유 (로깅용)
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 심볼 설정 (지정되지 않은 경우 현재 심볼 사용)
            target_symbol = symbol or self.symbol
            
            # position_id로 포지션 정보 찾기 - PortfolioManager 사용
            position = None
            positions = self.portfolio_manager.get_open_positions(symbol=target_symbol)
            
            for pos in positions:
                if pos.get('id') == position_id:
                    position = pos
                    break
            
            # 포지션을 찾지 못한 경우
            if not position:
                logger.error(f"포지션 청산 실패: ID {position_id}에 해당하는 포지션을 찾을 수 없음")
                return False
            
            # 포지션 정보 추출
            position_side = side or position.get('side', '').lower()
            position_amount = position.get('amount', 0)
            
            # 청산할 수량 (지정되지 않은 경우 전체 포지션 청산)
            exit_amount = amount if amount is not None else position_amount
            
            # 비율 계산 (로깅용)
            exit_percentage = exit_amount / position_amount if position_amount > 0 else 1.0
            
            # 현재 가격 조회
            current_price = self.get_current_price()
            if not current_price or current_price <= 0:
                logger.error(f"포지션 청산 실패: 현재 가격 조회 실패 ({current_price})")
                return False
            
            # 실행 전 로그
            logger.info(f"포지션 {position_id} 청산 실행: {position_side} 포지션, {exit_amount}/{position_amount} ({exit_percentage:.1%})"
                      f", 청산가: {current_price}, 이유: {reason or '수동 청산'}")
            
            # 추가 종료 정보 설정
            additional_exit_info = {'exit_reason': reason} if reason else {'exit_reason': '수동 청산'}
            
            # 포지션 방향에 따라 적절한 메서드 실행
            result = False
            if position_side == 'long':
                # 롱 포지션은 매도로 청산
                result = self.execute_sell(
                    price=current_price,
                    quantity=exit_amount,
                    additional_exit_info=additional_exit_info,
                    percentage=exit_percentage,
                    position_id=position_id
                )
            elif position_side == 'short':
                # 숏 포지션은 매수로 청산
                result = self.execute_buy(
                    price=current_price,
                    quantity=exit_amount,
                    additional_info=additional_exit_info,
                    close_position=True,
                    position_id=position_id
                )
            else:
                logger.error(f"포지션 청산 실패: 알 수 없는 포지션 방향 '{position_side}'")
                return False
            
            # 결과 처리
            if result:
                logger.info(f"포지션 {position_id} 청산 성공 ({exit_percentage:.1%})")
                
                # 포트폴리오 정보 업데이트 - 포트폴리오 관리자 사용
                self.portfolio_manager.update_portfolio()
                
                # 이전 버전과의 호환성을 위해 포트폴리오 참조 업데이트
                self.portfolio = self.portfolio_manager.portfolio
                
                # 현재 상태 저장
                self.save_state()
                
                return True
            else:
                logger.error(f"포지션 {position_id} 청산 실패")
                return False
                
        except Exception as e:
            logger.error(f"포지션 청산 중 예상치 못한 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
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
