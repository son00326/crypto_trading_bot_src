# EC2 업데이트 가이드

## 1. 코드 업데이트
```bash
cd /home/ubuntu/crypto_trading_bot_src
git pull origin main
```

## 2. DB 마이그레이션 (중요!)
기존 DB에 contractSize 컬럼을 추가해야 합니다:

```bash
# Python으로 직접 실행
python3 -c "
import sqlite3
conn = sqlite3.connect('data/db/trading_bot.db')
cursor = conn.cursor()
try:
    cursor.execute('ALTER TABLE positions ADD COLUMN contractSize REAL DEFAULT 1.0')
    conn.commit()
    print('✅ contractSize 컬럼 추가 완료')
except Exception as e:
    print(f'⚠️  {e}')
conn.close()
"
```

## 3. 서비스 재시작
```bash
sudo systemctl restart trading-bot
sudo systemctl restart bot-api
```

## 4. 확인
```bash
# 로그 확인
sudo journalctl -u trading-bot -f

# DB 스키마 확인
sqlite3 data/db/trading_bot.db "PRAGMA table_info(positions);" | grep contractSize
```

## 수정된 파일 목록
- `src/models/position.py` - contract_size 필드 추가
- `src/db_manager.py` - DB 스키마에 contractSize 컬럼 추가
