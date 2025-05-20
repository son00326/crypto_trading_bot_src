#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 시스템 상태 모니터링 모듈

import logging
import time
import threading
import traceback
import os
import psutil
import json
from datetime import datetime, timedelta

from src.logging_config import get_logger
from src.error_handlers import error_analyzer

class SystemHealthMonitor:
    """시스템 상태 감시 및 복구 클래스"""
    
    def __init__(self, check_interval=60):
        """
        시스템 상태 감시자 초기화
        
        Args:
            check_interval (int): 상태 확인 간격 (초)
        """
        self.logger = get_logger('system_health')
        self.check_interval = check_interval
        self.running = False
        self.monitor_thread = None
        self.component_statuses = {}
        self.recovery_actions = {}
        self.last_check_time = {}
        self.health_stats = {
            'consecutive_failures': {},
            'recovery_attempts': {},
        }
        
        # 상태 히스토리 기록
        from src.config import DATA_DIR
        self.log_dir = os.path.join(DATA_DIR, 'system_health')
        os.makedirs(self.log_dir, exist_ok=True)
        self.status_history_path = os.path.join(self.log_dir, 'status_history.json')
        self.status_history = self._load_status_history()
    
    def _load_status_history(self):
        """상태 히스토리 로드"""
        try:
            if os.path.exists(self.status_history_path):
                with open(self.status_history_path, 'r') as f:
                    return json.load(f)
            return {'components': {}, 'recoveries': [], 'last_updated': None}
        except Exception as e:
            self.logger.error(f"상태 히스토리 로드 실패: {e}")
            return {'components': {}, 'recoveries': [], 'last_updated': None}
    
    def _save_status_history(self):
        """상태 히스토리 저장"""
        try:
            self.status_history['last_updated'] = datetime.now().isoformat()
            with open(self.status_history_path, 'w') as f:
                json.dump(self.status_history, f, indent=2)
        except Exception as e:
            self.logger.error(f"상태 히스토리 저장 실패: {e}")
    
    def register_component(self, component_name, check_function, recovery_function=None,
                          custom_interval=None, max_consecutive_failures=3):
        """
        감시할 컴포넌트 등록
        
        Args:
            component_name (str): 컴포넌트 이름
            check_function (callable): 상태 확인 함수
            recovery_function (callable, optional): 복구 함수
            custom_interval (int, optional): 커스텀 확인 간격
            max_consecutive_failures (int): 최대 연속 실패 횟수
        """
        self.component_statuses[component_name] = {
            'status': 'unknown',
            'last_check': None,
            'check_function': check_function,
            'custom_interval': custom_interval,
            'max_consecutive_failures': max_consecutive_failures
        }
        
        if recovery_function:
            self.recovery_actions[component_name] = recovery_function
        
        self.health_stats['consecutive_failures'][component_name] = 0
        self.health_stats['recovery_attempts'][component_name] = 0
        
        # 상태 히스토리에 컴포넌트 추가
        if component_name not in self.status_history['components']:
            self.status_history['components'][component_name] = {
                'status_changes': [],
                'total_failures': 0,
                'total_recoveries': 0
            }
        
        self.logger.info(f"컴포넌트 등록됨: {component_name}")
    
    def start_monitoring(self):
        """상태 감시 시작"""
        if self.running:
            self.logger.warning("상태 감시가 이미 실행 중입니다.")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        self.logger.info(f"시스템 상태 감시 시작 (확인 간격: {self.check_interval}초)")
    
    def stop_monitoring(self):
        """상태 감시 중지"""
        if not self.running:
            self.logger.warning("상태 감시가 이미 중지되었습니다.")
            return
        
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        
        self.logger.info("시스템 상태 감시 중지")
    
    def _monitoring_loop(self):
        """상태 감시 루프"""
        while self.running:
            try:
                current_time = time.time()
                
                # 각 컴포넌트 확인
                for component_name, component_info in self.component_statuses.items():
                    # 확인 간격 설정
                    interval = component_info['custom_interval'] or self.check_interval
                    last_check = self.last_check_time.get(component_name, 0)
                    
                    # 확인 시간이 되었는지 확인
                    if current_time - last_check >= interval:
                        self._check_component(component_name)
                
                # 시스템 자원 상태 기록
                self._check_system_resources()
                
                # 다음 확인까지 대기
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"상태 감시 루프 오류: {e}")
                self.logger.debug(traceback.format_exc())
                time.sleep(5)  # 오류 발생 시 짧게 대기
    
    def _check_component(self, component_name):
        """
        컴포넌트 상태 확인
        
        Args:
            component_name (str): 확인할 컴포넌트 이름
        """
        try:
            component_info = self.component_statuses[component_name]
            self.last_check_time[component_name] = time.time()
            
            # 상태 확인 함수 호출
            check_result = component_info['check_function']()
            
            # 상태 업데이트
            prev_status = component_info['status']
            component_info['status'] = 'healthy' if check_result else 'unhealthy'
            component_info['last_check'] = datetime.now().isoformat()
            
            # 상태 변경 기록
            if prev_status != component_info['status']:
                self._record_status_change(component_name, prev_status, component_info['status'])
            
            # 건강한 상태인 경우 연속 실패 카운터 리셋
            if check_result:
                self.health_stats['consecutive_failures'][component_name] = 0
                
                # 상태가 복구된 경우 로그
                if prev_status == 'unhealthy':
                    self.logger.info(f"컴포넌트 '{component_name}'이(가) 복구되었습니다.")
                    
                    # 오류 분석기에 로그
                    if 'error_analyzer' in globals():
                        error_analyzer.log_error(
                            'component_recovery',
                            f"컴포넌트 '{component_name}' 자동 복구됨",
                            {'component': component_name, 'prev_status': prev_status}
                        )
            else:
                # 연속 실패 카운터 증가
                self.health_stats['consecutive_failures'][component_name] += 1
                consecutive_failures = self.health_stats['consecutive_failures'][component_name]
                
                # 상태 히스토리 업데이트
                self.status_history['components'][component_name]['total_failures'] += 1
                self._save_status_history()
                
                # 상태가 불량한 경우 로그
                if prev_status != 'unhealthy':
                    self.logger.warning(f"컴포넌트 '{component_name}'이(가) 불량 상태입니다.")
                else:
                    self.logger.warning(f"컴포넌트 '{component_name}'이(가) 계속 불량 상태입니다 (연속 {consecutive_failures}회).")
                
                # 최대 연속 실패 횟수를 초과한 경우 복구 시도
                if consecutive_failures >= component_info['max_consecutive_failures']:
                    self._try_recovery(component_name)
        
        except Exception as e:
            self.logger.error(f"컴포넌트 '{component_name}' 확인 중 오류: {e}")
            self.logger.debug(traceback.format_exc())
    
    def _try_recovery(self, component_name):
        """
        컴포넌트 복구 시도
        
        Args:
            component_name (str): 복구할 컴포넌트 이름
        """
        try:
            # 복구 함수가 없으면 스킵
            if component_name not in self.recovery_actions:
                self.logger.warning(f"컴포넌트 '{component_name}'에 대한 복구 함수가 없습니다.")
                return
            
            # 복구 시도 횟수 증가
            self.health_stats['recovery_attempts'][component_name] += 1
            attempts = self.health_stats['recovery_attempts'][component_name]
            
            self.logger.info(f"컴포넌트 '{component_name}' 복구 시도 ({attempts}번째)...")
            
            # 복구 시작 시간
            start_time = time.time()
            
            # 복구 함수 호출
            recovery_result = self.recovery_actions[component_name]()
            
            # 복구 종료 시간 및 소요 시간
            end_time = time.time()
            duration = end_time - start_time
            
            # 복구 이력 기록
            recovery_entry = {
                'component': component_name,
                'timestamp': datetime.now().isoformat(),
                'success': bool(recovery_result),
                'duration': duration,
                'attempt': attempts
            }
            self.status_history['recoveries'].append(recovery_entry)
            
            # 복구 성공 시 통계 업데이트
            if recovery_result:
                self.status_history['components'][component_name]['total_recoveries'] += 1
            
            self._save_status_history()
            
            # 복구 결과 로깅
            if recovery_result:
                self.logger.info(f"컴포넌트 '{component_name}' 복구 성공 (소요 시간: {duration:.2f}초)")
            else:
                self.logger.warning(f"컴포넌트 '{component_name}' 복구 실패 (소요 시간: {duration:.2f}초)")
            
            return recovery_result
            
        except Exception as e:
            self.logger.error(f"컴포넌트 '{component_name}' 복구 시도 중 오류: {e}")
            self.logger.debug(traceback.format_exc())
            return False
    
    def _record_status_change(self, component_name, old_status, new_status):
        """상태 변경 기록"""
        try:
            status_change = {
                'timestamp': datetime.now().isoformat(),
                'old_status': old_status,
                'new_status': new_status
            }
            
            self.status_history['components'][component_name]['status_changes'].append(status_change)
            self._save_status_history()
            
            # 상태 변경 로그
            self.logger.info(f"컴포넌트 '{component_name}' 상태 변경: {old_status} -> {new_status}")
            
        except Exception as e:
            self.logger.error(f"상태 변경 기록 중 오류: {e}")
    
    def _check_system_resources(self):
        """시스템 자원 상태 확인 및 기록"""
        try:
            # CPU 사용량
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # 메모리 사용량
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 디스크 사용량
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # 프로세스 정보
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info().rss / (1024 * 1024)  # MB
            process_cpu = process.cpu_percent(interval=0.1)
            
            # 로깅 (리소스 사용량이 높은 경우만)
            if cpu_percent > 80 or memory_percent > 80 or disk_percent > 90 or process_memory > 500:
                self.logger.warning(
                    f"시스템 자원 경고 - CPU: {cpu_percent}%, "
                    f"메모리: {memory_percent}%, "
                    f"디스크: {disk_percent}%, "
                    f"프로세스 메모리: {process_memory:.2f}MB, "
                    f"프로세스 CPU: {process_cpu}%"
                )
            
            # 자원 사용량이 임계치를 초과하는 경우 조치
            if memory_percent > 90:
                self.logger.critical("메모리 사용량이 90%를 초과했습니다. 메모리 정리를 시도합니다.")
                self._perform_memory_cleanup()
            
        except Exception as e:
            self.logger.error(f"시스템 자원 확인 중 오류: {e}")
    
    def _perform_memory_cleanup(self):
        """메모리 정리 작업 수행"""
        try:
            # Python 가비지 컬렉션 강제 실행
            import gc
            collected = gc.collect()
            self.logger.info(f"가비지 컬렉션 수행: {collected}개 객체 정리됨")
            
            # 추가적인 메모리 정리 작업
            # ...
            
        except Exception as e:
            self.logger.error(f"메모리 정리 중 오류: {e}")

# 데이터베이스 컴포넌트 상태 확인 함수
def check_database_connection():
    """데이터베이스 연결 상태 확인"""
    try:
        from src.db_manager import db_manager
        return db_manager.check_connection()
    except Exception:
        return False

# 거래소 API 연결 상태 확인 함수
def check_exchange_api_connection(exchange_id='binance'):
    """거래소 API 연결 상태 확인"""
    try:
        from src.exchange_api import ExchangeAPI
        api = ExchangeAPI(exchange_id=exchange_id)
        return api.check_connection()
    except Exception:
        return False

# 데이터 수집기 상태 확인 함수
def check_data_collector():
    """데이터 수집기 상태 확인"""
    try:
        from src.data_collector import DataCollector
        collector = DataCollector()
        # 간단한 데이터 요청으로 상태 확인
        data = collector.fetch_recent_data(limit=1)
        return data is not None and not data.empty
    except Exception:
        return False

# 거래소 API 연결 복구 함수
def recover_exchange_api_connection(exchange_id='binance'):
    """거래소 API 연결 복구"""
    try:
        from src.exchange_api import ExchangeAPI
        # 새 인스턴스 생성으로 연결 재설정
        api = ExchangeAPI(exchange_id=exchange_id, force_new=True)
        return api.check_connection()
    except Exception:
        return False

# 사용 예:
# health_monitor = SystemHealthMonitor(check_interval=60)
# health_monitor.register_component('database', check_database_connection)
# health_monitor.register_component('exchange_api', check_exchange_api_connection, recover_exchange_api_connection)
# health_monitor.start_monitoring()
