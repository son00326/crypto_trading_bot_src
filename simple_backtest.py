#!/usr/bin/env python3
"""
간단한 백테스트 실행 스크립트
"""

import os
import sys
from datetime import datetime, timedelta

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backtesting import Backtester
from src.strategies import MovingAverageCrossover

def run_simple_backtest():
    """이동평균 전략으로 간단한 백테스트 실행"""
    
    print("\n=== 백테스트 시작 ===")
    print("전략: 이동평균 교차 (MA 10/30)")
    print("심볼: BTC/USDT")
    print("타임프레임: 1시간")
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='1h'
    )
    
    # 백테스트 기간 설정 (최근 3개월)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    print(f"기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    print(f"초기 자산: $10,000")
    print("=" * 50)
    
    # 전략 생성
    strategy = MovingAverageCrossover(short_period=10, long_period=30)
    
    try:
        # 백테스트 실행
        result = backtester.run_backtest(
            strategy=strategy,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            initial_balance=10000,
            commission=0.001  # 0.1% 수수료
        )
        
        # 결과 출력
        print("\n=== 백테스트 결과 ===")
        print(f"최종 잔액: ${result.final_balance:,.2f}")
        print(f"총 수익률: {result.total_return:.2f}%")
        print(f"승률: {result.win_rate:.2f}%")
        print(f"최대 낙폭(MDD): {result.max_drawdown:.2f}%")
        print(f"샤프 비율: {result.sharpe_ratio:.2f}")
        print(f"총 거래 횟수: {result.total_trades}")
        print(f"승리 거래: {result.win_trades}")
        print(f"패배 거래: {result.loss_trades}")
        
        if result.total_trades > 0:
            print(f"\n평균 수익: {result.average_profit:.2f}%")
            print(f"평균 손실: {result.average_loss:.2f}%")
            print(f"손익비: {result.profit_loss_ratio:.2f}")
        
        # 월별 수익률
        print("\n=== 월별 수익률 ===")
        monthly_returns = result.calculate_monthly_returns()
        for month, ret in monthly_returns.items():
            print(f"{month}: {ret:.2f}%")
        
        # 차트 생성
        print("\n차트 생성 중...")
        try:
            # 잔액 곡선
            result.plot_equity_curve(save_path='backtest_equity_curve.png')
            print("✅ 잔액 곡선 차트 저장: backtest_equity_curve.png")
        except Exception as e:
            print(f"차트 생성 실패: {e}")
        
        # Futures 백테스트 추가
        print("\n\n=== Futures 백테스트 ===")
        print("전략: 이동평균 교차 (MA 5/20)")
        print("레버리지: 3x")
        
        futures_strategy = MovingAverageCrossover(short_period=5, long_period=20)
        
        futures_result = backtester.run_backtest(
            strategy=futures_strategy,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            initial_balance=10000,
            commission=0.001,
            market_type='futures',
            leverage=3
        )
        
        print(f"\n최종 잔액: ${futures_result.final_balance:,.2f}")
        print(f"총 수익률: {futures_result.total_return:.2f}%")
        print(f"승률: {futures_result.win_rate:.2f}%")
        print(f"최대 낙폭(MDD): {futures_result.max_drawdown:.2f}%")
        print(f"샤프 비율: {futures_result.sharpe_ratio:.2f}")
        print(f"총 거래 횟수: {futures_result.total_trades}")
        
        # 현물 vs 선물 비교
        print("\n=== 현물 vs 선물 비교 ===")
        print(f"{'구분':10} {'수익률':>10} {'MDD':>10} {'샤프':>10} {'거래수':>10}")
        print("-" * 55)
        print(f"{'현물':10} {result.total_return:>9.2f}% {result.max_drawdown:>9.2f}% {result.sharpe_ratio:>9.2f} {result.total_trades:>10}")
        print(f"{'선물(3x)':10} {futures_result.total_return:>9.2f}% {futures_result.max_drawdown:>9.2f}% {futures_result.sharpe_ratio:>9.2f} {futures_result.total_trades:>10}")
        
    except Exception as e:
        print(f"\n백테스트 오류: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n백테스트 완료!")

if __name__ == "__main__":
    run_simple_backtest()
