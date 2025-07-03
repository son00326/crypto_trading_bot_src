#!/usr/bin/env python3
"""
손절/익절 자동 설정 간단 테스트
"""
import os
import sys
from dotenv import load_dotenv
import logging

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.risk_manager import RiskManager
from utils.api import set_stop_loss_take_profit, get_positions, get_open_orders

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_stop_loss_take_profit():
    """손절/익절 테스트"""
    load_dotenv()
    
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        print("❌ API 키가 설정되지 않았습니다.")
        return
    
    symbol = 'BTC/USDT'
    
    print("\n=== 손절/익절 자동 설정 테스트 ===")
    
    # 1. 현재 포지션 확인
    print("\n1. 현재 포지션 확인")
    positions = get_positions(api_key, api_secret, symbol)
    
    if not positions:
        print("   ❌ 열린 포지션이 없습니다.")
        print("   💡 테스트를 위해 선물 포지션을 먼저 생성해주세요.")
        return
    
    position = positions[0]
    print(f"   ✅ 포지션 발견: {position['side']} {position['contracts']} @ ${position['entry_price']:,.2f}")
    
    # 2. RiskManager로 손절/익절 가격 계산
    print("\n2. RiskManager로 손절/익절 가격 계산")
    risk_manager = RiskManager(stop_loss_pct=0.02, take_profit_pct=0.04)
    
    entry_price = position['entry_price']
    position_side = position['side'].lower()  # 'LONG' -> 'long'
    
    stop_loss_price = risk_manager.calculate_stop_loss_price(entry_price, position_side)
    take_profit_price = risk_manager.calculate_take_profit_price(entry_price, position_side)
    
    print(f"   - 진입가: ${entry_price:,.2f}")
    print(f"   - 손절가: ${stop_loss_price:,.2f} ({position_side} 포지션)")
    print(f"   - 익절가: ${take_profit_price:,.2f} ({position_side} 포지션)")
    
    # 3. 기존 손절/익절 주문 확인
    print("\n3. 기존 손절/익절 주문 확인")
    open_orders = get_open_orders(api_key, api_secret, symbol)
    
    existing_sl = False
    existing_tp = False
    
    for order in open_orders:
        order_type = order.get('type', '').lower()
        if 'stop' in order_type and 'profit' not in order_type:
            existing_sl = True
            print(f"   - 기존 손절 주문: {order.get('side')} @ ${order.get('stopPrice', 0):,.2f}")
        elif 'take_profit' in order_type or 'profit' in order_type:
            existing_tp = True
            print(f"   - 기존 익절 주문: {order.get('side')} @ ${order.get('stopPrice', 0):,.2f}")
    
    if existing_sl and existing_tp:
        print("   ✅ 이미 손절/익절 주문이 설정되어 있습니다.")
        return
    
    # 4. 손절/익절 주문 설정
    print("\n4. 손절/익절 주문 설정")
    user_input = input("   손절/익절 주문을 설정하시겠습니까? (y/n): ")
    
    if user_input.lower() != 'y':
        print("   취소되었습니다.")
        return
    
    result = set_stop_loss_take_profit(
        api_key=api_key,
        api_secret=api_secret,
        symbol=symbol,
        stop_loss=stop_loss_price if not existing_sl else None,
        take_profit=take_profit_price if not existing_tp else None,
        position_side=position['side']  # 'LONG' or 'SHORT'
    )
    
    if result['success']:
        print("\n   ✅ 손절/익절 주문 설정 성공!")
        if result.get('stop_loss_order'):
            print(f"   - 손절 주문 ID: {result['stop_loss_order']['id']}")
        if result.get('take_profit_order'):
            print(f"   - 익절 주문 ID: {result['take_profit_order']['id']}")
    else:
        print(f"\n   ❌ 설정 실패: {result.get('error')}")
    
    # 5. 최종 확인
    print("\n5. 최종 주문 상태 확인")
    final_orders = get_open_orders(api_key, api_secret, symbol)
    
    sl_count = 0
    tp_count = 0
    
    for order in final_orders:
        order_type = order.get('type', '').lower()
        if 'stop' in order_type and 'profit' not in order_type:
            sl_count += 1
        elif 'take_profit' in order_type or 'profit' in order_type:
            tp_count += 1
    
    print(f"   - 손절 주문: {sl_count}개")
    print(f"   - 익절 주문: {tp_count}개")
    
    print("\n✅ 테스트 완료!")

if __name__ == "__main__":
    test_stop_loss_take_profit()
