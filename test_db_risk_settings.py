#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
리스크 관리 설정 DB 저장 테스트
"""

import sys
import os
import json
from datetime import datetime

# 프로젝트 루트 디렉토리 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.db_manager import DatabaseManager

def test_risk_settings_db():
    """리스크 설정이 DB에 저장되고 불러와지는지 테스트"""
    
    print("=" * 50)
    print("리스크 관리 설정 DB 저장 테스트")
    print("=" * 50)
    
    # DB 매니저 초기화
    db = DatabaseManager()
    
    # 테스트용 봇 상태 생성
    test_bot_state = {
        'exchange_id': 'binance',
        'symbol': 'BTC/USDT',
        'timeframe': '15m',
        'strategy': 'RSI_14_70_30',
        'market_type': 'spot',
        'leverage': 1,
        'is_running': True,
        'test_mode': True,
        'updated_at': datetime.now().isoformat(),
        'parameters': {
            'stop_loss_pct': 0.02,
            'take_profit_pct': 0.08,
            'max_position_size': 0.25  # 25% 최대 포지션
        },
        'additional_info': {
            'interval': 5
        }
    }
    
    print("\n1. 봇 상태 저장 중...")
    print(f"저장할 리스크 설정:")
    print(f"  - 손절매: {test_bot_state['parameters']['stop_loss_pct']*100}%")
    print(f"  - 이익실현: {test_bot_state['parameters']['take_profit_pct']*100}%")
    print(f"  - 최대 포지션 크기: {test_bot_state['parameters']['max_position_size']*100}%")
    
    # 상태 저장
    success = db.save_bot_state(test_bot_state)
    
    if success:
        print("✅ 봇 상태 저장 성공")
    else:
        print("❌ 봇 상태 저장 실패")
        return
    
    # 상태 불러오기
    print("\n2. 봇 상태 불러오기...")
    loaded_state = db.load_bot_state()
    
    if loaded_state:
        print("✅ 봇 상태 불러오기 성공")
        
        # parameters 확인
        if 'parameters' in loaded_state and loaded_state['parameters']:
            params = loaded_state['parameters']
            print(f"\n불러온 리스크 설정:")
            print(f"  - 손절매: {params.get('stop_loss_pct', 0)*100}%")
            print(f"  - 이익실현: {params.get('take_profit_pct', 0)*100}%") 
            print(f"  - 최대 포지션 크기: {params.get('max_position_size', 0)*100}%")
            
            # 검증
            if (params.get('stop_loss_pct') == 0.02 and 
                params.get('take_profit_pct') == 0.08 and
                params.get('max_position_size') == 0.25):
                print("\n✅ 리스크 설정이 올바르게 저장/불러와졌습니다!")
            else:
                print("\n❌ 리스크 설정이 일치하지 않습니다!")
        else:
            print("\n❌ parameters 필드가 없거나 비어있습니다!")
            print(f"불러온 상태: {loaded_state}")
    else:
        print("❌ 봇 상태 불러오기 실패")
    
    print("\n" + "=" * 50)
    print("테스트 완료")
    print("=" * 50)

if __name__ == "__main__":
    test_risk_settings_db()
