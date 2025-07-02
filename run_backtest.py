#!/usr/bin/env python3
"""
백테스트 실행 스크립트
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backtesting import Backtester
from src.strategies import (
    MovingAverageCrossover,
    RSIStrategy, 
    BollingerBandsStrategy,
    MACDStrategy
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('backtest_runner')

def run_multiple_backtests():
    """여러 전략으로 백테스트 실행"""
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='1h'
    )
    
    # 백테스트 기간 설정 (최근 6개월)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    # 초기 자산
    initial_balance = 10000  # USDT
    
    # 테스트할 전략들
    strategies = [
        {
            'strategy': MovingAverageCrossover(short_period=10, long_period=30),
            'name': 'MA Crossover (10/30)',
            'market_type': 'spot'
        },
        {
            'strategy': RSIStrategy(period=14, oversold=30, overbought=70),
            'name': 'RSI Strategy',
            'market_type': 'spot'
        },
        {
            'strategy': BollingerBandsStrategy(period=20, std_dev=2),
            'name': 'Bollinger Bands',
            'market_type': 'spot'
        },
        {
            'strategy': MACDStrategy(fast_period=12, slow_period=26, signal_period=9),
            'name': 'MACD Strategy',
            'market_type': 'spot'
        }
    ]
    
    # Futures 전략 추가
    strategies.extend([
        {
            'strategy': MovingAverageCrossover(short_period=5, long_period=20),
            'name': 'MA Crossover Futures (5/20)',
            'market_type': 'futures',
            'leverage': 3
        },
        {
            'strategy': BollingerBandsStrategy(period=20, std_dev=2),
            'name': 'Bollinger Bands Futures',
            'market_type': 'futures',
            'leverage': 5
        }
    ])
    
    results = []
    
    print("\n=== 백테스트 시작 ===")
    print(f"심볼: BTC/USDT")
    print(f"기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    print(f"초기 자산: ${initial_balance:,.2f}")
    print(f"거래 수수료: 0.1%")
    print("=" * 50)
    
    for strategy_info in strategies:
        try:
            print(f"\n전략 테스트 중: {strategy_info['name']}")
            print(f"시장 타입: {strategy_info['market_type']}")
            if strategy_info['market_type'] == 'futures':
                print(f"레버리지: {strategy_info.get('leverage', 1)}x")
            
            # 백테스트 실행
            result = backtester.run_backtest(
                strategy=strategy_info['strategy'],
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                initial_balance=initial_balance,
                commission=0.001,  # 0.1% 수수료
                market_type=strategy_info['market_type'],
                leverage=strategy_info.get('leverage', 1)
            )
            
            results.append({
                'name': strategy_info['name'],
                'market_type': strategy_info['market_type'],
                'leverage': strategy_info.get('leverage', 1),
                'result': result
            })
            
            # 주요 지표 출력
            print(f"최종 잔액: ${result.final_balance:,.2f}")
            print(f"총 수익률: {result.total_return:.2f}%")
            print(f"승률: {result.win_rate:.2f}%")
            print(f"최대 낙폭(MDD): {result.max_drawdown:.2f}%")
            print(f"샤프 비율: {result.sharpe_ratio:.2f}")
            print(f"거래 횟수: {result.total_trades}")
            
        except Exception as e:
            logger.error(f"전략 {strategy_info['name']} 백테스트 실패: {e}")
            continue
    
    # 결과 비교
    print("\n\n=== 백테스트 결과 요약 ===")
    print(f"{'전략명':30} {'시장':8} {'레버리지':8} {'최종잔액':15} {'수익률':10} {'승률':8} {'MDD':8} {'샤프':8}")
    print("=" * 110)
    
    for res in results:
        result = res['result']
        print(f"{res['name']:30} {res['market_type']:8} {res['leverage']:>8}x "
              f"${result.final_balance:>14,.2f} {result.total_return:>9.2f}% "
              f"{result.win_rate:>7.2f}% {result.max_drawdown:>7.2f}% {result.sharpe_ratio:>7.2f}")
    
    # 최고 성능 전략 찾기
    best_return = max(results, key=lambda x: x['result'].total_return)
    best_sharpe = max(results, key=lambda x: x['result'].sharpe_ratio)
    
    print(f"\n📈 최고 수익률: {best_return['name']} ({best_return['result'].total_return:.2f}%)")
    print(f"📊 최고 샤프비율: {best_sharpe['name']} ({best_sharpe['result'].sharpe_ratio:.2f})")
    
    # 차트 생성 (상위 3개 전략)
    print("\n차트 생성 중...")
    top_strategies = sorted(results, key=lambda x: x['result'].total_return, reverse=True)[:3]
    
    for i, res in enumerate(top_strategies):
        try:
            # 잔액 곡선 차트
            res['result'].plot_equity_curve(save_path=f'backtest_equity_{i+1}.png')
            print(f"✅ {res['name']} 잔액 곡선 저장: backtest_equity_{i+1}.png")
            
            # 수익률 분포 차트
            res['result'].plot_returns_distribution(save_path=f'backtest_returns_{i+1}.png')
            print(f"✅ {res['name']} 수익률 분포 저장: backtest_returns_{i+1}.png")
            
        except Exception as e:
            logger.error(f"차트 생성 실패: {e}")
    
    # 상세 보고서 저장
    try:
        report_path = f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backtester.save_results(results, report_path)
        print(f"\n📄 상세 보고서 저장: {report_path}")
    except Exception as e:
        logger.error(f"보고서 저장 실패: {e}")
    
    print("\n백테스트 완료!")
    return results

if __name__ == "__main__":
    try:
        results = run_multiple_backtests()
    except KeyboardInterrupt:
        print("\n백테스트 중단됨")
    except Exception as e:
        logger.error(f"백테스트 실행 중 오류: {e}", exc_info=True)
