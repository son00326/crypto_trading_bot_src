#!/usr/bin/env python3
"""
선물거래 전체 플로우 테스트
- 데이터 수신
- 지표 계산 (RSI, MACD, 볼린저밴드 등)
- 전략 실행
- 신호 생성
- 주문 실행 시뮬레이션
"""

import os
import sys
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trading_algorithm import TradingAlgorithm

# 전략별 파라미터 정의
STRATEGY_PARAMS = {
    'golden_death_cross': {
        'short_period': 50,
        'long_period': 200,
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70
    },
    'rsi_oversold_overbought': {
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'volume_threshold': 1.5
    },
    'macd_signal_cross': {
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_period': 14
    },
    'bollinger_squeeze': {
        'bollinger_period': 20,
        'bollinger_std': 2,
        'rsi_period': 14,
        'volume_threshold': 1.5
    },
    'multi_indicator_ensemble': {
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'bollinger_period': 20,
        'bollinger_std': 2,
        'volume_threshold': 2.0,
        'confidence_threshold': 0.6
    }
}

def test_full_trading_flow():
    """선물거래 전체 플로우 테스트"""
    print("=" * 70)
    print("바이낸스 선물거래 봇 전체 플로우 테스트")
    print(f"테스트 시간: {datetime.now()}")
    print("=" * 70)
    
    # 테스트할 전략들
    strategies_to_test = [
        'golden_death_cross',
        'rsi_oversold_overbought',
        'macd_signal_cross',
        'bollinger_squeeze',
        'multi_indicator_ensemble'
    ]
    
    for strategy_name in strategies_to_test:
        print(f"\n\n{'='*70}")
        print(f"전략 테스트: {strategy_name}")
        print("="*70)
        
        try:
            # 1. TradingAlgorithm 초기화
            print(f"\n[1] {strategy_name} 전략으로 봇 초기화")
            algo = TradingAlgorithm(
                exchange_id='binance',
                symbol='BTC/USDT',
                timeframe='5m',
                strategy=strategy_name,
                test_mode=True,  # 테스트 모드
                market_type='futures',
                leverage=5
            )
            print(f"✅ 초기화 성공 (레버리지: {algo.leverage}x)")
            
            # 2. 시장 데이터 수신
            print(f"\n[2] OHLCV 데이터 수신")
            ohlcv_df = algo.exchange_api.get_ohlcv(limit=200)
            
            if ohlcv_df is not None and not ohlcv_df.empty:
                print(f"✅ OHLCV 데이터 수신 완료: {len(ohlcv_df)}개 캔들")
                
                # DataFrame 구조 확인
                print(f"\n   DataFrame 컬럼: {list(ohlcv_df.columns)}")
                print(f"   DataFrame 인덱스 이름: {ohlcv_df.index.name}")
                
                # 최신 캔들 정보
                latest = ohlcv_df.iloc[-1]
                
                # timestamp가 인덱스인 경우
                if ohlcv_df.index.name in ['timestamp', 'datetime', 'date']:
                    latest_time = ohlcv_df.index[-1]
                elif 'timestamp' in ohlcv_df.columns:
                    latest_time = latest['timestamp']
                elif 'datetime' in ohlcv_df.columns:
                    latest_time = latest['datetime']
                else:
                    latest_time = "N/A"
                    
                print(f"   최신 캔들: 시간={latest_time}, O={latest['open']:.2f}, H={latest['high']:.2f}, L={latest['low']:.2f}, C={latest['close']:.2f}")
                
                # 3. 전략 파라미터 확인
                print(f"\n[3] 전략 파라미터 확인")
                strategy_params = STRATEGY_PARAMS[strategy_name]
                print(f"✅ 전략 파라미터:")
                for key, value in strategy_params.items():
                    print(f"   - {key}: {value}")
                
                # 4. 기술적 지표 계산
                print(f"\n[4] 기술적 지표 계산")
                
                # 지표 계산
                from src.indicators import (
                    simple_moving_average, exponential_moving_average,
                    relative_strength_index, moving_average_convergence_divergence,
                    bollinger_bands
                )
                
                # RSI 계산
                if 'rsi_period' in strategy_params:
                    rsi = relative_strength_index(ohlcv_df, period=strategy_params['rsi_period'])
                    print(f"✅ RSI({strategy_params['rsi_period']}): {rsi.iloc[-1]:.2f}")
                
                # MACD 계산
                if 'macd_fast' in strategy_params:
                    macd, signal, histogram = moving_average_convergence_divergence(
                        ohlcv_df, 
                        fast_period=strategy_params['macd_fast'],
                        slow_period=strategy_params['macd_slow'],
                        signal_period=strategy_params['macd_signal']
                    )
                    print(f"✅ MACD: {macd.iloc[-1]:.2f}, Signal: {signal.iloc[-1]:.2f}")
                
                # 볼린저 밴드 계산
                if 'bollinger_period' in strategy_params:
                    middle, upper, lower = bollinger_bands(
                        ohlcv_df,
                        period=strategy_params['bollinger_period'],
                        std_dev=strategy_params['bollinger_std']
                    )
                    print(f"✅ 볼린저 밴드: 상단={upper.iloc[-1]:.2f}, 중간={middle.iloc[-1]:.2f}, 하단={lower.iloc[-1]:.2f}")
                
                # 이동평균 계산
                if 'short_period' in strategy_params:
                    sma_short = simple_moving_average(ohlcv_df, period=strategy_params['short_period'])
                    sma_long = simple_moving_average(ohlcv_df, period=strategy_params['long_period'])
                    print(f"✅ SMA({strategy_params['short_period']}): {sma_short.iloc[-1]:.2f}")
                    print(f"✅ SMA({strategy_params['long_period']}): {sma_long.iloc[-1]:.2f}")
                
                # 5. 전략 실행 및 신호 생성
                print(f"\n[5] 전략 실행 및 신호 생성")
                
                # 간단한 신호 생성 로직
                signal = 'neutral'
                
                # RSI 기반 신호
                if 'rsi_period' in strategy_params and not rsi.empty:
                    current_rsi = rsi.iloc[-1]
                    if current_rsi < strategy_params.get('rsi_oversold', 30):
                        signal = 'buy'
                        print(f"📈 매수 신호: RSI({current_rsi:.2f}) < {strategy_params.get('rsi_oversold', 30)}")
                    elif current_rsi > strategy_params.get('rsi_overbought', 70):
                        signal = 'sell'
                        print(f"📉 매도 신호: RSI({current_rsi:.2f}) > {strategy_params.get('rsi_overbought', 70)}")
                
                # 이동평균 골든크로스/데드크로스
                if 'short_period' in strategy_params and not sma_short.empty:
                    if sma_short.iloc[-1] > sma_long.iloc[-1] and sma_short.iloc[-2] <= sma_long.iloc[-2]:
                        signal = 'buy'
                        print(f"📈 매수 신호: 골든크로스 발생")
                    elif sma_short.iloc[-1] < sma_long.iloc[-1] and sma_short.iloc[-2] >= sma_long.iloc[-2]:
                        signal = 'sell'
                        print(f"📉 매도 신호: 데드크로스 발생")
                
                if signal == 'neutral':
                    print("⚖️ 중립 신호: 매매 조건 미충족")
                
                # 6. 주문 시뮬레이션
                print(f"\n[6] 주문 시뮬레이션")
                current_price = algo.get_current_price()
                balance = algo.exchange_api.get_balance()
                usdt_balance = balance.get('USDT', {}).get('free', 0)
                
                print(f"   현재가: ${current_price:,.2f}")
                print(f"   USDT 잔액: ${usdt_balance:,.2f}")
                
                # 포지션 크기 계산 (잔액의 10% 사용)
                position_size_usdt = usdt_balance * 0.1
                position_size_btc = position_size_usdt / current_price
                
                print(f"   예상 주문:")
                print(f"   - 방향: {signal}")
                print(f"   - 크기: {position_size_btc:.6f} BTC (${position_size_usdt:.2f})")
                print(f"   - 레버리지: {algo.leverage}x")
                print(f"   - 실제 노출: ${position_size_usdt * algo.leverage:,.2f}")
                
                # 손절매/이익실현 가격 계산
                if signal == 'buy':
                    sl_price = current_price * 0.98  # 2% 손절
                    tp_price = current_price * 1.03  # 3% 이익실현
                else:
                    sl_price = current_price * 1.02  # 2% 손절
                    tp_price = current_price * 0.97  # 3% 이익실현
                
                print(f"   - 손절가: ${sl_price:,.2f}")
                print(f"   - 이익실현가: ${tp_price:,.2f}")
                
                # 7. 포지션 관리 기능 확인
                print(f"\n[7] 포지션 관리 기능 확인")
                if hasattr(algo, 'auto_position_manager') and algo.auto_position_manager:
                    print("✅ AutoPositionManager 활성화됨")
                    print(f"   - 손절매: {algo.auto_position_manager.stop_loss_percent}%")
                    print(f"   - 이익실현: {algo.auto_position_manager.take_profit_percent}%")
                else:
                    print("❌ AutoPositionManager 비활성화됨")
                
                print(f"\n✅ {strategy_name} 전략 테스트 완료")
                
            else:
                print("❌ OHLCV 데이터 수신 실패")
                continue
            
        except Exception as e:
            print(f"\n❌ {strategy_name} 전략 테스트 실패: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n\n" + "="*70)
    print("전체 테스트 완료")
    print("="*70)
    print("\n다음 단계:")
    print("1. 실제 API 키로 테스트")
    print("2. 소액으로 실거래 테스트")
    print("3. EC2 배포 준비")

if __name__ == "__main__":
    test_full_trading_flow()
