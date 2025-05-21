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
from typing import Dict, Any, List, Optional, Tuple
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
from src.backup_manager import get_backup_manager
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
        
        # 백업 관리자 초기화
        self.backup_manager = get_backup_manager()
        self.backup_manager.start_backup_scheduler()
        
        # 이전 상태 복원
        if restore_state:
            self._restore_state()
        
        logger.info(f"{exchange_id} 거래소의 {symbol} 거래 알고리즘이 초기화되었습니다.")
    
    def _restore_state(self):
        """
        데이터베이스 및 백업에서 이전 상태 복원
        """
        try:
            # 먼저 데이터베이스에서 복원 시도
            self.portfolio_manager.restore_portfolio()
            # 최신 포트폴리오 참조
            self.portfolio = self.portfolio_manager.portfolio
            logger.info("이전 포트폴리오 상태를 데이터베이스에서 복원했습니다.")
        except Exception as e:
            logger.warning(f"데이터베이스에서 상태 복원 실패: {e}")
            
            # 데이터베이스 복원 실패 시 백업에서 복원 시도
            self._restore_from_backup()
    
    def _restore_from_backup(self):
        """
        백업 파일에서 상태 복원 시도
        """
        try:
            # 최신 상태 백업 파일 조회
            latest_backup = self.backup_manager.get_latest_backup(self.backup_manager.BACKUP_TYPE_STATE)
            if not latest_backup:
                logger.warning("사용 가능한 상태 백업이 없습니다.")
                return False
            
            # 백업 파일 복원
            success, restore_data = self.backup_manager.restore_from_backup(latest_backup)
            if not success:
                logger.warning(f"백업 복원 실패: {restore_data.get('error')}")
                return False
            
            # 복원된 데이터에서 상태 추출
            backup_data = restore_data.get('backup_data', {})
            state_data = backup_data.get('state', {})
            positions_data = backup_data.get('positions', {})
            
            # 상태 복원 로직 구현 (다음 단계에서 구현)
            logger.info(f"백업에서 상태 복원 성공: {latest_backup}")
            return True
            
        except Exception as e:
            logger.error(f"백업에서 상태 복원 중 오류: {e}")
            return False
    
    def save_state(self):
        """
        현재 상태를 데이터베이스와 백업 시스템에 저장
        """
        try:
            # 포트폴리오 상태를 데이터베이스에 저장
            self.portfolio_manager.save_portfolio()
            logger.debug("현재 상태가 데이터베이스에 저장되었습니다.")
            
            # 상태 백업 생성
            self._create_state_backup()
            
        except Exception as e:
            logger.error(f"상태 저장 중 오류: {e}")
    
    def _create_state_backup(self):
        """
        현재 상태의 백업 생성
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 백업할 상태 데이터 수집
            backup_data = {
                'state': {
                    'trading_active': self.trading_active,
                    'last_signal': self.last_signal,
                    'auto_sl_tp_enabled': self.auto_sl_tp_enabled,
                    'partial_tp_enabled': self.partial_tp_enabled,
                    'last_update': time.time()
                },
                'positions': self.portfolio_manager.get_open_positions_data()
            }
            
            # 백업 생성
            backup_path = self.backup_manager.create_backup(
                self.backup_manager.BACKUP_TYPE_STATE, 
                backup_data
            )
            
            if backup_path:
                logger.debug(f"상태 백업 생성 완료: {os.path.basename(backup_path)}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"상태 백업 생성 중 오류: {e}")
            return False
    
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
    
    def _create_full_backup(self):
        """
        전체 데이터 백업 생성
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 백업할 전체 데이터 수집
            backup_data = {
                'state': {
                    'trading_active': self.trading_active,
                    'last_signal': self.last_signal,
                    'auto_sl_tp_enabled': self.auto_sl_tp_enabled,
                    'partial_tp_enabled': self.partial_tp_enabled,
                    'last_update': time.time()
                },
                'positions': self.portfolio_manager.get_open_positions_data(),
                'config': self.get_config(),
                'trades': self.portfolio_manager.get_recent_trades(50)  # 최근 50개 거래 기록
            }
            
            # 백업 생성
            backup_path = self.backup_manager.create_backup(
                self.backup_manager.BACKUP_TYPE_FULL, 
                backup_data
            )
            
            if backup_path:
                logger.info(f"전체 백업 생성 완료: {os.path.basename(backup_path)}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"전체 백업 생성 중 오류: {e}")
            return False
    
    def get_config(self):
        """
        현재 설정 정보 반환
        
        Returns:
            Dict[str, Any]: 설정 정보
        """
        return {
            'exchange_id': self.exchange_id,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'test_mode': self.test_mode,
            'risk_management': self.risk_management,
            'strategy': {
                'name': self.strategy.name if hasattr(self.strategy, 'name') else self.strategy.__class__.__name__,
                'type': self.strategy.__class__.__name__,
                'parameters': self.strategy.get_parameters() if hasattr(self.strategy, 'get_parameters') else {}
            }
        }
    
    def backup_config(self):
        """
        현재 설정 정보 백업
        
        Returns:
            bool: 성공 여부
        """
        try:
            config_data = {'config': self.get_config()}
            backup_path = self.backup_manager.create_backup(
                self.backup_manager.BACKUP_TYPE_CONFIG, 
                config_data
            )
            
            if backup_path:
                logger.info(f"설정 백업 생성 완료: {os.path.basename(backup_path)}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"설정 백업 생성 중 오류: {e}")
            return False
    
    def get_backups(self):
        """
        사용 가능한 백업 목록 조회
        
        Returns:
            Dict[str, List[Dict[str, Any]]]: 백업 목록
        """
        return self.backup_manager.list_backups()
    
    def start_trading(self):
        """
        거래 시작
        """
        if self.trading_active:
            logger.warning("거래가 이미 진행 중입니다.")
            return
        
        # 메모리 관리 모니터링 시작
        self.memory_monitor.start_monitoring()
        self.resource_manager.start_cleanup_scheduler()
        
        # 백업 스케줄러 시작
        self.backup_manager.start_backup_scheduler()
        
        # 포트폴리오 업데이트
        self.update_portfolio()
        
        # 자동 손절매/이익실현 활성화 (설정되어 있는 경우)
        if self.auto_sl_tp_enabled:
            self.enable_auto_sl_tp()
        
        self.trading_active = True
        
        # 초기 상태 백업 생성
        self._create_state_backup()
        
        logger.info("자동 거래가 시작되었습니다.")
    
    def stop_trading(self):
        """
        거래 중지
        """
        if not self.trading_active:
            logger.warning("거래가 이미 중지된 상태입니다.")
            return
        
        self.trading_active = False
        
        # 자동 손절매/이익실현 비활성화
        if self.auto_sl_tp_enabled:
            self.disable_auto_sl_tp()
        
        # 메모리 관리 모니터링 종료
        self.memory_monitor.stop_monitoring()
        self.resource_manager.stop_cleanup_scheduler()
        
        # 백업 스케줄러 종료
        self.backup_manager.stop_backup_scheduler()
        
        # 최종 상태 백업 생성
        self._create_full_backup()
        
        # 상태 저장
        self.save_state()
        
        logger.info("거래가 중지되었습니다.")
    
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
