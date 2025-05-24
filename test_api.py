#!/usr/bin/env python3
import ccxt
import sys
import requests
import time

print(f"Python 버전: {sys.version}")
print(f"CCXT 버전: {ccxt.__version__}")

# 시스템 정보 출력
print("\n===== 시스템 정보 =====")
print(f"\ud604재 시간: {time.ctime()}")

# 네트워크 접속 상태 확인
print("\n===== 네트워크 접속 테스트 =====")
try:
    print("Binance.com 연결 테스트...")
    response = requests.get('https://api.binance.com/api/v3/time', timeout=10)
    print(f"Binance 응답: {response.status_code} {response.reason}")
    print(f"Binance 서버 시간: {response.json()}")
except Exception as e:
    print(f"Binance 연결 오류: {str(e)}")

# API 키 직접 입력
api_key = "wtA4vC2hpvJUcimjdRUbGTpa3pHXQFBFCh1PoMyKQ9Favux4qJQ7gvyGRZ6Ts8I6"
api_secret = "q1mQB47ELPQm2cvLfzK3w6GGuk3NCZySLCvoL5vIIKAieifKkwW5nlLY5PkSvYso"

print(f"\n===== API 키 정보 =====")
print(f"API 키: {api_key[:5]}... (길이: {len(api_key)})")
print(f"시크릿 키: {api_secret[:5]}... (길이: {len(api_secret)})")

# 단계별 API 테스트
print("\n===== 단계 1: 기본 마켓 정보 조회 (인증 없이) =====")
try:
    # API 키 없이 접속 테스트
    public_binance = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'recvWindow': 5000,
            'adjustForTimeDifference': True
        }
    })
    
    # 기본 마켓 정보 조회
    print("\ub9c8켓 정보 조회 시도...")
    markets = public_binance.load_markets()
    print(f"마켓 정보 조회 성공: {len(markets)} 개 마켓 발견")
    
    # 일부 마켓 정보 출력
    btc_usdt = public_binance.market('BTC/USDT')
    print(f"BTC/USDT 마켓 정보: {btc_usdt['symbol']}, 최소 주문량: {btc_usdt['limits']['amount']['min']}")
except Exception as e:
    print(f"\uae30본 마켓 정보 조회 오류: {str(e)}")
    import traceback
    print(traceback.format_exc())

print("\n===== 단계 2: 개인키를 사용한 기본 API 호출 =====")
try:
    # 바이낸스 현물 인스턴스 생성
    binance = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {
            'recvWindow': 5000,
            'adjustForTimeDifference': True
        }
    })
    
    # 먼저 간단한 API 호출 시도
    print("\uac1c인 API 키를 사용한 계정 정보 조회 시도...")
    account_info = binance.privateGetAccount()
    print(f"계정 정보 조회 성공: {account_info['canTrade']}")
    
    print("\n현물 계정 잔액 조회 시도...")
    spot_balance = binance.fetch_balance()
    print("현물 잔액 조회 성공!")
    
    # 잔액 정보 출력
    for currency in ['USDT', 'BTC', 'ETH']:
        if currency in spot_balance['total'] and spot_balance['total'][currency] > 0:
            print(f"{currency} 잔액: {spot_balance['total'][currency]}")
except Exception as e:
    print(f"\uac1c인 API 호출 오류: {str(e)}")
    import traceback
    print(traceback.format_exc())
    
    # 주요 통화 잔액 출력
    print("\n현물 계정 주요 통화 잔액:")
    for currency in ['USDT', 'BTC', 'ETH', 'BNB']:
        if currency in spot_balance['total']:
            print(f"{currency}: {spot_balance['total'][currency]}")
    
    # 바이낸스 선물 인스턴스 생성
    binance_futures = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    
    print("\n2. 선물 계정 잔액 조회 시도:")
    futures_balance = binance_futures.fetch_balance()
    print("선물 잔액 조회 성공!")
    
    # 주요 통화 잔액 출력
    print("\n선물 계정 주요 통화 잔액:")
    for currency in ['USDT', 'BTC', 'ETH', 'BNB']:
        if currency in futures_balance['total']:
            print(f"{currency}: {futures_balance['total'][currency]}")
    
except Exception as e:
    print(f"\n오류 발생: {str(e)}")
    import traceback
    print(traceback.format_exc())
