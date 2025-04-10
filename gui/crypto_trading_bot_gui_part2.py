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
