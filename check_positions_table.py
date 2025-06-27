import sqlite3

# DB 연결
conn = sqlite3.connect('crypto_trading.db')
cursor = conn.cursor()

# positions 테이블 구조 확인
cursor.execute("PRAGMA table_info(positions)")
columns = cursor.fetchall()

print("=== positions 테이블 구조 ===")
for col in columns:
    print(f"{col[1]} - {col[2]}")

# stop_loss_orders 테이블 존재 확인
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stop_loss_orders'")
if cursor.fetchone():
    print("\n=== stop_loss_orders 테이블 구조 ===")
    cursor.execute("PRAGMA table_info(stop_loss_orders)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"{col[1]} - {col[2]}")
else:
    print("\n❌ stop_loss_orders 테이블이 존재하지 않습니다.")

conn.close()
