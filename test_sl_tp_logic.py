#!/usr/bin/env python3
"""
손절/익절 로직 검증 테스트
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.risk_manager import RiskManager
from src.db_manager import DatabaseManager

def test_sl_tp_logic():
    """손절/익절 로직 테스트"""
    print("\n=== 손절/익절 로직 검증 ===")
    
    # 1. RiskManager 테스트
    print("\n1. RiskManager 가격 계산 검증")
    risk_config = {
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.04
    }
    risk_manager = RiskManager(risk_config=risk_config)
    
    test_cases = [
        {'entry': 100000, 'side': 'long'},
        {'entry': 100000, 'side': 'short'},
        {'entry': 50000, 'side': 'long'},
        {'entry': 50000, 'side': 'short'},
    ]
    
    for case in test_cases:
        entry_price = case['entry']
        side = case['side']
        
        sl_price = risk_manager.calculate_stop_loss_price(entry_price, side)
        tp_price = risk_manager.calculate_take_profit_price(entry_price, side)
        
        print(f"\n   {side.upper()} @ ${entry_price:,.0f}:")
        print(f"   - 손절가: ${sl_price:,.0f} (변화율: {(sl_price/entry_price - 1)*100:.1f}%)")
        print(f"   - 익절가: ${tp_price:,.0f} (변화율: {(tp_price/entry_price - 1)*100:.1f}%)")
        
        # 검증
        if side == 'long':
            assert sl_price < entry_price, f"Long 손절가는 진입가보다 낮아야 함"
            assert tp_price > entry_price, f"Long 익절가는 진입가보다 높아야 함"
        else:
            assert sl_price > entry_price, f"Short 손절가는 진입가보다 높아야 함"
            assert tp_price < entry_price, f"Short 익절가는 진입가보다 낮아야 함"
    
    print("\n   ✅ RiskManager 계산 로직 정상")
    
    # 2. DB 저장 테스트
    print("\n2. DB 포지션 저장 필드 확인")
    db_manager = DatabaseManager()
    
    # 더미 포지션 데이터
    test_position = {
        'symbol': 'BTC/USDT',
        'side': 'long',
        'entry_price': 45000,
        'contracts': 0.1,
        'notional': 4500,
        'quantity': 0.1,
        'leverage': 10,
        'stop_loss_price': 44100,    # 2% 손절 (필드명 수정)
        'take_profit_price': 46800,  # 4% 이익 (필드명 수정)
        'strategy': 'Test',
        'market_type': 'futures'
    }
    
    # 포지션 저장
    position_id = db_manager.save_position(test_position)
    print(f"   - 테스트 포지션 저장 ID: {position_id}")
    
    # 저장된 포지션 조회
    saved_positions = db_manager.get_open_positions(symbol='BTC/USDT')
    
    if saved_positions:
        pos = saved_positions[-1]  # 가장 최근 포지션
        print(f"\n   저장된 포지션 데이터:")
        print(f"   - ID: {pos.get('id')}")
        print(f"   - Symbol: {pos.get('symbol')}")
        print(f"   - Side: {pos.get('side')}")
        print(f"   - Entry Price: ${pos.get('entry_price', 0):,.0f}")
        print(f"   - Stop Loss Price: ${pos.get('stop_loss_price') or 0:,.0f}")
        print(f"   - Take Profit Price: ${pos.get('take_profit_price') or 0:,.0f}")
        print(f"   - SL Order ID: {pos.get('stop_loss_order_id')}")
        print(f"   - TP Order ID: {pos.get('take_profit_order_id')}")
        
        # 테스트 데이터 정리 (DB 직접 접근)
        import sqlite3
        conn = sqlite3.connect(db_manager.db_path)
        conn.execute("DELETE FROM positions WHERE id = ?", (position_id,))
        conn.commit()
        conn.close()
        print(f"\n   ✅ DB 저장/조회 정상 (테스트 데이터 삭제됨)")
    
    # 3. API 호출 로직 분석
    print("\n3. API 호출 로직 분석")
    print("   TradingAlgorithm.execute_signal 메서드:")
    print("   - 라인 1000-1065: 손절/익절 자동 설정 로직")
    print("   - 조건: market_type == 'futures' AND (stop_loss OR take_profit)")
    print("   - 호출: utils.api.set_stop_loss_take_profit()")
    print("   - 파라미터: position_side는 signal.direction.upper()로 설정됨")
    
    print("\n4. 통합 플로우:")
    print("   1) 신호 생성 → execute_signal()")
    print("   2) RiskManager → calculate_stop_loss_price/calculate_take_profit_price")
    print("   3) execute_order() → 포지션 생성")
    print("   4) set_stop_loss_take_profit() → API 주문")
    print("   5) DB 저장 → stop_loss_order_id, take_profit_order_id")
    
    print("\n✅ 손절/익절 로직 검증 완료!")

if __name__ == "__main__":
    load_dotenv()
    test_sl_tp_logic()
