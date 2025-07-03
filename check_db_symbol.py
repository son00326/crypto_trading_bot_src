#!/usr/bin/env python3

import sqlite3
import os
import json

# DB 파일 경로
db_path = 'data/trading_bot.db'

if not os.path.exists(db_path):
    print(f"DB 파일이 없습니다: {db_path}")
    exit(1)

# DB 연결
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 포지션 테이블 확인
print("=== 포지션 테이블 데이터 확인 ===\n")

# 최근 10개 포지션 조회
cursor.execute("""
    SELECT id, symbol, side, amount, contracts, status, additional_info 
    FROM positions 
    ORDER BY id DESC 
    LIMIT 10
""")

rows = cursor.fetchall()

if not rows:
    print("포지션 데이터가 없습니다.")
else:
    print("ID | Symbol | Side | Amount | Contracts | Status | Market Type")
    print("-" * 80)
    
    for row in rows:
        id, symbol, side, amount, contracts, status, additional_info = row
        
        # additional_info에서 market_type 추출
        market_type = 'unknown'
        if additional_info:
            try:
                info = json.loads(additional_info)
                market_type = info.get('market_type', 'unknown')
            except:
                pass
        
        print(f"{id:3d} | {symbol:10s} | {side:4s} | {amount:7.4f} | {contracts:7.4f} | {status:6s} | {market_type}")

# 테이블 구조 확인
print("\n\n=== positions 테이블 구조 ===")
cursor.execute("PRAGMA table_info(positions)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]:20s} {col[2]:10s} {'NOT NULL' if col[3] else 'NULL':<10s} {f'DEFAULT {col[4]}' if col[4] else ''}")

conn.close()
