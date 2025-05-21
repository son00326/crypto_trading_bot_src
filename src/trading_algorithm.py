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
from src.memory_monitor import get_memory_monitor
from src.resource_manager import get_resource_manager
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
        
        # 메모리 관리 초기화
        self.memory_monitor = get_memory_monitor()
        self.resource_manager = get_resource_manager()
        self.memory_monitor.start_monitoring()
        self.resource_manager.start_cleanup_scheduler()
        
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
    
    def get_memory_usage(self):
        """
        현재 메모리 사용량 조회
        
        Returns:
            Dict: 메모리 사용량 정보
        """
        # 메모리 모니터에서 상세 정보 가져오기
        memory_summary = self.memory_monitor.get_memory_usage_summary()
        
        # 자원 관리자에서 캐시 정보 가져오기
        resource_stats = self.resource_manager.get_resource_stats()
        
        result = {
            'memory': memory_summary,
            'resources': {
                'dataframe_cache_count': resource_stats['dataframe_cache']['count'],
                'temp_files_count': resource_stats['temp_files']['count']
            }
        }
        
        return result
    
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
