import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import logging

logger = logging.getLogger('crypto_bot')

def convert_series_to_df_column(func):
    def wrapper(df, *args, **kwargs):
        try:
            # 원본 데이터프레임 복사
            df_copy = df.copy()
            
            # 원래 함수 호출
            result = func(df_copy, *args, **kwargs)
            
            # 결과가 튜플인 경우(여러 시리즈를 반환하는 함수)
            if isinstance(result, tuple):
                return result
            
            # Series 결과를 DataFrame 컬럼으로 변환
            if isinstance(result, pd.Series):
                return result
                
            return result
        except Exception as e:
            logger.error(f'{func.__name__} 함수 오류: {e}')
            if isinstance(result, tuple):
                return tuple(pd.Series(np.nan, index=df.index) for _ in range(len(result)))
            return pd.Series(np.nan, index=df.index)
    return wrapper

# 안전한 다차원 인덱싱을 위한 유틸리티 함수
def safe_indexing(df, column):
    try:
        return df[column].copy()
    except Exception as e:
        logger.error(f'컬럼 접근 오류: {e}')
        return pd.Series(np.nan, index=df.index)

# 이제 이 데코레이터를 모든 지표 함수에 적용할 수 있습니다
