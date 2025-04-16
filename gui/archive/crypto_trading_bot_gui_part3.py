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
