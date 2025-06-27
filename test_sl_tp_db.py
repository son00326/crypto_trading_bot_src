#!/usr/bin/env python3
"""
SL/TP DB 기능 테스트
"""

import os
import sys
from datetime import datetime
import time

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.db_manager import DatabaseManager

def test_sl_tp_db():
    """SL/TP DB 기능 테스트"""
    print("=== SL/TP DB 기능 테스트 ===\n")
    
    try:
        # DB 매니저 초기화
        db = DatabaseManager()
        print("✅ DatabaseManager 초기화 성공")
        
        # 이전 테스트 데이터 정리
        try:
            db.execute_query("DELETE FROM stop_loss_orders WHERE order_id LIKE '%TEST%'")
            print("✅ 이전 테스트 데이터 정리 완료")
        except:
            pass
        
        # 테스트용 포지션 생성
        test_position = {
            'symbol': 'BTC/USDT',
            'side': 'long',
            'contracts': 0.001,
            'entry_price': 100000.0,
            'status': 'open',
            'opened_at': datetime.now()
        }
        
        # 포지션 저장
        position_result = db.save_position(test_position)
        
        # save_position이 position ID를 반환하는지 확인
        if isinstance(position_result, int):
            position_id = position_result
            print(f"✅ 테스트 포지션 생성 성공 (ID: {position_id})")
        elif position_result:
            # ID를 얻기 위해 방금 생성한 포지션 조회
            positions = db.get_open_positions('BTC/USDT')
            if positions:
                position_id = positions[-1].get('id')
                print(f"✅ 테스트 포지션 생성 성공 (ID: {position_id})")
            else:
                print("❌ 포지션 ID를 찾을 수 없습니다")
                return
        else:
            print("❌ 테스트 포지션 생성 실패")
            return
        
        # 타임스탬프 기반 유니크 ID 생성
        timestamp = int(time.time() * 1000)
        
        # SL/TP 주문 정보
        sl_order = {
            'order_id': f'SL_TEST_{timestamp}',
            'symbol': 'BTC/USDT',
            'order_type': 'stop_loss',
            'trigger_price': 95000.0,
            'amount': 0.001,
            'side': 'sell',
            'raw_data': {'test': 'stop_loss_order'}
        }
        
        tp_order = {
            'order_id': f'TP_TEST_{timestamp + 1}',
            'symbol': 'BTC/USDT',
            'order_type': 'take_profit',
            'trigger_price': 110000.0,
            'amount': 0.001,
            'side': 'sell',
            'raw_data': {'test': 'take_profit_order'}
        }
        
        # SL/TP 주문 저장
        sl_id = db.save_stop_loss_order(position_id, sl_order)
        tp_id = db.save_stop_loss_order(position_id, tp_order)
        
        if sl_id and tp_id:
            print(f"✅ SL 주문 저장 성공 (ID: {sl_id})")
            print(f"✅ TP 주문 저장 성공 (ID: {tp_id})")
        else:
            print("❌ SL/TP 주문 저장 실패")
            return
        
        # 활성 SL/TP 주문 조회
        active_orders = db.get_active_stop_loss_orders(position_id=position_id)
        print(f"\n활성 SL/TP 주문 수: {len(active_orders)}")
        for order in active_orders:
            print(f"  - {order['order_type']}: {order['order_id']} @ {order['trigger_price']}")
        
        # 포지션 정보 확인 (SL/TP 가격이 업데이트되었는지)
        positions = db.get_open_positions('BTC/USDT')
        if positions:
            position = positions[-1]
            print(f"\n포지션 SL/TP 정보:")
            print(f"  - SL 가격: {position.get('stop_loss_price')}")
            print(f"  - TP 가격: {position.get('take_profit_price')}")
            print(f"  - SL 주문 ID: {position.get('stop_loss_order_id')}")
            print(f"  - TP 주문 ID: {position.get('take_profit_order_id')}")
        
        # SL 주문 상태 업데이트 테스트
        if db.update_stop_loss_order_status(sl_order['order_id'], 'triggered'):
            print(f"\n✅ SL 주문 상태 업데이트 성공 (triggered)")
        
        # 업데이트된 주문 확인
        active_orders = db.get_active_stop_loss_orders(position_id=position_id)
        print(f"활성 SL/TP 주문 수 (SL 트리거 후): {len(active_orders)}")
        
        # 테스트 정리 - 포지션 닫기
        db.close_position(position_id, 105000.0, 500.0)
        print("\n✅ 테스트 포지션 닫기 완료")
        
    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sl_tp_db()
