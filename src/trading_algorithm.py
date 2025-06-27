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
                 max_init_retries=3, retry_delay=2, strategy_params=None, market_type='spot', leverage=1):
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
            market_type (str): 시장 타입 ('spot' 또는 'futures')
            leverage (int): 레버리지 배수 (선물거래에서만 사용)
        """
        # 로거 초기화
        self.logger = get_logger('trading_algorithm')
        
        # 기본 속성 설정
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.test_mode = test_mode
        self.strategy_params = strategy_params or {}
        self.market_type = market_type  # market_type 속성 추가
        self.leverage = leverage  # leverage 속성 추가
        
        # 데이터베이스 관리자 초기화
        self.db = DatabaseManager()
        
        # 거래소 API 및 데이터 관련 객체 초기화 (재시도 로직 포함)
        self.exchange_api = self._initialize_exchange_api_with_retry(
            exchange_id, symbol, timeframe, market_type=self.market_type, leverage=self.leverage, max_retries=max_init_retries, delay=retry_delay
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
            # 전략 이름을 기반으로 전략 객체 생성
            if isinstance(strategy, str):
                strategy_name = strategy
                # 전략 이름에 따라 해당 파라미터를 적용한 전략 객체 생성
                if strategy_name == 'MovingAverageCrossover':
                    params = self.strategy_params.get('MovingAverageCrossover', {})
                    strategy = MovingAverageCrossover(
                        short_period=params.get('short_period', 9),
                        long_period=params.get('long_period', 26),
                        ma_type=params.get('ma_type', 'ema')
                    )
                    
                elif strategy_name == 'RSIStrategy':
                    params = self.strategy_params.get('RSIStrategy', {})
                    strategy = RSIStrategy(
                        period=params.get('period', 14),
                        overbought=params.get('overbought', 70),
                        oversold=params.get('oversold', 30)
                    )
                    
                elif strategy_name == 'MACDStrategy':
                    params = self.strategy_params.get('MACDStrategy', {})
                    strategy = MACDStrategy(
                        fast_period=params.get('fast_period', 12),
                        slow_period=params.get('slow_period', 26),
                        signal_period=params.get('signal_period', 9)
                    )
                    
                elif strategy_name == 'BollingerBandsStrategy':
                    params = self.strategy_params.get('BollingerBandsStrategy', {})
                    strategy = BollingerBandsStrategy(
                        period=params.get('period', 20),
                        std_dev=params.get('std_dev', 2.0)
                    )
                    
                elif strategy_name == 'CombinedStrategy':
                    # 복합 전략은 기본적으로 MovingAverageCrossover와 RSI를 포함
                    strategies = []
                    
                    # MA 전략 추가
                    if self.strategy_params.get('MovingAverageCrossover'):
                        mac_params = self.strategy_params['MovingAverageCrossover']
                        strategies.append(MovingAverageCrossover(
                            short_period=mac_params.get('short_period', 9),
                            long_period=mac_params.get('long_period', 26),
                            ma_type=mac_params.get('ma_type', 'ema')
                        ))
                    else:
                        strategies.append(MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema'))
                        
                    # RSI 전략 추가
                    if self.strategy_params.get('RSIStrategy'):
                        rsi_params = self.strategy_params['RSIStrategy']
                        strategies.append(RSIStrategy(
                            period=rsi_params.get('period', 14),
                            overbought=rsi_params.get('overbought', 70),
                            oversold=rsi_params.get('oversold', 30)
                        ))
                    else:
                        strategies.append(RSIStrategy(period=14, overbought=70, oversold=30))
                        
                    strategy = CombinedStrategy(strategies)
                else:
                    # 나머지 전략은 기본 파라미터로 처리
                    self.logger.warning(f"알 수 없는 전략 이름: {strategy_name}, 기본 파라미터로 초기화합니다.")
                    strategy = MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema')
                    
            # 전략 객체 적용
            self.strategy = strategy
        
        logger.info(f"{self.strategy.name} 전략을 사용합니다.")
        if self.strategy_params:
            logger.info(f"전략 파라미터: {self.strategy_params}")
        
        # 이전 버전과의 호환성을 위해 포트폴리오 객체 유지 (향후 리팩토링 시 제거 예정)
        self.portfolio = self.portfolio_manager.portfolio
        
        # 거래 상태 (기본값)
        self.trading_active = False
        self.last_signal = 0  # 0: 중립, 1: 매수, -1: 매도
        
        # 현재 거래 정보 (진입가, 목표가, 손절가 등)
        self.current_trade_info = {}
        
        # 자동 포지션 관리자 초기화
        self.auto_position_manager = AutoPositionManager(self)
        self.auto_sl_tp_enabled = False  # 자동 손절매/이익실현 활성화 여부
        self.partial_tp_enabled = False  # 부분 이익실현 활성화 여부
        
        # 위험 관리 설정
        self.risk_management = RISK_MANAGEMENT.copy()
        
        # strategy_params에서 위험 관리 설정 업데이트
        if self.strategy_params:
            if 'stop_loss_pct' in self.strategy_params:
                self.risk_management['stop_loss_percent'] = self.strategy_params['stop_loss_pct']
            if 'take_profit_pct' in self.strategy_params:
                self.risk_management['take_profit_percent'] = self.strategy_params['take_profit_pct']
            if 'max_position_size' in self.strategy_params:
                self.risk_management['max_position_size'] = self.strategy_params['max_position_size']
            
            logger.info(f"위험 관리 설정 업데이트: stop_loss={self.risk_management['stop_loss_percent']}, "
                       f"take_profit={self.risk_management['take_profit_percent']}, "
                       f"max_position_size={self.risk_management['max_position_size']}")
        
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
        
        # 초기 포트폴리오 상태 업데이트 (거래소에서 잔액 가져오기)
        if not self.test_mode:
            try:
                self.portfolio_manager.update_portfolio()
                logger.info("초기 포트폴리오 상태 업데이트 완료")
            except Exception as e:
                logger.error(f"초기 포트폴리오 업데이트 실패: {e}")
        
        logger.info(f"{exchange_id} 거래소의 {symbol} 거래 알고리즘이 초기화되었습니다.")
        
    def _initialize_exchange_api_with_retry(self, exchange_id, symbol, timeframe, market_type='spot', leverage=1, max_retries=3, delay=2):
        """
        거래소 API를 초기화하고 연결을 검증합니다. 실패 시 재시도합니다.
        
        Args:
            exchange_id (str): 거래소 ID
            symbol (str): 거래 심볼
            timeframe (str): 타임프레임
            market_type (str): 시장 타입 ('spot' 또는 'futures')
            leverage (int): 레버리지 배수 (선물거래에서만 사용)
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
                exchange_api = ExchangeAPI(
                    exchange_id=exchange_id, 
                    symbol=symbol, 
                    timeframe=timeframe,
                    market_type=market_type,
                    leverage=leverage
                )
                
                # API 키 유효성 검증 (간단한 API 호출로 확인)
                try:
                    # 서버 시간 조회로 API 연결 테스트 (가장 가벼운 API 호출)
                    server_time = exchange_api.exchange.fetch_time()
                    self.logger.info(f"API 연결 확인: 서버 시간 {datetime.fromtimestamp(server_time/1000)}")  
                    
                    # 추가 검증: 적절한 API 권한이 있는지 확인
                    if not exchange_api.exchange.checkRequiredCredentials():
                        self.logger.warning("API 키가 설정되지 않았거나 불완전합니다. 일부 기능이 제한될 수 있습니다.")
                    
                    # API 권한 상세 확인
                    permissions = exchange_api.verify_api_permissions()
                    self.logger.info(f"API 권한 확인 결과: {permissions['message']}")
                    
                    if not permissions['can_trade']:
                        self.logger.error("거래 권한이 없습니다! API 키 설정을 확인해주세요.")
                        if self.test_mode:
                            self.logger.info("테스트 모드이므로 계속 진행합니다.")
                        else:
                            raise APIError("API 키에 거래 권한이 없습니다. 바이낸스에서 API 권한을 확인해주세요.")
                    
                    return exchange_api
                except Exception as validation_error:
                    self.logger.error(f"API 키 유효성 검증 실패: {validation_error}")
                    raise
                    
            except Exception as e:
                last_exception = e
                retry_count += 1
                
                if retry_count <= max_retries:
                    self.logger.warning(f"거래소 API 초기화 실패 ({retry_count}/{max_retries}): {e}")
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
            
    def start_trading_thread(self, interval=60):
        """
        별도 스레드에서 거래 사이클을 주기적으로 실행
        
        Args:
            interval (int): 거래 사이클 실행 간격 (초)
            
        Returns:
            threading.Thread: 거래 스레드 객체
        """
        self.logger.info(f"거래 스레드 시작 요청 (간격: {interval}초)")
        self.logger.info(f"거래 활성화 상태: {self.trading_active}")
        
        # 거래 스레드 상태 설정
        self.trading_active = True
        self.trading_interval = interval
        
        self.logger.info(f"거래 활성화 상태 변경됨: {self.trading_active}")
        
        # 거래 루프를 실행할 스레드 생성
        def trading_loop():
            self.logger.info("=== 거래 루프 시작 ===")
            self.logger.info(f"거래 심볼: {self.symbol}")
            self.logger.info(f"타임프레임: {self.timeframe}")
            self.logger.info(f"전략: {self.strategy.__class__.__name__}")
            self.logger.info(f"거래 간격: {interval}초")
            self.logger.info(f"테스트 모드: {self.test_mode}")
            consecutive_errors = 0
            max_consecutive_errors = 5  # 연속 오류 최대 허용 횟수
            
            while self.trading_active:
                try:
                    self.logger.info(f"[거래 사이클 시작] trading_active={self.trading_active}")
                    
                    # 거래 사이클 실행
                    self.execute_trading_cycle()
                    
                    # 성공 시 연속 오류 카운트 초기화
                    consecutive_errors = 0
                    
                    # 포트폴리오 상태 저장
                    try:
                        self.save_state()
                    except Exception as save_error:
                        self.logger.error(f"상태 저장 중 오류 발생: {save_error}")
                    
                    # 다음 사이클까지 대기
                    time.sleep(interval)
                    
                except Exception as e:
                    consecutive_errors += 1
                    self.logger.error(f"거래 사이클 실행 중 오류 발생 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                    self.logger.debug(traceback.format_exc())
                    
                    # 연속 오류가 최대 허용치를 넘으면 일시 중지
                    if consecutive_errors >= max_consecutive_errors:
                        self.logger.critical(f"연속 오류가 {max_consecutive_errors}회를 초과하여 거래를 일시 중지합니다.")
                        
                        # 경고 이벤트 발행
                        try:
                            self.event_manager.publish(EventType.TRADING_ERROR, {
                                'timestamp': datetime.now().isoformat(),
                                'error': str(e),
                                'consecutive_errors': consecutive_errors,
                                'action': 'pause_trading'
                            })
                        except Exception as event_error:
                            self.logger.error(f"오류 이벤트 발행 중 추가 오류: {event_error}")
                        
                        # 복구 대기 시간
                        recovery_wait = min(300, 30 * consecutive_errors)  # 최대 5분까지 대기
                        self.logger.warning(f"{recovery_wait}초 후 거래를 재개합니다.")
                        time.sleep(recovery_wait)
                    else:
                        # 일반 오류는 짧은 시간 대기 후 재시도
                        time.sleep(5)
        
        # 스레드 생성 및 시작
        trading_thread = threading.Thread(target=trading_loop, daemon=True)
        trading_thread.start()
        
        return trading_thread
        
    def execute_trading_cycle(self):
        """
        한 번의 거래 사이클을 실행합니다.
        1. 시장 데이터 가져오기
        2. 전략에 데이터 전달하여 거래 신호 생성
        3. 리스크 평가 및 관리
        4. 신호가 있다면 주문 실행
        """
        self.logger.info(f"=== 거래 사이클 실행 시작 ===")
        self.logger.info(f"심볼: {self.symbol}, 전략: {self.strategy.__class__.__name__}")
        self.logger.info(f"테스트 모드: {self.test_mode}, 거래 활성화: {self.trading_active}")
        cycle_start_time = datetime.now()
        
        try:
            # 1. 현재 포트폴리오 상태 확인
            self.logger.info("1단계: 포트폴리오 상태 확인 중...")
            portfolio_status = self.portfolio_manager.get_portfolio_status()
            self.logger.info(f"포트폴리오 상태: 잔액={portfolio_status.get('quote_balance', 0):.4f}, 포지션 수={len(portfolio_status.get('open_positions', []))}")
            
            # 2. 시장 데이터 가져오기 (OHLCV 데이터)
            self.logger.info("2단계: 시장 데이터 수집 중...")
            market_data = self.data_collector.fetch_recent_data(
                limit=self.strategy.required_data_points
            )
            
            if market_data is None or len(market_data) < self.strategy.required_data_points:
                self.logger.warning(f"충분한 시장 데이터를 가져올 수 없습니다. 가져온 데이터: {len(market_data) if market_data is not None else 0}/{self.strategy.required_data_points}")
                return
            
            self.logger.info(f"시장 데이터 수집 완료: {len(market_data)}개 캔들")
            
            # 시장 데이터 상세 로깅
            if market_data is not None and len(market_data) > 0:
                latest_candle = market_data.iloc[-1]
                self.logger.info(f"최신 캔들 정보:")
                self.logger.info(f"  - 시간: {latest_candle.name}")
                self.logger.info(f"  - 시가: {latest_candle['open']:.2f}")
                self.logger.info(f"  - 고가: {latest_candle['high']:.2f}")
                self.logger.info(f"  - 저가: {latest_candle['low']:.2f}")
                self.logger.info(f"  - 종가: {latest_candle['close']:.2f}")
                self.logger.info(f"  - 거래량: {latest_candle['volume']:.2f}")
                
                # 가격 변동성 계산
                price_change = latest_candle['close'] - latest_candle['open']
                price_change_pct = (price_change / latest_candle['open']) * 100
                self.logger.info(f"  - 가격 변동: {price_change:.2f} ({price_change_pct:+.2f}%)")
                
                # 최근 5개 캔들의 추세
                if len(market_data) >= 5:
                    recent_closes = market_data['close'].tail(5)
                    trend = "상승" if recent_closes.iloc[-1] > recent_closes.iloc[0] else "하락"
                    self.logger.info(f"  - 최근 5개 캔들 추세: {trend}")
            
            # 3. 현재 가격 가져오기
            self.logger.info("3단계: 현재 가격 조회 중...")
            current_price = self.get_current_price(self.symbol)
            if current_price is None:
                self.logger.warning("현재 가격을 가져올 수 없습니다. 거래 사이클을 건너뜁니다.")
                return
            
            self.logger.info(f"현재 가격: {current_price}")
            
            # 4. 전략에 데이터 전달하여 거래 신호 생성
            self.logger.info(f"4단계: 거래 신호 생성 중... (전략: {self.strategy.__class__.__name__})")
            signal = self.strategy.generate_signal(
                market_data=market_data, 
                current_price=current_price,
                portfolio=portfolio_status
            )
            
            # 5. 신호 로깅
            if signal:
                self.logger.info(f"★ 거래 신호 발생! ★")
                self.logger.info(f"  - 방향: {signal.direction}")
                self.logger.info(f"  - 신뢰도: {signal.confidence:.2f}")
                self.logger.info(f"  - 강도: {signal.strength}")
                self.logger.info(f"  - 전략: {signal.strategy}")
            else:
                self.logger.info("거래 신호 없음 (HOLD)")
                return
            
            # 6. 리스크 평가 및 관리
            self.logger.info("5단계: 리스크 평가 중...")
            risk_assessment = self.risk_manager.assess_risk(
                signal=signal,
                portfolio_status=portfolio_status,
                current_price=current_price
            )
            
            if not risk_assessment['should_execute']:
                self.logger.warning(f"리스크 평가 결과 거래 금지: {risk_assessment['reason']}")
                return
            
            self.logger.info(f"리스크 평가 통과: 포지션 크기={risk_assessment['position_size']}")
            
            # 7. 신호에 따른 주문 실행
            position_size = risk_assessment['position_size']
            if signal.direction == 'buy':
                self.logger.info(f"6단계: 매수 주문 실행 중...")
                self.logger.info(f"  - 금액: {position_size}")
                self.logger.info(f"  - 가격: {current_price}")
                order_result = self.order_executor.execute_buy(
                    symbol=self.symbol,
                    amount=position_size,
                    price=current_price,
                    signal=signal
                )
            elif signal.direction == 'sell':
                self.logger.info(f"6단계: 매도 주문 실행 중...")
                self.logger.info(f"  - 금액: {position_size}")
                self.logger.info(f"  - 가격: {current_price}")
                order_result = self.order_executor.execute_sell(
                    symbol=self.symbol,
                    amount=position_size,
                    price=current_price,
                    signal=signal
                )
            else:
                self.logger.warning(f"알 수 없는 신호 디렉션: {signal.direction}")
                return
            
            # 8. 주문 결과 처리
            if order_result and order_result.get('success'):
                self.logger.info(f"✅ 주문 성공!")
                self.logger.info(f"  - 방향: {signal.direction}")
                self.logger.info(f"  - 주문 ID: {order_result.get('order_id')}")
                self.logger.info(f"  - 금액: {position_size}")
                
                # 거래 정보 저장 (매수 시)
                if signal.direction == 'buy':
                    self.current_trade_info = {
                        'entry_price': current_price,
                        'entry_time': datetime.now().isoformat(),
                        'position_size': position_size,
                        'order_id': order_result.get('order_id'),
                        'take_profit': risk_assessment.get('take_profit'),
                        'stop_loss': risk_assessment.get('stop_loss'),
                        'signal': {
                            'direction': signal.direction,
                            'strength': signal.strength,
                            'strategy': signal.strategy
                        }
                    }
                    self.logger.info(f"거래 정보 저장: {self.current_trade_info}")
                    
                    # 선물 거래인 경우 자동으로 손절/익절 주문 설정
                    if self.market_type.lower() == 'futures':
                        stop_loss_price = risk_assessment.get('stop_loss')
                        take_profit_price = risk_assessment.get('take_profit')
                        
                        if stop_loss_price or take_profit_price:
                            self.logger.info("자동 손절/익절 주문 설정 시작...")
                            try:
                                from utils.api import set_stop_loss_take_profit
                                
                                # API 키 가져오기
                                api_key = os.getenv('BINANCE_API_KEY')
                                api_secret = os.getenv('BINANCE_API_SECRET')
                                
                                if api_key and api_secret:
                                    sl_tp_result = set_stop_loss_take_profit(
                                        api_key=api_key,
                                        api_secret=api_secret,
                                        symbol=self.symbol,
                                        stop_loss=stop_loss_price,
                                        take_profit=take_profit_price,
                                        position_side='LONG'  # 매수 포지션의 SL/TP는 매도
                                    )
                                    
                                    if sl_tp_result.get('success'):
                                        self.logger.info(f"✅ 자동 손절/익절 주문 설정 성공!")
                                        self.logger.info(f"  - 손절가: {stop_loss_price}")
                                        self.logger.info(f"  - 익절가: {take_profit_price}")
                                        self.logger.info(f"  - 메시지: {sl_tp_result.get('message')}")
                                        
                                        # 주문 ID 저장
                                        if 'orders' in sl_tp_result:
                                            self.current_trade_info['sl_tp_orders'] = sl_tp_result.get('orders', [])
                                            
                                            # DB에 SL/TP 주문 정보 저장
                                            try:
                                                # 현재 포지션 ID 가져오기
                                                active_positions = self.db_manager.get_open_positions(self.symbol)
                                                if active_positions:
                                                    position_id = active_positions[-1]['id']  # 가장 최근 포지션
                                                    
                                                    # SL/TP 주문 정보 DB에 저장
                                                    for order in sl_tp_result.get('orders', []):
                                                        order_info = {
                                                            'order_id': order.get('order_id', ''),
                                                            'symbol': self.symbol,
                                                            'order_type': order.get('type', ''),
                                                            'trigger_price': order.get('price', 0),
                                                            'amount': position_size,
                                                            'side': 'sell',  # 매수 포지션의 SL/TP는 매도
                                                            'raw_data': order
                                                        }
                                                        self.db_manager.save_stop_loss_order(position_id, order_info)
                                                        
                                                    self.logger.info("✅ SL/TP 주문 정보가 DB에 저장되었습니다.")
                                            except Exception as db_error:
                                                self.logger.error(f"SL/TP 주문 DB 저장 중 오류: {str(db_error)}")
                                    else:
                                        self.logger.warning(f"자동 손절/익절 주문 설정 실패: {sl_tp_result.get('message')}")
                                else:
                                    self.logger.warning("API 키가 설정되지 않아 자동 손절/익절 주문을 설정할 수 없습니다.")
                                    
                            except Exception as e:
                                self.logger.error(f"자동 손절/익절 주문 설정 중 오류: {str(e)}")
                                # 손절/익절 설정 실패는 거래 자체를 실패시키지 않음
                                
                elif signal.direction == 'sell':
                    # 매도 시 거래 정보 초기화
                    if self.current_trade_info:
                        self.logger.info(f"포지션 청산 - 진입가: {self.current_trade_info.get('entry_price')}, 청산가: {current_price}")
                        self.current_trade_info = {}
                
                # 이벤트 발행
                self.event_manager.publish(EventType.ORDER_EXECUTED, {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': self.symbol,
                    'direction': signal.direction,
                    'price': current_price,
                    'amount': position_size,
                    'order_id': order_result.get('order_id')
                })
            else:
                error_msg = order_result.get('error', '알 수 없는 오류') if order_result else '주문 처리 결과가 없습니다'
                self.logger.error(f"주문 실패: {signal.direction}, 오류: {error_msg}")
            
            # 거래 사이클 완료 시간 로깅
            execution_time = (datetime.now() - cycle_start_time).total_seconds()
            self.logger.info(f"거래 사이클 완료 - 실행 시간: {execution_time:.2f}초")
            
        except Exception as e:
            self.logger.error(f"거래 사이클 실행 중 예외 발생: {e}")
            self.logger.debug(traceback.format_exc())
            
            # 심각한 오류의 경우 이벤트 발행
            try:
                self.event_manager.publish(EventType.TRADING_ERROR, {
                    'timestamp': datetime.now().isoformat(),
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
            except Exception as event_error:
                self.logger.error(f"오류 이벤트 발행 중 추가 오류: {event_error}")

    def get_current_price(self, symbol=None):
        """
        지정된 심볼의 현재 가격을 가져옵니다.
        
        Args:
            symbol (str): 가격을 조회할 심볼 (None일 경우 기본 심볼 사용)
            
        Returns:
            float: 현재 가격, 실패 시 None
        """
        try:
            if symbol is None:
                symbol = self.symbol
            
            # exchange_api를 통해 현재 가격 조회
            ticker = self.exchange_api.exchange.fetch_ticker(symbol)
            current_price = ticker.get('last', ticker.get('close'))
            
            if current_price is None:
                self.logger.error(f"현재 가격을 가져올 수 없습니다: {symbol}")
                return None
                
            return float(current_price)
            
        except Exception as e:
            self.logger.error(f"현재 가격 조회 중 오류 발생: {e}")
            return None
    
    def get_open_positions(self, symbol=None):
        """
        현재 오픈된 포지션 목록을 가져옵니다.
        
        Args:
            symbol (str): 포지션을 조회할 심볼 (None일 경우 모든 포지션)
            
        Returns:
            list: 포지션 목록
        """
        try:
            if symbol is None:
                symbol = self.symbol
                
            # exchange_api를 통해 포지션 조회
            positions = self.exchange_api.get_positions(symbol)
            
            # 열린 포지션만 필터링
            open_positions = []
            for pos in positions:
                if pos.get('contracts', 0) != 0 or pos.get('size', 0) != 0:
                    open_positions.append(pos)
                    
            return open_positions
            
        except Exception as e:
            self.logger.error(f"포지션 조회 중 오류 발생: {e}")
            return []
    
    def close_position(self, symbol=None, position_id=None, size=None):
        """
        특정 포지션을 청산합니다.
        
        Args:
            symbol (str): 청산할 포지션의 심볼
            position_id (str): 청산할 포지션 ID (선택사항)
            size (float): 청산할 수량 (None일 경우 전체 청산)
            
        Returns:
            dict: 주문 결과
        """
        try:
            if symbol is None:
                symbol = self.symbol
                
            # 현재 포지션 조회
            positions = self.get_open_positions(symbol)
            if not positions:
                self.logger.warning(f"청산할 포지션이 없습니다: {symbol}")
                return {'success': False, 'error': 'No open positions'}
                
            # 첫 번째 포지션 선택 (position_id가 지정되지 않은 경우)
            position = positions[0]
            if position_id:
                # position_id가 지정된 경우 해당 포지션 찾기
                for pos in positions:
                    if pos.get('id') == position_id:
                        position = pos
                        break
                        
            # 포지션 사이드 확인
            side = position.get('side', '').lower()
            position_size = abs(position.get('contracts', 0) or position.get('size', 0))
            
            if position_size == 0:
                self.logger.warning(f"포지션 크기가 0입니다: {symbol}")
                return {'success': False, 'error': 'Position size is 0'}
                
            # 청산할 수량 결정
            close_size = size if size else position_size
            close_size = min(close_size, position_size)  # 포지션 크기를 초과하지 않도록
            
            # 반대 방향 주문으로 포지션 청산
            if side == 'long':
                # 롱 포지션 청산 = 매도
                order_result = self.order_executor.execute_sell(
                    symbol=symbol,
                    amount=close_size,
                    price=None,  # 시장가 주문
                    signal=None
                )
            elif side == 'short':
                # 숏 포지션 청산 = 매수
                order_result = self.order_executor.execute_buy(
                    symbol=symbol,
                    amount=close_size,
                    price=None,  # 시장가 주문
                    signal=None
                )
            else:
                self.logger.error(f"알 수 없는 포지션 사이드: {side}")
                return {'success': False, 'error': f'Unknown position side: {side}'}
                
            return order_result
            
        except Exception as e:
            self.logger.error(f"포지션 청산 중 오류 발생: {e}")
            return {'success': False, 'error': str(e)}
    
    # 테스트 코드
    if __name__ == "__main__":
        # 거래 알고리즘 초기화 (테스트 모드)
        algorithm = TradingAlgorithm(
            exchange_id='binance',
            symbol='BTC/USDT',
            timeframe='1h',
            initial_balance=10000,  # 10,000 USDT
            test_mode=True,
            market_type='spot',
            leverage=1
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
