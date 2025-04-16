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
        settings_layout.addWidget(api_group)
        settings_layout.addWidget(trade_group)
        settings_layout.addWidget(risk_group)
        settings_layout.addWidget(strategy_group)
        
        settings_tab.setLayout(settings_layout)
        
        # 로그 탭
        log_tab = QWidget()
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        log_layout.addWidget(self.log_text)
        
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
