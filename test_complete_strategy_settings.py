#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
전략 설정 완전성 테스트 - 모든 전략 파라미터가 DB에 저장되는지 확인
"""

import sys
import os
import json
from datetime import datetime

# 프로젝트 루트 디렉토리 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.db_manager import DatabaseManager

def test_complete_strategy_settings():
    """전략과 모든 설정이 DB에 저장되고 불러와지는지 테스트"""
    
    print("=" * 70)
    print("전략 설정 완전성 테스트")
    print("=" * 70)
    
    # DB 매니저 초기화
    db = DatabaseManager()
    
    # 실제 웹에서 전송하는 형식과 동일한 테스트 데이터
    test_strategy_params = {
        # 리스크 관리 설정
        'stop_loss_pct': 0.03,       # 3% 손절
        'take_profit_pct': 0.06,     # 6% 이익실현
        'max_position_size': 0.2,    # 20% 최대 포지션
        
        # RSI 전략 파라미터
        'rsi_period': 14,
        'rsi_overbought': 70,
        'rsi_oversold': 30,
        
        # 추가 전략 설정
        'use_trailing_stop': True,
        'trailing_stop_pct': 0.02,
        'partial_tp_enabled': True,
        'partial_tp_levels': [
            {'percentage': 0.5, 'profit_pct': 0.03},
            {'percentage': 0.3, 'profit_pct': 0.05}
        ]
    }
    
    # 테스트용 봇 상태 생성
    test_bot_state = {
        'exchange_id': 'binance',
        'symbol': 'BTC/USDT',
        'timeframe': '15m',
        'strategy': 'RSI_14_70_30',  # 전략 이름
        'market_type': 'spot',
        'leverage': 1,
        'is_running': True,
        'test_mode': True,
        'updated_at': datetime.now().isoformat(),
        'parameters': test_strategy_params,  # 모든 전략 파라미터
        'additional_info': {
            'interval': 5,
            'start_time': datetime.now().isoformat()
        }
    }
    
    print("\n1. 봇 상태 및 전략 설정 저장 중...")
    print(f"\n전략: {test_bot_state['strategy']}")
    print(f"\n저장할 전략 파라미터:")
    for key, value in test_strategy_params.items():
        if isinstance(value, list):
            print(f"  - {key}: {json.dumps(value, indent=4)}")
        else:
            print(f"  - {key}: {value}")
    
    # 상태 저장
    success = db.save_bot_state(test_bot_state)
    
    if success:
        print("\n✅ 봇 상태 및 전략 설정 저장 성공")
    else:
        print("\n❌ 봇 상태 저장 실패")
        return
    
    # 상태 불러오기
    print("\n2. 봇 상태 불러오기...")
    loaded_state = db.load_bot_state()
    
    if loaded_state:
        print("✅ 봇 상태 불러오기 성공")
        
        print(f"\n불러온 전략: {loaded_state.get('strategy')}")
        
        # parameters 확인
        if 'parameters' in loaded_state and loaded_state['parameters']:
            params = loaded_state['parameters']
            print(f"\n불러온 전략 파라미터:")
            
            # 각 파라미터 검증
            all_correct = True
            for key, expected_value in test_strategy_params.items():
                loaded_value = params.get(key)
                if isinstance(expected_value, list):
                    print(f"  - {key}: {json.dumps(loaded_value, indent=4)}")
                    if loaded_value != expected_value:
                        print(f"    ❌ 불일치! 예상: {expected_value}")
                        all_correct = False
                else:
                    print(f"  - {key}: {loaded_value}")
                    if loaded_value != expected_value:
                        print(f"    ❌ 불일치! 예상: {expected_value}")
                        all_correct = False
            
            if all_correct:
                print("\n✅ 모든 전략 설정이 올바르게 저장/불러와졌습니다!")
            else:
                print("\n❌ 일부 전략 설정이 일치하지 않습니다!")
        else:
            print("\n❌ parameters 필드가 없거나 비어있습니다!")
            print(f"불러온 상태: {loaded_state}")
    else:
        print("❌ 봇 상태 불러오기 실패")
    
    # 추가 검증: 실제 거래 시 필요한 모든 정보가 있는지 확인
    print("\n3. 거래 실행에 필요한 정보 검증...")
    if loaded_state and loaded_state.get('parameters'):
        required_fields = [
            ('전략 이름', loaded_state.get('strategy')),
            ('손절매 %', loaded_state['parameters'].get('stop_loss_pct')),
            ('이익실현 %', loaded_state['parameters'].get('take_profit_pct')),
            ('최대 포지션 크기', loaded_state['parameters'].get('max_position_size')),
            ('거래소', loaded_state.get('exchange_id')),
            ('심볼', loaded_state.get('symbol')),
            ('시간프레임', loaded_state.get('timeframe'))
        ]
        
        all_present = True
        for field_name, field_value in required_fields:
            if field_value is not None:
                print(f"  ✅ {field_name}: {field_value}")
            else:
                print(f"  ❌ {field_name}: 없음")
                all_present = False
        
        if all_present:
            print("\n✅ 거래 실행에 필요한 모든 정보가 DB에 저장되어 있습니다!")
        else:
            print("\n❌ 일부 필수 정보가 누락되었습니다!")
    
    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)

if __name__ == "__main__":
    test_complete_strategy_settings()
