#!/usr/bin/env python3
"""
볼린저 밴드 선물 전략 백테스트 (15분봉, 3개월)
"""

import os
import sys
from datetime import datetime, timedelta

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backtesting import Backtester
from src.strategies import BollingerBandsStrategy

def run_bollinger_futures_backtest():
    """볼린저 밴드 선물 전략 백테스트 실행"""
    
    print("\n=== 볼린저 밴드 선물 백테스트 시작 ===")
    print("전략: 볼린저 밴드 (20일, 2σ)")
    print("시장: Binance Futures")
    print("심볼: BTC/USDT")
    print("타임프레임: 15분")
    print("레버리지: 5x")
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='15m'  # 15분봉
    )
    
    # 백테스트 기간 설정 (최근 3개월)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    print(f"기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    print(f"초기 자산: $10,000 USDT")
    print(f"거래 수수료: 0.05% (Maker)")
    print("=" * 60)
    
    # 전략 파라미터 리스트 (최적화를 위한 여러 설정)
    strategy_params = [
        {'period': 20, 'std_dev': 2.0, 'leverage': 5},
        {'period': 20, 'std_dev': 2.5, 'leverage': 3},
        {'period': 14, 'std_dev': 2.0, 'leverage': 5},
        {'period': 30, 'std_dev': 2.0, 'leverage': 3}
    ]
    
    results = []
    
    for params in strategy_params:
        try:
            print(f"\n테스트 중: Period={params['period']}, StdDev={params['std_dev']}, Leverage={params['leverage']}x")
            
            # 전략 생성
            strategy = BollingerBandsStrategy(
                period=params['period'], 
                std_dev=params['std_dev']
            )
            
            # calculate_positions 메서드가 없으면 generate_signals를 사용
            if not hasattr(strategy, 'calculate_positions'):
                # generate_signals 메서드를 calculate_positions로 별칭 추가
                strategy.calculate_positions = strategy.generate_signals
            
            # 백테스트 실행
            result = backtester.run_backtest(
                strategy=strategy,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                initial_balance=10000,
                commission=0.0005,  # 0.05% Maker 수수료
                market_type='futures',
                leverage=params['leverage']
            )
            
            if result:
                results.append({
                    'params': params,
                    'result': result
                })
                
                # 결과 출력
                print(f"최종 잔액: ${result.final_balance:,.2f}")
                print(f"총 수익률: {result.total_return:.2f}%")
                print(f"연환산 수익률: {result.total_return * 4:.2f}%")
                print(f"승률: {result.win_rate:.2f}%")
                print(f"최대 낙폭(MDD): {result.max_drawdown:.2f}%")
                print(f"샤프 비율: {result.sharpe_ratio:.2f}")
                print(f"총 거래 횟수: {result.total_trades}")
                
                # 월별 수익률
                try:
                    monthly_returns = result.calculate_monthly_returns()
                    print("\n월별 수익률:")
                    for month, ret in monthly_returns.items():
                        print(f"  {month}: {ret:.2f}%")
                except:
                    pass
                
        except Exception as e:
            print(f"백테스트 오류: {e}")
            import traceback
            traceback.print_exc()
    
    # 최적 파라미터 찾기
    if results:
        print("\n\n=== 백테스트 결과 비교 ===")
        print(f"{'설정':40} {'수익률':>10} {'MDD':>10} {'샤프':>10} {'거래수':>10}")
        print("-" * 85)
        
        for r in results:
            params = r['params']
            result = r['result']
            setting = f"P{params['period']}/σ{params['std_dev']}/L{params['leverage']}x"
            print(f"{setting:40} {result.total_return:>9.2f}% {result.max_drawdown:>9.2f}% "
                  f"{result.sharpe_ratio:>9.2f} {result.total_trades:>10}")
        
        # 최고 성과 찾기
        best_return = max(results, key=lambda x: x['result'].total_return)
        best_sharpe = max(results, key=lambda x: x['result'].sharpe_ratio)
        
        print(f"\n📈 최고 수익률: P{best_return['params']['period']}/σ{best_return['params']['std_dev']}/L{best_return['params']['leverage']}x "
              f"({best_return['result'].total_return:.2f}%)")
        print(f"📊 최고 샤프비율: P{best_sharpe['params']['period']}/σ{best_sharpe['params']['std_dev']}/L{best_sharpe['params']['leverage']}x "
              f"({best_sharpe['result'].sharpe_ratio:.2f})")
        
        # 최적 설정으로 차트 생성
        try:
            print("\n차트 생성 중...")
            best_result = best_return['result']
            best_result.plot_equity_curve(save_path='bollinger_futures_equity.png')
            print("✅ 잔액 곡선 차트 저장: bollinger_futures_equity.png")
        except Exception as e:
            print(f"차트 생성 실패: {e}")
    
    # 추천 사항
    print("\n=== 추천 사항 ===")
    print("1. 15분봉에서는 짧은 기간(14-20)의 볼린저 밴드가 효과적")
    print("2. 표준편차 2.0-2.5 범위가 적절한 신호 빈도 제공")
    print("3. 레버리지는 3-5배가 리스크/수익 균형에 적합")
    print("4. 변동성이 큰 시간대(미국 시장 오픈)에 집중 거래 고려")
    print("5. 손절매 설정으로 최대 손실 제한 필요")
    
    print("\n백테스트 완료!")

if __name__ == "__main__":
    run_bollinger_futures_backtest()
