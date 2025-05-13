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

# 에러 처리 데코레이터
def handle_errors(retry_count=0, retry_delay=1, log_level="error", reraise=True):
    """
    함수의 예외 처리를 위한 데코레이터
    
    Args:
        retry_count (int): 재시도 횟수
        retry_delay (int): 재시도 간 지연 시간(초)
        log_level (str): 로깅 레벨 (error, warning, info)
        reraise (bool): 예외를 다시 발생시킬지 여부
    """
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
                    attempts += 1
                    last_exception = e
                    
                    # 스택 트레이스 가져오기
                    trace = traceback.format_exc()
                    
                    # 로깅
                    if log_level == "error":
                        error_logger.error(f"Error in {func.__name__}: {str(e)}\n{trace}")
                    elif log_level == "warning":
                        logger.warning(f"Warning in {func.__name__}: {str(e)}")
                    else:
                        logger.info(f"Info in {func.__name__}: {str(e)}")
                    
                    # 재시도 가능한 경우
                    if attempts <= retry_count:
                        logger.info(f"Retrying {func.__name__} ({attempts}/{retry_count})...")
                        time.sleep(retry_delay)
                    else:
                        if reraise:
                            # 원본 예외를 포함한 봇 관련 예외로 변환
                            if isinstance(e, BotError):
                                raise
                            else:
                                if "api" in func.__name__.lower() or "exchange" in func.__module__.lower():
                                    raise APIError(f"API error in {func.__name__}: {str(e)}", original_exception=e)
                                elif "database" in func.__name__.lower() or "db" in func.__module__.lower():
                                    raise DatabaseError(f"Database error in {func.__name__}: {str(e)}", original_exception=e)
                                elif "trade" in func.__name__.lower():
                                    raise TradeError(f"Trade error in {func.__name__}: {str(e)}", original_exception=e)
                                else:
                                    raise BotError(f"Error in {func.__name__}: {str(e)}", original_exception=e)
                        return None
        return wrapper
    return decorator

# 자주 사용하는 데코레이터 미리 정의
def api_error_handler(func):
    """API 호출에 대한 에러 처리"""
    return handle_errors(retry_count=3, retry_delay=2, log_level="error")(func)

def db_error_handler(func):
    """데이터베이스 작업에 대한 에러 처리"""
    return handle_errors(retry_count=2, retry_delay=1, log_level="error")(func)

def trade_error_handler(func):
    """거래 작업에 대한 에러 처리"""
    return handle_errors(retry_count=0, log_level="error")(func)

def safe_execution(func):
    """일반적인 함수에 대한 에러 처리 (예외 재발생 안함)"""
    return handle_errors(retry_count=0, log_level="warning", reraise=False)(func)

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
