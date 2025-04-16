#!/usr/bin/env python3
# crypto_trading_bot_gui.py
# 암호화폐 자동 매매 봇 GUI 버전
import sys
import os
import pandas as pd
import numpy as np
import ccxt
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
QHBoxLayout,
QLabel, QPushButton, QComboBox, QLineEdit, QTextEdit,
QCheckBox, QGroupBox, QFormLayout, QDoubleSpinBox,
QSpinBox,
QTabWidget, QFileDialog, QMessageBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QIcon

# 로깅 설정
logging.basicConfig(
level=logging.INFO,
format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
handlers=[
logging.FileHandler("trading_bot.log"),
logging.StreamHandler()
]
)
logger = logging.getLogger('trading_bot')

# 기술적 지표 함수들
def simple_moving_average(df, period=20, column='close'):
    return df[column].rolling(window=period).mean()

def exponential_moving_average(df, period=20, column='close'):
    return df[column].ewm(span=period, adjust=False).mean()

def relative_strength_index(df, period=14, column='close'):
    delta = df[column].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def moving_average_convergence_divergence(df, fast_period=12, slow_period=26,
signal_period=9, column='close'):
    fast_ema = exponential_moving_average(df, period=fast_period, column=column)
    slow_ema = exponential_moving_average(df, period=slow_period, column=column)
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def bollinger_bands(df, period=20, std_dev=2, column='close'):
    middle_band = simple_moving_average(df, period=period, column=column)
    std = df[column].rolling(window=period).std()
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    return middle_band, upper_band, lower_band

# 전략 클래스들
class Strategy:
    """거래 전략의 기본 클래스"""
    def __init__(self, name="BaseStrategy"):
        self.name = name
        logger.info(f"{self.name} 전략이 초기화되었습니다.")
    
    def generate_signals(self, df):
        raise NotImplementedError("자식 클래스에서 구현해야 합니다.")
    
    def calculate_positions(self, df):
        if 'signal' not in df.columns:
            df = self.generate_signals(df)
        df['position'] = df['signal'].diff()
        return df

class MovingAverageCrossover(Strategy):
    """이동평균 교차 전략"""
    def __init__(self, short_period=9, long_period=26, ma_type='sma'):
        super().__init__(name=f"MA_Crossover_{short_period}_{long_period}_{ma_type}")
        self.short_period = short_period
        self.long_period = long_period
        self.ma_type = ma_type
    
    def generate_signals(self, df):
        df = df.copy()
        if self.ma_type.lower() == 'sma':
            df['short_ma'] = simple_moving_average(df, period=self.short_period)
            df['long_ma'] = simple_moving_average(df, period=self.long_period)
        elif self.ma_type.lower() == 'ema':
            df['short_ma'] = exponential_moving_average(df, period=self.short_period)
            df['long_ma'] = exponential_moving_average(df, period=self.long_period)
        else:
            raise ValueError(f"지원하지 않는 이동평균 유형입니다: {self.ma_type}")
        
        df['signal'] = 0
        df.loc[df['short_ma'] > df['long_ma'], 'signal'] = 1
        df.loc[df['short_ma'] < df['long_ma'], 'signal'] = -1
        return df

class RSIStrategy(Strategy):
    """RSI 기반 전략"""
    def __init__(self, period=14, overbought=70, oversold=30):
        super().__init__(name=f"RSI_{period}_{overbought}_{oversold}")
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
    
    def generate_signals(self, df):
        df = df.copy()
        df['rsi'] = relative_strength_index(df, period=self.period)
        df['signal'] = 0
        df.loc[df['rsi'] < self.oversold, 'signal'] = 1
        df.loc[df['rsi'] > self.overbought, 'signal'] = -1
        return df

class MACDStrategy(Strategy):
    """MACD 기반 전략"""
    def __init__(self, fast_period=12, slow_period=26, signal_period=9):
        super().__init__(name=f"MACD_{fast_period}_{slow_period}_{signal_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
    
    def generate_signals(self, df):
        df = df.copy()
        macd_line, signal_line, histogram = moving_average_convergence_divergence(
            df,
            fast_period=self.fast_period,
            slow_period=self.slow_period,
            signal_period=self.signal_period
        )
        
        df['macd'] = macd_line
        df['signal_line'] = signal_line
        df['histogram'] = histogram
        df['signal'] = 0
        df.loc[(df['macd'] > df['signal_line']) & (df['macd'].shift(1) <= df['signal_line'].shift(1)), 'signal'] = 1
        df.loc[(df['macd'] < df['signal_line']) & (df['macd'].shift(1) >= df['signal_line'].shift(1)), 'signal'] = -1
        return df
