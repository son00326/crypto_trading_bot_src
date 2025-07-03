# 암호화폐 트레이딩 봇 심볼 형식 분석 리포트

## 현재 상황 요약

### 1. 각 시스템별 심볼 형식
- **바이낸스 API**: `BTCUSDT` (슬래시 없음)
- **CCXT 라이브러리**: 
  - 현물: `BTC/USDT`
  - 선물: `BTC/USDT:USDT` (내부 표현)
- **DB 저장**: `BTC/USDT` (positions 테이블에서 확인)
- **웹 UI 표시**: 
  - 현물: `BTC/USDT`
  - 선물: `BTCUSDT`

### 2. 문제점 분석

#### 2.1 형식 불일치
- DB에는 `BTC/USDT`로 저장되는데 선물 거래 시 웹 UI는 `BTCUSDT`를 기대
- CCXT는 선물 심볼을 `BTC/USDT:USDT`로 관리하지만 봇은 `BTCUSDT` 사용

#### 2.2 변환 로직 분산
- exchange_api.py: get_market_info에서 심볼 변환
- bot_api_server.py: 여러 곳에서 심볼 변환
- symbol_utils.py: 중앙화된 변환 로직 존재하지만 모든 곳에서 사용 안함

### 3. 현재 플로우

```
사용자 입력 (웹 UI)
    ↓
[선물] BTCUSDT 입력
    ↓
bot_api_server.py (start_bot_api)
    ↓
symbol_to_use = BTCUSDT (콜론 제거 로직 존재)
    ↓
ExchangeAPI 초기화 (symbol=BTCUSDT)
    ↓
get_market_info() 호출
    ↓
CCXT에서 BTCUSDT 못 찾음
    ↓
BTCUSDT → BTC/USDT:USDT 변환 시도
    ↓
시장 정보 조회 성공
```

### 4. 권장 해결 방안

#### 4.1 즉각적인 수정 (단기)
1. DB 저장 시 선물은 `BTCUSDT` 형식으로 통일
2. 웹 UI 표시도 동일하게 유지

#### 4.2 근본적인 해결 (장기)
1. symbol_utils.py를 모든 심볼 변환의 중앙 허브로 사용
2. 각 레이어별 명확한 형식 정의:
   - UI 레이어: 사용자 친화적 형식
   - 비즈니스 레이어: 표준 형식
   - API 레이어: 거래소별 형식
