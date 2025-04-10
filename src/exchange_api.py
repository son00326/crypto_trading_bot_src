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
from config import (
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
    
    def __init__(self, exchange_id=DEFAULT_EXCHANGE, symbol=DEFAULT_SYMBOL, timeframe=DEFAULT_TIMEFRAME):
        """
        거래소 API 클래스 초기화
        
        Args:
            exchange_id (str): 거래소 ID ('binance', 'upbit', 'bithumb')
            symbol (str): 거래 심볼 (예: 'BTC/USDT')
            timeframe (str): 차트 타임프레임 (예: '1m', '1h', '1d')
        """
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = self._initialize_exchange()
        
    def _initialize_exchange(self):
        """거래소 객체 초기화"""
        try:
            if self.exchange_id == 'binance':
                exchange = ccxt.binance({
                    'apiKey': BINANCE_API_KEY,
                    'secret': BINANCE_API_SECRET,
                    'enableRateLimit': True,
                })
            elif self.exchange_id == 'upbit':
                exchange = ccxt.upbit({
                    'apiKey': UPBIT_API_KEY,
                    'secret': UPBIT_API_SECRET,
                    'enableRateLimit': True,
                })
            elif self.exchange_id == 'bithumb':
                exchange = ccxt.bithumb({
                    'apiKey': BITHUMB_API_KEY,
                    'secret': BITHUMB_API_SECRET,
                    'enableRateLimit': True,
                })
            else:
                raise ValueError(f"지원하지 않는 거래소입니다: {self.exchange_id}")
            
            logger.info(f"{self.exchange_id} 거래소에 연결되었습니다.")
            return exchange
        
        except Exception as e:
            logger.error(f"거래소 초기화 중 오류 발생: {e}")
            raise
    
    def get_ticker(self, symbol=None):
        """현재 시세 정보 조회"""
        try:
            symbol = symbol or self.symbol
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"시세 정보 조회 중 오류 발생: {e}")
            return None
    
    def get_ohlcv(self, symbol=None, timeframe=None, limit=100):
        """OHLCV 데이터 조회 (봉 데이터)"""
        try:
            symbol = symbol or self.symbol
            timeframe = timeframe or self.timeframe
            
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
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
    
    def create_market_buy_order(self, symbol=None, amount=None):
        """시장가 매수 주문"""
        try:
            symbol = symbol or self.symbol
            if amount is None:
                raise ValueError("주문 수량을 지정해야 합니다.")
            
            order = self.exchange.create_market_buy_order(symbol, amount)
            logger.info(f"시장가 매수 주문 성공: {order}")
            return order
        
        except Exception as e:
            logger.error(f"시장가 매수 주문 중 오류 발생: {e}")
            return None
    
    def create_market_sell_order(self, symbol=None, amount=None):
        """시장가 매도 주문"""
        try:
            symbol = symbol or self.symbol
            if amount is None:
                raise ValueError("주문 수량을 지정해야 합니다.")
            
            order = self.exchange.create_market_sell_order(symbol, amount)
            logger.info(f"시장가 매도 주문 성공: {order}")
            return order
        
        except Exception as e:
            logger.error(f"시장가 매도 주문 중 오류 발생: {e}")
            return None
    
    def create_limit_buy_order(self, symbol=None, amount=None, price=None):
        """지정가 매수 주문"""
        try:
            symbol = symbol or self.symbol
            if amount is None or price is None:
                raise ValueError("주문 수량과 가격을 지정해야 합니다.")
            
            order = self.exchange.create_limit_buy_order(symbol, amount, price)
            logger.info(f"지정가 매수 주문 성공: {order}")
            return order
        
        except Exception as e:
            logger.error(f"지정가 매수 주문 중 오류 발생: {e}")
            return None
    
    def create_limit_sell_order(self, symbol=None, amount=None, price=None):
        """지정가 매도 주문"""
        try:
            symbol = symbol or self.symbol
            if amount is None or price is None:
                raise ValueError("주문 수량과 가격을 지정해야 합니다.")
            
            order = self.exchange.create_limit_sell_order(symbol, amount, price)
            logger.info(f"지정가 매도 주문 성공: {order}")
            return order
        
        except Exception as e:
            logger.error(f"지정가 매도 주문 중 오류 발생: {e}")
            return None
    
    def cancel_order(self, order_id, symbol=None):
        """주문 취소"""
        try:
            symbol = symbol or self.symbol
            result = self.exchange.cancel_order(order_id, symbol)
            logger.info(f"주문 취소 성공: {result}")
            return result
        
        except Exception as e:
            logger.error(f"주문 취소 중 오류 발생: {e}")
            return None
    
    def get_order_status(self, order_id, symbol=None):
        """주문 상태 조회"""
        try:
            symbol = symbol or self.symbol
            order = self.exchange.fetch_order(order_id, symbol)
            return order
        
        except Exception as e:
            logger.error(f"주문 상태 조회 중 오류 발생: {e}")
            return None
    
    def get_open_orders(self, symbol=None):
        """미체결 주문 조회"""
        try:
            symbol = symbol or self.symbol
            orders = self.exchange.fetch_open_orders(symbol)
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
