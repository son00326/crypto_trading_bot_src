#!/usr/bin/env python3
"""
개선된 전략 백테스트 스크립트
"""
import logging
import pandas as pd
from datetime import datetime, timedelta
from src.strategies import BollingerBandFuturesStrategy, MovingAverageCrossover
from src.backtesting import Backtester

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_improved')

def run_improved_backtest():
    """개선된 전략들의 백테스트 실행"""
    
    # 백테스트 설정
    exchange_id = 'binance'
    symbol = 'BTC/USDT'
    timeframes = ['1h', '4h']
    
    results_summary = []
    
    # 1. BollingerBandFuturesStrategy (개선된 버전)
    logger.info("=" * 80)
    logger.info("BollingerBandFuturesStrategy 백테스트 시작 (개선 버전)")
    logger.info("=" * 80)
    
    for timeframe in timeframes:
        logger.info(f"\n타임프레임: {timeframe}")
        
        # 백테스터 초기화
        backtester = Backtester(
            exchange_id=exchange_id,
            symbol=symbol,
            timeframe=timeframe,
            market_type='futures',
            leverage=2  # 3에서 2로 감소
        )
        
        # 개선된 전략 초기화 (조건 완화, 레버리지 감소, SL/TP 조정)
        strategy = BollingerBandFuturesStrategy(
            bb_period=20,
            bb_std=2.0,
            rsi_period=14,
            stop_loss_pct=2.0,  # 4.0 -> 2.0
            take_profit_pct=3.0,  # 8.0 -> 3.0
            leverage=2  # 3 -> 2
        )
        
        # 백테스트 실행
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        
        result = backtester.run_backtest(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            initial_balance=10000,
            commission=0.001,
            market_type='futures',
            leverage=2
        )
        
        # 결과 저장
        results_summary.append({
            'strategy': 'BollingerBand_Improved',
            'timeframe': timeframe,
            'total_return': result.total_return,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown,
            'win_rate': result.win_rate,
            'total_trades': result.total_trades
        })
        
        logger.info(f"최종 수익률: {result.total_return:.2f}%")
        logger.info(f"샤프 비율: {result.sharpe_ratio:.2f}")
        logger.info(f"최대 낙폭: {result.max_drawdown:.2f}%")
        logger.info(f"승률: {result.win_rate:.2f}%")
        logger.info(f"총 거래 횟수: {result.total_trades}")
    
    # 2. MovingAverageCrossover (개선된 버전)
    logger.info("\n" + "=" * 80)
    logger.info("MovingAverageCrossover 백테스트 시작 (개선 버전)")
    logger.info("=" * 80)
    
    for timeframe in timeframes:
        logger.info(f"\n타임프레임: {timeframe}")
        
        # 백테스터 초기화
        backtester = Backtester(
            exchange_id=exchange_id,
            symbol=symbol,
            timeframe=timeframe,
            market_type='futures',
            leverage=3
        )
        
        # 개선된 전략 초기화 (RSI/볼륨 필터 추가, 파라미터 조정)
        strategy = MovingAverageCrossover(
            short_period=20,  # 9 -> 20
            long_period=50,   # 26 -> 50
            ma_type='ema',    # sma -> ema
            stop_loss_pct=1.5,   # 2.0 -> 1.5
            take_profit_pct=3.0  # 4.0 -> 3.0
        )
        
        # 백테스트 실행
        result = backtester.run_backtest(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            initial_balance=10000,
            commission=0.001,
            market_type='futures',
            leverage=2
        )
        
        # 결과 저장
        results_summary.append({
            'strategy': 'MA_Crossover_Improved',
            'timeframe': timeframe,
            'total_return': result.total_return,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown,
            'win_rate': result.win_rate,
            'total_trades': result.total_trades
        })
        
        logger.info(f"최종 수익률: {result.total_return:.2f}%")
        logger.info(f"샤프 비율: {result.sharpe_ratio:.2f}")
        logger.info(f"최대 낙폭: {result.max_drawdown:.2f}%")
        logger.info(f"승률: {result.win_rate:.2f}%")
        logger.info(f"총 거래 횟수: {result.total_trades}")
    
    # 전체 결과 요약
    logger.info("\n" + "=" * 80)
    logger.info("전체 백테스트 결과 요약 (개선 전 vs 개선 후)")
    logger.info("=" * 80)
    
    # 이전 결과 (하드코딩)
    previous_results = {
        'BollingerBand_1h': -10.55,
        'BollingerBand_4h': -20.90,
        'MA_Crossover_1h': -19.00,
        'MA_Crossover_4h': -10.35
    }
    
    logger.info(f"\n{'전략':25} {'타임프레임':10} {'개선 전':>12} {'개선 후':>12} {'변화':>12}")
    logger.info("-" * 80)
    
    for result in results_summary:
        strategy_key = result['strategy'].replace('_Improved', '')
        timeframe = result['timeframe']
        prev_key = f"{strategy_key}_{timeframe}"
        
        if prev_key in previous_results:
            prev_return = previous_results[prev_key]
            curr_return = result['total_return']
            change = curr_return - prev_return
            
            logger.info(f"{result['strategy']:25} {timeframe:10} {prev_return:>11.2f}% {curr_return:>11.2f}% {change:>+11.2f}%")

if __name__ == "__main__":
    run_improved_backtest()
