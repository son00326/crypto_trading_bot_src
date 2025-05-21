#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 메모리 사용량 모니터링 모듈

import os
import sys
import time
import psutil
import gc
import logging
import threading
import traceback
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Tuple

from src.logging_config import get_logger
from src.config import DATA_DIR

class MemoryMonitor:
    """
    메모리 사용량 모니터링 및 관리 클래스
    
    시스템 및 프로세스의 메모리 사용량을 추적하고,
    메모리 사용이 임계값을 초과할 경우 경고 또는 조치를 취합니다.
    """
    
    def __init__(
        self, 
        check_interval: int = 60,
        warning_threshold_percent: float = 75.0,
        critical_threshold_percent: float = 90.0,
        auto_cleanup: bool = True
    ):
        """
        MemoryMonitor 초기화
        
        Args:
            check_interval: 메모리 확인 간격 (초)
            warning_threshold_percent: 경고 임계값 (전체 메모리의 %)
            critical_threshold_percent: 위험 임계값 (전체 메모리의 %)
            auto_cleanup: 임계값 초과 시 자동 정리 여부
        """
        self.logger = get_logger('memory_monitor')
        self.check_interval = check_interval
        self.warning_threshold = warning_threshold_percent
        self.critical_threshold = critical_threshold_percent
        self.auto_cleanup = auto_cleanup
        
        # 모니터링 상태
        self.monitoring = False
        self.monitor_thread = None
        
        # 메모리 사용 기록
        self.memory_history = []
        self.max_history_size = 1000  # 최대 1000개 기록 유지
        
        # 로그 디렉토리
        self.log_dir = os.path.join(DATA_DIR, 'memory_logs')
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, f'memory_log_{datetime.now().strftime("%Y%m%d")}.json')
        
        # 현재 프로세스
        self.process = psutil.Process(os.getpid())
        
        # 청소 콜백 함수 (외부에서 등록 가능)
        self.cleanup_callbacks = []
        
        # 시스템 정보 기록
        self.system_info = self._get_system_info()
        
        self.logger.info("메모리 모니터링 시스템 초기화 완료")
        self.logger.info(f"시스템 정보: 총 메모리 {self.system_info['total_memory_mb']:.1f}MB, "
                         f"CPU {self.system_info['cpu_count']}코어")
    
    def _get_system_info(self) -> Dict[str, Any]:
        """
        시스템 정보 수집
        
        Returns:
            Dict[str, Any]: 시스템 정보
        """
        return {
            'total_memory_mb': psutil.virtual_memory().total / (1024 * 1024),
            'cpu_count': psutil.cpu_count(),
            'platform': sys.platform,
            'python_version': sys.version
        }
    
    def start_monitoring(self):
        """메모리 모니터링 시작"""
        if self.monitoring:
            self.logger.warning("이미 모니터링 중입니다.")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        self.logger.info(f"메모리 모니터링 시작 (간격: {self.check_interval}초)")
    
    def stop_monitoring(self):
        """메모리 모니터링 중지"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        
        # 로그 저장
        self._save_memory_log()
        
        self.logger.info("메모리 모니터링 중지")
    
    def _monitoring_loop(self):
        """메모리 모니터링 메인 루프"""
        while self.monitoring:
            try:
                # 현재 메모리 사용량 확인
                memory_info = self._get_memory_info()
                
                # 메모리 사용량 기록
                self._record_memory_usage(memory_info)
                
                # 임계값 확인
                self._check_thresholds(memory_info)
                
                # 로그 주기적 저장 (매 10분)
                if datetime.now().minute % 10 == 0 and datetime.now().second < 10:
                    self._save_memory_log()
                
                # 다음 확인까지 대기
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"메모리 모니터링 중 오류: {e}")
                self.logger.debug(traceback.format_exc())
                time.sleep(5)  # 오류 발생 시 짧게 대기
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """
        메모리 사용량 정보 수집
        
        Returns:
            Dict[str, Any]: 메모리 사용량 정보
        """
        # 시스템 메모리 정보
        system_memory = psutil.virtual_memory()
        
        # 현재 프로세스 메모리 정보
        process_memory = self.process.memory_info()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'system': {
                'total_mb': system_memory.total / (1024 * 1024),
                'available_mb': system_memory.available / (1024 * 1024),
                'used_mb': system_memory.used / (1024 * 1024),
                'percent': system_memory.percent
            },
            'process': {
                'rss_mb': process_memory.rss / (1024 * 1024),  # 실제 물리 메모리 사용량
                'vms_mb': process_memory.vms / (1024 * 1024),  # 가상 메모리 사용량
                'percent': self.process.memory_percent()
            }
        }
    
    def _record_memory_usage(self, memory_info: Dict[str, Any]):
        """
        메모리 사용량 기록
        
        Args:
            memory_info: 메모리 사용량 정보
        """
        self.memory_history.append(memory_info)
        
        # 최대 기록 크기 제한
        if len(self.memory_history) > self.max_history_size:
            self.memory_history = self.memory_history[-self.max_history_size:]
    
    def _check_thresholds(self, memory_info: Dict[str, Any]):
        """
        메모리 임계값 확인 및 조치
        
        Args:
            memory_info: 메모리 사용량 정보
        """
        system_percent = memory_info['system']['percent']
        process_percent = memory_info['process']['percent']
        
        # 시스템 메모리 임계값 확인
        if system_percent >= self.critical_threshold:
            self.logger.critical(
                f"시스템 메모리 사용량 위험 수준: {system_percent:.1f}% "
                f"(프로세스: {process_percent:.1f}%)"
            )
            
            if self.auto_cleanup:
                self._perform_emergency_cleanup()
                
        elif system_percent >= self.warning_threshold:
            self.logger.warning(
                f"시스템 메모리 사용량 경고 수준: {system_percent:.1f}% "
                f"(프로세스: {process_percent:.1f}%)"
            )
            
            if self.auto_cleanup:
                self._perform_cleanup()
        
        # 프로세스 메모리 사용량 로깅 (디버그)
        else:
            self.logger.debug(
                f"메모리 사용량: 시스템 {system_percent:.1f}%, "
                f"프로세스 {process_percent:.1f}% "
                f"(RSS: {memory_info['process']['rss_mb']:.1f}MB)"
            )
    
    def _perform_cleanup(self):
        """
        메모리 정리 작업 수행
        """
        self.logger.info("메모리 정리 작업 시작...")
        
        # 가비지 컬렉션 수행
        collected = gc.collect()
        self.logger.info(f"가비지 컬렉션 수행: {collected}개 객체 정리")
        
        # 등록된 콜백 함수 실행
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                self.logger.error(f"메모리 정리 콜백 실행 중 오류: {e}")
    
    def _perform_emergency_cleanup(self):
        """
        긴급 메모리 정리 작업 수행
        """
        self.logger.warning("긴급 메모리 정리 작업 시작...")
        
        # 일반 정리 작업 수행
        self._perform_cleanup()
        
        # 추가 긴급 조치
        try:
            # 강제 가비지 컬렉션 (여러 세대)
            for i in range(3):
                collected = gc.collect(i)
                self.logger.info(f"세대 {i} 가비지 컬렉션: {collected}개 객체 정리")
            
            # 미사용 메모리 시스템에 반환 요청 (플랫폼에 따라 다름)
            if hasattr(gc, 'malloc_trim'):  # PyPy에만 존재
                gc.malloc_trim()
            
        except Exception as e:
            self.logger.error(f"긴급 메모리 정리 중 오류: {e}")
    
    def register_cleanup_callback(self, callback: Callable[[], None]):
        """
        메모리 정리 콜백 함수 등록
        
        Args:
            callback: 메모리 정리 시 호출할 함수
        """
        if callback not in self.cleanup_callbacks:
            self.cleanup_callbacks.append(callback)
            self.logger.info(f"메모리 정리 콜백 등록: {callback.__name__}")
    
    def unregister_cleanup_callback(self, callback: Callable[[], None]):
        """
        메모리 정리 콜백 함수 등록 해제
        
        Args:
            callback: 등록 해제할 콜백 함수
        """
        if callback in self.cleanup_callbacks:
            self.cleanup_callbacks.remove(callback)
            self.logger.info(f"메모리 정리 콜백 등록 해제: {callback.__name__}")
    
    def _save_memory_log(self):
        """메모리 사용 기록 저장"""
        try:
            # 로그 파일명 (날짜별)
            current_date = datetime.now().strftime("%Y%m%d")
            self.log_file = os.path.join(self.log_dir, f'memory_log_{current_date}.json')
            
            # 이전 로그 불러오기
            previous_logs = []
            if os.path.exists(self.log_file):
                try:
                    with open(self.log_file, 'r') as f:
                        previous_logs = json.load(f)
                except:
                    # 파일이 손상되었을 경우 새로 시작
                    pass
            
            # 로그 데이터 준비 (중복 방지)
            existing_timestamps = {log.get('timestamp') for log in previous_logs}
            new_logs = [
                log for log in self.memory_history 
                if log.get('timestamp') not in existing_timestamps
            ]
            
            # 저장할 로그 (이전 + 새로운 로그)
            all_logs = previous_logs + new_logs
            
            # 최대 크기 제한
            max_logs = 10000  # 최대 10000개 로그 저장
            if len(all_logs) > max_logs:
                all_logs = all_logs[-max_logs:]
            
            # 저장
            with open(self.log_file, 'w') as f:
                json.dump(all_logs, f)
            
            self.logger.debug(f"메모리 로그 저장 완료: {len(new_logs)}개 항목 추가")
            
        except Exception as e:
            self.logger.error(f"메모리 로그 저장 중 오류: {e}")
    
    def get_memory_usage_summary(self) -> Dict[str, Any]:
        """
        최근 메모리 사용량 요약 정보 반환
        
        Returns:
            Dict[str, Any]: 메모리 사용량 요약 정보
        """
        if not self.memory_history:
            return {
                'current': None,
                'average': None,
                'max': None,
                'trend': 'unknown'
            }
        
        # 현재 사용량
        current = self.memory_history[-1]
        
        # 최근 10개 기록 (또는 전체)
        recent_count = min(10, len(self.memory_history))
        recent_records = self.memory_history[-recent_count:]
        
        # 평균 사용량
        avg_system = sum(r['system']['percent'] for r in recent_records) / recent_count
        avg_process = sum(r['process']['percent'] for r in recent_records) / recent_count
        
        # 최대 사용량
        max_system = max(r['system']['percent'] for r in recent_records)
        max_process = max(r['process']['percent'] for r in recent_records)
        
        # 추세 분석 (상승/하락/유지)
        if recent_count >= 3:
            first_half = recent_records[:recent_count//2]
            second_half = recent_records[recent_count//2:]
            
            avg_first = sum(r['process']['percent'] for r in first_half) / len(first_half)
            avg_second = sum(r['process']['percent'] for r in second_half) / len(second_half)
            
            diff = avg_second - avg_first
            if diff > 5.0:
                trend = 'increasing'
            elif diff < -5.0:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'unknown'
        
        return {
            'current': {
                'system_percent': current['system']['percent'],
                'process_percent': current['process']['percent'],
                'process_rss_mb': current['process']['rss_mb'],
                'timestamp': current['timestamp']
            },
            'average': {
                'system_percent': avg_system,
                'process_percent': avg_process
            },
            'max': {
                'system_percent': max_system,
                'process_percent': max_process
            },
            'trend': trend
        }
    
    def force_cleanup(self):
        """
        강제 메모리 정리 수행
        """
        self.logger.info("강제 메모리 정리 요청")
        self._perform_cleanup()
        
        # 정리 후 메모리 정보 기록
        memory_info = self._get_memory_info()
        self._record_memory_usage(memory_info)
        
        return {
            'success': True,
            'current_usage': {
                'system_percent': memory_info['system']['percent'],
                'process_percent': memory_info['process']['percent'],
                'process_rss_mb': memory_info['process']['rss_mb']
            }
        }

# 전역 메모리 모니터 인스턴스
memory_monitor = None

def get_memory_monitor():
    """
    전역 메모리 모니터 인스턴스 반환
    
    Returns:
        MemoryMonitor: 메모리 모니터 인스턴스
    """
    global memory_monitor
    if memory_monitor is None:
        memory_monitor = MemoryMonitor()
    return memory_monitor

# 테스트 코드
if __name__ == "__main__":
    # 간단한 테스트
    monitor = MemoryMonitor(check_interval=5)
    monitor.start_monitoring()
    
    try:
        # 메모리 사용 테스트
        print("메모리 사용량 테스트 시작...")
        large_list = []
        
        for i in range(10):
            # 메모리 사용 증가
            print(f"메모리 사용 증가 ({i+1}/10)...")
            large_list.extend([0] * 1000000)  # 약 8MB 증가
            time.sleep(3)
        
        # 메모리 사용량 확인
        summary = monitor.get_memory_usage_summary()
        print(f"메모리 사용량 요약:\n{json.dumps(summary, indent=2)}")
        
        # 강제 정리
        print("메모리 정리 실행...")
        result = monitor.force_cleanup()
        print(f"정리 결과: {result}")
        
        # 메모리 해제
        print("대용량 리스트 해제...")
        large_list = None
        time.sleep(5)
        
        # 최종 상태 확인
        summary = monitor.get_memory_usage_summary()
        print(f"최종 메모리 사용량:\n{json.dumps(summary, indent=2)}")
        
    except KeyboardInterrupt:
        print("\n테스트 중단")
    finally:
        monitor.stop_monitoring()
        print("모니터링 종료")
