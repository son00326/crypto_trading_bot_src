"""
거래 전략 모듈 - 암호화폐 자동매매 봇

이 모듈은 다양한 거래 전략을 구현합니다.
이동평균 교차, RSI 기반, MACD 기반, 볼린저 밴드 등 여러 전략을 제공합니다.
"""

import pandas as pd
import numpy as np
import logging
from src.indicators import (
    simple_moving_average, exponential_moving_average, 
    moving_average_convergence_divergence, relative_strength_index,
    bollinger_bands, stochastic_oscillator
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('strategies')

class Strategy:
    """거래 전략의 기본 클래스"""
    
    def __init__(self, name="BaseStrategy"):
        """
        전략 초기화
        
        Args:
            name (str): 전략 이름
        """
        self.name = name
        logger.info(f"{self.name} 전략이 초기화되었습니다.")
    
    def generate_signals(self, df):
        """
        거래 신호 생성 (자식 클래스에서 구현)
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            DataFrame: 거래 신호가 추가된 데이터프레임
        """
        raise NotImplementedError("자식 클래스에서 구현해야 합니다.")
    
class MovingAverageCrossover(Strategy):
    def calculate_positions(self, df):
        """
        포지션 계산
        
        Args:
            df (DataFrame): 거래 신호가 포함된 데이터프레임
        
        Returns:
            DataFrame: 포지션이 추가된 데이터프레임
        """
        try:
            if 'signal' not in df.columns:
                df = self.generate_signals(df)
            
            # NumPy 배열로 변환하여 포지션 계산 (다차원 인덱싱 방지)
            signal_values = df['signal'].values
            position_values = np.zeros_like(signal_values)
            
            # diff 연산을 수동으로 처리: 현재 값에서 이전 값을 빼기
            if len(signal_values) > 1:
                position_values[1:] = signal_values[1:] - signal_values[:-1]
            
            # 결과를 데이터프레임에 할당
            df['position'] = position_values
            
            return df
        except Exception as e:
            logger.error(f"포지션 계산 중 오류 발생: {e}")
            df['position'] = 0
            return df
    """이동평균 교차 전략"""
    
    def __init__(self, short_period=9, long_period=26, ma_type='sma'):
        """
        이동평균 교차 전략 초기화
        
        Args:
            short_period (int): 단기 이동평균 기간
            long_period (int): 장기 이동평균 기간
            ma_type (str): 이동평균 유형 ('sma' 또는 'ema')
        """
        super().__init__(name=f"MA_Crossover_{short_period}_{long_period}_{ma_type}")
        self.short_period = short_period
        self.long_period = long_period
        self.ma_type = ma_type
    
    def generate_signals(self, df):
        """
        이동평균 교차 기반 거래 신호 생성
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            DataFrame: 거래 신호가 추가된 데이터프레임
        """
        try:
            # 데이터프레임 복사
            df = df.copy()
            
            # 이동평균 계산
            if self.ma_type.lower() == 'sma':
                df['short_ma'] = simple_moving_average(df, period=self.short_period)
                df['long_ma'] = simple_moving_average(df, period=self.long_period)
            elif self.ma_type.lower() == 'ema':
                df['short_ma'] = exponential_moving_average(df, period=self.short_period)
                df['long_ma'] = exponential_moving_average(df, period=self.long_period)
            else:
                raise ValueError(f"지원하지 않는 이동평균 유형입니다: {self.ma_type}")
            
            # NumPy 배열로 변환하여 신호 생성 (다차원 인덱싱 방지)
            short_ma_values = df['short_ma'].values
            long_ma_values = df['long_ma'].values
            
            # np.where를 사용한 벡터화된 조건부 할당
            signals = np.zeros(len(df))
            signals = np.where(short_ma_values > long_ma_values, 1, 
                              np.where(short_ma_values < long_ma_values, -1, 0))
            
            # 결과를 데이터프레임에 할당
            df['signal'] = signals
            
            return df
        except Exception as e:
            logger.error(f"이동평균 교차 신호 생성 중 오류 발생: {e}")
            df['signal'] = 0
            return df

class RSIStrategy(Strategy):
    """RSI 기반 전략"""
    
    def __init__(self, period=14, overbought=70, oversold=30):
        """
        RSI 전략 초기화
        
        Args:
            period (int): RSI 계산 기간
            overbought (int): 과매수 기준값
            oversold (int): 과매도 기준값
        """
        super().__init__(name=f"RSI_{period}_{overbought}_{oversold}")
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
    
    def generate_signals(self, df):
        """
        RSI 기반 거래 신호 생성
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            DataFrame: 거래 신호가 추가된 데이터프레임
        """
        try:
            # 데이터프레임 복사
            df = df.copy()
            
            # RSI 계산
            df['rsi'] = relative_strength_index(df, period=self.period)
            
            # NumPy 배열로 변환하여 신호 생성 (다차원 인덱싱 방지)
            rsi_values = df['rsi'].values
            
            # np.where를 사용한 벡터화된 조건부 할당
            signals = np.zeros(len(df))
            signals = np.where(rsi_values < self.oversold, 1, 
                             np.where(rsi_values > self.overbought, -1, 0))
            
            # 결과를 데이터프레임에 할당
            df['signal'] = signals
            
            return df
        except Exception as e:
            logger.error(f"RSI 신호 생성 중 오류 발생: {e}")
            df['signal'] = 0
            return df

class MACDStrategy(Strategy):
    """MACD 기반 전략"""
    
    def __init__(self, fast_period=12, slow_period=26, signal_period=9):
        """
        MACD 전략 초기화
        
        Args:
            fast_period (int): 빠른 EMA 기간
            slow_period (int): 느린 EMA 기간
            signal_period (int): 시그널 기간
        """
        super().__init__(name=f"MACD_{fast_period}_{slow_period}_{signal_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
    
    def generate_signals(self, df):
        """
        MACD 기반 거래 신호 생성
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            DataFrame: 거래 신호가 추가된 데이터프레임
        """
        try:
            # 데이터프레임 복사
            df = df.copy()
            
            # MACD 계산
            macd_line, signal_line, histogram = moving_average_convergence_divergence(
                df, 
                fast_period=self.fast_period, 
                slow_period=self.slow_period, 
                signal_period=self.signal_period
            )
            
            df['macd'] = macd_line
            df['signal_line'] = signal_line
            df['histogram'] = histogram
            
            # NumPy 배열로 변환하여 신호 생성 (다차원 인덱싱 방지)
            macd_values = df['macd'].values
            signal_values = df['signal_line'].values
            
            # 이전 값을 사용하기 위해 시프트된 배열 생성
            macd_prev = np.roll(macd_values, 1)
            macd_prev[0] = np.nan  # 첫 번째 값은 유효하지 않음
            
            signal_prev = np.roll(signal_values, 1)
            signal_prev[0] = np.nan
            
            # 신호 생성을 위한 조건 배열
            buy_condition = (macd_values > signal_values) & (macd_prev <= signal_prev)
            sell_condition = (macd_values < signal_values) & (macd_prev >= signal_prev)
            
            # 신호 생성 (다차원 인덱싱 방지)
            signals = np.zeros(len(df))
            signals = np.where(buy_condition, 1, np.where(sell_condition, -1, 0))
            
            # NaN 처리
            signals[0] = 0  # 첫 번째 값은 0으로 설정
            
            # 결과를 데이터프레임에 할당
            df['signal'] = signals
            
            return df
        except Exception as e:
            logger.error(f"MACD 신호 생성 중 오류 발생: {e}")
            df['signal'] = 0
            return df

class BollingerBandsStrategy(Strategy):
    """볼린저 밴드 기반 전략"""
    
    def __init__(self, period=20, std_dev=2):
        """
        볼린저 밴드 전략 초기화
        
        Args:
            period (int): 이동평균 기간
            std_dev (float): 표준편차 배수
        """
        super().__init__(name=f"BollingerBands_{period}_{std_dev}")
        self.period = period
        self.std_dev = std_dev
    
    def generate_signals(self, df):
        """
        볼린저 밴드 기반 거래 신호 생성
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            DataFrame: 거래 신호가 추가된 데이터프레임
        """
        try:
            # 데이터프레임 복사
            df = df.copy()
            
            # 볼린저 밴드 계산
            middle_band, upper_band, lower_band = bollinger_bands(
                df, 
                period=self.period, 
                std_dev=self.std_dev
            )
            
            df['middle_band'] = middle_band
            df['upper_band'] = upper_band
            df['lower_band'] = lower_band
            
            # NumPy 배열로 변환하여 신호 생성 (다차원 인덱싱 방지)
            close_values = df['close'].values
            lower_band_values = df['lower_band'].values
            upper_band_values = df['upper_band'].values
            
            # 이전 값을 사용하기 위해 시프트된 배열 생성
            close_prev = np.roll(close_values, 1)
            close_prev[0] = np.nan
            
            lower_band_prev = np.roll(lower_band_values, 1)
            lower_band_prev[0] = np.nan
            
            upper_band_prev = np.roll(upper_band_values, 1)
            upper_band_prev[0] = np.nan
            
            # 신호 생성을 위한 조건 배열
            buy_condition = (close_values < lower_band_prev) & (close_values > close_prev)
            sell_condition = (close_values > upper_band_prev) & (close_values < close_prev)
            
            # 신호 생성 (다차원 인덱싱 방지)
            signals = np.zeros(len(df))
            signals = np.where(buy_condition, 1, np.where(sell_condition, -1, 0))
            
            # NaN 처리
            signals[0] = 0  # 첫 번째 값은 0으로 설정
            np.nan_to_num(signals, copy=False, nan=0)
            
            # 결과를 데이터프레임에 할당
            df['signal'] = signals
            
            return df
        except Exception as e:
            logger.error(f"볼린저 밴드 신호 생성 중 오류 발생: {e}")
            df['signal'] = 0
            return df

class StochasticStrategy(Strategy):
    """스토캐스틱 오실레이터 기반 전략"""
    
    def __init__(self, k_period=14, d_period=3, slowing=3, overbought=80, oversold=20):
        """
        스토캐스틱 전략 초기화
        
        Args:
            k_period (int): %K 기간
            d_period (int): %D 기간
            slowing (int): 슬로잉 기간
            overbought (int): 과매수 기준값
            oversold (int): 과매도 기준값
        """
        super().__init__(name=f"Stochastic_{k_period}_{d_period}_{slowing}")
        self.k_period = k_period
        self.d_period = d_period
        self.slowing = slowing
        self.overbought = overbought
        self.oversold = oversold
        
    def calculate_positions(self, df):
        """
        포지션 계산
        
        Args:
            df (DataFrame): 거래 신호가 포함된 데이터프레임
        
        Returns:
            DataFrame: 포지션이 추가된 데이터프레임
        """
        try:
            if 'signal' not in df.columns:
                df = self.generate_signals(df)
            
            # NumPy 배열로 변환하여 포지션 계산 (다차원 인덱싱 방지)
            signal_values = df['signal'].values
            position_values = np.zeros_like(signal_values)
            
            # diff 연산을 수동으로 처리: 현재 값에서 이전 값을 빼기
            if len(signal_values) > 1:
                position_values[1:] = signal_values[1:] - signal_values[:-1]
            
            # 결과를 데이터프레임에 할당
            df['position'] = position_values
            
            return df
        except Exception as e:
            logger.error(f"포지션 계산 중 오류 발생: {e}")
            df['position'] = 0
            return df
    def generate_signals(self, df):
        """
        스토캐스틱 오실레이터 기반 거래 신호 생성
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            DataFrame: 거래 신호가 추가된 데이터프레임
        """
        try:
            # 데이터프레임 복사
            df = df.copy()
            
            # 스토캐스틱 오실레이터 계산
            k, d = stochastic_oscillator(
                df, 
                k_period=self.k_period, 
                d_period=self.d_period, 
                slowing=self.slowing
            )
            
            df['stoch_k'] = k
            df['stoch_d'] = d
            
            # NumPy 배열로 변환하여 신호 생성 (다차원 인덱싱 방지)
            k_values = df['stoch_k'].values
            d_values = df['stoch_d'].values
            
            # 이전 값을 사용하기 위해 시프트된 배열 생성
            k_prev = np.roll(k_values, 1)
            k_prev[0] = np.nan
            
            d_prev = np.roll(d_values, 1)
            d_prev[0] = np.nan
            
            # 신호 생성을 위한 조건 배열
            buy_condition = (k_values > d_values) & \
                           (k_prev <= d_prev) & \
                           (k_values < self.oversold)
                           
            sell_condition = (k_values < d_values) & \
                            (k_prev >= d_prev) & \
                            (k_values > self.overbought)
            
            # 신호 생성 (다차원 인덱싱 방지)
            signals = np.zeros(len(df))
            signals = np.where(buy_condition, 1, np.where(sell_condition, -1, 0))
            
            # NaN 처리
            signals[0] = 0  # 첫 번째 값은 0으로 설정
            np.nan_to_num(signals, copy=False, nan=0)
            
            # 결과를 데이터프레임에 할당
            df['signal'] = signals
            
            return df
        except Exception as e:
            logger.error(f"스토캐스틱 신호 생성 중 오류 발생: {e}")
            df['signal'] = 0
            return df
        return df

class CombinedStrategy(Strategy):
    """여러 전략을 결합한 복합 전략"""
    
    def __init__(self, strategies, weights=None):
        """
        복합 전략 초기화
        
        Args:
            strategies (list): 전략 객체 리스트
            weights (list, optional): 각 전략의 가중치. None인 경우 동일 가중치 적용
        """
        strategy_names = [s.name for s in strategies]
        super().__init__(name=f"Combined_{'_'.join(strategy_names)}")
        
        self.strategies = strategies
        
        if weights is None:
            self.weights = [1/len(strategies)] * len(strategies)
        else:
            if len(weights) != len(strategies):
                raise ValueError("전략 수와 가중치 수가 일치해야 합니다.")
            self.weights = weights
    
    def generate_signals(self, df):
        """
        여러 전략의 신호를 결합하여 거래 신호 생성
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            DataFrame: 거래 신호가 추가된 데이터프레임
        """
        # 데이터프레임 복사
        df = df.copy()
        
        # 각 전략의 신호 계산
        signals = []
        for i, strategy in enumerate(self.strategies):
            strategy_df = strategy.generate_signals(df)
            signals.append(strategy_df['signal'] * self.weights[i])
        
        # 신호 결합
        df['combined_signal'] = pd.concat(signals, axis=1).sum(axis=1)
        
        # 최종 신호 생성 (1: 매수, 0: 홀드, -1: 매도) - NumPy 배열 기반으로 변환
        
        # 필요한 값들을 NumPy 배열로 변환
        combined_signal_values = df['combined_signal'].values
        
        # np.where를 사용한 벡터화된 조건부 할당
        signals = np.zeros(len(df))
        signals = np.where(combined_signal_values > 0.3, 1, signals)  # 매수 신호
        signals = np.where(combined_signal_values < -0.3, -1, signals)  # 매도 신호
        
        # NaN 처리
        np.nan_to_num(signals, copy=False, nan=0)
        
        # 결과를 데이터프레임에 할당
        df['signal'] = signals
        
        return df

class BreakoutStrategy(Strategy):
    """돌파 전략"""
    
    def __init__(self, period=20):
        """
        돌파 전략 초기화
        
        Args:
            period (int): 저항/지지 레벨 계산 기간
        """
        super().__init__(name=f"Breakout_{period}")
        self.period = period
    
    def generate_signals(self, df):
        """
        돌파 기반 거래 신호 생성
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            DataFrame: 거래 신호가 추가된 데이터프레임
        """
        # 데이터프레임 복사
        df = df.copy()
        
        # 저항/지지 레벨 계산
        df['resistance'] = df['high'].rolling(window=self.period).max()
        df['support'] = df['low'].rolling(window=self.period).min()
        
        # 신호 생성 (1: 매수, 0: 홀드, -1: 매도) - NumPy 배열 기반으로 변환
        
        # 필요한 값들을 NumPy 배열로 변환
        close_values = df['close'].values
        resistance_values = df['resistance'].shift(1).values
        support_values = df['support'].shift(1).values
        
        # np.where를 사용한 벡터화된 조건부 할당
        signals = np.zeros(len(df))
        signals = np.where(close_values > resistance_values, 1, signals)  # 저항 레벨 돌파: 매수
        signals = np.where(close_values < support_values, -1, signals)   # 지지 레벨 하향 돌파: 매도
        
        # NaN 처리
        np.nan_to_num(signals, copy=False, nan=0)
        
        # 결과를 데이터프레임에 할당
        df['signal'] = signals
        
        return df

class VolatilityBreakoutStrategy(Strategy):
    """변동성 돌파 전략 (Larry Williams의 변동성 돌파)"""
    
    def __init__(self, period=1, k=0.5):
        """
        변동성 돌파 전략 초기화
        
        Args:
            period (int): 변동성 계산 기간
            k (float): 변동성 계수 (0~1)
        """
        super().__init__(name=f"VolatilityBreakout_{period}_{k}")
        self.period = period
        self.k = k
    
    def generate_signals(self, df):
        """
        변동성 돌파 기반 거래 신호 생성
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            DataFrame: 거래 신호가 추가된 데이터프레임
        """
        # 데이터프레임 복사
        df = df.copy()
        
        # 전일 변동성 계산 (고가 - 저가)
        df['volatility'] = df['high'].shift(1) - df['low'].shift(1)
        
        # 목표가 계산 (시가 + 변동성 * k)
        df['target'] = df['open'] + df['volatility'] * self.k
        
        # 신호 생성 (1: 매수, 0: 홀드, -1: 매도) - NumPy 배열 기반으로 변환
        
        # 필요한 값들을 NumPy 배열로 변환
        high_values = df['high'].values
        target_values = df['target'].values
        
        # 가격이 목표가를 돌파하면 매수 신호
        signals = np.zeros(len(df))
        signals = np.where(high_values > target_values, 1, 0)
        
        # 다음 날 시가에 청산 (시프트 처리)
        shifted_signals = np.zeros_like(signals)
        if len(signals) > 1:
            shifted_signals[1:] = signals[:-1]
        
        # 매수 신호가 있던 날 다음 날에는 매도(-1)
        final_signals = np.where(shifted_signals == 1, -1, 0)
        
        # NaN 처리
        np.nan_to_num(final_signals, copy=False, nan=0)
        
        # 결과를 데이터프레임에 할당
        df['signal'] = final_signals
        
        return df

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
    
    # 각 전략 테스트
    strategies = [
        MovingAverageCrossover(short_period=9, long_period=26),
        RSIStrategy(period=14, overbought=70, oversold=30),
        MACDStrategy(),
        BollingerBandsStrategy(),
        StochasticStrategy(),
        BreakoutStrategy(),
        VolatilityBreakoutStrategy()
    ]
    
    for strategy in strategies:
        result_df = strategy.generate_signals(df)
        result_df = strategy.calculate_positions(result_df)
        
        print(f"\n{strategy.name} 전략 테스트 결과:")
        print(f"매수 신호 수: {len(result_df[result_df['signal'] == 1])}")
        print(f"매도 신호 수: {len(result_df[result_df['signal'] == -1])}")
        print(f"포지션 변경 수: {len(result_df[result_df['position'] != 0])}")
    
    # 복합 전략 테스트
    combined = CombinedStrategy([
        MovingAverageCrossover(short_period=9, long_period=26),
        RSIStrategy(period=14, overbought=70, oversold=30),
        MACDStrategy()
    ])
    
    result_df = combined.generate_signals(df)
    result_df = combined.calculate_positions(result_df)
    
    print(f"\n{combined.name} 전략 테스트 결과:")
    print(f"매수 신호 수: {len(result_df[result_df['signal'] == 1])}")
    print(f"매도 신호 수: {len(result_df[result_df['signal'] == -1])}")
    print(f"포지션 변경 수: {len(result_df[result_df['position'] != 0])}")
