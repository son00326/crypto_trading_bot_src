# 단순 이동평균(SMA)과 지수 이동평균(EMA) 함수
# 이 함수들은 indicators.py 파일에 있는 함수를 수정하여 다차원 인덱싱 문제를 해결합니다

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
        df_sma = df.copy()
        df_sma['sma'] = df_sma[column].rolling(window=period).mean()
        return df_sma['sma']
    except Exception as e:
        logger.error(f"SMA 계산 오류: {e}")
        return pd.Series(np.nan, index=df.index)

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
        df_ema = df.copy()
        df_ema['ema'] = df_ema[column].ewm(span=period, adjust=False).mean()
        return df_ema['ema']
    except Exception as e:
        logger.error(f"EMA 계산 오류: {e}")
        return pd.Series(np.nan, index=df.index)
