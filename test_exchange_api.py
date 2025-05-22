#!/usr/bin/env python3
"""
거래소 API 연결 테스트 스크립트
"""
from src.exchange_api import ExchangeAPI
import time

def test_exchange_connection():
    """거래소 API 연결 테스트"""
    print("거래소 API 연결 테스트 시작...")
    
    # 테스트 모드로 거래소 API 초기화
    api = ExchangeAPI(exchange_id='binance', symbol='BTC/USDT', market_type='spot')
    print(f"거래소 {api.exchange_id} 연결 성공, 시장: {api.market_type}, 심볼: {api.symbol}")
    
    # 현재 시세 조회 테스트
    try:
        ticker = api.get_ticker()
        print(f"현재 {api.symbol} 가격: {ticker['last']}")
    except Exception as e:
        print(f"시세 조회 중 오류 발생: {str(e)}")
    
    # 계정 잔고 조회 테스트 (테스트 모드)
    try:
        balances = api.get_balance()
        print(f"계정 잔고: {balances}")
    except Exception as e:
        print(f"잔고 조회 중 오류 발생: {str(e)}")
    
    print("거래소 API 연결 테스트 완료")

if __name__ == "__main__":
    test_exchange_connection()
