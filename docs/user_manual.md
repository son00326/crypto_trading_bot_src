# 암호화폐 자동 매매 봇 사용 설명서

## 1. 소개

이 문서는 암호화폐 자동 매매 봇의 사용 방법을 설명합니다. 이 봇은 다양한 기술적 분석 지표와 거래 전략을 활용하여 암호화폐 시장에서 자동으로 거래를 수행할 수 있습니다. 또한 백테스팅 기능을 통해 과거 데이터로 전략의 성능을 평가하고, 위험 관리 기능을 통해 자산을 보호할 수 있습니다.

## 2. 시스템 요구사항

- Python 3.8 이상
- 필요한 라이브러리: pandas, numpy, matplotlib, ccxt, python-binance, python-dotenv, requests, seaborn, tqdm
- 거래소 API 키 (바이낸스, 업비트, 빗썸 등)

## 3. 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/yourusername/crypto_trading_bot.git
cd crypto_trading_bot
```

2. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

3. 환경 설정
```bash
cp src/env.template .env
```
`.env` 파일을 열고 거래소 API 키 정보를 입력하세요.

## 4. 프로젝트 구조

```
crypto_trading_bot/
├── README.md
├── requirements.txt
├── .env
├── src/
│   ├── config.py              # 설정 파일
│   ├── exchange_api.py        # 거래소 API 연결
│   ├── data_manager.py        # 데이터 저장 및 관리
│   ├── data_collector.py      # 데이터 수집
│   ├── data_analyzer.py       # 데이터 분석 및 시각화
│   ├── indicators.py          # 기술적 분석 지표
│   ├── strategies.py          # 거래 전략
│   ├── trading_algorithm.py   # 거래 알고리즘
│   ├── backtesting.py         # 백테스팅 프레임워크
│   └── risk_manager.py        # 위험 관리
└── data/                      # 데이터 저장 디렉토리
    ├── ohlcv/                 # OHLCV 데이터
    ├── charts/                # 차트 이미지
    ├── backtest_results/      # 백테스팅 결과
    └── risk_logs/             # 위험 관리 로그
```

## 5. 주요 기능

### 5.1 데이터 수집 및 분석

#### 데이터 수집
```python
from src.data_collector import DataCollector

# 데이터 수집기 초기화
collector = DataCollector(exchange_id='binance', symbol='BTC/USDT', timeframe='1h')

# 최근 데이터 가져오기
recent_data = collector.fetch_recent_data(limit=100)

# 과거 데이터 가져오기
historical_data = collector.fetch_historical_data(
    start_date='2023-01-01',
    end_date='2023-12-31'
)

# 실시간 데이터 수집 (별도 스레드에서 실행)
import threading
thread = threading.Thread(
    target=collector.fetch_realtime_data,
    args=(60, None)  # 60초 간격으로 데이터 수집
)
thread.daemon = True
thread.start()
```

#### 데이터 분석
```python
from src.data_analyzer import DataAnalyzer

# 데이터 분석기 초기화
analyzer = DataAnalyzer(exchange_id='binance', symbol='BTC/USDT')

# 기술적 분석 지표 적용
df_with_indicators = analyzer.apply_indicators(df)

# 가격 차트 생성
analyzer.plot_price_chart(df_with_indicators)

# 시장 데이터 종합 분석
analysis_result = analyzer.analyze_market_data(timeframe='1d', period=100)
```

### 5.2 거래 전략

#### 전략 생성
```python
from src.strategies import (
    MovingAverageCrossover, RSIStrategy, MACDStrategy, 
    BollingerBandsStrategy, CombinedStrategy
)

# 이동평균 교차 전략
ma_strategy = MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema')

# RSI 전략
rsi_strategy = RSIStrategy(period=14, overbought=70, oversold=30)

# 복합 전략
combined_strategy = CombinedStrategy([
    MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema'),
    RSIStrategy(period=14, overbought=70, oversold=30)
], weights=[0.6, 0.4])
```

#### 신호 생성
```python
# 전략에 따른 신호 생성
df_with_signals = ma_strategy.generate_signals(df)

# 포지션 계산
df_with_positions = ma_strategy.calculate_positions(df_with_signals)
```

### 5.3 백테스팅

#### 단일 전략 백테스트
```python
from src.backtesting import Backtester

# 백테스터 초기화
backtester = Backtester(exchange_id='binance', symbol='BTC/USDT', timeframe='1d')

# 백테스트 실행
result = backtester.run_backtest(
    strategy=ma_strategy,
    start_date='2023-01-01',
    end_date='2023-12-31',
    initial_balance=10000,
    commission=0.001
)

# 결과 시각화
result.plot_equity_curve()
result.plot_drawdown_chart()
result.plot_monthly_returns()

# 결과 저장
result.save_results()
```

#### 전략 최적화
```python
# 파라미터 그리드 정의
param_grid = {
    'short_period': [5, 9, 14],
    'long_period': [20, 26, 50],
    'ma_type': ['sma', 'ema']
}

# 전략 최적화
best_params, best_result = backtester.optimize_strategy(
    strategy_class=MovingAverageCrossover,
    param_grid=param_grid,
    start_date='2023-01-01',
    end_date='2023-12-31'
)
```

#### 여러 전략 비교
```python
# 여러 전략 정의
strategies = [
    MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema'),
    RSIStrategy(period=14, overbought=70, oversold=30),
    MACDStrategy(),
    BollingerBandsStrategy()
]

# 전략 비교
results = backtester.compare_strategies(
    strategies=strategies,
    start_date='2023-01-01',
    end_date='2023-12-31'
)
```

### 5.4 거래 알고리즘

#### 거래 알고리즘 초기화
```python
from src.trading_algorithm import TradingAlgorithm

# 거래 알고리즘 초기화 (테스트 모드)
algorithm = TradingAlgorithm(
    exchange_id='binance',
    symbol='BTC/USDT',
    timeframe='1h',
    strategy=combined_strategy,
    initial_balance=10000,
    test_mode=True
)
```

#### 자동 거래 시작
```python
# 별도 스레드에서 자동 거래 시작
trading_thread = algorithm.start_trading_thread(interval=60)  # 60초 간격으로 거래 사이클 실행

# 거래 중지
algorithm.stop_trading()

# 포트폴리오 요약 정보 확인
summary = algorithm.get_portfolio_summary()
```

### 5.5 위험 관리

#### 위험 관리자 초기화
```python
from src.risk_manager import RiskManager

# 위험 관리자 초기화
risk_manager = RiskManager(exchange_id='binance', symbol='BTC/USDT')
```

#### 포지션 크기 계산
```python
# 적절한 포지션 크기 계산
position_size = risk_manager.calculate_position_size(
    account_balance=10000,
    current_price=50000,
    risk_per_trade=0.01
)
```

#### 손절매 및 이익실현 가격 계산
```python
# 손절매 가격 계산
stop_loss_price = risk_manager.calculate_stop_loss_price(
    entry_price=50000,
    side='long'
)

# 이익실현 가격 계산
take_profit_price = risk_manager.calculate_take_profit_price(
    entry_price=50000,
    side='long'
)
```

#### 트레일링 스탑 구현
```python
# 트레일링 스탑 구현
updated_position, triggered = risk_manager.implement_trailing_stop(
    current_price=52000,
    position=position,
    activation_pct=0.01,
    trail_pct=0.02
)
```

#### 알림 전송
```python
# 알림 전송
risk_manager.send_alert(
    subject="위험 경고",
    message="포트폴리오 손실이 일일 한도를 초과했습니다.",
    alert_type='all'  # 'email', 'telegram', 'all'
)
```

## 6. 설정 파일 (config.py)

설정 파일에서는 다음과 같은 항목을 설정할 수 있습니다:

- 기본 거래소, 심볼, 타임프레임
- 데이터 저장 경로
- 위험 관리 설정 (손절매 비율, 이익실현 비율, 최대 포지션 크기 등)
- 이메일 및 텔레그램 알림 설정
- 백테스팅 파라미터

```python
# 기본 설정
DEFAULT_EXCHANGE = 'binance'
DEFAULT_SYMBOL = 'BTC/USDT'
DEFAULT_TIMEFRAME = '1h'

# 데이터 디렉토리
DATA_DIR = '/home/ubuntu/crypto_trading_bot/data'

# 위험 관리 설정
RISK_MANAGEMENT = {
    'stop_loss_pct': 0.05,        # 손절매 비율 (5%)
    'take_profit_pct': 0.1,       # 이익실현 비율 (10%)
    'max_position_size': 0.2,     # 최대 포지션 크기 (계좌 자산의 20%)
    'risk_per_trade': 0.01,       # 거래당 위험 비율 (1%)
    'daily_loss_limit': 0.05,     # 일일 손실 한도 (5%)
    'max_loss_limit': 0.2,        # 총 손실 한도 (20%)
    'max_positions': 3,           # 최대 포지션 수
    'base_volatility': 0.2,       # 기준 변동성
    'min_risk_per_trade': 0.001,  # 최소 거래당 위험 비율
    'max_risk_per_trade': 0.02    # 최대 거래당 위험 비율
}

# 이메일 알림 설정
EMAIL_CONFIG = {
    'sender_email': 'your_email@gmail.com',
    'receiver_email': 'your_email@gmail.com',
    'password': 'your_app_password',
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587
}

# 텔레그램 알림 설정
TELEGRAM_CONFIG = {
    'bot_token': 'your_bot_token',
    'chat_id': 'your_chat_id'
}

# 백테스팅 파라미터
BACKTEST_PARAMS = {
    'default_commission': 0.001,  # 기본 수수료율 (0.1%)
    'default_slippage': 0.0005    # 기본 슬리피지 (0.05%)
}
```

## 7. 주의사항

- 이 봇은 교육 및 연구 목적으로 제공됩니다. 실제 거래에 사용할 경우 발생하는 손실에 대한 책임은 사용자에게 있습니다.
- 항상 테스트 모드에서 충분히 테스트한 후 실제 거래에 사용하세요.
- API 키는 절대 공개하지 마세요. `.env` 파일을 통해 안전하게 관리하세요.
- 거래소의 API 사용 제한을 확인하고 준수하세요.
- 백테스팅 결과가 좋다고 해서 실제 거래에서도 좋은 성과를 보장하지는 않습니다.

## 8. 문제 해결

### 8.1 API 연결 오류
- API 키와 시크릿이 올바르게 설정되었는지 확인하세요.
- 인터넷 연결을 확인하세요.
- 거래소 서버 상태를 확인하세요.

### 8.2 데이터 수집 오류
- 타임프레임과 심볼이 거래소에서 지원하는지 확인하세요.
- 요청 제한을 초과하지 않았는지 확인하세요.
- 과거 데이터 요청 시 너무 긴 기간을 한 번에 요청하지 마세요.

### 8.3 거래 오류
- 계좌에 충분한 잔고가 있는지 확인하세요.
- 최소 주문 수량을 충족하는지 확인하세요.
- 거래소의 거래 규칙을 확인하세요.

## 9. 추가 자료

- [CCXT 문서](https://ccxt.readthedocs.io/)
- [Python-Binance 문서](https://python-binance.readthedocs.io/)
- [Pandas 문서](https://pandas.pydata.org/docs/)
- [Matplotlib 문서](https://matplotlib.org/stable/contents.html)
- [암호화폐 기술적 분석 가이드](https://www.investopedia.com/terms/t/technicalanalysis.asp)

## 10. 연락처

문제나 질문이 있으면 다음 연락처로 문의하세요:
- 이메일: your_email@example.com
- GitHub: https://github.com/yourusername/crypto_trading_bot/issues
