"""
거래소 API 연결 모듈 - 암호화폐 자동매매 봇

이 모듈은 다양한 암호화폐 거래소(바이낸스, 업비트, 빗썸)에 연결하고
시장 데이터 조회, 주문 실행 등의 기능을 제공합니다.
"""

import ccxt
import pandas as pd
from datetime import datetime
import time
import logging
from src.config import (
    BINANCE_API_KEY, BINANCE_API_SECRET,
    UPBIT_API_KEY, UPBIT_API_SECRET,
    BITHUMB_API_KEY, BITHUMB_API_SECRET,
    DEFAULT_EXCHANGE, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('exchange_api')

class ExchangeAPI:
    """암호화폐 거래소 API 연결 및 작업을 위한 클래스"""
    
    def __init__(self, exchange_id=DEFAULT_EXCHANGE, symbol=DEFAULT_SYMBOL, timeframe=DEFAULT_TIMEFRAME, market_type='spot', leverage=1):
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
        self.symbol = symbol
        self.market_type = market_type
        self.leverage = leverage if market_type == 'futures' else 1
        self.timeframe = timeframe
        self.exchange = self._initialize_exchange()
        
    def _initialize_exchange(self):
        """거래소 객체 초기화"""
        try:
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
                    logger.info(f"Binance 선물 거래 모드로 설정했습니다.")
                else:
                    logger.warning(f"{self.exchange_id} 거래소는 현재 선물 거래를 지원하지 않습니다.")
            
            # 거래소 객체 생성
            exchange_class = getattr(ccxt, self.exchange_id)
            exchange = exchange_class(config)
            
            # 선물 거래인 경우 레버리지 설정
            if self.market_type == 'futures' and self.exchange_id == 'binance':
                # 심볼 형식 변환
                futures_symbol = self._convert_symbol_format()
                
                try:
                    # 실제 API 키가 설정된 경우에만 레버리지 설정 시도
                    if config['apiKey'] and config['secret'] and config['apiKey'] != 'your_api_key_here':
                        # 레버리지 설정
                        exchange.setLeverage(self.leverage, futures_symbol)
                        logger.info(f"레버리지 설정 완료: {futures_symbol}, {self.leverage}배")
                        
                        # 필요한 경우 포지션 모드 설정 (one-way 모드: 한 방향만 포지션 가능)
                        # exchange.setPositionMode(False, futures_symbol)  # False: 단일 포지션 모드
                    else:
                        logger.warning("API 키가 설정되지 않아 레버리지 설정을 건너뜁니다.")
                except Exception as e:
                    logger.error(f"레버리지 설정 중 오류 발생: {e}")
            
            market_type_str = f"시장 유형: {self.market_type}" + (f", 레버리지: {self.leverage}배" if self.market_type == 'futures' else "")
            logger.info(f"{self.exchange_id} 거래소에 연결되었습니다. {market_type_str}")
            return exchange
        
        except Exception as e:
            logger.error(f"거래소 초기화 중 오류 발생: {e}")
            raise
    
    def _convert_symbol_format(self, symbol=None):
        """시장 타입에 맞는 심볼 형식으로 변환
        
        Args:
            symbol (str, optional): 변환할 심볼. None이면 인스턴스의 symbol 속성 사용
            
        Returns:
            str: 변환된 심볼 형식
        """
        symbol = symbol or self.symbol
        
        # 선물 거래이고 심볼에 '/'가 포함되어 있으면 제거
        if self.market_type == 'futures' and '/' in symbol:
            return symbol.replace('/', '')
        return symbol
    
    def get_ticker(self, symbol=None):
        """현재 시세 정보 조회"""
        try:
            symbol = self._convert_symbol_format(symbol)
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"시세 정보 조회 중 오류 발생: {e}")
            return None
    
    def get_ohlcv(self, symbol=None, timeframe=None, limit=100):
        """OHLCV 데이터 조회 (봉 데이터)"""
        try:
            symbol = self._convert_symbol_format(symbol)
            timeframe = timeframe or self.timeframe
            
            # 시장 타입에 따른 추가 설정
            params = {}
            if self.market_type == 'futures' and self.exchange_id == 'binance':
                # 바이낸스 선물의 경우 필요한 추가 파라미터
                params = {
                    'contract': True,  # 선물 계약 데이터 지정
                }
            
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit, params=params)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 시장 유형 정보 추가
            df['market_type'] = self.market_type
            if self.market_type == 'futures':
                df['leverage'] = self.leverage
                
            return df
        
        except Exception as e:
            logger.error(f"OHLCV 데이터 조회 중 오류 발생: {e}")
            return None
    
    def get_balance(self):
        """계정 잔고 조회"""
        try:
            balance = self.exchange.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"잔고 조회 중 오류 발생: {e}")
            return None
            
    def get_positions(self, symbol=None):
        """현재 포지션 정보 조회
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            
        Returns:
            list: 포지션 정보 리스트. 현물 계좌 또는 오류 발생 시 빈 리스트 반환
        """
        try:
            if self.market_type != 'futures':
                # 현물 계좌에서는 포지션을 반환하지 않음
                return []
            
            # 심볼 처리
            if symbol:
                symbol = self._convert_symbol_format(symbol)
            else:
                symbol = self._convert_symbol_format(self.symbol)
                
            positions = self.exchange.fetch_positions(symbol)
            
            # 포지션 정보 없을 경우 빈 리스트 반환
            if not positions:
                return []
                
            # 필요한 추가 계산 수행
            for position in positions:
                # 포지션 정보에 없는 경우 추가 계산
                if 'entryPrice' in position and 'markPrice' in position and position['entryPrice'] != 0:
                    entry_price = float(position['entryPrice'])
                    mark_price = float(position['markPrice'])
                    size = float(position['size']) if 'size' in position else float(position['contracts']) if 'contracts' in position else 0
                    side = position['side']
                    leverage = float(position['leverage']) if 'leverage' in position else self.leverage
                    
                    # PNL 계산
                    if side == 'long':
                        pnl_percent = ((mark_price - entry_price) / entry_price) * 100 * leverage
                    else:  # short
                        pnl_percent = ((entry_price - mark_price) / entry_price) * 100 * leverage
                        
                    position['pnl_percent'] = pnl_percent
                    position['position_value'] = size * mark_price
                    
            return positions
            
        except Exception as e:
            logger.error(f"포지션 정보 조회 중 오류 발생: {e}")
            return []
    
    def create_market_buy_order(self, symbol=None, amount=None):
        """시장가 매수 주문
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            amount (float): 주문 수량
            
        Returns:
            dict: 주문 결과 정보 (성공 시) 또는 None (실패 시)
        """
        try:
            symbol = self._convert_symbol_format(symbol)
            if amount is None:
                raise ValueError("주문 수량을 지정해야 합니다.")
            
            # 선물 거래에 필요한 추가 매개변수
            params = {}
            if self.market_type == 'futures':
                # 선물 거래 관련 매개변수 설정
                params = {
                    'reduceOnly': False,  # 포지션 청산용 주문인지
                    'timeInForce': 'GTC',  # Good Till Cancel
                }
                
                logger.info(f"선물 시장가 매수 주문 실행: {symbol}, {amount}, 레버리지: {self.leverage}배")
            
            order = self.exchange.create_market_buy_order(symbol, amount, params)
            
            order_info = f"시장가 매수 주문 성공: {symbol}, {amount}"
            if self.market_type == 'futures':
                order_info += f", 시장 유형: 선물, 레버리지: {self.leverage}배"
            logger.info(order_info)
            
            return order
        
        except Exception as e:
            logger.error(f"시장가 매수 주문 중 오류 발생: {e}")
            return None
    
    def create_market_sell_order(self, symbol=None, amount=None):
        """시장가 매도 주문
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            amount (float): 주문 수량
            
        Returns:
            dict: 주문 결과 정보 (성공 시) 또는 None (실패 시)
        """
        try:
            symbol = self._convert_symbol_format(symbol)
            if amount is None:
                raise ValueError("주문 수량을 지정해야 합니다.")
            
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
                logger.info(f"선물 시장가 매도 주문 실행 (쇼트 포지션): {symbol}, {amount}, 레버리지: {self.leverage}배")
            
            order = self.exchange.create_market_sell_order(symbol, amount, params)
            
            order_info = f"시장가 매도 주문 성공: {symbol}, {amount}"
            if self.market_type == 'futures':
                order_info += f", 시장 유형: 선물, 레버리지: {self.leverage}배"
            logger.info(order_info)
            
            return order
        
        except Exception as e:
            logger.error(f"시장가 매도 주문 중 오류 발생: {e}")
            return None
    
    def create_limit_buy_order(self, symbol=None, amount=None, price=None):
        """지정가 매수 주문
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            amount (float): 주문 수량
            price (float): 주문 가격
            
        Returns:
            dict: 주문 결과 정보 (성공 시) 또는 None (실패 시)
        """
        try:
            symbol = self._convert_symbol_format(symbol)
            if amount is None or price is None:
                raise ValueError("주문 수량과 가격을 지정해야 합니다.")
            
            # 선물 거래에 필요한 추가 매개변수
            params = {}
            if self.market_type == 'futures':
                # 선물 거래 관련 매개변수 설정
                params = {
                    'reduceOnly': False,  # 포지션 청산용 주문인지
                    'timeInForce': 'GTC',  # Good Till Cancel
                }
                
                logger.info(f"선물 지정가 매수 주문 실행 (롱 포지션): {symbol}, {amount}, 가격: {price}, 레버리지: {self.leverage}배")
            
            order = self.exchange.create_limit_buy_order(symbol, amount, price, params)
            
            order_info = f"지정가 매수 주문 성공: {symbol}, {amount}, 가격: {price}"
            if self.market_type == 'futures':
                order_info += f", 시장 유형: 선물, 레버리지: {self.leverage}배"
            logger.info(order_info)
            
            return order
        
        except Exception as e:
            logger.error(f"지정가 매수 주문 중 오류 발생: {e}")
            return None
    
    def create_limit_sell_order(self, symbol=None, amount=None, price=None):
        """지정가 매도 주문
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            amount (float): 주문 수량
            price (float): 주문 가격
            
        Returns:
            dict: 주문 결과 정보 (성공 시) 또는 None (실패 시)
        """
        try:
            symbol = self._convert_symbol_format(symbol)
            if amount is None or price is None:
                raise ValueError("주문 수량과 가격을 지정해야 합니다.")
            
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
                logger.info(f"선물 지정가 매도 주문 실행 (쇼트 포지션): {symbol}, {amount}, 가격: {price}, 레버리지: {self.leverage}배")
            
            order = self.exchange.create_limit_sell_order(symbol, amount, price, params)
            
            order_info = f"지정가 매도 주문 성공: {symbol}, {amount}, 가격: {price}"
            if self.market_type == 'futures':
                order_info += f", 시장 유형: 선물, 레버리지: {self.leverage}배"
            logger.info(order_info)
            
            return order
        
        except Exception as e:
            logger.error(f"지정가 매도 주문 중 오류 발생: {e}")
            return None
    
    def cancel_order(self, order_id, symbol=None):
        """주문 취소
        
        Args:
            order_id (str): 취소할 주문 ID
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            
        Returns:
            dict: 취소 결과 정보 (성공 시) 또는 None (실패 시)
        """
        try:
            symbol = self._convert_symbol_format(symbol)
            result = self.exchange.cancel_order(order_id, symbol)
            
            cancel_info = f"주문 취소 성공: {order_id}, {symbol}"
            if self.market_type == 'futures':
                cancel_info += f", 시장 유형: 선물"
            logger.info(cancel_info)
            
            return result
        
        except Exception as e:
            logger.error(f"주문 취소 중 오류 발생: {e}")
            return None
    
    def get_order_status(self, order_id, symbol=None):
        """주문 상태 조회
        
        Args:
            order_id (str): 조회할 주문 ID
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            
        Returns:
            dict: 주문 상태 정보 (성공 시) 또는 None (실패 시)
        """
        try:
            symbol = self._convert_symbol_format(symbol)
            order = self.exchange.fetch_order(order_id, symbol)
            
            if order and self.market_type == 'futures':
                logger.info(f"선물 주문 상태 조회: {order_id}, {symbol}, 상태: {order['status']}")
                
            return order
        
        except Exception as e:
            logger.error(f"주문 상태 조회 중 오류 발생: {e}")
            return None
    
    def get_open_orders(self, symbol=None):
        """미체결 주문 조회
        
        Args:
            symbol (str, optional): 거래 심볼. 기본값은 인스턴스의 symbol
            
        Returns:
            list: 미체결 주문 목록 (성공 시) 또는 None (실패 시)
        """
        try:
            symbol = self._convert_symbol_format(symbol)
            
            # 시장 타입에 따른 추가 설정
            params = {}
            if self.market_type == 'futures' and self.exchange_id == 'binance':
                # 바이낸스 선물의 경우 필요한 파라미터
                params = {
                    'type': 'future',
                }
            
            orders = self.exchange.fetch_open_orders(symbol, params=params)
            
            if self.market_type == 'futures':
                logger.info(f"선물 미체결 주문 조회: {symbol}, 개수: {len(orders)}")
                
            return orders
        
        except Exception as e:
            logger.error(f"미체결 주문 조회 중 오류 발생: {e}")
            return None

# 테스트 코드
if __name__ == "__main__":
    # API 키가 설정되어 있지 않으면 테스트 모드로 실행
    if not BINANCE_API_KEY:
        print("API 키가 설정되어 있지 않아 테스트 모드로 실행합니다.")
        exchange = ExchangeAPI(exchange_id='binance')
        exchange.exchange.set_sandbox_mode(True)
    else:
        exchange = ExchangeAPI(exchange_id='binance')
    
    # 시세 정보 조회 테스트
    ticker = exchange.get_ticker()
    print(f"현재 {exchange.symbol} 시세: {ticker['last']} {ticker['quote']}")
    
    # OHLCV 데이터 조회 테스트
    ohlcv = exchange.get_ohlcv(limit=5)
    print("\nOHLCV 데이터 (최근 5개):")
    print(ohlcv)
