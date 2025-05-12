"""
데이터베이스 관리 모듈

이 모듈은 봇의 상태, 거래 내역, 포지션 정보 등을 SQLite 데이터베이스에 저장하고 복원하는 기능을 제공합니다.
이를 통해 봇이 재시작되어도 이전 상태를 유지할 수 있습니다.
"""

import os
import json
import sqlite3
import logging
import pandas as pd
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('crypto_bot')

# 스레드 로컬 스토리지 - 각 스레드마다 고유한 데이터베이스 연결 저장
_thread_local = threading.local()

class DatabaseManager:
    """데이터베이스 관리 클래스"""
    
    def __init__(self, db_path=None):
        """
        DatabaseManager 초기화
        
        Args:
            db_path (str, optional): 데이터베이스 파일 경로
        """
        # 기본 데이터베이스 경로 설정
        if db_path is None:
            db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'db')
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, 'trading_bot.db')
        
        self.db_path = db_path
        
        # 데이터베이스 연결 및 테이블 생성
        # 스레드 안전 연결을 위해 전역 변수 대신 로컬 스레드 스토리지 사용
        conn, cursor = self._get_connection()
        self._create_tables(conn, cursor)
        
        logger.info(f"데이터베이스 관리자 초기화 완료: {self.db_path}")
    
    def _get_connection(self):
        """
        현재 스레드에 대한 데이터베이스 연결 가져오기
        
        Returns:
            tuple: (connection, cursor) 형태로 데이터베이스 연결 및 커서 반환
        """
        # 현재 스레드에 연결이 없으면 새로 생성
        if not hasattr(_thread_local, 'conn') or _thread_local.conn is None:
            try:
                # 데이터베이스 연결 생성
                _thread_local.conn = sqlite3.connect(self.db_path)
                _thread_local.conn.row_factory = sqlite3.Row  # 결과를 딕셔너리 형태로 반환
                _thread_local.cursor = _thread_local.conn.cursor()
                logger.debug(f"스레드 {threading.get_ident()} 에 데이터베이스 연결 생성: {self.db_path}")
            except sqlite3.Error as e:
                logger.error(f"데이터베이스 연결 오류: {e}")
                raise
        
        return _thread_local.conn, _thread_local.cursor
    
    def _create_tables(self, conn, cursor):
        """필요한 테이블 생성"""
        try:
            # 봇 상태 테이블
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_state (
                id INTEGER PRIMARY KEY,
                exchange_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                strategy TEXT NOT NULL,
                market_type TEXT NOT NULL,
                leverage INTEGER DEFAULT 1,
                is_running BOOLEAN DEFAULT 0,
                test_mode BOOLEAN DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                parameters TEXT,
                additional_info TEXT
            )
            ''')
            
            # 포지션 테이블
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                amount REAL NOT NULL,
                entry_price REAL NOT NULL,
                leverage INTEGER DEFAULT 1,
                opened_at TIMESTAMP NOT NULL,
                closed_at TIMESTAMP,
                pnl REAL,
                status TEXT NOT NULL,
                additional_info TEXT
            )
            ''')
            
            # 거래 내역 테이블
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                amount REAL NOT NULL,
                price REAL NOT NULL,
                cost REAL NOT NULL,
                fee REAL,
                timestamp TIMESTAMP NOT NULL,
                position_id INTEGER,
                additional_info TEXT,
                FOREIGN KEY (position_id) REFERENCES positions (id)
            )
            ''')
            
            # 설정 저장 테이블
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # 잔액 기록 테이블
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS balance_history (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                currency TEXT NOT NULL,
                amount REAL NOT NULL,
                additional_info TEXT
            )
            ''')
            
            conn.commit()
            logger.debug("데이터베이스 테이블 생성 완료")
        except sqlite3.Error as e:
            logger.error(f"테이블 생성 오류: {e}")
            conn.rollback()
            raise
    
    def close(self):
        """데이터베이스 연결 닫기"""
        if hasattr(_thread_local, 'conn') and _thread_local.conn:
            _thread_local.conn.close()
            _thread_local.conn = None
            _thread_local.cursor = None
            logger.debug(f"스레드 {threading.get_ident()} 의 데이터베이스 연결 종료")
    
    def save_bot_state(self, state_data):
        """
        봇의 현재 상태를 저장
        
        Args:
            state_data (dict): 봇 상태 정보
        
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            # 기존 상태 삭제 (항상 최신 상태만 유지)
            cursor.execute("DELETE FROM bot_state")
            
            # JSON으로 직렬화해야 하는 필드 처리
            if 'parameters' in state_data and isinstance(state_data['parameters'], dict):
                state_data['parameters'] = json.dumps(state_data['parameters'])
            
            if 'additional_info' in state_data and isinstance(state_data['additional_info'], dict):
                state_data['additional_info'] = json.dumps(state_data['additional_info'])
            
            state_data['updated_at'] = datetime.now().isoformat()
            
            # 새 상태 저장
            placeholders = ', '.join(['?'] * len(state_data))
            columns = ', '.join(state_data.keys())
            values = list(state_data.values())
            
            query = f"INSERT INTO bot_state ({columns}) VALUES ({placeholders})"
            cursor.execute(query, values)
            conn.commit()
            
            logger.info("봇 상태 저장 완료")
            return True
        except sqlite3.Error as e:
            logger.error(f"봇 상태 저장 오류: {e}")
            conn.rollback()
            return False
            
    def save_position(self, position_data):
        """
        포지션 정보 저장
        
        Args:
            position_data (dict): 포지션 정보
        
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            position_id = position_data.get('id') or position_data.get('position_id')
            
            # 이미 존재하는 포지션인지 확인
            if position_id:
                cursor.execute("SELECT id FROM positions WHERE id = ?", (position_id,))
                exists = cursor.fetchone()
                
                if exists:
                    # 기존 포지션 업데이트
                    set_clause = ", ".join([f"{k} = ?" for k in position_data.keys() if k != 'id'])
                    values = [position_data[k] for k in position_data.keys() if k != 'id']
                    values.append(position_id)
                    
                    query = f"UPDATE positions SET {set_clause} WHERE id = ?"
                    cursor.execute(query, values)
                else:
                    # 새 포지션 삽입
                    placeholders = ', '.join(['?'] * len(position_data))
                    columns = ', '.join(position_data.keys())
                    values = list(position_data.values())
                    
                    query = f"INSERT INTO positions ({columns}) VALUES ({placeholders})"
                    cursor.execute(query, values)
            else:
                # ID가 없는 새 포지션 삽입
                placeholders = ', '.join(['?'] * len(position_data))
                columns = ', '.join(position_data.keys())
                values = list(position_data.values())
                
                query = f"INSERT INTO positions ({columns}) VALUES ({placeholders})"
                cursor.execute(query, values)
            
            conn.commit()
            logger.info(f"포지션 저장 완료 - {position_data.get('symbol')}")
            return True
        except sqlite3.Error as e:
            logger.error(f"포지션 저장 오류: {e}")
            conn.rollback()
            return False
    
    def load_bot_state(self):
        """
        저장된 봇 상태 불러오기
        
        Returns:
            dict: 봇 상태 정보 (없으면 None)
        """
        try:
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            cursor.execute("SELECT * FROM bot_state ORDER BY updated_at DESC LIMIT 1")
            row = cursor.fetchone()
            
            if row:
                state = dict(row)
                
                # JSON 형식의 필드 역직렬화
                if 'parameters' in state and state['parameters']:
                    state['parameters'] = json.loads(state['parameters'])
                
                if 'additional_info' in state and state['additional_info']:
                    state['additional_info'] = json.loads(state['additional_info'])
                
                logger.info("봇 상태 불러오기 완료")
                return state
            else:
                logger.warning("저장된 봇 상태가 없습니다")
                return None
        except sqlite3.Error as e:
            logger.error(f"봇 상태 불러오기 오류: {e}")
            return None
    
    def save_position(self, position_data):
        """
        포지션 정보 저장
        
        Args:
            position_data (dict): 포지션 정보
        
        Returns:
            int: 새로 생성된 포지션 ID
        """
        try:
            # JSON으로 직렬화해야 하는 필드 처리
            if 'additional_info' in position_data and isinstance(position_data['additional_info'], dict):
                position_data['additional_info'] = json.dumps(position_data['additional_info'])
            
            # 새 포지션 저장
            placeholders = ', '.join(['?'] * len(position_data))
            columns = ', '.join(position_data.keys())
            values = list(position_data.values())
            
            query = f"INSERT INTO positions ({columns}) VALUES ({placeholders})"
            self.cursor.execute(query, values)
            self.conn.commit()
            
            position_id = self.cursor.lastrowid
            logger.info(f"포지션 저장 완료 (ID: {position_id})")
            return position_id
        except sqlite3.Error as e:
            logger.error(f"포지션 저장 오류: {e}")
            self.conn.rollback()
            return None
    
    def update_position(self, position_id, update_data):
        """
        포지션 정보 업데이트
        
        Args:
            position_id (int): 포지션 ID
            update_data (dict): 업데이트할 정보
        
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            # JSON으로 직렬화해야 하는 필드 처리
            if 'additional_info' in update_data and isinstance(update_data['additional_info'], dict):
                update_data['additional_info'] = json.dumps(update_data['additional_info'])
            
            # 업데이트 쿼리 구성
            set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
            values = list(update_data.values())
            values.append(position_id)
            
            query = f"UPDATE positions SET {set_clause} WHERE id = ?"
            self.cursor.execute(query, values)
            self.conn.commit()
            
            logger.info(f"포지션 업데이트 완료 (ID: {position_id})")
            return True
        except sqlite3.Error as e:
            logger.error(f"포지션 업데이트 오류: {e}")
            self.conn.rollback()
            return False
    
    def get_open_positions(self, symbol=None):
        """
        열린 포지션 가져오기
        
        Args:
            symbol (str, optional): 특정 심볼 필터링
        
        Returns:
            list: 포지션 정보 목록
        """
        try:
            query = "SELECT * FROM positions WHERE status = 'open'"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            positions = []
            for row in rows:
                position = dict(row)
                
                # JSON 필드 역직렬화
                if 'additional_info' in position and position['additional_info']:
                    position['additional_info'] = json.loads(position['additional_info'])
                
                positions.append(position)
            
            return positions
        except sqlite3.Error as e:
            logger.error(f"열린 포지션 조회 오류: {e}")
            return []
    
    def save_trade(self, trade_data):
        """
        거래 내역 저장
        
        Args:
            trade_data (dict): 거래 정보
        
        Returns:
            int: 새로 생성된 거래 ID
        """
        try:
            # JSON으로 직렬화해야 하는 필드 처리
            if 'additional_info' in trade_data and isinstance(trade_data['additional_info'], dict):
                trade_data['additional_info'] = json.dumps(trade_data['additional_info'])
            
            # 새 거래 저장
            placeholders = ', '.join(['?'] * len(trade_data))
            columns = ', '.join(trade_data.keys())
            values = list(trade_data.values())
            
            query = f"INSERT INTO trades ({columns}) VALUES ({placeholders})"
            self.cursor.execute(query, values)
            self.conn.commit()
            
            trade_id = self.cursor.lastrowid
            logger.info(f"거래 내역 저장 완료 (ID: {trade_id})")
            return trade_id
        except sqlite3.Error as e:
            logger.error(f"거래 내역 저장 오류: {e}")
            self.conn.rollback()
            return None
    
    def get_trades(self, symbol=None, limit=50, offset=0):
        """
        거래 내역 가져오기
        
        Args:
            symbol (str, optional): 특정 심볼 필터링
            limit (int, optional): 반환할 최대 결과 수
            offset (int, optional): 결과 오프셋
        
        Returns:
            list: 거래 내역 목록
        """
        try:
            query = "SELECT * FROM trades"
            params = []
            
            if symbol:
                query += " WHERE symbol = ?"
                params.append(symbol)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            trades = []
            for row in rows:
                trade = dict(row)
                
                # JSON 필드 역직렬화
                if 'additional_info' in trade and trade['additional_info']:
                    trade['additional_info'] = json.loads(trade['additional_info'])
                
                trades.append(trade)
            
            return trades
        except sqlite3.Error as e:
            logger.error(f"거래 내역 조회 오류: {e}")
            return []
    
    def load_trades(self, limit=20):
        """
        최근 거래 내역 로드 (API용)
        
        Args:
            limit (int, optional): 가져올 거래 내역 수
            
        Returns:
            list: 거래 내역 목록
        """
        try:
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            # 거래 내역 쿼리
            query = "SELECT * FROM trades ORDER BY timestamp DESC"
            params = []
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            trades = []
            for row in rows:
                trade = dict(row)
                
                # JSON 필드 역직렬화
                if 'additional_info' in trade and trade['additional_info']:
                    try:
                        trade['additional_info'] = json.loads(trade['additional_info'])
                    except json.JSONDecodeError:
                        pass
                
                # 필드명 변환 (API 응답 형식에 맞게)
                if 'side' in trade:
                    trade['type'] = trade['side']  # side -> type
                if 'timestamp' in trade:
                    trade['datetime'] = trade['timestamp']  # timestamp -> datetime
                
                trades.append(trade)
            
            return trades
        except sqlite3.Error as e:
            logger.error(f"거래 내역 로드 오류: {e}")
            return []
    
    def load_positions(self):
        """
        현재 열린 포지션 정보 로드 (API용)
        
        Returns:
            list: 포지션 정보 목록
        """
        try:
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            # 열린 포지션 쿼리
            cursor.execute("SELECT * FROM positions WHERE status = 'open' ORDER BY opened_at DESC")
            rows = cursor.fetchall()
            
            positions = []
            for row in rows:
                position = dict(row)
                
                # JSON 필드 역직렬화
                if 'additional_info' in position and position['additional_info']:
                    try:
                        position['additional_info'] = json.loads(position['additional_info'])
                    except json.JSONDecodeError:
                        pass
                
                # 필드명 변환 (API 응답 형식에 맞게)
                if 'side' in position:
                    position['type'] = position['side']
                if 'entry_price' in position:
                    position['entry_price'] = float(position['entry_price'])
                if 'amount' in position:
                    position['amount'] = float(position['amount'])
                if 'opened_at' in position:
                    position['open_time'] = position['opened_at']
                
                # 현재 가격과 수익 정보 가져오기 (실제로는 거래소 API에서 가져와야 함)
                position['current_price'] = position.get('entry_price', 0)  # 예시 값
                position['profit'] = 0  # 예시 값
                position['profit_percent'] = 0  # 예시 값
                
                positions.append(position)
            
            return positions
        except sqlite3.Error as e:
            logger.error(f"포지션 로드 오류: {e}")
            return []
    
    def load_performance_stats(self):
        """
        거래 성과 통계 로드 (API용)
        
        Returns:
            dict: 성과 통계 정보
        """
        try:
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            # 모든 거래 내역 가져오기
            cursor.execute("SELECT * FROM trades")
            trades = cursor.fetchall()
            
            # 통계 계산
            total_profit = 0
            win_count = 0
            loss_count = 0
            total_count = len(trades)
            
            for trade in trades:
                profit = trade.get('pnl', 0)
                if profit > 0:
                    win_count += 1
                    total_profit += profit
                elif profit < 0:
                    loss_count += 1
                    total_profit += profit
            
            # 승률 계산
            win_rate = (win_count / total_count * 100) if total_count > 0 else 0
            # 평균 수익 계산
            avg_profit = (total_profit / total_count) if total_count > 0 else 0
            
            return {
                'total_profit': f"{total_profit:.2f}",
                'win_rate': f"{win_rate:.1f}%",
                'avg_profit': f"{avg_profit:.2f}",
                'total_trades': total_count,
                'win_trades': win_count,
                'loss_trades': loss_count
            }
        except sqlite3.Error as e:
            logger.error(f"성과 통계 로드 오류: {e}")
            return {
                'total_profit': '0.00',
                'win_rate': '0%',
                'avg_profit': '0.00',
                'total_trades': 0,
                'win_trades': 0,
                'loss_trades': 0
            }
    
    def save_setting(self, key, value):
        """
        설정 저장
        
        Args:
            key (str): 설정 키
            value (any): 설정 값 (JSON으로 직렬화됨)
        
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 값을 JSON으로 직렬화
            json_value = json.dumps(value)
            
            # UPSERT 쿼리 (SQLite 3.24.0 이상 지원)
            query = """
            INSERT INTO settings (key, value, updated_at) 
            VALUES (?, ?, ?) 
            ON CONFLICT(key) DO UPDATE SET 
                value = excluded.value,
                updated_at = excluded.updated_at
            """
            
            updated_at = datetime.now().isoformat()
            self.cursor.execute(query, (key, json_value, updated_at))
            self.conn.commit()
            
            logger.debug(f"설정 저장 완료: {key}")
            return True
        except sqlite3.Error as e:
            logger.error(f"설정 저장 오류: {e}")
            self.conn.rollback()
            return False
    
    def get_setting(self, key, default=None):
        """
        설정 불러오기
        
        Args:
            key (str): 설정 키
            default (any, optional): 설정이 없을 경우 기본값
        
        Returns:
            any: 설정 값 (없으면 기본값)
        """
        try:
            self.cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = self.cursor.fetchone()
            
            if row:
                # JSON 역직렬화
                return json.loads(row['value'])
            else:
                return default
        except sqlite3.Error as e:
            logger.error(f"설정 불러오기 오류: {e}")
            return default
    
    def save_balance(self, currency, amount, additional_info=None):
        """
        잔액 정보 저장
        
        Args:
            currency (str): 통화 (예: BTC, USDT)
            amount (float): 잔액
            additional_info (dict, optional): 추가 정보
        
        Returns:
            bool: 저장 성공 여부
        """
        try:
            timestamp = datetime.now().isoformat()
            
            # 추가 정보가 있으면 JSON으로 직렬화
            json_info = None
            if additional_info:
                json_info = json.dumps(additional_info)
            
            self.cursor.execute(
                "INSERT INTO balance_history (timestamp, currency, amount, additional_info) VALUES (?, ?, ?, ?)",
                (timestamp, currency, amount, json_info)
            )
            self.conn.commit()
            
            logger.debug(f"잔액 기록 저장 완료: {currency} {amount}")
            return True
        except sqlite3.Error as e:
            logger.error(f"잔액 기록 저장 오류: {e}")
            self.conn.rollback()
            return False
    
    def get_latest_balance(self, currency=None):
        """
        최신 잔액 정보 가져오기
        
        Args:
            currency (str, optional): 특정 통화 필터링
        
        Returns:
            dict: 통화별 최신 잔액 정보
        """
        try:
            query = """
            SELECT b1.* 
            FROM balance_history b1
            INNER JOIN (
                SELECT currency, MAX(timestamp) as max_time
                FROM balance_history
                GROUP BY currency
            ) b2 ON b1.currency = b2.currency AND b1.timestamp = b2.max_time
            """
            
            params = []
            if currency:
                query += " WHERE b1.currency = ?"
                params.append(currency)
            
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            balance = {}
            for row in rows:
                bal = dict(row)
                
                # JSON 필드 역직렬화
                if 'additional_info' in bal and bal['additional_info']:
                    bal['additional_info'] = json.loads(bal['additional_info'])
                
                balance[bal['currency']] = bal
            
            return balance
        except sqlite3.Error as e:
            logger.error(f"최신 잔액 조회 오류: {e}")
            return {}
    
    def execute_query(self, query, params=None):
        """
        직접 쿼리 실행 (고급 사용)
        
        Args:
            query (str): SQL 쿼리
            params (tuple, optional): 쿼리 파라미터
        
        Returns:
            list: 결과 행 목록
        """
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            if query.strip().upper().startswith(('SELECT', 'PRAGMA')):
                return [dict(row) for row in self.cursor.fetchall()]
            else:
                self.conn.commit()
                return []
        except sqlite3.Error as e:
            logger.error(f"쿼리 실행 오류: {e}")
            if not query.strip().upper().startswith(('SELECT', 'PRAGMA')):
                self.conn.rollback()
            return []
