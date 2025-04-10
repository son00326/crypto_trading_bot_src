"""
기술적 분석 지표 모듈 - 암호화폐 자동매매 봇

이 모듈은 다양한 기술적 분석 지표를 계산하는 함수들을 제공합니다.
이동평균선, RSI, MACD, 볼린저 밴드 등 트레이딩에 필요한 지표들을 구현합니다.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('indicators')

def simple_moving_average(df, period=20, column='close'):
    """
    단순 이동평균선(SMA) 계산
    
    Args:
        df (DataFrame): OHLCV 데이터
        period (int): 이동평균 기간
        column (str): 계산에 사용할 컬럼명
    
    Returns:
        Series: 이동평균선 값
    """
    return df[column].rolling(window=period).mean()

def exponential_moving_average(df, period=20, column='close'):
    """
    지수 이동평균선(EMA) 계산
    
    Args:
        df (DataFrame): OHLCV 데이터
        period (int): 이동평균 기간
        column (str): 계산에 사용할 컬럼명
    
    Returns:
        Series: 지수 이동평균선 값
    """
    return df[column].ewm(span=period, adjust=False).mean()

def moving_average_convergence_divergence(df, fast_period=12, slow_period=26, signal_period=9, column='close'):
    """
    MACD(Moving Average Convergence Divergence) 계산
    
    Args:
        df (DataFrame): OHLCV 데이터
        fast_period (int): 빠른 EMA 기간
        slow_period (int): 느린 EMA 기간
        signal_period (int): 시그널 기간
        column (str): 계산에 사용할 컬럼명
    
    Returns:
        tuple: (MACD 라인, 시그널 라인, 히스토그램)
    """
    # 빠른 EMA와 느린 EMA 계산
    fast_ema = exponential_moving_average(df, period=fast_period, column=column)
    slow_ema = exponential_moving_average(df, period=slow_period, column=column)
    
    # MACD 라인 = 빠른 EMA - 느린 EMA
    macd_line = fast_ema - slow_ema
    
    # 시그널 라인 = MACD의 EMA
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    
    # 히스토그램 = MACD 라인 - 시그널 라인
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

def relative_strength_index(df, period=14, column='close'):
    """
    RSI(Relative Strength Index) 계산
    
    Args:
        df (DataFrame): OHLCV 데이터
        period (int): RSI 계산 기간
        column (str): 계산에 사용할 컬럼명
    
    Returns:
        Series: RSI 값
    """
    # 가격 변화 계산
    delta = df[column].diff()
    
    # 상승/하락 구분
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # 평균 상승/하락 계산
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # 첫 번째 값 이후의 평균 상승/하락은 다음 공식으로 계산
    # avg_gain = (이전 avg_gain * (period-1) + 현재 gain) / period
    for i in range(period, len(df)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period-1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period-1) + loss.iloc[i]) / period
    
    # RS(Relative Strength) 계산
    rs = avg_gain / avg_loss
    
    # RSI 계산: RSI = 100 - (100 / (1 + RS))
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def bollinger_bands(df, period=20, std_dev=2, column='close'):
    """
    볼린저 밴드 계산
    
    Args:
        df (DataFrame): OHLCV 데이터
        period (int): 이동평균 기간
        std_dev (float): 표준편차 배수
        column (str): 계산에 사용할 컬럼명
    
    Returns:
        tuple: (중간 밴드(SMA), 상단 밴드, 하단 밴드)
    """
    # 중간 밴드 = 단순 이동평균선
    middle_band = simple_moving_average(df, period=period, column=column)
    
    # 표준편차 계산
    std = df[column].rolling(window=period).std()
    
    # 상단 밴드 = 중간 밴드 + (표준편차 * 배수)
    upper_band = middle_band + (std * std_dev)
    
    # 하단 밴드 = 중간 밴드 - (표준편차 * 배수)
    lower_band = middle_band - (std * std_dev)
    
    return middle_band, upper_band, lower_band

def stochastic_oscillator(df, k_period=14, d_period=3, slowing=3):
    """
    스토캐스틱 오실레이터 계산
    
    Args:
        df (DataFrame): OHLCV 데이터
        k_period (int): %K 기간
        d_period (int): %D 기간
        slowing (int): 슬로잉 기간
    
    Returns:
        tuple: (%K, %D)
    """
    # 최근 k_period 동안의 최고가와 최저가 계산
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    
    # %K 계산: (현재가 - 최저가) / (최고가 - 최저가) * 100
    k_fast = 100 * ((df['close'] - low_min) / (high_max - low_min))
    
    # 슬로잉 적용
    k = k_fast.rolling(window=slowing).mean()
    
    # %D 계산: %K의 d_period 이동평균
    d = k.rolling(window=d_period).mean()
    
    return k, d

def average_directional_index(df, period=14):
    """
    ADX(Average Directional Index) 계산
    
    Args:
        df (DataFrame): OHLCV 데이터
        period (int): ADX 계산 기간
    
    Returns:
        tuple: (ADX, +DI, -DI)
    """
    # 고가, 저가, 종가의 차이 계산
    high_diff = df['high'].diff()
    low_diff = df['low'].diff() * -1  # 부호 변경
    
    # True Range 계산
    tr1 = df['high'] - df['low']
    tr2 = abs(df['high'] - df['close'].shift())
    tr3 = abs(df['low'] - df['close'].shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # +DM, -DM 계산
    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
    
    # +DI, -DI 계산
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    
    # DX 계산: |+DI - -DI| / |+DI + -DI| * 100
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    
    # ADX 계산: DX의 이동평균
    adx = dx.rolling(window=period).mean()
    
    return adx, plus_di, minus_di

def ichimoku_cloud(df, conversion_period=9, base_period=26, lagging_span2_period=52, displacement=26):
    """
    일목균형표(Ichimoku Cloud) 계산
    
    Args:
        df (DataFrame): OHLCV 데이터
        conversion_period (int): 전환선 기간
        base_period (int): 기준선 기간
        lagging_span2_period (int): 선행스팬2 기간
        displacement (int): 선행스팬 이동 기간
    
    Returns:
        tuple: (전환선, 기준선, 선행스팬1, 선행스팬2, 후행스팬)
    """
    # 전환선(Conversion Line) = (최고가 + 최저가) / 2 (conversion_period 기간)
    high_conversion = df['high'].rolling(window=conversion_period).max()
    low_conversion = df['low'].rolling(window=conversion_period).min()
    conversion_line = (high_conversion + low_conversion) / 2
    
    # 기준선(Base Line) = (최고가 + 최저가) / 2 (base_period 기간)
    high_base = df['high'].rolling(window=base_period).max()
    low_base = df['low'].rolling(window=base_period).min()
    base_line = (high_base + low_base) / 2
    
    # 선행스팬1(Leading Span A) = (전환선 + 기준선) / 2
    # displacement 기간만큼 미래로 이동
    leading_span_a = ((conversion_line + base_line) / 2).shift(displacement)
    
    # 선행스팬2(Leading Span B) = (최고가 + 최저가) / 2 (lagging_span2_period 기간)
    # displacement 기간만큼 미래로 이동
    high_lagging = df['high'].rolling(window=lagging_span2_period).max()
    low_lagging = df['low'].rolling(window=lagging_span2_period).min()
    leading_span_b = ((high_lagging + low_lagging) / 2).shift(displacement)
    
    # 후행스팬(Lagging Span) = 현재 종가를 displacement 기간만큼 과거로 이동
    lagging_span = df['close'].shift(-displacement)
    
    return conversion_line, base_line, leading_span_a, leading_span_b, lagging_span

def fibonacci_retracement(high, low):
    """
    피보나치 되돌림 레벨 계산
    
    Args:
        high (float): 최고가
        low (float): 최저가
    
    Returns:
        dict: 피보나치 되돌림 레벨
    """
    diff = high - low
    
    return {
        '0.0': low,
        '0.236': low + 0.236 * diff,
        '0.382': low + 0.382 * diff,
        '0.5': low + 0.5 * diff,
        '0.618': low + 0.618 * diff,
        '0.786': low + 0.786 * diff,
        '1.0': high
    }

def plot_indicators(df, indicators=None, title='Technical Indicators'):
    """
    기술적 지표를 시각화
    
    Args:
        df (DataFrame): OHLCV 데이터
        indicators (dict): 시각화할 지표들의 딕셔너리
        title (str): 차트 제목
    """
    if indicators is None:
        indicators = {}
    
    # 기본 차트 설정
    plt.figure(figsize=(12, 8))
    
    # 가격 차트 (캔들스틱)
    ax1 = plt.subplot2grid((6, 1), (0, 0), rowspan=3, colspan=1)
    ax1.set_title(title)
    ax1.plot(df.index, df['close'], label='Close Price')
    
    # 지표 추가
    for name, indicator in indicators.items():
        if isinstance(indicator, tuple):
            for i, ind in enumerate(indicator):
                if i == 0:
                    ax1.plot(df.index, ind, label=f'{name}')
                else:
                    ax1.plot(df.index, ind, label=f'{name}_{i}')
        else:
            ax1.plot(df.index, indicator, label=name)
    
    ax1.set_ylabel('Price')
    ax1.legend(loc='upper left')
    ax1.grid(True)
    
    # 거래량 차트
    ax2 = plt.subplot2grid((6, 1), (3, 0), rowspan=1, colspan=1, sharex=ax1)
    ax2.bar(df.index, df['volume'])
    ax2.set_ylabel('Volume')
    ax2.grid(True)
    
    # RSI 차트
    ax3 = plt.subplot2grid((6, 1), (4, 0), rowspan=2, colspan=1, sharex=ax1)
    rsi = relative_strength_index(df)
    ax3.plot(df.index, rsi, label='RSI')
    ax3.axhline(70, color='red', linestyle='--')
    ax3.axhline(30, color='green', linestyle='--')
    ax3.set_ylabel('RSI')
    ax3.grid(True)
    ax3.legend(loc='upper left')
    
    plt.tight_layout()
    plt.show()

# 테스트 코드
if __name__ == "__main__":
    # 테스트용 데이터 생성
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    data = {
        'open': np.random.normal(10000, 200, 100),
        'high': np.random.normal(10100, 200, 100),
        'low': np.random.normal(9900, 200, 100),
        'close': np.random.normal(10050, 200, 100),
        'volume': np.random.normal(1000, 200, 100)
    }
    df = pd.DataFrame(data, index=dates)
    
    # 지표 계산
    sma_20 = simple_moving_average(df, period=20)
    ema_20 = exponential_moving_average(df, period=20)
    macd_line, signal_line, histogram = moving_average_convergence_divergence(df)
    rsi = relative_strength_index(df)
    middle_band, upper_band, lower_band = bollinger_bands(df)
    
    # 결과 출력
    print("SMA(20):")
    print(sma_20.tail())
    print("\nEMA(20):")
    print(ema_20.tail())
    print("\nMACD:")
    print(macd_line.tail())
    print("\nRSI:")
    print(rsi.tail())
    print("\nBollinger Bands:")
    print(middle_band.tail())
    
    # 지표 시각화
    indicators = {
        'SMA(20)': sma_20,
        'EMA(20)': ema_20,
        'Bollinger Bands': (middle_band, upper_band, lower_band)
    }
    plot_indicators(df, indicators, title='Technical Indicators Test')
