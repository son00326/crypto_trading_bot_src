#!/usr/bin/env python3
"""
바이낸스 API 키 유효성 검사 테스트 스크립트 (확장 버전)
다양한 엔드포인트와 설정을 사용하여 API 키를 테스트합니다
"""
import time
import hmac
import hashlib
import requests
import urllib.parse
import socket
import json

# API 키와 시크릿
API_KEY = "wtA4vC2hpvJUcimjdRUbGTpa3pHXQFBFCh1PoMyKQ9Favux4qJQ7gvyGRZ6Ts8I6"
SECRET_KEY = "q1mQB47ELPQm2cvLfzK3w6GGuk3NCZySLCvoL5vIIKAieifKkwW5nlLY5PkSvYso"

# 환경 정보 출력
print("===== 시스템 및 네트워크 정보 =====")
print(f"호스트명: {socket.gethostname()}")

# IP 주소 확인
try:
    response = requests.get('https://api.ipify.org?format=json')
    print(f"외부 IP 주소: {response.json()['ip']}")
except Exception as e:
    print(f"IP 주소 확인 오류: {str(e)}")

# 바이낸스 API 서버 목록
API_SERVERS = [
    "https://api.binance.com",  # 글로벌 API 서버
    "https://api1.binance.com",  # 백업 API 서버
    "https://api2.binance.com",  # 백업 API 서버
    "https://api3.binance.com",  # 백업 API 서버
]

FUTURES_API_SERVERS = [
    "https://fapi.binance.com",  # 선물 API 서버
    "https://dapi.binance.com",  # 코인 선물 API 서버
]

def create_signed_params():
    """서명된 파라미터 생성"""
    params = {
        'timestamp': int(time.time() * 1000),
        'recvWindow': 10000  # 더 긴 대기 시간 설정
    }
    
    # 서명 생성
    query_string = urllib.parse.urlencode(params)
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # 서명 추가
    params['signature'] = signature
    return params

def test_api_server(base_url):
    """API 서버 테스트"""
    print(f"\n===== {base_url} 테스트 =====")
    
    # 헤더 설정
    headers = {
        'X-MBX-APIKEY': API_KEY,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    # 1. 서버 상태 확인 (인증 필요 없음)
    try:
        response = requests.get(f'{base_url}/api/v3/ping')
        print(f"서버 상태: {response.status_code} {response.reason}")
    except Exception as e:
        print(f"서버 상태 확인 오류: {str(e)}")
        return  # 서버에 연결할 수 없으면 나머지 테스트 건너뛰기
    
    # 2. 인증이 필요한 API 호출 테스트
    try:
        # 서명된 파라미터 생성
        params = create_signed_params()
        
        # API 호출
        url = f'{base_url}/api/v3/account'
        response = requests.get(url, headers=headers, params=params)
        
        print(f"계정 정보 API 응답: {response.status_code} {response.reason}")
        
        if response.status_code == 200:
            account_data = response.json()
            print(f"API 키 유효성 검사 성공! 계정 거래 가능: {account_data.get('canTrade', False)}")
            # 일부 잔액 정보 출력
            balances = [b for b in account_data.get('balances', []) if float(b['free']) > 0 or float(b['locked']) > 0]
            if balances:
                print("주요 잔액 정보:")
                for balance in balances[:3]:  # 최대 3개만 출력
                    print(f"  {balance['asset']}: {balance['free']} (가용), {balance['locked']} (잠김)")
            return True  # 성공 반환
        else:
            print(f"API 키 유효성 검사 실패: {response.text}")
    except Exception as e:
        print(f"API 호출 오류: {str(e)}")
    
    return False  # 실패 반환

def test_futures_api_server(base_url):
    """선물 API 서버 테스트"""
    print(f"\n===== {base_url} 선물 API 테스트 =====")
    
    # 헤더 설정
    headers = {
        'X-MBX-APIKEY': API_KEY,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    # 1. 서버 상태 확인
    try:
        response = requests.get(f'{base_url}/fapi/v1/ping')
        print(f"선물 서버 상태: {response.status_code} {response.reason}")
    except Exception as e:
        print(f"선물 서버 상태 확인 오류: {str(e)}")
        return  # 서버에 연결할 수 없으면 나머지 테스트 건너뛰기
    
    # 2. 인증이 필요한 API 호출 테스트
    try:
        # 서명된 파라미터 생성
        params = create_signed_params()
        
        # API 호출 (USDT 선물 계정 정보)
        url = f'{base_url}/fapi/v2/account'
        response = requests.get(url, headers=headers, params=params)
        
        print(f"선물 계정 정보 API 응답: {response.status_code} {response.reason}")
        
        if response.status_code == 200:
            print("선물 API 키 유효성 검사 성공!")
            account_data = response.json()
            
            # 계정 정보 일부 출력
            if 'totalWalletBalance' in account_data:
                print(f"총 지갑 잔액: {account_data['totalWalletBalance']} USDT")
                print(f"총 미실현 손익: {account_data.get('totalUnrealizedProfit', '0')} USDT")
            return True  # 성공 반환
        else:
            print(f"선물 API 키 유효성 검사 실패: {response.text}")
    except Exception as e:
        print(f"선물 API 호출 오류: {str(e)}")
    
    return False  # 실패 반환

# 테스트 실행
print("\n===== 바이낸스 API 키 테스트 =====")
print(f"API 키: {API_KEY[:5]}...")
print(f"시크릿 키: {SECRET_KEY[:5]}...")

# 스팟 API 서버 테스트
spot_success = False
for server in API_SERVERS:
    if test_api_server(server):
        spot_success = True
        print(f"✅ {server}에서 API 키가 정상 작동합니다!")
        break
    else:
        print(f"❌ {server}에서 API 키 검증 실패")

# 선물 API 서버 테스트
futures_success = False
for server in FUTURES_API_SERVERS:
    if test_futures_api_server(server):
        futures_success = True
        print(f"✅ {server}에서 선물 API 키가 정상 작동합니다!")
        break
    else:
        print(f"❌ {server}에서 선물 API 키 검증 실패")

# 최종 결과 요약
print("\n===== 테스트 결과 요약 =====")
if spot_success:
    print("✅ 스팟 API 연결 성공")
else:
    print("❌ 스팟 API 연결 실패")

if futures_success:
    print("✅ 선물 API 연결 성공")
else:
    print("❌ 선물 API 연결 실패")

print("\n문제 해결 제안:")
if not (spot_success or futures_success):
    print("1. API 키가 아직 활성화되지 않았을 수 있습니다. 바이낸스 이메일에서 확인 링크를 클릭했는지 확인하세요.")
    print("2. IP 제한이 올바르게 설정되어 있는지 다시 확인하세요.")
    print("3. API 키를 새로 생성해 보세요.")
    print("4. 일부 지역에서는 바이낸스 접속에 VPN이 필요할 수 있습니다.")
else:
    print("일부 API 기능이 작동하지만 모든 기능이 활성화되지 않았습니다.")
    print("API 키에 필요한 모든 권한이 부여되었는지 확인하세요.")

print("\n===== 테스트 완료 =====")
