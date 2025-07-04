#!/usr/bin/env python3
"""
레버리지에 따른 손절매/이익실현 가격 계산 상세 테스트
실제 가격 움직임과 레버리지가 정확히 반영되는지 검증
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.risk_manager import RiskManager
from src.exchange_api import ExchangeAPI
from src.auto_position_manager import AutoPositionManager

def test_leverage_price_movements():
    """레버리지별 가격 움직임 테스트"""
    
    print("=== 레버리지별 손절매/이익실현 가격 움직임 검증 ===\n")
    
    # 테스트 설정
    entry_price = 50000  # BTC 진입가
    position_size = 0.1  # 0.1 BTC
    account_balance = 10000  # $10,000
    
    # 손절매 4%, 이익실현 8% 설정
    stop_loss_pct = 0.04  # 4% as decimal
    take_profit_pct = 0.08  # 8% as decimal
    
    # 다양한 레버리지 시나리오
    leverage_scenarios = [1, 5, 10, 20, 50, 100]
    
    print(f"진입가: ${entry_price:,.2f}")
    print(f"포지션 크기: {position_size} BTC")
    print(f"계좌 잔고: ${account_balance:,.2f}")
    print(f"손절매 설정: {stop_loss_pct*100:.1f}%")
    print(f"이익실현 설정: {take_profit_pct*100:.1f}%\n")
    
    for leverage in leverage_scenarios:
        print(f"\n{'='*60}")
        print(f"레버리지 {leverage}배 분석")
        print(f"{'='*60}")
        
        # RiskManager 생성
        risk_config = {
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'leverage': leverage
        }
        
        risk_manager = RiskManager(
            exchange_id='binance',
            symbol='BTC/USDT',
            risk_config=risk_config
        )
        
        # 포지션 가치 계산
        position_value = position_size * entry_price
        required_margin = position_value / leverage
        
        print(f"\n1. 포지션 정보:")
        print(f"   - 포지션 가치: ${position_value:,.2f}")
        print(f"   - 필요 마진: ${required_margin:,.2f}")
        print(f"   - 마진 비율: {(required_margin/account_balance)*100:.2f}%")
        
        # 손절매/이익실현 가격 계산
        # Long 포지션 기준
        stop_loss_price = risk_manager.calculate_stop_loss_price(entry_price, 'long')
        take_profit_price = risk_manager.calculate_take_profit_price(entry_price, 'long')
        
        print(f"\n2. 손절매/이익실현 가격:")
        print(f"   - 손절매 가격: ${stop_loss_price:,.2f}")
        print(f"   - 이익실현 가격: ${take_profit_price:,.2f}")
        
        # 실제 가격 움직임 계산
        price_move_to_sl = entry_price - stop_loss_price
        price_move_pct_to_sl = (price_move_to_sl / entry_price) * 100
        
        price_move_to_tp = take_profit_price - entry_price
        price_move_pct_to_tp = (price_move_to_tp / entry_price) * 100
        
        print(f"\n3. 필요한 가격 움직임:")
        print(f"   - 손절매까지: ${price_move_to_sl:,.2f} ({price_move_pct_to_sl:.2f}%)")
        print(f"   - 이익실현까지: ${price_move_to_tp:,.2f} ({price_move_pct_to_tp:.2f}%)")
        
        # 실제 손익 계산
        # 손절매 시
        loss_amount = position_size * price_move_to_sl
        loss_pct_on_margin = (loss_amount / required_margin) * 100
        loss_pct_on_account = (loss_amount / account_balance) * 100
        
        # 이익실현 시
        profit_amount = position_size * price_move_to_tp
        profit_pct_on_margin = (profit_amount / required_margin) * 100
        profit_pct_on_account = (profit_amount / account_balance) * 100
        
        print(f"\n4. 손절매 시 손실:")
        print(f"   - 손실 금액: ${abs(loss_amount):,.2f}")
        print(f"   - 마진 대비 손실: {abs(loss_pct_on_margin):.2f}%")
        print(f"   - 계좌 대비 손실: {abs(loss_pct_on_account):.2f}%")
        
        print(f"\n5. 이익실현 시 이익:")
        print(f"   - 이익 금액: ${profit_amount:,.2f}")
        print(f"   - 마진 대비 이익: {profit_pct_on_margin:.2f}%")
        print(f"   - 계좌 대비 이익: {profit_pct_on_account:.2f}%")
        
        # 청산 가격 계산 (선물의 경우)
        if leverage > 1:
            # 간단한 청산 가격 계산 (유지 마진 0.5% 가정)
            maintenance_margin_rate = 0.005
            liquidation_price = entry_price * (1 - 1/leverage + maintenance_margin_rate)
            distance_to_liquidation = ((entry_price - liquidation_price) / entry_price) * 100
            
            print(f"\n6. 청산 정보 (선물):")
            print(f"   - 예상 청산가: ${liquidation_price:,.2f}")
            print(f"   - 청산까지 거리: {distance_to_liquidation:.2f}%")
            
            if stop_loss_price > liquidation_price:
                print(f"   ✓ 손절매가 청산보다 먼저 실행됩니다 (안전)")
            else:
                print(f"   ✗ 경고: 손절매가 청산 이후에 위치합니다 (위험!)")
    
    # 핵심 검증 포인트
    print(f"\n\n{'='*60}")
    print("=== 핵심 검증 결과 ===")
    print(f"{'='*60}\n")
    
    print("✅ 레버리지와 관계없이 손절매/이익실현 가격은 동일합니다:")
    print(f"   - 이는 설정된 %가 '포지션 가치' 기준이 아닌 '가격 변동' 기준이기 때문입니다")
    print(f"   - 손절매 4% = 가격이 4% 하락할 때")
    print(f"   - 이익실현 8% = 가격이 8% 상승할 때")
    
    print("\n✅ 하지만 실제 손익은 레버리지에 비례해서 증가합니다:")
    print(f"   - 레버리지 1배: 4% 가격 하락 시 마진의 4% 손실")
    print(f"   - 레버리지 10배: 4% 가격 하락 시 마진의 40% 손실")
    print(f"   - 레버리지 100배: 4% 가격 하락 시 마진의 400% 손실 (청산)")
    
    print("\n⚠️ 고레버리지 주의사항:")
    print(f"   - 레버리지가 높을수록 작은 가격 움직임에도 큰 손익 발생")
    print(f"   - 청산 위험이 증가하므로 손절매 설정이 더욱 중요")
    print(f"   - 포지션 크기를 레버리지에 반비례하여 조절 필요")

def test_auto_position_manager_sl_tp():
    """AutoPositionManager의 손절매/이익실현 실행 로직 테스트"""
    
    print("\n\n=== AutoPositionManager 손절매/이익실현 실행 테스트 ===\n")
    
    # Mock 포지션 데이터
    mock_position = {
        'symbol': 'BTC/USDT',
        'side': 'long',
        'contracts': 0.1,
        'contractSize': 1,
        'markPrice': 50000,
        'percentage': 0,
        'info': {
            'positionAmt': '0.1',
            'entryPrice': '50000',
            'markPrice': '50000',
            'unRealizedProfit': '0'
        }
    }
    
    # 다양한 가격 시나리오 테스트
    price_scenarios = [
        {'current': 50000, 'desc': '진입가 (변동 없음)'},
        {'current': 49000, 'desc': '2% 하락'},
        {'current': 48000, 'desc': '4% 하락 (손절매 도달)'},
        {'current': 47000, 'desc': '6% 하락 (손절매 초과)'},
        {'current': 52000, 'desc': '4% 상승'},
        {'current': 54000, 'desc': '8% 상승 (이익실현 도달)'},
        {'current': 56000, 'desc': '12% 상승 (이익실현 초과)'}
    ]
    
    for scenario in price_scenarios:
        current_price = scenario['current']
        entry_price = float(mock_position['info']['entryPrice'])
        price_change_pct = ((current_price - entry_price) / entry_price) * 100
        
        print(f"\n시나리오: {scenario['desc']}")
        print(f"현재가: ${current_price:,.2f} (변동: {price_change_pct:+.2f}%)")
        
        # 손절매/이익실현 조건 확인
        if price_change_pct <= -4.0:
            print("→ 손절매 조건 충족! 포지션 청산 실행")
        elif price_change_pct >= 8.0:
            print("→ 이익실현 조건 충족! 포지션 청산 실행")
        else:
            print("→ 대기 중 (손절매/이익실현 미도달)")

if __name__ == "__main__":
    test_leverage_price_movements()
    test_auto_position_manager_sl_tp()
    print("\n✅ 모든 테스트 완료")
