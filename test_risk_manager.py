#!/usr/bin/env python3
"""
위험 관리자 테스트 스크립트
"""
from src.risk_manager import RiskManager
import time

def test_risk_manager():
    """위험 관리자 테스트"""
    print("위험 관리자 테스트 시작...")
    
    try:
        # 위험 관리자 초기화
        risk_manager = RiskManager(exchange_id='binance', symbol='BTC/USDT')
        print(f"위험 관리자 초기화 완료")
        
        # 위험 관리 설정 확인
        default_settings = risk_manager.get_risk_settings() if hasattr(risk_manager, 'get_risk_settings') else None
        print(f"기본 위험 관리 설정: {default_settings}")
        
        # 손절매 계산 테스트
        entry_price = 50000  # 진입 가격
        position_size = 0.1  # 포지션 크기
        position_type = 'long'  # 롱 포지션
        
        try:
            sl_price = risk_manager.calculate_stop_loss(
                entry_price=entry_price,
                position_size=position_size, 
                position_type=position_type
            )
            print(f"계산된 손절매 가격: {sl_price}")
        except Exception as e:
            print(f"손절매 계산 중 오류: {str(e)}")
        
        # 이익실현 계산 테스트
        try:
            tp_price = risk_manager.calculate_take_profit(
                entry_price=entry_price,
                position_size=position_size, 
                position_type=position_type
            )
            print(f"계산된 이익실현 가격: {tp_price}")
        except Exception as e:
            print(f"이익실현 계산 중 오류: {str(e)}")
        
        # 포지션 크기 계산 테스트
        account_balance = 10000  # 계정 잔고
        risk_per_trade = 0.02  # 거래당 위험 비율 (2%)
        
        try:
            position_size = risk_manager.calculate_position_size(
                account_balance=account_balance,
                risk_per_trade=risk_per_trade,
                entry_price=entry_price,
                stop_loss_price=entry_price * 0.95  # 5% 손실 예상
            )
            print(f"계산된 포지션 크기: {position_size}")
        except Exception as e:
            print(f"포지션 크기 계산 중 오류: {str(e)}")
        
        # 위험도 계산 테스트
        try:
            if hasattr(risk_manager, 'calculate_risk_level'):
                risk_level = risk_manager.calculate_risk_level(
                    open_positions=[{'size': 0.1, 'unrealized_pnl': -50}],
                    account_balance=account_balance
                )
                print(f"계산된 위험도: {risk_level}")
        except Exception as e:
            print(f"위험도 계산 중 오류: {str(e)}")
        
    except Exception as e:
        print(f"위험 관리자 테스트 중 오류: {str(e)}")
    
    print("위험 관리자 테스트 완료")

if __name__ == "__main__":
    test_risk_manager()
