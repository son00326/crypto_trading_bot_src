#!/usr/bin/env python3
"""
Moving Average Crossover 전략 멀티 타임프레임 백테스트
- 1시간봉과 4시간봉으로 백테스트 실행
- 선물 거래 모드로 레버리지 포함
"""

import logging
import sys
import os
from datetime import datetime, timedelta

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backtesting import Backtester
from src.strategies import MovingAverageCrossover

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ma_multiframe_backtest')

def run_ma_backtest(timeframe):
    """Moving Average Crossover 백테스트 실행"""
    logger.info(f"\nMoving Average Crossover 백테스트 시작 ({timeframe})")
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe=timeframe,
        market_type='futures',  # futures 모드
        leverage=3  # 3배 레버리지
    )
    
    # Moving Average Crossover 전략 생성
    strategy = MovingAverageCrossover(
        short_period=20,
        long_period=50,
        stop_loss_pct=2.0,      # 2% 손절매
        take_profit_pct=4.0,    # 4% 익절매
    )
    
    # 백테스트 실행
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)  # 6개월 데이터
    
    result = backtester.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        initial_balance=10000,
        commission=0.0005  # 0.05% 수수료
    )
    
    # 결과 로깅
    logger.info(f"\n백테스트 결과 ({timeframe}):")
    logger.info(f"{'=' * 80}")
    logger.info(f"최종 자산: {result.final_balance:.2f} USDT")
    
    # total_return이 이미 백분율인지 확인
    if hasattr(result, 'percent_return'):
        logger.info(f"총 수익률: {result.percent_return:.2f}%")
    else:
        logger.info(f"총 수익률: {result.total_return:.2f}%")
    
    logger.info(f"샤프 비율: {result.sharpe_ratio:.2f}")
    logger.info(f"최대 낙폭: {result.max_drawdown:.2f}%")
    logger.info(f"승률: {result.win_rate:.2f}%")
    logger.info(f"총 거래 횟수: {result.total_trades}")
    
    # 추가 정보가 있는 경우에만 출력
    if hasattr(result, 'winning_trades'):
        logger.info(f"수익 거래: {result.winning_trades}")
        logger.info(f"수익 거래 비율: {(result.winning_trades/result.total_trades*100):.1f}%" if result.total_trades > 0 else "N/A")
    if hasattr(result, 'losing_trades'):
        logger.info(f"손실 거래: {result.losing_trades}")
    if hasattr(result, 'profit_factor') and result.profit_factor is not None:
        logger.info(f"Profit Factor: {result.profit_factor:.2f}")
    
    logger.info(f"{'=' * 80}")
    
    # 최근 거래 출력
    logger.info(f"\n최근 10개 거래:")
    logger.info("-" * 80)
    recent_trades = result.trades[-10:] if len(result.trades) > 0 else []
    
    for i, trade in enumerate(recent_trades, 1):
        logger.info(f"{i}. 시간: {trade.get('timestamp', 'N/A')}")
        logger.info(f"   방향: {trade.get('side', 'N/A')}")
        logger.info(f"   가격: ${trade.get('price', 0):.2f}")
        logger.info(f"   수량: {trade.get('amount', 0):.4f}")
    
    # 전체 성과 메트릭 출력
    logger.info(f"\n전략 성과 메트릭:")
    logger.info("-" * 80)
    for key, value in vars(result).items():
        if key not in ['trades', 'equity_curve', 'positions']:
            logger.info(f"{key}: {value:.2f}" if isinstance(value, (int, float)) else f"{key}: {value}")
    
    logger.info(f"{'=' * 80}")
    logger.info(f"백테스트 완료 ({timeframe})!\n\n")
    
    return result

def main():
    """메인 함수 - 멀티 타임프레임 백테스트 실행"""
    timeframes = ['1h', '4h']  # 1시간봉과 4시간봉
    results = {}
    
    for timeframe in timeframes:
        try:
            result = run_ma_backtest(timeframe)
            results[timeframe] = result
        except Exception as e:
            logger.error(f"{timeframe} 백테스트 중 오류 발생: {e}")
            continue
    
    # 전체 결과 요약
    logger.info("\n" + "=" * 80)
    logger.info("전체 백테스트 결과 요약")
    logger.info("=" * 80)
    logger.info(f"{'타임프레임':<10} {'최종 수익률':<15} {'샤프 비율':<12} {'최대 낙폭':<12} {'승률':<10} {'거래 횟수':<10}")
    logger.info("-" * 80)
    
    for tf in timeframes:
        if tf in results:
            r = results[tf]
            # percent_return이 있으면 사용, 없으면 total_return 사용
            return_value = r.percent_return if hasattr(r, 'percent_return') else r.total_return
            logger.info(f"{tf:<10} {return_value:<15.2f}% {r.sharpe_ratio:<12.2f} {r.max_drawdown:<12.2f}% {r.win_rate:<10.2f}% {r.total_trades:<10}")
        else:
            logger.info(f"{tf:<10} {'실패':<15} {'-':<12} {'-':<12} {'-':<10} {'-':<10}")
    
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
