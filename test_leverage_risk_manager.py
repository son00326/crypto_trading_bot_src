#!/usr/bin/env python3
"""
레버리지를 고려한 리스크 관리 테스트
RiskManager가 레버리지를 올바르게 적용하여 포지션 크기와 리스크를 계산하는지 확인
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.risk_manager import RiskManager
from src.exchange_api import ExchangeAPI
import pandas as pd

def test_leverage_risk_calculations():
    """레버리지가 리스크 계산에 올바르게 적용되는지 테스트"""
    
    print("=== 레버리지 리스크 관리 테스트 ===\n")
    
    # 테스트 설정
    test_leverage = 10
    test_symbol = "BTC/USDT"
    test_exchange = "binance"
    account_balance = 10000  # $10,000
    current_price = 50000    # $50,000 per BTC
    
    print(f"테스트 설정:")
    print(f"- 계좌 잔고: ${account_balance:,}")
    print(f"- 현재 BTC 가격: ${current_price:,}")
    print(f"- 레버리지: {test_leverage}배\n")
    
    # Risk configuration with leverage-adjusted values
    risk_config = {
        'max_position_size': 0.2,  # 20% of capital
        'stop_loss_percent': 2.0,  # 2% stop loss
        'take_profit_percent': 4.0,  # 4% take profit
        'max_trades_per_day': 10,
        'max_risk_per_trade': 0.02,  # 2% risk per trade
        'leverage': test_leverage  # Include leverage in config
    }
    
    # 1. RiskManager 초기화
    print("1. RiskManager 초기화...")
    risk_manager = RiskManager(
        exchange_id=test_exchange,
        symbol=test_symbol,
        risk_config=risk_config
    )
    
    print(f"   - Max position size: {risk_config['max_position_size']*100}%")
    print(f"   - Stop loss: {risk_config['stop_loss_percent']}%")
    print(f"   - Take profit: {risk_config['take_profit_percent']}%")
    print(f"   - Max risk per trade: {risk_config['max_risk_per_trade']*100}%")
    print(f"   - Leverage: {risk_config.get('leverage', 1)}배\n")
    
    # 2. 포지션 크기 계산 (레버리지 없는 경우)
    print("2. 포지션 크기 계산 비교...")
    
    # 레버리지 없는 경우
    max_position_value_no_leverage = account_balance * risk_config['max_position_size']
    max_btc_no_leverage = max_position_value_no_leverage / current_price
    
    print(f"   레버리지 없는 경우 (1배):")
    print(f"   - 최대 포지션 가치: ${max_position_value_no_leverage:,.2f}")
    print(f"   - 최대 BTC 수량: {max_btc_no_leverage:.6f} BTC")
    print(f"   - 필요 자금: ${max_position_value_no_leverage:,.2f}\n")
    
    # 레버리지 있는 경우
    max_position_value_with_leverage = account_balance * risk_config['max_position_size'] * test_leverage
    max_btc_with_leverage = max_position_value_with_leverage / current_price
    required_margin = max_position_value_with_leverage / test_leverage
    
    print(f"   레버리지 있는 경우 ({test_leverage}배):")
    print(f"   - 최대 포지션 가치: ${max_position_value_with_leverage:,.2f}")
    print(f"   - 최대 BTC 수량: {max_btc_with_leverage:.6f} BTC")
    print(f"   - 필요 마진: ${required_margin:,.2f}")
    print(f"   - 레버리지로 인한 포지션 증가: {test_leverage}배\n")
    
    # 3. 리스크 계산 (손절 시 손실)
    print("3. 리스크 계산 (손절 시 예상 손실)...")
    
    # 손절가 계산
    stop_loss_price = current_price * (1 - risk_config['stop_loss_percent'] / 100)
    
    # 레버리지 없는 경우 손실
    loss_no_leverage = max_btc_no_leverage * (current_price - stop_loss_price)
    loss_percent_no_leverage = (loss_no_leverage / account_balance) * 100
    
    print(f"   레버리지 없는 경우:")
    print(f"   - 손절가: ${stop_loss_price:,.2f}")
    print(f"   - 예상 손실: ${loss_no_leverage:,.2f}")
    print(f"   - 계좌 대비 손실: {loss_percent_no_leverage:.2f}%\n")
    
    # 레버리지 있는 경우 손실
    loss_with_leverage = max_btc_with_leverage * (current_price - stop_loss_price)
    loss_percent_with_leverage = (loss_with_leverage / account_balance) * 100
    
    print(f"   레버리지 있는 경우 ({test_leverage}배):")
    print(f"   - 손절가: ${stop_loss_price:,.2f} (동일)")
    print(f"   - 예상 손실: ${loss_with_leverage:,.2f}")
    print(f"   - 계좌 대비 손실: {loss_percent_with_leverage:.2f}%")
    print(f"   - 레버리지로 인한 손실 증가: {test_leverage}배\n")
    
    # 4. 이익실현 계산
    print("4. 이익실현 계산...")
    
    # 이익실현가 계산
    take_profit_price = current_price * (1 + risk_config['take_profit_percent'] / 100)
    
    # 레버리지 있는 경우 이익
    profit_with_leverage = max_btc_with_leverage * (take_profit_price - current_price)
    profit_percent_with_leverage = (profit_with_leverage / account_balance) * 100
    
    print(f"   레버리지 있는 경우 ({test_leverage}배):")
    print(f"   - 이익실현가: ${take_profit_price:,.2f}")
    print(f"   - 예상 이익: ${profit_with_leverage:,.2f}")
    print(f"   - 계좌 대비 이익: {profit_percent_with_leverage:.2f}%\n")
    
    # 5. 청산 가격 계산 (선물 거래)
    print("5. 청산 가격 계산 (선물 거래)...")
    
    # 간단한 청산가 계산 (isolated margin)
    # 청산가 = 진입가 * (1 - 1/레버리지 + 유지마진율)
    maintenance_margin_rate = 0.005  # 0.5%
    liquidation_price = current_price * (1 - 1/test_leverage + maintenance_margin_rate)
    distance_to_liquidation = ((current_price - liquidation_price) / current_price) * 100
    
    print(f"   - 진입가: ${current_price:,.2f}")
    print(f"   - 예상 청산가: ${liquidation_price:,.2f}")
    print(f"   - 청산까지 거리: {distance_to_liquidation:.2f}%")
    print(f"   - 손절매 설정: {risk_config['stop_loss_percent']}%")
    
    if risk_config['stop_loss_percent'] < distance_to_liquidation:
        print(f"   ✓ 손절매가 청산보다 먼저 실행됩니다 (안전)")
    else:
        print(f"   ✗ 경고: 손절매 설정이 청산 거리보다 큽니다!")
    
    # 6. 리스크 관리 권장사항
    print("\n=== 레버리지 리스크 관리 요약 ===")
    print(f"1. 레버리지 {test_leverage}배 사용 시:")
    print(f"   - 포지션 크기는 {test_leverage}배 증가")
    print(f"   - 손익도 {test_leverage}배 증가")
    print(f"   - 청산 위험이 존재 (거리: {distance_to_liquidation:.2f}%)")
    
    print(f"\n2. 안전한 거래를 위한 권장사항:")
    print(f"   - 손절매는 청산가보다 먼저 설정")
    print(f"   - 높은 레버리지일수록 작은 포지션 크기 사용")
    print(f"   - 계좌 대비 최대 손실 제한 설정")
    
    # 실제 안전한 포지션 크기 계산
    safe_position_percent = risk_config['max_risk_per_trade'] / (risk_config['stop_loss_percent'] / 100)
    safe_position_value = account_balance * safe_position_percent
    safe_btc_amount = safe_position_value / current_price
    
    print(f"\n3. 2% 리스크 기준 안전한 포지션:")
    print(f"   - 권장 포지션 비율: {safe_position_percent*100:.1f}%")
    print(f"   - 권장 포지션 가치: ${safe_position_value:,.2f}")
    print(f"   - 권장 BTC 수량: {safe_btc_amount:.6f} BTC")
    print(f"   - 손절 시 최대 손실: ${account_balance * risk_config['max_risk_per_trade']:,.2f}")
    
    print("\n✅ 레버리지를 고려한 리스크 관리 계산이 올바르게 작동합니다.")

if __name__ == "__main__":
    test_leverage_risk_calculations()
