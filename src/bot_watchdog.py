#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 봇 감시자(Watchdog) 시스템

import os
import sys
import time
import json
import signal
import logging
import threading
import subprocess
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Callable, Union

from src.logging_config import get_logger
from src.config import DATA_DIR, PROJECT_ROOT
from src.watchdog import HeartbeatMonitor
from src.recovery_manager import RecoveryManager

class BotWatchdog:
    """
    봇 감시자(Watchdog) 시스템
    
    HeartbeatMonitor와 RecoveryManager를 통합하여
    봇의 안정적인 실행을 보장하는 감시 시스템입니다.
    """
    
    def __init__(
        self, 
        bot_script_path: str,
        bot_args: Optional[List[str]] = None,
        heartbeat_interval: int = 30,
        max_missed_beats: int = 3,
        max_recovery_attempts: int = 5,
        cooldown_period: int = 3600
    ):
        """
        BotWatchdog 초기화
        
        Args:
            bot_script_path: 봇 메인 스크립트 경로
            bot_args: 봇 실행 인수
            heartbeat_interval: 심박 확인 간격 (초)
            max_missed_beats: 재시작 전 허용되는 최대 누락 심박 수
            max_recovery_attempts: 특정 기간 내 최대 복구 시도 횟수
            cooldown_period: 복구 시도 제한 재설정 기간 (초)
        """
        self.logger = get_logger('bot_watchdog')
        self.bot_script_path = bot_script_path
        self.bot_args = bot_args or []
        
        # 컴포넌트 초기화
        self.heartbeat_monitor = HeartbeatMonitor(
            heartbeat_interval=heartbeat_interval,
            max_missed_beats=max_missed_beats
        )
        
        self.recovery_manager = RecoveryManager(
            max_recovery_attempts=max_recovery_attempts,
            cooldown_period=cooldown_period
        )
        
        # 감시 상태
        self.watching = False
        self.watch_thread = None
        self.bot_process = None
        self.last_restart_time = None
        self.restart_count = 0
        
        # 봇 프로세스 상태
        self.bot_status = "unknown"
        
        # 감시자 디렉토리
        self.watchdog_dir = os.path.join(DATA_DIR, 'watchdog')
        os.makedirs(self.watchdog_dir, exist_ok=True)
        self.watchdog_status_file = os.path.join(self.watchdog_dir, 'watchdog_status.json')
        
        self.logger.info("봇 감시자(Watchdog) 초기화 완료")
    
    def record_heartbeat(self) -> bool:
        """
        현재 봇 상태의 심박 기록
        
        봇 프로세스에서 주기적으로 호출해야 합니다.
        
        Returns:
            bool: 성공 여부
        """
        return self.heartbeat_monitor.record_heartbeat()
    
    def save_bot_state(self, state_data: Dict[str, Any]) -> bool:
        """
        봇 상태 정보 저장
        
        Returns:
            bool: 성공 여부
        """
        return self.recovery_manager.save_bot_state(state_data)
    
    def load_bot_state(self) -> Optional[Dict[str, Any]]:
        """
        저장된 봇 상태 정보 로드
        
        Returns:
            Optional[Dict[str, Any]]: 봇 상태 또는 None
        """
        return self.recovery_manager.load_bot_state()
    
    def start_bot(self) -> bool:
        """
        봇 프로세스 시작
        
        Returns:
            bool: 성공 여부
        """
        try:
            self.logger.info(f"봇 프로세스 시작: {self.bot_script_path}")
            
            # 경로 확인
            if not os.path.exists(self.bot_script_path):
                raise FileNotFoundError(f"봇 스크립트를 찾을 수 없습니다: {self.bot_script_path}")
            
            # 명령행 인수 준비
            cmd_args = [sys.executable, self.bot_script_path] + self.bot_args
            
            # 봇 프로세스 시작
            self.bot_process = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            self.bot_status = "starting"
            self.last_restart_time = datetime.now()
            self.restart_count += 1
            
            self.logger.info(f"봇 프로세스가 시작되었습니다 (PID: {self.bot_process.pid})")
            return True
            
        except Exception as e:
            self.logger.error(f"봇 시작 중 오류: {e}")
            self.logger.debug(traceback.format_exc())
            self.bot_status = "error"
            return False
    
    def restart_bot(self) -> bool:
        """
        봇 프로세스 재시작
        
        Returns:
            bool: 성공 여부
        """
        try:
            self.logger.info("봇 재시작 시도")
            
            # 기존 프로세스 종료
            if self.bot_process:
                try:
                    self.bot_status = "stopping"
                    # SIGTERM 신호 전송 후 잠시 대기
                    self.bot_process.terminate()
                    self.bot_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 강제 종료
                    self.logger.warning("봇 종료 시간 초과, 강제 종료합니다")
                    self.bot_process.kill()
            
            # 봇 재시작
            success = self.start_bot()
            
            # 재시작 기록
            self.recovery_manager.log_recovery_attempt(
                reason="봇 감시자에 의한 재시작",
                success=success,
                details={
                    'restart_count': self.restart_count,
                    'script': self.bot_script_path,
                    'args': self.bot_args
                }
            )
            
            return success
            
        except Exception as e:
            self.logger.error(f"봇 재시작 중 오류: {e}")
            self.logger.debug(traceback.format_exc())
            self.bot_status = "error"
            return False
    
    def start_watching(self) -> bool:
        """
        봇 감시 시작
        
        Returns:
            bool: 성공 여부
        """
        if self.watching:
            self.logger.warning("이미 감시 중입니다")
            return False
        
        self.watching = True
        
        # 심박 모니터링 시작
        self.heartbeat_monitor.start_monitoring()
        
        # 감시 스레드 시작
        self.watch_thread = threading.Thread(target=self._watching_loop)
        self.watch_thread.daemon = True
        self.watch_thread.start()
        
        self.logger.info("봇 감시 시작")
        
        # 봇 프로세스가 없으면 시작
        if not self.bot_process or self.bot_process.poll() is not None:
            self.start_bot()
            
        return True
    
    def stop_watching(self) -> bool:
        """
        봇 감시 중지
        
        Returns:
            bool: 성공 여부
        """
        if not self.watching:
            return False
        
        self.watching = False
        
        # 심박 모니터링 중지
        self.heartbeat_monitor.stop_monitoring()
        
        # 감시 스레드 종료 대기
        if self.watch_thread and self.watch_thread.is_alive():
            self.watch_thread.join(timeout=2.0)
        
        self.logger.info("봇 감시 중지")
        return True
    
    def _watching_loop(self):
        """봇 감시 메인 루프"""
        while self.watching:
            try:
                # 심박 확인
                is_valid, timestamp = self.heartbeat_monitor.check_heartbeat()
                
                # 봇 프로세스 상태 확인
                if self.bot_process:
                    return_code = self.bot_process.poll()
                    
                    # 프로세스가 종료됨
                    if return_code is not None:
                        self.logger.warning(f"봇 프로세스가 종료되었습니다 (반환 코드: {return_code})")
                        self.bot_status = "crashed"
                        
                        # 복구 가능 여부 확인
                        if self.recovery_manager.can_attempt_recovery():
                            self.logger.info("봇 복구 시도")
                            self.restart_bot()
                        else:
                            self.logger.error("최대 복구 시도 횟수를 초과하여 복구를 중단합니다")
                            self.bot_status = "failed"
                    else:
                        # 프로세스는 실행 중이지만 심박이 없음
                        if not is_valid:
                            self.logger.warning("봇 프로세스는 실행 중이지만 심박이 없습니다")
                            self.bot_status = "unresponsive"
                            
                            # 연속된 심박 누락 횟수 확인
                            if self.heartbeat_monitor.missed_beats >= self.heartbeat_monitor.max_missed_beats:
                                self.logger.warning("연속 심박 누락 한계 초과, 봇 재시작")
                                self.restart_bot()
                        else:
                            # 정상 상태
                            self.bot_status = "running"
                else:
                    # 봇 프로세스가 없음
                    self.logger.warning("봇 프로세스가 없습니다")
                    self.bot_status = "not_running"
                    
                    # 봇 시작
                    if self.recovery_manager.can_attempt_recovery():
                        self.start_bot()
                
                # 상태 저장
                self._save_watchdog_status()
                
            except Exception as e:
                self.logger.error(f"감시 루프 오류: {e}")
                self.logger.debug(traceback.format_exc())
            
            # 다음 확인까지 대기
            time.sleep(5)
    
    def _save_watchdog_status(self):
        """감시자 상태 저장"""
        try:
            status_data = {
                'timestamp': datetime.now().isoformat(),
                'bot_status': self.bot_status,
                'bot_pid': self.bot_process.pid if self.bot_process else None,
                'restart_count': self.restart_count,
                'last_restart': self.last_restart_time.isoformat() if self.last_restart_time else None,
                'watchdog_pid': os.getpid()
            }
            
            with open(self.watchdog_status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"감시자 상태 저장 중 오류: {e}")

# 봇 실행 데몬
def run_watchdog(bot_script_path, bot_args=None, daemonize=True):
    """
    봇 감시자 실행 헬퍼 함수
    
    Args:
        bot_script_path: 봇 메인 스크립트 경로
        bot_args: 봇 실행 인수
        daemonize: 데몬으로 실행할지 여부
    
    Returns:
        감시자 인스턴스
    """
    # 감시자 인스턴스 생성
    watchdog = BotWatchdog(
        bot_script_path=bot_script_path,
        bot_args=bot_args or []
    )
    
    # 데몬으로 실행할 경우
    if daemonize:
        # 현재 스크립트 재실행
        current_script = os.path.abspath(__file__)
        
        # 명령행 인수 준비
        args = [
            sys.executable,
            current_script,
            '--daemon',
            '--script', bot_script_path
        ]
        
        if bot_args:
            args.extend(['--args'] + bot_args)
        
        # 데몬 프로세스 시작
        daemon_process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        print(f"감시자 데몬이 시작되었습니다 (PID: {daemon_process.pid})")
        return watchdog
    
    # 직접 실행
    try:
        watchdog.start_watching()
        return watchdog
    except KeyboardInterrupt:
        watchdog.stop_watching()
        return watchdog

# 메인 실행 코드
if __name__ == "__main__":
    import argparse
    
    # 명령행 인수 파싱
    parser = argparse.ArgumentParser(description='암호화폐 봇 감시자')
    parser.add_argument('--daemon', action='store_true', help='데몬으로 실행')
    parser.add_argument('--script', type=str, help='봇 스크립트 경로')
    parser.add_argument('--args', nargs='*', help='봇 실행 인수')
    
    args = parser.parse_args()
    
    # 기본 스크립트 경로
    bot_script = args.script
    if not bot_script:
        bot_script = os.path.join(PROJECT_ROOT, 'main.py')
    
    # 감시자 생성 및 실행
    watchdog = BotWatchdog(
        bot_script_path=bot_script,
        bot_args=args.args or []
    )
    
    # 데몬 모드인 경우
    if args.daemon:
        print(f"데몬 모드로 감시자 실행 중 (PID: {os.getpid()})")
        watchdog.start_watching()
        
        try:
            # 무한 실행
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
        finally:
            watchdog.stop_watching()
    else:
        # 대화형 모드
        print("감시자 테스트 모드")
        
        # 봇 감시 시작
        watchdog.start_watching()
        
        try:
            print("Ctrl+C로 종료")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            watchdog.stop_watching()
            print("감시자 종료")
