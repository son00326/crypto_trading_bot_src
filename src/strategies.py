"""
거래 전략 모듈 - 암호화폐 자동매매 봇

이 모듈은 다양한 거래 전략을 구현합니다.
이동평균 교차, RSI 기반, MACD 기반, 볼린저 밴드 등 여러 전략을 제공합니다.
"""

import pandas as pd
import numpy as np
import logging
from indicators import (
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
    
    def calculate_positions(self, df):
        """
        포지션 계산
        
        Args:
            df (DataFrame): 거래 신호가 포함된 데이터프레임
        
        Returns:
            DataFrame: 포지션이 추가된 데이터프레임
        """
        if 'signal' not in df.columns:
            df = self.generate_signals(df)
        
        # 포지션 계산 (1: 롱, -1: 숏, 0: 포지션 없음)
        df['position'] = df['signal'].diff()
        
        return df

class MovingAverageCrossover(Strategy):
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
        
        # 신호 생성 (1: 매수, 0: 홀드, -1: 매도)
        df['signal'] = 0
        
        # 골든 크로스 (단기 > 장기): 매수 신호
        df.loc[df['short_ma'] > df['long_ma'], 'signal'] = 1
        
        # 데드 크로스 (단기 < 장기): 매도 신호
        df.loc[df['short_ma'] < df['long_ma'], 'signal'] = -1
        
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
        # 데이터프레임 복사
        df = df.copy()
        
        # RSI 계산
        df['rsi'] = relative_strength_index(df, period=self.period)
        
        # 신호 생성 (1: 매수, 0: 홀드, -1: 매도)
        df['signal'] = 0
        
        # 과매도 상태에서 회복 시 매수 신호
        df.loc[df['rsi'] < self.oversold, 'signal'] = 1
        
        # 과매수 상태에서 하락 시 매도 신호
        df.loc[df['rsi'] > self.overbought, 'signal'] = -1
        
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
        
        # 신호 생성 (1: 매수, 0: 홀드, -1: 매도)
        df['signal'] = 0
        
        # MACD가 시그널 라인을 상향 돌파: 매수 신호
        df.loc[(df['macd'] > df['signal_line']) & (df['macd'].shift(1) <= df['signal_line'].shift(1)), 'signal'] = 1
        
        # MACD가 시그널 라인을 하향 돌파: 매도 신호
        df.loc[(df['macd'] < df['signal_line']) & (df['macd'].shift(1) >= df['signal_line'].shift(1)), 'signal'] = -1
        
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
        
        # 신호 생성 (1: 매수, 0: 홀드, -1: 매도)
        df['signal'] = 0
        
        # 가격이 하단 밴드 아래로 내려갔다가 다시 상승: 매수 신호
        df.loc[(df['close'] < df['lower_band'].shift(1)) & (df['close'] > df['close'].shift(1)), 'signal'] = 1
        
        # 가격이 상단 밴드 위로 올라갔다가 다시 하락: 매도 신호
        df.loc[(df['close'] > df['upper_band'].shift(1)) & (df['close'] < df['close'].shift(1)), 'signal'] = -1
        
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
    
    def generate_signals(self, df):
        """
        스토캐스틱 오실레이터 기반 거래 신호 생성
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            DataFrame: 거래 신호가 추가된 데이터프레임
        """
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
        
        # 신호 생성 (1: 매수, 0: 홀드, -1: 매도)
        df['signal'] = 0
        
        # %K가 %D를 상향 돌파하고 둘 다 과매도 영역에 있을 때: 매수 신호
        df.loc[(df['stoch_k'] > df['stoch_d']) & 
               (df['stoch_k'].shift(1) <= df['stoch_d'].shift(1)) & 
               (df['stoch_k'] < self.oversold), 'signal'] = 1
        
        # %K가 %D를 하향 돌파하고 둘 다 과매수 영역에 있을 때: 매도 신호
        df.loc[(df['stoch_k'] < df['stoch_d']) & 
               (df['stoch_k'].shift(1) >= df['stoch_d'].shift(1)) & 
               (df['stoch_k'] > self.overbought), 'signal'] = -1
        
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
        
        # 최종 신호 생성 (1: 매수, 0: 홀드, -1: 매도)
        df['signal'] = 0
        df.loc[df['combined_signal'] > 0.3, 'signal'] = 1
        df.loc[df['combined_signal'] < -0.3, 'signal'] = -1
        
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
        
        # 신호 생성 (1: 매수, 0: 홀드, -1: 매도)
        df['signal'] = 0
        
        # 저항 레벨 돌파: 매수 신호
        df.loc[df['close'] > df['resistance'].shift(1), 'signal'] = 1
        
        # 지지 레벨 하향 돌파: 매도 신호
        df.loc[df['close'] < df['support'].shift(1), 'signal'] = -1
        
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
        
        # 신호 생성 (1: 매수, 0: 홀드, -1: 매도)
        df['signal'] = 0
        
        # 가격이 목표가를 돌파하면 매수 신호
        df.loc[df['high'] > df['target'], 'signal'] = 1
        
        # 다음 날 시가에 청산
        df['signal'] = df['signal'].shift(1)
        df.loc[df['signal'] == 1, 'signal'] = -1
        
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
