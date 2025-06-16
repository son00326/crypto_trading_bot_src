#!/usr/bin/env python3
"""
바이낸스 선물 API 직접 호출 테스트
"""

import os
import sys
import requests
import hmac
import hashlib
import time
from urllib.parse import urlencode

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_signature(query_string, secret):
    """바이낸스 API 서명 생성"""
    return hmac.new(
        secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def test_direct_api():
    """바이낸스 API 직접 호출 테스트"""
    
    # API 키 확인
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        print("❌ BINANCE_API_KEY 또는 BINANCE_API_SECRET 환경 변수가 설정되지 않았습니다.")
        return
    
    print("✅ API 키 확인 완료")
    
    # 1. 현물 잔고 테스트
    print("\n1️⃣ 현물 잔고 테스트")
    timestamp = int(time.time() * 1000)
    params = {
        'timestamp': timestamp,
        'recvWindow': 10000
    }
    query_string = urlencode(params)
    signature = create_signature(query_string, api_secret)
    
    url = f"https://api.binance.com/api/v3/account?{query_string}&signature={signature}"
    headers = {'X-MBX-APIKEY': api_key}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        for balance in data['balances']:
            if balance['asset'] == 'USDT':
                print(f"✅ USDT 잔고: {balance['free']} USDT")
                break
    else:
        print(f"❌ 현물 잔고 조회 실패: {response.status_code}")
    
    # 2. 선물 포지션 v1 테스트
    print("\n2️⃣ 선물 포지션 v1 API 테스트")
    timestamp = int(time.time() * 1000)
    params = {
        'timestamp': timestamp,
        'recvWindow': 10000
    }
    query_string = urlencode(params)
    signature = create_signature(query_string, api_secret)
    
    url = f"https://fapi.binance.com/fapi/v1/positionRisk?{query_string}&signature={signature}"
    headers = {'X-MBX-APIKEY': api_key}
    
    response = requests.get(url, headers=headers)
    print(f"v1 응답 코드: {response.status_code}")
    if response.status_code != 200:
        print(f"v1 응답 내용: {response.text[:200]}...")
    
    # 3. 선물 포지션 v2 테스트
    print("\n3️⃣ 선물 포지션 v2 API 테스트")
    timestamp = int(time.time() * 1000)
    params = {
        'timestamp': timestamp,
        'recvWindow': 10000
    }
    query_string = urlencode(params)
    signature = create_signature(query_string, api_secret)
    
    url = f"https://fapi.binance.com/fapi/v2/positionRisk?{query_string}&signature={signature}"
    headers = {'X-MBX-APIKEY': api_key}
    
    response = requests.get(url, headers=headers)
    print(f"v2 응답 코드: {response.status_code}")
    
    if response.status_code == 200:
        positions = response.json()
        active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        print(f"✅ 전체 포지션: {len(positions)}개")
        print(f"✅ 활성 포지션: {len(active_positions)}개")
        
        if active_positions:
            for pos in active_positions[:3]:  # 최대 3개만 표시
                print(f"  - {pos['symbol']}: {pos['positionAmt']} ({pos['marginType']})")
    else:
        print(f"❌ v2 응답 실패: {response.text[:200]}...")
    
    # 4. 대안: 계정 정보 API
    print("\n4️⃣ 대안: 선물 계정 정보 API")
    timestamp = int(time.time() * 1000)
    params = {
        'timestamp': timestamp,
        'recvWindow': 10000
    }
    query_string = urlencode(params)
    signature = create_signature(query_string, api_secret)
    
    url = f"https://fapi.binance.com/fapi/v2/account?{query_string}&signature={signature}"
    headers = {'X-MBX-APIKEY': api_key}
    
    response = requests.get(url, headers=headers)
    print(f"계정 정보 응답 코드: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        positions = data.get('positions', [])
        active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        print(f"✅ 활성 포지션: {len(active_positions)}개")
        
        if active_positions:
            for pos in active_positions[:3]:  # 최대 3개만 표시
                print(f"  - {pos['symbol']}: {pos['positionAmt']}")

if __name__ == "__main__":
    test_direct_api()
