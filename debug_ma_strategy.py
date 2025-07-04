import pandas as pd
import numpy as np
import sys
sys.path.append('/Users/yong/Desktop/crypto_trading_bot_src')

from src.strategies import MovingAverageCrossover
from src.backtesting import Backtester
from src.data_manager import DataManager
import logging

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 백테스터를 통해 데이터 로드
from src.exchange_api import ExchangeAPI
from src.data_collector import DataCollector

exchange_api = ExchangeAPI(exchange_id='binance', api_key='', api_secret='', test_mode=True)
data_collector = DataCollector(exchange_api)
backtester = Backtester(exchange_api, 'futures', leverage=1)

# 백테스트 데이터 준비
from datetime import datetime, timedelta
end_date = datetime.now()
start_date = end_date - timedelta(days=30)

df = backtester.prepare_backtest_data(
    symbol='BTC/USDT',
    timeframe='1h',
    start_date=start_date,
    end_date=end_date,
    data_collector=data_collector
)

# 최근 1000개 데이터만 사용
if df is not None and len(df) > 1000:
    df = df.tail(1000)

# 전략 생성
strategy = MovingAverageCrossover(
    short_period=9,
    long_period=26,
    ma_type='ema'
)

# 신호 생성
result_df = strategy.generate_signals(df)

# 신호 분석
print(f"총 데이터 개수: {len(result_df)}")
print(f"신호 값 분포: {result_df['signal'].value_counts()}")
print(f"포지션 값 분포: {result_df['position'].value_counts()}")

# 이동평균 교차 지점 찾기
result_df['short_ma'] = result_df['short_ma']
result_df['long_ma'] = result_df['long_ma']
result_df['ma_diff'] = result_df['short_ma'] - result_df['long_ma']
result_df['ma_diff_prev'] = result_df['ma_diff'].shift(1)

# 교차 지점 찾기
crossovers = result_df[
    ((result_df['ma_diff_prev'] <= 0) & (result_df['ma_diff'] > 0)) |
    ((result_df['ma_diff_prev'] >= 0) & (result_df['ma_diff'] < 0))
].copy()

print(f"\n총 교차 지점 개수: {len(crossovers)}")

# RSI와 볼륨 조건 확인
if len(crossovers) > 0:
    print("\n교차 지점에서의 조건:")
    for idx in crossovers.index[:10]:  # 처음 10개만 확인
        row = result_df.loc[idx]
        print(f"\n날짜: {row.name}")
        print(f"  교차 유형: {'상향' if row['ma_diff'] > 0 else '하향'}")
        print(f"  RSI: {row['rsi']:.2f}")
        print(f"  볼륨: {row['volume']:.2f}")
        print(f"  볼륨 MA: {row['volume_ma']:.2f}")
        print(f"  볼륨/볼륨MA 비율: {row['volume']/row['volume_ma']:.2f}")
        print(f"  신호: {row['signal']}")
        
# 필터 조건 테스트
print("\n필터 조건 충족 여부:")
print(f"RSI < 70 인 데이터: {len(result_df[result_df['rsi'] < 70])} / {len(result_df)}")
print(f"RSI > 30 인 데이터: {len(result_df[result_df['rsi'] > 30])} / {len(result_df)}")
print(f"볼륨 > 볼륨MA*0.5 인 데이터: {len(result_df[result_df['volume'] > result_df['volume_ma']*0.5])} / {len(result_df)}")
