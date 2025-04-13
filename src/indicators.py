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
    try:
        # 입력 데이터 검증
        if df is None or len(df) == 0:
            logger.error("SMA 계산 오류: 입력 데이터프레임이 비어있거나 None입니다.")
            return pd.Series(np.nan, index=range(1))
            
        if column not in df.columns:
            logger.error(f"SMA 계산 오류: '{column}' 컬럼이 데이터프레임에 없습니다.")
            return pd.Series(np.nan, index=df.index)
            
        # NumPy 배열 사용하여 SMA 계산 (다차원 인덱싱 방지)
        values = df[column].values  # NumPy 배열로 변환
        n = len(values)
        result = np.full(n, np.nan)
        
        # 루프 기반의 명시적 계산 (내부적 다차원 인덱싱 회피)
        for i in range(period-1, n):
            window = values[i-period+1:i+1]
            if np.any(np.isnan(window)):
                result[i] = np.nan
            else:
                result[i] = np.mean(window)
                
        # 결과를 시리즈로 변환 (원본 인덱스 유지)
        return pd.Series(result, index=df.index)
    except Exception as e:
        logger.error(f"SMA 계산 오류: {e}")
        return pd.Series(np.nan, index=df.index if df is not None and hasattr(df, 'index') else range(1))

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
    try:
        # 입력 데이터 검증
        if df is None or len(df) == 0:
            logger.error("EMA 계산 오류: 입력 데이터프레임이 비어있거나 None입니다.")
            return pd.Series(np.nan, index=range(1))
            
        if column not in df.columns:
            logger.error(f"EMA 계산 오류: '{column}' 컬럼이 데이터프레임에 없습니다.")
            return pd.Series(np.nan, index=df.index)
        
        # 데이터프레임 복사
        df_copy = df.copy()
        
        # NumPy 배열 사용하여 EMA 직접 계산 (다차원 인덱싱 방지)
        values = df_copy[column].values  # NumPy 배열로 변환
        n = len(values)
        result = np.full(n, np.nan)
        
        # SMA로 첫 번째 값 초기화
        if period <= n:
            initial_sma = np.nanmean(values[:period])
            result[period-1] = initial_sma
            
            # EMA 계산 공식: EMA_today = (Value_today * k) + (EMA_yesterday * (1-k)) where k = 2/(period+1)
            k = 2 / (period + 1)
            
            # 루프 기반의 명시적 계산 (내부적 다차원 인덱싱 회피)
            for i in range(period, n):
                if np.isnan(values[i]) or np.isnan(result[i-1]):
                    result[i] = np.nan
                else:
                    result[i] = (values[i] * k) + (result[i-1] * (1 - k))
        
        # 결과를 시리즈로 변환 (원본 인덱스 유지)
        return pd.Series(result, index=df.index)
    except Exception as e:
        logger.error(f"EMA 계산 오류: {e}")
        return pd.Series(np.nan, index=df.index if df is not None and hasattr(df, 'index') else range(1))

def moving_average_convergence_divergence(df, fast_period=12, slow_period=26, signal_period=9, column='close'):
    """
    MACD(Moving Average Convergence Divergence) 계산
    
    Args:
        df (DataFrame): OHLCV 데이터
        fast_period (int): 빠른 EMA 기간
        slow_period (int): 느린 EMA 기간
        signal_period (int): 시그널 기간
        column (str): 계산에 사용할 컴럼명
    
    Returns:
        tuple: (MACD 라인, 시그널 라인, 히스토그램)
    """
    try:
        # 데이터프레임 복사본 생성
        df_macd = df.copy()
        
        # 빠른 EMA와 느린 EMA 계산
        df_macd['fast_ema'] = df_macd[column].ewm(span=fast_period, adjust=False).mean()
        df_macd['slow_ema'] = df_macd[column].ewm(span=slow_period, adjust=False).mean()
        
        # MACD 라인 = 빠른 EMA - 느린 EMA
        df_macd['macd_line'] = df_macd['fast_ema'] - df_macd['slow_ema']
        
        # 시그널 라인 = MACD의 EMA
        df_macd['signal_line'] = df_macd['macd_line'].ewm(span=signal_period, adjust=False).mean()
        
        # 히스토그램 = MACD 라인 - 시그널 라인
        df_macd['histogram'] = df_macd['macd_line'] - df_macd['signal_line']
        
        # NaN 없는 결과값 반환
        df_macd = df_macd.replace([np.inf, -np.inf], np.nan)
        
        return df_macd['macd_line'], df_macd['signal_line'], df_macd['histogram']
    
    except Exception as e:
        logger.error(f"MACD 계산 오류: {e}")
        # 빈 시리즈 반환
        empty_series = pd.Series(np.nan, index=df.index)
        return empty_series, empty_series, empty_series

def relative_strength_index(df, period=14, column='close'):
    """
    RSI(Relative Strength Index) 계산
    
    Args:
        df (DataFrame): OHLCV 데이터
        period (int): RSI 계산 기간
        column (str): 계산에 사용할 컴럼명
    
    Returns:
        Series: RSI 값
    """
    try:
        # 데이터프레임 복사본 생성
        df_rsi = df.copy()
        
        # 가격 변화 계산
        df_rsi['delta'] = df_rsi[column].diff()
        
        # 상승/하락 구분
        df_rsi['gain'] = df_rsi['delta'].clip(lower=0)
        df_rsi['loss'] = -df_rsi['delta'].clip(upper=0)
        
        # 초기 평균 값
        first_avg_gain = df_rsi['gain'].rolling(window=period).mean().iloc[period-1]
        first_avg_loss = df_rsi['loss'].rolling(window=period).mean().iloc[period-1]
        
        # wilder's smoothing
        df_rsi['avg_gain'] = np.nan
        df_rsi['avg_loss'] = np.nan
        df_rsi.loc[period-1, 'avg_gain'] = first_avg_gain
        df_rsi.loc[period-1, 'avg_loss'] = first_avg_loss
        
        # 숫자로 변환하여 연산 수행
        gain_values = df_rsi['gain'].values
        loss_values = df_rsi['loss'].values
        avg_gain_values = np.full_like(gain_values, np.nan)
        avg_loss_values = np.full_like(loss_values, np.nan)
        avg_gain_values[period-1] = first_avg_gain
        avg_loss_values[period-1] = first_avg_loss
        
        # 벡터화 대신 단순 반복문 사용
        for i in range(period, len(df_rsi)):
            avg_gain_values[i] = (avg_gain_values[i-1] * (period-1) + gain_values[i]) / period
            avg_loss_values[i] = (avg_loss_values[i-1] * (period-1) + loss_values[i]) / period
        
        # 계산된 값을 다시 데이터프레임에 저장
        df_rsi['avg_gain'] = avg_gain_values
        df_rsi['avg_loss'] = avg_loss_values
        
        # 0으로 나누기 방지
        df_rsi['avg_loss'] = np.where(df_rsi['avg_loss'] == 0, 0.001, df_rsi['avg_loss'])
        
        # RS(Relative Strength) 계산
        df_rsi['rs'] = df_rsi['avg_gain'] / df_rsi['avg_loss']
        
        # RSI 계산: RSI = 100 - (100 / (1 + RS))
        df_rsi['rsi'] = 100 - (100 / (1 + df_rsi['rs']))
        
        # NaN 처리
        df_rsi = df_rsi.replace([np.inf, -np.inf], np.nan)
        
        return df_rsi['rsi']
    
    except Exception as e:
        logger.error(f"RSI 계산 오류: {e}")
        # 빈 시리즈 반환
        return pd.Series(np.nan, index=df.index)

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
    try:
        # 데이터프레임 복사본 생성
        df_bb = df.copy()
        
        # 중간 밴드 = 단순 이동평균선
        df_bb['middle_band'] = df_bb[column].rolling(window=period).mean()
        
        # 표준편차 계산
        df_bb['std'] = df_bb[column].rolling(window=period).std()
        
        # 상단 밴드 = 중간 밴드 + (표준편차 * 배수)
        # 벡터화된 방식으로 계산하여 다차원 인덱싱 문제 방지
        df_bb['upper_band'] = df_bb['middle_band'] + (df_bb['std'] * std_dev)
        
        # 하단 밴드 = 중간 밴드 - (표준편차 * 배수)
        df_bb['lower_band'] = df_bb['middle_band'] - (df_bb['std'] * std_dev)
        
        # NaN 및 무한값 처리
        df_bb = df_bb.replace([np.inf, -np.inf], np.nan)
        
        return df_bb['middle_band'], df_bb['upper_band'], df_bb['lower_band']
    
    except Exception as e:
        logger.error(f"볼린저 밴드 계산 오류: {e}")
        # 빈 시리즈 반환
        empty_series = pd.Series(np.nan, index=df.index)
        return empty_series, empty_series, empty_series

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
    try:
        # 데이터프레임 복사본 생성
        df_stoch = df.copy()
        
        # 최근 k_period 동안의 최고가와 최저가 계산
        df_stoch['low_min'] = df_stoch['low'].rolling(window=k_period).min()
        df_stoch['high_max'] = df_stoch['high'].rolling(window=k_period).max()
        
        # 0으로 나누는 오류 방지
        divisor = df_stoch['high_max'] - df_stoch['low_min']
        # 0인 부분은 작은 값으로 대체하여 나누기 오류 방지
        divisor = np.where(divisor == 0, 0.0001, divisor)
        
        # %K 계산: (현재가 - 최저가) / (최고가 - 최저가) * 100
        df_stoch['k_fast'] = 100 * ((df_stoch['close'] - df_stoch['low_min']) / divisor)
        
        # 슬로잉 적용
        df_stoch['k'] = df_stoch['k_fast'].rolling(window=slowing).mean()
        
        # %D 계산: %K의 d_period 이동평균
        df_stoch['d'] = df_stoch['k'].rolling(window=d_period).mean()
        
        # NaN 처리
        df_stoch = df_stoch.replace([np.inf, -np.inf], np.nan)
        
        return df_stoch['k'], df_stoch['d']
    
    except Exception as e:
        logger.error(f"스토캐스틱 오실레이터 계산 오류: {e}")
        # 빈 시리즈 반환
        empty_series = pd.Series(np.nan, index=df.index)
        return empty_series, empty_series

def average_directional_index(df, period=14):
    """
    ADX(Average Directional Index) 계산
    
    Args:
        df (DataFrame): OHLCV 데이터
        period (int): ADX 계산 기간
    
    Returns:
        tuple: (ADX, +DI, -DI)
    """
    try:
        # 데이터프레임 복사본 생성하여 계산
        df_adx = df.copy()
        
        # 고가, 저가, 종가의 차이 계산
        df_adx['high_diff'] = df_adx['high'].diff()
        df_adx['low_diff'] = df_adx['low'].diff() * -1  # 부호 변경
        
        # True Range 계산
        df_adx['tr1'] = df_adx['high'] - df_adx['low']
        df_adx['tr2'] = (df_adx['high'] - df_adx['close'].shift()).abs()
        df_adx['tr3'] = (df_adx['low'] - df_adx['close'].shift()).abs()
        
        # numpy 배열로 변환하여 max 계산
        tr_array = np.vstack([df_adx['tr1'].values, df_adx['tr2'].values, df_adx['tr3'].values])
        df_adx['tr'] = np.max(tr_array, axis=0)
        
        # +DM, -DM 계산
        condition1 = (df_adx['high_diff'] > df_adx['low_diff']) & (df_adx['high_diff'] > 0)
        condition2 = (df_adx['low_diff'] > df_adx['high_diff']) & (df_adx['low_diff'] > 0)
        
        df_adx['plus_dm'] = np.where(condition1, df_adx['high_diff'], 0)
        df_adx['minus_dm'] = np.where(condition2, df_adx['low_diff'], 0)
        
        # +DI, -DI 계산
        df_adx['atr'] = df_adx['tr'].rolling(window=period).mean()
        df_adx['plus_di'] = 100 * (df_adx['plus_dm'].rolling(window=period).mean() / df_adx['atr'])
        df_adx['minus_di'] = 100 * (df_adx['minus_dm'].rolling(window=period).mean() / df_adx['atr'])
        
        # DX 계산: |+DI - -DI| / |+DI + -DI| * 100
        df_adx['dx'] = 100 * abs(df_adx['plus_di'] - df_adx['minus_di']) / (df_adx['plus_di'] + df_adx['minus_di'])
        
        # ADX 계산: DX의 이동평균
        df_adx['adx'] = df_adx['dx'].rolling(window=period).mean()
        
        # NaN 값 처리
        df_adx = df_adx.replace([np.inf, -np.inf], np.nan)
        
        return df_adx['adx'], df_adx['plus_di'], df_adx['minus_di']
    
    except Exception as e:
        logger.error(f"ADX 계산 중 오류 발생: {e}")
        # 빈 시리즈 반환
        empty_series = pd.Series(np.nan, index=df.index)
        return empty_series, empty_series, empty_series

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
    try:
        # 데이터프레임 복사본 생성
        df_ichimoku = df.copy()
        
        # 전환선(Conversion Line) = (최고가 + 최저가) / 2 (conversion_period 기간)
        df_ichimoku['high_conversion'] = df_ichimoku['high'].rolling(window=conversion_period).max()
        df_ichimoku['low_conversion'] = df_ichimoku['low'].rolling(window=conversion_period).min()
        df_ichimoku['conversion_line'] = (df_ichimoku['high_conversion'] + df_ichimoku['low_conversion']) / 2
        
        # 기준선(Base Line) = (최고가 + 최저가) / 2 (base_period 기간)
        df_ichimoku['high_base'] = df_ichimoku['high'].rolling(window=base_period).max()
        df_ichimoku['low_base'] = df_ichimoku['low'].rolling(window=base_period).min()
        df_ichimoku['base_line'] = (df_ichimoku['high_base'] + df_ichimoku['low_base']) / 2
        
        # 선행스팬1(Leading Span A) = (전환선 + 기준선) / 2
        # displacement 기간만큼 미래로 이동
        df_ichimoku['span_a_without_shift'] = (df_ichimoku['conversion_line'] + df_ichimoku['base_line']) / 2
        df_ichimoku['leading_span_a'] = df_ichimoku['span_a_without_shift'].shift(displacement)
        
        # 선행스팬2(Leading Span B) = (최고가 + 최저가) / 2 (lagging_span2_period 기간)
        # displacement 기간만큼 미래로 이동
        df_ichimoku['high_lagging'] = df_ichimoku['high'].rolling(window=lagging_span2_period).max()
        df_ichimoku['low_lagging'] = df_ichimoku['low'].rolling(window=lagging_span2_period).min()
        df_ichimoku['span_b_without_shift'] = (df_ichimoku['high_lagging'] + df_ichimoku['low_lagging']) / 2
        df_ichimoku['leading_span_b'] = df_ichimoku['span_b_without_shift'].shift(displacement)
        
        # 후행스팬(Lagging Span) = 현재 종가를 displacement 기간만큼 과거로 이동
        df_ichimoku['lagging_span'] = df_ichimoku['close'].shift(-displacement)
        
        # NaN 및 무한값 처리
        df_ichimoku = df_ichimoku.replace([np.inf, -np.inf], np.nan)
        
        return df_ichimoku['conversion_line'], df_ichimoku['base_line'], df_ichimoku['leading_span_a'], df_ichimoku['leading_span_b'], df_ichimoku['lagging_span']
        
    except Exception as e:
        logger.error(f"일목균형표 계산 오류: {e}")
        # 빈 시리즈 반환
        empty_series = pd.Series(np.nan, index=df.index)
        return empty_series, empty_series, empty_series, empty_series, empty_series

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
