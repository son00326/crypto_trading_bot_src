#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 에러 처리 유틸리티
import functools
import traceback
import time
import json
import os
import random
import threading
import inspect
import socket
from typing import List, Dict, Any, Callable, Optional, Type, Union, Set, Tuple
from datetime import datetime, timedelta
from collections import deque, defaultdict

# 로거는 지연 가져오기로 순환 참조 방지
from src.logging_config import get_logger, error_logger

# 레이트 리미트 관리 클래스
class RateLimitManager:
    """API 요청 제한 관리 클래스"""
    
    def __init__(self):
        """레이트 리미트 관리자 초기화"""
        # 거래소별 요청 추적
        self.request_counters = {}
        # 거래소별 한도 설정
        self.rate_limits = {
            'binance': {'window_size': 60, 'max_requests': 1200},  # 1분당 1200 요청
            'bybit': {'window_size': 60, 'max_requests': 600},     # 1분당 600 요청
            'ftx': {'window_size': 60, 'max_requests': 300},       # 1분당 300 요청
            'default': {'window_size': 60, 'max_requests': 100}    # 기본값
        }
        # 각 거래소별 마지막 429 오류 시간
        self.last_rate_limit_hit = {}
        # 요청 이력
        self.request_history = {}
        # 로거 설정
        self.logger = get_logger('rate_limit_manager')
        
    def register_request(self, exchange_id, endpoint=None):
        """
        API 요청 등록 및 제한 확인
        
        Args:
            exchange_id (str): 거래소 ID
            endpoint (str, optional): 특정 엔드포인트
            
        Returns:
            bool: 요청 가능 여부
        """
        current_time = time.time()
        exchange_id = exchange_id.lower()
        
        # 거래소가 등록되어 있지 않으면 초기화
        if exchange_id not in self.request_counters:
            self.request_counters[exchange_id] = []
            self.request_history[exchange_id] = []
        
        # 요청 이력 추가
        self.request_counters[exchange_id].append(current_time)
        
        # 레이트 리미트 설정 가져오기
        rate_limit = self.rate_limits.get(exchange_id, self.rate_limits['default'])
        window_size = rate_limit['window_size']
        max_requests = rate_limit['max_requests']
        
        # 윈도우 내 요청만 유지
        self.request_counters[exchange_id] = [t for t in self.request_counters[exchange_id] 
                                             if current_time - t < window_size]
        
        # 현재 요청 수
        current_requests = len(self.request_counters[exchange_id])
        
        # 요청 제한 임계치 (안전 마진 20%)
        safe_threshold = int(max_requests * 0.8)
        
        # 제한에 근접했는지 확인
        if current_requests > safe_threshold:
            wait_time = max(0.1, window_size / max_requests * 2)  # 동적 대기 시간
            self.logger.warning(f"{exchange_id} 요청 제한 근접: {current_requests}/{max_requests}. {wait_time:.2f}초 대기")
            time.sleep(wait_time)
            
        # 제한 초과 확인
        if current_requests >= max_requests:
            self.logger.critical(f"{exchange_id} 요청 제한 초과: {current_requests}/{max_requests}")
            last_hit_time = self.last_rate_limit_hit.get(exchange_id, 0)
            
            # 최근 요청 제한 초과가 발생했으면 대기 시간 증가
            if current_time - last_hit_time < window_size * 2:
                wait_time = window_size  # 윈도우 크기만큼 대기
                self.logger.critical(f"요청 제한 반복 초과. {wait_time}초 동안 대기")
                time.sleep(wait_time)
            
            self.last_rate_limit_hit[exchange_id] = current_time
            return False
            
        return True
    
    def handle_rate_limit_error(self, exchange_id):
        """
        레이트 리미트 오류 처리
        
        Args:
            exchange_id (str): 거래소 ID
            
        Returns:
            float: 권장 대기 시간
        """
        current_time = time.time()
        exchange_id = exchange_id.lower()
        
        # 마지막 요청 제한 초과 기록
        self.last_rate_limit_hit[exchange_id] = current_time
        
        # 레이트 리미트 설정 가져오기
        rate_limit = self.rate_limits.get(exchange_id, self.rate_limits['default'])
        window_size = rate_limit['window_size']
        
        # 최근 요청 이력 기록
        if exchange_id not in self.request_history:
            self.request_history[exchange_id] = []
        
        self.request_history[exchange_id].append(current_time)
        
        # 대기 시간 계산 (최근 초과 빈도에 따라 조정)
        recent_hits = [t for t in self.request_history[exchange_id] 
                       if current_time - t < window_size * 5]  # 5배 윈도우 기간 내 초과
        
        wait_time = window_size * (1 + 0.5 * len(recent_hits))
        wait_time = min(wait_time, window_size * 5)  # 최대 5배 윈도우 시간
        
        # 모든 요청 카운터 리셋 (안전을 위해)
        if exchange_id in self.request_counters:
            self.request_counters[exchange_id] = []
        
        self.logger.warning(f"{exchange_id} 요청 제한 초과 감지. {wait_time:.2f}초 대기")
        return wait_time

# 글로벌 레이트 리미트 관리자 인스턴스
rate_limit_manager = RateLimitManager()

# 오류 로깅 및 분석 클래스
class ErrorAnalyzer:
    """오류 로깅 및 분석 클래스"""
    
    def __init__(self, log_dir=None):
        """
        오류 분석기 초기화
        
        Args:
            log_dir (str, optional): 로그 디렉토리
        """
        self.logger = get_logger('error_analyzer')
        self.error_counts = {}
        self.error_history = []
        self.recurring_errors = {}
        self.critical_errors = set()
        
        # 로그 디렉토리 설정
        if log_dir is None:
            import os
            from src.config import DATA_DIR
            log_dir = os.path.join(DATA_DIR, 'error_logs')
        
        os.makedirs(log_dir, exist_ok=True)
        self.log_dir = log_dir
        self.error_log_path = os.path.join(log_dir, 'error_analysis.json')
        
        # 기존 로그 로드
        self._load_error_log()
    
    def _load_error_log(self):
        """기존 오류 로그 파일 로드"""
        try:
            if os.path.exists(self.error_log_path):
                with open(self.error_log_path, 'r') as f:
                    data = json.load(f)
                    self.error_counts = data.get('error_counts', {})
                    self.recurring_errors = data.get('recurring_errors', {})
                    self.critical_errors = set(data.get('critical_errors', []))
        except Exception as e:
            self.logger.error(f"오류 로그 로드 실패: {e}")
    
    def _save_error_log(self):
        """현재 오류 통계 저장"""
        try:
            data = {
                'error_counts': self.error_counts,
                'recurring_errors': self.recurring_errors,
                'critical_errors': list(self.critical_errors),
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.error_log_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"오류 로그 저장 실패: {e}")
    
    def log_error(self, error_type, error_message, context=None, is_critical=False):
        """
        오류 로깅 및 분석
        
        Args:
            error_type (str): 오류 유형
            error_message (str): 오류 메시지
            context (dict, optional): 오류 발생 컨텍스트 정보
            is_critical (bool): 치명적 오류 여부
            
        Returns:
            dict: 오류 분석 결과
        """
        current_time = datetime.now()
        
        # 오류 정보 구성
        error_info = {
            'type': error_type,
            'message': error_message,
            'timestamp': current_time.isoformat(),
            'context': context or {}
        }
        
        # 오류 기록
        self.error_history.append(error_info)
        
        # 오류 발생 횟수 증가
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
        
        # 반복 오류 탐지
        error_key = f"{error_type}:{error_message}"
        if error_key not in self.recurring_errors:
            self.recurring_errors[error_key] = {
                'count': 0,
                'first_seen': current_time.isoformat(),
                'last_seen': current_time.isoformat(),
                'intervals': []
            }
        else:
            last_seen = datetime.fromisoformat(self.recurring_errors[error_key]['last_seen'])
            interval = (current_time - last_seen).total_seconds()
            self.recurring_errors[error_key]['intervals'].append(interval)
            self.recurring_errors[error_key]['last_seen'] = current_time.isoformat()
        
        self.recurring_errors[error_key]['count'] += 1
        
        # 치명적 오류 기록
        if is_critical:
            self.critical_errors.add(error_key)
        
        # 주기적 저장 (10번째 오류마다)
        if sum(self.error_counts.values()) % 10 == 0:
            self._save_error_log()
        
        # 오류 분석
        analysis_result = self._analyze_error(error_key)
        
        return analysis_result
    
    def _analyze_error(self, error_key):
        """
        오류 분석 수행
        
        Args:
            error_key (str): 오류 키
            
        Returns:
            dict: 분석 결과
        """
        if error_key not in self.recurring_errors:
            return {'is_recurring': False}
        
        error_data = self.recurring_errors[error_key]
        
        # 반복 오류 분석
        count = error_data['count']
        intervals = error_data.get('intervals', [])
        
        # 오류 패턴 분석
        is_recurring = count >= 3
        is_frequent = count >= 5 and (sum(intervals[-5:]) / max(1, len(intervals[-5:]))) < 300  # 최근 5번의 간격이 평균 5분 이내
        is_critical = error_key in self.critical_errors
        
        return {
            'is_recurring': is_recurring,
            'is_frequent': is_frequent,
            'is_critical': is_critical,
            'count': count,
            'recommendation': self._generate_recommendation(is_recurring, is_frequent, is_critical)
        }
    
    def _generate_recommendation(self, is_recurring, is_frequent, is_critical):
        """오류 대응 권장사항 생성"""
        if is_critical:
            return "시스템 관리자의 즉각적인 조치가 필요합니다. 시스템을 중지하고 문제를 해결하세요."
        elif is_frequent:
            return "이 오류가 자주 발생하고 있습니다. 즉시 조사하고 원인을 해결하세요."
        elif is_recurring:
            return "이 오류가 반복적으로 발생하고 있습니다. 주의 깊게 모니터링하세요."
        else:
            return "정기적으로 이 오류의 발생 빈도를 모니터링하세요."

# 글로벌 오류 분석기 인스턴스
error_analyzer = ErrorAnalyzer()

# 에러 유형 정의
class BotError(Exception):
    """암호화폐 봇 관련 기본 예외 클래스"""
    def __init__(self, message, error_code=None, original_exception=None, **kwargs):
        self.message = message
        self.error_code = error_code
        self.original_exception = original_exception
        self.timestamp = datetime.now()
        self.additional_info = kwargs
        super().__init__(self.message)
    
    def to_dict(self):
        """오류 정보를 사전 형태로 반환"""
        result = {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'timestamp': self.timestamp.isoformat()
        }
        
        if self.error_code:
            result['error_code'] = self.error_code
            
        if self.additional_info:
            result['additional_info'] = self.additional_info
            
        return result

# 구체적인 에러 유형
class APIError(BotError):
    """외부 API 통신 관련 오류"""
    def __init__(self, message, error_code=None, original_exception=None, endpoint=None, status_code=None, **kwargs):
        self.endpoint = endpoint
        self.status_code = status_code
        super().__init__(message, error_code or 'API_ERROR', original_exception, endpoint=endpoint, status_code=status_code, **kwargs)

class DatabaseError(BotError):
    """데이터베이스 작업 관련 오류"""
    def __init__(self, message, error_code=None, original_exception=None, operation=None, **kwargs):
        self.operation = operation
        super().__init__(message, error_code or 'DB_ERROR', original_exception, operation=operation, **kwargs)

class TradeError(BotError):
    """거래 처리 관련 오류"""
    def __init__(self, message, error_code=None, original_exception=None, symbol=None, order_type=None, side=None, **kwargs):
        self.symbol = symbol
        self.order_type = order_type
        self.side = side
        super().__init__(message, error_code or 'TRADE_ERROR', original_exception, 
                         symbol=symbol, order_type=order_type, side=side, **kwargs)

class ConfigError(BotError):
    """설정 관련 오류"""
    def __init__(self, message, error_code=None, original_exception=None, config_key=None, **kwargs):
        self.config_key = config_key
        super().__init__(message, error_code or 'CONFIG_ERROR', original_exception, config_key=config_key, **kwargs)

class AuthenticationError(APIError):
    """인증 관련 오류"""
    def __init__(self, message, error_code=None, original_exception=None, **kwargs):
        super().__init__(message, error_code or 'AUTH_ERROR', original_exception, **kwargs)

class MarketTypeError(BotError):
    """시장 타입(현물/선물) 관련 오류"""
    def __init__(self, message, error_code=None, original_exception=None, market_type=None, **kwargs):
        self.market_type = market_type
        super().__init__(message, error_code or 'MARKET_TYPE_ERROR', original_exception, market_type=market_type, **kwargs)

class OrderNotFound(TradeError):
    """주문을 찾을 수 없을 때 발생하는 오류"""
    def __init__(self, message, error_code=None, original_exception=None, order_id=None, **kwargs):
        self.order_id = order_id
        super().__init__(message, error_code or 'ORDER_NOT_FOUND', original_exception, order_id=order_id, **kwargs)

class RateLimitExceeded(APIError):
    """요청 제한 초과 관련 오류"""
    def __init__(self, message, error_code=None, original_exception=None, retry_after=None, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, error_code or 'RATE_LIMIT_EXCEEDED', original_exception, retry_after=retry_after, **kwargs)

# 네트워크 관련 오류
class NetworkError(BotError):
    """네트워크 연결 관련 오류"""
    def __init__(self, message, error_code=None, original_exception=None, host=None, **kwargs):
        self.host = host
        super().__init__(message, error_code or 'NETWORK_ERROR', original_exception, host=host, **kwargs)

class ConnectionTimeout(NetworkError):
    """연결 시간 초과 오류"""
    def __init__(self, message, error_code=None, original_exception=None, timeout_seconds=None, **kwargs):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, error_code or 'CONNECTION_TIMEOUT', original_exception, 
                         timeout_seconds=timeout_seconds, **kwargs)

class RequestTimeout(NetworkError):
    """요청 시간 초과 오류"""
    def __init__(self, message, error_code=None, original_exception=None, timeout_seconds=None, **kwargs):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, error_code or 'REQUEST_TIMEOUT', original_exception, 
                         timeout_seconds=timeout_seconds, **kwargs)

class ConnectionReset(NetworkError):
    """연결 재설정 오류"""
    def __init__(self, message, error_code=None, original_exception=None, **kwargs):
        super().__init__(message, error_code or 'CONNECTION_RESET', original_exception, **kwargs)

# 데이터 관련 오류
class DataError(BotError):
    """데이터 처리 관련 오류"""
    def __init__(self, message, error_code=None, original_exception=None, data_source=None, **kwargs):
        self.data_source = data_source
        super().__init__(message, error_code or 'DATA_ERROR', original_exception, data_source=data_source, **kwargs)

class InvalidDataFormat(DataError):
    """잘못된 데이터 형식 오류"""
    def __init__(self, message, error_code=None, original_exception=None, expected_format=None, received_format=None, **kwargs):
        self.expected_format = expected_format
        self.received_format = received_format
        super().__init__(message, error_code or 'INVALID_DATA_FORMAT', original_exception, 
                         expected_format=expected_format, received_format=received_format, **kwargs)

class MarketDataError(DataError):
    """시장 데이터 관련 오류"""
    def __init__(self, message, error_code=None, original_exception=None, market=None, data_type=None, **kwargs):
        self.market = market
        self.data_type = data_type
        super().__init__(message, error_code or 'MARKET_DATA_ERROR', original_exception, 
                         market=market, data_type=data_type, **kwargs)

# 포지션 관련 오류
class PositionError(BotError):
    """포지션 관리 관련 오류"""
    def __init__(self, message, error_code=None, original_exception=None, symbol=None, position_id=None, **kwargs):
        self.symbol = symbol
        self.position_id = position_id
        super().__init__(message, error_code or 'POSITION_ERROR', original_exception, 
                         symbol=symbol, position_id=position_id, **kwargs)

class PositionNotFound(PositionError):
    """포지션을 찾을 수 없을 때 발생하는 오류"""
    def __init__(self, message, error_code=None, original_exception=None, symbol=None, position_id=None, **kwargs):
        super().__init__(message, error_code or 'POSITION_NOT_FOUND', original_exception, 
                         symbol=symbol, position_id=position_id, **kwargs)

class MarginLevelCritical(PositionError):
    """마진 레벨이 위험 수준에 도달했을 때 발생하는 오류"""
    def __init__(self, message, error_code=None, original_exception=None, margin_level=None, threshold=None, **kwargs):
        self.margin_level = margin_level
        self.threshold = threshold
        super().__init__(message, error_code or 'MARGIN_LEVEL_CRITICAL', original_exception, 
                         margin_level=margin_level, threshold=threshold, **kwargs)

# 오류 처리 유틸리티 함수
def calculate_backoff(attempt, base_delay=1, max_delay=60, jitter=True, adaptive=False, stability_score=1.0):
    """
    회귀 시간 계산을 위한 고급 백오프 알고리즘
    
    Args:
        attempt (int): 현재 시도 횟수
        base_delay (float): 기본 지연 시간(초)
        max_delay (float): 최대 지연 시간(초)
        jitter (bool): 야팔 적용 여부
        adaptive (bool): 적응형 백오프 사용 여부
        stability_score (float): 연결 안정성 점수 (0.1 ~ 1.0, 1.0이 가장 안정적)
        
    Returns:
        float: 계산된 적절한 대기 시간(초)
    """
    # 기본 지수 백오프 계산 (2^attempt * base_delay)
    delay = base_delay * (2 ** (attempt - 1))
    
    # 적응형 백오프인 경우 안정성 점수 반영
    if adaptive and stability_score < 1.0:
        # 안정성이 낮을수록 더 긴 대기 시간
        delay = delay / max(stability_score, 0.1)  # 0.1을 최소값으로 설정
    
    # 야팔 추가 (0.5 ~ 1.5 사이의 랜덤값 곱하기)
    if jitter:
        jitter_factor = random.uniform(0.5, 1.5)
        delay = delay * jitter_factor
    
    # 최대 지연 시간으로 제한
    return min(delay, max_delay)


def detect_error_type(error, retry_on_status_codes=None):
    """
    오류 유형 분석 및 분류
    
    Args:
        error (Exception): 발생한 예외
        retry_on_status_codes (list): 재시도할 HTTP 상태 코드 목록
        
    Returns:
        tuple: (오류유형, 상태코드, 재시도가능여부)
    """
    # 기본값 설정
    if retry_on_status_codes is None:
        retry_on_status_codes = [429, 500, 502, 503, 504, 520, 521, 522, 524]
    
    error_type = 'general'  # 기본 유형
    status_code = None
    is_retryable = False
    
    # 상태 코드 추출
    if hasattr(error, 'status_code'):
        status_code = error.status_code
    elif hasattr(error, 'code'):
        status_code = error.code
    elif hasattr(error, 'response') and hasattr(error.response, 'status_code'):
        status_code = error.response.status_code
    
    # 오류 유형 분류
    error_str = str(error).lower()
    
    # 레이트 리미트 오류 확인
    if status_code == 429 or "rate limit" in error_str or "too many requests" in error_str:
        error_type = 'rate_limit'
        is_retryable = True
    
    # 네트워크 오류 확인
    elif (
        isinstance(error, (ConnectionError, TimeoutError)) or
        "connection" in error_str or
        "timeout" in error_str or
        "network" in error_str or
        "socket" in error_str or
        "unreachable" in error_str or
        (status_code and status_code in retry_on_status_codes)
    ):
        error_type = 'network'
        is_retryable = True
    
    # 인증 오류 확인
    elif (
        status_code in [401, 403] or
        "auth" in error_str or
        "unauthorized" in error_str or
        "permission" in error_str or
        "denied" in error_str
    ):
        error_type = 'authentication'
        is_retryable = False  # 인증 오류는 일반적으로 재시도해도 동일한 결과
    
    # 거래 오류 확인
    elif (
        "order" in error_str or
        "trade" in error_str or
        "position" in error_str
    ):
        error_type = 'trade'
        # 일부 거래 오류는 재시도 가능
        is_retryable = "not found" not in error_str and "insufficient" not in error_str
    
    # 데이터베이스 오류 확인
    elif (
        "database" in error_str or 
        "db" in error_str or 
        "sql" in error_str
    ):
        error_type = 'database'
        # 일시적 DB 오류는 재시도 가능
        is_retryable = "constraint" not in error_str and "duplicate" not in error_str
    
    # 데이터 형식 오류 확인
    elif (
        "json" in error_str or
        "format" in error_str or
        "parse" in error_str or
        "invalid" in error_str
    ):
        error_type = 'data_format'
        is_retryable = False  # 형식 오류는 재시도해도 동일한 결과
    
    return error_type, status_code, is_retryable


def extract_error_context(func, args, kwargs, error):
    """
    오류 문맥 정보 추출
    
    Args:
        func (callable): 오류가 발생한 함수
        args (tuple): 함수 인자
        kwargs (dict): 함수 키워드 인자
        error (Exception): 발생한 예외
        
    Returns:
        dict: 오류 문맥 정보
    """
    context = {
        'function': func.__name__,
        'module': func.__module__,
        'error_type': error.__class__.__name__,
        'error_message': str(error),
        'timestamp': datetime.now().isoformat()
    }
    
    # 거래소 ID 추출 시도
    exchange_id = None
    for arg in args:
        if hasattr(arg, 'exchange_id'):
            exchange_id = arg.exchange_id
            break
        elif isinstance(arg, dict) and 'exchange_id' in arg:
            exchange_id = arg['exchange_id']
            break
    
    if exchange_id is None and 'exchange_id' in kwargs:
        exchange_id = kwargs['exchange_id']
    
    if exchange_id:
        context['exchange_id'] = exchange_id
    
    # 심볼 추출 시도
    symbol = None
    for arg in args:
        if hasattr(arg, 'symbol'):
            symbol = arg.symbol
            break
        elif isinstance(arg, dict) and 'symbol' in arg:
            symbol = arg['symbol']
            break
    
    if symbol is None and 'symbol' in kwargs:
        symbol = kwargs['symbol']
    
    if symbol:
        context['symbol'] = symbol
    
    # 안전한 인자 정보만 추가 (대용량 데이터나 비밀 정보 제외)
    safe_args = []
    for arg in args:
        if isinstance(arg, (str, int, float, bool)) or arg is None:
            safe_args.append(arg)
        elif isinstance(arg, (list, tuple)) and len(arg) < 10:
            safe_args.append(str(arg))
        else:
            safe_args.append(f"<{type(arg).__name__}>")
    
    safe_kwargs = {}
    for k, v in kwargs.items():
        if k not in ['password', 'apiKey', 'secret', 'private_key', 'token']:
            if isinstance(v, (str, int, float, bool)) or v is None:
                safe_kwargs[k] = v
            elif isinstance(v, (list, tuple)) and len(v) < 10:
                safe_kwargs[k] = str(v)
            else:
                safe_kwargs[k] = f"<{type(v).__name__}>"
    
    context['args'] = str(safe_args)
    context['kwargs'] = str(safe_kwargs)
    
    return context

# 통합 오류 처리 데코레이터
def error_handler(
    func=None, 
    retry_count=3, 
    base_delay=1.0, 
    max_delay=60.0,
    log_level="error", 
    reraise=True,
    handler_type="general",  # "api", "network", "db", "trade"
    retry_on_exceptions=None,
    retry_on_status_codes=None,
    adaptive_backoff=False,
    collect_context=True,
    rate_limit_manager=None,
    error_analyzer=None
):
    """
    통합 오류 처리 데코레이터
    
    Args:
        func (callable, optional): 데코레이트할 함수
        retry_count (int): 재시도 횟수
        base_delay (float): 기본 지연 시간(초)
        max_delay (float): 최대 지연 시간(초) 
        log_level (str): 로깅 레벨 (error, warning, info)
        reraise (bool): 모든 재시도 실패 후 예외를 다시 발생시킬지 여부
        handler_type (str): 오류 처리기 유형 (general, api, network, db, trade)
        retry_on_exceptions (list): 재시도할 예외 클래스 목록
        retry_on_status_codes (list): 재시도할 HTTP 상태 코드 목록
        adaptive_backoff (bool): 적응형 백오프 사용 여부
        collect_context (bool): 오류 컨텍스트 수집 여부
        rate_limit_manager: 레이트 리미트 관리자 인스턴스
        error_analyzer: 오류 분석기 인스턴스
        
    Returns:
        함수를 래핑하는 데코레이터
    """
    if retry_on_exceptions is None:
        # 핸들러 유형에 따른 기본 재시도 예외 설정
        if handler_type == "api":
            retry_on_exceptions = (ConnectionError, TimeoutError, RateLimitExceeded, NetworkError)
        elif handler_type == "network":
            retry_on_exceptions = (ConnectionError, TimeoutError, NetworkError, ConnectionReset, RequestTimeout, ConnectionTimeout)
        elif handler_type == "db":
            retry_on_exceptions = (DatabaseError, ConnectionError, TimeoutError)
        elif handler_type == "trade":
            retry_on_exceptions = (TradeError, APIError, NetworkError)
        else:
            retry_on_exceptions = (Exception,)  # 기본값: 모든 예외

    if retry_on_status_codes is None and handler_type in ["api", "network"]:
        retry_on_status_codes = [429, 500, 502, 503, 504, 520, 521, 522, 524]
        
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 레이트 리미트 관리자와 오류 분석기 인스턴스 결정
            nonlocal rate_limit_manager, error_analyzer
            if rate_limit_manager is None and 'rate_limit_manager' in globals():
                rate_limit_manager = globals()['rate_limit_manager']
            if error_analyzer is None and 'error_analyzer' in globals():
                error_analyzer = globals()['error_analyzer']

            # 상태 추적을 위한 변수
            attempts = 0
            last_exception = None
            connection_stability = 1.0
            success_streak = 0
            
            # 거래소 ID 추출 시도 (API 요청 레이트 리미트용)
            exchange_id = None
            for arg in args:
                if hasattr(arg, 'exchange_id'):
                    exchange_id = arg.exchange_id
                    break
                elif isinstance(arg, dict) and 'exchange_id' in arg:
                    exchange_id = arg['exchange_id']
                    break
            
            if exchange_id is None and 'exchange_id' in kwargs:
                exchange_id = kwargs['exchange_id']
            
            # API 요청 레이트 리미트 확인
            if exchange_id and rate_limit_manager and handler_type in ["api", "network"]:
                rate_limit_manager.register_request(exchange_id)
            
            # 재시도 루프
            while attempts <= retry_count:
                try:
                    # 함수 실행
                    result = func(*args, **kwargs)
                    
                    # 성공 스트릭 및 연결 안정성 업데이트
                    if attempts > 0:  # 재시도 후 성공한 경우
                        success_streak += 1
                        if success_streak >= 5:
                            connection_stability = min(1.0, connection_stability + 0.1)
                    
                    return result
                
                except Exception as e:
                    attempts += 1
                    last_exception = e
                    success_streak = 0
                    
                    # 연결 안정성 감소
                    if handler_type in ["api", "network"]:
                        connection_stability = max(0.1, connection_stability - 0.2)
                    
                    # 재시도 가능한 예외인지 확인
                    should_retry = isinstance(e, retry_on_exceptions)
                    
                    # 오류 타입 감지
                    error_type, status_code, is_retryable = detect_error_type(e, retry_on_status_codes)
                    should_retry = should_retry or is_retryable
                    
                    # 레이트 리미트 오류 처리
                    if error_type == 'rate_limit' and exchange_id and rate_limit_manager:
                        wait_time = rate_limit_manager.handle_rate_limit_error(exchange_id)
                        # 로그 레벨에 따른 로깅
                        if log_level == "error":
                            error_logger.error(f"레이트 리미트 초과: {e}. {wait_time:.2f}초 대기 후 재시도 ({attempts}/{retry_count})")
                        else:
                            error_logger.warning(f"레이트 리미트 초과: {e}. {wait_time:.2f}초 대기 후 재시도 ({attempts}/{retry_count})")
                        
                        time.sleep(wait_time)
                        should_retry = True
                        continue
                    
                    # 로깅
                    log_message = f"함수 {func.__name__} 실행 중 오류 발생: {e}"
                    
                    if log_level == "error":
                        error_logger.error(log_message)
                        error_logger.debug(traceback.format_exc())
                    elif log_level == "warning":
                        error_logger.warning(log_message)
                    elif log_level == "info":
                        error_logger.info(log_message)
                    
                    # 컨텍스트 수집 및 오류 분석
                    if collect_context and error_analyzer:
                        context = extract_error_context(func, args, kwargs, e)
                        # 마지막 시도에서 실패한 경우 critical=True로 설정
                        is_critical = attempts >= retry_count
                        error_analyzer.log_error(
                            error_type=error_type,
                            error_message=str(e),
                            context=context,
                            is_critical=is_critical
                        )
                    
                    # 재시도 여부 결정
                    if not should_retry or attempts > retry_count:
                        break
                    
                    # 백오프 계산
                    delay = calculate_backoff(
                        attempt=attempts,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        adaptive=adaptive_backoff,
                        stability_score=connection_stability if handler_type in ["api", "network"] else 1.0
                    )
                    
                    error_logger.info(f"함수 {func.__name__} 재시도 중 ({attempts}/{retry_count}). {delay:.2f}초 대기...")
                    time.sleep(delay)
            
            # 모든 재시도 실패 처리
            if last_exception and reraise:
                # 핸들러 유형에 맞게 예외 변환
                if isinstance(last_exception, retry_on_exceptions):
                    # 기존 예외 종류 유지
                    raise last_exception
                elif handler_type == "api" and error_type == 'rate_limit':
                    raise RateLimitExceeded(f"최대 재시도 횟수 초과 ({retry_count}): {last_exception}")
                elif handler_type == "network" or error_type == 'network':
                    raise NetworkError(f"네트워크 오류 지속 ({retry_count}회 재시도 후): {last_exception}")
                elif handler_type == "db":
                    raise DatabaseError(f"데이터베이스 오류 지속 ({retry_count}회 재시도 후): {last_exception}")
                elif handler_type == "trade":
                    raise TradeError(f"거래 오류 지속 ({retry_count}회 재시도 후): {last_exception}")
                else:
                    # 기본 동작: 원래 예외 다시 발생
                    raise last_exception
            
            # reraise가 False이고 모든 시도가 실패한 경우 None 반환
            return None
        return wrapper
    return decorator

# 자주 사용하는 데코레이터 미리 정의

def simple_error_handler(default_return=None, log_level="error"):
    """
    오류 발생시 단순히 로깅하고 기본값을 반환하는 간단한 데코레이터
    코드베이스에서 흔한 단순 try-except 패턴에 사용
    
    Args:
        default_return: 예외 발생시 반환할 기본값
        log_level (str): 로깅 레벨 (error, warning, info)
    
    Returns:
        데코레이터 함수
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 스택 트레이스 가져오기
                trace = traceback.format_exc()
                
                # 예외 유형 파악
                exception_name = e.__class__.__name__
                func_name = func.__name__
                
                # 로깅 레벨에 따라 로깅
                logger = get_logger(func.__module__)
                if log_level == "error":
                    error_logger.error(f"Error in {func_name}: {exception_name}: {str(e)}\n{trace}")
                elif log_level == "warning":
                    error_logger.warning(f"함수 {func.__name__} 실행 오류: {e}")
                elif log_level == "info":
                    error_logger.info(f"함수 {func.__name__} 실행 오류: {e}")
                
                # 오류 분석기에 기록
                if 'error_analyzer' in globals():
                    context = extract_error_context(func, args, kwargs, e)
                    error_analyzer.log_error(
                        error_type='general',
                        error_message=str(e),
                        context=context,
                        is_critical=False
                    )
                
                return default_return
        return wrapper
    return decorator


def safe_execution(func=None, retry_count=0, log_level="warning"):
    """
    일반적인 함수에 대한 오류 처리 (예외 재발생 안함)
    
    Args:
        func (callable, optional): 데코레이트할 함수
        retry_count (int): 재시도 횟수
        log_level (str): 로그 레벨
    """
    return error_handler(
        func=func, 
        retry_count=retry_count, 
        log_level=log_level, 
        reraise=False,
        handler_type="general"
    )

def api_error_handler(func=None, retry_count=3, base_delay=2, max_delay=30):
    """
    API 요청 관련 오류 처리 데코레이터
    
    Args:
        func (callable, optional): 데코레이트할 함수
        retry_count (int): 최대 재시도 횟수
        base_delay (float): 기본 지연 시간(초)
        max_delay (float): 최대 지연 시간(초)
    """
    return error_handler(
        func=func,
        retry_count=retry_count,
        base_delay=base_delay,
        max_delay=max_delay,
        handler_type="api",
        log_level="warning",
        retry_on_status_codes=[400, 401, 403, 404, 408, 429, 500, 502, 503, 504, 520, 521, 522, 524],
        adaptive_backoff=True,
        collect_context=True
    )

def network_error_handler(func=None, retry_count=5, base_delay=2, max_delay=60):
    """
    네트워크 오류에 특화된 오류 처리 데코레이터
    
    Args:
        func: 데코레이트할 함수
        retry_count (int): 최대 재시도 횟수
        base_delay (float): 기본 지연 시간(초)
        max_delay (float): 최대 지연 시간(초)
    """
    # 재시도할 네트워크 예외 유형
    network_exceptions = [
        NetworkError, ConnectionTimeout, RequestTimeout, ConnectionReset,
        ConnectionError, TimeoutError
    ]
    
    if func is None:
        return lambda f: network_error_handler(f, retry_count, base_delay, max_delay)
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        attempts = 0
        last_exception = None
        logger = get_logger(func.__module__)
        
        while attempts <= retry_count:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                attempts += 1
                last_exception = e
                error_str = str(e).lower()
                
                # 네트워크 오류인지 확인
                is_network_error = any(isinstance(e, exc) for exc in network_exceptions) or \
                                  any(term in error_str for term in ['connection', 'timeout', 'network', 'reset'])
                
                if is_network_error:
                    # 지수 백오프 적용
                    delay = calculate_backoff(attempts, base_delay=base_delay, max_delay=max_delay)
                    
                    # 네트워크 오류 유형 분류
                    if "timeout" in error_str:
                        error_type = "Timeout"
                    elif "connection" in error_str and "refused" in error_str:
                        error_type = "Connection refused"
                    elif "reset" in error_str:
                        error_type = "Connection reset"
                    else:
                        error_type = "Network error"
                    
                    logger.warning(f"{error_type}: {str(e)}. Retrying {attempts}/{retry_count} after {delay:.2f}s")
                    time.sleep(delay)
                    continue
                else:
                    # 네트워크 오류가 아니면 바로 예외 발생
                    if isinstance(e, BotError):
                        raise
                    else:
                        raise BotError(f"Error in {func.__name__}: {str(e)}", original_exception=e)
def network_error_handler(func=None, retry_count=5, base_delay=2, max_delay=60):
    """
    네트워크 오류에 특화된 오류 처리 데코레이터
    
    Args:
        func (callable, optional): 데코레이트할 함수
        retry_count (int): 최대 재시도 횟수
        base_delay (float): 기본 지연 시간(초)
        max_delay (float): 최대 지연 시간(초)
    """
    return error_handler(
        func=func,
        retry_count=retry_count,
        base_delay=base_delay,
        max_delay=max_delay,
        handler_type="network",
        log_level="warning",
        adaptive_backoff=True,
        retry_on_exceptions=(ConnectionError, TimeoutError),
        collect_context=True
    )

def db_error_handler(func=None, retry_count=3, base_delay=1, max_delay=10):
    """
    데이터베이스 작업에 대한 오류 처리 데코레이터
    
    Args:
        func (callable, optional): 데코레이트할 함수
        retry_count (int): 최대 재시도 횟수
        base_delay (float): 기본 지연 시간(초)
        max_delay (float): 최대 지연 시간(초)
    """
    return error_handler(
        func=func,
        retry_count=retry_count,
        base_delay=base_delay,
        max_delay=max_delay,
        handler_type="db",
        log_level="error",
        adaptive_backoff=False,
        retry_on_exceptions=Exception,  # 대부분의 DB 오류는 일시적일 수 있음
        collect_context=True
    )

def trade_error_handler(func=None, retry_count=1, base_delay=1, max_delay=5):
    """
    거래 작업 오류 처리 데코레이터
    
    Args:
        func (callable, optional): 데코레이트할 함수
        retry_count (int): 최대 재시도 횟수
        base_delay (float): 기본 지연 시간(초)
        max_delay (float): 최대 지연 시간(초)
    """
    return error_handler(
        func=func,
        retry_count=retry_count,
        base_delay=base_delay,
        max_delay=max_delay,
        handler_type="trade",
        log_level="error",
        retry_on_exceptions=(NetworkError, APIError),  # 네트워크 관련 오류만 재시도
        collect_context=True
    )

def safe_execution(func=None, retry_count=0, log_level="warning"):
    """
    일반적인 함수에 대한 오류 처리 (예외 재발생 안함)
    
    Args:
        func (callable, optional): 데코레이트할 함수
        retry_count (int): 재시도 횟수
        log_level (str): 로그 레벨
    """
    return error_handler(
        func=func,
        retry_count=retry_count,
        log_level=log_level,
        reraise=False,
        handler_type="general"
    )

# 유틸리티 함수
def format_error_response(error, include_traceback=False):
    """API 응답을 위한 오류 포맷팅"""
    if isinstance(error, BotError):
        response = {
            'error': {
                'type': error.__class__.__name__,
                'message': str(error),
                'code': error.error_code
            }
        }
    else:
        response = {
            'error': {
                'type': error.__class__.__name__,
                'message': str(error)
            }
        }
    
    if include_traceback:
        response['error']['traceback'] = traceback.format_exc()
    
    return response


def advanced_network_error_handler(func=None, retry_count=5, base_delay=2, max_delay=120, 
                                   adaptive_backoff=True, retry_on_status_codes=None):
    """
    네트워크 오류에 대한 고급 오류 처리 데코레이터
    
    Args:
        func (callable, optional): 데코레이트할 함수
        retry_count (int): 최대 재시도 횟수
        base_delay (float): 기본 지연 시간(초)
        max_delay (float): 최대 지연 시간(초)
        adaptive_backoff (bool): 적응형 백오프 사용 여부
        retry_on_status_codes (list): 재시도할 HTTP 상태 코드 목록
    """
    if retry_on_status_codes is None:
        retry_on_status_codes = [408, 429, 500, 502, 503, 504, 507, 509, 520, 521, 522, 524, 598, 599]
        
    return error_handler(
        func=func,
        retry_count=retry_count,
        base_delay=base_delay,
        max_delay=max_delay,
        handler_type="network",
        log_level="warning",
        retry_on_status_codes=retry_on_status_codes,
        adaptive_backoff=adaptive_backoff,
        retry_on_exceptions=(ConnectionError, TimeoutError, ConnectionResetError, socket.error),
        collect_context=True
    )
