#!/usr/bin/env python3
"""
봇 자동 재시작 기능 모듈

서버 재시작 시 이전 실행 중이던 봇을 자동으로 재시작합니다.
"""

import os
import sys
import time
import logging
import json
from datetime import datetime

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot_api_server import BotAPIServer
from src.db_manager import DBManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('auto_restart')

class BotAutoRestarter:
    """봇 자동 재시작 관리 클래스"""
    
    def __init__(self, db_path='crypto_bot.db'):
        self.db_path = db_path
        self.db_manager = DBManager(db_path)
    
    def check_previous_state(self):
        """이전 봇 상태 확인"""
        try:
            # 데이터베이스에서 마지막 봇 상태 조회
            saved_state = self.db_manager.load_bot_state()
            
            if not saved_state:
                logger.info("저장된 봇 상태가 없습니다.")
                return None
            
            # 봇이 실행 중이었는지 확인
            was_running = saved_state.get('is_running', False)
            if not was_running:
                logger.info("이전에 봇이 실행 중이지 않았습니다.")
                return None
            
            # 마지막 업데이트 시간 확인 (24시간 이내인지)
            last_update = saved_state.get('updated_at')
            if last_update:
                from datetime import datetime, timedelta
                last_update_time = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                if datetime.now() - last_update_time > timedelta(hours=24):
                    logger.warning("마지막 업데이트가 24시간 이상 지났습니다. 자동 재시작을 건너뜁니다.")
                    return None
            
            logger.info(f"이전 실행 상태 발견: {saved_state['exchange_id']} - {saved_state['symbol']}")
            return saved_state
            
        except Exception as e:
            logger.error(f"이전 상태 확인 중 오류: {e}")
            return None
    
    def restart_bot(self, saved_state):
        """봇 재시작"""
        try:
            logger.info("봇 자동 재시작을 시작합니다...")
            
            # BotAPIServer 초기화
            bot_server = BotAPIServer(port=5000)
            
            # 저장된 설정으로 봇 시작
            start_params = {
                'exchange_id': saved_state.get('exchange_id', 'binance'),
                'symbol': saved_state.get('symbol', 'BTC/USDT'),
                'timeframe': saved_state.get('timeframe', '1h'),
                'strategy': saved_state.get('strategy', 'ma_crossover'),
                'market_type': saved_state.get('market_type', 'futures'),
                'leverage': saved_state.get('leverage', 1),
                'test_mode': saved_state.get('test_mode', True),
                'strategy_params': saved_state.get('strategy_params', saved_state.get('parameters', {}))
            }
            
            # 추가 설정이 있으면 포함
            additional_info = saved_state.get('additional_info')
            if additional_info:
                if isinstance(additional_info, str):
                    additional_info = json.loads(additional_info)
                
                start_params.update({
                    'stop_loss': additional_info.get('stop_loss', 2.0),
                    'take_profit': additional_info.get('take_profit', 5.0),
                    'max_position': additional_info.get('max_position', 1000),
                    'auto_sl_tp': additional_info.get('auto_sl_tp', True),
                    'partial_tp': additional_info.get('partial_tp', False)
                })
            
            # 봇 시작
            logger.info(f"봇 재시작 파라미터: {json.dumps(start_params, indent=2)}")
            
            # 봇 GUI 시작
            success = bot_server.start_bot_with_settings(start_params)
            
            if success:
                logger.info("✅ 봇이 성공적으로 재시작되었습니다!")
                
                # 재시작 로그 저장
                restart_log = {
                    'timestamp': datetime.now().isoformat(),
                    'reason': 'auto_restart',
                    'previous_state': saved_state,
                    'result': 'success'
                }
                self.save_restart_log(restart_log)
                
                return True
            else:
                logger.error("봇 재시작 실패")
                return False
                
        except Exception as e:
            logger.error(f"봇 재시작 중 오류: {e}", exc_info=True)
            
            # 오류 로그 저장
            error_log = {
                'timestamp': datetime.now().isoformat(),
                'reason': 'auto_restart',
                'previous_state': saved_state,
                'result': 'error',
                'error': str(e)
            }
            self.save_restart_log(error_log)
            
            return False
    
    def save_restart_log(self, log_data):
        """재시작 로그 저장"""
        try:
            log_file = 'bot_restart_log.json'
            
            # 기존 로그 읽기
            logs = []
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            
            # 새 로그 추가
            logs.append(log_data)
            
            # 최근 100개만 유지
            logs = logs[-100:]
            
            # 저장
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
                
        except Exception as e:
            logger.error(f"로그 저장 실패: {e}")
    
    def enable_auto_restart(self):
        """자동 재시작 활성화 (systemd 서비스 등록)"""
        service_content = """[Unit]
Description=Crypto Trading Bot Auto Restart
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={working_dir}
ExecStart=/usr/bin/python3 {script_path}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        try:
            # 서비스 파일 내용 생성
            import getpass
            service_file = service_content.format(
                user=getpass.getuser(),
                working_dir=os.path.dirname(os.path.abspath(__file__)),
                script_path=os.path.abspath(__file__)
            )
            
            # 서비스 파일 경로
            service_path = '/etc/systemd/system/crypto-bot-auto-restart.service'
            
            print(f"다음 내용을 {service_path}에 저장하세요:")
            print("-" * 60)
            print(service_file)
            print("-" * 60)
            print("\n그리고 다음 명령어를 실행하세요:")
            print("sudo systemctl daemon-reload")
            print("sudo systemctl enable crypto-bot-auto-restart")
            print("sudo systemctl start crypto-bot-auto-restart")
            
        except Exception as e:
            logger.error(f"서비스 설정 생성 실패: {e}")

def main():
    """메인 함수"""
    logger.info("봇 자동 재시작 프로세스 시작...")
    
    # 자동 재시작 관리자 초기화
    restarter = BotAutoRestarter()
    
    # 명령행 인수 확인
    if len(sys.argv) > 1:
        if sys.argv[1] == '--enable':
            # systemd 서비스 활성화 안내
            restarter.enable_auto_restart()
            return
        elif sys.argv[1] == '--check':
            # 상태만 확인
            state = restarter.check_previous_state()
            if state:
                print(f"이전 봇 상태: {json.dumps(state, indent=2)}")
            else:
                print("저장된 봇 상태가 없습니다.")
            return
    
    # 이전 상태 확인
    saved_state = restarter.check_previous_state()
    
    if saved_state:
        # 잠시 대기 (네트워크 등이 완전히 준비될 때까지)
        logger.info("10초 후 봇을 재시작합니다...")
        time.sleep(10)
        
        # 봇 재시작
        success = restarter.restart_bot(saved_state)
        
        if success:
            logger.info("자동 재시작 완료!")
        else:
            logger.error("자동 재시작 실패!")
            sys.exit(1)
    else:
        logger.info("재시작할 봇 상태가 없습니다.")

if __name__ == "__main__":
    main()
