#!/usr/bin/env python3
"""
바이낸스 자동 손절매/이익실현 기능 테스트
"""

import os
import sys
from pathlib import Path
import asyncio
import time

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.api import set_stop_loss_take_profit
from src.exchange_api import ExchangeAPI

def test_binance_stop_loss_take_profit():
    """바이낸스 자동 손절/익절 설정 테스트"""
    print("=" * 60)
    print("바이낸스 자동 손절매/이익실현 기능 테스트")
    print("=" * 60)
    
    # 환경변수에서 API 키 확인
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        print("❌ 환경변수 BINANCE_API_KEY와 BINANCE_API_SECRET이 설정되어 있지 않습니다.")
        print("export BINANCE_API_KEY='your_api_key' 형식으로 설정해주세요.")
        return
    
    # 바이낸스 선물 거래소 API 초기화
    print("\n1. 바이낸스 선물 거래소 API 초기화...")
    try:
        exchange_api = ExchangeAPI(
            exchange_id='binance',
            symbol='BTC/USDT',
            market_type='futures',
            leverage=10
        )
        print("✅ 거래소 API 초기화 성공")
    except Exception as e:
        print(f"❌ 거래소 API 초기화 실패: {e}")
        return
    
    # 현재 포지션 확인
    print("\n2. 현재 포지션 확인...")
    try:
        positions = exchange_api.get_positions('BTC/USDT')
        if positions:
            for pos in positions:
                print(f"  - 심볼: {pos.get('symbol')}, 사이즈: {pos.get('contracts', 0)}, PnL: {pos.get('unrealizedPnl', 0)}")
        else:
            print("  - 현재 열린 포지션이 없습니다.")
    except Exception as e:
        print(f"❌ 포지션 조회 실패: {e}")
    
    # 테스트용 손절/익절 설정 (실제 포지션이 없어도 API 호출 테스트)
    print("\n3. 손절/익절 주문 설정 테스트...")
    test_position_info = {
        'symbol': 'BTCUSDT',
        'entry_price': 40000,  # 가상의 진입가
        'position_qty': 0.01,   # 가상의 포지션 수량
        'side': 'long'         # 매수 포지션
    }
    
    stop_loss_pct = 0.03     # 3% 손절
    take_profit_pct = 0.06   # 6% 익절
    
    # 손절가와 익절가 계산
    stop_loss_price = test_position_info['entry_price'] * (1 - stop_loss_pct)
    take_profit_price = test_position_info['entry_price'] * (1 + take_profit_pct)
    
    print(f"  - 심볼: {test_position_info['symbol']}")
    print(f"  - 진입가: ${test_position_info['entry_price']:,.2f}")
    print(f"  - 수량: {test_position_info['position_qty']}")
    print(f"  - 손절가 ({stop_loss_pct*100}%): ${stop_loss_price:,.2f}")
    print(f"  - 익절가 ({take_profit_pct*100}%): ${take_profit_price:,.2f}")
    
    # set_stop_loss_take_profit 함수 직접 호출
    try:
        result = set_stop_loss_take_profit(
            api_key=api_key,
            api_secret=api_secret,
            symbol=test_position_info['symbol'],
            stop_loss=stop_loss_price,
            take_profit=take_profit_price,
            position_side='BOTH'  # 또는 'LONG' / 'SHORT'
        )
        
        if result.get('success'):
            print("✅ 손절/익절 주문 설정 성공!")
            if result.get('stop_loss_order'):
                print(f"  - 손절 주문 ID: {result['stop_loss_order'].get('orderId')}")
            if result.get('take_profit_order'):
                print(f"  - 익절 주문 ID: {result['take_profit_order'].get('orderId')}")
        else:
            print(f"❌ 손절/익절 주문 설정 실패: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ 손절/익절 주문 설정 중 오류 발생: {e}")
    
    # 현재 미체결 주문 확인
    print("\n4. 현재 미체결 주문 확인...")
    try:
        open_orders = exchange_api.get_open_orders('BTC/USDT')
        if open_orders:
            for order in open_orders:
                print(f"  - 주문 ID: {order.get('id')}, 타입: {order.get('type')}, 가격: {order.get('price')}")
        else:
            print("  - 현재 미체결 주문이 없습니다.")
    except Exception as e:
        print(f"❌ 미체결 주문 조회 실패: {e}")
    
    print("\n" + "=" * 60)
    print("테스트 완료")

if __name__ == "__main__":
    # 이벤트 루프 생성 및 실행
    try:
        test_binance_stop_loss_take_profit()
    except KeyboardInterrupt:
        print("\n\n테스트가 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n\n예기치 않은 오류 발생: {e}")
        import traceback
        traceback.print_exc()
