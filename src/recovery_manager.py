#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 시스템 복구 관리자

import os
import sys
import time
import json
import signal
import logging
import subprocess
import traceback
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Callable, Union

from src.logging_config import get_logger
from src.config import DATA_DIR

class RecoveryManager:
    """
    시스템 복구 관리자
    
    봇 충돌 또는 비정상 상태를 감지하고 자동 복구 작업을 수행합니다.
    1. 상태 저장 및 로드
    2. 봇 프로세스 재시작
    3. 복구 시도 로깅
    """
    
    def __init__(self, max_recovery_attempts: int = 5, cooldown_period: int = 3600):
        """
        RecoveryManager 초기화
        
        Args:
            max_recovery_attempts: 특정 기간 내 최대 복구 시도 횟수
            cooldown_period: 복구 시도 제한 재설정 기간 (초)
        """
        self.logger = get_logger('recovery_manager')
        self.max_recovery_attempts = max_recovery_attempts
        self.cooldown_period = cooldown_period
        
        # 복구 기록 디렉토리
        self.recovery_dir = os.path.join(DATA_DIR, 'recovery')
        os.makedirs(self.recovery_dir, exist_ok=True)
        
        # 복구 기록 파일
        self.recovery_log_file = os.path.join(self.recovery_dir, 'recovery_log.json')
        self.state_file = os.path.join(self.recovery_dir, 'bot_state.json')
        
        # 복구 상태 데이터
        self.recovery_attempts = 0
        self.last_recovery_time = None
        self.recovery_history = []
        
        # 기존 복구 로그 로드
        self._load_recovery_log()
        
        self.logger.info("복구 관리자 초기화 완료")
    
    def _load_recovery_log(self):
        """기존 복구 로그 로드"""
        try:
            if os.path.exists(self.recovery_log_file):
                with open(self.recovery_log_file, 'r') as f:
                    recovery_data = json.load(f)
                
                # 최근 복구 시도 횟수 계산
                current_time = datetime.now()
                recent_attempts = [
                    attempt for attempt in recovery_data.get('history', [])
                    if current_time - datetime.fromisoformat(attempt['timestamp']) < timedelta(seconds=self.cooldown_period)
                ]
                
                self.recovery_attempts = len(recent_attempts)
                if recent_attempts:
                    self.last_recovery_time = datetime.fromisoformat(recent_attempts[-1]['timestamp'])
                
                self.recovery_history = recovery_data.get('history', [])
                
                self.logger.info(f"복구 로그 로드 완료: 최근 시도 {self.recovery_attempts}회")
        except Exception as e:
            self.logger.error(f"복구 로그 로드 중 오류: {e}")
            self.logger.debug(traceback.format_exc())
    
    def _save_recovery_log(self):
        """현재 복구 로그 저장"""
        try:
            recovery_data = {
                'last_updated': datetime.now().isoformat(),
                'total_attempts': len(self.recovery_history),
                'recent_attempts': self.recovery_attempts,
                'history': self.recovery_history
            }
            
            with open(self.recovery_log_file, 'w') as f:
                json.dump(recovery_data, f, indent=2)
                
            self.logger.debug("복구 로그 저장 완료")
        except Exception as e:
            self.logger.error(f"복구 로그 저장 중 오류: {e}")
    
    def save_bot_state(self, state_data: Dict[str, Any]) -> bool:
        """
        봇 상태 정보 저장
        
        Args:
            state_data: 저장할 봇 상태 데이터
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 현재 시간 추가
            state_data['saved_at'] = datetime.now().isoformat()
            state_data['pid'] = os.getpid()
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            return True
        except Exception as e:
            self.logger.error(f"봇 상태 저장 중 오류: {e}")
            return False
    
    def load_bot_state(self) -> Optional[Dict[str, Any]]:
        """
        저장된 봇 상태 정보 로드
        
        Returns:
            Optional[Dict[str, Any]]: 봇 상태 데이터 또는 None (오류 시)
        """
        try:
            if not os.path.exists(self.state_file):
                self.logger.warning("저장된 봇 상태 파일이 없습니다.")
                return None
            
            with open(self.state_file, 'r') as f:
                state_data = json.load(f)
            
            self.logger.info(f"봇 상태 로드 완료 (저장 시간: {state_data.get('saved_at')})")
            return state_data
        except Exception as e:
            self.logger.error(f"봇 상태 로드 중 오류: {e}")
            return None
    
    def can_attempt_recovery(self) -> bool:
        """
        복구 시도 가능 여부 확인
        
        Returns:
            bool: 복구 시도 가능 여부
        """
        # 최대 시도 횟수 초과 여부 확인
        if self.recovery_attempts >= self.max_recovery_attempts:
            # 마지막 복구 시도 이후 쿨다운 기간이 지났는지 확인
            if self.last_recovery_time:
                time_since_last = (datetime.now() - self.last_recovery_time).total_seconds()
                if time_since_last < self.cooldown_period:
                    self.logger.warning(
                        f"최대 복구 시도 횟수 초과. 다음 시도까지 {(self.cooldown_period - time_since_last) / 60:.1f}분 남음"
                    )
                    return False
            
            # 쿨다운 기간이 지났으면 카운터 리셋
            self.recovery_attempts = 0
        
        return True
    
    def log_recovery_attempt(self, reason: str, success: bool, details: Optional[Dict[str, Any]] = None) -> None:
        """
        복구 시도 기록
        
        Args:
            reason: 복구 시도 이유
            success: 성공 여부
            details: 추가 상세 정보
        """
        current_time = datetime.now()
        
        # 복구 기록 추가
        recovery_entry = {
            'timestamp': current_time.isoformat(),
            'reason': reason,
            'success': success,
            'details': details or {}
        }
        
        self.recovery_history.append(recovery_entry)
        self.recovery_attempts += 1
        self.last_recovery_time = current_time
        
        # 로그 저장
        self._save_recovery_log()
        
        # 로그 메시지
        status = "성공" if success else "실패"
        self.logger.info(f"복구 시도 ({status}): {reason}")
    
    def restart_bot(self, script_path: str, args: Optional[List[str]] = None) -> bool:
        """
        봇 프로세스 재시작
        
        Args:
            script_path: 시작 스크립트 경로
            args: 추가 명령행 인수
            
        Returns:
            bool: 성공 여부
        """
        if not self.can_attempt_recovery():
            return False
        
        try:
            self.logger.info(f"봇 재시작 시도: {script_path}")
            
            # 현재 프로세스 ID 저장
            current_pid = os.getpid()
            
            # 명령행 인수 준비
            cmd_args = [sys.executable, script_path]
            if args:
                cmd_args.extend(args)
            
            # 새 프로세스 시작
            subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True  # 새 세션에서 실행 (부모와 독립)
            )
            
            # 재시작 시도 기록
            self.log_recovery_attempt(
                reason="봇 프로세스 재시작",
                success=True,
                details={
                    'script': script_path,
                    'args': args,
                    'parent_pid': current_pid
                }
            )
            
            return True
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"봇 재시작 중 오류: {error_msg}")
            
            # 실패 기록
            self.log_recovery_attempt(
                reason="봇 프로세스 재시작",
                success=False,
                details={
                    'script': script_path,
                    'args': args,
                    'error': error_msg
                }
            )
            
            return False
    
    def emergency_shutdown(self, reason: str) -> None:
        """
        응급 상황에서 안전하게 종료
        
        Args:
            reason: 종료 이유
        """
        self.logger.critical(f"응급 종료 실행: {reason}")
        
        # 종료 상태 기록
        shutdown_state = {
            'status': 'emergency_shutdown',
            'reason': reason,
            'timestamp': datetime.now().isoformat(),
            'pid': os.getpid()
        }
        
        # 상태 저장
        self.save_bot_state(shutdown_state)
        
        # 종료 기록
        self.log_recovery_attempt(
            reason=f"응급 종료: {reason}",
            success=True
        )
        
        # 프로세스 종료
        sys.exit(1)

# 테스트 코드
if __name__ == "__main__":
    # 간단한 테스트
    recovery = RecoveryManager(max_recovery_attempts=3, cooldown_period=60)
    
    # 상태 저장
    test_state = {
        'mode': 'test',
        'balance': 1000.0,
        'positions': []
    }
    recovery.save_bot_state(test_state)
    
    # 상태 로드
    loaded_state = recovery.load_bot_state()
    print(f"로드된 상태: {loaded_state}")
    
    # 복구 가능 여부 확인
    can_recover = recovery.can_attempt_recovery()
    print(f"복구 가능 여부: {can_recover}")
    
    # 테스트: 여러 번 복구 시도
    for i in range(4):
        recovery.log_recovery_attempt(
            reason=f"테스트 복구 #{i+1}",
            success=True,
            details={'test_run': True}
        )
        can_recover = recovery.can_attempt_recovery()
        print(f"복구 시도 #{i+1} 후 복구 가능 여부: {can_recover}")
    
    # 참고: 실제 재시작 테스트는 위험하므로 구현만 확인
    print("재시작 코드 구현 확인 완료")
