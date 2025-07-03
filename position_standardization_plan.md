# 포지션 데이터 구조 표준화 계획

## 현재 상황 분석

### 1. Position 모델 클래스 (src/models/position.py)
- dataclass로 구현된 완전한 Position 모델 존재
- to_dict() 및 from_dict() 메서드 구현
- 필드: id, symbol, side, amount, entry_price, status 등

### 2. 문제점
- 대부분의 코드에서 Position 클래스 대신 딕셔너리 사용
- 필드명 불일치:
  - amount vs contracts vs quantity
  - opened_at vs created_at
  - pnl vs profit vs unrealized_profit

### 3. 포지션 생성 위치
- OrderExecutor: 딕셔너리로 생성
- PortfolioManager: 딕셔너리 받아서 저장
- DatabaseManager: 딕셔너리로 저장/조회
- ExchangeAPI: 딕셔너리 반환

## 표준화 방안

### 1단계: 필드명 통일
- 수량: `amount` (기본), `quantity`는 alias로 처리
- 생성 시간: `opened_at`
- 손익: `pnl` (realized/unrealized 구분)
- 상태: `status` ('open', 'closed')

### 2단계: Position 클래스 사용 확대
1. OrderExecutor에서 Position 객체 생성
2. PortfolioManager에서 Position 객체 관리
3. DatabaseManager에서 Position 객체 변환
4. API 응답에서는 to_dict() 사용

### 3단계: 마이그레이션
1. Position 클래스에 backward compatibility 메서드 추가
2. 점진적으로 딕셔너리 → Position 객체로 변경
3. 테스트 코드 추가

## 구현 순서
1. Position 클래스 개선 (backward compatibility)
2. OrderExecutor 수정
3. PortfolioManager 수정
4. DatabaseManager 수정
5. 테스트 및 검증
