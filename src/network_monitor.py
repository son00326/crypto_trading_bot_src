#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 네트워크 모니터링 모듈

import time
import threading
import socket
import requests
import logging
import traceback
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict, deque

from src.logging_config import get_logger
from src.error_handlers import error_analyzer

class NetworkMonitor:
    """
    네트워크 연결 상태 및 성능 모니터링 클래스
    
    기능:
    - 주요 거래소 및 서비스 연결 상태 모니터링
    - 네트워크 지연시간(latency) 측정 및 추적
    - 네트워크 중단 감지 및 로깅
    - 네트워크 성능 통계 제공
    """
    
    def __init__(self, check_interval=60):
        """
        네트워크 모니터 초기화
        
        Args:
            check_interval (int): 네트워크 상태 확인 간격 (초)
        """
        self.logger = get_logger('network_monitor')
        self.check_interval = check_interval
        self.running = False
        self.monitor_thread = None
        
        # 연결 대상 목록 (거래소 및 중요 서비스)
        self.targets = {
            'binance': 'https://api.binance.com/api/v3/ping',
            'bybit': 'https://api.bybit.com/v2/public/time',
            'ftx': 'https://ftx.com/api/time',
            'internet': 'https://www.google.com',
            'dns': '8.8.8.8'  # Google DNS 서버
        }
        
        # 상태 및 지연시간 기록
        self.status = {target: False for target in self.targets}
        self.latency = {target: float('inf') for target in self.targets}
        self.latency_history = {target: deque(maxlen=100) for target in self.targets}
        
        # 성능 통계
        self.stats = {
            'outages': defaultdict(int),
            'outage_durations': defaultdict(list),
            'last_outage': {},
            'current_outage_start': {},
            'total_checks': defaultdict(int)
        }
        
        # 네트워크 로그 디렉토리
        from src.config import DATA_DIR
        self.log_dir = os.path.join(DATA_DIR, 'network_logs')
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_path = os.path.join(self.log_dir, f'network_log_{datetime.now().strftime("%Y%m%d")}.json')
        
        # 로그 로드
        self._load_logs()
    
    def _load_logs(self):
        """이전 네트워크 로그 로드"""
        try:
            if os.path.exists(self.log_path):
                with open(self.log_path, 'r') as f:
                    log_data = json.load(f)
                    
                    # 관련 데이터 복원
                    if 'outages' in log_data:
                        for target, count in log_data['outages'].items():
                            self.stats['outages'][target] = count
                    
                    if 'outage_durations' in log_data:
                        for target, durations in log_data['outage_durations'].items():
                            self.stats['outage_durations'][target] = durations
                    
                    if 'last_outage' in log_data:
                        self.stats['last_outage'] = log_data['last_outage']
                    
                    self.logger.info(f"네트워크 로그를 로드했습니다: {self.log_path}")
            else:
                self.logger.info("기존 네트워크 로그가 없습니다. 새로 생성합니다.")
        except Exception as e:
            self.logger.error(f"네트워크 로그 로드 중 오류: {e}")
    
    def _save_logs(self):
        """현재 네트워크 상태 및 통계 저장"""
        try:
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'status': self.status,
                'latency': self.latency,
                'stats': {
                    'outages': dict(self.stats['outages']),
                    'outage_durations': dict(self.stats['outage_durations']),
                    'last_outage': self.stats['last_outage'],
                    'total_checks': dict(self.stats['total_checks'])
                }
            }
            
            # JSON 파일로 저장
            with open(self.log_path, 'w') as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"네트워크 로그 저장 중 오류: {e}")
    
    def start_monitoring(self):
        """네트워크 모니터링 시작"""
        if self.running:
            self.logger.warning("네트워크 모니터링이 이미 실행 중입니다.")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        self.logger.info(f"네트워크 모니터링을 시작합니다 (확인 간격: {self.check_interval}초)")
    
    def stop_monitoring(self):
        """네트워크 모니터링 중지"""
        if not self.running:
            self.logger.warning("네트워크 모니터링이 이미 중지되었습니다.")
            return
        
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        
        self._save_logs()
        self.logger.info("네트워크 모니터링을 중지했습니다.")
    
    def _monitoring_loop(self):
        """네트워크 모니터링 루프"""
        while self.running:
            try:
                for target, url in self.targets.items():
                    self._check_target(target, url)
                
                # 로그 저장 (주기적으로)
                if datetime.now().minute % 10 == 0:  # 10분마다 저장
                    self._save_logs()
                
                # 다음 확인까지 대기
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"네트워크 모니터링 루프 오류: {e}")
                self.logger.debug(traceback.format_exc())
                time.sleep(5)  # 오류 발생 시 짧게 대기
    
    def _check_target(self, target, url):
        """
        대상 서비스 연결 확인 및 지연시간 측정
        
        Args:
            target (str): 확인할 대상 이름
            url (str): 확인할 URL 또는 호스트
        """
        self.stats['total_checks'][target] += 1
        prev_status = self.status[target]
        
        try:
            start_time = time.time()
            
            # DNS 서버 확인은 다른 방식으로 수행
            if target == 'dns':
                status, latency = self._check_dns(url)
            else:
                status, latency = self._check_http(url)
            
            # 상태 및 지연시간 업데이트
            self.status[target] = status
            self.latency[target] = latency
            self.latency_history[target].append(latency)
            
            # 중단 추적
            if not status and prev_status:
                # 새로운 중단 발생
                self.stats['outages'][target] += 1
                self.stats['current_outage_start'][target] = datetime.now()
                self.logger.warning(f"네트워크 중단 감지: {target}")
                
                # 오류 분석기에 기록
                if 'error_analyzer' in globals():
                    error_analyzer.log_error(
                        'network_outage',
                        f"{target} 연결 중단",
                        {'target': target, 'url': url},
                        is_critical=True
                    )
            
            elif status and not prev_status:
                # 중단 복구
                end_time = datetime.now()
                start_time = self.stats['current_outage_start'].get(target)
                
                if start_time:
                    duration = (end_time - start_time).total_seconds()
                    self.stats['outage_durations'][target].append(duration)
                    self.stats['last_outage'][target] = {
                        'start': start_time.isoformat(),
                        'end': end_time.isoformat(),
                        'duration': duration
                    }
                    self.logger.info(f"네트워크 복구: {target} (중단 시간: {duration:.2f}초)")
        
        except Exception as e:
            self.logger.error(f"네트워크 상태 확인 중 오류 ({target}): {e}")
            self.status[target] = False
    
    def _check_http(self, url, timeout=5):
        """
        HTTP 연결 확인 및 지연시간 측정
        
        Args:
            url (str): 확인할 URL
            timeout (int): 연결 제한시간 (초)
            
        Returns:
            tuple: (연결 성공 여부, 지연시간)
        """
        try:
            start_time = time.time()
            response = requests.get(url, timeout=timeout)
            end_time = time.time()
            
            latency = (end_time - start_time) * 1000  # ms 단위
            
            if response.status_code < 400:
                return True, latency
            else:
                return False, float('inf')
        except Exception:
            return False, float('inf')
    
    def _check_dns(self, host, port=53, timeout=2):
        """
        DNS 서버 연결 확인 및 지연시간 측정
        
        Args:
            host (str): DNS 서버 주소
            port (int): 포트 번호
            timeout (int): 연결 제한시간 (초)
            
        Returns:
            tuple: (연결 성공 여부, 지연시간)
        """
        try:
            start_time = time.time()
            
            # 소켓 연결 시도
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # ms 단위
            
            return True, latency
        except Exception:
            return False, float('inf')
    
    def get_status_report(self):
        """
        현재 네트워크 상태 보고서 생성
        
        Returns:
            dict: 네트워크 상태 정보
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': all(self.status.values()),
            'targets': {}
        }
        
        for target in self.targets:
            # 평균 및 최대 지연시간 계산
            history = list(self.latency_history[target])
            avg_latency = sum(history) / len(history) if history else None
            max_latency = max(history) if history else None
            
            report['targets'][target] = {
                'status': self.status[target],
                'current_latency': self.latency[target],
                'avg_latency': avg_latency,
                'max_latency': max_latency,
                'outages': self.stats['outages'][target],
                'last_outage': self.stats['last_outage'].get(target)
            }
        
        return report
    
    def is_network_healthy(self):
        """
        전체 네트워크 상태 확인
        
        Returns:
            bool: 네트워크가 정상인 경우 True
        """
        # 주요 거래소 중 하나 이상 연결 가능하고 인터넷 연결이 정상인지 확인
        exchanges = ['binance', 'bybit', 'ftx']
        exchange_status = any(self.status[ex] for ex in exchanges if ex in self.status)
        internet_status = self.status.get('internet', False)
        
        return exchange_status and internet_status

# 단독 실행 테스트용
if __name__ == "__main__":
    monitor = NetworkMonitor(check_interval=10)
    monitor.start_monitoring()
    
    try:
        while True:
            time.sleep(60)
            report = monitor.get_status_report()
            print(json.dumps(report, indent=2))
    except KeyboardInterrupt:
        monitor.stop_monitoring()
        print("네트워크 모니터링 중지됨")
