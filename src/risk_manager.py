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
    
    def __init__(self, exchange_id='binance', symbol='BTC/USDT', risk_config=None):
        """
        위험 관리자 초기화
        
        Args:
            exchange_id (str): 거래소 ID
            symbol (str): 거래 심볼
            risk_config (dict, optional): 위험 관리 설정
        """
        self.exchange_id = exchange_id
        self.symbol = symbol
        
        # 위험 관리 설정
        self.risk_config = risk_config if risk_config else RISK_MANAGEMENT.copy()
        
        # 로그 디렉토리
        self.log_dir = os.path.join(DATA_DIR, 'risk_logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 알림 설정
        self.email_config = EMAIL_CONFIG.copy() if 'EMAIL_CONFIG' in globals() else None
        self.telegram_config = TELEGRAM_CONFIG.copy() if 'TELEGRAM_CONFIG' in globals() else None
        
        logger.info(f"{exchange_id} 거래소의 {symbol} 위험 관리자가 초기화되었습니다.")
        logger.info(f"위험 관리 설정: {self.risk_config}")
    
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
        try:
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
        
        except Exception as e:
            logger.error(f"위험 대비 보상 비율 계산 중 오류 발생: {e}")
            return 0
    
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
    
    def send_email_alert(self, subject, message):
        """
        이메일 알림 전송
        
        Args:
            subject (str): 이메일 제목
            message (str): 이메일 내용
        
        Returns:
            bool: 전송 성공 여부
        """
        try:
            if not self.email_config:
                logger.warning("이메일 설정이 없어 알림을 전송할 수 없습니다.")
                return False
            
            # 이메일 설정
            sender_email = self.email_config['sender_email']
            receiver_email = self.email_config['receiver_email']
            password = self.email_config['password']
            smtp_server = self.email_config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = self.email_config.get('smtp_port', 587)
            
            # 이메일 메시지 생성
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = receiver_email
            msg['Subject'] = f"[암호화폐 봇 알림] {subject}"
            
            # 메시지 본문 추가
            msg.attach(MIMEText(message, 'plain'))
            
            # SMTP 서버 연결 및 이메일 전송
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, password)
                server.send_message(msg)
            
            logger.info(f"이메일 알림 전송 완료: {subject}")
            return True
        
        except Exception as e:
            logger.error(f"이메일 알림 전송 중 오류 발생: {e}")
            return False
    
    def send_telegram_alert(self, message):
        """
        텔레그램 알림 전송
        
        Args:
            message (str): 알림 메시지
        
        Returns:
            bool: 전송 성공 여부
        """
        try:
            if not self.telegram_config:
                logger.warning("텔레그램 설정이 없어 알림을 전송할 수 없습니다.")
                return False
            
            # 텔레그램 설정
            bot_token = self.telegram_config['bot_token']
            chat_id = self.telegram_config['chat_id']
            
            # 텔레그램 API URL
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            # 요청 데이터
            data = {
                'chat_id': chat_id,
                'text': f"[암호화폐 봇 알림]\n{message}",
                'parse_mode': 'Markdown'
            }
            
            # 요청 전송
            response = requests.post(url, data=data)
            
            # 응답 확인
            if response.status_code == 200:
                logger.info("텔레그램 알림 전송 완료")
                return True
            else:
                logger.warning(f"텔레그램 알림 전송 실패: {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"텔레그램 알림 전송 중 오류 발생: {e}")
            return False
    
    def send_alert(self, subject, message, alert_type='all'):
        """
        알림 전송
        
        Args:
            subject (str): 알림 제목
            message (str): 알림 내용
            alert_type (str): 알림 유형 ('email', 'telegram', 'all')
        
        Returns:
            bool: 전송 성공 여부
        """
        try:
            success = False
            
            if alert_type in ['email', 'all'] and self.email_config:
                email_success = self.send_email_alert(subject, message)
                success = success or email_success
            
            if alert_type in ['telegram', 'all'] and self.telegram_config:
                telegram_success = self.send_telegram_alert(message)
                success = success or telegram_success
            
            return success
        
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
