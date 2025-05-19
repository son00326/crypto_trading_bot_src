#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 에러 처리 유틸리티
import functools
import traceback
import time
from src.logging_config import get_logger, error_logger

# 에러 유형 정의
class BotError(Exception):
    """암호화폐 봇 관련 기본 예외 클래스"""
    def __init__(self, message, error_code=None, original_exception=None):
        self.message = message
        self.error_code = error_code
        self.original_exception = original_exception
        super().__init__(self.message)

# 구체적인 에러 유형
class APIError(BotError):
    """API 통신 관련 오류"""
    pass

class DatabaseError(BotError):
    """데이터베이스 작업 관련 오류"""
    pass

class TradeError(BotError):
    """거래 처리 관련 오류"""
    pass

class ConfigError(BotError):
    """설정 관련 오류"""
    pass

class AuthenticationError(BotError):
    """인증 관련 오류"""
    pass

class MarketTypeError(BotError):
    """시장 타입(현물/선물) 관련 오류"""
    pass

class OrderNotFound(BotError):
    """주문을 찾을 수 없을 때 발생하는 오류"""
    pass

class RateLimitExceeded(BotError):
    """요청 제한 초과 관련 오류"""
    pass

# 네트워크 관련 오류
class NetworkError(BotError):
    """네트워크 연결 관련 오류"""
    pass

class ConnectionTimeout(NetworkError):
    """연결 시간 초과 오류"""
    pass

class RequestTimeout(NetworkError):
    """요청 시간 초과 오류"""
    pass

class ConnectionReset(NetworkError):
    """연결 재설정 오류"""
    pass

# 데이터 관련 오류
class DataError(BotError):
    """데이터 처리 관련 오류"""
    pass

class InvalidDataFormat(DataError):
    """잘못된 데이터 형식 오류"""
    pass

class MarketDataError(DataError):
    """시장 데이터 관련 오류"""
    pass

# 포지션 관련 오류
class PositionError(TradeError):
    """포지션 관리 관련 오류"""
    pass

class PositionNotFound(PositionError):
    """포지션을 찾을 수 없을 때 발생하는 오류"""
    pass

class MarginLevelCritical(PositionError):
    """마진 레벨이 위험 수준에 도달했을 때 발생하는 오류"""
    pass

# 유틸리티 함수
def calculate_backoff(attempt, base_delay=1, max_delay=60):
    """
    지수 백오프 지연 시간 계산
    
    Args:
        attempt (int): 현재 시도 횟수
        base_delay (float): 기본 지연 시간(초)
        max_delay (float): 최대 지연 시간(초)
        
    Returns:
        float: 지수 백오프 알고리즘이 적용된 지연 시간
    """
    import random
    # 2^attempt * base_delay + 랜덤 지터(0.1~0.5초)를 적용하여 쌍도 주기 회피
    delay = min(base_delay * (2 ** attempt) + random.uniform(0.1, 0.5), max_delay)
    return delay

# 표준 에러 처리 데코레이터
def handle_errors(retry_count=0, retry_delay=1, max_delay=60, log_level="error", reraise=True, 
                  retry_on_exceptions=None):
    """
    함수의 예외 처리를 위한 데코레이터
    
    Args:
        retry_count (int): 재시도 횟수
        retry_delay (int): 재시도 간 기본 지연 시간(초)
        max_delay (int): 재시도 간 최대 지연 시간(초)
        log_level (str): 로깅 레벨 (error, warning, info)
        reraise (bool): 예외를 다시 발생시킬지 여부
        retry_on_exceptions (list): 재시도할 예외 클래스 목록, None이면 모든 예외에 대해 재시도
    """
    # 기본적으로 네트워크 오류는 항상 재시도
    if retry_on_exceptions is None:
        retry_on_exceptions = [NetworkError, ConnectionTimeout, RequestTimeout, ConnectionReset, RateLimitExceeded]
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            attempts = 0
            last_exception = None
            
            while attempts <= retry_count:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # 예외 정보 기록
                    attempts += 1
                    last_exception = e
                    
                    # 스택 트레이스 가져오기
                    trace = traceback.format_exc()
                    
                    # 예외 유형 파악
                    exception_name = e.__class__.__name__
                    retry_this_exception = any(isinstance(e, exc) for exc in retry_on_exceptions)
                    
                    # 로깅 레벨에 따라 로깅
                    if log_level == "error":
                        error_logger.error(f"Error in {func.__name__}: {exception_name}: {str(e)}\n{trace}")
                    elif log_level == "warning":
                        logger.warning(f"Warning in {func.__name__}: {exception_name}: {str(e)}")
                    else:
                        logger.info(f"Info in {func.__name__}: {exception_name}: {str(e)}")
                    
                    # 재시도 가능한 경우
                    if attempts <= retry_count and retry_this_exception:
                        # 지수 백오프 적용
                        delay = calculate_backoff(attempts, base_delay=retry_delay, max_delay=max_delay)
                        logger.info(f"Retrying {func.__name__} ({attempts}/{retry_count}) after {delay:.2f}s delay...")
                        time.sleep(delay)
                    else:
                        # 더 이상 재시도하지 않거나, 리트라이 대상이 아닌 예외
                        if reraise:
                            # 예외 변환 및 처리
                            if isinstance(e, BotError):
                                raise
                            else:
                                # 함수와 모듈 이름을 기반으로 맞춤형 예외 발생
                                module_name = func.__module__.lower()
                                func_name = func.__name__.lower()
                                
                                if "network" in str(e).lower() or isinstance(e, (ConnectionError, TimeoutError)):
                                    raise NetworkError(f"Network error in {func.__name__}: {str(e)}", original_exception=e)
                                elif "api" in func_name or "exchange" in module_name:
                                    raise APIError(f"API error in {func.__name__}: {str(e)}", original_exception=e)
                                elif "database" in func_name or "db" in module_name:
                                    raise DatabaseError(f"Database error in {func.__name__}: {str(e)}", original_exception=e)
                                elif "trade" in func_name or "order" in func_name:
                                    raise TradeError(f"Trade error in {func.__name__}: {str(e)}", original_exception=e)
                                elif "position" in func_name:
                                    raise PositionError(f"Position error in {func.__name__}: {str(e)}", original_exception=e)
                                else:
                                    raise BotError(f"Error in {func.__name__}: {str(e)}", original_exception=e)
                        break
            return None  # 모든 재시도가 실패한 경우
        return wrapper
    return decorator

# 자주 사용하는 데코레이터 미리 정의
def api_error_handler(func=None, retry_count=3, base_delay=2, max_delay=30):
    """
    API 호출 관련 오류를 처리하는 데코레이터
    API 요청 실패시 자동 재시도를 포함
    
    Args:
        func: 데코레이트할 함수
        retry_count (int): 최대 재시도 횟수
        base_delay (float): 기본 지연 시간(초)
        max_delay (float): 최대 지연 시간(초)
    """
    if func is None:
        return lambda f: api_error_handler(f, retry_count, base_delay, max_delay)
    
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
                
                # 예외 유형 분류
                is_network_error = False
                is_rate_limit = False
                specific_error = None
                
                # 네트워크 오류 확인
                if (isinstance(e, (ConnectionError, TimeoutError)) or 
                    "connection" in error_str or "timeout" in error_str or "network" in error_str):
                    is_network_error = True
                    if "timeout" in error_str:
                        specific_error = RequestTimeout(f"Request timeout: {e}")
                    else:
                        specific_error = NetworkError(f"Network error: {e}")
                
                # API 제한 오류 확인
                elif "limit" in error_str and "rate" in error_str:
                    is_rate_limit = True
                    specific_error = RateLimitExceeded(f"Rate limit exceeded: {e}")
                
                # 그 외 API 관련 오류
                elif "auth" in error_str or "authentication" in error_str or "apikey" in error_str:
                    specific_error = AuthenticationError(f"Authentication error: {e}")
                elif "order not found" in error_str or "not found" in error_str:
                    specific_error = OrderNotFound(f"Order not found: {e}")
                elif "futures" in error_str and "is not supported" in error_str:
                    specific_error = MarketTypeError(f"Market type error: {e}")
                else:
                    specific_error = APIError(f"API error in {func.__name__}: {str(e)}")
                
                # 재시도 가능 확인 (네트워크 오류와 API 제한은 재시도)
                if attempts <= retry_count and (is_network_error or is_rate_limit):
                    # 지수 백오프 적용
                    delay = calculate_backoff(attempts, base_delay=base_delay, max_delay=max_delay)
                    
                    # 로깅
                    if is_rate_limit:
                        logger.warning(f"Rate limit exceeded. Waiting {delay:.2f}s before retry {attempts}/{retry_count}")
                    else:
                        logger.warning(f"Network error: {str(e)}. Retrying {attempts}/{retry_count} after {delay:.2f}s")
                    
                    time.sleep(delay)
                else:
                    # 더 이상 재시도 하지 않음
                    if specific_error:
                        raise specific_error
                    else:
                        raise APIError(f"API error in {func.__name__}: {str(e)}")
                    
        # 모든 재시도 실패
        if last_exception:
            raise APIError(f"All retries failed for {func.__name__}: {str(last_exception)}")
        return None
    return wrapper

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
        
        # 모든 재시도 실패
        if last_exception:
            raise NetworkError(f"All network retries failed ({retry_count}) for {func.__name__}: {str(last_exception)}")
        return None
    
    return wrapper

def db_error_handler(func=None, retry_count=3, base_delay=1, max_delay=10):
    """
    데이터베이스 작업에 대한 에러 처리
    일시적 데이터베이스 연결 오류를 다루도록 개선
    
    Args:
        func: 데코레이트할 함수
        retry_count (int): 최대 재시도 횟수
        base_delay (float): 기본 지연 시간(초)
        max_delay (float): 최대 지연 시간(초)
    """
    if func is None:
        return lambda f: db_error_handler(f, retry_count, base_delay, max_delay)
        
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
                
                # 데이터베이스 연결 오류인지 확인
                is_connection_error = "connection" in error_str or "timeout" in error_str or \
                                    "operational error" in error_str
                
                if is_connection_error and attempts <= retry_count:
                    delay = calculate_backoff(attempts, base_delay=base_delay, max_delay=max_delay)
                    logger.warning(f"Database connection error: {str(e)}. Retrying {attempts}/{retry_count} after {delay:.2f}s")
                    time.sleep(delay)
                else:
                    # 연결 오류가 아니거나 재시도 횟수 초과
                    if isinstance(e, BotError):
                        raise
                    else:
                        raise DatabaseError(f"Database error in {func.__name__}: {str(e)}", original_exception=e)
        
        # 모든 재시도 실패
        if last_exception:
            raise DatabaseError(f"All database retries failed for {func.__name__}: {str(last_exception)}")
        return None
    
    return wrapper

def trade_error_handler(func=None, retry_count=1, base_delay=1):
    """
    거래 작업에 대한 에러 처리
    거래 출력 오류를 재시도 할 수 있음
    
    Args:
        func: 데코레이트할 함수
        retry_count (int): 최대 재시도 횟수
        base_delay (float): 기본 지연 시간(초)    
    """
    if func is None:
        return lambda f: trade_error_handler(f, retry_count, base_delay)
        
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
                
                # 오류 발생 시 일정 시간 후 재시도 (네트워크 오류 같은 경우)
                if isinstance(e, (NetworkError, APIError)) and attempts <= retry_count:
                    delay = base_delay
                    logger.warning(f"Trade error (network related): {str(e)}. Retrying {attempts}/{retry_count} after {delay:.2f}s")
                    time.sleep(delay)
                else:
                    # 다른 유형의 오류는 바로 예외 발생
                    if isinstance(e, BotError):
                        raise
                    else:
                        raise TradeError(f"Trade error in {func.__name__}: {str(e)}", original_exception=e)
        
        # 모든 재시도 실패
        if last_exception:
            raise TradeError(f"All trade retries failed for {func.__name__}: {str(last_exception)}")
        return None
    
    return wrapper

def safe_execution(func=None, retry_count=0, log_level="warning"):
    """
    일반적인 함수에 대한 에러 처리 (예외 재발생 안함)
    
    Args:
        func: 데코레이트할 함수
        retry_count (int): 재시도 횟수
        log_level (str): 로그 레벨
    """
    if func is None:
        return lambda f: safe_execution(f, retry_count, log_level)
    
    return handle_errors(retry_count=retry_count, retry_delay=1, log_level=log_level, reraise=False)(func)

# 유틸리티 함수
def format_error_response(error, include_traceback=False):
    """API 응답을 위한 오류 포맷팅"""
    response = {
        'success': False,
        'error': {
            'message': str(error),
            'type': error.__class__.__name__
        }
    }
    
    if include_traceback:
        response['error']['traceback'] = traceback.format_exc()
    
    if isinstance(error, BotError) and error.error_code:
        response['error']['code'] = error.error_code
        
    return response
