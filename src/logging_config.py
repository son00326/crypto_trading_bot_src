#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 로깅 설정 모듈
import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import json
from datetime import datetime

# 로그 디렉토리 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 로그 파일 경로
MAIN_LOG_FILE = os.path.join(LOG_DIR, "main.log")
TRADE_LOG_FILE = os.path.join(LOG_DIR, "trades.log")
API_LOG_FILE = os.path.join(LOG_DIR, "api.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "errors.log")
DEBUG_LOG_FILE = os.path.join(LOG_DIR, "debug.log")

# 로그 포맷 설정
SIMPLE_FORMAT = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
DETAILED_FORMAT = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)

class JSONFormatter(logging.Formatter):
    """JSON 형식으로 로그 포맷팅"""
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "file": record.filename,
            "line": record.lineno
        }
        
        # 예외 정보 추가
        if record.exc_info:
            log_record["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1])
            }
        
        # 추가 데이터가 있으면 포함
        if hasattr(record, 'data'):
            log_record["data"] = record.data
            
        return json.dumps(log_record)

def setup_logger(name, log_file, level=logging.INFO, use_json=False, max_size=10*1024*1024, backup_count=5):
    """로거 셋업 유틸리티 함수"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 기존 핸들러 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 파일 핸들러 (크기 기반 로테이션)
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=max_size, 
        backupCount=backup_count
    )
    
    # 포맷터 설정
    if use_json:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(DETAILED_FORMAT if level == logging.DEBUG else SIMPLE_FORMAT)
    
    logger.addHandler(file_handler)
    
    # 콘솔 핸들러 (필요에 따라 활성화)
    # 개발 환경에서만 콘솔 로깅 활성화
    if os.getenv('DEBUG', 'false').lower() == 'true':
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(SIMPLE_FORMAT)
        logger.addHandler(console_handler)
    
    return logger

# 메인 로거 (일반 정보용)
main_logger = setup_logger("crypto_bot", MAIN_LOG_FILE)

# 트레이드 로거 (거래 정보 전용, JSON 형식)
trade_logger = setup_logger("crypto_bot.trades", TRADE_LOG_FILE, use_json=True)

# API 로거 (API 통신 전용)
api_logger = setup_logger("crypto_bot.api", API_LOG_FILE)

# 에러 로거 (오류 전용, 자세한 형식)
error_logger = setup_logger("crypto_bot.error", ERROR_LOG_FILE, level=logging.ERROR)

# 디버그 로거 (개발용, 매우 상세)
debug_logger = setup_logger("crypto_bot.debug", DEBUG_LOG_FILE, level=logging.DEBUG)

def get_logger(name=None):
    """적절한 로거 인스턴스 반환"""
    if name is None:
        return main_logger
    
    return logging.getLogger(name)

def log_trade(action, data):
    """거래 활동 로깅 유틸리티"""
    record = trade_logger.makeRecord(
        "crypto_bot.trades", 
        logging.INFO, 
        "(trade)", 
        0, 
        f"Trade Action: {action}", 
        (), 
        None
    )
    record.data = data
    trade_logger.handle(record)

def log_api_call(endpoint, method, request_data=None, response_data=None, error=None):
    """API 호출 로깅 유틸리티"""
    if error:
        message = f"API Error: {endpoint} [{method}]"
        level = logging.ERROR
        api_logger.error(message, extra={
            "endpoint": endpoint,
            "method": method,
            "request": request_data,
            "error": str(error)
        })
    else:
        message = f"API Call: {endpoint} [{method}]"
        level = logging.INFO
        record = api_logger.makeRecord(
            "crypto_bot.api", 
            level, 
            "(api)", 
            0, 
            message, 
            (), 
            None
        )
        record.data = {
            "endpoint": endpoint,
            "method": method,
            "request": request_data,
            "response": response_data
        }
        api_logger.handle(record)
