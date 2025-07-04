import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
sys.path.append('/Users/yong/Desktop/crypto_trading_bot_src')

from src.exchange_api import ExchangeAPI
from src.backtesting import Backtester
from src.strategies import MovingAverageCrossover
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ExchangeAPI 초기화
exchange_api = ExchangeAPI('binance', test_mode=True)

# 백테스터 초기화
backtester = Backtester(exchange_api, 'futures', leverage=2)

# 전략 생성
strategy = MovingAverageCrossover(
    short_period=9,
    long_period=26,
    ma_type='ema'
)

# 백테스트 실행
end_date = datetime.now()
start_date = end_date - timedelta(days=30)

result = backtester.run_backtest(
    strategy=strategy,
    start_date=start_date,
    end_date=end_date,
    initial_balance=10000,
    commission=0.001,
    market_type='futures',
    leverage=2
)

# 백테스트 결과 확인
logger.info(f"총 거래 횟수: {result.total_trades}")
logger.info(f"최종 수익률: {result.total_return:.2f}%")

# 백테스트 데이터에서 신호 확인
if hasattr(backtester, 'df') and backtester.df is not None:
    df = backtester.df
    logger.info(f"데이터 개수: {len(df)}")
    logger.info(f"signal 컬럼의 값 분포: {df['signal'].value_counts().to_dict()}")
    logger.info(f"position 컬럼의 값 분포: {df['position'].value_counts().to_dict()}")
    
    # 신호가 발생한 데이터 확인
    non_zero_signals = df[df['position'] != 0]
    logger.info(f"포지션 변경 횟수: {len(non_zero_signals)}")
    
    if len(non_zero_signals) > 0:
        logger.info("\n포지션 변경 샘플 (처음 5개):")
        for idx in non_zero_signals.index[:5]:
            row = df.loc[idx]
            logger.info(f"  날짜: {row.name}, 포지션: {row['position']}, 신호: {row['signal']}")
else:
    logger.warning("백테스트 데이터를 확인할 수 없습니다.")
    
# trades 상세 정보
if result.trades:
    logger.info(f"\n거래 내역 (처음 5개):")
    for trade in result.trades[:5]:
        logger.info(f"  {trade}")
