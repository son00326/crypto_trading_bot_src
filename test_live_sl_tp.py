#!/usr/bin/env python3
"""
바이낸스 선물 손절/익절 실제 테스트
작은 포지션을 열고 자동 손절/익절 설정 테스트
"""

import os
import sys
from pathlib import Path
import asyncio
from dotenv import load_dotenv
import time

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.exchange_api import ExchangeAPI
from utils.api import set_stop_loss_take_profit

# 환경 변수 로드
load_dotenv()

def test_live_sl_tp():
    """실제 포지션 진입 후 손절/익절 테스트"""
    
    print("============================================================")
    print("바이낸스 선물 손절/익절 실제 테스트")
    print("⚠️ 주의: 이 테스트는 실제로 작은 포지션을 생성합니다!")
    print("============================================================")
    
    # API 키 확인
    api_key = os.getenv('BINANCE_API_KEY', '')
    api_secret = os.getenv('BINANCE_API_SECRET', '')
    
    if not api_key or not api_secret:
        print("❌ 환경 변수에서 BINANCE_API_KEY 또는 BINANCE_API_SECRET를 찾을 수 없습니다.")
        return
    
    # 사용자 확인
    response = input("\n정말로 테스트 포지션을 생성하시겠습니까? (yes/no): ")
    if response.lower() != 'yes':
        print("테스트가 취소되었습니다.")
        return
    
    try:
        # 1. ExchangeAPI 초기화
        print("\n1. 바이낸스 선물 ExchangeAPI 초기화...")
        exchange_api = ExchangeAPI(
            exchange_id='binance',
            symbol='BTCUSDT',
            timeframe='1m',
            market_type='futures',
            leverage=10
        )
        print("✅ ExchangeAPI 초기화 성공")
        
        # 2. 현재 가격 확인
        print("\n2. 현재 BTC 가격 확인...")
        ticker = exchange_api.exchange.fetch_ticker('BTC/USDT')
        current_price = ticker['last']
        print(f"  - 현재 가격: ${current_price:,.2f}")
        
        # 3. 최소 주문 수량 확인
        print("\n3. 최소 주문 수량 확인...")
        markets = exchange_api.exchange.load_markets()
        btc_market = markets.get('BTC/USDT')
        min_amount = btc_market['limits']['amount']['min']
        print(f"  - 최소 주문 수량: {min_amount} BTC")
        
        # 테스트 수량 설정 (최소 수량의 2배)
        test_amount = min_amount * 2
        test_value = test_amount * current_price
        print(f"  - 테스트 수량: {test_amount} BTC (≈ ${test_value:.2f})")
        
        # 4. 테스트 포지션 생성
        print("\n4. 테스트 포지션 생성 중...")
        try:
            # 롱 포지션 진입
            order = exchange_api.exchange.create_market_order(
                symbol='BTC/USDT',
                side='buy',
                amount=test_amount
            )
            print(f"✅ 포지션 생성 성공!")
            print(f"  - 주문 ID: {order['id']}")
            print(f"  - 수량: {order['amount']} BTC")
            print(f"  - 평균 가격: ${order.get('average', current_price):,.2f}")
            
            # 잠시 대기
            print("\n⏳ 포지션 확인을 위해 2초 대기...")
            time.sleep(2)
            
            # 5. 손절/익절 설정
            print("\n5. 자동 손절/익절 설정...")
            stop_loss_price = current_price * 0.97  # 3% 손절
            take_profit_price = current_price * 1.06  # 6% 익절
            
            print(f"  - 손절가: ${stop_loss_price:,.2f} (현재가 -3%)")
            print(f"  - 익절가: ${take_profit_price:,.2f} (현재가 +6%)")
            
            sl_tp_result = set_stop_loss_take_profit(
                api_key=api_key,
                api_secret=api_secret,
                symbol='BTC/USDT',
                stop_loss=stop_loss_price,
                take_profit=take_profit_price,
                position_side='LONG'
            )
            
            if sl_tp_result.get('success'):
                print("✅ 손절/익절 설정 성공!")
                for message in sl_tp_result.get('message', []):
                    print(f"  - {message}")
                
                # 6. 대기 열린 주문 확인
                print("\n6. 대기 중인 주문 확인...")
                open_orders = exchange_api.exchange.fetch_open_orders('BTC/USDT')
                if open_orders:
                    print(f"  - {len(open_orders)}개의 대기 주문이 있습니다:")
                    for idx, order in enumerate(open_orders, 1):
                        print(f"    {idx}. {order['type']} {order['side']} @ ${order.get('stopPrice', order.get('price', 0)):,.2f}")
                
                # 7. 포지션 청산
                print("\n7. 테스트 포지션 청산...")
                response = input("포지션을 청산하시겠습니까? (yes/no): ")
                
                if response.lower() == 'yes':
                    # 대기 중인 손절/익절 주문 취소
                    for order in open_orders:
                        try:
                            exchange_api.exchange.cancel_order(order['id'], 'BTC/USDT')
                            print(f"  - 주문 {order['id']} 취소됨")
                        except:
                            pass
                    
                    # 포지션 청산
                    close_order = exchange_api.exchange.create_market_order(
                        symbol='BTC/USDT',
                        side='sell',
                        amount=test_amount,
                        params={'reduceOnly': True}
                    )
                    print("✅ 포지션 청산 완료!")
                    print(f"  - 청산 가격: ${close_order.get('average', current_price):,.2f}")
                else:
                    print("⚠️ 포지션이 청산되지 않았습니다. 수동으로 청산해주세요!")
                    
            else:
                print(f"❌ 손절/익절 설정 실패: {sl_tp_result.get('message')}")
                # 포지션 즉시 청산
                print("\n포지션을 즉시 청산합니다...")
                close_order = exchange_api.exchange.create_market_order(
                    symbol='BTC/USDT',
                    side='sell',
                    amount=test_amount,
                    params={'reduceOnly': True}
                )
                print("✅ 포지션 청산 완료")
                
        except Exception as e:
            print(f"❌ 포지션 생성 실패: {str(e)}")
            
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n============================================================")
    print("테스트 완료")

if __name__ == "__main__":
    test_live_sl_tp()
