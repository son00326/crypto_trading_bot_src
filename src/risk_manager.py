"""
위험 관리 모듈 - 암호화폐 자동매매 봇

이 모듈은 거래 위험을 관리하고 모니터링하는 기능을 제공합니다.
손절매, 이익실현, 포지션 크기 조절, 리스크 모니터링 등의 기능을 구현합니다.
"""

import pandas as pd
import numpy as np
import logging
import time
import json
import os
import smtplib
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.notification_service import NotificationService
from src.error_handlers import simple_error_handler

from src.config import (
    RISK_MANAGEMENT, DATA_DIR, 
    EMAIL_CONFIG, TELEGRAM_CONFIG
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('risk_manager')

class RiskManager:
    """거래 위험 관리를 위한 클래스"""
    
    def __init__(self, exchange_id='binance', symbol='BTC/USDT', risk_config=None, auto_exit_enabled=True,
                 partial_tp_enabled=False, tp_levels=None, tp_percentages=None, margin_safety_enabled=True):
        """
        위험 관리자 초기화
        
        Args:
            exchange_id (str): 거래소 ID
            symbol (str): 거래 심볼
            risk_config (dict, optional): 위험 관리 설정
            auto_exit_enabled (bool): 자동 손절매/이익실현 활성화 여부
            partial_tp_enabled (bool): 부분 이익실현 활성화 여부
            tp_levels (list): 이익실현 수준 목록 [0.05, 0.1, 0.2] (각각 5%, 10%, 20% 이익 시)
            tp_percentages (list): 각 이익실현 수준에서 청산할 비율 [0.3, 0.3, 0.4] (각각 30%, 30%, 40%)
            margin_safety_enabled (bool): 마진 안전장치 활성화 여부
        """
        self.exchange_id = exchange_id
        self.symbol = symbol
        
        # 자동 손절매/이익실현 활성화 여부
        self.auto_exit_enabled = auto_exit_enabled
        
        # 부분 이익실현 설정
        self.partial_tp_enabled = partial_tp_enabled
        self.tp_levels = tp_levels if tp_levels else [0.05, 0.1, 0.2]  # 기본 이익실현 단계: 5%, 10%, 20%
        self.tp_percentages = tp_percentages if tp_percentages else [0.3, 0.3, 0.4]  # 기본 청산 비율: 30%, 30%, 40%
        
        # 마진 안전장치 설정
        self.margin_safety_enabled = margin_safety_enabled
        self.margin_levels = {
            'warning': 1.5,     # 경고 레벨: 마진 레벨 1.5
            'critical': 1.2,   # 심각 경고 레벨: 마진 레벨 1.2
            'emergency': 1.05,  # 비상 상황: 마진 레벨 1.05
        }
        self.last_margin_level_alert = {}
        self.margin_alert_cooldown = 300  # 같은 레벨의 알림 간 최소 간격(초)
        
        # tp_levels와 tp_percentages 검증
        if len(self.tp_levels) != len(self.tp_percentages):
            logger.warning(f"TP 레벨과 백분율 배열 길이 불일치: {len(self.tp_levels)} vs {len(self.tp_percentages)}")
            # 길이 맞추기
            min_len = min(len(self.tp_levels), len(self.tp_percentages))
            self.tp_levels = self.tp_levels[:min_len]
            self.tp_percentages = self.tp_percentages[:min_len]
            logger.info(f"배열 길이 조정함: {min_len}")
        
        # 백분율 합계 검증 - 1.0 초과 시 정규화
        total_percentage = sum(self.tp_percentages)
        if total_percentage > 1.0:
            logger.warning(f"TP 백분율 합계가 1.0을 초과: {total_percentage}")
            # 정규화
            self.tp_percentages = [p/total_percentage for p in self.tp_percentages]
            logger.info(f"백분율 정규화함: {self.tp_percentages}")
        
        # 청산 이력 추적 (포지션 ID를 키로 사용하는 사전)
        self.tp_executed_levels = {}
        
        # 위험 관리 설정
        self.risk_config = risk_config if risk_config else RISK_MANAGEMENT.copy()
        
        # 로그 디렉토리
        self.log_dir = os.path.join(DATA_DIR, 'risk_logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 알림 서비스 초기화
        self.notification_service = NotificationService()
        
        logger.info(f"{exchange_id} 거래소의 {symbol} 위험 관리자가 초기화되었습니다.")
        logger.info(f"위험 관리 설정: {self.risk_config}")
        logger.info(f"자동 손절매/이익실현 활성화: {self.auto_exit_enabled}")
    
    def calculate_position_size(self, account_balance, current_price, risk_per_trade=None):
        """
        적절한 포지션 크기 계산
        
        Args:
            account_balance (float): 계좌 잔고
            current_price (float): 현재 가격
            risk_per_trade (float, optional): 거래당 위험 비율 (None인 경우 설정값 사용)
        
        Returns:
            float: 매수/매도할 수량
        """
        try:
            # 거래당 위험 비율 설정
            if risk_per_trade is None:
                risk_per_trade = self.risk_config['risk_per_trade']
            
            # 최대 포지션 크기 (계좌 자산의 일정 비율)
            max_position_size = account_balance * self.risk_config['max_position_size']
            
            # 거래당 위험 금액
            risk_amount = account_balance * risk_per_trade
            
            # 손절매 비율
            stop_loss_pct = self.risk_config['stop_loss_pct']
            
            # 손절매 가격까지의 거리
            price_distance = current_price * stop_loss_pct
            
            # 위험 기반 포지션 크기 계산
            risk_based_size = risk_amount / price_distance
            
            # 최종 포지션 크기 (최대 포지션 크기와 위험 기반 크기 중 작은 값)
            position_size = min(max_position_size / current_price, risk_based_size)
            
            # 소수점 8자리까지 반올림
            position_size = round(position_size, 8)
            
            logger.info(f"포지션 크기 계산: 계좌잔고={account_balance}, 현재가격={current_price}, 포지션크기={position_size}")
            return position_size
        
        except Exception as e:
            logger.error(f"포지션 크기 계산 중 오류 발생: {e}")
            return 0
    
    def calculate_stop_loss_price(self, entry_price, side, custom_pct=None):
        """
        손절매 가격 계산
        
        Args:
            entry_price (float): 진입 가격
            side (str): 포지션 방향 ('long' 또는 'short')
            custom_pct (float, optional): 커스텀 손절매 비율 (None인 경우 설정값 사용)
        
        Returns:
            float: 손절매 가격
        """
        try:
            # 손절매 비율 설정
            stop_loss_pct = custom_pct if custom_pct is not None else self.risk_config['stop_loss_pct']
            
            # 롱 포지션인 경우 진입가보다 낮은 가격에 손절매
            if side.lower() == 'long':
                stop_loss_price = entry_price * (1 - stop_loss_pct)
            # 숏 포지션인 경우 진입가보다 높은 가격에 손절매
            elif side.lower() == 'short':
                stop_loss_price = entry_price * (1 + stop_loss_pct)
            else:
                logger.error(f"잘못된 포지션 방향: {side}")
                return None
            
            # 소수점 2자리까지 반올림
            stop_loss_price = round(stop_loss_price, 2)
            
            logger.info(f"{side} 포지션 손절매 가격 계산: 진입가격={entry_price}, 손절매가격={stop_loss_price}")
            return stop_loss_price
        
        except Exception as e:
            logger.error(f"손절매 가격 계산 중 오류 발생: {e}")
            return None
    
    @simple_error_handler(default_return=None)
    def calculate_take_profit_price(self, entry_price, side, custom_pct=None):
        """
        이익실현 가격 계산
        
        Args:
            entry_price (float): 진입 가격
            side (str): 포지션 방향 ('long' 또는 'short')
            custom_pct (float, optional): 커스텀 이익실현 비율 (None인 경우 설정값 사용)
        
        Returns:
            float: 이익실현 가격
        """
        try:
            # 이익실현 비율 설정
            take_profit_pct = custom_pct if custom_pct is not None else self.risk_config['take_profit_pct']
            
            # 롱 포지션인 경우 진입가보다 높은 가격에 이익실현
            if side.lower() == 'long':
                take_profit_price = entry_price * (1 + take_profit_pct)
            # 숏 포지션인 경우 진입가보다 낮은 가격에 이익실현
            elif side.lower() == 'short':
                take_profit_price = entry_price * (1 - take_profit_pct)
            else:
                logger.error(f"잘못된 포지션 방향: {side}")
                return None
            
            # 소수점 2자리까지 반올림
            take_profit_price = round(take_profit_price, 2)
            
            logger.info(f"{side} 포지션 이익실현 가격 계산: 진입가격={entry_price}, 이익실현가격={take_profit_price}")
            return take_profit_price
        
        except Exception as e:
            logger.error(f"이익실현 가격 계산 중 오류 발생: {e}")
            return None
    
    @simple_error_handler(default_return=0)
    def calculate_risk_reward_ratio(self, entry_price, stop_loss_price, take_profit_price):
        """
        위험 대비 보상 비율 계산
        
        Args:
            entry_price (float): 진입 가격
            stop_loss_price (float): 손절매 가격
            take_profit_price (float): 이익실현 가격
        
        Returns:
            float: 위험 대비 보상 비율
        """
        # 손실 크기
        risk = abs(entry_price - stop_loss_price)
        
        # 이익 크기
        reward = abs(entry_price - take_profit_price)
        
        # 위험 대비 보상 비율
        if risk > 0:
            risk_reward_ratio = reward / risk
        else:
            logger.warning("위험이 0이므로 위험 대비 보상 비율을 계산할 수 없습니다.")
            return 0
        
        logger.info(f"위험 대비 보상 비율: {risk_reward_ratio:.2f}")
        return risk_reward_ratio
    
    @simple_error_handler(default_return=(None, None, None))
    def check_exit_conditions(self, current_price, position_type, entry_price, stop_loss_price, take_profit_price, position_id=None, check_partial=True):
        """
        현재 가격이 손절매나 이익실현 조건을 만족하는지 확인
        
        Args:
            current_price (float): 현재 가격
            position_type (str): 포지션 타입 ('long' 또는 'short')
            entry_price (float): 진입 가격
            stop_loss_price (float): 손절매 가격
            take_profit_price (float): 이익실현 가격
            position_id (str, optional): 포지션 ID (부분 청산 추적용)
            check_partial (bool): 부분 이익실현 확인 여부
            
        Returns:
            tuple: (exit_type, exit_reason, exit_percentage)
                   exit_type: None, 'stop_loss', 'take_profit', 'partial_tp' 중 하나
                   exit_reason: 종료 이유 설명
                   exit_percentage: 청산할 비율 (None 또는 0~1 사이 값)
        """
        # 안전성 검사 - 진입가격 및 현재 가격 유효성 검사
        if entry_price is None or entry_price <= 0 or current_price is None or current_price <= 0:
            logger.error(f"유효하지 않은 가격 데이터: entry_price={entry_price}, current_price={current_price}")
            return None, None, None
        
        # 자동 손절매/이익실현이 비활성화된 경우 실행하지 않음
        if not self.auto_exit_enabled:
            logger.debug("자동 손절매/이익실현이 비활성화되어 체크하지 않음")
            return None, None, None
            
        # 부분 이익실현 확인 조건 검증
        check_partial_tp = check_partial and self.partial_tp_enabled
        
        # position_id 유효성 검사
        if check_partial_tp and (position_id is None or position_id == ''):
            logger.warning("부분 청산 확인을 위한 position_id가 없음, 전체 청산만 검사합니다.")
            check_partial_tp = False
        
        # 부분 이익실현 확인 (활성화 및 position_id가 있는 경우만)
        if check_partial_tp and position_id:
            try:
                is_partial, level_idx, percentage, reason = self.check_partial_take_profit(
                    position_id, current_price, position_type, entry_price
                )
                if is_partial and percentage is not None and percentage > 0:
                    logger.info(f"부분 청산 신호 발견: {percentage:.1%}, 이유: {reason}")
                    return 'partial_tp', reason, percentage
            except Exception as e:
                logger.error(f"부분 청산 검사 중 오류: {e}")
                # 부분 청산 오류 발생 시 일반 이익실현/손절매 검사로 진행

        if position_type.lower() == 'long':
            # 롱 포지션 체크
            if current_price <= stop_loss_price:
                return 'stop_loss', f'현재 가격({current_price})이 손절매 가격({stop_loss_price}) 이하로 하락', 1.0
            elif current_price >= take_profit_price:
                # 부분 이익실현이 활성화되지 않은 경우에만 전체 청산
                if not self.partial_tp_enabled:
                    return 'take_profit', f'현재 가격({current_price})이 이익실현 가격({take_profit_price}) 이상으로 상승', 1.0
        elif position_type.lower() == 'short':
            # 숏 포지션 체크
            if current_price >= stop_loss_price:
                return 'stop_loss', f'현재 가격({current_price})이 손절매 가격({stop_loss_price}) 이상으로 상승', 1.0
            elif current_price <= take_profit_price:
                # 부분 이익실현이 활성화되지 않은 경우에만 전체 청산
                if not self.partial_tp_enabled:
                    return 'take_profit', f'현재 가격({current_price})이 이익실현 가격({take_profit_price}) 이하로 하락', 1.0
        else:
            logger.warning(f"잘못된 포지션 타입: {position_type}")
        
        # 조건이 충족되지 않으면 None 반환
        return None, None, None
    
    def check_partial_take_profit(self, position_id, current_price, position_type, entry_price):
        """
        현재 가격이 부분 이익실현 조건을 만족하는지 확인
        
        Args:
            position_id (str): 포지션 ID
            current_price (float): 현재 가격
            position_type (str): 포지션 타입 ('long' 또는 'short')
            entry_price (float): 진입 가격
            
        Returns:
            tuple: (is_partial_tp, level_index, percentage, reason)
                   is_partial_tp: 부분 이익실현 조건 충족 여부
                   level_index: 충족된 이익실현 수준 인덱스
                   percentage: 청산할 비율
                   reason: 청산 이유 설명
        """
        # 자동 이익실현 또는 부분 이익실현이 비활성화된 경우 처리
        if not self.auto_exit_enabled or not self.partial_tp_enabled:
            return False, None, None, None
        
        # 안전 검사 - entry_price가 0이면 분모가 0이 되어 예외 발생
        if entry_price == 0 or entry_price is None:
            logger.error(f"진입가격이 유효하지 않음 (0 또는 None): position_id={position_id}")
            return False, None, None, None
        
        # 포지션별 청산 이력 초기화
        if position_id not in self.tp_executed_levels:
            self.tp_executed_levels[position_id] = [False] * len(self.tp_levels)
            logger.info(f"새 포지션 TP 추적 초기화: {position_id}, 추적 레벨: {len(self.tp_levels)}")
        
        try:
            # 현재 수익률 계산
            if position_type.lower() == 'long':
                profit_pct = (current_price - entry_price) / entry_price
            else:  # short
                profit_pct = (entry_price - current_price) / entry_price
                
            # 수익률 로깅 (디버깅 목적)
            if profit_pct > 0.01:  # 1% 이상 수익 시에만 로깅
                executed_levels = sum(1 for level in self.tp_executed_levels.get(position_id, []) if level)
                logger.debug(f"Position {position_id}: 현재 수익률 {profit_pct:.2%}, 이미 청산된 레벨: {executed_levels}/{len(self.tp_levels)}")
        except (ZeroDivisionError, TypeError) as e:
            logger.error(f"수익률 계산 오류: {e}, entry_price={entry_price}, current_price={current_price}")
            return False, None, None, None
        
        # 가장 높은 수준부터 확인 (높은 목표가부터 체크)
        for i in range(len(self.tp_levels) - 1, -1, -1):
            # 이미 해당 수준에서 청산했으면 건너듯
            if self.tp_executed_levels[position_id][i]:
                continue
            
            # 수익률이 해당 수준을 넘었는지 확인
            if profit_pct >= self.tp_levels[i]:
                self.tp_executed_levels[position_id][i] = True
                reason = f"부분 이익실현: 현재 수익률({profit_pct:.2%})이 목표 수준({self.tp_levels[i]:.2%})에 도달"
                logger.info(reason)
                return True, i, self.tp_percentages[i], reason
        
        return False, None, None, None
    
    def check_stop_loss_take_profit(self, current_price, positions):
        """
        손절매 및 이익실현 조건 확인
        
        Args:
            current_price (float): 현재 가격
            positions (list): 포지션 목록
        
        Returns:
            tuple: (손절매 포지션 목록, 이익실현 포지션 목록)
        """
        try:
            stop_loss_positions = []
            take_profit_positions = []
            
            for position in positions:
                # 이미 종료된 포지션은 무시
                if position['status'] != 'open':
                    continue
                
                # 손절매 가격 계산
                stop_loss_price = self.calculate_stop_loss_price(
                    entry_price=position['entry_price'],
                    side=position['side']
                )
                
                # 이익실현 가격 계산
                take_profit_price = self.calculate_take_profit_price(
                    entry_price=position['entry_price'],
                    side=position['side']
                )
                
                # 롱 포지션
                if position['side'].lower() == 'long':
                    # 손절매 조건 확인
                    if current_price <= stop_loss_price:
                        position['exit_reason'] = 'stop_loss'
                        stop_loss_positions.append(position)
                        logger.info(f"롱 포지션 손절매 조건 충족: 진입가={position['entry_price']}, 현재가={current_price}, 손절가={stop_loss_price}")
                    
                    # 이익실현 조건 확인
                    elif current_price >= take_profit_price:
                        position['exit_reason'] = 'take_profit'
                        take_profit_positions.append(position)
                        logger.info(f"롱 포지션 이익실현 조건 충족: 진입가={position['entry_price']}, 현재가={current_price}, 이익실현가={take_profit_price}")
                
                # 숏 포지션
                elif position['side'].lower() == 'short':
                    # 손절매 조건 확인
                    if current_price >= stop_loss_price:
                        position['exit_reason'] = 'stop_loss'
                        stop_loss_positions.append(position)
                        logger.info(f"숏 포지션 손절매 조건 충족: 진입가={position['entry_price']}, 현재가={current_price}, 손절가={stop_loss_price}")
                    
                    # 이익실현 조건 확인
                    elif current_price <= take_profit_price:
                        position['exit_reason'] = 'take_profit'
                        take_profit_positions.append(position)
                        logger.info(f"숏 포지션 이익실현 조건 충족: 진입가={position['entry_price']}, 현재가={current_price}, 이익실현가={take_profit_price}")
            
            return stop_loss_positions, take_profit_positions
        
        except Exception as e:
            logger.error(f"손절매/이익실현 확인 중 오류 발생: {e}")
            return [], []
    
    def calculate_margin_level(self, account_info, market_type='futures'):
        """
        마진 레벨 계산
        
        Args:
            account_info (dict): 계정 정보 (예치금, 포지션 수량 등)
            market_type (str): 시장 유형 ('spot' 또는 'futures')
        
        Returns:
            float: 마진 레벨 (0 < x < 무한대. 1.0에 가까울수록 청산 위험)
        """
        try:
            # 현물 계정이 아닌 경우 계산하지 않음
            if market_type.lower() != 'futures':
                return float('inf')  # 무한대 값 반환 (안전함을 의미)
            
            # 거래소별 마진 계산 유틸리티 사용
            try:
                from src.exchange_utils import MarginCalculator
                margin_level = MarginCalculator.calculate_margin_level(self.exchange_id, account_info)
                logger.info(f"{self.exchange_id} 거래소의 마진 레벨 계산 결과: {margin_level:.4f}")
                return margin_level
            except ImportError:
                logger.warning("exchange_utils 모듈을 가져올 수 없습니다. 기본 마진 계산 방식을 사용합니다.")
                
            # 모듈 로드 실패 시 기본 계산 사용
            wallet_balance = account_info.get('wallet_balance', 0)
            unrealized_pnl = account_info.get('unrealized_pnl', 0)
            maintenance_margin = account_info.get('maintenance_margin', 0)
            
            # 유효성 검사
            if wallet_balance <= 0 or maintenance_margin <= 0:
                logger.error(f"마진 레벨 계산을 위한 유효하지 않은 값: wallet={wallet_balance}, margin={maintenance_margin}")
                return float('inf')  # 무한대 값 반환 (안전함을 의미)
            
            # 마진 레벨 계산 = (Wallet Balance + Unrealized PnL) / Maintenance Margin
            margin_level = (wallet_balance + unrealized_pnl) / maintenance_margin
            
            logger.info(f"기본 마진 레벨 계산 결과: {margin_level:.4f} (wallet={wallet_balance}, unrealized_pnl={unrealized_pnl}, margin={maintenance_margin})")
            return margin_level
        
        except Exception as e:
            logger.error(f"마진 레벨 계산 중 오류: {e}")
            logger.error(traceback.format_exc())
            return float('inf')  # 오류 발생 시 안전한 값 반환
    
    def check_margin_safety(self, account_info, current_positions=None, market_type='futures'):
        """
        마진 안전성 검사 및 경고 발생
        
        Args:
            account_info (dict): 계정 정보
            current_positions (list): 현재 포지션 목록
            market_type (str): 시장 유형 ('spot' 또는 'futures')
            
        Returns:
            tuple: (안전성 상태, 경고 메시지, 제안되는 조치)
        """
        try:
            # 마진 안전장치가 비활성화되었거나 현물 계정이 아닌 경우
            if not self.margin_safety_enabled or market_type.lower() != 'futures':
                return 'safe', None, None
            
            # 마진 레벨 계산
            margin_level = self.calculate_margin_level(account_info, market_type)
            
            # 안전성 상태 확인
            now = time.time()
            
            # 비상 상태 (emergency level) - 청산 임박
            if margin_level <= self.margin_levels['emergency']:
                # 쿨다운 체크
                if 'emergency' not in self.last_margin_level_alert or \
                   (now - self.last_margin_level_alert.get('emergency', 0)) > self.margin_alert_cooldown:
                    self.last_margin_level_alert['emergency'] = now
                    message = f"환불일 수준의 마진 레벨 경고: {margin_level:.2f} - 포지션 청산 발생 위험!"
                    suggested_actions = ["position_reduce_emergency", "leverage_reduce"]
                    return 'emergency', message, suggested_actions
            
            # 심각 경고 (critical level)
            elif margin_level <= self.margin_levels['critical']:
                # 쿨다운 체크
                if 'critical' not in self.last_margin_level_alert or \
                   (now - self.last_margin_level_alert.get('critical', 0)) > self.margin_alert_cooldown:
                    self.last_margin_level_alert['critical'] = now
                    message = f"심각한 마진 레벨 경고: {margin_level:.2f} - 긴급 조치 필요!"
                    suggested_actions = ["position_reduce_partial", "leverage_reduce"]
                    return 'critical', message, suggested_actions
            
            # 일반 경고 (warning level)
            elif margin_level <= self.margin_levels['warning']:
                # 쿨다운 체크
                if 'warning' not in self.last_margin_level_alert or \
                   (now - self.last_margin_level_alert.get('warning', 0)) > self.margin_alert_cooldown:
                    self.last_margin_level_alert['warning'] = now
                    message = f"마진 레벨 경고: {margin_level:.2f} - 구성을 조정하세요."
                    suggested_actions = ["monitor_closely"]
                    return 'warning', message, suggested_actions
            
            # 안전한 상태
            return 'safe', None, None
            
        except Exception as e:
            logger.error(f"마진 안전성 검사 중 오류: {e}")
            return 'unknown', f"마진 안전성 검사 오류: {e}", ["check_manually"]
    
    def suggest_risk_reduction_actions(self, margin_level, current_positions):
        """
        마진 레벨에 따른 위험 감소 조치 제안
        
        Args:
            margin_level (float): 현재 마진 레벨
            current_positions (list): 현재 포지션 목록
            
        Returns:
            list: 제안되는 조치 목록
        """
        try:
            # 출력할 추천 조치 목록
            actions = []
            
            # 마진 레벨에 따른 대응
            if margin_level <= self.margin_levels['emergency']:
                # 매우 위험한 수준: 승로스가 가장 큰 포지션 청산 후 레버리지 감소
                actions.append({
                    'action': 'reduce_positions',
                    'percentage': 0.5,  # 50% 포지션 촐정
                    'target': 'highest_risk',
                    'urgency': 'emergency'
                })
                actions.append({
                    'action': 'reduce_leverage',
                    'target_level': 5,  # 레버리지 5x로 제한
                    'urgency': 'emergency'
                })
                
            elif margin_level <= self.margin_levels['critical']:
                # 심각한 수준: 일부 포지션 청산
                actions.append({
                    'action': 'reduce_positions',
                    'percentage': 0.3,  # 30% 포지션 촐정
                    'target': 'unprofitable',
                    'urgency': 'high'
                })
                actions.append({
                    'action': 'reduce_leverage',
                    'target_level': 10,  # 레버리지 10x로 제한
                    'urgency': 'high'
                })
                
            elif margin_level <= self.margin_levels['warning']:
                # 경고 수준: 좋지 않은 포지션 일부 청산 계획
                actions.append({
                    'action': 'reduce_positions',
                    'percentage': 0.1,  # 10% 포지션 촐정
                    'target': 'worst_performing',
                    'urgency': 'medium'
                })
                
            return actions
        
        except Exception as e:
            logger.error(f"위험 감소 조치 제안 중 오류: {e}")
            return [{'action': 'manual_check', 'urgency': 'medium'}]
    
    def implement_trailing_stop(self, current_price, position, activation_pct=0.01, trail_pct=0.02):
        """
        트레일링 스탑 구현
        
        Args:
            current_price (float): 현재 가격
            position (dict): 포지션 정보
            activation_pct (float): 트레일링 스탑 활성화 비율
            trail_pct (float): 트레일링 스탑 비율
        
        Returns:
            tuple: (업데이트된 포지션, 트레일링 스탑 발동 여부)
        """
        try:
            # 포지션 복사
            updated_position = position.copy()
            triggered = False
            
            # 트레일링 스탑 정보가 없으면 초기화
            if 'trailing_stop' not in updated_position:
                updated_position['trailing_stop'] = {
                    'activated': False,
                    'activation_price': 0,
                    'stop_price': 0
                }
            
            # 롱 포지션
            if updated_position['side'].lower() == 'long':
                # 활성화 가격 계산
                activation_price = updated_position['entry_price'] * (1 + activation_pct)
                
                # 트레일링 스탑이 아직 활성화되지 않은 경우
                if not updated_position['trailing_stop']['activated']:
                    # 현재 가격이 활성화 가격 이상이면 트레일링 스탑 활성화
                    if current_price >= activation_price:
                        updated_position['trailing_stop']['activated'] = True
                        updated_position['trailing_stop']['activation_price'] = activation_price
                        updated_position['trailing_stop']['stop_price'] = current_price * (1 - trail_pct)
                        logger.info(f"롱 포지션 트레일링 스탑 활성화: 현재가={current_price}, 스탑가={updated_position['trailing_stop']['stop_price']}")
                
                # 트레일링 스탑이 이미 활성화된 경우
                else:
                    # 현재 가격이 기존 최고가보다 높으면 스탑 가격 업데이트
                    if current_price > updated_position['trailing_stop']['stop_price'] / (1 - trail_pct):
                        updated_position['trailing_stop']['stop_price'] = current_price * (1 - trail_pct)
                        logger.info(f"롱 포지션 트레일링 스탑 업데이트: 현재가={current_price}, 스탑가={updated_position['trailing_stop']['stop_price']}")
                    
                    # 현재 가격이 스탑 가격 이하로 떨어지면 트레일링 스탑 발동
                    if current_price <= updated_position['trailing_stop']['stop_price']:
                        updated_position['exit_reason'] = 'trailing_stop'
                        triggered = True
                        logger.info(f"롱 포지션 트레일링 스탑 발동: 현재가={current_price}, 스탑가={updated_position['trailing_stop']['stop_price']}")
            
            # 숏 포지션
            elif updated_position['side'].lower() == 'short':
                # 활성화 가격 계산
                activation_price = updated_position['entry_price'] * (1 - activation_pct)
                
                # 트레일링 스탑이 아직 활성화되지 않은 경우
                if not updated_position['trailing_stop']['activated']:
                    # 현재 가격이 활성화 가격 이하이면 트레일링 스탑 활성화
                    if current_price <= activation_price:
                        updated_position['trailing_stop']['activated'] = True
                        updated_position['trailing_stop']['activation_price'] = activation_price
                        updated_position['trailing_stop']['stop_price'] = current_price * (1 + trail_pct)
                        logger.info(f"숏 포지션 트레일링 스탑 활성화: 현재가={current_price}, 스탑가={updated_position['trailing_stop']['stop_price']}")
                
                # 트레일링 스탑이 이미 활성화된 경우
                else:
                    # 현재 가격이 기존 최저가보다 낮으면 스탑 가격 업데이트
                    if current_price < updated_position['trailing_stop']['stop_price'] / (1 + trail_pct):
                        updated_position['trailing_stop']['stop_price'] = current_price * (1 + trail_pct)
                        logger.info(f"숏 포지션 트레일링 스탑 업데이트: 현재가={current_price}, 스탑가={updated_position['trailing_stop']['stop_price']}")
                    
                    # 현재 가격이 스탑 가격 이상으로 올라가면 트레일링 스탑 발동
                    if current_price >= updated_position['trailing_stop']['stop_price']:
                        updated_position['exit_reason'] = 'trailing_stop'
                        triggered = True
                        logger.info(f"숏 포지션 트레일링 스탑 발동: 현재가={current_price}, 스탑가={updated_position['trailing_stop']['stop_price']}")
            
            return updated_position, triggered
        
        except Exception as e:
            logger.error(f"트레일링 스탑 구현 중 오류 발생: {e}")
            return position, False
    
    def calculate_kelly_criterion(self, win_rate, win_loss_ratio):
        """
        켈리 기준 계산
        
        Args:
            win_rate (float): 승률 (0~1)
            win_loss_ratio (float): 승리 시 이익 / 패배 시 손실
        
        Returns:
            float: 켈리 비율
        """
        try:
            # 켈리 기준 공식: f* = (p * b - q) / b
            # p: 승률, q: 패률 (1-p), b: 승리 시 이익 / 패배 시 손실
            
            if win_rate <= 0 or win_rate >= 1:
                logger.warning(f"승률은 0과 1 사이여야 합니다: {win_rate}")
                return 0
            
            if win_loss_ratio <= 0:
                logger.warning(f"승패 비율은 0보다 커야 합니다: {win_loss_ratio}")
                return 0
            
            kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
            
            # 음수인 경우 0 반환
            if kelly < 0:
                logger.info(f"켈리 비율이 음수입니다. 투자하지 않는 것이 좋습니다: {kelly}")
                return 0
            
            # 켈리 비율의 절반만 사용 (보수적 접근)
            half_kelly = kelly / 2
            
            logger.info(f"켈리 비율 계산: 승률={win_rate}, 승패비율={win_loss_ratio}, 켈리비율={kelly}, 절반켈리={half_kelly}")
            return half_kelly
        
        except Exception as e:
            logger.error(f"켈리 기준 계산 중 오류 발생: {e}")
            return 0
    
    def calculate_max_drawdown(self, balance_history):
        """
        최대 낙폭 계산
        
        Args:
            balance_history (list): 잔고 기록
        
        Returns:
            tuple: (최대 낙폭 비율, 최대 낙폭 시작 인덱스, 최대 낙폭 종료 인덱스)
        """
        try:
            if not balance_history:
                logger.warning("잔고 기록이 없어 최대 낙폭을 계산할 수 없습니다.")
                return 0, 0, 0
            
            # 누적 최대값 계산
            peak = balance_history[0]
            max_drawdown = 0
            max_drawdown_start = 0
            max_drawdown_end = 0
            
            for i, balance in enumerate(balance_history):
                # 새로운 최고점 갱신
                if balance > peak:
                    peak = balance
                
                # 현재 낙폭 계산
                drawdown = (peak - balance) / peak
                
                # 최대 낙폭 갱신
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                    max_drawdown_end = i
                    
                    # 최대 낙폭 시작점 찾기
                    for j in range(i, -1, -1):
                        if balance_history[j] == peak:
                            max_drawdown_start = j
                            break
            
            logger.info(f"최대 낙폭 계산: {max_drawdown:.2%}")
            return max_drawdown, max_drawdown_start, max_drawdown_end
        
        except Exception as e:
            logger.error(f"최대 낙폭 계산 중 오류 발생: {e}")
            return 0, 0, 0
    
    def check_risk_limits(self, portfolio, current_price):
        """
        위험 한도 확인
        
        Args:
            portfolio (dict): 포트폴리오 정보
            current_price (float): 현재 가격
        
        Returns:
            tuple: (위험 한도 초과 여부, 경고 메시지)
        """
        try:
            warnings = []
            risk_exceeded = False
            
            # 일일 손실 한도 확인
            if 'daily_loss_limit' in self.risk_config and 'daily_pl' in portfolio:
                daily_loss = portfolio['daily_pl']
                daily_loss_limit = portfolio['initial_balance'] * self.risk_config['daily_loss_limit']
                
                if daily_loss < -daily_loss_limit:
                    risk_exceeded = True
                    warning = f"일일 손실 한도 초과: 현재 손실={daily_loss:.2f}, 한도={daily_loss_limit:.2f}"
                    warnings.append(warning)
                    logger.warning(warning)
            
            # 총 손실 한도 확인
            if 'max_loss_limit' in self.risk_config:
                initial_balance = portfolio['initial_balance']
                current_balance = portfolio['quote_balance'] + portfolio['base_balance'] * current_price
                total_loss = current_balance - initial_balance
                max_loss_limit = initial_balance * self.risk_config['max_loss_limit']
                
                if total_loss < -max_loss_limit:
                    risk_exceeded = True
                    warning = f"총 손실 한도 초과: 현재 손실={total_loss:.2f}, 한도={max_loss_limit:.2f}"
                    warnings.append(warning)
                    logger.warning(warning)
            
            # 최대 포지션 수 확인
            if 'max_positions' in self.risk_config:
                open_positions = [p for p in portfolio['positions'] if p['status'] == 'open']
                max_positions = self.risk_config['max_positions']
                
                if len(open_positions) > max_positions:
                    risk_exceeded = True
                    warning = f"최대 포지션 수 초과: 현재 포지션 수={len(open_positions)}, 한도={max_positions}"
                    warnings.append(warning)
                    logger.warning(warning)
            
            # 최대 포지션 크기 확인
            if 'max_position_size' in self.risk_config:
                open_positions = [p for p in portfolio['positions'] if p['status'] == 'open']
                max_position_size = portfolio['quote_balance'] * self.risk_config['max_position_size']
                
                for position in open_positions:
                    position_value = position['quantity'] * current_price
                    if position_value > max_position_size:
                        risk_exceeded = True
                        warning = f"최대 포지션 크기 초과: 포지션 가치={position_value:.2f}, 한도={max_position_size:.2f}"
                        warnings.append(warning)
                        logger.warning(warning)
            
            return risk_exceeded, warnings
        
        except Exception as e:
            logger.error(f"위험 한도 확인 중 오류 발생: {e}")
            return False, []
    
    def send_alert(self, subject, message, alert_type='all'):
        """
        알림 전송 - NotificationService 사용
        
        Args:
            subject (str): 알림 제목
            message (str): 알림 내용
            alert_type (str): 알림 유형 ('email', 'telegram', 'all')
        
        Returns:
            bool: 전송 성공 여부
        """
        try:
            # NotificationService를 통한 알림 전송
            return self.notification_service.send_alert(subject, message, alert_type)
        except Exception as e:
            logger.error(f"알림 전송 중 오류 발생: {e}")
            return False
    
    def log_risk_event(self, event_type, event_data):
        """
        위험 이벤트 로깅
        
        Args:
            event_type (str): 이벤트 유형
            event_data (dict): 이벤트 데이터
        """
        try:
            # 로그 파일 경로
            log_file = os.path.join(self.log_dir, f"risk_events_{datetime.now().strftime('%Y%m%d')}.json")
            
            # 이벤트 데이터 준비
            event = {
                'timestamp': datetime.now().isoformat(),
                'type': event_type,
                'symbol': self.symbol,
                'data': event_data
            }
            
            # 기존 로그 파일이 있으면 읽기
            events = []
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    try:
                        events = json.load(f)
                    except json.JSONDecodeError:
                        events = []
            
            # 새 이벤트 추가
            events.append(event)
            
            # 로그 파일 저장
            with open(log_file, 'w') as f:
                json.dump(events, f, indent=4)
            
            logger.info(f"위험 이벤트 로깅 완료: {event_type}")
        
        except Exception as e:
            logger.error(f"위험 이벤트 로깅 중 오류 발생: {e}")
    
    def monitor_volatility(self, price_history, window=20, threshold=2.0):
        """
        변동성 모니터링
        
        Args:
            price_history (list): 가격 기록
            window (int): 변동성 계산 기간
            threshold (float): 변동성 임계값
        
        Returns:
            tuple: (높은 변동성 여부, 변동성 값)
        """
        try:
            if len(price_history) < window:
                logger.warning(f"변동성 계산을 위한 데이터가 부족합니다: {len(price_history)} < {window}")
                return False, 0
            
            # 최근 가격 데이터
            recent_prices = price_history[-window:]
            
            # 일일 수익률 계산
            returns = [recent_prices[i] / recent_prices[i-1] - 1 for i in range(1, len(recent_prices))]
            
            # 변동성 계산 (수익률의 표준편차)
            volatility = np.std(returns) * (252 ** 0.5)  # 연간 변동성으로 변환
            
            # 높은 변동성 여부
            high_volatility = volatility > threshold
            
            if high_volatility:
                logger.warning(f"높은 변동성 감지: {volatility:.4f} > {threshold}")
            
            return high_volatility, volatility
        
        except Exception as e:
            logger.error(f"변동성 모니터링 중 오류 발생: {e}")
            return False, 0
    
    def adjust_risk_based_on_volatility(self, volatility, base_risk_per_trade):
        """
        변동성에 따른 위험 조정
        
        Args:
            volatility (float): 현재 변동성
            base_risk_per_trade (float): 기본 거래당 위험 비율
        
        Returns:
            float: 조정된 거래당 위험 비율
        """
        try:
            # 변동성 기준값
            base_volatility = self.risk_config.get('base_volatility', 0.2)
            
            # 변동성 비율
            volatility_ratio = volatility / base_volatility
            
            # 위험 조정 (변동성이 높을수록 위험 감소)
            adjusted_risk = base_risk_per_trade / volatility_ratio
            
            # 최소 및 최대 위험 제한
            min_risk = self.risk_config.get('min_risk_per_trade', 0.001)
            max_risk = self.risk_config.get('max_risk_per_trade', 0.02)
            
            adjusted_risk = max(min_risk, min(adjusted_risk, max_risk))
            
            logger.info(f"변동성에 따른 위험 조정: 기본위험={base_risk_per_trade}, 변동성={volatility:.4f}, 조정위험={adjusted_risk:.4f}")
            return adjusted_risk
        
        except Exception as e:
            logger.error(f"변동성에 따른 위험 조정 중 오류 발생: {e}")
            return base_risk_per_trade
    
    def check_market_conditions(self, df, lookback_period=20):
        """
        시장 상황 확인
        
        Args:
            df (DataFrame): OHLCV 데이터
            lookback_period (int): 확인 기간
        
        Returns:
            dict: 시장 상황 정보
        """
        try:
            if len(df) < lookback_period:
                logger.warning(f"시장 상황 확인을 위한 데이터가 부족합니다: {len(df)} < {lookback_period}")
                return {'trend': 'unknown', 'volatility': 'unknown', 'volume': 'unknown'}
            
            # 최근 데이터
            recent_df = df.tail(lookback_period)
            
            # 추세 확인
            price_change = (recent_df['close'].iloc[-1] / recent_df['close'].iloc[0] - 1) * 100
            if price_change > 5:
                trend = 'strong_uptrend'
            elif price_change > 2:
                trend = 'uptrend'
            elif price_change < -5:
                trend = 'strong_downtrend'
            elif price_change < -2:
                trend = 'downtrend'
            else:
                trend = 'sideways'
            
            # 변동성 확인
            returns = recent_df['close'].pct_change().dropna()
            volatility = returns.std() * (252 ** 0.5) * 100  # 연간 변동성 (%)
            
            if volatility > 80:
                volatility_status = 'extreme'
            elif volatility > 50:
                volatility_status = 'high'
            elif volatility > 30:
                volatility_status = 'moderate'
            else:
                volatility_status = 'low'
            
            # 거래량 확인
            avg_volume = recent_df['volume'].mean()
            recent_volume = recent_df['volume'].iloc[-1]
            volume_ratio = recent_volume / avg_volume
            
            if volume_ratio > 2:
                volume_status = 'very_high'
            elif volume_ratio > 1.5:
                volume_status = 'high'
            elif volume_ratio < 0.5:
                volume_status = 'low'
            else:
                volume_status = 'normal'
            
            market_conditions = {
                'trend': trend,
                'price_change': price_change,
                'volatility': volatility_status,
                'volatility_value': volatility,
                'volume': volume_status,
                'volume_ratio': volume_ratio
            }
            
            logger.info(f"시장 상황 확인: {market_conditions}")
            return market_conditions
        
        except Exception as e:
            logger.error(f"시장 상황 확인 중 오류 발생: {e}")
            return {'trend': 'unknown', 'volatility': 'unknown', 'volume': 'unknown'}
    
    def adjust_strategy_parameters(self, strategy, market_conditions):
        """
        시장 상황에 따른 전략 파라미터 조정
        
        Args:
            strategy: 거래 전략 객체
            market_conditions (dict): 시장 상황 정보
        
        Returns:
            object: 조정된 전략 객체
        """
        try:
            # 전략 유형 확인
            strategy_type = type(strategy).__name__
            
            # 시장 추세
            trend = market_conditions['trend']
            volatility = market_conditions['volatility']
            
            # 이동평균 교차 전략 조정
            if strategy_type == 'MovingAverageCrossover':
                if trend in ['strong_uptrend', 'strong_downtrend']:
                    # 강한 추세에서는 빠른 이동평균 사용
                    strategy.short_period = max(5, strategy.short_period - 2)
                    strategy.long_period = max(15, strategy.long_period - 5)
                elif trend == 'sideways':
                    # 횡보 시장에서는 긴 이동평균 사용
                    strategy.short_period = min(12, strategy.short_period + 2)
                    strategy.long_period = min(30, strategy.long_period + 5)
                
                logger.info(f"이동평균 교차 전략 파라미터 조정: short_period={strategy.short_period}, long_period={strategy.long_period}")
            
            # RSI 전략 조정
            elif strategy_type == 'RSIStrategy':
                if volatility == 'high' or volatility == 'extreme':
                    # 높은 변동성에서는 RSI 범위 확장
                    strategy.overbought = min(80, strategy.overbought + 5)
                    strategy.oversold = max(20, strategy.oversold - 5)
                else:
                    # 낮은 변동성에서는 RSI 범위 축소
                    strategy.overbought = max(65, strategy.overbought - 5)
                    strategy.oversold = min(35, strategy.oversold + 5)
                
                logger.info(f"RSI 전략 파라미터 조정: overbought={strategy.overbought}, oversold={strategy.oversold}")
            
            # 볼린저 밴드 전략 조정
            elif strategy_type == 'BollingerBandsStrategy':
                if volatility == 'high' or volatility == 'extreme':
                    # 높은 변동성에서는 표준편차 증가
                    strategy.std_dev = min(3.0, strategy.std_dev + 0.5)
                else:
                    # 낮은 변동성에서는 표준편차 감소
                    strategy.std_dev = max(1.5, strategy.std_dev - 0.5)
                
                logger.info(f"볼린저 밴드 전략 파라미터 조정: std_dev={strategy.std_dev}")
            
            return strategy
        
        except Exception as e:
            logger.error(f"전략 파라미터 조정 중 오류 발생: {e}")
            return strategy

# 테스트 코드
if __name__ == "__main__":
    # 위험 관리자 초기화
    risk_manager = RiskManager(exchange_id='binance', symbol='BTC/USDT')
    
    # 포지션 크기 계산 테스트
    position_size = risk_manager.calculate_position_size(
        account_balance=10000,
        current_price=50000,
        risk_per_trade=0.01
    )
    print(f"계산된 포지션 크기: {position_size} BTC")
    
    # 손절매 및 이익실현 가격 계산 테스트
    entry_price = 50000
    stop_loss_price = risk_manager.calculate_stop_loss_price(entry_price, 'long')
    take_profit_price = risk_manager.calculate_take_profit_price(entry_price, 'long')
    
    print(f"롱 포지션 - 진입가: {entry_price}, 손절매가: {stop_loss_price}, 이익실현가: {take_profit_price}")
    
    # 위험 대비 보상 비율 계산 테스트
    risk_reward_ratio = risk_manager.calculate_risk_reward_ratio(entry_price, stop_loss_price, take_profit_price)
    print(f"위험 대비 보상 비율: {risk_reward_ratio:.2f}")
    
    # 켈리 기준 계산 테스트
    kelly_fraction = risk_manager.calculate_kelly_criterion(win_rate=0.6, win_loss_ratio=2.0)
    print(f"켈리 비율: {kelly_fraction:.4f}")
    
    # 변동성 모니터링 테스트
    price_history = [50000, 51000, 52000, 51500, 51800, 52500, 53000, 52800, 52600, 52900,
                     53500, 54000, 53800, 53600, 53900, 54200, 54500, 54300, 54100, 54400]
    high_volatility, volatility = risk_manager.monitor_volatility(price_history)
    print(f"변동성: {volatility:.4f}, 높은 변동성: {high_volatility}")
    
    # 변동성에 따른 위험 조정 테스트
    adjusted_risk = risk_manager.adjust_risk_based_on_volatility(volatility, 0.01)
    print(f"조정된 위험 비율: {adjusted_risk:.4f}")
    
    # 트레일링 스탑 테스트
    position = {
        'entry_time': '2024-04-10T12:00:00',
        'entry_price': 50000,
        'quantity': 0.1,
        'side': 'long',
        'status': 'open'
    }
    
    # 가격 상승 시뮬레이션
    current_price = 52000  # 4% 상승
    updated_position, triggered = risk_manager.implement_trailing_stop(current_price, position)
    print(f"트레일링 스탑 테스트 (가격: {current_price}) - 발동: {triggered}")
    
    if not triggered and updated_position['trailing_stop']['activated']:
        print(f"트레일링 스탑 활성화 - 스탑가: {updated_position['trailing_stop']['stop_price']}")
        
        # 가격 하락 시뮬레이션
        current_price = updated_position['trailing_stop']['stop_price'] - 100
        updated_position, triggered = risk_manager.implement_trailing_stop(current_price, updated_position)
        print(f"트레일링 스탑 테스트 (가격: {current_price}) - 발동: {triggered}")
        
        if triggered:
            print(f"트레일링 스탑 발동 - 종료 이유: {updated_position['exit_reason']}")
