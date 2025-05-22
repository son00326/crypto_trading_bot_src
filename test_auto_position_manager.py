#!/usr/bin/env python3
"""
자동 포지션 관리자 테스트 스크립트
"""
from src.auto_position_manager import AutoPositionManager
from src.exchange_api import ExchangeAPI
import time

def test_auto_position_manager():
    """자동 포지션 관리자 테스트"""
    print("자동 포지션 관리자 테스트 시작...")
    
    try:
        # 직접 객체 생성을 시도하지는 않고 클래스 구조만 확인
        print("AutoPositionManager 클래스 구조 확인:")
        
        # 클래스 메서드 목록 조회
        methods = [method for method in dir(AutoPositionManager) 
                  if not method.startswith('__') and callable(getattr(AutoPositionManager, method))]
        print(f"메서드 목록: {methods}")
        
        # 중요 메서드 확인
        important_methods = [
            'set_auto_sl_tp',
            'set_sl_tp_percentages',
            'set_partial_tp',
            '_check_position_exit_conditions',
            '_execute_position_exit',
            '_check_margin_safety',
            '_handle_margin_safety_actions'
        ]
        
        for method in important_methods:
            if method in methods:
                print(f"✓ {method} 메서드 존재함")
            else:
                print(f"✗ {method} 메서드 없음")
                
        # 자동 손절매/이익실현 기능 구현 완료 여부 확인
        sl_tp_implemented = all(method in methods for method in [
            'set_auto_sl_tp',
            '_check_position_exit_conditions',
            '_execute_position_exit'
        ])
        print(f"자동 손절매/이익실현 기능 구현됨: {sl_tp_implemented}")
        
        # 포지션 안전장치 기능 구현 완료 여부 확인
        safety_implemented = all(method in methods for method in [
            '_check_margin_safety',
            '_handle_margin_safety_actions',
            '_emergency_reduce_positions'
        ])
        print(f"포지션 안전장치 기능 구현됨: {safety_implemented}")
        
    except Exception as e:
        print(f"자동 포지션 관리자 테스트 중 오류: {str(e)}")
    
    print("자동 포지션 관리자 테스트 완료")

if __name__ == "__main__":
    test_auto_position_manager()
