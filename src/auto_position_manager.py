"""
자동 포지션 관리 모듈 - 암호화폐 자동매매 봇

이 모듈은 포지션의 자동 모니터링 및 관리 기능을 제공합니다.
- 자동 손절매/이익실현 기능
- 부분 청산 기능
- 포지션 안전장치 기능
"""

import time
import logging
import threading
from datetime import datetime
import traceback

# 개선된 오류 처리 시스템 추가
from src.error_handlers import (
    network_error_handler, api_error_handler, trade_error_handler, safe_execution,
    NetworkError, APIError, TradeError, PositionError, PositionNotFound, MarginLevelCritical
)

# 개선된 로깅 설정 사용
from src.logging_config import get_logger

# 로거 가져오기
logger = get_logger('crypto_bot.auto_position_manager')

class AutoPositionManager:
    """포지션 자동 관리 클래스"""
    
    def __init__(self, trading_algorithm, monitor_interval=15):
        """
        자동 포지션 관리자 초기화
        
        Args:
            trading_algorithm: TradingAlgorithm 인스턴스
            monitor_interval (int): 포지션 모니터링 간격 (초)
        """
        self.trading_algorithm = trading_algorithm
        self.monitor_interval = monitor_interval
        self.monitoring_active = False
        self.monitor_thread = None
        
        # 설정값
        self.auto_sl_tp_enabled = False  # 자동 손절매/이익실현 활성화 여부
        self.partial_tp_enabled = False  # 부분 이익실현 활성화 여부
        self.margin_safety_enabled = True  # 마진 안전장치 활성화 여부
        
        # 손절매/이익실현 설정
        self.sl_percentage = 0.05  # 기본 손절매 비율 (5%)
        self.tp_percentage = 0.1   # 기본 이익실현 비율 (10%)
        
        # 마진 안전장치 관련 상태 변수
        self.last_margin_check_time = 0
        self.margin_check_interval = 60  # 마진 레벨 검사 간격(초)
        self.emergency_actions_taken = False  # 비상 조치 수행 여부
        
        logger.info("자동 포지션 관리자가 초기화되었습니다.")
        logger.info("마진 안전장치 기능이 활성화되었습니다.")
    
    @safe_execution
    def start_monitoring(self):
        """포지션 모니터링 시작"""
        if self.monitoring_active:
            logger.warning("포지션 모니터링이 이미 활성화되어 있습니다.")
            return
        
        # 필요한 속성이 있는지 확인
        if not hasattr(self, 'trading_algorithm') or self.trading_algorithm is None:
            logger.error("트레이딩 알고리즘이 초기화되지 않았습니다.")
            raise ValueError("트레이딩 알고리즘이 초기화되지 않음")
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_positions_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        logger.info(f"포지션 모니터링을 시작합니다. 모니터링 간격: {self.monitor_interval}초")
        return True
        
    @safe_execution
    def stop_monitoring(self):
        """포지션 모니터링 중지"""
        if not self.monitoring_active:
            logger.warning("포지션 모니터링이 이미 비활성화되어 있습니다.")
            return False
        
        # 먼저 monitoring_active를 False로 설정하여 스레드가 자연스럽게 종료되도록 함
        self.monitoring_active = False
        logger.info("모니터링 플래그를 비활성화했습니다. 스레드 종료 대기 중...")
        
        # 스레드가 있으면 안전하게 종료 대기
        if self.monitor_thread and self.monitor_thread.is_alive():
            try:
                self.monitor_thread.join(timeout=2.0)
                if self.monitor_thread.is_alive():
                    logger.warning("모니터링 스레드가 시간 내에 종료되지 않았지만, 비활성화 플래그는 설정되었습니다.")
            except Exception as e:
                logger.error(f"스레드 종료 중 오류: {e}")
            
        logger.info("포지션 모니터링을 중지했습니다.")
        return True
        
    @safe_execution
    def set_auto_sl_tp(self, enabled=True, partial_tp=False, sl_percentage=None, tp_percentage=None):
        """
        자동 손절매/이익실현 기능 설정
        
        Args:
            enabled (bool): 자동 손절매/이익실현 활성화 여부
            partial_tp (bool): 부분 이익실현 활성화 여부
            sl_percentage (float): 손절매 비율 (None이면 현재 설정 유지)
            tp_percentage (float): 이익실현 비율 (None이면 현재 설정 유지)
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 기능 활성화 여부 설정
            self.auto_sl_tp_enabled = enabled
            self.partial_tp_enabled = partial_tp
            
            # 비율 설정 (지정한 경우에만 변경)
            if sl_percentage is not None and 0 < sl_percentage < 1.0:
                self.sl_percentage = sl_percentage
            
            if tp_percentage is not None and 0 < tp_percentage < 1.0:
                self.tp_percentage = tp_percentage
            
            # 설정 적용 확인
            if self.auto_sl_tp_enabled:
                logger.info(f"자동 손절매/이익실현 기능이 활성화됨. 손절비율={self.sl_percentage:.1%}, 이익실현비율={self.tp_percentage:.1%}")
                
                # 부분 이익실현 설정 확인
                if self.partial_tp_enabled:
                    logger.info("부분 이익실현 기능이 활성화됨")
                
                # 모니터링이 활성화되지 않은 경우 자동으로 시작
                if not self.monitoring_active:
                    logger.info("손절매/이익실현 기능 활성화로 모니터링 자동 시작")
                    self.start_monitoring()
            else:
                logger.info("자동 손절매/이익실현 기능이 비활성화됨")
            
            return True
        except Exception as e:
            logger.error(f"자동 손절매/이익실현 기능 설정 중 오류: {e}")
            return False
    
    def _monitor_positions_loop(self):
        """포지션 모니터링 루프"""
        consecutive_errors = 0
        max_consecutive_errors = 5
        last_success_time = time.time()
        
        while self.monitoring_active:
            try:
                current_time = time.time()
                
                # 자동 손절매/이익실현 활성화 확인
                has_open_positions = False
                if self.auto_sl_tp_enabled:
                    # 열린 포지션이 있는지 확인 - 네트워크 오류에 대해 더 강화된 오류 처리 필요
                    try:
                        has_open_positions = self._check_and_manage_positions()
                        # 성공적인 검사이면 오류 카운터 초기화
                        consecutive_errors = 0
                        last_success_time = current_time
                    except NetworkError as e:
                        consecutive_errors += 1
                        logger.warning(f"포지션 검사 중 네트워크 오류 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                        # 네트워크 오류 발생 시 기다리는 시간 조정
                        sleep_interval = min(30, consecutive_errors * 5)  # 최대 30초, 오류 발생마다 5초씩 증가
                        time.sleep(sleep_interval)
                        continue
                    except Exception as e:
                        consecutive_errors += 1
                        logger.error(f"포지션 검사 중 예상치 못한 오류 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                # 마진 안전장치 검사 (설정된 간격으로 실행)
                if self.margin_safety_enabled and (current_time - self.last_margin_check_time >= self.margin_check_interval):
                    try:
                        self._check_margin_safety()
                        self.last_margin_check_time = current_time
                    except Exception as e:
                        logger.error(f"마진 안전성 검사 오류: {e}")
                        # 오류가 발생해도 마지막 검사 시간은 업데이트
                        self.last_margin_check_time = current_time - (self.margin_check_interval // 2)  # 다음 검사 시간을 좀 빨리 설정
                
                # 열린 포지션이 없으면 모니터링 간격을 늘림
                sleep_interval = self.monitor_interval
                if not has_open_positions:
                    sleep_interval = self.monitor_interval * 2
                # 비상 상태에서는 모니터링 간격을 줄임
                elif self.emergency_actions_taken:
                    sleep_interval = max(5, self.monitor_interval // 3)  # 최소 5초, 또는 기본 간격의 1/3
                
                # 지속적인 오류 또는 오랜 시간 성공적인 검사가 없을 때 환인 메시지 생성
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(f"연속 {consecutive_errors}회 오류 발생: 모니터링 시스템을 재시작하는 것이 좋을 수 있습니다.")
                    # 최대 연속 오류 횟수 초과 시 오류 카운터 초기화 (로그 스팸 방지)
                    consecutive_errors = 0
                
                # 오랜 시간 성공적인 검사가 없을 때 (1시간 이상)
                if (current_time - last_success_time) > 3600:
                    logger.warning(f"마지막 성공 검사로부터 {(current_time - last_success_time) // 60:.0f}분 경과: 시스템 상태를 확인하세요.")
                    last_success_time = current_time  # 로그 스팸 방지를 위해 시간 업데이트
                
                time.sleep(sleep_interval)
                
            except Exception as e:
                logger.error(f"포지션 모니터링 중 예상치 못한 오류 발생: {e}")
                logger.error(traceback.format_exc())  # 자세한 스택 트레이스 추가
                # 오류 발생 시 안전한 재시도를 위해 짠시 대기
                time.sleep(max(self.monitor_interval, 10))  # 최소 10초 이상 대기
    
    @network_error_handler(retry_count=3, max_delay=30)
    def _check_and_manage_positions(self):
        """포지션 확인 및 관리"""
        try:
            # 현재 포지션 가져오기 - API 호출 실패 가능
            positions = self.trading_algorithm.get_open_positions()
            if not positions:
                logger.debug("열린 포지션이 없습니다.")
                return False
            
            # 현재 가격 조회 - API 호출 실패 가능
            current_price = self.trading_algorithm.get_current_price()
            if current_price <= 0:
                logger.warning(f"유효하지 않은 현재 가격: {current_price}. 가격 조회 재시도 필요")
                raise APIError(f"유효하지 않은 현재 가격: {current_price}")
                
            # 로그에 현재 설정 표시
            if self.auto_sl_tp_enabled:
                logger.debug(f"자동 손절매/이익실현 활성화됨: 손절={self.sl_percentage:.1%}, 이익실현={self.tp_percentage:.1%}, 부분 이익실현: {self.partial_tp_enabled}")
            
            # 성공적으로 정보 수집 완료 - 로그 추가
            position_count = len(positions)
            logger.debug(f"현재 {position_count}개의 포지션 처리 중, 현재가: {current_price}")
            
            # 각 포지션에 대해 손절매/이익실현 조건 확인
            for i, position in enumerate(positions):
                try:
                    position_id = position.get('id', f"unknown_position_{i}")
                    logger.debug(f"포지션 {i+1}/{position_count} 검사 중: ID={position_id}")
                    self._check_position_exit_conditions(position, current_price)
                except Exception as e:
                    # 개별 포지션 처리 오류가 전체 과정을 중단하지 않도록 처리
                    logger.error(f"포지션 {position_id} 처리 중 오류: {e} - 다음 포지션으로 진행합니다.")
            
            return True
            
        except NetworkError as e:
            # 네트워크 오류에 대한 특별 처리 - network_error_handler에 의해 재시도 처리됨
            logger.warning(f"포지션 검사 중 네트워크 오류: {e}")
            raise  # network_error_handler에서 재시도를 처리하도록 예외 전파
        except APIError as e:
            # API 오류에 대한 특별 처리
            logger.warning(f"API 오류: {e}")
            raise  # network_error_handler에서 재시도를 처리하도록 예외 전파
        except Exception as e:
            # 기타 예상치 못한 오류
            logger.error(f"포지션 검사 중 예상치 못한 오류: {e}")
            logger.error(traceback.format_exc())
            return False  # 예상치 못한 오류는 False 반환
    
    @trade_error_handler(retry_count=1)
    def _check_position_exit_conditions(self, position, current_price):
        """개별 포지션의 종료 조건 확인"""
        # 포지션 ID 확인
        position_id = position.get('id')
        if not position_id:
            logger.warning("포지션 ID가 없어 자동 관리할 수 없습니다.")
            raise PositionError("포지션 ID가 없어 처리할 수 없음")
        
        # 포지션 정보 확인
        side = position.get('side')
        entry_price = position.get('entry_price')
        if not side or not entry_price or entry_price <= 0:
            logger.warning(f"포지션 {position_id}: 유효하지 않은 포지션 정보 side={side}, entry_price={entry_price}")
            raise PositionError(f"유효하지 않은 포지션 정보: side={side}, entry_price={entry_price}")
        
        try:
            # 위험 관리 구성 가져오기
            risk_config = self.trading_algorithm.risk_management
            if not risk_config:
                logger.warning(f"포지션 {position_id}: 위험 관리 구성이 없습니다. 기본값 사용")
                # 기본 값 설정 (자체 설정 사용)
                risk_config = {'stop_loss_pct': self.sl_percentage, 'take_profit_pct': self.tp_percentage}
            
            # RiskManager를 사용하여 손절매/이익실현 가격 계산
            try:
                risk_manager = self.trading_algorithm.exchange_api.risk_manager
                
                # 위험 관리자 설정 업데이트
                risk_manager.partial_tp_enabled = self.partial_tp_enabled
                risk_manager.auto_exit_enabled = self.auto_sl_tp_enabled
                
                # 현재 설정으로 위험 관리자 업데이트
                if not hasattr(risk_manager, 'risk_config'):
                    risk_manager.risk_config = {}
                    
                risk_manager.risk_config['stop_loss_pct'] = self.sl_percentage
                risk_manager.risk_config['take_profit_pct'] = self.tp_percentage
                
                # RiskManager의 중앙화된 계산 메서드 사용
                stop_loss_price = risk_manager.calculate_stop_loss_price(
                    entry_price=entry_price,
                    side=side,
                    custom_pct=risk_config.get('stop_loss_pct')
                )
                
                take_profit_price = risk_manager.calculate_take_profit_price(
                    entry_price=entry_price,
                    side=side,
                    custom_pct=risk_config.get('take_profit_pct')
                )
                
                if stop_loss_price is None or take_profit_price is None:
                    logger.error(f"포지션 {position_id}: 손절매/이익실현 가격 계산 실패")
                    raise ValueError("손절매/이익실현 가격 계산 실패")
                    
            except Exception as e:
                logger.error(f"RiskManager를 통한 가격 계산 중 오류: {e}")
                # 폴백: 기본 RiskManager 인스턴스 생성하여 계산
                logger.warning(f"폴백 모드로 새 RiskManager 인스턴스 생성")
                try:
                    from src.risk_manager import RiskManager
                    fallback_risk_manager = RiskManager(self.config)
                    fallback_risk_manager.risk_config = {
                        'stop_loss_pct': risk_config.get('stop_loss_pct', self.sl_percentage),
                        'take_profit_pct': risk_config.get('take_profit_pct', self.tp_percentage)
                    }
                    
                    stop_loss_price = fallback_risk_manager.calculate_stop_loss_price(
                        entry_price=entry_price,
                        side=side
                    )
                    
                    take_profit_price = fallback_risk_manager.calculate_take_profit_price(
                        entry_price=entry_price,
                        side=side
                    )
                    
                    if stop_loss_price is None or take_profit_price is None:
                        raise ValueError("폴백 계산도 실패")
                        
                except Exception as fallback_error:
                    logger.error(f"폴백 계산 중 오류: {fallback_error}")
                    # 최후의 수단: 직접 계산 (이전 로직 유지)
                    if side.lower() == 'long':
                        stop_loss_price = entry_price * (1 - risk_config['stop_loss_pct'])
                        take_profit_price = entry_price * (1 + risk_config['take_profit_pct'])
                    else:  # short
                        stop_loss_price = entry_price * (1 + risk_config['stop_loss_pct'])
                        take_profit_price = entry_price * (1 - risk_config['take_profit_pct'])
        except Exception as main_error:
            logger.error(f"포지션 {position_id} 처리 중 일반 오류: {main_error}")
            # 기본값으로 직접 계산
            if side.lower() == 'long':
                stop_loss_price = entry_price * (1 - self.sl_percentage)
                take_profit_price = entry_price * (1 + self.tp_percentage)
            else:  # short
                stop_loss_price = entry_price * (1 + self.sl_percentage)
                take_profit_price = entry_price * (1 - self.tp_percentage)
        
        # 선물거래인 경우 청산 가격 확인
        if self.trading_algorithm.market_type.lower() == 'futures':
            leverage = position.get('leverage', 10)  # 기본 레버리지 10
            liquidation_price = risk_manager.calculate_liquidation_price(
                entry_price=entry_price,
                side=side,
                leverage=leverage
            )
            
            if liquidation_price:
                # 현재 가격과 청산 가격의 거리 계산
                if side.lower() == 'long':
                    liq_distance_pct = (current_price - liquidation_price) / current_price * 100
                    if liq_distance_pct < 5:  # 청산 가격과 5% 이내 근접
                        logger.critical(f"⚠️⚠️⚠️ 포지션 {position_id} 청산 경고! 현재가={current_price}, 청산가={liquidation_price} (이격: {liq_distance_pct:.2f}%)")
                else:  # short
                    liq_distance_pct = (liquidation_price - current_price) / current_price * 100
                    if liq_distance_pct < 5:  # 청산 가격과 5% 이내 근접
                        logger.critical(f"⚠️⚠️⚠️ 포지션 {position_id} 청산 경고! 현재가={current_price}, 청산가={liquidation_price} (이격: {liq_distance_pct:.2f}%)")
                
                logger.debug(f"포지션 {position_id} (유형: {side}) 검사: 현재가={current_price}, 손절가={stop_loss_price:.2f}, 이익실현가={take_profit_price:.2f}, 청산가={liquidation_price:.2f}")
        else:
            logger.debug(f"포지션 {position_id} (유형: {side}) 검사: 현재가={current_price}, 손절가={stop_loss_price:.2f}, 이익실현가={take_profit_price:.2f}")
        
        # 종료 조건 확인 - API 오류 발생 가능
        try:
            exit_type, exit_reason, exit_percentage = risk_manager.check_exit_conditions(
                current_price=current_price,
                position_type=side,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                position_id=position_id,
                check_partial=self.partial_tp_enabled
            )
        except Exception as e:
            logger.error(f"포지션 {position_id}: 종료 조건 검사 중 오류: {e}")
            raise APIError(f"종료 조건 검사 실패: {e}")
        
        # 청산 조건 충족 시 처리
        if exit_type:
            logger.info(f"포지션 {position_id}: {exit_type} 시그널 발생, 이유: {exit_reason}, 비율: {exit_percentage:.1%}")
            self._execute_position_exit(position, current_price, exit_type, exit_reason, exit_percentage)
            return True
            
        return False
            
    @trade_error_handler(retry_count=3, max_delay=20)
    def _execute_position_exit(self, position, current_price, exit_type, exit_reason, exit_percentage):
        """
        포지션 청산 실행
        
        Args:
            position (dict): 청산할 포지션 정보
            current_price (float): 현재 가격
            exit_type (str): 청산 유형 (stop_loss, take_profit, manual, emergency)
            exit_reason (str): 청산 이유
            exit_percentage (float): 청산할 포지션 비율 (0.0-1.0)
        
        Returns:
            bool: 성공 여부
        """
        # 중복 주문 방지를 위한 주문 ID 추적
        # 같은 포지션에 대해 최근 주문을 추적하여 중복 주문 정보를 저장
        order_id_cache_key = f"exit_order_{position.get('id')}_{exit_type}"
        last_order_timestamp = getattr(self, '_last_exit_order_timestamps', {}).get(order_id_cache_key, 0)
        current_timestamp = time.time()
        
        # 최소 주문 간격 설정 (1초)
        min_order_interval = 1.0
        
        # 마지막 주문 이후 최소 주문 간격 체크
        if current_timestamp - last_order_timestamp < min_order_interval:
            logger.warning(f"포지션 {position.get('id')}: 중복 주문 방지 - 마지막 주문 후 {min_order_interval}초 내 주문 무시")
            return False
        try:
            position_id = position.get('id')
            symbol = position.get('symbol')
            side = position.get('side')
            size = position.get('size')
            entry_price = position.get('entry_price')
            
            if not all([position_id, symbol, side, size, entry_price]):
                logger.error(f"포지션 청산 실패: 필수 정보 부족 [ID={position_id}, symbol={symbol}, side={side}, size={size}, entry_price={entry_price}]")
                raise PositionError(f"포지션 청산을 위한 필수 정보 부족")
            
            # 청산 사이즈 계산
            exit_size = size
            if 0 < exit_percentage < 1.0:
                exit_size = size * exit_percentage
                logger.info(f"포지션 {position_id}: 부분 청산 ({exit_percentage:.1%}, {exit_size}/{size})")
            
            # 청산 시도 전 로그
            logger.info(f"포지션 {position_id} ({symbol}, {side}) 청산 시도: 이유={exit_reason}, 현재가={current_price}, 사이즈={exit_size}")
            
            # 청산 실행 - 네트워크 오류 발생 가능
            try:
                # 주문 실행
                order_result = self.trading_algorithm.close_position(
                    position_id=position_id,
                    symbol=symbol,
                    side=side,
                    amount=exit_size,
                    reason=exit_reason
                )
                
                # 주문 ID가 반환되었는지 확인
                order_id = None
                if isinstance(order_result, dict) and 'id' in order_result:
                    order_id = order_result.get('id')
                elif isinstance(order_result, str):
                    order_id = order_result
                
                if not order_id:
                    logger.warning(f"포지션 {position_id} 청산: 주문 ID가 없습니다. 주문 상태를 확인할 수 없습니다.")
                else:
                    # 주문 상태 확인
                    try:
                        # 주문 상태 확인 전 약간의 지연
                        time.sleep(0.5)  # 0.5초 대기
                        
                        # 주문 상태 확인
                        order_status = self.trading_algorithm.exchange_api.get_order_status(symbol, order_id)
                        
                        if order_status and order_status.get('status') in ['closed', 'filled']:
                            logger.info(f"포지션 {position_id} 청산 주문({order_id}) 상태 확인: {order_status.get('status')}")
                        elif order_status and order_status.get('status') == 'canceled':
                            logger.warning(f"포지션 {position_id} 청산 주문({order_id})이 취소되었습니다.")
                            return False
                        else:
                            logger.warning(f"포지션 {position_id} 청산 주문({order_id}) 상태: {order_status.get('status') if order_status else '알 수 없음'}")
                    except Exception as status_error:
                        logger.error(f"포지션 {position_id} 청산 주문 상태 확인 중 오류: {status_error}")
                
                # 중복 주문 방지를 위한 주문 시간 기록 업데이트
                if not hasattr(self, '_last_exit_order_timestamps'):
                    self._last_exit_order_timestamps = {}
                self._last_exit_order_timestamps[order_id_cache_key] = current_timestamp
                
                # 성공 처리
                result = bool(order_id)  # 주문 ID가 있으면 성공으로 처리
                
            except NetworkError as e:
                logger.error(f"포지션 {position_id} 청산 중 네트워크 오류: {e}")
                raise  # trade_error_handler에서 재시도 처리
            except APIError as e:
                logger.error(f"포지션 {position_id} 청산 중 API 오류: {e}")
                raise  # trade_error_handler에서 재시도 처리
            except Exception as e:
                logger.error(f"포지션 {position_id} 청산 중 예상치 못한 오류: {e}")
                raise TradeError(f"포지션 청산 중 오류: {e}")
            
            # 결과 처리
            if result:
                # 성공 시 수익/손실 계산
                profit_loss = (current_price - entry_price) * exit_size if side.lower() == 'long' else (entry_price - current_price) * exit_size
                profit_loss_pct = abs(current_price - entry_price) / entry_price * 100
                pnl_direction = '+' if profit_loss > 0 else '-'
                
                # 성공 로그
                logger.info(f"포지션 {position_id}: {exit_type} 실행 성공. 이유: {exit_reason}, PnL: {pnl_direction}{abs(profit_loss):.2f} ({profit_loss_pct:.2f}%)")
                
                # 비상 상태가 아니면 비상 조치 기록 초기화
                if exit_type.lower() != 'emergency':
                    self.emergency_actions_taken = False
                
                return True
            else:
                # 청산 실패 처리
                error_msg = f"포지션 {position_id}: {exit_type} 실행 실패. 이유: {exit_reason}"
                logger.error(error_msg)
                raise TradeError(error_msg)
                
        except NetworkError as e:
            # 네트워크 오류 - 재시도 가능
            logger.warning(f"포지션 {position_id} 청산 중 네트워크 오류: {e}")
            raise  # trade_error_handler에서 재시도 처리
        except Exception as e:
            # 기타 예상치 못한 오류
            logger.error(f"포지션 {position_id} 청산 중 최종 오류: {e}")
            logger.error(traceback.format_exc())
            
            # 중요한 청산 실패인 경우 비상 상태 플래그 설정
            if exit_type.lower() in ['stop_loss', 'emergency']:
                self.emergency_actions_taken = True
                logger.critical(f"중요 포지션 청산 실패 ({exit_type}): 비상 상태 플래그 설정")
            
            return False
            profit_loss_pct = abs(current_price - entry_price) / entry_price * 100
            pnl_direction = '+' if profit_loss > 0 else '-'
            
            # 성공 로그
            logger.info(f"포지션 {position_id}: {exit_type} 실행 성공. 이유: {exit_reason}, PnL: {pnl_direction}{abs(profit_loss):.2f} ({profit_loss_pct:.2f}%)")
            
            # 비상 상태가 아니면 중학성 조치 기록 초기화
            if exit_type.lower() != 'emergency':
                self.emergency_actions_taken = False
            
            return True
        else:
            # 청산 실패 처리
            error_msg = f"포지션 {position_id}: {exit_type} 실행 실패. 이유: {exit_reason}"
            logger.error(error_msg)
            raise TradeError(error_msg)
            
    def _check_margin_safety(self):
        """마진 안전성 검사 및 위험 상황에서 자동 대응"""
        try:
            # 마진 안전장치가 비활성화되었거나 현물 계정이 아닌 경우 스킵
            if not self.margin_safety_enabled or self.trading_algorithm.market_type.lower() != 'futures':
                return
            
            # 계정 정보 가져오기
            account_info = self.trading_algorithm.exchange_api.get_account_info()
            if not account_info:
                logger.warning("계정 정보를 가져오지 못했습니다. 마진 안전성 검사를 건너끻니다.")
                return
            
            # 현재 포지션 가져오기
            positions = self.trading_algorithm.get_open_positions()
            
            # 마진 안전성 검사
            risk_manager = self.trading_algorithm.exchange_api.risk_manager
            safety_status, message, suggested_actions = risk_manager.check_margin_safety(
                account_info=account_info,
                current_positions=positions,
                market_type=self.trading_algorithm.market_type
            )
            
            # 반환된 경고 메시지 처리
            if safety_status != 'safe' and message:
                logger.warning(f"마진 안전장치 경고: {message}")
                
                # 위험 상태에 따른 조치 실행
                self._handle_margin_safety_actions(safety_status, suggested_actions, positions, account_info)
            
            # 안전 상태에서는 비상 조치 플래그 비활성화
            elif safety_status == 'safe' and self.emergency_actions_taken:
                self.emergency_actions_taken = False
                logger.info("마진 레벨이 안전 상태로 회복되었습니다. 비상 조치 상태를 해제합니다.")
            
        except Exception as e:
            logger.error(f"마진 안전성 검사 중 오류: {e}")
    
    def _handle_margin_safety_actions(self, safety_status, suggested_actions, positions, account_info):
        """마진 안전성 상태에 따른 조치 실행"""
        try:
            # 비상 상태 표시
            if safety_status == 'emergency':
                self.emergency_actions_taken = True
                logger.critical("마진 안전장치: 비상 상태 - 주의가 필요한 자동 조치를 실행합니다.")
            
            # 제안된 조치가 없는 경우 처리
            if not suggested_actions:
                return
            
            # 위험도에 따라 조치 실행
            if "position_reduce_emergency" in suggested_actions:
                # 긴급 상황: 가장 위험한 포지션의 50% 청산
                self._emergency_reduce_positions(positions, 0.5)
                
            elif "position_reduce_partial" in suggested_actions:
                # 심각 상황: 위험한 포지션의 30% 청산
                self._emergency_reduce_positions(positions, 0.3)
            
            # 레버리지 감소 처리
            if "leverage_reduce" in suggested_actions:
                try:
                    # 자동 레버리지 조절 기능 사용
                    from src.exchange_utils import LeverageManager, MarginCalculator
                    
                    # 현재 심볼 가져오기
                    symbol = self.trading_algorithm.symbol if hasattr(self.trading_algorithm, 'symbol') else None
                    
                    if symbol and hasattr(self.trading_algorithm, 'exchange_api'):
                        exchange_api = self.trading_algorithm.exchange_api
                        
                        # 현재 레버리지 가져오기
                        current_leverage = LeverageManager.get_current_leverage(exchange_api, symbol)
                        
                        # 마진 레벨 가져오기
                        margin_level = None
                        if account_info:
                            # 거래소 ID 가져오기
                            exchange_id = exchange_api.exchange_id if hasattr(exchange_api, 'exchange_id') else 'unknown'
                            margin_level = MarginCalculator.calculate_margin_level(exchange_id, account_info)
                        
                        # 안전한 레버리지 계산
                        if margin_level and margin_level < float('inf'):
                            safe_leverage = LeverageManager.calculate_safe_leverage(margin_level, current_leverage)
                            
                            # 레버리지 자동 조절
                            if safe_leverage < current_leverage:
                                result, new_leverage, message = LeverageManager.adjust_leverage(exchange_api, symbol, safe_leverage)
                                
                                if result:
                                    logger.info(f"마진 안전장치: 레버리지 자동 조절 성공 - {current_leverage}x → {new_leverage}x")
                                else:
                                    logger.warning(f"마진 안전장치: 레버리지 자동 조절 실패 - {message}")
                            else:
                                logger.info(f"현재 레버리지({current_leverage}x)가 안전한 수준({safe_leverage}x) 이하입니다. 조정이 필요하지 않습니다.")
                        else:
                            logger.warning("마진 레벨을 계산할 수 없습니다. 레버리지 자동 조절을 건너뜁니다.")
                    else:
                        logger.warning("심볼 정보가 없거나 거래소 API를 사용할 수 없습니다. 수동 조절이 필요할 수 있습니다.")
                        
                except ImportError:
                    logger.warning("레버리지 관리 모듈을 로드할 수 없습니다. 수동 레버리지 조절이 필요합니다.")
                except Exception as e:
                    logger.error(f"레버리지 자동 조절 중 오류: {e}")
                    logger.error(traceback.format_exc())
                    
        except Exception as e:
            logger.error(f"마진 안전 조치 실행 중 오류: {e}")
    
    def _emergency_reduce_positions(self, positions, reduction_percentage):
        """비상 상황에서 포지션 감소 조치 실행"""
        try:
            if not positions:
                logger.warning("현재 열린 포지션이 없습니다. 비상 청산 처리를 건너뛵니다.")
                return
            
            # 현재 가격 조회
            current_price = self.trading_algorithm.get_current_price()
            if current_price <= 0:
                logger.warning(f"유효하지 않은 현재 가격: {current_price}. 비상 청산 처리를 건너뛵니다.")
                return
            
            # 강제 청산 정보
            exit_info = {
                'exit_type': 'margin_safety',
                'exit_reason': '마진 안전장치 강제 청산',
                'auto_exit': True,
                'emergency': True,
                'timestamp': datetime.now().isoformat()
            }
            
            # 각 포지션에 대해 청산 실행
            successful_exits = 0
            for position in positions:
                # 포지션 정보 확인
                position_id = position.get('id')
                side = position.get('side')
                size = position.get('size', position.get('amount', 0))  # size로 변수명 통일
                
                if not position_id or not side or size <= 0:
                    logger.warning(f"포지션 정보 부족: ID={position_id}, side={side}, size={size}")
                    continue
                
                # 청산할 수량 계산
                exit_size = size * reduction_percentage
                
                # 최소 주문 사이즈 검사
                min_order_size = self.trading_algorithm.exchange_api.get_minimum_order_size(position.get('symbol', ''))
                if exit_size < min_order_size:
                    logger.warning(f"포지션 {position_id}: 청산 사이즈({exit_size})가 최소 주문 사이즈({min_order_size})보다 작습니다.")
                    continue
                
                logger.warning(f"마진 안전장치: 포지션 {position_id} 의 {reduction_percentage:.0%} 강제 청산 시도")
                
                try:
                    # 롱 포지션 청산 (매도)
                    if side.lower() == 'long':
                        result = self.trading_algorithm.execute_sell(
                            price=current_price,
                            quantity=exit_size,
                            additional_exit_info=exit_info,
                            percentage=reduction_percentage,
                            position_id=position_id
                        )
                    
                    # 숏 포지션 청산 (매수)
                    elif side.lower() == 'short':
                        result = self.trading_algorithm.execute_buy(
                            price=current_price,
                            quantity=exit_size,
                            additional_info=exit_info,
                            close_position=True,
                            position_id=position_id
                        )
                    
                    if result:
                        successful_exits += 1
                        logger.info(f"포지션 {position_id} 청산 성공: {exit_size} {side}")
                    else:
                        logger.error(f"포지션 {position_id} 청산 실패")
                        
                except Exception as e:
                    logger.error(f"포지션 {position_id} 청산 중 오류: {e}")
                    logger.error(traceback.format_exc())
            
            logger.warning(f"마진 안전장치: 비상 청산 처리가 완료되었습니다. {len(positions)}개 포지션 중 {successful_exits}개 청산 성공")
            
        except Exception as e:
            logger.error(f"비상 포지션 감소 조치 중 오류: {e}")
            logger.error(traceback.format_exc())
    
    def set_auto_sl_tp(self, enabled):
        """자동 손절매/이익실현 활성화/비활성화"""
        try:
            self.auto_sl_tp_enabled = bool(enabled)  # bool로 변환하여 안전하게 대입
            logger.info(f"자동 손절매/이익실현 {'활성화' if self.auto_sl_tp_enabled else '비활성화'}")
        except Exception as e:
            logger.error(f"자동 손절매/이익실현 설정 오류: {e}")
            self.auto_sl_tp_enabled = False  # 오류 발생 시 안전하게 비활성화
    
    def set_partial_tp(self, enabled, tp_levels=None, tp_percentages=None):
        """부분 이익실현 활성화/비활성화
        
        Args:
            enabled (bool): 부분 이익실현 활성화 여부
            tp_levels (list, optional): 이익실현 가격 레벨 목록. 각 요소는 이익실현을 트리거할 가격 비율 (0.0 ~ 1.0)
            tp_percentages (list, optional): 각 레벨에서 청산할 포지션 비율 목록. tp_levels와 같은 길이여야 함.
        """
        try:
            self.partial_tp_enabled = bool(enabled)  # bool로 변환하여 안전하게 대입
            
            # tp_levels와 tp_percentages가 모두 제공된 경우
            if (tp_levels is not None and isinstance(tp_levels, list) and 
                tp_percentages is not None and isinstance(tp_percentages, list)):
                
                # 길이 확인
                if len(tp_levels) == len(tp_percentages) and len(tp_levels) > 0:
                    # 각 레벨과 비율의 유효성 검사
                    valid_levels = []
                    for i, (level, percentage) in enumerate(zip(tp_levels, tp_percentages)):
                        if 0 < level < 1.0 and 0 < percentage <= 1.0:
                            valid_levels.append((level, percentage))
                    
                    # 유효한 레벨이 있으면 정렬하여 저장
                    if valid_levels:
                        # 가격 비율순으로 정렬
                        self.tp_levels = sorted(valid_levels, key=lambda x: x[0])
                        
                        # 요청대로 별도로도 저장
                        self.tp_price_levels = [level for level, _ in self.tp_levels]
                        self.tp_percentages = [pct for _, pct in self.tp_levels]
                        
                        logger.info(f"부분 이익실현 레벨 설정: {self.tp_levels}")
                        logger.info(f"가격 레벨: {self.tp_price_levels}, 청산 비율: {self.tp_percentages}")
                else:
                    logger.warning(f"tp_levels와 tp_percentages의 길이가 다릅니다: {len(tp_levels)} vs {len(tp_percentages)}")
            
            # 레게시 지원: tp_levels가 튜플의 리스트로 제공된 경우
            elif tp_levels is not None and isinstance(tp_levels, list) and len(tp_levels) > 0 and tp_percentages is None:
                # 첫 번째 요소가 튜플인지 확인
                if isinstance(tp_levels[0], (list, tuple)):
                    valid_levels = []
                    for level in tp_levels:
                        if isinstance(level, (list, tuple)) and len(level) == 2:
                            price_pct, amount_pct = level
                            if 0 < price_pct < 1.0 and 0 < amount_pct <= 1.0:
                                valid_levels.append((price_pct, amount_pct))
                    
                    # 유효한 레벨이 있으면 정렬하여 저장
                    if valid_levels:
                        self.tp_levels = sorted(valid_levels, key=lambda x: x[0])
                        self.tp_price_levels = [level for level, _ in self.tp_levels]
                        self.tp_percentages = [pct for _, pct in self.tp_levels]
                        logger.info(f"부분 이익실현 레벨 설정: {self.tp_levels}")
                        logger.info(f"가격 레벨: {self.tp_price_levels}, 청산 비율: {self.tp_percentages}")
                else:
                    logger.warning("tp_levels에 유효한 레벨이 없습니다.")
            
            logger.info(f"부분 이익실현 {'활성화' if self.partial_tp_enabled else '비활성화'}")
            return True
        except Exception as e:
            logger.error(f"부분 이익실현 설정 오류: {e}")
            self.partial_tp_enabled = False  # 오류 발생 시 안전하게 비활성화
            
    def set_margin_safety(self, enabled):
        """마진 안전장치 활성화/비활성화"""
        try:
            self.margin_safety_enabled = bool(enabled)  # bool로 변환하여 안전하게 대입
            logger.info(f"마진 안전장치 {'활성화' if self.margin_safety_enabled else '비활성화'}")
            
            # 마진 안전장치 활성화 시, risk_manager에도 설정 적용
            if hasattr(self.trading_algorithm, 'exchange_api') and \
               hasattr(self.trading_algorithm.exchange_api, 'risk_manager'):
                risk_manager = self.trading_algorithm.exchange_api.risk_manager
                risk_manager.margin_safety_enabled = self.margin_safety_enabled
            
        except Exception as e:
            logger.error(f"마진 안전장치 설정 오류: {e}")
            logger.error(traceback.format_exc())
