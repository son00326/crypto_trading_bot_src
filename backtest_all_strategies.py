#!/usr/bin/env python
"""
Crypto Trading Bot 모든 전략 백테스트 스크립트

이 스크립트는 모든 거래 전략에 대해 지정된 파라미터로 백테스트를 실행하고 결과를 비교합니다.
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import logging

from src.backtesting import Backtester
from src.strategies import (
    MovingAverageCrossover, RSIStrategy, MACDStrategy, 
    BollingerBandsStrategy, StochasticStrategy, BollingerBandFuturesStrategy
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('backtest_all_strategies')

def run_all_backtests(symbol="BTCUSDT", timeframes=["15m", "1h", "4h"], 
                       start_date=None, end_date=None, market_type="futures", 
                       leverage=3, stop_loss_pct=4.0, take_profit_pct=8.0):
    """
    모든 전략에 대해 백테스트를 실행하고 결과를 반환합니다.
    
    Args:
        symbol (str): 거래 심볼
        timeframes (list): 백테스트할 타임프레임 목록
        start_date (str): 시작 날짜 (None이면 60일 전)
        end_date (str): 종료 날짜 (None이면 오늘)
        market_type (str): 시장 유형 ('spot' 또는 'futures')
        leverage (int): 레버리지 배수
        stop_loss_pct (float): 손절 비율(%)
        take_profit_pct (float): 이익실현 비율(%)
        
    Returns:
        dict: 타임프레임별 백테스트 결과
    """
    # 기간 설정 (기본값: 최근 60일)
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        
    logger.info(f"백테스트 기간: {start_date} ~ {end_date}")
    logger.info(f"시장 유형: {market_type}, 레버리지: {leverage}x")
    logger.info(f"손절: {stop_loss_pct}%, 이익실현: {take_profit_pct}%")
    
    # 결과 저장 딕셔너리
    results = {}
    
    # 각 타임프레임에 대해 백테스트 실행
    for timeframe in timeframes:
        logger.info(f"\n===== 타임프레임: {timeframe} =====")
        
        # 백테스터 초기화
        backtester = Backtester(
            exchange_id='binance', 
            symbol=symbol, 
            timeframe=timeframe,
            market_type=market_type,
            leverage=leverage
        )
        
        # 전략 객체 생성
        strategies = [
            MovingAverageCrossover(
                stop_loss_pct=stop_loss_pct, 
                take_profit_pct=take_profit_pct, 
                leverage=leverage
            ),
            RSIStrategy(
                stop_loss_pct=stop_loss_pct, 
                take_profit_pct=take_profit_pct, 
                leverage=leverage
            ),
            MACDStrategy(
                stop_loss_pct=stop_loss_pct, 
                take_profit_pct=take_profit_pct, 
                leverage=leverage
            ),
            BollingerBandsStrategy(
                stop_loss_pct=stop_loss_pct, 
                take_profit_pct=take_profit_pct, 
                leverage=leverage
            ),
            StochasticStrategy(
                stop_loss_pct=stop_loss_pct, 
                take_profit_pct=take_profit_pct, 
                leverage=leverage
            ),
            BollingerBandFuturesStrategy(
                stop_loss_pct=stop_loss_pct, 
                take_profit_pct=take_profit_pct, 
                leverage=leverage
            )
        ]
        
        # 각 전략에 대해 백테스트 실행
        timeframe_results = {}
        for strategy in strategies:
            logger.info(f"전략 '{strategy.name}' 백테스트 실행 중...")
            
            # 백테스트 실행
            result = backtester.run_backtest(
                strategy=strategy,
                start_date=start_date,
                end_date=end_date,
                initial_balance=10000,
                commission=0.001,
                market_type=market_type,
                leverage=leverage
            )
            
            if result:
                timeframe_results[strategy.name] = result
                logger.info(f"전략 '{strategy.name}' 백테스트 완료")
            else:
                logger.warning(f"전략 '{strategy.name}' 백테스트 실패")
        
        # 결과 저장
        results[timeframe] = timeframe_results
    
    return results

def create_summary_table(results):
    """
    백테스트 결과를 요약한 테이블을 생성합니다.
    
    Args:
        results (dict): 타임프레임별 백테스트 결과
        
    Returns:
        DataFrame: 결과 요약 테이블
    """
    # 결과 저장용 리스트
    summary_data = []
    
    # 각 타임프레임과 전략에 대한 결과 추출
    for timeframe, timeframe_results in results.items():
        for strategy_name, result in timeframe_results.items():
            summary_data.append({
                'Timeframe': timeframe,
                'Strategy': strategy_name,
                'Total Return (%)': round(result.total_return, 2),
                'Win Rate (%)': round(result.win_rate, 2),
                'Total Trades': result.total_trades,
                'Max Drawdown (%)': round(result.max_drawdown, 2),
                'Sharpe Ratio': round(result.sharpe_ratio, 2),
                'Profit Factor': round(result.profit_factor, 2) if result.profit_factor != float('inf') else 'inf',
                'Final Balance': round(result.final_balance, 2),
            })
    
    # 데이터프레임 생성
    df = pd.DataFrame(summary_data)
    
    # 타임프레임과 수익률로 정렬
    df = df.sort_values(['Timeframe', 'Total Return (%)'], ascending=[True, False])
    
    return df

def plot_equity_curves(results, timeframe, save_dir=None, show=True):
    """
    특정 타임프레임에 대한 모든 전략의 수익률 곡선을 그립니다.
    
    Args:
        results (dict): 백테스트 결과
        timeframe (str): 표시할 타임프레임
        save_dir (str): 저장할 디렉토리 경로
        show (bool): 차트 표시 여부
    """
    plt.figure(figsize=(16, 10))
    
    # 각 전략에 대한 수익률 곡선 그리기
    for strategy_name, result in results[timeframe].items():
        equity_curve = result.equity_curve
        if equity_curve is not None and not equity_curve.empty and 'equity_curve' in equity_curve.columns:
            # 판다스 인덱스를 numpy 배열로 변환하여 사용
            plt.plot(np.array(equity_curve.index), 
                     np.array(equity_curve['equity_curve'] * 100), 
                     label=strategy_name)
    
    plt.title(f'전략별 수익률 비교 (타임프레임: {timeframe})', fontsize=16)
    plt.xlabel('날짜', fontsize=12)
    plt.ylabel('수익률 (%)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    # 결과 저장
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f'equity_curves_{timeframe}.png')
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"수익률 곡선을 {save_path}에 저장했습니다.")
    
    if show:
        plt.show()
    else:
        plt.close()

def run_and_display_results():
    """
    백테스트를 실행하고 결과를 표시합니다.
    """
    # 백테스트 파라미터 설정
    timeframes = ["15m", "1h", "4h"]
    market_type = "futures"
    leverage = 3
    stop_loss_pct = 4.0
    take_profit_pct = 8.0
    symbol = "BTCUSDT"
    
    # 결과 저장 디렉토리
    results_dir = os.path.join(os.path.dirname(__file__), "backtest_results")
    os.makedirs(results_dir, exist_ok=True)
    
    logger.info("모든 전략에 대한 백테스트를 시작합니다.")
    
    # 백테스트 실행
    results = run_all_backtests(
        symbol=symbol,
        timeframes=timeframes,
        market_type=market_type,
        leverage=leverage,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct
    )
    
    # 결과 요약 테이블 생성
    summary_table = create_summary_table(results)
    
    # 결과 표시 및 저장
    print("\n===== 백테스트 결과 요약 =====")
    print(summary_table.to_string())
    
    # CSV로 저장
    csv_path = os.path.join(results_dir, "backtest_summary.csv")
    summary_table.to_csv(csv_path, index=False)
    logger.info(f"백테스트 결과를 {csv_path}에 저장했습니다.")
    
    # 각 타임프레임에 대한 수익률 곡선 생성 및 저장
    for timeframe in timeframes:
        plot_equity_curves(results, timeframe, save_dir=results_dir, show=False)
    
    # 최고 성능 전략 찾기
    best_strategy_row = summary_table.loc[summary_table['Total Return (%)'].idxmax()]
    print(f"\n===== 최고 성능 전략 =====")
    print(f"타임프레임: {best_strategy_row['Timeframe']}")
    print(f"전략: {best_strategy_row['Strategy']}")
    print(f"총 수익률: {best_strategy_row['Total Return (%)']}%")
    print(f"승률: {best_strategy_row['Win Rate (%)']}%")
    print(f"최대 낙폭: {best_strategy_row['Max Drawdown (%)']}%")
    print(f"샤프 비율: {best_strategy_row['Sharpe Ratio']}")
    print(f"최종 자산: ${best_strategy_row['Final Balance']}")
    
    # 타임프레임별 최고 성능 전략 요약
    print("\n===== 타임프레임별 최고 성능 전략 =====")
    for timeframe in timeframes:
        timeframe_data = summary_table[summary_table['Timeframe'] == timeframe]
        if not timeframe_data.empty:
            best_row = timeframe_data.loc[timeframe_data['Total Return (%)'].idxmax()]
            print(f"{timeframe}: {best_row['Strategy']} - 수익률: {best_row['Total Return (%)']}%, 승률: {best_row['Win Rate (%)']}%")
    
    logger.info("백테스트 완료!")
    return results, summary_table

if __name__ == "__main__":
    run_and_display_results()
