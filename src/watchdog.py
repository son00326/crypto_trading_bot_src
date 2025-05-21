#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 시스템 감시 및 자동 재시작 모듈

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
from typing import Dict, Any, Optional, List, Tuple, Callable

from src.logging_config import get_logger
from src.config import DATA_DIR

class HeartbeatMonitor:
    """
    심박(Heartbeat) 모니터링 시스템
    
    봇 프로세스가 정상적으로 동작하는지 주기적으로 확인하고
    응답이 없을 경우 알림 또는 복구 조치를 수행합니다.
    """
    
    def __init__(self, heartbeat_interval: int = 30, max_missed_beats: int = 3):
        """
        HeartbeatMonitor 초기화
        
        Args:
            heartbeat_interval: 심박 확인 간격 (초)
            max_missed_beats: 재시작 전 허용되는 최대 누락 심박 수
        """
        self.logger = get_logger('heartbeat_monitor')
        self.heartbeat_interval = heartbeat_interval
        self.max_missed_beats = max_missed_beats
        self.monitoring = False
        self.monitor_thread = None
        
        # 심박 파일 경로
        self.heartbeat_dir = os.path.join(DATA_DIR, 'system_health')
        os.makedirs(self.heartbeat_dir, exist_ok=True)
        self.heartbeat_file = os.path.join(self.heartbeat_dir, 'heartbeat.json')
        
        # 상태 저장
        self.missed_beats = 0
        self.last_heartbeat_time = None
        self.recovery_attempts = 0
        self.recovery_timestamps = []
        
        self.logger.info("심박 모니터링 시스템 초기화 완료")
    
    def record_heartbeat(self) -> bool:
        """
        현재 시간으로 심박 기록 갱신
        
        Returns:
            bool: 성공 여부
        """
        try:
            current_time = datetime.now()
            
            heartbeat_data = {
                'timestamp': current_time.isoformat(),
                'status': 'active',
                'pid': os.getpid(),
                'uptime': self._get_process_uptime()
            }
            
            # 심박 파일에 기록
            with open(self.heartbeat_file, 'w') as f:
                json.dump(heartbeat_data, f, indent=2)
            
            return True
        except Exception as e:
            self.logger.error(f"심박 기록 중 오류: {e}")
            return False
    
    def _get_process_uptime(self) -> int:
        """
        현재 프로세스 실행 시간 계산 (초)
        
        Returns:
            int: 프로세스 실행 시간 (초)
        """
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return int(time.time() - process.create_time())
        except Exception:
            return 0
    
    def check_heartbeat(self) -> Tuple[bool, Optional[datetime]]:
        """
        최근 심박 기록 확인
        
        Returns:
            Tuple[bool, Optional[datetime]]: (심박 정상 여부, 마지막 심박 시간)
        """
        try:
            if not os.path.exists(self.heartbeat_file):
                self.logger.warning("심박 파일이 존재하지 않습니다.")
                return False, None
            
            # 파일 수정 시간 확인
            file_mtime = datetime.fromtimestamp(os.path.getmtime(self.heartbeat_file))
            current_time = datetime.now()
            time_diff = (current_time - file_mtime).total_seconds()
            
            # 심박 데이터 확인
            with open(self.heartbeat_file, 'r') as f:
                heartbeat_data = json.load(f)
            
            timestamp_str = heartbeat_data.get('timestamp')
            if not timestamp_str:
                return False, None
            
            # 타임스탬프 파싱
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%f")
            
            # 시간 차이 계산
            time_diff = (current_time - timestamp).total_seconds()
            
            # 허용 간격보다 오래되었으면 비정상으로 판단
            is_valid = time_diff <= (self.heartbeat_interval * 2)
            return is_valid, timestamp
        
        except Exception as e:
            self.logger.error(f"심박 확인 중 오류: {e}")
            return False, None
    
    def start_monitoring(self):
        """심박 모니터링 시작"""
        if self.monitoring:
            self.logger.warning("이미 모니터링 중입니다.")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        self.logger.info(f"심박 모니터링 시작 (간격: {self.heartbeat_interval}초)")
    
    def stop_monitoring(self):
        """심박 모니터링 중지"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        
        self.logger.info("심박 모니터링 중지")
    
    def _monitoring_loop(self):
        """심박 모니터링 메인 루프"""
        while self.monitoring:
            try:
                is_valid, timestamp = self.check_heartbeat()
                
                if is_valid:
                    # 정상 심박 감지
                    self.missed_beats = 0
                    self.last_heartbeat_time = timestamp
                else:
                    # 심박 누락
                    self.missed_beats += 1
                    self.logger.warning(f"심박 누락 감지 ({self.missed_beats}/{self.max_missed_beats})")
                    
                    if self.missed_beats >= self.max_missed_beats:
                        self.logger.critical(f"연속 {self.missed_beats}회 심박 누락. 복구 조치 필요.")
                        # 여기서 복구 조치를 호출할 예정 (다음 단계에서 구현)
                        self.missed_beats = 0
            
            except Exception as e:
                self.logger.error(f"모니터링 루프 오류: {e}")
            
            # 다음 확인까지 대기
            time.sleep(self.heartbeat_interval)

# 테스트 코드
if __name__ == "__main__":
    # 간단한 테스트
    monitor = HeartbeatMonitor(heartbeat_interval=5)
    
    # 심박 기록 테스트
    monitor.record_heartbeat()
    
    # 심박 확인 테스트
    is_valid, timestamp = monitor.check_heartbeat()
    print(f"심박 상태: {'정상' if is_valid else '비정상'}, 시간: {timestamp}")
    
    # 모니터링 시작 (테스트 목적)
    monitor.start_monitoring()
    
    try:
        # 몇 초 동안 심박 계속 기록
        for _ in range(5):
            time.sleep(2)
            monitor.record_heartbeat()
            print("심박 기록됨")
        
        # 심박 중단 시뮬레이션
        print("심박 중단 시뮬레이션 (10초)")
        time.sleep(10)
        
        # 다시 심박 기록
        monitor.record_heartbeat()
        print("심박 재개")
        time.sleep(5)
        
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop_monitoring()
        print("테스트 완료")
