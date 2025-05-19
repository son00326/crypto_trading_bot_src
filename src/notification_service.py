"""
알림 서비스 모듈 - 암호화폐 자동매매 봇

이 모듈은 다양한 알림 채널(이메일, 텔레그램 등)을 통합하여 알림을 전송하는 기능을 제공합니다.
"""

import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.config import EMAIL_CONFIG, TELEGRAM_CONFIG

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('notification_service')

class NotificationService:
    """알림 서비스 클래스"""
    
    def __init__(self, email_config=None, telegram_config=None):
        """
        알림 서비스 초기화
        
        Args:
            email_config (dict, optional): 이메일 설정
            telegram_config (dict, optional): 텔레그램 설정
        """
        # 이메일 설정
        self.email_config = email_config if email_config else EMAIL_CONFIG.copy() if 'EMAIL_CONFIG' in globals() else None
        
        # 텔레그램 설정
        self.telegram_config = telegram_config if telegram_config else TELEGRAM_CONFIG.copy() if 'TELEGRAM_CONFIG' in globals() else None
        
        logger.info("알림 서비스가 초기화되었습니다.")
        
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
