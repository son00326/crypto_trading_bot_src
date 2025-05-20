#!/usr/bin/env python3
import os
import ccxt
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# API 키 가져오기
api_key = os.getenv('BINANCE_API_KEY', '')
api_secret = os.getenv('BINANCE_API_SECRET', '')

print(f"API 키 존재 여부: {'설정됨' if api_key else '설정 안됨'}")
print(f"API 시크릿 존재 여부: {'설정됨' if api_secret else '설정 안됨'}")

# 바이낸스 연결 테스트
try:
    print("\n1. 일반 바이낸스 연결 테스트:")
    binance = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True
    })
    
    # 서버 상태 확인
    status = binance.fetch_status()
    print(f"서버 상태: {status}")
    
    # 심볼 정보 가져오기
    print("\n2. 심볼 정보 가져오기:")
    markets = binance.load_markets()
    print(f"사용 가능한 심볼 수: {len(markets)}")
    
    # 현물 시장 잔고 조회
    print("\n3. 현물 시장 잔고 조회:")
    balance = binance.fetch_balance()
    print(f"총 자산 개수: {len(balance['total'])}")
    
    # 선물 시장 설정
    print("\n4. 선물 시장 설정:")
    future_binance = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future'
        }
    })
    
    # 포지션 조회
    print("\n5. 선물 포지션 조회:")
    positions = future_binance.fetch_positions(['BTC/USDT'])
    print(f"포지션 수: {len(positions)}")
    
except Exception as e:
    print(f"\n오류 발생: {type(e).__name__}: {str(e)}")
    
print("\n테스트 완료")
