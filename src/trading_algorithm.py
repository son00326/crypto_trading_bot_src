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
import traceback
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import psutil
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
from src.logging_config import get_logger
from src.backup_manager import get_backup_manager
from src.event_manager import get_event_manager, EventType
from src.backup_restore import get_backup_restore_manager
from src.config import (
    BACKUP_FREQUENCY, BACKUP_DIR, DATA_DIR, DEFAULT_EXCHANGE, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME,
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
                 strategy=None, initial_balance=None, test_mode=True, restore_state=True,
                 max_init_retries=3, retry_delay=2, strategy_params=None):
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
            max_init_retries (int): API 초기화 최대 재시도 횟수
            retry_delay (int): 재시도 간 지연 시간(초)
            strategy_params (dict): 전략별 세부 파라미터
        """
        # 로거 초기화
        self.logger = get_logger('trading_algorithm')
        
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.test_mode = test_mode
        self.strategy_params = strategy_params or {}
        
        # 데이터베이스 관리자 초기화
        self.db = DatabaseManager()
        
        # 거래소 API 및 데이터 관련 객체 초기화 (재시도 로직 포함)
        self.exchange_api = self._initialize_exchange_api_with_retry(
            exchange_id, symbol, timeframe, max_retries=max_init_retries, delay=retry_delay
        )
        
        # API 초기화 성공 후 나머지 구성요소 초기화
        self.data_manager = DataManager(exchange_id=exchange_id, symbol=symbol)
        self.data_collector = DataCollector(exchange_id=exchange_id, symbol=symbol, timeframe=timeframe)
        self.data_analyzer = DataAnalyzer(exchange_id=exchange_id, symbol=symbol)
        
        # 테스트 모드 설정
        if test_mode:
            try:
                self.exchange_api.exchange.set_sandbox_mode(True)
                logger.info("테스트 모드로 실행합니다.")
            except Exception as e:
                logger.warning(f"테스트 모드 설정 실패: {str(e)}. 실제 모드로 진행합니다.")
        
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
            symbol=symbol,
            test_mode=test_mode
        )
        
        # 전략 설정
        if strategy is None:
            # 기본 전략: 이동평균 교차 + RSI
            # 전략 파라미터가 있으면 적용
            if 'MovingAverageCrossover' in self.strategy_params:
                mac_params = self.strategy_params['MovingAverageCrossover']
                ma_cross = MovingAverageCrossover(
                    short_period=mac_params.get('short_period', 9),
                    long_period=mac_params.get('long_period', 26),
                    ma_type=mac_params.get('ma_type', 'ema')
                )
            else:
                ma_cross = MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema')
                
            if 'RSIStrategy' in self.strategy_params:
                rsi_params = self.strategy_params['RSIStrategy']
                rsi = RSIStrategy(
                    period=rsi_params.get('period', 14),
                    overbought=rsi_params.get('overbought', 70),
                    oversold=rsi_params.get('oversold', 30)
                )
            else:
                rsi = RSIStrategy(period=14, overbought=70, oversold=30)
                
            self.strategy = CombinedStrategy([ma_cross, rsi])
        else:
            # 이미 전략 객체가 제공된 경우
            self.strategy = strategy
        
        logger.info(f"{self.strategy.name} 전략을 사용합니다.")
        if self.strategy_params:
            logger.info(f"전략 파라미터: {self.strategy_params}")
        
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
        try:
            self.memory_monitor = get_memory_monitor()
            # ResourceManager가 정의되지 않은 경우를 대비
            try:
                from src.resource_manager import get_resource_manager
                self.resource_manager = get_resource_manager()
                self.resource_manager.start_cleanup_scheduler()
            except (ImportError, NameError):
                logger.warning("ResourceManager를 초기화할 수 없습니다. 테스트 모드에서는 무시합니다.")
                self.resource_manager = None
            
            self.memory_monitor.start_monitoring()
        except Exception as e:
            logger.warning(f"메모리 관리 초기화 실패: {str(e)}")
            self.memory_monitor = None
            self.resource_manager = None
        
        # 백업 관리자 초기화
        self.backup_manager = get_backup_manager()
        self.backup_restore_manager = get_backup_restore_manager()
        
        # 이벤트 관리자 초기화
        self.event_manager = get_event_manager()
        
        # 이전 상태 복원
        if restore_state:
            self._restore_state()
        
        logger.info(f"{exchange_id} 거래소의 {symbol} 거래 알고리즘이 초기화되었습니다.")
        
    def _initialize_exchange_api_with_retry(self, exchange_id, symbol, timeframe, max_retries=3, delay=2):
        """
        거래소 API를 초기화하고 연결을 검증합니다. 실패 시 재시도합니다.
        
        Args:
            exchange_id (str): 거래소 ID
            symbol (str): 거래 심볼
            timeframe (str): 타임프레임
            max_retries (int): 최대 재시도 횟수
            delay (int): 재시도 간 지연 시간(초)
            
        Returns:
            ExchangeAPI: 초기화된 거래소 API 인스턴스
            
        Raises:
            APIError: 모든 재시도 후에도 초기화 실패한 경우
        """
        retry_count = 0
        last_exception = None
        
        while retry_count <= max_retries:
            try:
                # 거래소 API 초기화
                exchange_api = ExchangeAPI(exchange_id=exchange_id, symbol=symbol, timeframe=timeframe)
                
                # API 키 유효성 검증 (간단한 API 호출로 확인)
                try:
                    # 서버 시간 조회로 API 연결 테스트 (가장 가벼운 API 호출)
                    server_time = exchange_api.exchange.fetch_time()
                    self.logger.info(f"API 연결 확인: 서버 시간 {datetime.fromtimestamp(server_time/1000)}")  
                    
                    # 추가 검증: 적절한 API 권한이 있는지 확인
                    if not exchange_api.exchange.checkRequiredCredentials():
                        self.logger.warning("API 키가 설정되지 않았거나 불완전합니다. 일부 기능이 제한될 수 있습니다.")
                    
                    return exchange_api
                except Exception as validation_error:
                    self.logger.error(f"API 키 유효성 검증 실패: {validation_error}")
                    raise
                    
            except Exception as e:
                last_exception = e
                retry_count += 1
                self.logger.warning(f"거래소 API 초기화 실패 ({retry_count}/{max_retries}): {str(e)}")
                
                if retry_count <= max_retries:
                    self.logger.info(f"{delay}초 후 재시도 합니다...")
                    time.sleep(delay)
                    # 지수 백오프: 다음 재시도는 더 오래 기다림
                    delay = min(delay * 2, 30)  # 최대 30초까지 증가
        
        # 모든 재시도 실패 시
        error_msg = f"최대 재시도 횟수({max_retries})를 초과했습니다. 거래소 API 초기화 실패."
        self.logger.error(error_msg)
        if last_exception:
            raise APIError(error_msg, original_exception=last_exception)
        else:
            raise APIError(error_msg)
    
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
            self._try_restore_from_backup()
    
    def _try_restore_from_backup(self):
        """
        백업에서 자동 복원 시도
        
        Returns:
            bool: 성공 여부
        """
        try:
            self.logger.info("백업에서 자동 복원 시도 중...")
            
            # 복원 매니저를 사용하여 자동 복원 시도
            success, result = self.backup_restore_manager.auto_restore_from_backup()
            
            if success:
                restored_components = result.get('components_restored', {})
                self.logger.info(f"백업 복원 성공! 복원된 구성요소: {restored_components}")
                
                # 복원 이벤트에 구독
                # SYSTEM_RECOVERY 이벤트 유형이 정의되지 않았을 수 있으므로 일반 이벤트로 대체
                try:
                    self.event_manager.publish(EventType.SYSTEM_RECOVERY, {
                        'timestamp': datetime.now().isoformat(),
                        'success': True,
                        'restored_components': restored_components
                    })
                except Exception as e:
                    self.logger.error(f"복원 성공 이벤트 발행 중 오류: {e}")
                
                return True
            else:
                error = result.get('error', '알 수 없는 오류')
                self.logger.warning(f"백업 복원 실패: {error}")
                
                # 실패 이벤트 발행
                # SYSTEM_RECOVERY 이벤트 유형이 정의되지 않았을 수 있으므로 일반 이벤트로 대체
                try:
                    self.event_manager.publish(EventType.SYSTEM_RECOVERY, {
                        'timestamp': datetime.now().isoformat(),
                        'success': False,
                        'error': error,
                        'backup_file': result.get('backup_file', 'unknown')
                    })
                except Exception as e:
                    self.logger.error(f"복원 실패 이벤트 발행 중 오류: {e}")
                
                return False
        except Exception as e:
            self.logger.error(f"백업 파일 복원 시도 중 예외 발생: {e}")
            self.logger.debug(traceback.format_exc())
            return False
            
    def _restore_from_backup(self, backup_file=None):
        """
        특정 백업 파일에서 상태 복원
        
        Args:
            backup_file (str, optional): 복원할 백업 파일 경로. None인 경우 자동 선택.
            
        Returns:
            bool: 성공 여부
        """
        try:
            self.logger.info(f"백업 파일에서 복원 시도: {backup_file if backup_file else '자동 선택'}")
            
            if backup_file:
                # 특정 백업 파일에서 복원
                success, result = self.backup_restore_manager.restore_from_backup(backup_file)
            else:
                # 자동 선택된 백업에서 복원
                success, result = self.backup_restore_manager.auto_restore_from_backup()
            
            if success:
                restored_components = result.get('components_restored', {})
                self.logger.info(f"백업 파일 복원 성공! 복원된 구성요소: {restored_components}")
                
                # 복원 이벤트 발행
                # SYSTEM_RECOVERY 이벤트 유형이 정의되지 않았을 수 있으므로 일반 이벤트로 대체
                try:
                    self.event_manager.publish(EventType.SYSTEM_RECOVERY, {
                        'timestamp': datetime.now().isoformat(),
                        'success': True,
                        'restored_components': restored_components,
                        'backup_file': result.get('backup_file', 'unknown')
                    })
                except Exception as e:
                    self.logger.error(f"복원 성공 이벤트 발행 중 오류: {e}")
                
                return True
            else:
                error = result.get('error', '알 수 없는 오류')
                self.logger.warning(f"백업 파일 복원 실패: {error}")
                
                # 실패 이벤트 발행
                # SYSTEM_RECOVERY 이벤트 유형이 정의되지 않았을 수 있으므로 일반 이벤트로 대체
                try:
                    self.event_manager.publish(EventType.SYSTEM_RECOVERY, {
                        'timestamp': datetime.now().isoformat(),
                        'success': False,
                        'error': error,
                        'backup_file': result.get('backup_file', 'unknown')
                    })
                except Exception as e:
                    self.logger.error(f"복원 실패 이벤트 발행 중 오류: {e}")
                
                return False
        except Exception as e:
            self.logger.error(f"백업 파일 복원 시도 중 예외 발생: {e}")
            self.logger.debug(traceback.format_exc())
            return False
    
    def save_state(self):
        """
        현재 상태를 데이터베이스와 백업 시스템에 저장
        """
        try:
            # 포트폴리오 상태를 데이터베이스에 저장
            self.portfolio_manager.save_portfolio()
            self.logger.debug("현재 상태가 데이터베이스에 저장되었습니다.")
            
            # 백업 생성
            try:
                backup_data = {
                    'portfolio': self.portfolio,
                    'trading_active': self.trading_active,
                    'last_signal': self.last_signal,
                    'auto_sl_tp_enabled': self.auto_sl_tp_enabled,
                    'partial_tp_enabled': self.partial_tp_enabled,
                    'risk_management': self.risk_management,
                    'timestamp': datetime.now().isoformat()
                }
                
                backup_path = self.backup_manager.create_backup(backup_data)
                self.logger.info(f"백업 파일 생성 완료: {backup_path}")
                
                # 백업 이벤트 발행
                try:
                    self.event_manager.publish(EventType.BACKUP_CREATED, {
                        'backup_file': backup_path,
                        'result': 'success',
                        'timestamp': datetime.now().isoformat()
                    })
                except Exception as e:
                    self.logger.error(f"백업 이벤트 발행 중 오류: {e}")
                
                return True
            except Exception as e:
                self.logger.error(f"백업 생성 중 오류 발생: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"상태 저장 중 오류 발생: {e}")
            self.logger.debug(traceback.format_exc())
            return False
    
    def get_current_price(self, symbol=None, max_retries=3):
        """
        현재 가격 조회 (API 오류 발생 시 재시도 로직 추가 및 기본값 처리 강화)
        
        Args:
            symbol (str, optional): 거래 심볼. None이면 기본 심볼 사용
            max_retries (int): 최대 재시도 횟수
            
        Returns:
            float: 현재 가격, 실패 시 None 대신 마지막 유효한 가격 또는 추정값 반환
        """
        symbol = symbol or self.symbol
        retry_count = 0
        last_error = None
        last_valid_price = None
        price_cache_key = f"{symbol}_last_price"
        
        # 경고 로그 수준 설정 (재시도 횟수에 따라 조정)
        log_level = 'warning' if retry_count > 1 else 'error'
        
        # 재시도 루프
        while retry_count <= max_retries:
            try:
                # 현재 가격 조회
                ticker = self.exchange_api.get_ticker(symbol)
                
                if not ticker or 'last' not in ticker:
                    retry_count += 1
                    if log_level == 'warning':
                        self.logger.warning(f"현재 가격 조회 결과 불완전: {ticker}, 재시도 {retry_count}/{max_retries}")
                    else:
                        self.logger.error(f"현재 가격 조회 결과 불완전: {ticker}, 재시도 {retry_count}/{max_retries}")
                    time.sleep(1)  # 재시도 전 짠시 대기
                    continue
                
                current_price = float(ticker['last'])
                
                # 가격 유효성 검사
                if current_price <= 0:
                    self.logger.warning(f"비정상적인 가격 받음: {current_price}, 재시도 {retry_count}/{max_retries}")
                    retry_count += 1
                    time.sleep(1)  # 재시도 전 짠시 대기
                    continue
                
                # 캐시 업데이트
                if not hasattr(self, '_price_cache'):
                    self._price_cache = {}
                self._price_cache[price_cache_key] = {
                    'price': current_price,
                    'timestamp': time.time()
                }
                
                return current_price
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count <= max_retries:
                    self.logger.warning(f"현재 가격 조회 실패 ({retry_count}/{max_retries}): {e}")
                    time.sleep(retry_count)  # 지수적 대기 시간 증가
                else:
                    self.logger.error(f"현재 가격 조회 최대 재시도 횟수 초과: {e}")
        
        # 모든 재시도 실패 시
        self.logger.error(f"현재 가격 조회 최종 실패: {last_error}")
        
        # 최근 캐시된 가격 확인 (1분 이내)
        if hasattr(self, '_price_cache') and price_cache_key in self._price_cache:
            cache_data = self._price_cache[price_cache_key]
            if time.time() - cache_data['timestamp'] < 60:  # 1분 이내 캐시
                self.logger.warning(f"캐시된 가격 사용: {cache_data['price']} ({int(time.time() - cache_data['timestamp'])}초 전)")
                return cache_data['price']
        
        # 데이터베이스에서 최근 가격 가져오기 시도
        try:
            recent_price = self.db.get_latest_price(symbol)
            if recent_price and recent_price > 0:
                self.logger.warning(f"DB에서 최근 가격 사용: {recent_price}")
                return recent_price
        except Exception as db_error:
            self.logger.error(f"DB에서 최근 가격 조회 실패: {db_error}")
        
        # OHLCV 데이터에서 수집
        try:
            ohlcv_data = self.exchange_api.get_ohlcv(symbol, limit=1)
            if not ohlcv_data.empty:
                last_close = float(ohlcv_data.iloc[-1]['close'])
                self.logger.warning(f"OHLCV에서 마지막 종가 사용: {last_close}")
                return last_close
        except Exception as ohlcv_error:
            self.logger.error(f"OHLCV에서 가격 조회 실패: {ohlcv_error}")
        
        # 마지막 수단: 최소한 마지막으로 알고 있는 가격 반환
        self.logger.critical(f"현재 가격 조회 모든 방법 실패: {symbol}")
        return None
    
    def get_portfolio_summary(self):
        """
        포트폴리오 요약 정보 반환
        """
        try:
            # 현재 가격 조회
            try:
                current_price = self.get_current_price(self.symbol)
            except Exception as e:
                self.logger.warning(f"현재 가격 조회 실패: {e}")
                current_price = 0
            
            # 포트폴리오 데이터 가져오기
            portfolio = self.portfolio_manager.portfolio
            
            # 기본 통화 및 견적 통화 정보
            base_currency = portfolio.get('base_currency', '')
            quote_currency = portfolio.get('quote_currency', '')
            base_balance = portfolio.get('base_balance', 0)
            quote_balance = portfolio.get('quote_balance', 0)
            
            # 총 가치 계산
            total_base_value = base_balance + (quote_balance / current_price if current_price > 0 else 0)
            total_quote_value = (base_balance * current_price) + quote_balance if current_price > 0 else quote_balance
            
            # 포지션 정보
            open_positions = portfolio.get('open_positions', [])
            closed_positions = portfolio.get('closed_positions', [])
            
            # 수익 계산
            total_profit = sum([p.get('realized_profit', 0) for p in closed_positions])
            initial_investment = portfolio.get('initial_investment', 1) # 0으로 나누는 것 방지
            total_profit_pct = (total_profit / initial_investment) * 100 if initial_investment > 0 else 0
            
            # 미실현 수익 계산
            unrealized_profit = sum([p.get('unrealized_profit', 0) for p in open_positions])
            unrealized_profit_pct = (unrealized_profit / initial_investment) * 100 if initial_investment > 0 else 0
            
            # 거래 통계
            trade_history = portfolio.get('trade_history', [])
            total_trades = len(trade_history)
            buy_trades = len([t for t in trade_history if t.get('type') == 'buy'])
            sell_trades = len([t for t in trade_history if t.get('type') == 'sell'])
            
            return {
                'base_currency': base_currency,
                'quote_currency': quote_currency,
                'base_balance': base_balance,
                'quote_balance': quote_balance,
                'current_price': current_price,
                'total_base_value': total_base_value,
                'total_quote_value': total_quote_value,
                'open_positions': len(open_positions),
                'closed_positions': len(closed_positions),
                'total_profit': total_profit,
                'total_profit_pct': total_profit_pct,
                'unrealized_profit': unrealized_profit,
                'unrealized_profit_pct': unrealized_profit_pct,
                'total_trades': total_trades,
                'buy_trades': buy_trades,
                'sell_trades': sell_trades,
                'strategy': self.strategy.name if hasattr(self.strategy, 'name') else 'Unknown',
                'test_mode': self.test_mode
            }
        
        except Exception as e:
            self.logger.error(f"포트폴리오 요약 정보 생성 중 오류 발생: {e}")
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
