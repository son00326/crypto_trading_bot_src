#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 네트워크 복구 관리자

import os
import time
import json
import socket
import logging
import threading
import traceback
import requests
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Callable, Any, Union

from src.logging_config import get_logger
from src.error_handlers import error_analyzer
from src.config import DATA_DIR

class NetworkRecoveryManager:
    """
    네트워크 복구 관리자
    
    네트워크 문제를 감지하고 다양한 복구 전략을 사용하여
    자동으로 연결을 복구하는 기능을 제공합니다.
    """
    
    def __init__(self, check_interval: int = 30, max_recovery_attempts: int = 5):
        """
        NetworkRecoveryManager 초기화
        
        Args:
            check_interval: 연결 확인 간격 (초)
            max_recovery_attempts: 최대 연속 복구 시도 횟수
        """
        self.logger = get_logger('network_recovery')
        self.check_interval = check_interval
        self.max_recovery_attempts = max_recovery_attempts
        
        # 연결 상태 관리
        self.connection_status = {}
        self.recovery_attempts = {}
        self.last_successful_connection = {}
        self.alternative_endpoints = {}
        
        # 백오프 설정
        self.base_backoff_time = 1.0
        self.max_backoff_time = 300.0  # 5분
        self.backoff_factor = 2.0
        self.jitter_factor = 0.2
        
        # 네트워크 모니터링 상태
        self.monitoring = False
        self.monitor_thread = None
        
        # 복구 전략 등록
        self.recovery_strategies = {
            'dns_failure': self._recover_from_dns_failure,
            'connection_timeout': self._recover_from_connection_timeout,
            'connection_reset': self._recover_from_connection_reset,
            'rate_limit': self._recover_from_rate_limit,
            'api_error': self._recover_from_api_error,
            'general_network': self._recover_from_general_network_error
        }
        
        # 복구 로그 디렉토리
        self.log_dir = os.path.join(DATA_DIR, 'network_recovery')
        os.makedirs(self.log_dir, exist_ok=True)
        self.recovery_log_file = os.path.join(self.log_dir, 'recovery_log.json')
        
        # 복구 기록 로드
        self._load_recovery_logs()
        
        self.logger.info("네트워크 복구 관리자 초기화 완료")
    
    def _load_recovery_logs(self):
        """기존 복구 로그 로드"""
        try:
            if os.path.exists(self.recovery_log_file):
                with open(self.recovery_log_file, 'r') as f:
                    recovery_data = json.load(f)
                
                self.recovery_attempts = recovery_data.get('recovery_attempts', {})
                self.connection_status = recovery_data.get('connection_status', {})
                
                # 시간 형식 변환
                for key, value in recovery_data.get('last_successful_connection', {}).items():
                    if value:
                        try:
                            self.last_successful_connection[key] = datetime.fromisoformat(value)
                        except ValueError:
                            self.last_successful_connection[key] = None
                
                self.logger.info("복구 로그 로드 완료")
        except Exception as e:
            self.logger.error(f"복구 로그 로드 중 오류: {e}")
    
    def _save_recovery_logs(self):
        """현재 복구 로그 저장"""
        try:
            # 저장을 위한 시간 형식 변환
            last_connections = {}
            for key, value in self.last_successful_connection.items():
                if value and isinstance(value, datetime):
                    last_connections[key] = value.isoformat()
                else:
                    last_connections[key] = None
            
            recovery_data = {
                'last_updated': datetime.now().isoformat(),
                'recovery_attempts': self.recovery_attempts,
                'connection_status': self.connection_status,
                'last_successful_connection': last_connections
            }
            
            with open(self.recovery_log_file, 'w') as f:
                json.dump(recovery_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"복구 로그 저장 중 오류: {e}")
    
    def register_endpoint(self, service_name: str, primary_url: str, 
                         alternative_urls: Optional[List[str]] = None):
        """
        모니터링할 엔드포인트 등록
        
        Args:
            service_name: 서비스 이름 (예: 'binance', 'bybit')
            primary_url: 기본 URL
            alternative_urls: 대체 URL 목록 (장애 시 사용)
        """
        self.connection_status[service_name] = 'unknown'
        self.recovery_attempts[service_name] = 0
        self.last_successful_connection[service_name] = None
        
        # 대체 엔드포인트 설정
        self.alternative_endpoints[service_name] = {
            'primary': primary_url,
            'alternatives': alternative_urls or [],
            'current': primary_url,  # 현재 사용 중인 엔드포인트
            'failed_endpoints': set()  # 실패한 엔드포인트 목록
        }
        
        self.logger.info(f"엔드포인트 등록: {service_name} - {primary_url}")
    
    def check_connection(self, service_name: str, timeout: float = 10.0) -> bool:
        """
        서비스 연결 상태 확인
        
        Args:
            service_name: 확인할 서비스 이름
            timeout: 연결 제한 시간 (초)
            
        Returns:
            bool: 연결 상태 (True=정상, False=실패)
        """
        if service_name not in self.alternative_endpoints:
            self.logger.warning(f"등록되지 않은 서비스: {service_name}")
            return False
        
        # 현재 사용 중인 엔드포인트
        current_url = self.alternative_endpoints[service_name]['current']
        
        try:
            # 연결 테스트
            start_time = time.time()
            response = requests.get(current_url, timeout=timeout)
            elapsed_time = time.time() - start_time
            
            # 상태 코드 확인
            if response.status_code < 400:
                # 성공적인 연결
                self.connection_status[service_name] = 'connected'
                self.last_successful_connection[service_name] = datetime.now()
                self.recovery_attempts[service_name] = 0
                
                # 로그 기록 (상태 변경 시에만)
                self.logger.debug(f"{service_name} 연결 성공 (응답 시간: {elapsed_time:.2f}초)")
                return True
            else:
                # 서버 응답 오류
                self.connection_status[service_name] = 'error'
                self.logger.warning(f"{service_name} 연결 오류: 상태 코드 {response.status_code}")
                return False
        
        except requests.exceptions.Timeout:
            # 타임아웃 오류
            self.connection_status[service_name] = 'timeout'
            self.logger.warning(f"{service_name} 연결 타임아웃")
            return False
        
        except requests.exceptions.ConnectionError:
            # 연결 오류
            self.connection_status[service_name] = 'connection_error'
            self.logger.warning(f"{service_name} 연결 실패")
            return False
        
        except Exception as e:
            # 기타 오류
            self.connection_status[service_name] = 'unknown_error'
            self.logger.error(f"{service_name} 연결 확인 중 오류: {e}")
            return False
    
    def start_monitoring(self):
        """네트워크 연결 모니터링 시작"""
        if self.monitoring:
            self.logger.warning("이미 모니터링 중입니다.")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        self.logger.info(f"네트워크 연결 모니터링 시작 (간격: {self.check_interval}초)")
    
    def stop_monitoring(self):
        """네트워크 연결 모니터링 중지"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        
        self._save_recovery_logs()
        self.logger.info("네트워크 연결 모니터링 중지")
    
    def _monitoring_loop(self):
        """네트워크 모니터링 메인 루프"""
        while self.monitoring:
            try:
                # 모든 서비스 연결 확인
                for service_name in self.alternative_endpoints:
                    # 연결 상태 확인
                    connected = self.check_connection(service_name)
                    
                    # 연결 실패 시 복구 시도
                    if not connected:
                        self.recovery_attempts[service_name] += 1
                        
                        # 복구 필요 여부
                        if self.recovery_attempts[service_name] <= self.max_recovery_attempts:
                            self._attempt_recovery(service_name)
                
                # 복구 로그 저장 (30분마다)
                current_time = datetime.now()
                if current_time.minute % 30 == 0 and current_time.second < 10:
                    self._save_recovery_logs()
                
                # 다음 확인까지 대기
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"모니터링 루프 오류: {e}")
                time.sleep(5)  # 오류 발생 시 짧게 대기
    
    def _attempt_recovery(self, service_name: str) -> bool:
        """
        연결 복구 시도
        
        Args:
            service_name: 복구할 서비스 이름
            
        Returns:
            bool: 복구 성공 여부
        """
        # 오류 상태 확인
        error_type = self.connection_status[service_name]
        attempt = self.recovery_attempts[service_name]
        
        self.logger.info(f"{service_name} 복구 시도 #{attempt}: 오류 유형 '{error_type}'")
        
        # 지능형 백오프 계산
        backoff_time = self._calculate_backoff(attempt)
        
        # 복구 전략 선택
        recovery_func = self.recovery_strategies.get(error_type, self.recovery_strategies['general_network'])
        
        try:
            # 복구 시도
            success = recovery_func(service_name)
            
            if success:
                self.logger.info(f"{service_name} 복구 성공!")
                self.recovery_attempts[service_name] = 0
                self.connection_status[service_name] = 'connected'
                self.last_successful_connection[service_name] = datetime.now()
                
                # 오류 분석기에 기록
                if 'error_analyzer' in globals():
                    error_analyzer.log_error(
                        'network_recovery_success',
                        f"{service_name} 네트워크 연결 복구 성공",
                        {'service': service_name, 'error_type': error_type, 'attempts': attempt}
                    )
                
                return True
            else:
                self.logger.warning(f"{service_name} 복구 실패, {backoff_time:.1f}초 후 재시도")
                time.sleep(backoff_time)
                return False
                
        except Exception as e:
            self.logger.error(f"{service_name} 복구 시도 중 오류: {e}")
            time.sleep(backoff_time)
            return False
    
    def _calculate_backoff(self, attempt: int) -> float:
        """
        지능형 백오프 시간 계산
        
        Args:
            attempt: 현재 시도 횟수
            
        Returns:
            float: 대기 시간 (초)
        """
        # 기본 백오프 계산 (지수 백오프)
        backoff = min(
            self.max_backoff_time,
            self.base_backoff_time * (self.backoff_factor ** (attempt - 1))
        )
        
        # 야팔(jitter) 추가 (무작위성으로 동시 재시도 방지)
        jitter = random.uniform(-self.jitter_factor, self.jitter_factor)
        backoff = backoff * (1 + jitter)
        
        return max(self.base_backoff_time, backoff)
    
    def _switch_endpoint(self, service_name: str) -> bool:
        """
        대체 엔드포인트로 전환
        
        Args:
            service_name: 서비스 이름
            
        Returns:
            bool: 전환 성공 여부
        """
        if service_name not in self.alternative_endpoints:
            return False
        
        endpoints = self.alternative_endpoints[service_name]
        current = endpoints['current']
        alternatives = endpoints['alternatives']
        failed_endpoints = endpoints['failed_endpoints']
        
        # 현재 엔드포인트를 실패 목록에 추가
        failed_endpoints.add(current)
        
        # 사용 가능한 대체 엔드포인트 찾기
        available_alternatives = [url for url in alternatives if url not in failed_endpoints]
        
        if available_alternatives:
            # 대체 엔드포인트 중 하나를 무작위로 선택
            new_endpoint = random.choice(available_alternatives)
            endpoints['current'] = new_endpoint
            
            self.logger.info(f"{service_name} 엔드포인트 전환: {current} -> {new_endpoint}")
            return True
        else:
            # 모든 대체 엔드포인트가 실패한 경우, 기본 엔드포인트로 복귀
            failed_endpoints.clear()  # 실패 목록 초기화
            endpoints['current'] = endpoints['primary']
            
            self.logger.warning(f"{service_name} 모든 대체 엔드포인트 실패, 기본 엔드포인트로 복귀")
            return False
    
    def reset_failed_endpoints(self, service_name: str):
        """
        실패한 엔드포인트 목록 초기화
        
        Args:
            service_name: 서비스 이름
        """
        if service_name in self.alternative_endpoints:
            self.alternative_endpoints[service_name]['failed_endpoints'].clear()
            self.logger.info(f"{service_name} 실패 엔드포인트 목록 초기화")
    
    def get_current_endpoint(self, service_name: str) -> Optional[str]:
        """
        현재 사용 중인 엔드포인트 반환
        
        Args:
            service_name: 서비스 이름
            
        Returns:
            Optional[str]: 현재 엔드포인트 또는 None (등록되지 않은 경우)
        """
        if service_name in self.alternative_endpoints:
            return self.alternative_endpoints[service_name]['current']
        return None
    
    def _recover_from_dns_failure(self, service_name: str) -> bool:
        """
        DNS 실패 복구
        
        Args:
            service_name: 서비스 이름
            
        Returns:
            bool: 복구 성공 여부
        """
        self.logger.info(f"{service_name} DNS 실패 복구 시도")
        
        # DNS 캐시 초기화 시도 (플랫폼에 따라 다름)
        try:
            if os.name == 'posix':
                # Linux/Mac: nscd 캐시 초기화
                if os.path.exists('/usr/sbin/nscd'):
                    os.system('/usr/sbin/nscd -i hosts')
            elif os.name == 'nt':
                # Windows: DNS 캐시 초기화
                os.system('ipconfig /flushdns')
                
            # DNS 서버 변경 (Google DNS 사용)
            # 참고: 이는 프로그램 차원에서 전체 시스템의 DNS를 변경하지는 않음
            # socket.getaddrinfo 동작에 영향을 주기 위한 힌트 수준
            socket.setdefaulttimeout(5.0)
                
            # 대체 엔드포인트로 전환
            self._switch_endpoint(service_name)
            
            # 연결 확인
            return self.check_connection(service_name)
            
        except Exception as e:
            self.logger.error(f"DNS 복구 중 오류: {e}")
            return False
    
    def _recover_from_connection_timeout(self, service_name: str) -> bool:
        """
        연결 타임아웃 복구
        
        Args:
            service_name: 서비스 이름
            
        Returns:
            bool: 복구 성공 여부
        """
        self.logger.info(f"{service_name} 연결 타임아웃 복구 시도")
        
        # 타임아웃 값 조정
        socket.setdefaulttimeout(15.0)  # 더 긴 타임아웃 설정
        
        # 대체 엔드포인트 시도
        self._switch_endpoint(service_name)
        
        # 연결 재시도
        return self.check_connection(service_name, timeout=15.0)
    
    def _recover_from_connection_reset(self, service_name: str) -> bool:
        """
        연결 재설정 복구
        
        Args:
            service_name: 서비스 이름
            
        Returns:
            bool: 복구 성공 여부
        """
        self.logger.info(f"{service_name} 연결 재설정 복구 시도")
        
        # 약간의 지연 추가 (서버 부하 방지)
        time.sleep(2)
        
        # 대체 엔드포인트 시도
        self._switch_endpoint(service_name)
        
        # 연결 재시도
        return self.check_connection(service_name)
    
    def _recover_from_rate_limit(self, service_name: str) -> bool:
        """
        요청 제한(Rate Limit) 복구
        
        Args:
            service_name: 서비스 이름
            
        Returns:
            bool: 복구 성공 여부
        """
        self.logger.info(f"{service_name} 요청 제한 복구 시도")
        
        # 요청 제한에는 더 긴 대기 시간 필요
        wait_time = 60.0  # 1분 대기
        
        self.logger.info(f"요청 제한으로 {wait_time}초 대기")
        time.sleep(wait_time)
        
        # 연결 재시도
        return self.check_connection(service_name)
    
    def _recover_from_api_error(self, service_name: str) -> bool:
        """
        API 오류 복구
        
        Args:
            service_name: 서비스 이름
            
        Returns:
            bool: 복구 성공 여부
        """
        self.logger.info(f"{service_name} API 오류 복구 시도")
        
        # API 오류는 대체 엔드포인트가 도움이 될 수 있음
        self._switch_endpoint(service_name)
        
        # 짧은 대기 후 재시도
        time.sleep(3)
        
        # 연결 재시도
        return self.check_connection(service_name)
    
    def _recover_from_general_network_error(self, service_name: str) -> bool:
        """
        일반적인 네트워크 오류 복구
        
        Args:
            service_name: 서비스 이름
            
        Returns:
            bool: 복구 성공 여부
        """
        self.logger.info(f"{service_name} 일반 네트워크 오류 복구 시도")
        
        # 대체 엔드포인트 시도
        self._switch_endpoint(service_name)
        
        # 연결 재시도
        return self.check_connection(service_name)

# 테스트 코드
if __name__ == "__main__":
    # 간단한 테스트
    recovery_manager = NetworkRecoveryManager(check_interval=10)
    
    # 거래소 엔드포인트 등록
    recovery_manager.register_endpoint(
        service_name='binance',
        primary_url='https://api.binance.com/api/v3/ping',
        alternative_urls=[
            'https://api1.binance.com/api/v3/ping',
            'https://api2.binance.com/api/v3/ping',
            'https://api3.binance.com/api/v3/ping'
        ]
    )
    
    recovery_manager.register_endpoint(
        service_name='bybit',
        primary_url='https://api.bybit.com/v2/public/time',
        alternative_urls=[
            'https://api.bytick.com/v2/public/time'
        ]
    )
    
    # 모니터링 시작
    recovery_manager.start_monitoring()
    
    try:
        # 테스트를 위해 일정 시간 동안 실행
        print("네트워크 복구 관리자 테스트 실행 중... (Ctrl+C로 종료)")
        while True:
            time.sleep(10)
            
            # 현재 상태 출력
            print("\n현재 연결 상태:")
            for service, status in recovery_manager.connection_status.items():
                current_endpoint = recovery_manager.get_current_endpoint(service)
                print(f"  - {service}: {status} (엔드포인트: {current_endpoint})")
            
    except KeyboardInterrupt:
        print("\n테스트 종료")
    finally:
        recovery_manager.stop_monitoring()
        print("모니터링 종료")
