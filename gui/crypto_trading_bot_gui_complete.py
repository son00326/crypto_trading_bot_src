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
QSpinBox, QScrollArea,
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
class BollingerBandsStrategy(Strategy):
    """볼린저 밴드 기반 전략"""
    def __init__(self, period=20, std_dev=2):
        super().__init__(name=f"BollingerBands_{period}_{std_dev}")
        self.period = period
        self.std_dev = std_dev
    
    def generate_signals(self, df):
        df = df.copy()
        middle_band, upper_band, lower_band = bollinger_bands(
            df,
            period=self.period,
            std_dev=self.std_dev
        )
        
        df['middle_band'] = middle_band
        df['upper_band'] = upper_band
        df['lower_band'] = lower_band
        df['signal'] = 0
        df.loc[(df['close'] < df['lower_band'].shift(1)) & (df['close'] > df['close'].shift(1)), 'signal'] = 1
        df.loc[(df['close'] > df['upper_band'].shift(1)) & (df['close'] < df['close'].shift(1)), 'signal'] = -1
        return df

class CombinedStrategy(Strategy):
    """여러 전략을 결합한 복합 전략"""
    def __init__(self, strategies, weights=None):
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
        df = df.copy()
        signals = []
        for i, strategy in enumerate(self.strategies):
            strategy_df = strategy.generate_signals(df)
            signals.append(strategy_df['signal'] * self.weights[i])
        
        df['combined_signal'] = pd.concat(signals, axis=1).sum(axis=1)
        df['signal'] = 0
        df.loc[df['combined_signal'] > 0.3, 'signal'] = 1
        df.loc[df['combined_signal'] < -0.3, 'signal'] = -1
        return df

class DataCollector:
    """데이터 수집 클래스"""
    def __init__(self, exchange='binance'):
        self.exchange_id = exchange
        self.exchange = getattr(ccxt, exchange)({
            'enableRateLimit': True,
        })
        logger.info(f"{exchange} 거래소에 연결되었습니다.")
    
    def get_historical_data(self, symbol, timeframe='1d', limit=500):
        """
        과거 OHLCV 데이터 가져오기
        Args:
            symbol (str): 거래 쌍 (예: 'BTC/USDT')
            timeframe (str): 타임프레임 (예: '1m', '1h', '1d')
            limit (int): 가져올 캔들 수
        Returns:
            DataFrame: OHLCV 데이터
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            logger.info(f"{symbol} {timeframe} 데이터 {len(df)}개 수집 완료")
            return df
        except Exception as e:
            logger.error(f"데이터 수집 중 오류 발생: {e}")
            return pd.DataFrame()

class RiskManager:
    """위험 관리 클래스"""
    def __init__(self, stop_loss_pct=0.05, take_profit_pct=0.1, max_position_size=0.2):
        """
        위험 관리 초기화
        Args:
            stop_loss_pct (float): 손절매 비율 (예: 0.05 = 5%)
            take_profit_pct (float): 이익실현 비율 (예: 0.1 = 10%)
            max_position_size (float): 최대 포지션 크기 (계좌 자산의 비율)
        """
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_position_size = max_position_size
        logger.info(f"위험 관리 설정: 손절매 {stop_loss_pct*100}%, 이익실현 {take_profit_pct*100}%, 최대 포지션 {max_position_size*100}%")
    
    def calculate_position_size(self, account_balance, current_price, risk_per_trade=0.01):
        """
        포지션 크기 계산
        Args:
            account_balance (float): 계좌 잔고
            current_price (float): 현재 가격
            risk_per_trade (float): 거래당 위험 비율 (예: 0.01 = 1%)
        Returns:
            float: 포지션 크기 (코인 수량)
        """
        risk_amount = account_balance * risk_per_trade
        position_size = risk_amount / (current_price * self.stop_loss_pct)
        
        # 최대 포지션 크기 제한
        max_size = (account_balance * self.max_position_size) / current_price
        position_size = min(position_size, max_size)
        
        return position_size
    
    def calculate_stop_loss(self, entry_price, position_type='long'):
        """
        손절매 가격 계산
        Args:
            entry_price (float): 진입 가격
            position_type (str): 포지션 유형 ('long' 또는 'short')
        Returns:
            float: 손절매 가격
        """
        if position_type.lower() == 'long':
            return entry_price * (1 - self.stop_loss_pct)
        else: # short
            return entry_price * (1 + self.stop_loss_pct)
    
    def calculate_take_profit(self, entry_price, position_type='long'):
        """
        이익실현 가격 계산
        Args:
            entry_price (float): 진입 가격
            position_type (str): 포지션 유형 ('long' 또는 'short')
        Returns:
            float: 이익실현 가격
        """
        if position_type.lower() == 'long':
            return entry_price * (1 + self.take_profit_pct)
        else: # short
            return entry_price * (1 - self.take_profit_pct)
class TradingBot:
    """자동 매매 봇 클래스"""
    def __init__(self, exchange='binance', api_key=None, api_secret=None,
                 strategy=None, symbol='BTC/USDT', timeframe='1h',
                 risk_manager=None, test_mode=True):
        """
        자동 매매 봇 초기화
        Args:
            exchange (str): 거래소 이름
            api_key (str): API 키
            api_secret (str): API 시크릿
            strategy (Strategy): 거래 전략
            symbol (str): 거래 쌍
            timeframe (str): 타임프레임
            risk_manager (RiskManager): 위험 관리 객체
            test_mode (bool): 테스트 모드 여부
        """
        self.exchange_id = exchange
        self.exchange = getattr(ccxt, exchange)({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.test_mode = test_mode
        
        if risk_manager is None:
            self.risk_manager = RiskManager()
        else:
            self.risk_manager = risk_manager
        
        self.data_collector = DataCollector(exchange)
        self.position = {
            'type': None, # 'long' 또는 'short'
            'size': 0,
            'entry_price': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        
        logger.info(f"자동 매매 봇 초기화 완료: {exchange}, {symbol}, {timeframe}, 테스트 모드: {test_mode}")
    
    def get_account_balance(self):
        """계좌 잔고 조회"""
        try:
            if self.test_mode:
                return 10000  # 테스트 모드에서는 가상의 잔고 사용
            
            balance = self.exchange.fetch_balance()
            quote_currency = self.symbol.split('/')[1]
            return balance[quote_currency]['free']
        except Exception as e:
            logger.error(f"잔고 조회 중 오류 발생: {e}")
            return 0
    
    def get_current_price(self):
        """현재 가격 조회"""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"가격 조회 중 오류 발생: {e}")
            return 0
    
    def execute_order(self, order_type, size):
        """주문 실행"""
        try:
            if self.test_mode:
                logger.info(f"[테스트 모드] {order_type} 주문 실행: {self.symbol}, 수량: {size}")
                return {'id': 'test_order', 'price': self.get_current_price()}
            
            if order_type == 'buy':
                order = self.exchange.create_market_buy_order(self.symbol, size)
            elif order_type == 'sell':
                order = self.exchange.create_market_sell_order(self.symbol, size)
            else:
                raise ValueError(f"지원하지 않는 주문 유형입니다: {order_type}")
            
            logger.info(f"주문 실행 완료: {order_type}, {self.symbol}, 수량: {size}, 주문 ID: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"주문 실행 중 오류 발생: {e}")
            return None
    
    def update_position(self, position_type, size, price):
        """포지션 업데이트"""
        self.position['type'] = position_type
        self.position['size'] = size
        self.position['entry_price'] = price
        
        if position_type == 'long':
            self.position['stop_loss'] = self.risk_manager.calculate_stop_loss(price, 'long')
            self.position['take_profit'] = self.risk_manager.calculate_take_profit(price, 'long')
        elif position_type == 'short':
            self.position['stop_loss'] = self.risk_manager.calculate_stop_loss(price, 'short')
            self.position['take_profit'] = self.risk_manager.calculate_take_profit(price, 'short')
        
        logger.info(f"포지션 업데이트: {position_type}, 수량: {size}, 가격: {price}, SL: {self.position['stop_loss']}, TP: {self.position['take_profit']}")
    
    def close_position(self):
        """포지션 종료"""
        if self.position['type'] is None or self.position['size'] == 0:
            return
        
        order_type = 'sell' if self.position['type'] == 'long' else 'buy'
        order = self.execute_order(order_type, self.position['size'])
        
        if order:
            logger.info(f"포지션 종료: {self.position['type']}, 수량: {self.position['size']}, 가격: {order['price']}")
            self.position = {
                'type': None,
                'size': 0,
                'entry_price': 0,
                'stop_loss': 0,
                'take_profit': 0
            }
    
    def check_exit_conditions(self, current_price):
        """종료 조건 확인"""
        if self.position['type'] is None or self.position['size'] == 0:
            return False
        
        # 손절매 확인
        if self.position['type'] == 'long' and current_price <= self.position['stop_loss']:
            logger.info(f"손절매 조건 충족: 현재 가격 {current_price} <= 손절매 가격 {self.position['stop_loss']}")
            return True
        if self.position['type'] == 'short' and current_price >= self.position['stop_loss']:
            logger.info(f"손절매 조건 충족: 현재 가격 {current_price} >= 손절매 가격 {self.position['stop_loss']}")
            return True
        
        # 이익실현 확인
        if self.position['type'] == 'long' and current_price >= self.position['take_profit']:
            logger.info(f"이익실현 조건 충족: 현재 가격 {current_price} >= 이익실현 가격 {self.position['take_profit']}")
            return True
        if self.position['type'] == 'short' and current_price <= self.position['take_profit']:
            logger.info(f"이익실현 조건 충족: 현재 가격 {current_price} <= 이익실현 가격 {self.position['take_profit']}")
            return True
        
        return False
    
    def run_once(self):
        """한 번의 거래 주기 실행"""
        try:
            # 데이터 수집
            df = self.data_collector.get_historical_data(self.symbol, self.timeframe)
            if df.empty:
                logger.error("데이터 수집 실패")
                return
            
            # 신호 생성
            df = self.strategy.generate_signals(df)
            
            # 현재 가격 조회
            current_price = self.get_current_price()
            if current_price == 0:
                logger.error("현재 가격 조회 실패")
                return
            
            # 종료 조건 확인
            if self.check_exit_conditions(current_price):
                self.close_position()
            
            # 마지막 신호 확인
            last_signal = df['signal'].iloc[-1]
            
            # 포지션이 없는 경우 신호에 따라 진입
            if self.position['type'] is None:
                if last_signal == 1:  # 매수 신호
                    account_balance = self.get_account_balance()
                    position_size = self.risk_manager.calculate_position_size(account_balance, current_price)
                    order = self.execute_order('buy', position_size)
                    if order:
                        self.update_position('long', position_size, current_price)
                elif last_signal == -1:  # 매도 신호 (숏 포지션)
                    # 현물 거래에서는 숏 포지션을 사용하지 않음
                    pass
            
            # 포지션이 있는 경우 반대 신호에 따라 종료
            elif self.position['type'] == 'long' and last_signal == -1:
                self.close_position()
            elif self.position['type'] == 'short' and last_signal == 1:
                self.close_position()
            
            logger.info(f"거래 주기 실행 완료: 현재 가격 {current_price}, 신호 {last_signal}, 포지션 {self.position['type']}")
        
        except Exception as e:
            logger.error(f"거래 주기 실행 중 오류 발생: {e}")
    
    def start(self, interval=3600):
        """자동 매매 시작"""
        logger.info(f"자동 매매 시작: {self.symbol}, {self.timeframe}, 간격: {interval}초")
        try:
            while True:
                self.run_once()
                logger.info(f"{interval}초 대기 중...")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("사용자에 의해 자동 매매가 중지되었습니다.")
        except Exception as e:
            logger.error(f"자동 매매 중 오류 발생: {e}")
        finally:
            # 종료 시 포지션 정리
            if not self.test_mode and self.position['type'] is not None:
                logger.info("종료 전 포지션 정리 중...")
                self.close_position()

# 봇 실행을 위한 스레드
class BotThread(QThread):
    update_signal = pyqtSignal(str)
    
    def __init__(self, bot, interval):
        super().__init__()
        self.bot = bot
        self.interval = interval
        self.running = True
    
    def run(self):
        self.update_signal.emit("자동 매매 봇이 시작되었습니다.")
        try:
            while self.running:
                self.bot.run_once()
                self.update_signal.emit(f"{self.interval}초 대기 중...")
                
                # 로그 업데이트
                with open("trading_bot.log", "r") as f:
                    logs = f.readlines()
                    if logs:
                        last_logs = logs[-5:]  # 마지막 5줄만 표시
                        for log in last_logs:
                            self.update_signal.emit(log.strip())
                
                for i in range(self.interval):
                    if not self.running:
                        break
                    time.sleep(1)
        
        except Exception as e:
            self.update_signal.emit(f"오류 발생: {e}")
        finally:
            self.update_signal.emit("봇이 중지되었습니다.")
    
    def stop(self):
        self.running = False
        self.bot.close_position()
        self.update_signal.emit("봇 종료 중...")
# 메인 윈도우
class CryptoTradingBotApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.bot_thread = None
        self.initUI()
        
        # 환경 변수 로드
        load_dotenv()
        
        # API 키 설정
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        if api_key and api_secret:
            self.api_key_input.setText(api_key)
            self.api_secret_input.setText(api_secret)
    
    def initUI(self):
        self.setWindowTitle('암호화폐 자동 매매 봇')
        self.setGeometry(100, 100, 800, 600)
        
        # 메인 위젯 및 레이아웃
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 탭 위젯
        tabs = QTabWidget()
        
        # 설정 탭
        settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_content = QWidget()
        settings_content_layout = QVBoxLayout(settings_content)
        
        # API 설정 그룹
        api_group = QGroupBox("API 설정")
        api_layout = QFormLayout()
        
        self.exchange_combo = QComboBox()
        self.exchange_combo.addItems(['binance', 'upbit', 'bithumb'])
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        
        api_layout.addRow("거래소:", self.exchange_combo)
        api_layout.addRow("API 키:", self.api_key_input)
        api_layout.addRow("API 시크릿:", self.api_secret_input)
        
        api_group.setLayout(api_layout)
        
        # 거래 설정 그룹
        trade_group = QGroupBox("거래 설정")
        trade_layout = QFormLayout()
        
        self.symbol_input = QLineEdit("BTC/USDT")
        
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(['1m', '5m', '15m', '30m', '1h', '4h', '1d'])
        self.timeframe_combo.setCurrentText('1h')
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(60, 3600)
        self.interval_spin.setValue(300)
        self.interval_spin.setSuffix(" 초")
        
        self.test_mode_check = QCheckBox("테스트 모드 (실제 거래 없음)")
        self.test_mode_check.setChecked(True)
        
        trade_layout.addRow("거래 쌍:", self.symbol_input)
        trade_layout.addRow("타임프레임:", self.timeframe_combo)
        trade_layout.addRow("실행 간격:", self.interval_spin)
        trade_layout.addRow(self.test_mode_check)
        
        trade_group.setLayout(trade_layout)
        
        # 전략 설정 그룹
        strategy_group = QGroupBox("전략 설정")
        strategy_layout = QVBoxLayout()
        
        # 이동평균 전략 설정
        ma_check = QCheckBox("이동평균 교차 전략")
        ma_check.setChecked(True)
        self.ma_check = ma_check
        
        ma_form = QFormLayout()
        
        self.ma_short_spin = QSpinBox()
        self.ma_short_spin.setRange(1, 50)
        self.ma_short_spin.setValue(9)
        
        self.ma_long_spin = QSpinBox()
        self.ma_long_spin.setRange(10, 200)
        self.ma_long_spin.setValue(26)
        
        self.ma_type_combo = QComboBox()
        self.ma_type_combo.addItems(['sma', 'ema'])
        self.ma_type_combo.setCurrentText('ema')
        
        self.ma_weight_spin = QDoubleSpinBox()
        self.ma_weight_spin.setRange(0, 1)
        self.ma_weight_spin.setValue(0.4)
        self.ma_weight_spin.setSingleStep(0.1)
        
        ma_form.addRow("단기 기간:", self.ma_short_spin)
        ma_form.addRow("장기 기간:", self.ma_long_spin)
        ma_form.addRow("이동평균 유형:", self.ma_type_combo)
        ma_form.addRow("가중치:", self.ma_weight_spin)
        
        ma_widget = QWidget()
        ma_widget.setLayout(ma_form)
        
        # RSI 전략 설정
        rsi_check = QCheckBox("RSI 전략")
        rsi_check.setChecked(True)
        self.rsi_check = rsi_check
        
        rsi_form = QFormLayout()
        
        self.rsi_period_spin = QSpinBox()
        self.rsi_period_spin.setRange(1, 50)
        self.rsi_period_spin.setValue(14)
        
        self.rsi_overbought_spin = QSpinBox()
        self.rsi_overbought_spin.setRange(50, 100)
        self.rsi_overbought_spin.setValue(70)
        
        self.rsi_oversold_spin = QSpinBox()
        self.rsi_oversold_spin.setRange(0, 50)
        self.rsi_oversold_spin.setValue(30)
        
        self.rsi_weight_spin = QDoubleSpinBox()
        self.rsi_weight_spin.setRange(0, 1)
        self.rsi_weight_spin.setValue(0.3)
        self.rsi_weight_spin.setSingleStep(0.1)
        
        rsi_form.addRow("기간:", self.rsi_period_spin)
        rsi_form.addRow("과매수 기준:", self.rsi_overbought_spin)
        rsi_form.addRow("과매도 기준:", self.rsi_oversold_spin)
        rsi_form.addRow("가중치:", self.rsi_weight_spin)
        
        rsi_widget = QWidget()
        rsi_widget.setLayout(rsi_form)
        
        # MACD 전략 설정
        macd_check = QCheckBox("MACD 전략")
        macd_check.setChecked(True)
        self.macd_check = macd_check
        
        macd_form = QFormLayout()
        
        self.macd_fast_spin = QSpinBox()
        self.macd_fast_spin.setRange(1, 50)
        self.macd_fast_spin.setValue(12)
        
        self.macd_slow_spin = QSpinBox()
        self.macd_slow_spin.setRange(10, 100)
        self.macd_slow_spin.setValue(26)
        
        self.macd_signal_spin = QSpinBox()
        self.macd_signal_spin.setRange(1, 50)
        self.macd_signal_spin.setValue(9)
        
        self.macd_weight_spin = QDoubleSpinBox()
        self.macd_weight_spin.setRange(0, 1)
        self.macd_weight_spin.setValue(0.2)
        self.macd_weight_spin.setSingleStep(0.1)
        
        macd_form.addRow("빠른 기간:", self.macd_fast_spin)
        macd_form.addRow("느린 기간:", self.macd_slow_spin)
        macd_form.addRow("시그널 기간:", self.macd_signal_spin)
        macd_form.addRow("가중치:", self.macd_weight_spin)
        
        macd_widget = QWidget()
        macd_widget.setLayout(macd_form)
        
        # 볼린저 밴드 전략 설정
        bb_check = QCheckBox("볼린저 밴드 전략")
        bb_check.setChecked(True)
        self.bb_check = bb_check
        
        bb_form = QFormLayout()
        
        self.bb_period_spin = QSpinBox()
        self.bb_period_spin.setRange(1, 50)
        self.bb_period_spin.setValue(20)
        
        self.bb_std_spin = QDoubleSpinBox()
        self.bb_std_spin.setRange(0.5, 5)
        self.bb_std_spin.setValue(2)
        self.bb_std_spin.setSingleStep(0.1)
        
        self.bb_weight_spin = QDoubleSpinBox()
        self.bb_weight_spin.setRange(0, 1)
        self.bb_weight_spin.setValue(0.1)
        self.bb_weight_spin.setSingleStep(0.1)
        
        bb_form.addRow("기간:", self.bb_period_spin)
        bb_form.addRow("표준편차:", self.bb_std_spin)
        bb_form.addRow("가중치:", self.bb_weight_spin)
        
        bb_widget = QWidget()
        bb_widget.setLayout(bb_form)
        
        # 전략 레이아웃에 추가
        strategy_layout.addWidget(ma_check)
        strategy_layout.addWidget(ma_widget)
        strategy_layout.addWidget(rsi_check)
        strategy_layout.addWidget(rsi_widget)
        strategy_layout.addWidget(macd_check)
        strategy_layout.addWidget(macd_widget)
        strategy_layout.addWidget(bb_check)
        strategy_layout.addWidget(bb_widget)
        
        strategy_group.setLayout(strategy_layout)
        
        # 위험 관리 설정 그룹
        risk_group = QGroupBox("위험 관리 설정")
        risk_layout = QFormLayout()
        
        self.stop_loss_spin = QDoubleSpinBox()
        self.stop_loss_spin.setRange(0.01, 0.5)
        self.stop_loss_spin.setValue(0.05)
        self.stop_loss_spin.setSingleStep(0.01)
        self.stop_loss_spin.setSuffix(" (5%)")
        
        self.take_profit_spin = QDoubleSpinBox()
        self.take_profit_spin.setRange(0.01, 0.5)
        self.take_profit_spin.setValue(0.1)
        self.take_profit_spin.setSingleStep(0.01)
        self.take_profit_spin.setSuffix(" (10%)")
        
        self.max_position_spin = QDoubleSpinBox()
        self.max_position_spin.setRange(0.01, 1)
        self.max_position_spin.setValue(0.2)
        self.max_position_spin.setSingleStep(0.05)
        self.max_position_spin.setSuffix(" (20%)")
        
        risk_layout.addRow("손절매 비율:", self.stop_loss_spin)
        risk_layout.addRow("이익실현 비율:", self.take_profit_spin)
        risk_layout.addRow("최대 포지션 크기:", self.max_position_spin)
        
        risk_group.setLayout(risk_layout)
        
        # 설정 탭에 그룹 추가
        settings_content_layout.addWidget(api_group)
        settings_content_layout.addWidget(trade_group)
        settings_content_layout.addWidget(risk_group)
        settings_content_layout.addWidget(strategy_group)
        
        settings_scroll.setWidget(settings_content)
        settings_layout.addWidget(settings_scroll)
        settings_tab.setLayout(settings_layout)
        
        # 로그 탭
        log_tab = QWidget()
        log_layout = QVBoxLayout()
        log_scroll = QScrollArea()
        log_scroll.setWidgetResizable(True)
        log_content = QWidget()
        log_content_layout = QVBoxLayout(log_content)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        log_content_layout.addWidget(self.log_text)
        log_scroll.setWidget(log_content)
        log_layout.addWidget(log_scroll)
        log_tab.setLayout(log_layout)
        
        # 탭 추가
        tabs.addTab(settings_tab, "설정")
        tabs.addTab(log_tab, "로그")
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("시작")
        self.start_button.clicked.connect(self.start_bot)
        
        self.stop_button = QPushButton("중지")
        self.stop_button.clicked.connect(self.stop_bot)
        self.stop_button.setEnabled(False)
        
        self.save_button = QPushButton("설정 저장")
        self.save_button.clicked.connect(self.save_settings)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.save_button)
        
        # 메인 레이아웃에 위젯 추가
        main_layout.addWidget(tabs)
        main_layout.addLayout(button_layout)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
    
    def start_bot(self):
        # API 키 저장
        api_key = self.api_key_input.text()
        api_secret = self.api_secret_input.text()
        
        if not api_key or not api_secret:
            QMessageBox.warning(self, "경고", "API 키와 시크릿을 입력해주세요.")
            return
        
        # .env 파일에 API 키 저장
        with open(".env", "w") as f:
            f.write(f"BINANCE_API_KEY={api_key}\n")
            f.write(f"BINANCE_API_SECRET={api_secret}\n")
        
        # 설정 가져오기
        exchange = self.exchange_combo.currentText()
        symbol = self.symbol_input.text()
        timeframe = self.timeframe_combo.currentText()
        interval = self.interval_spin.value()
        test_mode = self.test_mode_check.isChecked()
        
        # 전략 생성
        strategies = []
        weights = []
        
        if self.ma_check.isChecked():
            ma_strategy = MovingAverageCrossover(
                short_period=self.ma_short_spin.value(),
                long_period=self.ma_long_spin.value(),
                ma_type=self.ma_type_combo.currentText()
            )
            strategies.append(ma_strategy)
            weights.append(self.ma_weight_spin.value())
        
        if self.rsi_check.isChecked():
            rsi_strategy = RSIStrategy(
                period=self.rsi_period_spin.value(),
                overbought=self.rsi_overbought_spin.value(),
                oversold=self.rsi_oversold_spin.value()
            )
            strategies.append(rsi_strategy)
            weights.append(self.rsi_weight_spin.value())
        
        if self.macd_check.isChecked():
            macd_strategy = MACDStrategy(
                fast_period=self.macd_fast_spin.value(),
                slow_period=self.macd_slow_spin.value(),
                signal_period=self.macd_signal_spin.value()
            )
            strategies.append(macd_strategy)
            weights.append(self.macd_weight_spin.value())
        
        if self.bb_check.isChecked():
            bb_strategy = BollingerBandsStrategy(
                period=self.bb_period_spin.value(),
                std_dev=self.bb_std_spin.value()
            )
            strategies.append(bb_strategy)
            weights.append(self.bb_weight_spin.value())
        
        if not strategies:
            QMessageBox.warning(self, "경고", "최소한 하나 이상의 전략을 선택해주세요.")
            return
        
        # 가중치 정규화
        weight_sum = sum(weights)
        if weight_sum > 0:
            weights = [w / weight_sum for w in weights]
        
        # 복합 전략 생성
        combined_strategy = CombinedStrategy(strategies=strategies, weights=weights)
        
        # 위험 관리 설정
        risk_manager = RiskManager(
            stop_loss_pct=self.stop_loss_spin.value(),
            take_profit_pct=self.take_profit_spin.value(),
            max_position_size=self.max_position_spin.value()
        )
        
        # 봇 생성
        bot = TradingBot(
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            strategy=combined_strategy,
            symbol=symbol,
            timeframe=timeframe,
            risk_manager=risk_manager,
            test_mode=test_mode
        )
        
        # 봇 스레드 시작
        self.bot_thread = BotThread(bot, interval)
        self.bot_thread.update_signal.connect(self.update_log)
        self.bot_thread.start()
        
        # 버튼 상태 변경
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        self.log_text.append("자동 매매 봇이 시작되었습니다.")
    
    def stop_bot(self):
        if self.bot_thread and self.bot_thread.isRunning():
            self.bot_thread.stop()
            self.bot_thread.wait()
        
        # 버튼 상태 변경
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        self.log_text.append("자동 매매 봇이 중지되었습니다.")
    
    def update_log(self, message):
        self.log_text.append(message)
        # 스크롤을 항상 아래로 유지
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    def save_settings(self):
        # 설정 저장
        settings = {
            "exchange": self.exchange_combo.currentText(),
            "symbol": self.symbol_input.text(),
            "timeframe": self.timeframe_combo.currentText(),
            "interval": self.interval_spin.value(),
            "test_mode": self.test_mode_check.isChecked(),
            "ma_enabled": self.ma_check.isChecked(),
            "ma_short_period": self.ma_short_spin.value(),
            "ma_long_period": self.ma_long_spin.value(),
            "ma_type": self.ma_type_combo.currentText(),
            "ma_weight": self.ma_weight_spin.value(),
            "rsi_enabled": self.rsi_check.isChecked(),
            "rsi_period": self.rsi_period_spin.value(),
            "rsi_overbought": self.rsi_overbought_spin.value(),
            "rsi_oversold": self.rsi_oversold_spin.value(),
            "rsi_weight": self.rsi_weight_spin.value(),
            "macd_enabled": self.macd_check.isChecked(),
            "macd_fast_period": self.macd_fast_spin.value(),
            "macd_slow_period": self.macd_slow_spin.value(),
            "macd_signal_period": self.macd_signal_spin.value(),
            "macd_weight": self.macd_weight_spin.value(),
            "bb_enabled": self.bb_check.isChecked(),
            "bb_period": self.bb_period_spin.value(),
            "bb_std_dev": self.bb_std_spin.value(),
            "bb_weight": self.bb_weight_spin.value(),
            "stop_loss_pct": self.stop_loss_spin.value(),
            "take_profit_pct": self.take_profit_spin.value(),
            "max_position_size": self.max_position_spin.value(),
        }
        
        # 설정 파일 저장
        with open("bot_settings.txt", "w") as f:
            for key, value in settings.items():
                f.write(f"{key}={value}\n")
        
        QMessageBox.information(self, "알림", "설정이 저장되었습니다.")
    
    def closeEvent(self, event):
        # 프로그램 종료 시 봇 중지
        if self.bot_thread and self.bot_thread.isRunning():
            self.bot_thread.stop()
            self.bot_thread.wait()
        event.accept()

# 메인 함수
def main():
    app = QApplication(sys.argv)
    window = CryptoTradingBotApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
