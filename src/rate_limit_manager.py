#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - API 요청 제한 관리자

import time
import threading
import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Callable

from src.logging_config import get_logger

class RateLimitManager:
    """
    API 요청 제한 관리자
    
    거래소 API 호출 시 레이트 리밋을 초과하지 않도록 관리하는 클래스
    - 요청 스로틀링
    - 요청 큐잉
    - 우선순위 기반 요청 처리
    """
    
    def __init__(self, exchange_id: str = 'binance'):
        """
        RateLimitManager 초기화
        
        Args:
            exchange_id: 거래소 ID (binance, upbit 등)
        """
        self.exchange_id = exchange_id
        self.logger = get_logger(f'crypto_bot.rate_limit.{exchange_id}')
        
        # 스레드 안전을 위한 락
        self.lock = threading.RLock()
        
        # 요청 기록
        self.request_history = defaultdict(lambda: deque(maxlen=1000))
        
        # 엔드포인트별 제한 설정
        self.limits = self._get_default_limits(exchange_id)
        
        # 요청 큐
        self.request_queue = []
        
        # 현재 처리 중인 요청 카운터
        self.active_requests = 0
        
        # 큐 처리 스레드
        self.queue_thread = None
        self.queue_processing = False
        
        self.logger.info(f"{exchange_id} API 요청 제한 관리자 초기화 완료")
    
    def _get_default_limits(self, exchange_id: str) -> Dict[str, Dict]:
        """
        거래소별 기본 제한 설정 반환
        
        Args:
            exchange_id: 거래소 ID
            
        Returns:
            Dict: 엔드포인트별 제한 설정
        """
        # 바이낸스 기본 제한 설정
        if exchange_id.lower() == 'binance':
            return {
                'default': {
                    'weight': 1,             # 기본 가중치
                    'limit': 1200,           # 1분당 최대 요청 수
                    'interval': 60,          # 시간 간격 (초)
                    'retry_after': 0.5,      # 제한 초과 시 재시도 간격 (초)
                    'priority': 1            # 우선순위 (낮을수록 높은 우선순위)
                },
                '/api/v3/ticker': {
                    'weight': 1,
                    'limit': 1200,
                    'interval': 60,
                    'retry_after': 0.5,
                    'priority': 1
                },
                '/api/v3/klines': {
                    'weight': 1,
                    'limit': 1200,
                    'interval': 60,
                    'retry_after': 0.5,
                    'priority': 1
                },
                '/api/v3/order': {
                    'weight': 1,
                    'limit': 100,
                    'interval': 10,
                    'retry_after': 0.1,
                    'priority': 0            # 주문은 최우선 처리
                },
                '/api/v3/account': {
                    'weight': 10,
                    'limit': 100,
                    'interval': 60,
                    'retry_after': 1.0,
                    'priority': 2
                }
            }
        
        # 다른 거래소의 경우 기본 값만 제공
        return {
            'default': {
                'weight': 1,
                'limit': 100,
                'interval': 60,
                'retry_after': 1.0,
                'priority': 1
            }
        }
    
    def start_queue_processing(self):
        """큐 처리 스레드 시작"""
        if self.queue_thread is None or not self.queue_thread.is_alive():
            self.queue_processing = True
            self.queue_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.queue_thread.start()
            self.logger.info("요청 큐 처리 스레드 시작")
    
    def stop_queue_processing(self):
        """큐 처리 스레드 중지"""
        self.queue_processing = False
        if self.queue_thread and self.queue_thread.is_alive():
            self.queue_thread.join(timeout=2.0)
            self.logger.info("요청 큐 처리 스레드 종료")
    
    def _process_queue(self):
        """요청 큐 처리 루프"""
        while self.queue_processing:
            with self.lock:
                if not self.request_queue:
                    # 큐가 비어있으면 잠시 대기
                    pass
                else:
                    # 우선순위에 따라 정렬
                    self.request_queue.sort(key=lambda x: x['priority'])
                    
                    # 첫 번째 요청 처리
                    request = self.request_queue[0]
                    endpoint = request['endpoint']
                    
                    # 해당 엔드포인트에 제한이 걸려있는지 확인
                    if self.can_make_request(endpoint):
                        # 큐에서 제거
                        self.request_queue.pop(0)
                        
                        # 요청 실행
                        self.active_requests += 1
                        try:
                            request['callback'](*request['args'], **request['kwargs'])
                        except Exception as e:
                            self.logger.error(f"큐 처리 중 요청 실행 오류: {e}")
                        finally:
                            self.active_requests -= 1
                    else:
                        # 제한에 걸린 경우 대기
                        retry_after = self.limits.get(
                            endpoint, self.limits['default']
                        ).get('retry_after', 0.5)
                        time.sleep(retry_after)
            
            # 루프 간 짧은 대기
            time.sleep(0.01)
    
    def register_request(self, endpoint: str, timestamp: float = None):
        """
        API 요청 등록
        
        Args:
            endpoint: API 엔드포인트
            timestamp: 요청 시간 (None이면 현재 시간)
        """
        with self.lock:
            timestamp = timestamp or time.time()
            self.request_history[endpoint].append(timestamp)
    
    def can_make_request(self, endpoint: str) -> bool:
        """
        요청 가능 여부 확인
        
        Args:
            endpoint: API 엔드포인트
            
        Returns:
            bool: 요청 가능 여부
        """
        with self.lock:
            # 엔드포인트에 대한 제한 설정 가져오기
            limit_config = self.limits.get(endpoint, self.limits['default'])
            
            # 제한 파라미터
            request_limit = limit_config['limit']
            interval = limit_config['interval']
            
            # 현재 시간
            current_time = time.time()
            
            # 지정된 간격 내의 요청 수 계산
            recent_requests = sum(
                1 for req_time in self.request_history[endpoint]
                if current_time - req_time <= interval
            )
            
            # 요청 가능 여부 반환
            can_request = recent_requests < request_limit
            
            if not can_request:
                self.logger.warning(
                    f"엔드포인트 {endpoint} 요청 제한 도달: {recent_requests}/{request_limit} "
                    f"(최근 {interval}초)"
                )
            
            return can_request
    
    def enqueue_request(self, endpoint: str, callback: Callable, *args, **kwargs):
        """
        요청을 큐에 추가
        
        Args:
            endpoint: API 엔드포인트
            callback: 실행할 콜백 함수
            *args, **kwargs: 콜백 함수에 전달할 인자
        """
        with self.lock:
            # 엔드포인트에 대한 제한 설정 가져오기
            limit_config = self.limits.get(endpoint, self.limits['default'])
            
            # 요청 정보 생성
            request = {
                'endpoint': endpoint,
                'callback': callback,
                'args': args,
                'kwargs': kwargs,
                'timestamp': time.time(),
                'priority': limit_config.get('priority', 1)
            }
            
            # 큐에 추가
            self.request_queue.append(request)
            
            # 큐 처리 스레드 시작 (아직 실행 중이 아니라면)
            if not self.queue_processing:
                self.start_queue_processing()
    
    def throttle_request(self, endpoint: str, blocking: bool = True) -> bool:
        """
        요청 스로틀링
        
        Args:
            endpoint: API 엔드포인트
            blocking: 요청 불가 시 차단 여부
            
        Returns:
            bool: 요청 가능 여부 (blocking=False인 경우에만 의미 있음)
        """
        with self.lock:
            # 요청 가능 여부 확인
            if self.can_make_request(endpoint):
                self.register_request(endpoint)
                return True
            
            if not blocking:
                return False
            
            # 요청 가능할 때까지 대기
            retry_after = self.limits.get(
                endpoint, self.limits['default']
            ).get('retry_after', 0.5)
            
            self.logger.info(f"엔드포인트 {endpoint} 제한 도달, {retry_after:.2f}초 대기")
            
            # 락을 해제하고 대기
            self.lock.release()
            try:
                time.sleep(retry_after)
                
                # 재귀적으로 다시 시도
                return self.throttle_request(endpoint, blocking)
            finally:
                # 락 다시 획득
                self.lock.acquire()
    
    def wait_if_needed(self, endpoint: str):
        """
        필요한 경우 요청 가능할 때까지 대기
        
        Args:
            endpoint: API 엔드포인트
        """
        self.throttle_request(endpoint, blocking=True)
    
    def get_rate_limit_status(self, endpoint: str = None) -> Dict:
        """
        현재 레이트 리밋 상태 조회
        
        Args:
            endpoint: 특정 엔드포인트 (None이면 모든 엔드포인트)
            
        Returns:
            Dict: 레이트 리밋 상태 정보
        """
        with self.lock:
            current_time = time.time()
            result = {}
            
            endpoints = [endpoint] if endpoint else self.request_history.keys()
            
            for ep in endpoints:
                limit_config = self.limits.get(ep, self.limits['default'])
                interval = limit_config['interval']
                limit = limit_config['limit']
                
                # 최근 요청 수 계산
                recent_requests = sum(
                    1 for req_time in self.request_history[ep]
                    if current_time - req_time <= interval
                )
                
                # 사용률 계산
                usage_percent = (recent_requests / limit) * 100 if limit > 0 else 0
                
                # 결과 저장
                result[ep] = {
                    'recent_requests': recent_requests,
                    'limit': limit,
                    'interval': interval,
                    'usage_percent': usage_percent,
                    'available': recent_requests < limit
                }
            
            return result

# 싱글톤 인스턴스 관리
_rate_limit_managers = {}

def get_rate_limit_manager(exchange_id: str = 'binance') -> RateLimitManager:
    """
    지정된 거래소에 대한 RateLimitManager 인스턴스 반환
    
    Args:
        exchange_id: 거래소 ID
        
    Returns:
        RateLimitManager: 관리자 인스턴스
    """
    global _rate_limit_managers
    
    if exchange_id not in _rate_limit_managers:
        _rate_limit_managers[exchange_id] = RateLimitManager(exchange_id)
        
    return _rate_limit_managers[exchange_id]

# 함수 데코레이터
def rate_limited(endpoint: str = 'default', exchange_id: str = 'binance'):
    """
    함수에 레이트 리밋 기능을 추가하는 데코레이터
    
    Args:
        endpoint: API 엔드포인트
        exchange_id: 거래소 ID
        
    Returns:
        Callable: 데코레이터 함수
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 레이트 리밋 관리자 가져오기
            manager = get_rate_limit_manager(exchange_id)
            
            # 요청 스로틀링
            manager.throttle_request(endpoint)
            
            # 원본 함수 실행
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator

# 테스트 코드
if __name__ == "__main__":
    # 테스트용 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 레이트 리밋 관리자 생성
    manager = get_rate_limit_manager('binance')
    
    # 테스트 엔드포인트
    endpoint = '/api/v3/ticker'
    
    # 요청 등록 테스트
    for i in range(10):
        manager.register_request(endpoint)
        print(f"요청 {i+1} 등록")
    
    # 상태 조회
    status = manager.get_rate_limit_status(endpoint)
    print(f"상태: {status}")
    
    # 스로틀링 테스트
    def test_request():
        print("요청 시작...")
        manager.throttle_request(endpoint)
        print("요청 완료!")
    
    # 여러 요청 동시 실행
    threads = []
    for i in range(5):
        t = threading.Thread(target=test_request)
        threads.append(t)
        t.start()
    
    # 모든 스레드 완료 대기
    for t in threads:
        t.join()
    
    print("테스트 완료!")
