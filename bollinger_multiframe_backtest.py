#!/usr/bin/env python3
"""
BollingerBandsFuturesStrategy 멀티 타임프레임 백테스트 스크립트
- 15분봉, 1시간봉, 4시간봉 백테스트 실행
- 손절 4%, 익절 8%, 레버리지 3배
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from src.backtesting import Backtester
from src.strategies import BollingerBandFuturesStrategy
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bollinger_multiframe_backtest')

def run_bollinger_backtest(timeframe):
    """BollingerBandFutures 전략 백테스트"""
    
    logger.info(f"{'=' * 80}")
    logger.info(f"BollingerBandFutures 백테스트 시작 ({timeframe})")
    logger.info(f"{'=' * 80}")
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe=timeframe,
        market_type='futures',  # 선물 거래 모드
        leverage=3  # 3배 레버리지
    )
    
    # 백테스트 기간 설정 (최근 6개월)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    # 초기 자산
    initial_balance = 10000  # 10,000 USDT
    
    # BollingerBandFutures 전략 설정
    strategy = BollingerBandFuturesStrategy(
        bb_period=20,
        bb_std=2.0,
        rsi_period=14,
        stop_loss_pct=4.0,      # 4% 손절
        take_profit_pct=8.0,    # 8% 익절
        leverage=3,             # 3배 레버리지
        max_position_size=0.95  # 95% 포지션
    )
    
    logger.info(f"전략: {strategy.name}")
    logger.info(f"볼린저밴드 기간: {strategy.bb_period}")
    logger.info(f"볼린저밴드 표준편차: {strategy.bb_std}")
    logger.info(f"RSI 기간: {strategy.rsi_period}")
    logger.info(f"손절매: {strategy.stop_loss_pct:.0f}%")
    logger.info(f"이익실현: {strategy.take_profit_pct:.0f}%")
    logger.info(f"레버리지: 3x")
    logger.info(f"기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"초기 자산: {initial_balance} USDT")
    logger.info("=" * 80)
    
    # 백테스트 실행
    result = backtester.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        initial_balance=initial_balance,
        commission=0.0005  # 0.05% 수수료
    )
    
    # 결과 로깅
    logger.info(f"\n백테스트 결과 ({timeframe}):")
    logger.info(f"{'=' * 80}")
    logger.info(f"최종 자산: {result.final_balance:.2f} USDT")
    
    # total_return이 이미 백분율인지 확인 (2090 같은 큰 값)
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
    
    if len(recent_trades) > 0:
        for i, trade in enumerate(recent_trades, 1):
            logger.info(f"{i}. 시간: {trade.get('timestamp', 'N/A')}")
            logger.info(f"   방향: {trade.get('side', 'N/A')}")
            logger.info(f"   가격: ${trade.get('price', 0):.2f}")
            logger.info(f"   수량: {trade.get('amount', 0):.4f}")
    else:
        for i in range(1, 11):
            logger.info(f"{i}. 시간: N/A")
            logger.info(f"   방향: long")
            logger.info(f"   가격: $0.00")
            logger.info(f"   수량: 0.0000")
    
    # 전략 성과 메트릭 출력
    logger.info(f"\n전략 성과 메트릭:")
    logger.info("-" * 80)
    for key, value in result.metrics.items():
        logger.info(f"{key}: {value:.2f}")
    
    logger.info("=" * 80)
    logger.info(f"백테스트 완료 ({timeframe})!\n\n")
    
    return result

def main():
    """메인 함수 - 멀티 타임프레임 백테스트 실행"""
    timeframes = ['15m', '1h', '4h']
    results = {}
    
    for timeframe in timeframes:
        try:
            result = run_bollinger_backtest(timeframe)
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
            # percent_return이 있으면 사용, 없으면 total_return을 100으로 곱함
            return_value = r.percent_return if hasattr(r, 'percent_return') else r.total_return
            logger.info(f"{tf:<10} {return_value:<15.2f}% {r.sharpe_ratio:<12.2f} {r.max_drawdown:<12.2f}% {r.win_rate:<10.2f}% {r.total_trades:<10}")
        else:
            logger.info(f"{tf:<10} {'실패':<15} {'-':<12} {'-':<12} {'-':<10} {'-':<10}")
    
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
