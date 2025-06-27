"""
거래소 API 연결 모듈 - 암호화폐 자동매매 봇

이 모듈은 다양한 암호화폐 거래소(바이낸스, 업비트, 빗썸)에 연결하고
시장 데이터 조회, 주문 실행 등의 기능을 제공합니다.
"""

import ccxt
import pandas as pd
from datetime import datetime
import time
import traceback
import functools
import threading
import json
import os
from typing import Optional, List, Dict
from src.config import (
    BINANCE_API_KEY, BINANCE_API_SECRET,
    UPBIT_API_KEY, UPBIT_API_SECRET,
    BITHUMB_API_KEY, BITHUMB_API_SECRET,
    DEFAULT_EXCHANGE, DEFAULT_SYMBOL, DEFAULT_FUTURES_SYMBOL, DEFAULT_MARKET_TYPE, DEFAULT_TIMEFRAME
)
from src.network_recovery import NetworkRecoveryManager
from src.rate_limit_manager import get_rate_limit_manager, rate_limited

# 향상된 로깅 시스템 사용
from src.logging_config import get_logger, log_api_call
from src.error_handlers import api_error_handler, APIError, MarketTypeError, OrderNotFound, RateLimitExceeded

# 로거 설정
logger = get_logger('crypto_bot.exchange')

# API 성능 측정 데코레이터
def measure_api_performance(func):
    """
    API 호출 시간을 측정하고 로깅하는 데코레이터
    
    Args:
        func (callable): 데코레이트할 메서드
        
    Returns:
        callable: 성능 측정 기능이 추가된 래퍼 함수
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 첫 번째 인자를 self로 가정 (클래스 메서드인 경우)
        self = args[0] if args else None
        method_name = func.__name__
        # 시작 시간 기록
        start_time = time.time()
        
        try:
            # 원본 함수 실행 - 원래 인자 그대로 전달
            result = func(*args, **kwargs)
            # 완료 시간 기록 및 성능 로깅
            elapsed = time.time() - start_time
            if hasattr(self, 'logger'):
                self.logger.debug(f"{method_name} 완료 (소요시간: {elapsed:.4f}초)")
            return result
        except Exception as e:
            # 예외 발생 시에도 소요 시간 기록
            elapsed = time.time() - start_time
            if hasattr(self, 'logger'):
                self.logger.error(f"{method_name} 실패 (소요시간: {elapsed:.4f}초): {str(e)}")
            raise
    return wrapper

# API 호출 로깅 데코레이터
def log_api_request(endpoint_format=None, include_response=True):
    """
    API 요청 및 응답을 자동으로 로깅하는 데코레이터
    
    Args:
        endpoint_format (str): 엔드포인트 형식 (메서드 파라미터로 포매팅됨)
        include_response (bool): 응답 데이터 로깅 여부
    
    Returns:
        callable: API 로깅 기능이 추가된 래퍼 함수
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 첫 번째 인자는 self임을 가정 (API 메서드는 일반적으로 클래스 메서드)
            self = args[0] if args else None
            
            # 요청 엔드포인트 구성
            if endpoint_format:
                # 파라미터 값으로 엔드포인트 포매팅
                # symbol 파라미터 추출 - kwargs에서 먼저 찾고 없으면 args[1](첫 번째 인자는 self)
                symbol = None
                if 'symbol' in kwargs:
                    symbol = kwargs['symbol']
                elif len(args) > 1:
                    symbol = args[1]
                elif hasattr(self, 'symbol'):
                    symbol = self.symbol
                    
                # symbol 형식화
                if symbol and hasattr(self, 'format_symbol'):
                    symbol = self.format_symbol(symbol)
                    
                try:
                    # 엔드포인트 포매팅 - 표현식에 필요한 모든 변수가 있는지 확인
                    endpoint = endpoint_format.format(symbol=symbol)
                except (KeyError, IndexError, ValueError):
                    # 포매팅 오류시 기본 엔드포인트 사용
                    endpoint = f"/{func.__name__}"
            else:
                # 기본 엔드포인트는 메서드 이름 사용
                endpoint = f"/{func.__name__}"
                
            # 요청 데이터 구성 - 모든 kwargs와 일부 필터링된 args
            request_data = {k: v for k, v in kwargs.items() if v is not None}
            # args에서 먼저 self 제외
            filtered_args = args[1:] if args else []
            if filtered_args:
                for i, arg in enumerate(filtered_args):
                    # 대용량 타입은 표시하지 않음
                    if isinstance(arg, (str, int, float, bool)) or arg is None:
                        request_data[f"arg{i}"] = arg
                    
            # API 호출 전 로깅
            http_method = "GET" if func.__name__.startswith("get") else "POST"
            if hasattr(self, 'logger'):
                log_api_call(endpoint, http_method, request_data=request_data)
            
            try:
                # 함수 실행 - 모든 인자 그대로 전달
                result = func(*args, **kwargs)
                
                # 응답 로깅 (필요한 경우)
                if include_response and hasattr(self, 'logger'):
                    # 대용량 데이터인 경우 요약 정보만 로깅
                    if isinstance(result, pd.DataFrame):
                        log_data = {
                            "records": len(result),
                            "columns": list(result.columns),
                            "first_row": result.iloc[0].to_dict() if not result.empty else None
                        }
                    elif isinstance(result, dict):
                        # 사전의 경우 최상위 키만 로깅
                        log_data = {k: ("..." if isinstance(v, (dict, list)) else v) 
                                   for k, v in list(result.items())[:5]}
                    elif isinstance(result, list):
                        # 리스트의 경우 길이와 첫 항목만 로깅
                        log_data = {
                            "count": len(result),
                            "first_item": str(result[0])[:100] + "..." if result else None
                        }
                    else:
                        log_data = {"result": str(result)[:100]}
                        
                    log_api_call(endpoint, http_method, response_data=log_data)
                
                return result
                
            except Exception as e:
                # 오류 로깅
                if hasattr(self, 'logger'):
                    log_api_call(endpoint, http_method, error=e)
                raise
                
        return wrapper
    return decorator

class ExchangeAPI:
    """암호화폐 거래소 API 연결 및 작업을 위한 클래스"""
    
    def __init__(self, exchange_id=DEFAULT_EXCHANGE, symbol=None, timeframe=DEFAULT_TIMEFRAME, market_type=DEFAULT_MARKET_TYPE, leverage=1):
        """
        거래소 API 클래스 초기화
        
        Args:
            exchange_id (str): 거래소 ID ('binance', 'upbit', 'bithumb')
            symbol (str): 거래 심볼 (예: 'BTC/USDT', 선물거래의 경우 'BTCUSDT' 형식도 가능)
            timeframe (str): 차트 타임프레임 (예: '1m', '1h', '1d')
            market_type (str): 시장 유형 ('spot' 또는 'futures')
            leverage (int): 레버리지 배수 (선물 거래에만 적용, 1-125)
        """
        self.exchange_id = exchange_id
        # 시장 유형에 따른 기본 심볼 선택
        if symbol is None:
            if market_type == 'futures':
                self.symbol = DEFAULT_FUTURES_SYMBOL
            else:
                self.symbol = DEFAULT_SYMBOL
        else:
            self.symbol = symbol
        
        self.market_type = market_type
        self.leverage = leverage if market_type == 'futures' else 1
        self.timeframe = timeframe
        self.logger = get_logger(f'crypto_bot.exchange.{self.exchange_id}')
        self.exchange = self._initialize_exchange()
        
        # 네트워크 복구 관리자 초기화
        self.network_recovery = self._initialize_network_recovery()
        
        # 초기화 완료 로그
        self.logger.info(f"거래소 API 초기화 완료: {self.exchange_id}, 시장: {self.market_type}, 심볼: {self.symbol}")
        
    def format_symbol(self, symbol=None):
        """
        거래소 및 거래 유형에 맞는 심볼 형식으로 변환
        
        Args:
            symbol (str, optional): 기본 심볼 문자열. None이면 self.symbol 사용
            
        Returns:
            str: 거래소 형식에 맞게 포맷팅된 심볼
        """
        # 심볼이 없으면 기본값 사용
        symbol = symbol or self.symbol
        
        # 바이낸스 선물인 경우
        if self.exchange_id == 'binance' and self.market_type == 'futures':
            # '/'가 포함된 형태이면 제거 ('BTC/USDT' -> 'BTCUSDT')
            if '/' in symbol:
                formatted_symbol = symbol.replace('/', '')
                # ':USDT' 부분 있는지 확인하고 제거
                if ':' in formatted_symbol:
                    base, quote = formatted_symbol.split(':')
                    if base.endswith(quote):
                        self.logger.warning(f"심볼 수정: {formatted_symbol} -> {base}")
                        formatted_symbol = base
                return formatted_symbol
            # ':USDT' 부분 있는지 확인하고 제거
            elif ':' in symbol:
                base, quote = symbol.split(':')
                if base.endswith(quote):
                    self.logger.warning(f"심볼 수정: {symbol} -> {base}")
                    return base
            return symbol
        
        # 현물 거래 또는 다른 거래소의 경우 원본 그대로 사용
        return symbol
        
    @api_error_handler
    def _initialize_network_recovery(self):
        """네트워크 복구 관리자 초기화"""
        try:
            recovery = NetworkRecoveryManager()
            
            # 거래소별 엔드포인트 등록
            if self.exchange_id == 'binance':
                recovery.register_endpoint(
                    service_name='binance',
                    primary_url='https://api.binance.com/api/v3/ping',
                    alternative_urls=[
                        'https://api1.binance.com/api/v3/ping',
                        'https://api2.binance.com/api/v3/ping',
                        'https://api3.binance.com/api/v3/ping'
                    ]
                )
            elif self.exchange_id == 'bybit':
                recovery.register_endpoint(
                    service_name='bybit',
                    primary_url='https://api.bybit.com/v2/public/time',
                    alternative_urls=[
                        'https://api.bytick.com/v2/public/time'
                    ]
                )
            elif self.exchange_id == 'upbit':
                recovery.register_endpoint(
                    service_name='upbit',
                    primary_url='https://api.upbit.com/v1/ticker',
                    alternative_urls=[]
                )
            elif self.exchange_id == 'bithumb':
                recovery.register_endpoint(
                    service_name='bithumb',
                    primary_url='https://api.bithumb.com/public/ticker/ALL',
                    alternative_urls=[]
                )
            
            # 모니터링 시작 (별도 스레드)
            threading.Thread(target=recovery.start_monitoring, daemon=True).start()
            self.logger.info(f"{self.exchange_id} 네트워크 복구 관리자 초기화 완료")
            
            return recovery
        except Exception as e:
            self.logger.error(f"네트워크 복구 관리자 초기화 실패: {e}")
            # 실패해도 계속 진행 (복구 관리자는 선택적 기능)
            return None
    
    def _initialize_exchange(self):
        """거래소 객체 초기화"""
        try:
            # 시작 시간 기록
            start_time = time.time()
            
            # API 키 및 기본 설정 가져오기
            config = {
                'apiKey': None, 
                'secret': None,
                'enableRateLimit': True,
            }
            
            # 거래소별 API 키 설정
            if self.exchange_id == 'binance':
                config['apiKey'] = BINANCE_API_KEY
                config['secret'] = BINANCE_API_SECRET
            elif self.exchange_id == 'upbit':
                config['apiKey'] = UPBIT_API_KEY
                config['secret'] = UPBIT_API_SECRET
            elif self.exchange_id == 'bithumb':
                config['apiKey'] = BITHUMB_API_KEY
                config['secret'] = BITHUMB_API_SECRET
            else:
                raise ValueError(f"지원하지 않는 거래소입니다: {self.exchange_id}")
            
            # 선물 거래 설정 (바이낸스 선물은 options을 통해 설정)
            if self.market_type == 'futures':
                # 거래소별 선물 거래 설정
                if self.exchange_id == 'binance':
                    # 바다낸스 경우 options에 defaultType을 설정
                    config['options'] = {
                        'defaultType': 'future',  # 선물투자
                        'adjustForTimeDifference': True
                    }
                    self.logger.info(f"Binance 선물 거래 모드로 설정했습니다.")
                else:
                    self.logger.warning(f"{self.exchange_id} 거래소는 현재 선물 거래를 지원하지 않습니다.")
            
            # 거래소 객체 생성 (API 호출 로깅)
            log_api_call(f"/exchange/{self.exchange_id}/initialize", "POST", request_data={
                "market_type": self.market_type,
                "symbol": self.symbol,
                "timeframe": self.timeframe
            })
            
            if self.exchange_id == 'binance':
                # 바이낸스의 경우 create_binance_client 함수 사용
                from utils.api import create_binance_client
                is_future = self.market_type == 'futures'
                use_testnet = config.get('test', {}).get('sandbox', False)
                
                exchange = create_binance_client(
                    api_key=config.get('apiKey'),
                    api_secret=config.get('secret'),
                    is_future=is_future,
                    use_testnet=use_testnet
                )
            else:
                # 다른 거래소는 기존 방식 사용
                exchange_class = getattr(ccxt, self.exchange_id)
                exchange = exchange_class(config)
            
            # 바이낸스 선물의 경우 positionRisk 엔드포인트가 v2를 사용하도록 수정
            if self.exchange_id == 'binance' and self.market_type == 'futures':
                # URL 패치 제거 - utils/api.py에서 선택적 패치 적용
                # positionRisk 엔드포인트만 v2 사용하도록 이미 처리됨
                self.logger.info("바이낸스 선물 모드 - positionRisk는 v2, 나머지는 v1 사용")
                
                # 바이낸스 선물 전용 옵션 설정
                exchange.options['defaultType'] = 'future'
                exchange.options['adjustForTimeDifference'] = True
                exchange.options['recvWindow'] = 10000
                
                # 레버리지 설정 (실제 거래만)
                if config['apiKey'] and config['secret'] and config['apiKey'] != 'your_api_key_here':
                    # 1. 레버리지 설정
                    log_api_call(f"/exchange/{self.exchange_id}/leverage", "POST", request_data={
                        "symbol": self.format_symbol(),
                        "leverage": self.leverage
                    })
                    
                    leverage_result = exchange.setLeverage(self.leverage, self.format_symbol())
                    self.logger.info(f"레버리지 설정 완료: {self.format_symbol()}, {self.leverage}배")
                    
                    # 2. 마진 타입 설정 (교차 또는 격리)
                    margin_mode = 'isolated'  # 격리 마진 사용
                    try:
                        log_api_call(f"/exchange/{self.exchange_id}/marginMode", "POST", request_data={
                            "symbol": self.format_symbol(),
                            "marginMode": margin_mode
                        })
                        
                        exchange.set_margin_mode(margin_mode, self.format_symbol())
                        self.logger.info(f"마진 타입 설정 완료: {self.format_symbol()}, {margin_mode} 모드")
                    except Exception as margin_error:
                        if "already" in str(margin_error):
                            self.logger.info(f"이미 {margin_mode} 마진 모드로 설정되어 있습니다: {self.format_symbol()}")
                        else:
                            self.logger.error(f"마진 타입 설정 실패: {str(margin_error)}")
                    
                    # 3. 포지션 모드 설정 (예: one-way 모드)
                    try:
                        exchange.set_position_mode(False, self.format_symbol())  # False: 단일 포지션 모드 (one-way)
                        self.logger.info(f"포지션 모드 설정 완료: {self.format_symbol()}, one-way 모드")
                    except Exception as position_mode_error:
                        if "already" in str(position_mode_error):
                            self.logger.info(f"이미 one-way 포지션 모드로 설정되어 있습니다: {self.format_symbol()}")
                        else:
                            self.logger.error(f"포지션 모드 설정 실패: {str(position_mode_error)}")
                else:
                    self.logger.warning("API 키가 설정되지 않아 레버리지 및 마진 설정을 건너뚝니다.")
            
            # 완료 시간 기록 및 성능 로깅
            elapsed = time.time() - start_time
            market_type_str = f"시장 유형: {self.market_type}" + (f", 레버리지: {self.leverage}배" if self.market_type == 'futures' else "")
            self.logger.info(f"{self.exchange_id} 거래소에 연결되었습니다. {market_type_str} (소요시간: {elapsed:.2f}초)")
            
            return exchange
        
        except Exception as e:
            self.logger.error(f"거래소 초기화 중 오류 발생: {str(e)}\n{traceback.format_exc()}")
            raise APIError(f"거래소 초기화 오류: {str(e)}", original_exception=e)
    

    
    @api_error_handler
    @measure_api_performance
    @log_api_request(endpoint_format="/ticker/{symbol}")
    def get_ticker(self, symbol=None):
        """현재 시세 정보 조회 (재시도 로직 포함)"""
        symbol = self.format_symbol(symbol)
        
        # 재시도 설정
        max_retries = 3
        retry_delay = 2
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 네트워크 복구 관리자를 통한 연결 확인
                if self.network_recovery is not None:
                    self.network_recovery.check_connection(self.exchange_id)
                    
                ticker = self.exchange.fetch_ticker(symbol)
                return ticker
                
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                
                # 네트워크 복구 관리자에 오류 기록
                if self.network_recovery is not None:
                    self.network_recovery.record_error(self.exchange_id, e)
                
                # 오류 유형별 처리
                if '502' in error_msg or 'bad gateway' in error_msg:
                    self.logger.warning(f"시세 조회 실패 ({attempt+1}/{max_retries}): 바이낸스 서버 오류 - {e}")
                elif '408' in error_msg or 'timeout' in error_msg:
                    self.logger.warning(f"시세 조회 실패 ({attempt+1}/{max_retries}): 타임아웃 - {e}")
                elif '429' in error_msg or 'rate limit' in error_msg:
                    self.logger.warning(f"시세 조회 실패 ({attempt+1}/{max_retries}): 요청 한도 초과 - {e}")
                    retry_delay = retry_delay * 2  # 요청 한도 초과 시 대기 시간 증가
                else:
                    self.logger.error(f"시세 조회 실패 ({attempt+1}/{max_retries}): {e}")
                
                # 마지막 시도가 아니면 대기 후 재시도
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # 지수 백오프
                    self.logger.info(f"{wait_time}초 대기 후 재시도...")
                    time.sleep(wait_time)
                    
                    # 네트워크 복구 시도
                    if self.network_recovery is not None:
                        recovery_success = self.network_recovery._attempt_recovery(self.exchange_id)
                        if recovery_success:
                            self.logger.info("네트워크 복구 성공, 즉시 재시도")
                            continue
        
        # 모든 시도 실패 시
        self.logger.error(f"시세 정보 조회 최종 실패: {last_error}")
        return None
    
    def fetch_ticker(self, symbol=None):
        """호환성을 위한 get_ticker 메서드의 별칭
        
        일부 코드에서 fetch_ticker를 직접 호출하고 있어 호환성을 위해 추가
        """
        return self.get_ticker(symbol)
    
    @api_error_handler
    @measure_api_performance
    @log_api_request(endpoint_format="/market/{symbol}")
    def get_market_info(self, symbol=None):
        """거래 페어의 시장 정보 조회"""
        try:
            symbol = self.format_symbol(symbol)
            self.logger.info(f"시장 정보 조회: {symbol}")
            
            # markets 정보가 없으면 먼저 로드
            if not hasattr(self.exchange, 'markets') or not self.exchange.markets:
                self.exchange.load_markets()
            
            # 특정 심볼의 시장 정보 반환
            if symbol in self.exchange.markets:
                return self.exchange.markets[symbol]
            else:
                self.logger.warning(f"시장 정보를 찾을 수 없음: {symbol}")
                return None
                
        except Exception as e:
            self.logger.error(f"시장 정보 조회 실패: {str(e)}")
            return None
    
    @api_error_handler
    @measure_api_performance
    @log_api_request(endpoint_format="/ohlcv/{symbol}")
    def get_ohlcv(self, symbol=None, timeframe=None, limit=100):
        """OHLCV 데이터 조회 (봉 데이터)"""
        # 기본값 설정
        symbol = self.format_symbol(symbol)
        if timeframe is None:
            timeframe = self.timeframe
        
        # 시장 타입에 따른 추가 설정
        params = {
            'limit': limit  # limit 매개변수를 params 딕셔너리에 추가
        }
        
        if self.market_type == 'futures' and self.exchange_id == 'binance':
            # 바이낸스 선물의 경우 필요한 추가 파라미터
            params['contract'] = True  # 선물 계약 데이터 지정
        
        try:
            # OHLCV 데이터 가져오기 (로깅은 데코레이터에서 처리)
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, params=params)
            
            if not ohlcv or len(ohlcv) == 0:
                self.logger.warning(f"fetch_ohlcv 호출 결과가 비어있습니다: {symbol}, {timeframe}")
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 시장 유형 정보 추가
            df['market_type'] = self.market_type
            if self.market_type == 'futures':
                df['leverage'] = self.leverage
                
            return df
            
        except Exception as e:
            self.logger.error(f"OHLCV 데이터 가져오기 실패: {str(e)}")
            # API 변경 대응을 위한 폴백 처리
            try:
                self.logger.info(f"대체 방식으로 OHLCV 데이터 조회 시도 중...")
                # 일부 거래소는 since 파라미터가 필요할 수 있음
                since = None
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since, params=params)
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # 시장 유형 정보 추가
                df['market_type'] = self.market_type
                if self.market_type == 'futures':
                    df['leverage'] = self.leverage
                    
                return df
            except Exception as fallback_e:
                self.logger.error(f"폴백 방식으로도 OHLCV 데이터 가져오기 실패: {str(fallback_e)}")
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    @api_error_handler
    def create_market_buy_order(self, symbol=None, amount=None):
        """시장가 매수 주문
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            amount (float): 주문 수량
            
        Returns:
            dict: 주문 결과 정보 (성공 시)
            
        Raises:
            ValueError: 값이 유효하지 않은 경우
            APIError: API 호출 오류
        """
        try:
            # 심볼 처리
            symbol = self.format_symbol(symbol)
            
            # 값 유효성 검사
            if amount is None:
                raise ValueError("주문 수량을 지정해야 합니다.")
            
            # 수량 형변환 시도
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                raise ValueError(f"유효하지 않은 주문 수량 형식: {amount}")
            
            if amount <= 0:
                raise ValueError(f"주문 수량은 0보다 커야 합니다: {amount}")
                
            # API 호출 로깅
            order_request = {
                "symbol": symbol,
                "amount": amount,
                "type": "market",
                "side": "buy",
                "market_type": self.market_type,
                "leverage": self.leverage if self.market_type == 'futures' else None
            }
            
            log_api_call(f"/orders/{symbol}", "POST", request_data=order_request)
            
            # 시작 시간 기록
            start_time = time.time()
            
            # 선물 거래에 필요한 추가 매개변수
            params = {}
            if self.market_type == 'futures':
                # 선물 거래 관련 매개변수 설정
                params = {
                    'reduceOnly': False,  # 포지션 청산용 주문인지
                    'timeInForce': 'GTC',  # Good Till Cancel
                }
                
                self.logger.info(f"선물 시장가 매수 주문 시도: {symbol}, {amount}, 레버리지: {self.leverage}배")
            else:
                self.logger.info(f"현물 시장가 매수 주문 시도: {symbol}, {amount}")
            
            # 주문 실행
            order = self.exchange.create_market_buy_order(symbol, amount, params)
            
            # 완료 시간 기록 및 성능 로깅
            elapsed = time.time() - start_time
            self.logger.debug(f"시장가 매수 주문 완료 (소요시간: {elapsed:.4f}초)")
            
            # 결과 가공
            order_result = {
                "id": order.get('id'),
                "symbol": order.get('symbol'),
                "timestamp": order.get('timestamp'),
                "datetime": order.get('datetime'),
                "type": order.get('type'),
                "side": order.get('side'),
                "amount": float(order.get('amount', 0)),
                "price": float(order.get('price', 0)) if order.get('price') else None,
                "cost": float(order.get('cost', 0)) if order.get('cost') else None,
                "filled": float(order.get('filled', 0)),
                "status": order.get('status'),
                "fee": order.get('fee'),
            }
            
            # 성공적인 응답 로깅
            log_api_call(f"/orders/{symbol}", "POST", response_data={
                "order_id": order.get('id'),
                "status": order.get('status'),
                "filled": order.get('filled'),
                "cost": order.get('cost')
            })
            
            # 성공 메시지 로깅
            order_info = f"시장가 매수 주문 성공: {symbol}, {amount}, 주문ID: {order.get('id')}"
            if self.market_type == 'futures':
                order_info += f", 시장 유형: 선물, 레버리지: {self.leverage}배"
            self.logger.info(order_info)
            
            return order
        
        except ccxt.InsufficientFunds as e:
            error_msg = f"잔고 부족으로 주문 실패: {symbol}, {amount}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except ccxt.InvalidOrder as e:
            error_msg = f"유효하지 않은 주문: {symbol}, {amount}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except Exception as e:
            error_msg = f"시장가 매수 주문 중 오류 발생: {symbol}, {amount}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}\n{traceback.format_exc()}")
            raise APIError(error_msg, original_exception=e)
    
    @api_error_handler
    def create_market_sell_order(self, symbol=None, amount=None):
        """시장가 매도 주문
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            amount (float): 주문 수량
            
        Returns:
            dict: 주문 결과 정보 (성공 시)
            
        Raises:
            ValueError: 값이 유효하지 않은 경우
            APIError: API 호출 오류
        """
        try:
            # 심볼 처리
            symbol = self.format_symbol(symbol)
            
            # 값 유효성 검사
            if amount is None:
                raise ValueError("주문 수량을 지정해야 합니다.")
            
            # 수량 형변환 시도
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                raise ValueError(f"유효하지 않은 주문 수량 형식: {amount}")
            
            if amount <= 0:
                raise ValueError(f"주문 수량은 0보다 커야 합니다: {amount}")
                
            # API 호출 로깅
            order_request = {
                "symbol": symbol,
                "amount": amount,
                "type": "market",
                "side": "sell",
                "market_type": self.market_type,
                "leverage": self.leverage if self.market_type == 'futures' else None
            }
            
            log_api_call(f"/orders/{symbol}", "POST", request_data=order_request)
            
            # 시작 시간 기록
            start_time = time.time()
            
            # 선물 거래에 필요한 추가 매개변수
            params = {}
            if self.market_type == 'futures':
                # 선물 거래 관련 매개변수 설정
                params = {
                    'reduceOnly': False,  # 포지션 청산용 주문인지 여부
                    'timeInForce': 'GTC',  # Good Till Cancel
                }
                
                self.logger.info(f"선물 시장가 매도 주문 시도 (쇼트 포지션): {symbol}, {amount}, 레버리지: {self.leverage}배")
            else:
                self.logger.info(f"현물 시장가 매도 주문 시도: {symbol}, {amount}")
            
            # 주문 실행
            order = self.exchange.create_market_sell_order(symbol, amount, params)
            
            # 완료 시간 기록 및 성능 로깅
            elapsed = time.time() - start_time
            self.logger.debug(f"시장가 매도 주문 완료 (소요시간: {elapsed:.4f}초)")
            
            # 결과 가공
            order_result = {
                "id": order.get('id'),
                "symbol": order.get('symbol'),
                "timestamp": order.get('timestamp'),
                "datetime": order.get('datetime'),
                "type": order.get('type'),
                "side": order.get('side'),
                "amount": float(order.get('amount', 0)),
                "price": float(order.get('price', 0)) if order.get('price') else None,
                "cost": float(order.get('cost', 0)) if order.get('cost') else None,
                "filled": float(order.get('filled', 0)),
                "status": order.get('status'),
                "fee": order.get('fee'),
            }
            
            # 성공적인 응답 로깅
            log_api_call(f"/orders/{symbol}", "POST", response_data={
                "order_id": order.get('id'),
                "status": order.get('status'),
                "filled": order.get('filled'),
                "cost": order.get('cost')
            })
            
            # 성공 메시지 로깅
            order_info = f"시장가 매도 주문 성공: {symbol}, {amount}, 주문ID: {order.get('id')}"
            if self.market_type == 'futures':
                order_info += f", 시장 유형: 선물, 레버리지: {self.leverage}배"
            self.logger.info(order_info)
            
            return order
        
        except ccxt.InsufficientFunds as e:
            error_msg = f"잔고 부족으로 주문 실패: {symbol}, {amount}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except ccxt.InvalidOrder as e:
            error_msg = f"유효하지 않은 주문: {symbol}, {amount}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except Exception as e:
            error_msg = f"시장가 매도 주문 중 오류 발생: {symbol}, {amount}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}\n{traceback.format_exc()}")
            raise APIError(error_msg, original_exception=e)
    
    @api_error_handler
    def create_limit_buy_order(self, symbol=None, amount=None, price=None):
        """지정가 매수 주문
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            amount (float): 주문 수량
            price (float): 주문 가격
            
        Returns:
            dict: 주문 결과 정보 (성공 시)
            
        Raises:
            ValueError: 값이 유효하지 않은 경우
            APIError: API 호출 오류
        """
        try:
            # 심볼 처리
            symbol = self.format_symbol(symbol)
            
            # 값 유효성 검사
            if amount is None or price is None:
                raise ValueError("주문 수량과 가격을 지정해야 합니다.")
            
            # 수량과 가격 형변환 시도
            try:
                amount = float(amount)
                price = float(price)
            except (ValueError, TypeError):
                raise ValueError(f"유효하지 않은 주문 수량 또는 가격 형식: 수량={amount}, 가격={price}")
            
            # 값 유효성 추가 검사
            if amount <= 0:
                raise ValueError(f"주문 수량은 0보다 커야 합니다: {amount}")
                
            if price <= 0:
                raise ValueError(f"주문 가격은 0보다 커야 합니다: {price}")
                
            # API 호출 로깅
            order_request = {
                "symbol": symbol,
                "amount": amount,
                "price": price,
                "type": "limit",
                "side": "buy",
                "market_type": self.market_type,
                "leverage": self.leverage if self.market_type == 'futures' else None
            }
            
            log_api_call(f"/orders/{symbol}", "POST", request_data=order_request)
            
            # 시작 시간 기록
            start_time = time.time()
            
            # 선물 거래에 필요한 추가 매개변수
            params = {}
            if self.market_type == 'futures':
                # 선물 거래 관련 매개변수 설정
                params = {
                    'reduceOnly': False,  # 포지션 청산용 주문인지 여부
                    'timeInForce': 'GTC',  # Good Till Cancel
                }
                
                self.logger.info(f"선물 지정가 매수 주문 시도 (롱 포지션): {symbol}, {amount}, 가격: {price}, 레버리지: {self.leverage}배")
            else:
                self.logger.info(f"현물 지정가 매수 주문 시도: {symbol}, {amount}, 가격: {price}")
            
            # 주문 실행
            order = self.exchange.create_limit_buy_order(symbol, amount, price, params)
            
            # 완료 시간 기록 및 성능 로깅
            elapsed = time.time() - start_time
            self.logger.debug(f"지정가 매수 주문 완료 (소요시간: {elapsed:.4f}초)")
            
            # 결과 가공
            order_result = {
                "id": order.get('id'),
                "symbol": order.get('symbol'),
                "timestamp": order.get('timestamp'),
                "datetime": order.get('datetime'),
                "type": order.get('type'),
                "side": order.get('side'),
                "amount": float(order.get('amount', 0)),
                "price": float(order.get('price', 0)) if order.get('price') else None,
                "cost": float(order.get('cost', 0)) if order.get('cost') else None,
                "filled": float(order.get('filled', 0)),
                "status": order.get('status'),
                "fee": order.get('fee'),
            }
            
            # 성공적인 응답 로깅
            log_api_call(f"/orders/{symbol}", "POST", response_data={
                "order_id": order.get('id'),
                "status": order.get('status'),
                "price": order.get('price'),
                "filled": order.get('filled')
            })
            
            # 성공 메시지 로깅
            order_info = f"지정가 매수 주문 성공: {symbol}, {amount}, 가격: {price}, 주문ID: {order.get('id')}"
            if self.market_type == 'futures':
                order_info += f", 시장 유형: 선물, 레버리지: {self.leverage}배"
            self.logger.info(order_info)
            
            return order
        
        except ccxt.InsufficientFunds as e:
            error_msg = f"잔고 부족으로 주문 실패: {symbol}, {amount}, 가격: {price}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except ccxt.InvalidOrder as e:
            error_msg = f"유효하지 않은 주문: {symbol}, {amount}, 가격: {price}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except Exception as e:
            error_msg = f"지정가 매수 주문 중 오류 발생: {symbol}, {amount}, 가격: {price}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}\n{traceback.format_exc()}")
            raise APIError(error_msg, original_exception=e)
    
    @api_error_handler
    def create_limit_sell_order(self, symbol=None, amount=None, price=None):
        """지정가 매도 주문
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            amount (float): 주문 수량
            price (float): 주문 가격
            
        Returns:
            dict: 주문 결과 정보 (성공 시)
            
        Raises:
            ValueError: 값이 유효하지 않은 경우
            APIError: API 호출 오류
        """
        try:
            # 심볼 처리
            symbol = self.format_symbol(symbol)
            
            # 값 유효성 검사
            if amount is None or price is None:
                raise ValueError("주문 수량과 가격을 지정해야 합니다.")
            
            # 수량과 가격 형변환 시도
            try:
                amount = float(amount)
                price = float(price)
            except (ValueError, TypeError):
                raise ValueError(f"유효하지 않은 주문 수량 또는 가격 형식: 수량={amount}, 가격={price}")
            
            # 값 유효성 추가 검사
            if amount <= 0:
                raise ValueError(f"주문 수량은 0보다 커야 합니다: {amount}")
                
            if price <= 0:
                raise ValueError(f"주문 가격은 0보다 커야 합니다: {price}")
                
            # API 호출 로깅
            order_request = {
                "symbol": symbol,
                "amount": amount,
                "price": price,
                "type": "limit",
                "side": "sell",
                "market_type": self.market_type,
                "leverage": self.leverage if self.market_type == 'futures' else None
            }
            
            log_api_call(f"/orders/{symbol}", "POST", request_data=order_request)
            
            # 시작 시간 기록
            start_time = time.time()
            
            # 선물 거래에 필요한 추가 매개변수
            params = {}
            if self.market_type == 'futures':
                # 선물 거래 관련 매개변수 설정
                params = {
                    'reduceOnly': False,  # 포지션 청산용 주문인지 여부
                    'timeInForce': 'GTC',  # Good Till Cancel
                }
                
                # 선물에서의 매도는 숙편 포지션 설정
                # 매도 = 쇼트 포지션 설정 (매수는 롱 포지션)
                self.logger.info(f"선물 지정가 매도 주문 시도 (쇼트 포지션): {symbol}, {amount}, 가격: {price}, 레버리지: {self.leverage}배")
            else:
                self.logger.info(f"현물 지정가 매도 주문 시도: {symbol}, {amount}, 가격: {price}")
            
            # 주문 실행
            order = self.exchange.create_limit_sell_order(symbol, amount, price, params)
            
            # 완료 시간 기록 및 성능 로깅
            elapsed = time.time() - start_time
            self.logger.debug(f"지정가 매도 주문 완료 (소요시간: {elapsed:.4f}초)")
            
            # 결과 가공
            order_result = {
                "id": order.get('id'),
                "symbol": order.get('symbol'),
                "timestamp": order.get('timestamp'),
                "datetime": order.get('datetime'),
                "type": order.get('type'),
                "side": order.get('side'),
                "amount": float(order.get('amount', 0)),
                "price": float(order.get('price', 0)) if order.get('price') else None,
                "cost": float(order.get('cost', 0)) if order.get('cost') else None,
                "filled": float(order.get('filled', 0)),
                "remaining": float(order.get('remaining', 0)) if order.get('remaining') else None,
                "status": order.get('status'),
                "fee": order.get('fee'),
            }
            
            # 성공적인 응답 로깅
            log_api_call(f"/orders/{symbol}", "POST", response_data={
                "order_id": order.get('id'),
                "status": order.get('status'),
                "price": order.get('price'),
                "filled": order.get('filled')
            })
            
            # 성공 메시지 로깅
            order_info = f"지정가 매도 주문 성공: {symbol}, {amount}, 가격: {price}, 주문ID: {order.get('id')}"
            if self.market_type == 'futures':
                order_info += f", 시장 유형: 선물, 레버리지: {self.leverage}배"
            self.logger.info(order_info)
            
            return order
        
        except ccxt.InsufficientFunds as e:
            error_msg = f"잔고 부족으로 주문 실패: {symbol}, {amount}, 가격: {price}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except ccxt.InvalidOrder as e:
            error_msg = f"유효하지 않은 주문: {symbol}, {amount}, 가격: {price}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except Exception as e:
            error_msg = f"지정가 매도 주문 중 오류 발생: {symbol}, {amount}, 가격: {price}"
            log_api_call(f"/orders/{symbol}", "POST", error=e)
            self.logger.error(f"{error_msg}: {str(e)}\n{traceback.format_exc()}")
            raise APIError(error_msg, original_exception=e)
    
    @api_error_handler
    def cancel_order(self, order_id, symbol=None):
        """주문 취소
        
        Args:
            order_id (str): 취소할 주문 ID
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            
        Returns:
            dict: 취소 결과 정보 (성공 시)
            
        Raises:
            ValueError: 값이 유효하지 않은 경우
            APIError: API 호출 오류
        """
        try:
            # 입력값 유효성 검사
            if not order_id:
                raise ValueError("취소할 주문 ID를 지정해야 합니다.")
                
            # 심볼 처리
            symbol = self.format_symbol(symbol)
            
            # API 호출 로깅
            cancel_request = {
                "order_id": order_id,
                "symbol": symbol,
                "market_type": self.market_type
            }
            
            log_api_call(f"/orders/{order_id}", "DELETE", request_data=cancel_request)
            
            # 시작 시간 기록
            start_time = time.time()
            
            # 거래소별 특수 처리
            params = {}
            if self.market_type == 'futures' and self.exchange_id == 'binance':
                params = {'type': 'future'}
            
            self.logger.info(f"주문 취소 시도: {order_id}, {symbol}")
            
            # 주문 취소 실행
            result = self.exchange.cancel_order(order_id, symbol, params)
            
            # 완료 시간 기록 및 성능 로깅
            elapsed = time.time() - start_time
            self.logger.debug(f"주문 취소 완료 (소요시간: {elapsed:.4f}초)")
            
            # 결과 가공
            cancel_result = {
                "id": result.get('id'),
                "order_id": order_id,
                "symbol": result.get('symbol'),
                "timestamp": result.get('timestamp'),
                "datetime": result.get('datetime'),
                "status": result.get('status')
            }
            
            # 성공적인 응답 로깅
            log_api_call(f"/orders/{order_id}", "DELETE", response_data={
                "order_id": order_id,
                "symbol": symbol,
                "status": result.get('status')
            })
            
            # 성공 메시지 로깅
            cancel_info = f"주문 취소 성공: {order_id}, {symbol}"
            if self.market_type == 'futures':
                cancel_info += f", 시장 유형: 선물"
            self.logger.info(cancel_info)
            
            return result
            
        except ccxt.OrderNotFound as e:
            error_msg = f"존재하지 않는 주문 ID: {order_id}, {symbol}"
            log_api_call(f"/orders/{order_id}", "DELETE", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except ccxt.CancelPending as e:
            # 일부 거래소에서는 취소 요청이 대기 상태의 응답을 보낼 수 있음
            error_msg = f"주문 취소 대기 중: {order_id}, {symbol}"
            log_api_call(f"/orders/{order_id}", "DELETE", response_data={"status": "pending_cancel"})
            self.logger.warning(f"{error_msg}: {str(e)}")
            
            # 이 경우 오류로 처리하지 않고 결과 반환
            return {"id": order_id, "status": "pending_cancel", "symbol": symbol}
            
        except Exception as e:
            error_msg = f"주문 취소 중 오류 발생: {order_id}, {symbol}"
            log_api_call(f"/orders/{order_id}", "DELETE", error=e)
            self.logger.error(f"{error_msg}: {str(e)}\n{traceback.format_exc()}")
            raise APIError(error_msg, original_exception=e)
    
    @api_error_handler
    def get_order_status(self, order_id, symbol=None):
        """주문 상태 조회
        
        Args:
            order_id (str): 조회할 주문 ID
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            
        Returns:
            dict: 주문 상태 정보 (성공 시)
            
        Raises:
            ValueError: 값이 유효하지 않은 경우
            APIError: API 호출 오류
            OrderNotFound: 주문을 찾을 수 없는 경우
        """
        try:
            # 입력값 유효성 검사
            if not order_id:
                raise ValueError("조회할 주문 ID를 지정해야 합니다.")
                
            # 심볼 처리
            symbol = self.format_symbol(symbol)
            
            # API 호출 로깅
            status_request = {
                "order_id": order_id,
                "symbol": symbol,
                "market_type": self.market_type
            }
            
            log_api_call(f"/orders/{order_id}", "GET", request_data=status_request)
            
            # 시작 시간 기록
            start_time = time.time()
            
            # 거래소별 특수 처리
            params = {}
            if self.market_type == 'futures' and self.exchange_id == 'binance':
                # 바이낸스 선물의 경우 필요한 파라미터
                params = {'type': 'future'}
                
            # 주문 상태 조회 실행
            self.logger.info(f"주문 상태 조회 요청: {symbol}, 주문 ID: {order_id}")
            order = self.exchange.fetch_order(order_id, symbol, params=params)
            
            # 완료 시간 기록 및 성능 로깅
            elapsed = time.time() - start_time
            self.logger.debug(f"주문 상태 조회 완료 (소요시간: {elapsed:.4f}초)")
            
            # 결과 가공
            order_result = {
                "id": order.get('id'),
                "symbol": order.get('symbol'),
                "timestamp": order.get('timestamp'),
                "datetime": order.get('datetime'),
                "type": order.get('type'),
                "side": order.get('side'),
                "amount": float(order.get('amount', 0)),
                "price": float(order.get('price', 0)) if order.get('price') else None,
                "cost": float(order.get('cost', 0)) if order.get('cost') else None,
                "filled": float(order.get('filled', 0)),
                "remaining": float(order.get('remaining', 0)) if order.get('remaining') else None,
                "status": order.get('status'),
                "fee": order.get('fee'),
            }
            
            # 성공적인 응답 로깅
            log_api_call(f"/orders/{order_id}", "GET", response_data={
                "order_id": order.get('id'),
                "status": order.get('status'),
                "filled": order.get('filled'),
                "remaining": order.get('remaining')
            })
            
            # 성공 메시지 로깅
            status_info = f"주문 상태 조회 성공: 주문 ID: {order_id}, 상태: {order.get('status')}, 심볼: {symbol}"
            if self.market_type == 'futures':
                status_info += f", 시장 유형: 선물"
            self.logger.info(status_info)
            
            return order_result
            
        except ccxt.OrderNotFound as e:
            error_msg = f"주문을 찾을 수 없음: {order_id}, 심볼: {symbol}"
            log_api_call(f"/orders/{order_id}", "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise OrderNotFound(error_msg, original_exception=e)
            
        except Exception as e:
            error_msg = f"주문 상태 조회 중 오류 발생: {order_id}, 심볼: {symbol}"
            log_api_call(f"/orders/{order_id}", "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}\n{traceback.format_exc()}")
            raise APIError(error_msg, original_exception=e)
    
    @api_error_handler
    def get_open_orders(self, symbol=None):
        """미체결 주문 조회
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            
        Returns:
            list: 미체결 주문 목록 (성공 시)
            
        Raises:
            ValueError: 값이 유효하지 않은 경우
            APIError: API 호출 오류
            AuthenticationError: 인증 오류 발생 시
        """
        try:
            # 심볼 처리
            symbol = self.format_symbol(symbol)
            
            # API 호출 로깅
            request_data = {
                "symbol": symbol,
                "market_type": self.market_type,
                "exchange_id": self.exchange_id
            }
            
            log_api_call("/orders/open", "GET", request_data=request_data)
            
            # 시작 시간 기록
            start_time = time.time()
            
            # 시장 타입에 따른 추가 설정
            params = {}
            if self.market_type == 'futures' and self.exchange_id == 'binance':
                # 바이낸스 선물의 경우 필요한 파라미터
                params = {
                    'type': 'future',
                }
                
            # 업비트의 경우 필요한 파라미터 처리
            elif self.exchange_id == 'upbit':
                # 업비트에서 필요한 추가 파라미터가 있다면 추가
                pass
            
            # 요청 실행 로깅
            if symbol:
                self.logger.info(f"미체결 주문 조회 요청: 심볼: {symbol}, 시장 유형: {self.market_type}")
            else:
                self.logger.info(f"모든 미체결 주문 조회 요청: 시장 유형: {self.market_type}")
            
            # API 호출 실행
            orders = self.exchange.fetch_open_orders(symbol, params=params)
            
            # 완료 시간 기록 및 성능 로깅
            elapsed = time.time() - start_time
            self.logger.debug(f"미체결 주문 조회 완료 (소요시간: {elapsed:.4f}초)")
            
            # 조회 결과 추가 로깅
            market_type_str = "선물" if self.market_type == 'futures' else "현물"
            self.logger.info(f"{market_type_str} 미체결 주문 조회: {symbol or '모든 심볼'}, 개수: {len(orders)}")
            
            # 결과 가공 - 표준화된 형태로 변환
            standardized_orders = []
            for order in orders:
                standardized_order = {
                    "id": order.get('id'),
                    "symbol": order.get('symbol'),
                    "timestamp": order.get('timestamp'),
                    "datetime": order.get('datetime'),
                    "type": order.get('type'),  # limit, market 등
                    "side": order.get('side'),  # buy, sell
                    "amount": float(order.get('amount', 0)),
                    "price": float(order.get('price', 0)) if order.get('price') else None,
                    "cost": float(order.get('cost', 0)) if order.get('cost') else None,
                    "filled": float(order.get('filled', 0)),
                    "remaining": float(order.get('remaining', 0)) if order.get('remaining') else None,
                    "status": order.get('status'),  # open, closed, canceled 등
                    "fee": order.get('fee'),
                    "market_type": self.market_type
                }
                standardized_orders.append(standardized_order)
            
            # 성공적인 응답 로깅
            response_summary = {
                "count": len(standardized_orders),
                "symbol": symbol or "all symbols",
                "market_type": self.market_type
            }
            log_api_call("/orders/open", "GET", response_data=response_summary)
                
            return standardized_orders
        
        except ccxt.AuthenticationError as e:
            error_msg = f"인증 오류로 미체결 주문 조회 실패: {self.exchange_id}"
            log_api_call("/orders/open", "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise AuthenticationError(error_msg, original_exception=e)
            
        except ccxt.ExchangeNotAvailable as e:
            error_msg = f"거래소 서버 연결 불가: {self.exchange_id}"
            log_api_call("/orders/open", "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except ccxt.RequestTimeout as e:
            error_msg = f"거래소 요청 시간 초과: {self.exchange_id}, {symbol or '모든 심볼'}"
            log_api_call("/orders/open", "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except ccxt.DDoSProtection as e:
            error_msg = f"거래소 DDoS 보호 활성화. 요청 제한: {self.exchange_id}"
            log_api_call("/orders/open", "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except ccxt.ExchangeError as e:
            error_msg = f"거래소 환경 오류: {self.exchange_id}, {symbol or '모든 심볼'}"
            log_api_call("/orders/open", "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
        
        except Exception as e:
            error_msg = f"미체결 주문 조회 중 오류 발생: {self.exchange_id}, {symbol or '모든 심볼'}"
            log_api_call("/orders/open", "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}\n{traceback.format_exc()}")
            raise APIError(error_msg, original_exception=e)
            
    @api_error_handler
    def get_my_trades(self, symbol=None, since=None, limit=100):
        """사용자의 거래 내역 조회
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            since (int, optional): 특정 시간 이후의 거래만 조회 (timestamp in milliseconds)
            limit (int, optional): 최대 조회 건수
            
        Returns:
            list: 거래 내역 목록 (성공 시)
            
        Raises:
            ValueError: 값이 유효하지 않은 경우
            APIError: API 호출 오류
            AuthenticationError: 인증 오류 발생 시
            RateLimitExceeded: 요청 제한 초과 시
        """
        try:
            # 심볼 유효성 검사 및 형식 변환
            original_symbol = symbol or self.symbol
            symbol = self.format_symbol(original_symbol)
            
            # since 파라미터 유효성 검사(타임스태프)
            if since is not None:
                # 문자열이나 다른 형식인 경우 정수로 변환 시도
                try:
                    since = int(since)
                    if since < 0:
                        raise ValueError("since 파라미터는 양의 정수여야 합니다")
                except (ValueError, TypeError):
                    raise ValueError(f"since 파라미터가 유효한 타임스태프가 아닙니다: {since}")
            
            # limit 파라미터 유효성 검사
            if limit is not None:
                try:
                    limit = int(limit)
                    if limit <= 0:
                        raise ValueError("limit 파라미터는 양의 정수여야 합니다")
                except (ValueError, TypeError):
                    raise ValueError(f"limit 파라미터가 유효한 숫자가 아닙니다: {limit}")
                    
            # API 호출 로깅
            request_data = {
                "symbol": symbol,
                "since": since,
                "limit": limit,
                "market_type": self.market_type,
                "exchange_id": self.exchange_id
            }
            
            endpoint = f"/trades/{symbol}" if symbol else "/trades/all"
            log_api_call(endpoint, "GET", request_data=request_data)
            
            # 시작 시간 기록
            start_time = time.time()
            
            # 시장 타입에 따른 추가 설정
            params = {}
            if self.market_type == 'futures' and self.exchange_id == 'binance':
                # 바이낸스 선물의 경우 필요한 파라미터
                params = {
                    'type': 'future',
                }
            
            # 요청 실행 로깅
            period_desc = f"{datetime.fromtimestamp(since/1000).strftime('%Y-%m-%d %H:%M:%S')} 이후" if since else "모든 기간"
            self.logger.info(f"거래 내역 조회 요청: {symbol or '모든 심볼'}, {period_desc}, 최대 {limit}개")
            
            # API 호출 실행 (포맷팅된 심볼 사용)
            trades = self.exchange.fetch_my_trades(symbol, since=since, limit=limit, params=params)
            
            # 만약 오류가 발생하고 심볼 형식이 문제였다면, 다른 형식 시도
            if not trades and self.market_type == 'futures' and self.exchange_id == 'binance':
                # 다른 형식으로 시도
                if symbol and '/' in original_symbol:
                    alt_symbol = original_symbol.replace('/', '')
                    self.logger.warning(f"대체 심볼 형식 시도: {symbol} -> {alt_symbol}")
                    trades = self.exchange.fetch_my_trades(alt_symbol, since=since, limit=limit, params=params)
            
            # 완료 시간 기록 및 성능 로깅
            elapsed = time.time() - start_time
            self.logger.debug(f"거래 내역 조회 완료 (소요시간: {elapsed:.4f}초)")
            
            # 조회 결과 로깅
            market_type_str = "선물" if self.market_type == 'futures' else "현물"
            if trades:
                self.logger.info(f"{market_type_str} 거래 내역 조회 성공: {symbol or '모든 심볼'}, 개수: {len(trades)}")
            else:
                self.logger.info(f"{market_type_str} 거래 내역 없음: {symbol or '모든 심볼'}")
            
            # 결과 가공 - 표준화된 형태로 변환
            standardized_trades = []
            
            for trade in trades:
                # 기본 거래 정보 추출
                standardized_trade = {
                    "id": trade.get('id'),
                    "symbol": trade.get('symbol'),
                    "order_id": trade.get('order'),  # 주문 ID
                    "timestamp": trade.get('timestamp'),
                    "datetime": trade.get('datetime'),
                    "type": trade.get('type'),  # limit, market 등
                    "side": trade.get('side'),  # buy, sell
                    "price": float(trade.get('price', 0)) if trade.get('price') else None,
                    "amount": float(trade.get('amount', 0)),
                    "cost": float(trade.get('cost', 0)) if trade.get('cost') else None,
                    "fee": {
                        "cost": float(trade.get('fee', {}).get('cost', 0)) if trade.get('fee') else 0,
                        "currency": trade.get('fee', {}).get('currency') if trade.get('fee') else None
                    },
                    "market_type": self.market_type
                }
                
                # 선물 거래일 경우 추가 정보
                if self.market_type == 'futures':
                    standardized_trade["leverage"] = self.leverage
                    # 추가 선물 관련 정보가 있다면 여기에 추가
                
                standardized_trades.append(standardized_trade)
            
            # 성공적인 응답 로깅
            response_summary = {
                "count": len(standardized_trades),
                "symbol": symbol or "all symbols",
                "market_type": self.market_type,
                "since": since,
                "limit": limit
            }
            log_api_call(endpoint, "GET", response_data=response_summary)
            
            return standardized_trades
        
        except ccxt.AuthenticationError as e:
            error_msg = f"인증 오류로 거래 내역 조회 실패: {self.exchange_id}"
            log_api_call(endpoint, "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise AuthenticationError(error_msg, original_exception=e)
            
        except ccxt.PermissionDenied as e:
            error_msg = f"권한 부족으로 거래 내역 조회 불가: {self.exchange_id}"
            log_api_call(endpoint, "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
        
        except ccxt.ExchangeNotAvailable as e:
            error_msg = f"거래소 서버 연결 불가: {self.exchange_id}"
            log_api_call(endpoint, "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
            
        except ccxt.RequestTimeout as e:
            error_msg = f"거래소 요청 시간 초과: {self.exchange_id}, {symbol or '모든 심볼'}"
            log_api_call(endpoint, "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise APIError(error_msg, original_exception=e)
        
        except ccxt.RateLimitExceeded as e:
            error_msg = f"요청 제한 초과: {self.exchange_id}"
            log_api_call(endpoint, "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}")
            raise RateLimitExceeded(error_msg, original_exception=e)
            
        except Exception as e:
            error_msg = f"거래 내역 조회 중 오류 발생: {self.exchange_id}, {symbol or '모든 심볼'}"
            log_api_call(endpoint, "GET", error=e)
            self.logger.error(f"{error_msg}: {str(e)}\n{traceback.format_exc()}")
            raise APIError(error_msg, original_exception=e)

    @api_error_handler
    @measure_api_performance
    @log_api_request(endpoint_format="/balance")
    def get_balance(self, balance_type=None):
        """계정 잔고 조회
        
        Args:
            balance_type (str, optional): 잔고 유형 ('spot', 'future', 'all'). 기본값은 인스턴스의 market_type 값
        
        Returns:
            dict: 잔고 정보. balance_type이 'all'인 경우 spot과 future 모두 포함
            
        Raises:
            ValueError: 잘못된 balance_type 지정 발생 시
            APIError: API 호출 오류
            AuthenticationError: 인증 오류 발생 시
            RateLimitExceeded: 요청 제한 초과 시
        """
        # 유효한 balance_type 값 확인
        valid_types = ['spot', 'future', 'futures', 'all', None]
        if balance_type not in valid_types:
            error_msg = f"잘못된 balance_type: {balance_type}, 유효한 값: {valid_types}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
            
        # futures를 future로 통일
        if balance_type == 'futures':
            balance_type = 'future'
            
        # 기본 잔고 유형 설정
        if balance_type is None:
            balance_type = self.market_type
            self.logger.debug(f"기본 잔고 유형 사용: {balance_type}")
        
        # 모든 잔고 가져오기
        if balance_type == 'all':
            # 현물 잔고 조회
            spot_balance = None
            future_balance = None
            
            try:
                spot_balance = self.exchange.fetch_balance()
                self.logger.debug(f"현물 잔고 조회 성공: {self.exchange_id}")
            except Exception as e:
                self.logger.warning(f"현물 잔고 조회 실패: {str(e)}")
            
            try:
                # 선물 잔고 파라미터
                params = {'type': 'future'} if self.exchange_id == 'binance' else {}
                future_balance = self.exchange.fetch_balance(params=params)
                self.logger.debug(f"선물 잔고 조회 성공: {self.exchange_id}")
            except Exception as e:
                self.logger.warning(f"선물 잔고 조회 실패: {str(e)}")
            
            # 결과 병합
            result = {
                'spot': {
                    'total': spot_balance.get('total', {}) if spot_balance else {},
                    'free': spot_balance.get('free', {}) if spot_balance else {},
                    'used': spot_balance.get('used', {}) if spot_balance else {}
                },
                'future': {
                    'total': future_balance.get('total', {}) if future_balance else {},
                    'free': future_balance.get('free', {}) if future_balance else {},
                    'used': future_balance.get('used', {}) if future_balance else {}
                }
            }
            
            return result
        
        # 선물 잔고만 가져오기
        elif balance_type == 'future':
            params = {'type': 'future'} if self.exchange_id == 'binance' else {}
            balance = self.exchange.fetch_balance(params=params)
            self.logger.info(f"선물 잔고 조회 성공: {self.exchange_id}")
            return balance
        
        # 현물 잔고만 가져오기 (기본값)
        else:  # 기본값 또는 'spot'
            balance = self.exchange.fetch_balance()
            self.logger.info(f"현물 잔고 조회 성공: {self.exchange_id}")
            return balance
            
    @api_error_handler
    @measure_api_performance
    @log_api_request(endpoint_format="/positions/{symbol}")
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """현재 포지션 정보 조회"""
        try:
            # 로그 추가
            self.logger.info(f"get_positions 호출: symbol={symbol}, market_type={self.market_type}, exchange_id={self.exchange_id}")
            
            # 현물 거래는 포지션이 없음
            if self.market_type != 'futures':
                return []
            
            # 바이낸스 선물의 경우 특별 처리
            if self.exchange_id == 'binance' and self.market_type == 'futures':
                try:
                    # 바이낸스 선물은 심볼 파라미터 없이 모든 포지션을 조회
                    self.logger.info("바이낸스 선물 포지션 조회 - CCXT fetch_positions() 사용")
                    
                    # CCXT를 사용하여 모든 포지션 조회 (심볼 파라미터 없이)
                    positions = self.exchange.fetch_positions()
                    
                    # 특정 심볼로 필터링
                    if symbol and positions:
                        # 심볼 형식 통일 (BTC/USDT 또는 BTCUSDT 모두 처리)
                        formatted_symbol = self.format_symbol(symbol)
                        alt_symbol = formatted_symbol.replace('/', '')  # BTC/USDT -> BTCUSDT
                        
                        filtered_positions = []
                        for pos in positions:
                            pos_symbol = pos.get('symbol', '')
                            if pos_symbol == formatted_symbol or pos_symbol == alt_symbol:
                                filtered_positions.append(pos)
                        
                        self.logger.info(f"전체 포지션 중 {symbol}: {len(filtered_positions)}개")
                        return filtered_positions
                    
                    return positions
                    
                except Exception as e:
                    # CCXT 방식 실패 시 직접 API 호출 시도
                    self.logger.warning(f"CCXT fetch_positions 실패, v2 API 직접 호출 시도: {e}")
                    
                    # requests를 사용하여 직접 v2 API 호출
                    import requests
                    import hmac
                    import hashlib
                    import time
                    from urllib.parse import urlencode
                    
                    api_key = os.getenv('BINANCE_API_KEY')
                    api_secret = os.getenv('BINANCE_API_SECRET')
                    
                    if not api_key or not api_secret:
                        self.logger.error("바이낸스 API 키가 설정되지 않았습니다")
                        return []
                    
                    # 파라미터 생성
                    timestamp = int(time.time() * 1000)
                    params = {
                        'timestamp': timestamp,
                        'recvWindow': 20000  # 10000에서 20000으로 증가
                    }
                    query_string = urlencode(params)
                    
                    # 서명 생성
                    signature = hmac.new(
                        api_secret.encode('utf-8'),
                        query_string.encode('utf-8'),
                        hashlib.sha256
                    ).hexdigest()
                    
                    # API 호출 (재시도 로직 포함)
                    url = f"https://fapi.binance.com/fapi/v2/positionRisk?{query_string}&signature={signature}"
                    headers = {'X-MBX-APIKEY': api_key}
                    
                    max_retries = 3
                    retry_delay = 2
                    
                    for attempt in range(max_retries):
                        try:
                            response = requests.get(
                                url, 
                                headers=headers,
                                timeout=30  # 타임아웃 설정
                            )
                            
                            if response.status_code == 200:
                                break
                            elif response.status_code == 408:  # 타임아웃 오류
                                self.logger.warning(f"v2 API 타임아웃 ({attempt+1}/{max_retries})")
                                if attempt < max_retries - 1:
                                    time.sleep(retry_delay * (2 ** attempt))
                                    continue
                            else:
                                self.logger.error(f"v2 API 호출 실패: {response.status_code}")
                                if attempt < max_retries - 1:
                                    time.sleep(retry_delay)
                                    continue
                                    
                        except requests.exceptions.Timeout:
                            self.logger.error(f"v2 API 요청 타임아웃 ({attempt+1}/{max_retries})")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay * (2 ** attempt))
                                continue
                            else:
                                return []  # 모든 시도 실패
                        except Exception as e:
                            self.logger.error(f"v2 API 호출 중 오류: {e}")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay)
                                continue
                            else:
                                return []
                    
                    if response.status_code != 200:
                        self.logger.error(f"v2 API 호출 최종 실패: {response.status_code}")
                        # v1 폴백은 404를 반환하므로 빈 배열 반환
                        return []
                    
                    # 응답 처리
                    response_data = response.json()
                    positions = []
                    
                    if isinstance(response_data, list):
                        for pos_data in response_data:
                            # 실제 포지션만 필터링 (positionAmt != 0)
                            position_amt = float(pos_data.get('positionAmt', 0))
                            if position_amt != 0:
                                position = {
                                    'symbol': pos_data.get('symbol', ''),
                                    'contracts': abs(position_amt),
                                    'contractSize': 1,  # USDT margined
                                    'side': 'long' if position_amt > 0 else 'short',
                                    'notional': float(pos_data.get('notional', 0)),
                                    'percentage': None,
                                    'marginMode': pos_data.get('marginType', 'cross').lower(),
                                    'markPrice': float(pos_data.get('markPrice', 0)),
                                    'lastPrice': None,
                                    'entryPrice': float(pos_data.get('entryPrice', 0)),
                                    'unrealizedPnl': float(pos_data.get('unRealizedProfit', 0)),
                                    'realizedPnl': None,
                                    'initialMargin': float(pos_data.get('initialMargin', 0)),
                                    'initialMarginPercentage': None,
                                    'maintenanceMargin': float(pos_data.get('maintMargin', 0)),
                                    'maintenanceMarginPercentage': None,
                                    'collateral': None,
                                    'leverage': int(pos_data.get('leverage', 1)),
                                    'liquidationPrice': float(pos_data.get('liquidationPrice', 0)) if pos_data.get('liquidationPrice') else None,
                                    'info': pos_data
                                }
                                positions.append(position)
                    
                    # 특정 심볼로 필터링
                    if symbol and positions:
                        formatted_symbol = self.format_symbol(symbol).replace('/', '')  # BTC/USDT -> BTCUSDT
                        positions = [pos for pos in positions if pos.get('symbol') == formatted_symbol]
                        self.logger.info(f"전체 포지션 중 {formatted_symbol}: {len(positions)}개")
                    
                    return positions

                except Exception as e:
                    self.logger.error(f"포지션 조회 오류: {str(e)}")
                    return []
            
            else:
                # 다른 거래소는 기본 방식 사용
                positions = self.exchange.fetch_positions([symbol] if symbol else None)
                
            return positions
            
        except Exception as e:
            self.logger.error(f"포지션 조회 오류: {str(e)}")
            return []
