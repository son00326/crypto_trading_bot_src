#!/usr/bin/env python
"""
백테스트 실행기 - 암호화폐 트레이딩 전략 백테스트

이 스크립트는 다양한 트레이딩 전략에 대한 백테스트를 실행하고 결과를 분석합니다.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from datetime import datetime, timedelta
import logging
import argparse
import os

from src.backtesting import Backtester, BacktestResult
from src.strategies import (
    MovingAverageCrossover,
    RSIStrategy,
    MACDStrategy,
    BollingerBandsStrategy,
    StochasticStrategy,
    BollingerBandFuturesStrategy
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('backtest_runner')

def run_single_backtest(strategy, exchange, symbol, timeframe, start_date, end_date, 
                       initial_balance=10000, commission=0.001, market_type='spot', 
                       leverage=1, save_results=True):
    """
    단일 전략에 대한 백테스트 실행
    
    Args:
        strategy: 백테스트할 전략 객체
        exchange (str): 거래소 이름 (예: 'binance')
        symbol (str): 트레이딩 심볼 (예: 'BTC/USDT')
        timeframe (str): 타임프레임 (예: '1h', '4h', '1d')
        start_date (str): 시작 날짜 (YYYY-MM-DD 형식)
        end_date (str): 종료 날짜 (YYYY-MM-DD 형식)
        initial_balance (float): 초기 잔고
        commission (float): 수수료 비율 (0.001 = 0.1%)
        market_type (str): 시장 유형 ('spot' 또는 'futures')
        leverage (int): 레버리지 (선물 거래용)
        save_results (bool): 결과 저장 여부
        
    Returns:
        BacktestResult: 백테스트 결과 객체
    """
    logger.info(f"'{strategy.name}' 전략에 대한 백테스트 시작: {exchange}/{symbol}/{timeframe}")
    logger.info(f"기간: {start_date} ~ {end_date}, 초기 잔고: ${initial_balance}, 수수료: {commission*100}%, 시장: {market_type}, 레버리지: {leverage}x")
    
    # Backtester 객체 생성
    backtester = Backtester(
        exchange_id=exchange,
        symbol=symbol,
        timeframe=timeframe,
        market_type=market_type,
        leverage=leverage
    )
    
    # 백테스트 실행
    result = backtester.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        initial_balance=initial_balance,
        commission=commission
    )
    
    # 결과 출력
    logger.info(f"백테스트 완료: {strategy.name}")
    logger.info(f"총 수익: {result.total_return:.2f}%")
    logger.info(f"연간 수익률: {result.annual_return:.2f}%")
    logger.info(f"최대 낙폭: {result.max_drawdown:.2f}%")
    logger.info(f"승률: {result.win_rate:.2f}%")
    logger.info(f"샤프 비율: {result.sharpe_ratio:.2f}")
    logger.info(f"총 거래 횟수: {result.total_trades}")
    
    # 결과 저장
    if save_results:
        output_dir = f"backtest_results/{exchange}_{symbol.replace('/', '')}_{timeframe}_{market_type}"
        os.makedirs(output_dir, exist_ok=True)
        
        # 결과를 CSV로 저장
        trades_file = os.path.join(output_dir, f"{strategy.name}_trades.csv")
        portfolio_file = f"{output_dir}/{strategy.name}_portfolio.csv"
        stats_file = f"{output_dir}/{strategy.name}_stats.json"
        
        if result.trades:
            trades_df = pd.DataFrame(result.trades)
            trades_df.to_csv(trades_file)
        else:
            pd.DataFrame().to_csv(trades_file)  # 빈 CSV 파일 생성
        
        if result.portfolio_history:
            portfolio_df = pd.DataFrame(result.portfolio_history)
            portfolio_df.to_csv(portfolio_file)
        else:
            pd.DataFrame().to_csv(portfolio_file)  # 빈 CSV 파일 생성
        # metrics 데이터를 JSON으로 저장
        with open(stats_file, 'w') as f:
            json.dump(result.metrics, f, indent=4)
        
        # 그래프 생성 및 저장
        try:
            fig_equity = result.plot_equity_curve()
            if fig_equity is not None:
                fig_equity.savefig(f"{output_dir}/{strategy.name}_equity.png")
        except Exception as e:
            logger.error(f"자산 곡선 저장 중 오류 발생: {e}")
        
        try:
            fig_drawdown = result.plot_drawdown_chart()
            if fig_drawdown is not None:
                fig_drawdown.savefig(f"{output_dir}/{strategy.name}_drawdown.png")
        except Exception as e:
            logger.error(f"낙폭 차트 저장 중 오류 발생: {e}")
            
        try:
            fig_monthly = result.plot_monthly_returns()
            if fig_monthly is not None:
                fig_monthly.savefig(f"{output_dir}/{strategy.name}_monthly_returns.png")
        except Exception as e:
            logger.error(f"월간 수익률 차트 저장 중 오류 발생: {e}")
        
        plt.close('all')  # 모든 그림 닫기
        logger.info(f"결과가 {output_dir} 디렉토리에 저장되었습니다.")
    
    return result

def compare_strategies(strategies, exchange, symbol, timeframe, start_date, end_date, 
                       initial_balance=10000, commission=0.001, market_type='spot', 
                       leverage=1, save_results=True):
    """
    여러 전략을 실행하고 비교
    
    Args:
        strategies (list): 백테스트할 전략 객체 리스트
        기타 매개변수는 run_single_backtest와 동일
        
    Returns:
        dict: 전략별 백테스트 결과
    """
    logger.info(f"전략 비교 시작: {len(strategies)}개 전략")
    
    results = {}
    for strategy in strategies:
        result = run_single_backtest(
            strategy=strategy,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            commission=commission,
            market_type=market_type,
            leverage=leverage,
            save_results=save_results
        )
        results[strategy.name] = result
    
    # 비교 테이블 출력
    comparison_data = []
    for name, result in results.items():
        comparison_data.append({
            '전략': name,
            '총 수익(%)': result.total_return,
            '연간 수익률(%)': result.annual_return,
            '최대 낙폭(%)': result.max_drawdown,
            '승률(%)': result.win_rate,
            '샤프 비율': result.sharpe_ratio,
            '총 거래 횟수': result.total_trades
        })
    
    comparison_df = pd.DataFrame(comparison_data)
    print("\n전략 비교 결과:")
    print(comparison_df.to_string(index=False))
    
    if save_results:
        output_dir = f"backtest_results/{exchange}_{symbol.replace('/', '')}_{timeframe}_{market_type}"
        os.makedirs(output_dir, exist_ok=True)
        comparison_df.to_csv(f"{output_dir}/strategy_comparison.csv", index=False)
        
        # 모든 전략의 자본금 추이 비교 그래프
        plt.figure(figsize=(12, 8))
        for name, result in results.items():
            plt.plot(result.portfolio.index, result.portfolio['equity'], label=name)
        
        plt.title(f"전략별 자본금 추이 비교 ({exchange} {symbol} {timeframe})")
        plt.xlabel('날짜')
        plt.ylabel('자본금 ($)')
        plt.legend()
        plt.grid(True)
        plt.savefig(f"{output_dir}/strategy_comparison.png")
        plt.close()
    
    return results

def optimize_strategy_parameters(strategy_class, param_grid, exchange, symbol, timeframe, 
                               start_date, end_date, initial_balance=10000, 
                               commission=0.001, market_type='spot', leverage=1,
                               metric='total_return'):
    """
    전략 매개변수 최적화
    
    Args:
        strategy_class: 최적화할 전략 클래스
        param_grid (dict): 최적화할 매개변수와 값 범위 (딕셔너리)
        metric (str): 최적화 기준 지표
        기타 매개변수는 run_single_backtest와 동일
        
    Returns:
        tuple: (최적 매개변수, 최적 결과, 최적화 결과 데이터프레임)
    """
    logger.info(f"{strategy_class.__name__} 전략 최적화 시작")
    
    # Backtester 객체 생성
    backtester = Backtester(
        exchange_id=exchange,
        symbol=symbol,
        timeframe=timeframe,
        market_type=market_type,
        leverage=leverage
    )
    
    # 최적화 실행
    best_params, best_result, results_df = backtester.optimize_strategy(
        strategy_class=strategy_class,
        param_grid=param_grid,
        start_date=start_date,
        end_date=end_date,
        initial_balance=initial_balance,
        commission=commission,
        metric=metric
    )
    
    # 결과 출력
    logger.info(f"최적화 완료: {len(results_df)} 조합 테스트됨")
    logger.info(f"최적 매개변수: {best_params}")
    logger.info(f"최적 {metric}: {getattr(best_result, metric)}")
    
    # 상위 10개 결과 출력
    top_results = results_df.sort_values(by=metric, ascending=False).head(10)
    print("\n상위 10개 매개변수 조합:")
    print(top_results.to_string(index=False))
    
    # 결과 저장
    output_dir = f"backtest_results/{exchange}_{symbol.replace('/', '')}_{timeframe}_{market_type}"
    os.makedirs(output_dir, exist_ok=True)
    results_df.to_csv(f"{output_dir}/{strategy_class.__name__}_optimization.csv", index=False)
    
    return best_params, best_result, results_df

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='암호화폐 트레이딩 전략 백테스트')
    
    parser.add_argument('--strategy', type=str, default='all',
                        help='백테스트할 전략 (ma, rsi, macd, bbands, stoch, bbfutures, all)')
    parser.add_argument('--exchange', type=str, default='binance',
                        help='거래소 이름')
    parser.add_argument('--symbol', type=str, default='BTC/USDT',
                        help='트레이딩 심볼')
    parser.add_argument('--timeframe', type=str, default='1d',
                        help='타임프레임 (1h, 4h, 1d 등)')
    parser.add_argument('--start_date', type=str, default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
                        help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end_date', type=str, default=datetime.now().strftime('%Y-%m-%d'),
                        help='종료 날짜 (YYYY-MM-DD)')
    parser.add_argument('--initial_balance', type=float, default=10000,
                        help='초기 잔고')
    parser.add_argument('--commission', type=float, default=0.001,
                        help='수수료 비율 (0.001 = 0.1%)')
    parser.add_argument('--market_type', type=str, default='spot', choices=['spot', 'futures'],
                        help='시장 유형 (spot 또는 futures)')
    parser.add_argument('--leverage', type=int, default=1,
                        help='레버리지 (선물 거래용)')
    parser.add_argument('--optimize', action='store_true',
                        help='매개변수 최적화 실행 여부')
    
    args = parser.parse_args()
    
    # 전략 인스턴스 생성
    strategies = []
    
    if args.strategy == 'ma' or args.strategy == 'all':
        strategies.append(MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema'))
    
    if args.strategy == 'rsi' or args.strategy == 'all':
        strategies.append(RSIStrategy(period=14, overbought=70, oversold=30))
    
    if args.strategy == 'macd' or args.strategy == 'all':
        strategies.append(MACDStrategy(fast_period=12, slow_period=26, signal_period=9))
    
    if args.strategy == 'bbands' or args.strategy == 'all':
        strategies.append(BollingerBandsStrategy(period=20, std_dev=2.0))
    
    if args.strategy == 'stoch' or args.strategy == 'all':
        strategies.append(StochasticStrategy(k_period=14, d_period=3, slowing=3, overbought=80, oversold=20))
    
    if args.strategy == 'bbfutures' or args.strategy == 'all':
        # 선물 전략의 경우 market_type을 'futures'로 자동 설정
        strategies.append(BollingerBandFuturesStrategy(
            bb_period=20, bb_std=2.0, rsi_period=14, 
            rsi_overbought=70, rsi_oversold=30,
            macd_fast=12, macd_slow=26, macd_signal=9,
            stop_loss_pct=4.0, take_profit_pct=8.0,
            trailing_stop_pct=1.5, risk_per_trade=1.5,
            leverage=args.leverage, timeframe=args.timeframe
        ))
    
    # 선택한 전략이 없으면 종료
    if not strategies:
        logger.error(f"유효하지 않은 전략: {args.strategy}")
        return
    
    if len(strategies) == 1 and args.optimize:
        # 단일 전략 최적화
        strategy = strategies[0]
        strategy_class = type(strategy)
        
        if isinstance(strategy, MovingAverageCrossover):
            param_grid = {
                'short_period': [5, 9, 12, 15],
                'long_period': [20, 26, 30, 40],
                'ma_type': ['sma', 'ema']
            }
        elif isinstance(strategy, RSIStrategy):
            param_grid = {
                'period': [7, 10, 14, 21],
                'overbought': [65, 70, 75, 80],
                'oversold': [20, 25, 30, 35]
            }
        elif isinstance(strategy, MACDStrategy):
            param_grid = {
                'fast_period': [8, 10, 12, 15],
                'slow_period': [20, 26, 30],
                'signal_period': [7, 9, 12]
            }
        elif isinstance(strategy, BollingerBandsStrategy):
            param_grid = {
                'period': [10, 15, 20, 25],
                'std_dev': [1.5, 2.0, 2.5, 3.0]
            }
        elif isinstance(strategy, StochasticStrategy):
            param_grid = {
                'k_period': [9, 14, 20],
                'd_period': [3, 5],
                'slowing': [3, 5],
                'overbought': [75, 80, 85],
                'oversold': [15, 20, 25]
            }
        elif isinstance(strategy, BollingerBandFuturesStrategy):
            param_grid = {
                'bb_period': [15, 20, 25],
                'bb_std': [1.8, 2.0, 2.2],
                'rsi_period': [10, 14, 18],
                'rsi_overbought': [65, 70, 75],
                'rsi_oversold': [25, 30, 35],
                'stop_loss_pct': [1.5, 2.0, 2.5],
                'take_profit_pct': [3.0, 5.0, 7.0]
            }
        else:
            logger.error(f"지원하지 않는 전략 클래스: {strategy_class.__name__}")
            return
        
        best_params, best_result, results_df = optimize_strategy_parameters(
            strategy_class=strategy_class,
            param_grid=param_grid,
            exchange=args.exchange,
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_balance=args.initial_balance,
            commission=args.commission,
            market_type=args.market_type,
            leverage=args.leverage,
            metric='total_return'  # 또는 'sharpe_ratio'
        )
        
        # 최적 매개변수로 전략 재생성 및 백테스트
        best_strategy = strategy_class(**best_params)
        run_single_backtest(
            strategy=best_strategy,
            exchange=args.exchange,
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_balance=args.initial_balance,
            commission=args.commission,
            market_type=args.market_type,
            leverage=args.leverage,
            save_results=True
        )
    elif len(strategies) == 1:
        # 단일 전략 백테스트
        run_single_backtest(
            strategy=strategies[0],
            exchange=args.exchange,
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_balance=args.initial_balance,
            commission=args.commission,
            market_type=args.market_type,
            leverage=args.leverage,
            save_results=True
        )
    else:
        # 여러 전략 비교
        compare_strategies(
            strategies=strategies,
            exchange=args.exchange,
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_balance=args.initial_balance,
            commission=args.commission,
            market_type=args.market_type,
            leverage=args.leverage,
            save_results=True
        )

if __name__ == '__main__':
    main()
