# 암호화폐 자동 매매 봇 (Crypto Trading Bot)

## 프로젝트 개요

이 프로젝트는 다양한 기술적 지표와 매매 전략을 활용한 암호화폐 자동 매매 봇입니다. 명령줄 인터페이스(CLI)와 그래픽 사용자 인터페이스(GUI)를 모두 지원하여 사용자 편의성을 높였습니다. 여러 거래소(Binance, Upbit, Bithumb)를 지원하며, 다양한 매매 전략(이동평균, RSI, MACD, 볼린저 밴드 등)을 조합하여 사용할 수 있습니다.

## 주요 기능

- **다양한 거래소 지원**: Binance, Upbit, Bithumb 등 주요 암호화폐 거래소 연동
- **여러 기술적 지표 기반 전략**:
  - 이동평균(Moving Average) 교차 전략
  - 상대강도지수(RSI) 전략
  - MACD(Moving Average Convergence Divergence) 전략
  - 볼린저 밴드(Bollinger Bands) 전략
- **위험 관리 기능**:
  - 손절매(Stop Loss) 설정
  - 이익실현(Take Profit) 설정
  - 최대 포지션 크기 제한
- **데이터 수집 및 분석**:
  - 과거 데이터 수집 및 저장
  - 데이터 분석 및 시각화
- **백테스팅**: 과거 데이터로 전략 성능 검증
- **GUI 인터페이스**: 직관적인 PyQt5 기반 사용자 인터페이스

## 설치 방법

### 1. 저장소 클론

```bash
git clone https://github.com/son00326/crypto_trading_bot_src.git
cd crypto_trading_bot_src
```

### 2. 필요한 패키지 설치

```bash
pip install -r requirements.txt
```

주요 의존성 패키지:
- pandas, numpy: 데이터 처리
- ccxt: 거래소 API 연동
- PyQt5: GUI 인터페이스
- matplotlib: 데이터 시각화
- python-dotenv: 환경 변수 관리

### 3. 환경 설정

1. `src/env.template` 파일을 `.env` 파일로 복사합니다.
2. `.env` 파일에 거래소 API 키와 시크릿을 설정합니다.

```
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
# 필요한 경우 다른 거래소 API 키도 추가
```

## 사용 방법

### CLI 모드 사용

```bash
# 데이터 수집
python main.py --mode collect --exchange binance --symbol BTC/USDT --timeframe 1h --start-date 2023-01-01

# 백테스팅
python main.py --mode backtest --strategy moving_average --params short_window=10,long_window=50

# 실제 거래 실행
python main.py --mode trade --exchange binance --symbol BTC/USDT --strategy combined
```

### GUI 모드 사용

```bash
python main.py --mode gui
```

또는

```bash
python gui/crypto_trading_bot_gui_complete.py
```

GUI가 실행되면:
1. API 설정 탭에서 거래소 선택 및 API 키 입력
2. 전략 설정 탭에서 원하는 매매 전략 선택 및 파라미터 설정
3. 위험 관리 설정 탭에서 손절매, 이익실현 등 설정
4. 시작 버튼을 클릭하여 봇 실행

## 프로젝트 구조

```
.
├── main.py                   # 메인 실행 파일
├── gui/                      # GUI 관련 파일
│   └── crypto_trading_bot_gui_complete.py # GUI 메인 파일
├── src/                      # 소스 코드
│   ├── backtesting.py        # 백테스팅 모듈
│   ├── config.py             # 설정 모듈
│   ├── data_analyzer.py      # 데이터 분석 모듈
│   ├── data_collector.py     # 데이터 수집 모듈
│   ├── data_manager.py       # 데이터 관리 모듈
│   ├── exchange_api.py       # 거래소 API 모듈
│   ├── indicators.py         # 기술적 지표 모듈
│   ├── risk_manager.py       # 위험 관리 모듈
│   ├── strategies.py         # 매매 전략 모듈
│   └── trading_algorithm.py  # 거래 알고리즘 모듈
└── docs/                     # 문서
    ├── performance_report.md # 성능 보고서
    └── user_manual.md        # 사용자 매뉴얼
```

## 기여 방법

1. 이 저장소를 포크합니다.
2. 새 브랜치를 생성합니다: `git checkout -b feature/awesome-feature`
3. 변경사항을 커밋합니다: `git commit -m 'Add awesome feature'`
4. 브랜치를 푸시합니다: `git push origin feature/awesome-feature`
5. Pull Request를 제출합니다.

## 주의사항

- 이 봇은 교육 및 연구 목적으로 제공됩니다.
- 실제 거래에 사용할 경우 발생하는 금전적 손실에 대한 책임은 사용자에게 있습니다.
- API 키 보안에 주의하세요. `.env` 파일을 절대 공유하지 마세요.

## 라이센스

MIT License
