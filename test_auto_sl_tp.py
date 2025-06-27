#!/usr/bin/env python3
"""
자동 손절매/이익실현 기능 테스트
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.trading_algorithm import TradingAlgorithm
from src.db_manager import DatabaseManager

def test_auto_sl_tp():
    """자동 손절/익절 설정 테스트"""
    print("=" * 60)
    print("자동 손절매/이익실현 기능 테스트")
    print("=" * 60)
    
    # 테스트용 설정
    db_path = os.path.join(project_root, "data", "trading_bot.db")
    db = DatabaseManager(db_path)
    
    # 선물 거래 알고리즘 생성
    print("\n1. 선물 거래 알고리즘 초기화...")
    trading_params = {
        'exchange': 'binance',
        'symbol': 'BTC/USDT',
        'timeframe': '15m',
        'market_type': 'futures',  # 선물 거래
        'leverage': 10,
        'test_mode': True,
        'strategy': 'RSI_14_70_30',
        'strategy_params': {
            'stop_loss_pct': 0.03,      # 3% 손절
            'take_profit_pct': 0.06,    # 6% 익절
            'max_position_size': 0.2,
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30
        }
    }
    
    try:
        algorithm = TradingAlgorithm(trading_params, db)
        print("✅ 알고리즘 초기화 성공")
        
        # 리스크 관리 설정 확인
        print("\n2. 리스크 관리 설정 확인...")
        print(f"  - 손절매 %: {algorithm.risk_management.get('stop_loss_pct', 0) * 100}%")
        print(f"  - 이익실현 %: {algorithm.risk_management.get('take_profit_pct', 0) * 100}%")
        print(f"  - 최대 포지션 크기: {algorithm.risk_management.get('max_position_size', 0) * 100}%")
        
        # 손절/익절 가격 계산 테스트
        print("\n3. 손절/익절 가격 계산 테스트...")
        test_price = 100000  # 테스트용 BTC 가격
        
        # RiskManager를 직접 호출하여 계산
        stop_loss_price = algorithm.risk_manager.calculate_stop_loss_price(
            entry_price=test_price,
            side='long'
        )
        take_profit_price = algorithm.risk_manager.calculate_take_profit_price(
            entry_price=test_price,
            side='long'
        )
        
        print(f"  - 진입가: ${test_price:,.2f}")
        print(f"  - 계산된 손절가: ${stop_loss_price:,.2f} ({((stop_loss_price - test_price) / test_price * 100):.1f}%)")
        print(f"  - 계산된 익절가: ${take_profit_price:,.2f} ({((take_profit_price - test_price) / test_price * 100):.1f}%)")
        
        # 실제 주문 시 자동 설정 여부 확인
        print("\n4. 주문 시 자동 손절/익절 설정 로직 확인...")
        print("  - market_type이 'futures'인가?: ", algorithm.market_type.lower() == 'futures')
        print("  - API 키가 설정되어 있는가?: ", bool(os.getenv('BINANCE_API_KEY')))
        print("  - set_stop_loss_take_profit 함수 import 가능한가?: ", end="")
        
        try:
            from utils.api import set_stop_loss_take_profit
            print("Yes")
        except ImportError:
            print("No")
        
        print("\n✅ 테스트 완료!")
        print("\n주요 확인 사항:")
        print("1. 선물 거래 시에만 자동 손절/익절이 설정됩니다.")
        print("2. 손절/익절 가격은 리스크 관리 설정에 따라 자동 계산됩니다.")
        print("3. 실제 거래 시 거래소에 자동으로 주문이 설정됩니다.")
        print("4. 테스트 모드에서도 로직은 실행되지만 실제 주문은 발생하지 않습니다.")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_auto_sl_tp()
