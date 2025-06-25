# Trading Bot Test Guide

## 강제 거래 테스트 스크립트 사용법

트레이딩 봇의 거래 신호 처리와 주문 실행을 테스트하기 위한 가이드입니다.

### 1. 기본 사용법

```bash
# 테스트 모드로 매수 신호 테스트
python force_trade_test.py --test-mode

# 실제 거래 모드로 매수 신호 테스트 (주의!)
python force_trade_test.py

# 매도 신호 테스트
python force_trade_test.py --signal sell --test-mode

# 매수 후 매도 연속 테스트
python force_trade_test.py --signal both --test-mode --delay 10
```

### 2. 주요 옵션

- `--signal`: 테스트할 신호 유형 (buy, sell, both)
- `--confidence`: 신호 신뢰도 (0.0 ~ 1.0, 기본값: 0.8)
- `--exchange`: 거래소 ID (기본값: binance)
- `--symbol`: 거래 심볼 (기본값: BTC/USDT)
- `--test-mode`: 테스트 모드 활성화 (실제 거래 안함)
- `--delay`: 신호 간 대기 시간 (초, 기본값: 5)

### 3. 테스트 시나리오

#### 시나리오 1: 기본 매수 테스트
```bash
python force_trade_test.py --test-mode --confidence 0.9
```

#### 시나리오 2: 낮은 신뢰도 테스트 (리스크 매니저 검증)
```bash
python force_trade_test.py --test-mode --confidence 0.3
```

#### 시나리오 3: 전체 거래 사이클 테스트
```bash
python force_trade_test.py --signal both --test-mode --delay 5
```

### 4. 로그 확인

테스트 실행 후 로그 파일에서 상세 내용을 확인할 수 있습니다:

```bash
# 최신 로그 확인
tail -f logs/trading_bot_*.log

# 오류 로그만 확인
grep ERROR logs/trading_bot_*.log

# 주문 관련 로그 확인
grep "주문" logs/trading_bot_*.log
```

### 5. 주의사항

⚠️ **중요**: 실제 거래 모드로 테스트하기 전에 반드시:
1. API 키 권한 확인
2. 계정 잔액 확인
3. 리스크 설정 확인
4. 테스트 모드에서 충분히 검증

### 6. 예상 결과

성공적인 테스트 시:
- ✅ API 권한 확인 완료
- ✅ 리스크 평가 통과
- ✅ 주문 실행 성공
- ✅ 포트폴리오 업데이트 완료

실패 시 확인 사항:
- ❌ API 키 설정 확인
- ❌ 거래 권한 확인
- ❌ 잔액 부족
- ❌ 리스크 한도 초과

### 7. 문제 해결

#### API 권한 오류
```
ERROR: API 키에 거래 권한이 없습니다
```
→ 바이낸스에서 API 키의 거래 권한 활성화 필요

#### 잔액 부족
```
WARNING: 계정 잔액 부족
```
→ 테스트 모드 사용 또는 계정에 자금 입금

#### 리스크 한도 초과
```
WARNING: 일일 거래 한도 초과
```
→ 리스크 설정 조정 또는 다음 날 테스트

### 8. 봇 정상 작동 확인 체크리스트

- [ ] API 연결 성공
- [ ] API 권한 확인 (거래 권한 필수)
- [ ] 시장 데이터 수신 정상
- [ ] 전략 신호 생성 확인
- [ ] 리스크 평가 통과
- [ ] 주문 실행 성공 (테스트 모드)
- [ ] 포트폴리오 업데이트 확인
- [ ] 로그 기록 정상
