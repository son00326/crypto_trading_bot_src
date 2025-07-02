"""
거래 전략 모듈 - 암호화폐 자동매매 봇

이 모듈은 다양한 거래 전략을 구현합니다.
이동평균 교차, RSI 기반, MACD 기반, 볼린저 밴드 등 여러 전략을 제공합니다.
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime
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
        # 기본 데이터 포인트 요구사항 설정 (30개를 기본값으로 설정)
        self.required_data_points = 30
        logger.info(f"{self.name} 전략이 초기화되었습니다.")
        
    def validate_parameters(self, params):
        """
        전략 파라미터 유효성 검사
        
        Args:
            params (dict): 검사할 파라미터 딩크셔너리
            
        Returns:
            tuple: (bool, str) - 유효성 여부와 오류 메시지(있는 경우)
        """
        # 기본 구현은 항상 True 반환 - 자식 클래스에서 재정의
        return True, ""
    
    @staticmethod
    def validate_numeric_parameter(name, value, min_value=None, max_value=None, allow_none=False):
        """
        숫자 파라미터 값 검증
        
        Args:
            name (str): 파라미터 이름
            value: 검증할 값
            min_value: 최소값 (선택적)
            max_value: 최대값 (선택적)
            allow_none (bool): None 값 허용 여부
            
        Returns:
            tuple: (bool, str) - 유효성 여부와 오류 메시지(있는 경우)
        """
        if value is None:
            if allow_none:
                return True, ""
            return False, f"{name} 파라미터는 None이 될 수 없습니다."
        
        try:
            # 숫자로 변환 시도
            num_value = float(value)
            
            # 최소값 검사
            if min_value is not None and num_value < min_value:
                return False, f"{name} 파라미터는 {min_value} 이상이어야 합니다. 현재 값: {value}"
                
            # 최대값 검사
            if max_value is not None and num_value > max_value:
                return False, f"{name} 파라미터는 {max_value} 이하여야 합니다. 현재 값: {value}"
                
            return True, ""
            
        except (ValueError, TypeError):
            return False, f"{name} 파라미터는 숫자여야 합니다. 현재 값: {value}"
    
    def generate_signals(self, df):
        """
        거래 신호 생성 (자식 클래스에서 구현)
        
        Args:
            df (DataFrame): OHLCV 데이터
        
        Returns:
            DataFrame: 거래 신호가 추가된 데이터프레임
        """
        raise NotImplementedError("자식 클래스에서 구현해야 합니다.")
    
    def generate_signal(self, market_data, current_price, portfolio=None):
        """
        현재 데이터에 기반해 거래 신호를 생성
        
        Args:
            market_data (DataFrame): OHLCV 데이터
            current_price (float): 현재 가격
            portfolio (dict): 포트폴리오 정보
            
        Returns:
            TradeSignal: 거래 신호 객체 또는 None
        """
        try:
            logger.info(f"[{self.name}] 신호 생성 시작 - 현재가: {current_price}")
            logger.debug(f"[{self.name}] 시장 데이터 크기: {len(market_data) if market_data is not None else 0}")
            
            # OHLCV 데이터에 신호 추가
            df_with_signals = self.generate_signals(market_data)
            logger.debug(f"[{self.name}] generate_signals 완료, 결과 데이터 크기: {len(df_with_signals)}")
            
            # 마지막 신호 가져오기
            last_signal = df_with_signals['signal'].iloc[-1] if len(df_with_signals) > 0 else 0
            last_position = df_with_signals['position'].iloc[-1] if 'position' in df_with_signals.columns and len(df_with_signals) > 0 else 0
            
            logger.info(f"[{self.name}] 마지막 신호: {last_signal}, 마지막 포지션: {last_position}")
            
            # 신호가 없으면 None 반환
            if last_position == 0:
                logger.info(f"[{self.name}] 포지션이 0이므로 거래 신호 없음 (HOLD)")
                return None
                
            # 포지션 변화가 있으면 신호 생성
            direction = 'buy' if last_position > 0 else 'sell' if last_position < 0 else None
            
            if direction:
                from src.models import TradeSignal
                confidence = abs(last_signal) if -1 <= last_signal <= 1 else 0.5
                
                logger.info(f"[{self.name}] 거래 신호 생성: {direction}, 신뢰도: {confidence:.2f}")
                
                return TradeSignal(
                    direction=direction,
                    symbol=market_data['symbol'].iloc[0] if 'symbol' in market_data.columns else None,
                    price=current_price,
                    confidence=confidence,
                    strength=confidence,  # strength를 confidence와 동일하게 설정
                    timestamp=datetime.now(),
                    strategy_name=self.name,
                )
            
            logger.info(f"[{self.name}] 방향이 없으므로 거래 신호 없음")
            return None
            
        except Exception as e:
            logger.error(f"[{self.name}] 신호 생성 중 오류 발생: {e}")
            logger.exception(f"[{self.name}] 상세 오류:")
            return None
    
class MovingAverageCrossover(Strategy):
    """이동평균 교차 전략"""
    
    def __init__(self, short_period=9, long_period=26, ma_type='sma', stop_loss_pct=4.0, take_profit_pct=8.0):
        """
        이동평균 교차 전략 초기화
        
        Args:
            short_period (int): 단기 이동평균 기간
            long_period (int): 장기 이동평균 기간
            ma_type (str): 이동평균 유형 ('sma' 또는 'ema')
            stop_loss_pct (float): 손절가 비율(%)
            take_profit_pct (float): 이익실현 비율(%)
        """
        # 파라미터 유효성 검사
        valid, message = self.validate_parameters({
            'short_period': short_period,
            'long_period': long_period,
            'ma_type': ma_type
        })
        
        if not valid:
            logger.warning(f"이동평균 교차 전략 파라미터 오류: {message}. 기본값을 사용합니다.")
            short_period = 9
            long_period = 26
            ma_type = 'ema'
            
        super().__init__(name=f"MA_Crossover_{short_period}_{long_period}_{ma_type}")
        self.short_period = short_period
        self.long_period = long_period
        self.ma_type = ma_type
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        
        # 데이터 포인트 요구사항 설정 (장기 이동평균 기간의 3배로 설정하여 충분한 데이터 확보)
        self.required_data_points = self.long_period * 3
        
    def generate_signal(self, market_data, current_price, portfolio=None):
        """
        현재 데이터에 기반해 거래 신호를 생성
        
        Args:
            market_data (DataFrame): OHLCV 데이터
            current_price (float): 현재 가격
            portfolio (dict): 포트폴리오 정보
            
        Returns:
            TradeSignal: 거래 신호 객체 또는 None
        """
        try:
            # OHLCV 데이터에 신호 추가
            df_with_signals = self.generate_signals(market_data)
            
            # 마지막 신호 가져오기
            last_signal = df_with_signals['signal'].iloc[-1] if len(df_with_signals) > 0 else 0
            last_position = df_with_signals['position'].iloc[-1] if 'position' in df_with_signals.columns and len(df_with_signals) > 0 else 0
            
            # 신호가 없으면 None 반환
            if last_position == 0:
                return None
                
            # 포지션 변화가 있으면 신호 생성
            direction = 'buy' if last_position > 0 else 'sell' if last_position < 0 else None
            
            if direction:
                from src.models import TradeSignal
                confidence = abs(last_signal) if -1 <= last_signal <= 1 else 0.5
                
                return TradeSignal(
                    direction=direction,
                    symbol=market_data['symbol'].iloc[0] if 'symbol' in market_data.columns else None,
                    price=current_price,
                    confidence=confidence,
                    timestamp=datetime.now(),
                    strategy_name=self.name,
                )
            
            return None
            
        except Exception as e:
            logger.error(f"신호 생성 중 오류 발생: {e}")
            return None
    
    def validate_parameters(self, params):
        """
        이동평균 교차 전략 파라미터 유효성 검사
        
        Args:
            params (dict): 검사할 파라미터 딩크셔너리
            
        Returns:
            tuple: (bool, str) - 유효성 여부와 오류 메시지(있는 경우)
        """
        # 단기 이동평균 기간 검사
        short_period = params.get('short_period')
        valid, message = self.validate_numeric_parameter('short_period', short_period, 
                                                       min_value=2, max_value=50)
        if not valid:
            return False, message
        
        # 장기 이동평균 기간 검사
        long_period = params.get('long_period')
        valid, message = self.validate_numeric_parameter('long_period', long_period, 
                                                     min_value=5, max_value=200)
        if not valid:
            return False, message
            
        # 장/단기 이동평균 비교
        if short_period >= long_period:
            return False, f"단기 기간({short_period})은 장기 기간({long_period})보다 작아야 합니다."
            
        # 이동평균 유형 검사
        ma_type = params.get('ma_type')
        if ma_type not in ['sma', 'ema']:
            return False, f"지원되지 않는 이동평균 유형: {ma_type}. 'sma' 또는 'ema'만 지원합니다."

        # 손절가 검사
        stop_loss_pct = params.get('stop_loss_pct')
        valid, message = self.validate_numeric_parameter('stop_loss_pct', stop_loss_pct, 
                                                      min_value=0.5, max_value=20)
        if not valid:
            return False, message
            
        # 이익실현가 검사
        take_profit_pct = params.get('take_profit_pct')
        valid, message = self.validate_numeric_parameter('take_profit_pct', take_profit_pct, 
                                                       min_value=1, max_value=50)
        if not valid:
            return False, message
            
        # 이익실현가와 손절가 비교
        if take_profit_pct <= stop_loss_pct:
            return False, f"이익실현 비율({take_profit_pct})은 손절 비율({stop_loss_pct})보다 커야 합니다."
            
        return True, ""
    
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
            
            # NaN 처리
            np.nan_to_num(signals, copy=False, nan=0)
            
            # 결과를 데이터프레임에 할당
            df['signal'] = signals
            
            # position 계산 (signal의 변화량)
            position_values = np.zeros_like(signals)
            if len(signals) > 1:
                position_values[1:] = signals[1:] - signals[:-1]
            
            df['position'] = position_values
            
            return df
        except Exception as e:
            logger.error(f"이동평균 교차 신호 생성 중 오류 발생: {e}")
            df['signal'] = 0
            df['position'] = 0
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
        # 파라미터 유효성 검사
        valid, message = self.validate_parameters({
            'period': period,
            'overbought': overbought,
            'oversold': oversold
        })
        
        if not valid:
            logger.warning(f"RSI 전략 파라미터 오류: {message}. 기본값을 사용합니다.")
            period = 14
            overbought = 70
            oversold = 30
            
        super().__init__(name=f"RSI_{period}_{overbought}_{oversold}")
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        
    def validate_parameters(self, params):
        """
        RSI 전략 파라미터 유효성 검사
        
        Args:
            params (dict): 검사할 파라미터 딕셔너리
            
        Returns:
            tuple: (bool, str) - 유효성 여부와 오류 메시지(있는 경우)
        """
        # RSI 기간 검사
        period = params.get('period')
        valid, message = self.validate_numeric_parameter('period', period, 
                                                      min_value=2, max_value=30)
        if not valid:
            return False, message
        
        # 과매수 기준값 검사
        overbought = params.get('overbought')
        valid, message = self.validate_numeric_parameter('overbought', overbought, 
                                                      min_value=50, max_value=90)
        if not valid:
            return False, message
            
        # 과매도 기준값 검사
        oversold = params.get('oversold')
        valid, message = self.validate_numeric_parameter('oversold', oversold, 
                                                     min_value=10, max_value=50)
        if not valid:
            return False, message
            
        # 과매수와 과매도 기준값 비교
        if overbought <= oversold:
            return False, f"과매수 기준값({overbought})은 과매도 기준값({oversold})보다 커야 합니다."
            
        return True, ""
        
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
            
            # NaN 처리
            np.nan_to_num(signals, copy=False, nan=0)
            
            # 결과를 데이터프레임에 할당
            df['signal'] = signals
            
            # position 계산 (signal의 변화량)
            position_values = np.zeros_like(signals)
            if len(signals) > 1:
                position_values[1:] = signals[1:] - signals[:-1]
            
            df['position'] = position_values
            
            return df
        except Exception as e:
            logger.error(f"RSI 신호 생성 중 오류 발생: {e}")
            df['signal'] = 0
            df['position'] = 0
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
        # 파라미터 유효성 검사
        valid, message = self.validate_parameters({
            'fast_period': fast_period,
            'slow_period': slow_period,
            'signal_period': signal_period
        })
        
        if not valid:
            logger.warning(f"MACD 전략 파라미터 오류: {message}. 기본값을 사용합니다.")
            fast_period = 12
            slow_period = 26
            signal_period = 9
            
        super().__init__(name=f"MACD_{fast_period}_{slow_period}_{signal_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        
    def validate_parameters(self, params):
        """
        MACD 전략 파라미터 유효성 검사
        
        Args:
            params (dict): 검사할 파라미터 딕셔너리
            
        Returns:
            tuple: (bool, str) - 유효성 여부와 오류 메시지(있는 경우)
        """
        # 빠른 EMA 기간 검사
        fast_period = params.get('fast_period')
        valid, message = self.validate_numeric_parameter('fast_period', fast_period, 
                                                      min_value=2, max_value=50)
        if not valid:
            return False, message
        
        # 느린 EMA 기간 검사
        slow_period = params.get('slow_period')
        valid, message = self.validate_numeric_parameter('slow_period', slow_period, 
                                                      min_value=5, max_value=100)
        if not valid:
            return False, message
            
        # 시그널 기간 검사
        signal_period = params.get('signal_period')
        valid, message = self.validate_numeric_parameter('signal_period', signal_period, 
                                                      min_value=2, max_value=50)
        if not valid:
            return False, message
            
        # 빠른/느린 EMA 기간 비교
        if fast_period >= slow_period:
            return False, f"느린 EMA 기간({slow_period})은 빠른 EMA 기간({fast_period})보다 커야 합니다."
            
        return True, ""
        
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
            np.nan_to_num(signals, copy=False, nan=0)
            
            # 결과를 데이터프레임에 할당
            df['signal'] = signals
            
            # position 계산 (signal의 변화량)
            position_values = np.zeros_like(signals)
            if len(signals) > 1:
                position_values[1:] = signals[1:] - signals[:-1]
            
            df['position'] = position_values
            
            return df
        except Exception as e:
            logger.error(f"MACD 신호 생성 중 오류 발생: {e}")
            logger.debug(f"데이터 크기: {len(df)}, 파라미터: fast={self.fast_period}, slow={self.slow_period}, signal={self.signal_period}")
            df['signal'] = 0
            df['position'] = 0
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
        # 파라미터 유효성 검사
        valid, message = self.validate_parameters({
            'period': period,
            'std_dev': std_dev
        })
        
        if not valid:
            logger.warning(f"볼린저 밴드 전략 파라미터 오류: {message}. 기본값을 사용합니다.")
            period = 20
            std_dev = 2
            
        super().__init__(name=f"BollingerBands_{period}_{std_dev}")
        self.period = period
        self.std_dev = std_dev
        
    def validate_parameters(self, params):
        """
        볼린저 밴드 전략 파라미터 유효성 검사
        
        Args:
            params (dict): 검사할 파라미터 딕셔너리
            
        Returns:
            tuple: (bool, str) - 유효성 여부와 오류 메시지(있는 경우)
        """
        # 이동평균 기간 검사
        period = params.get('period')
        valid, message = self.validate_numeric_parameter('period', period, 
                                                     min_value=5, max_value=100)
        if not valid:
            return False, message
        
        # 표준편차 배수 검사
        std_dev = params.get('std_dev')
        valid, message = self.validate_numeric_parameter('std_dev', std_dev, 
                                                      min_value=0.5, max_value=4)
        if not valid:
            return False, message
            
        return True, ""
        
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
            np.nan_to_num(signals, copy=False, nan=0)
            
            # 결과를 데이터프레임에 할당
            df['signal'] = signals
            
            # position 계산 (signal의 변화량)
            position_values = np.zeros_like(signals)
            if len(signals) > 1:
                position_values[1:] = signals[1:] - signals[:-1]
            
            df['position'] = position_values
            
            return df
        except Exception as e:
            logger.error(f"볼린저 밴드 신호 생성 중 오류 발생: {e}")
            logger.debug(f"데이터 크기: {len(df)}, 파라미터: period={self.period}, std_dev={self.std_dev}")
            df['signal'] = 0
            df['position'] = 0
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
            np.nan_to_num(signals, copy=False, nan=0)
            
            # 결과를 데이터프레임에 할당
            df['signal'] = signals
            
            return df
        except Exception as e:
            logger.error(f"스토캐스틱 신호 생성 중 오류 발생: {e}")
            df['signal'] = 0
            return df

class BollingerBandFuturesStrategy(Strategy):
    """
    볼린저 밴드 + RSI + MACD + 헤이킨 아시 기반 선물 전략 (복합 신호)
    """
    def __init__(self, bb_period=20, bb_std=2.0, rsi_period=14, rsi_overbought=70, rsi_oversold=30,
                 macd_fast=12, macd_slow=26, macd_signal=9, stop_loss_pct=4.0, take_profit_pct=8.0,
                 trailing_stop_pct=1.5, risk_per_trade=1.5, leverage=3, timeframe='4h'):
        super().__init__(name=f"BollingerBandFutures_{bb_period}_{bb_std}_{rsi_period}_{macd_fast}_{macd_slow}_{macd_signal}")
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.risk_per_trade = risk_per_trade
        self.leverage = leverage
        self.timeframe = timeframe

    def generate_signals(self, df):
        try:
            data = df.copy()
            # 볼린저 밴드
            mid, upper, lower = bollinger_bands(data, period=self.bb_period, std_dev=self.bb_std)
            data['bb_middle'] = mid
            data['bb_upper'] = upper
            data['bb_lower'] = lower
            # RSI
            data['rsi'] = relative_strength_index(data, period=self.rsi_period)
            # MACD
            macd_line, signal_line, hist = moving_average_convergence_divergence(
                data, fast_period=self.macd_fast, slow_period=self.macd_slow, signal_period=self.macd_signal)
            data['macd'] = macd_line
            data['macd_signal'] = signal_line
            data['macd_hist'] = hist
            # 헤이킨 아시 캔들 (재귀적 계산 - 더 정확한 방법)
            data['ha_close'] = (data['open'] + data['high'] + data['low'] + data['close']) / 4
            
            # ha_open 재귀적 계산
            ha_open = np.zeros(len(data))
            ha_open[0] = (data['open'].iloc[0] + data['close'].iloc[0]) / 2
            
            for i in range(1, len(data)):
                ha_open[i] = (ha_open[i-1] + data['ha_close'].iloc[i-1]) / 2
            
            data['ha_open'] = ha_open
            data['ha_high'] = data[['high', 'ha_open', 'ha_close']].max(axis=1)
            data['ha_low'] = data[['low', 'ha_open', 'ha_close']].min(axis=1)
            # 신호 생성 - 가중치 기반 시스템
            data['signal'] = 0
            data['long_score'] = 0
            data['short_score'] = 0
            
            # 롱 조건들 (각 조건에 가중치 부여)
            long_cond1 = (data['close'] < data['bb_lower']) & (data['rsi'] < self.rsi_oversold)
            long_cond2 = (data['macd'] > data['macd_signal']) & (data['macd_hist'] > 0) & (data['macd_hist'].shift(1) <= 0)
            long_cond3 = (data['ha_close'] > data['ha_open']) & (data['close'] > data['close'].shift(1))
            
            # 숏 조건들 (각 조건에 가중치 부여)
            short_cond1 = (data['close'] > data['bb_upper']) & (data['rsi'] > self.rsi_overbought)
            short_cond2 = (data['macd'] < data['macd_signal']) & (data['macd_hist'] < 0) & (data['macd_hist'].shift(1) >= 0)
            short_cond3 = (data['ha_close'] < data['ha_open']) & (data['close'] < data['close'].shift(1))
            
            # 가중치 계산
            data.loc[long_cond1, 'long_score'] += 0.4  # BB + RSI는 높은 가중치
            data.loc[long_cond2, 'long_score'] += 0.3  # MACD 교차
            data.loc[long_cond3, 'long_score'] += 0.3  # 헤이킨 아시 + 가격 상승
            
            data.loc[short_cond1, 'short_score'] += 0.4  # BB + RSI는 높은 가중치
            data.loc[short_cond2, 'short_score'] += 0.3  # MACD 교차
            data.loc[short_cond3, 'short_score'] += 0.3  # 헤이킨 아시 + 가격 하락
            
            # 최소 0.6 이상의 점수가 필요하고, 반대 신호가 없어야 함
            strong_long = (data['long_score'] >= 0.6) & (data['short_score'] == 0)
            strong_short = (data['short_score'] >= 0.6) & (data['long_score'] == 0)
            
            data.loc[strong_long, 'signal'] = 1
            data.loc[strong_short, 'signal'] = -1
            
            # 연속 신호 제거 개선 - 진입하던 포지션과 반대 신호만 허용
            prev_signal = data['signal'].shift(1).fillna(0)
            # 같은 방향 연속 신호를 0으로
            data.loc[(data['signal'] == prev_signal) & (data['signal'] != 0), 'signal'] = 0
            
            # position 계산 (signal의 변화량)
            position_values = np.zeros_like(data['signal'].values)
            if len(data) > 1:
                position_values[1:] = data['signal'].values[1:] - data['signal'].values[:-1]
            
            data['position'] = position_values
            
            return data
        except Exception as e:
            logger.error(f"BollingerBandFutures 신호 생성 중 오류 발생: {e}")
            df['signal'] = 0
            df['position'] = 0
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
        BollingerBandFuturesStrategy()
    ]
    
    for strategy in strategies:
        result_df = strategy.generate_signals(df)
        
        print(f"\n{strategy.name} 전략 테스트 결과:")
        print(f"매수 신호 수: {len(result_df[result_df['signal'] == 1])}")
        print(f"매도 신호 수: {len(result_df[result_df['signal'] == -1])}")
        
        # position 커럼이 있는 경우에만 출력 (BollingerBandFuturesStrategy만)
        if 'position' in result_df.columns:
            print(f"포지션 변경 수: {len(result_df[result_df['position'] != 0])}")

