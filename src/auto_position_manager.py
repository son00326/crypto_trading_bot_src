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

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('auto_position_manager')

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
        
        logger.info("자동 포지션 관리자가 초기화되었습니다.")
    
    def start_monitoring(self):
        """포지션 모니터링 시작"""
        try:
            if self.monitoring_active:
                logger.warning("포지션 모니터링이 이미 활성화되어 있습니다.")
                return
            
            # 필요한 속성이 있는지 확인
            if not hasattr(self, 'trading_algorithm') or self.trading_algorithm is None:
                logger.error("트레이딩 알고리즘이 초기화되지 않았습니다.")
                return
            
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(target=self._monitor_positions_loop)
            logger.info("포지션 모니터링이 시작되었습니다.")
        except Exception as e:
            logger.error(f"포지션 모니터링 시작 오류: {e}")
            self.monitoring_active = False
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        logger.info(f"포지션 모니터링을 시작합니다. 모니터링 간격: {self.monitor_interval}초")
        
    def stop_monitoring(self):
        """포지션 모니터링 중지"""
        if not self.monitoring_active:
            logger.warning("포지션 모니터링이 이미 비활성화되어 있습니다.")
            return
        
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            
        logger.info("포지션 모니터링을 중지했습니다.")
    
    def _monitor_positions_loop(self):
        """포지션 모니터링 루프"""
        while self.monitoring_active:
            try:
                if not self.auto_sl_tp_enabled:
                    time.sleep(self.monitor_interval)
                    continue
                
                # 열린 포지션이 있는지 확인
                has_open_positions = self._check_and_manage_positions()
                
                # 열린 포지션이 없으면 모니터링 간격을 늘림
                sleep_interval = self.monitor_interval
                if not has_open_positions:
                    sleep_interval = self.monitor_interval * 2
                
                time.sleep(sleep_interval)
                
            except Exception as e:
                logger.error(f"포지션 모니터링 중 오류 발생: {e}")
                time.sleep(self.monitor_interval)
    
    def _check_and_manage_positions(self):
        """포지션 확인 및 관리"""
        # 현재 포지션 가져오기
        positions = self.trading_algorithm.get_open_positions()
        if not positions:
            return False
        
        # 현재 가격 조회
        current_price = self.trading_algorithm.get_current_price()
        if current_price <= 0:
            logger.warning(f"유효하지 않은 현재 가격: {current_price}")
            return True
        
        # 각 포지션에 대해 손절매/이익실현 조건 확인
        for position in positions:
            self._check_position_exit_conditions(position, current_price)
        
        return True
    
    def _check_position_exit_conditions(self, position, current_price):
        """개별 포지션의 종료 조건 확인"""
        try:
            # 포지션 ID 확인
            position_id = position.get('id')
            if not position_id:
                logger.warning("포지션 ID가 없어 자동 관리할 수 없습니다.")
                return
            
            # 포지션 정보 확인
            side = position.get('side')
            entry_price = position.get('entry_price')
            if not side or not entry_price or entry_price <= 0:
                logger.warning(f"유효하지 않은 포지션 정보: side={side}, entry_price={entry_price}")
                return
            
            # 손절매/이익실현 가격 계산
            risk_config = self.trading_algorithm.risk_management
            
            if side.lower() == 'long':
                stop_loss_price = entry_price * (1 - risk_config['stop_loss_pct'])
                take_profit_price = entry_price * (1 + risk_config['take_profit_pct'])
            else:  # short
                stop_loss_price = entry_price * (1 + risk_config['stop_loss_pct'])
                take_profit_price = entry_price * (1 - risk_config['take_profit_pct'])
            
            # 종료 조건 확인
            risk_manager = self.trading_algorithm.exchange_api.risk_manager
            risk_manager.partial_tp_enabled = self.partial_tp_enabled
            
            exit_type, exit_reason, exit_percentage = risk_manager.check_exit_conditions(
                current_price=current_price,
                position_type=side,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                position_id=position_id,
                check_partial=self.partial_tp_enabled
            )
            
            # 청산 조건 충족 시 처리
            if exit_type:
                self._execute_position_exit(position, current_price, exit_type, exit_reason, exit_percentage)
                
        except Exception as e:
            logger.error(f"포지션 종료 조건 확인 중 오류: {e}")
    
    def _execute_position_exit(self, position, current_price, exit_type, exit_reason, exit_percentage):
        """포지션 청산 실행"""
        try:
            logger.info(f"자동 포지션 청산: {exit_type}, 이유: {exit_reason}, 비율: {exit_percentage:.1%}")
            
            # 포지션 정보 확인
            position_id = position.get('id')
            side = position.get('side')
            amount = position.get('amount', 0)
            
            if amount <= 0:
                logger.warning(f"포지션 수량이 0 이하입니다: {amount}")
                return
            
            # 청산할 수량 계산
            exit_amount = amount * exit_percentage
            
            # 청산 정보
            exit_info = {
                'exit_type': exit_type,
                'exit_reason': exit_reason,
                'auto_exit': True,
                'timestamp': datetime.now().isoformat()
            }
            
            # 롱 포지션 청산 (매도)
            if side.lower() == 'long':
                self.trading_algorithm.execute_sell(
                    price=current_price,
                    quantity=exit_amount,
                    additional_exit_info=exit_info,
                    percentage=exit_percentage,
                    position_id=position_id
                )
            
            # 숏 포지션 청산 (매수)
            elif side.lower() == 'short':
                self.trading_algorithm.execute_buy(
                    price=current_price,
                    quantity=exit_amount,
                    additional_info=exit_info,
                    close_position=True,
                    position_id=position_id
                )
            
            logger.info(f"자동 포지션 청산 완료: {exit_type}, 포지션ID: {position_id}")
            
        except Exception as e:
            logger.error(f"포지션 청산 실행 중 오류: {e}")
    
    def set_auto_sl_tp(self, enabled):
        """자동 손절매/이익실현 활성화/비활성화"""
        try:
            self.auto_sl_tp_enabled = bool(enabled)  # bool로 변환하여 안전하게 대입
            logger.info(f"자동 손절매/이익실현 {'활성화' if self.auto_sl_tp_enabled else '비활성화'}")
        except Exception as e:
            logger.error(f"자동 손절매/이익실현 설정 오류: {e}")
            self.auto_sl_tp_enabled = False  # 오류 발생 시 안전하게 비활성화
    
    def set_partial_tp(self, enabled):
        """부분 이익실현 활성화/비활성화"""
        try:
            self.partial_tp_enabled = bool(enabled)  # bool로 변환하여 안전하게 대입
            logger.info(f"부분 이익실현 {'활성화' if self.partial_tp_enabled else '비활성화'}")
        except Exception as e:
            logger.error(f"부분 이익실현 설정 오류: {e}")
            self.partial_tp_enabled = False  # 오류 발생 시 안전하게 비활성화
