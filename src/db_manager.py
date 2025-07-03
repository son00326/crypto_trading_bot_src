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
from src.db_connection_manager import get_db_connection
from contextlib import contextmanager


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
        
        # 로거를 먼저 초기화
        self.logger = logging.getLogger('crypto_bot')
        
        # 데이터베이스 연결 및 테이블 생성
        # 스레드 안전 연결을 위해 전역 변수 대신 로컬 스레드 스토리지 사용
        with get_db_connection(self.db_path) as (conn, cursor):
            self._create_tables(conn, cursor)
            conn.commit()
        
        self.logger.info(f"데이터베이스 관리자 초기화 완료: {self.db_path}")
    
    def _get_connection(self):
        """
        데이터베이스 연결 가져오기 (레거시 호환성을 위해 유지)
        
        Returns:
            tuple: (connection, cursor) - 주의: 이 연결은 수동으로 닫아야 함
        """
        # check_same_thread=False로 멀티스레드 지원
        conn = sqlite3.connect(
            self.db_path, 
            check_same_thread=False,
            timeout=30.0
        )
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # WAL 모드 활성화
        cursor.execute("PRAGMA journal_mode=WAL")
        
        return conn, cursor
    
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
                contracts REAL NOT NULL,
                notional REAL,
                entry_price REAL NOT NULL,
                mark_price REAL,
                liquidation_price REAL,
                unrealized_pnl REAL,
                margin_mode TEXT DEFAULT 'cross',
                leverage INTEGER DEFAULT 1,
                opened_at TIMESTAMP NOT NULL,
                closed_at TIMESTAMP,
                pnl REAL,
                status TEXT NOT NULL,
                additional_info TEXT,
                raw_data TEXT,
                contractSize REAL DEFAULT 1.0,
                stop_loss_price REAL,
                take_profit_price REAL,
                stop_loss_order_id TEXT,
                take_profit_order_id TEXT
            )
            ''')
            
            # 기존 positions 테이블 마이그레이션
            # amount 컬럼이 있는 경우 contracts로 이름 변경
            try:
                cursor.execute("PRAGMA table_info(positions)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'amount' in columns and 'contracts' not in columns:
                    self.logger.info("positions 테이블 마이그레이션: amount -> contracts")
                    cursor.execute('''
                        ALTER TABLE positions RENAME COLUMN amount TO contracts
                    ''')
                
                # 새로운 컬럼들 추가 (이미 존재하면 무시)
                new_columns = [
                    ('notional', 'REAL'),
                    ('mark_price', 'REAL'),
                    ('liquidation_price', 'REAL'),
                    ('unrealized_pnl', 'REAL'),
                    ('margin_mode', "TEXT DEFAULT 'cross'"),
                    ('contractSize', 'REAL DEFAULT 1.0'),
                    ('stop_loss_price', 'REAL'),
                    ('take_profit_price', 'REAL'),
                    ('stop_loss_order_id', 'TEXT'),
                    ('take_profit_order_id', 'TEXT')
                ]
                
                for col_name, col_type in new_columns:
                    if col_name not in columns:
                        try:
                            cursor.execute(f'ALTER TABLE positions ADD COLUMN {col_name} {col_type}')
                            self.logger.info(f"positions 테이블에 {col_name} 컬럼 추가")
                        except sqlite3.OperationalError:
                            # 컬럼이 이미 존재하는 경우 무시
                            pass
            except Exception as e:
                self.logger.warning(f"positions 테이블 마이그레이션 중 경고: {e}")
            
            # raw_data 컬럼 추가
            cursor.execute("PRAGMA table_info(positions)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'raw_data' not in columns:
                cursor.execute('ALTER TABLE positions ADD COLUMN raw_data TEXT')
                conn.commit()
                self.logger.info("positions 테이블에 raw_data 컬럼 추가됨")
            
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
            
            # 가격 데이터 테이블
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                UNIQUE(symbol)
            )
            ''')
            
            # 주문 테이블
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                type TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                additional_info TEXT
            )
            ''')
            
            # 손절/익절 주문 테이블
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS stop_loss_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                order_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                order_type TEXT NOT NULL,  -- 'stop_loss' or 'take_profit'
                trigger_price REAL NOT NULL,
                amount REAL NOT NULL,
                side TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',  -- 'active', 'triggered', 'cancelled'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                triggered_at TIMESTAMP,
                cancelled_at TIMESTAMP,
                raw_data TEXT,
                FOREIGN KEY (position_id) REFERENCES positions (id)
            )
            ''')
            
            # 잔액 테이블
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency TEXT NOT NULL,
                amount REAL NOT NULL,
                balance_type TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                additional_info TEXT,
                UNIQUE(currency, balance_type)
            )
            ''')
            
            # 사용자 테이블 (로그인 기능용)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT UNIQUE,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            conn.commit()
            self.logger.debug("데이터베이스 테이블 생성 완료")
        except sqlite3.Error as e:
            self.logger.error(f"테이블 생성 오류: {e}")
            conn.rollback()
            raise
    
    def close(self):
        """데이터베이스 연결 닫기"""
        if hasattr(_thread_local, 'conn') and _thread_local.conn:
            _thread_local.conn.close()
            _thread_local.conn = None
            _thread_local.cursor = None
            self.logger.debug(f"스레드 {threading.get_ident()} 의 데이터베이스 연결 종료")
    
    # 사용자 관련 메서드 (로그인 기능용)
    def create_users_table(self):
        """사용자 테이블 생성 (이미 _create_tables에서 처리)"""
        pass  # 호환성을 위해 남겨둠
    
    def get_user_by_id(self, user_id):
        """
        ID로 사용자 정보 조회
        
        Args:
            user_id (int): 사용자 ID
            
        Returns:
            dict: 사용자 정보, 없으면 None
        """
        try:
            conn, cursor = self._get_connection()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            user_data = cursor.fetchone()
            
            if user_data:
                # 타입 명시적으로 처리
                return {
                    'id': int(user_data['id']),
                    'username': str(user_data['username']),
                    'password_hash': str(user_data['password_hash']),
                    'email': user_data['email'],
                    'is_admin': bool(user_data['is_admin']),
                    'created_at': user_data['created_at']
                }
            return None
        except sqlite3.Error as e:
            self.logger.error(f"사용자 조회 오류 (ID): {e}")
            return None
    
    def get_user_by_username(self, username):
        """
        사용자명으로 사용자 정보 조회
        
        Args:
            username (str): 사용자명
            
        Returns:
            dict: 사용자 정보, 없으면 None
        """
        try:
            conn, cursor = self._get_connection()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user_data = cursor.fetchone()
            
            if user_data:
                # 타입 명시적으로 처리
                return {
                    'id': int(user_data['id']),
                    'username': str(user_data['username']),
                    'password_hash': str(user_data['password_hash']),
                    'email': user_data['email'],
                    'is_admin': bool(user_data['is_admin']),
                    'created_at': user_data['created_at']
                }
            return None
        except sqlite3.Error as e:
            self.logger.error(f"사용자 조회 오류 (사용자명): {e}")
            return None
    
    def create_user(self, username, password_hash, email=None, is_admin=False):
        """
        새 사용자 생성
        
        Args:
            username (str): 사용자명
            password_hash (str): 암호화된 비밀번호
            email (str, optional): 이메일 주소
            is_admin (bool, optional): 관리자 여부
            
        Returns:
            bool: 생성 성공 여부
        """
        try:
            conn, cursor = self._get_connection()
            cursor.execute(
                'INSERT INTO users (username, password_hash, email, is_admin) VALUES (?, ?, ?, ?)',
                (username, password_hash, email, int(is_admin))
            )
            conn.commit()
            self.logger.info(f"새 사용자 생성 완료: {username}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"사용자 생성 오류: {e}")
            conn.rollback()
            return False
            
    def update_user(self, user_id, username=None, password_hash=None, email=None, is_admin=None):
        """
        사용자 정보 업데이트
        
        Args:
            user_id (int): 사용자 ID
            username (str, optional): 사용자명
            password_hash (str, optional): 암호화된 비밀번호
            email (str, optional): 이메일 주소
            is_admin (bool, optional): 관리자 여부
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            conn, cursor = self._get_connection()
            current_user = self.get_user_by_id(user_id)
            
            if not current_user:
                self.logger.warning(f"업데이트할 사용자를 찾을 수 없음: ID {user_id}")
                return False
            
            # 업데이트할 필드 구성
            updates = []
            values = []
            
            if username is not None:
                updates.append("username = ?")
                values.append(username)
            
            if password_hash is not None:
                updates.append("password_hash = ?")
                values.append(password_hash)
            
            if email is not None:
                updates.append("email = ?")
                values.append(email)
            
            if is_admin is not None:
                updates.append("is_admin = ?")
                values.append(int(is_admin))
            
            if not updates:
                self.logger.warning("업데이트할 필드가 없습니다.")
                return False
            
            # 업데이트 쿼리 실행
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            values.append(user_id)
            
            cursor.execute(query, values)
            conn.commit()
            self.logger.info(f"사용자 정보 업데이트 완료: ID {user_id}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"사용자 업데이트 오류: {e}")
            conn.rollback()
            return False
            
    def delete_user(self, user_id):
        """
        사용자 삭제
        
        Args:
            user_id (int): 삭제할 사용자 ID
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            conn, cursor = self._get_connection()
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                self.logger.info(f"사용자 삭제 완료: ID {user_id}")
                return True
            else:
                self.logger.warning(f"삭제할 사용자를 찾을 수 없음: ID {user_id}")
                return False
        except sqlite3.Error as e:
            self.logger.error(f"사용자 삭제 오류: {e}")
            conn.rollback()
            return False
    
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
            
            # 복잡한 객체를 additional_info에 저장
            additional_info = state_data.get('additional_info', {})
            if not isinstance(additional_info, dict):
                additional_info = {}
            
            # positions와 current_trade_info를 additional_info로 이동
            if 'positions' in state_data:
                additional_info['positions'] = state_data.pop('positions')
            
            if 'current_trade_info' in state_data:
                additional_info['current_trade_info'] = state_data.pop('current_trade_info')
            
            # additional_info가 있으면 다시 state_data에 설정
            if additional_info:
                state_data['additional_info'] = additional_info
            
            # JSON으로 직렬화해야 하는 필드 처리
            if 'parameters' in state_data and isinstance(state_data['parameters'], dict):
                state_data['parameters'] = json.dumps(state_data['parameters'])
            
            # strategy_params를 parameters로 매핑 (역호환성 유지)
            if 'strategy_params' in state_data and 'parameters' not in state_data:
                if isinstance(state_data['strategy_params'], dict):
                    state_data['parameters'] = json.dumps(state_data['strategy_params'])
                else:
                    state_data['parameters'] = state_data['strategy_params']
            
            if 'additional_info' in state_data and isinstance(state_data['additional_info'], dict):
                state_data['additional_info'] = json.dumps(state_data['additional_info'])
            
            state_data['updated_at'] = datetime.now().isoformat()
            
            # bot_state 테이블의 컬럼만 남기기
            valid_columns = [
                'exchange_id', 'symbol', 'timeframe', 'strategy', 'market_type', 
                'leverage', 'is_running', 'test_mode', 'updated_at', 
                'parameters', 'additional_info'
            ]
            
            filtered_state = {}
            for col in valid_columns:
                if col in state_data:
                    filtered_state[col] = state_data[col]
            
            # 새 상태 저장
            placeholders = ', '.join(['?'] * len(filtered_state))
            columns = ', '.join(filtered_state.keys())
            values = list(filtered_state.values())
            
            query = f"INSERT INTO bot_state ({columns}) VALUES ({placeholders})"
            cursor.execute(query, values)
            conn.commit()
            
            self.logger.info("봇 상태 저장 완료")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"봇 상태 저장 오류: {e}")
            conn.rollback()
            return False
            
    def save_position(self, position_data):
        """
        단일 포지션 저장
        
        Args:
            position_data (dict): 포지션 데이터
        
        Returns:
            int: 포지션 ID
        """
        try:
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            # camelCase -> snake_case 필드명 변환 매핑
            field_mapping = {
                'entryPrice': 'entry_price',
                'markPrice': 'mark_price',
                'liquidationPrice': 'liquidation_price',
                'unrealizedPnl': 'unrealized_pnl',
                'marginMode': 'margin_mode',
                'contractSize': 'contractSize',  # 이미 적절한 형식
            }
            
            # 필드명 변환
            converted_position = {}
            for key, value in position_data.items():
                # 매핑이 있으면 변환, 없으면 그대로 사용
                new_key = field_mapping.get(key, key)
                converted_position[new_key] = value
            
            # opened_at 필드가 없으면 현재 시간 추가
            if 'opened_at' not in converted_position:
                converted_position['opened_at'] = datetime.now().isoformat()
            
            # status 필드가 없으면 'open' 추가
            if 'status' not in converted_position:
                converted_position['status'] = 'open'
            
            # JSON으로 직렬화해야 하는 필드 처리
            if 'additional_info' in converted_position and isinstance(converted_position['additional_info'], dict):
                converted_position['additional_info'] = json.dumps(converted_position['additional_info'])
            
            # raw_data 필드도 JSON으로 직렬화
            if 'raw_data' in converted_position:
                if isinstance(converted_position['raw_data'], (dict, list)):
                    converted_position['raw_data'] = json.dumps(converted_position['raw_data'])
                elif converted_position['raw_data'] is not None and not isinstance(converted_position['raw_data'], str):
                    converted_position['raw_data'] = str(converted_position['raw_data'])
            
            # 모든 필드의 데이터 타입 검증 및 변환
            for key, value in list(converted_position.items()):
                if value is None:
                    continue  # NULL은 SQLite에서 지원
                elif isinstance(value, (dict, list)):
                    # 복잡한 데이터 구조는 JSON으로 직렬화
                    converted_position[key] = json.dumps(value)
                elif isinstance(value, bool):
                    # bool은 정수로 변환 (SQLite는 boolean 타입이 없음)
                    converted_position[key] = int(value)
                elif not isinstance(value, (str, int, float)):
                    # 지원되지 않는 타입은 문자열로 변환
                    self.logger.warning(f"포지션 저장: {key} 필드의 타입 {type(value)}를 문자열로 변환")
                    converted_position[key] = str(value)
            
            # 테이블 스키마와 맞지 않는 키 제거
            valid_columns = ['id', 'symbol', 'side', 'contracts', 'notional',
                           'entry_price', 'mark_price', 'liquidation_price', 
                           'unrealized_pnl', 'margin_mode', 'leverage', 
                           'opened_at', 'closed_at', 'pnl', 'status', 
                           'additional_info', 'raw_data', 'contractSize',
                           'stop_loss_price', 'take_profit_price', 
                           'stop_loss_order_id', 'take_profit_order_id']
            
            invalid_keys = [key for key in converted_position.keys() if key not in valid_columns]
            if invalid_keys:
                self.logger.warning(f"유효하지 않은 키 발견: {invalid_keys}. 제거합니다.")
                for key in invalid_keys:
                    del converted_position[key]
            
            # 포지션 존재 여부 확인
            query = "SELECT id FROM positions WHERE symbol = ? AND side = ? AND status = 'open'"
            cursor.execute(query, (converted_position.get('symbol'), converted_position.get('side')))
            existing = cursor.fetchone()
            
            if existing:
                # 기존 포지션 업데이트
                update_fields = [f"{k} = ?" for k in converted_position.keys() if k != 'id']
                query = f"UPDATE positions SET {', '.join(update_fields)} WHERE id = ?"
                values = [converted_position[k] for k in converted_position.keys() if k != 'id'] + [existing[0]]
                cursor.execute(query, values)
                position_id = existing[0]
            else:
                # 새 포지션 삽입
                fields = list(converted_position.keys())
                placeholders = ['?' for _ in fields]
                query = f"INSERT INTO positions ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
                values = [converted_position[k] for k in fields]
                cursor.execute(query, values)
                position_id = cursor.lastrowid
        
            conn.commit()
            return position_id
        
        except Exception as e:
            self.logger.error(f"포지션 저장 오류: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()
    
    def save_positions(self, positions):
        """
        여러 포지션을 한번에 저장
        
        Args:
            positions (list): 포지션 데이터 리스트
        
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            # 기존 포지션 삭제
            cursor.execute("DELETE FROM positions WHERE 1=1")
            
            # camelCase -> snake_case 필드명 변환 매핑
            field_mapping = {
                'entryPrice': 'entry_price',
                'markPrice': 'mark_price',
                'liquidationPrice': 'liquidation_price',
                'unrealizedPnl': 'unrealized_pnl',
                'marginMode': 'margin_mode',
                'contractSize': 'contractSize',  # 이미 적절한 형식
            }
            
            # 새 포지션 저장
            for position in positions:
                # 필드명 변환
                converted_position = {}
                for key, value in position.items():
                    # 매핑이 있으면 변환, 없으면 그대로 사용
                    new_key = field_mapping.get(key, key)
                    converted_position[new_key] = value
                
                # opened_at 필드가 없으면 현재 시간 추가
                if 'opened_at' not in converted_position:
                    converted_position['opened_at'] = datetime.now().isoformat()
                
                # status 필드가 없으면 'open' 추가
                if 'status' not in converted_position:
                    converted_position['status'] = 'open'
                
                # JSON으로 직렬화해야 하는 필드 처리
                if 'additional_info' in converted_position and isinstance(converted_position['additional_info'], dict):
                    converted_position['additional_info'] = json.dumps(converted_position['additional_info'])
                
                # raw_data 필드도 JSON으로 직렬화
                if 'raw_data' in converted_position:
                    if isinstance(converted_position['raw_data'], (dict, list)):
                        converted_position['raw_data'] = json.dumps(converted_position['raw_data'])
                    elif converted_position['raw_data'] is not None and not isinstance(converted_position['raw_data'], str):
                        converted_position['raw_data'] = str(converted_position['raw_data'])
                
                # 모든 필드의 데이터 타입 검증 및 변환
                for key, value in list(converted_position.items()):
                    if value is None:
                        continue  # NULL은 SQLite에서 지원
                    elif isinstance(value, (dict, list)):
                        # 복잡한 데이터 구조는 JSON으로 직렬화
                        converted_position[key] = json.dumps(value)
                    elif isinstance(value, bool):
                        # bool은 정수로 변환 (SQLite는 boolean 타입이 없음)
                        converted_position[key] = int(value)
                    elif not isinstance(value, (str, int, float)):
                        # 지원되지 않는 타입은 문자열로 변환
                        self.logger.warning(f"포지션 저장: {key} 필드의 타입 {type(value)}를 문자열로 변환")
                        converted_position[key] = str(value)
                
                # 테이블 스키마와 맞지 않는 키 제거
                valid_columns = ['id', 'symbol', 'side', 'contracts', 'notional',
                               'entry_price', 'mark_price', 'liquidation_price', 
                               'unrealized_pnl', 'margin_mode', 'leverage', 
                               'opened_at', 'closed_at', 'pnl', 'status', 
                               'additional_info', 'raw_data', 'contractSize',
                               'stop_loss_price', 'take_profit_price', 
                               'stop_loss_order_id', 'take_profit_order_id']
                
                invalid_keys = [key for key in converted_position.keys() if key not in valid_columns]
                if invalid_keys:
                    self.logger.warning(f"유효하지 않은 키 발견: {invalid_keys}. 제거합니다.")
                    for key in invalid_keys:
                        del converted_position[key]
                
                # 새 포지션 삽입
                fields = list(converted_position.keys())
                placeholders = ['?' for _ in fields]
                query = f"INSERT INTO positions ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
                values = [converted_position[k] for k in fields]
                cursor.execute(query, values)
            
            conn.commit()
            self.logger.info(f"{len(positions)}개의 포지션을 저장했습니다.")
            return True
            
        except Exception as e:
            self.logger.error(f"포지션 저장 오류: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
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
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            # JSON으로 직렬화해야 하는 필드 처리
            if 'additional_info' in update_data and isinstance(update_data['additional_info'], dict):
                update_data['additional_info'] = json.dumps(update_data['additional_info'])
            
            # 업데이트 쿼리 구성
            set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
            values = list(update_data.values())
            values.append(position_id)
            
            query = f"UPDATE positions SET {set_clause} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            
            affected_rows = cursor.rowcount
            if affected_rows > 0:
                self.logger.info(f"포지션 업데이트 완료 (ID: {position_id})")
                return True
            else:
                self.logger.warning(f"포지션 업데이트 실패 - 해당 ID 찾을 수 없음: {position_id}")
                return False
                
        except sqlite3.Error as e:
            self.logger.error(f"포지션 업데이트 오류: {e}")
            conn, _ = self._get_connection()
            conn.rollback()
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
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            query = "SELECT * FROM positions WHERE status = 'open'"
            params = []

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            positions = []
            for row in rows:
                position = dict(row)

                # JSON 필드 역직렬화
                if 'additional_info' in position and position['additional_info']:
                    try:
                        position['additional_info'] = json.loads(position['additional_info'])
                    except json.JSONDecodeError:
                        position['additional_info'] = {}
                        self.logger.warning(f"포지션 ID {position.get('id')}의 additional_info JSON 파싱 오류")

                # 필수 필드 기본값 설정
                position.setdefault('type', position.get('side', 'unknown'))
                position.setdefault('current_price', 0)
                position.setdefault('profit', 0)
                position.setdefault('profit_percent', 0)

                positions.append(position)

            return positions
            
        except sqlite3.Error as e:
            self.logger.error(f"열린 포지션 조회 오류: {e}")
            return []
    
    def get_closed_positions(self, symbol=None):
        """
        닫힌 포지션 가져오기

        Args:
            symbol (str, optional): 특정 심볼 필터링

        Returns:
            list: 포지션 정보 목록
        """
        try:
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            query = "SELECT * FROM positions WHERE status = 'closed' ORDER BY closed_at DESC"
            params = []

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            positions = []
            for row in rows:
                position = dict(row)

                # JSON 필드 역직렬화
                if 'additional_info' in position and position['additional_info']:
                    try:
                        position['additional_info'] = json.loads(position['additional_info'])
                    except json.JSONDecodeError:
                        position['additional_info'] = {}
                        self.logger.warning(f"포지션 ID {position.get('id')}의 additional_info JSON 파싱 오류")

                # 필수 필드 기본값 설정
                position.setdefault('type', position.get('side', 'unknown'))
                position.setdefault('realized_profit', position.get('pnl', 0))

                positions.append(position)

            return positions
            
        except sqlite3.Error as e:
            self.logger.error(f"닫힌 포지션 조회 오류: {e}")
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
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            # JSON으로 직렬화해야 하는 필드 처리
            if 'additional_info' in trade_data and isinstance(trade_data['additional_info'], dict):
                trade_data['additional_info'] = json.dumps(trade_data['additional_info'])

            # 새 거래 저장
            placeholders = ', '.join(['?'] * len(trade_data))
            columns = ', '.join(trade_data.keys())
            values = list(trade_data.values())

            query = f"INSERT INTO trades ({columns}) VALUES ({placeholders})"
            cursor.execute(query, values)
            conn.commit()

            trade_id = cursor.lastrowid
            self.logger.info(f"거래 내역 저장 완료 (ID: {trade_id})")
            return trade_id
            
        except sqlite3.Error as e:
            self.logger.error(f"거래 내역 저장 오류: {e}")
            if conn:
                conn.rollback()
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
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            query = "SELECT * FROM trades"
            params = []

            if symbol:
                query += " WHERE symbol = ?"
                params.append(symbol)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

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
                        trade['additional_info'] = {}
                        self.logger.warning(f"거래 ID {trade.get('id')}의 additional_info JSON 파싱 오류")

                trades.append(trade)

            return trades
            
        except sqlite3.Error as e:
            self.logger.error(f"거래 내역 조회 오류: {e}")
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
                        trade['additional_info'] = {}
                        self.logger.warning(f"거래 ID {trade.get('id')}의 additional_info JSON 파싱 오류")
                else:
                    trade['additional_info'] = {}
                
                # 필드명 변환 및 기본값 설정 (API 응답 형식에 맞게)
                trade.setdefault('type', trade.get('side', 'unknown'))
                trade.setdefault('datetime', trade.get('timestamp', ''))
                trade.setdefault('price', 0)
                trade.setdefault('amount', 0)
                trade.setdefault('cost', 0)
                trade.setdefault('fee', 0)
                trade.setdefault('profit', 0)
                trade.setdefault('profit_percent', 0)
                
                trades.append(trade)
            
            return trades
        except sqlite3.Error as e:
            self.logger.error(f"거래 내역 로드 오류: {e}")
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
            self.logger.error(f"포지션 로드 오류: {e}")
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
                # trades 테이블에서 수익 계산
                # 거래 내역에서 side에 따라 매수/매도 구분
                side = trade['side']
                price = trade['price']
                amount = trade['amount']
                cost = trade['cost']
                
                # 추가 정보에서 수익 정보 확인 시도
                additional_info = {}
                if trade['additional_info']:
                    try:
                        additional_info = json.loads(trade['additional_info'])
                    except:
                        pass
                
                # 직접 제공된 수익 정보가 있으면 사용
                profit = additional_info.get('profit', 0)
                
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
            self.logger.error(f"성과 통계 로드 오류: {e}")
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
            
            self.logger.debug(f"설정 저장 완료: {key}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"설정 저장 오류: {e}")
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
            self.logger.error(f"설정 불러오기 오류: {e}")
            return default
    
    def update_price_data(self, price_data):
        """
        가격 데이터 업데이트
        
        Args:
            price_data (dict): 가격 데이터 정보
                - symbol: 심볼
                - price: 가격
                - timestamp: 타임스태프
        """
        conn, cursor = self._get_connection()
        try:
            # 이전 가격 데이터 조회
            cursor.execute("""
                SELECT * FROM price_data WHERE symbol = ?
            """, (price_data['symbol'],))
            existing = cursor.fetchone()
            
            if existing:
                # 기존 데이터 업데이트
                cursor.execute("""
                    UPDATE price_data 
                    SET price = ?, timestamp = ?
                    WHERE symbol = ?
                """, (
                    price_data['price'],
                    price_data['timestamp'],
                    price_data['symbol']
                ))
            else:
                # 새 데이터 추가
                cursor.execute("""
                    INSERT INTO price_data (symbol, price, timestamp)
                    VALUES (?, ?, ?)
                """, (
                    price_data['symbol'],
                    price_data['price'],
                    price_data['timestamp']
                ))
            
            conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"가격 데이터 업데이트 오류: {str(e)}")
            conn.rollback()
            return False
    
    def save_orders(self, orders):
        """
        주문 데이터 저장
        
        Args:
            orders (list): 주문 데이터 목록
        """
        conn, cursor = self._get_connection()
        try:
            # 기존 주문 삭제 (열린 주문만 관리하기 때문에 전체 삭제)
            cursor.execute("DELETE FROM orders WHERE status = 'open'")
            
            # 새 주문 데이터 추가
            for order in orders:
                order_id = order.get('id', '')
                symbol = order.get('symbol', '')
                side = order.get('side', '')  # buy or sell
                price = order.get('price', 0)
                amount = order.get('amount', 0)
                status = order.get('status', 'open')
                order_type = order.get('type', 'limit')
                timestamp = order.get('datetime', datetime.now().isoformat())
                additional_info = json.dumps(order.get('additional_info', {}))
                
                cursor.execute("""
                    INSERT INTO orders 
                    (order_id, symbol, side, price, amount, status, type, timestamp, additional_info) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order_id, symbol, side, price, amount, status, order_type, timestamp, additional_info
                ))
            
            conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"주문 데이터 저장 오류: {str(e)}")
            conn.rollback()
            return False
    
    def save_balances(self, balance_data):
        """
        전체 계좌 잔액 정보 저장
        
        Args:
            balance_data (dict): 계좌 잔액 정보 (현물 및 선물 가능)
        """
        conn, cursor = self._get_connection()
        try:
            # 이전 잔액 데이터 삭제
            cursor.execute("DELETE FROM balances WHERE 1=1")
            
            # 현물 잔액 처리
            if 'spot' in balance_data and balance_data['spot']:
                spot_data = balance_data['spot']
                
                for currency, amount in spot_data.get('total', {}).items():
                    if amount > 0:
                        cursor.execute("""
                            INSERT INTO balances 
                            (currency, amount, balance_type, timestamp, additional_info) 
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            currency, 
                            amount, 
                            'spot',
                            datetime.now().isoformat(),
                            json.dumps({"free": spot_data.get('free', {}).get(currency, 0)})
                        ))
            
            # 선물 잔액 처리
            if 'future' in balance_data and balance_data['future']:
                future_data = balance_data['future']
                
                for currency, amount in future_data.get('total', {}).items():
                    if amount > 0:
                        cursor.execute("""
                            INSERT INTO balances 
                            (currency, amount, balance_type, timestamp, additional_info) 
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            currency, 
                            amount, 
                            'future',
                            datetime.now().isoformat(),
                            json.dumps({
                                "free": future_data.get('free', {}).get(currency, 0),
                                "used": future_data.get('used', {}).get(currency, 0)
                            })
                        ))
            
            conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"계좌 잔액 저장 오류: {str(e)}")
            conn.rollback()
            return False
    
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
            
            self.logger.debug(f"잔액 기록 저장 완료: {currency} {amount}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"잔액 기록 저장 오류: {e}")
            self.conn.rollback()
            return False
    
    def get_balances(self, exchange_id=None):
        """
        저장된 계정 잔고 정보 가져오기
        
        Args:
            exchange_id (str, optional): 특정 거래소의 잔고만 가져올 경우
            
        Returns:
            dict: 통화별 잔고 정보를 담은 딕셔너리
        """
        conn, cursor = self._get_connection()
        
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
            if exchange_id:
                query += " WHERE b1.exchange_id = ?"
                params.append(exchange_id)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            balances = {}
            for row in rows:
                bal = dict(row)
                currency = bal.get('currency')
                exchange = bal.get('exchange_id', 'default')
                
                # JSON 필드 역직렬화
                if 'additional_info' in bal and bal['additional_info']:
                    bal['additional_info'] = json.loads(bal['additional_info'])
                
                if exchange not in balances:
                    balances[exchange] = {}
                    
                balances[exchange][currency] = {
                    'free': bal.get('free', 0.0),
                    'used': bal.get('used', 0.0),
                    'total': bal.get('amount', 0.0),  # 기존 필드를 호환성 있게 사용
                    'updated_at': bal.get('timestamp')
                }
            
            return balances
            
        except sqlite3.Error as e:
            self.logger.error(f"잔고 정보 조회 오류: {e}")
            return {}
    
    def get_latest_balance(self, currency=None):
        """
        최신 잔액 정보 가져오기
        
        Args:
            currency (str, optional): 특정 통화 필터링
        
        Returns:
            dict: 통화별 최신 잔액 정보
        """
        conn, cursor = self._get_connection()
        
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
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            balance = {}
            for row in rows:
                bal = dict(row)
                
                # JSON 필드 역직렬화
                if 'additional_info' in bal and bal['additional_info']:
                    bal['additional_info'] = json.loads(bal['additional_info'])
                
                balance[bal['currency']] = bal
            
            return balance
        except sqlite3.Error as e:
            self.logger.error(f"최신 잔액 조회 오류: {e}")
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
            self.logger.error(f"쿼리 실행 오류: {e}")
            if not query.strip().upper().startswith(('SELECT', 'PRAGMA')):
                self.conn.rollback()
            return []

    def save_stop_loss_order(self, position_id, order_info):
        """
        손절/익절 주문 정보를 DB에 저장
        
        Args:
            position_id (int): 포지션 ID
            order_info (dict): 주문 정보
                - order_id: 주문 ID
                - symbol: 심볼
                - order_type: 'stop_loss' 또는 'take_profit'
                - trigger_price: 트리거 가격
                - amount: 수량
                - side: 'buy' 또는 'sell'
                - raw_data: 원본 주문 데이터 (선택)
        
        Returns:
            int: 저장된 레코드 ID, 실패 시 None
        """
        try:
            conn, cursor = self._get_connection()
            
            cursor.execute('''
            INSERT INTO stop_loss_orders 
            (position_id, order_id, symbol, order_type, trigger_price, amount, side, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                position_id,
                order_info['order_id'],
                order_info['symbol'],
                order_info['order_type'],
                order_info['trigger_price'],
                order_info['amount'],
                order_info['side'],
                json.dumps(order_info.get('raw_data', {}))
            ))
            
            conn.commit()
            
            # positions 테이블 업데이트
            if order_info['order_type'] == 'stop_loss':
                cursor.execute('''
                UPDATE positions 
                SET stop_loss_price = ?, stop_loss_order_id = ?
                WHERE id = ?
                ''', (order_info['trigger_price'], order_info['order_id'], position_id))
            else:  # take_profit
                cursor.execute('''
                UPDATE positions 
                SET take_profit_price = ?, take_profit_order_id = ?
                WHERE id = ?
                ''', (order_info['trigger_price'], order_info['order_id'], position_id))
            
            conn.commit()
            
            self.logger.info(f"손절/익절 주문 저장 완료: {order_info['order_type']} - {order_info['order_id']}")
            return cursor.lastrowid
            
        except sqlite3.Error as e:
            self.logger.error(f"손절/익절 주문 저장 오류: {e}")
            return None
    
    def get_active_stop_loss_orders(self, position_id=None, symbol=None):
        """
        활성 손절/익절 주문 조회
        
        Args:
            position_id (int, optional): 포지션 ID
            symbol (str, optional): 심볼
        
        Returns:
            list: 활성 손절/익절 주문 목록
        """
        try:
            conn, cursor = self._get_connection()
            
            query = '''
            SELECT * FROM stop_loss_orders 
            WHERE status = 'active'
            '''
            params = []
            
            if position_id:
                query += ' AND position_id = ?'
                params.append(position_id)
            
            if symbol:
                query += ' AND symbol = ?'
                params.append(symbol)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            self.logger.error(f"손절/익절 주문 조회 오류: {e}")
            return []
    
    def update_stop_loss_order_status(self, order_id, status, timestamp=None):
        """
        손절/익절 주문 상태 업데이트
        
        Args:
            order_id (str): 주문 ID
            status (str): 새로운 상태 ('triggered', 'cancelled')
            timestamp (datetime, optional): 상태 변경 시각
        
        Returns:
            bool: 성공 여부
        """
        try:
            conn, cursor = self._get_connection()
            
            if timestamp is None:
                timestamp = datetime.now()
            
            if status == 'triggered':
                cursor.execute('''
                UPDATE stop_loss_orders 
                SET status = ?, triggered_at = ?
                WHERE order_id = ?
                ''', (status, timestamp, order_id))
            elif status == 'cancelled':
                cursor.execute('''
                UPDATE stop_loss_orders 
                SET status = ?, cancelled_at = ?
                WHERE order_id = ?
                ''', (status, timestamp, order_id))
            else:
                cursor.execute('''
                UPDATE stop_loss_orders 
                SET status = ?
                WHERE order_id = ?
                ''', (status, order_id))
            
            conn.commit()
            
            if cursor.rowcount > 0:
                self.logger.info(f"손절/익절 주문 상태 업데이트: {order_id} -> {status}")
                return True
            return False
            
        except sqlite3.Error as e:
            self.logger.error(f"손절/익절 주문 상태 업데이트 오류: {e}")
            return False

    def load_bot_state(self):
        """
        가장 최근의 봇 상태 불러오기
        
        Returns:
            dict: 봇 상태 정보
        """
        try:
            conn, cursor = self._get_connection()
            cursor.execute("""
                SELECT * FROM bot_state 
                ORDER BY updated_at DESC 
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if not row:
                return None
                
            # Row를 딕셔너리로 변환
            columns = [description[0] for description in cursor.description]
            state = dict(zip(columns, row))
            
            # JSON 필드 파싱
            if state.get('additional_info'):
                try:
                    state['additional_info'] = json.loads(state['additional_info'])
                except json.JSONDecodeError:
                    pass
            
            # parameters 필드도 JSON 파싱
            if state.get('parameters'):
                try:
                    state['parameters'] = json.loads(state['parameters'])
                    # strategy_params로도 매핑 (역호환성)
                    state['strategy_params'] = state['parameters']
                except json.JSONDecodeError:
                    pass
                    
            self.logger.info("봇 상태 불러오기 완료")
            return state
            
        except sqlite3.Error as e:
            self.logger.error(f"봇 상태 불러오기 오류: {e}")
            return None
            
    def save_positions(self, positions):
        """
        여러 포지션을 한번에 저장
        
        Args:
            positions (list): 포지션 데이터 리스트
        
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 스레드 안전 연결 가져오기
            conn, cursor = self._get_connection()
            
            # 기존 포지션 삭제
            cursor.execute("DELETE FROM positions WHERE 1=1")
            
            # camelCase -> snake_case 필드명 변환 매핑
            field_mapping = {
                'entryPrice': 'entry_price',
                'markPrice': 'mark_price',
                'liquidationPrice': 'liquidation_price',
                'unrealizedPnl': 'unrealized_pnl',
                'marginMode': 'margin_mode',
                'contractSize': 'contractSize',  # 이미 적절한 형식
            }
            
            # 새 포지션 저장
            for position in positions:
                # 필드명 변환
                converted_position = {}
                for key, value in position.items():
                    # 매핑이 있으면 변환, 없으면 그대로 사용
                    new_key = field_mapping.get(key, key)
                    converted_position[new_key] = value
                
                # opened_at 필드가 없으면 현재 시간 추가
                if 'opened_at' not in converted_position:
                    converted_position['opened_at'] = datetime.now().isoformat()
                
                # status 필드가 없으면 'open' 추가
                if 'status' not in converted_position:
                    converted_position['status'] = 'open'
                
                # JSON으로 직렬화해야 하는 필드 처리
                if 'additional_info' in converted_position and isinstance(converted_position['additional_info'], dict):
                    converted_position['additional_info'] = json.dumps(converted_position['additional_info'])
                
                # raw_data 필드도 JSON으로 직렬화
                if 'raw_data' in converted_position:
                    if isinstance(converted_position['raw_data'], (dict, list)):
                        converted_position['raw_data'] = json.dumps(converted_position['raw_data'])
                    elif converted_position['raw_data'] is not None and not isinstance(converted_position['raw_data'], str):
                        converted_position['raw_data'] = str(converted_position['raw_data'])
                
                # 모든 필드의 데이터 타입 검증 및 변환
                for key, value in list(converted_position.items()):
                    if value is None:
                        continue  # NULL은 SQLite에서 지원
                    elif isinstance(value, (dict, list)):
                        # 복잡한 데이터 구조는 JSON으로 직렬화
                        converted_position[key] = json.dumps(value)
                    elif isinstance(value, bool):
                        # bool은 정수로 변환 (SQLite는 boolean 타입이 없음)
                        converted_position[key] = int(value)
                    elif not isinstance(value, (str, int, float)):
                        # 지원되지 않는 타입은 문자열로 변환
                        self.logger.warning(f"포지션 저장: {key} 필드의 타입 {type(value)}를 문자열로 변환")
                        converted_position[key] = str(value)
                
                # 테이블 스키마와 맞지 않는 키 제거
                valid_columns = ['id', 'symbol', 'side', 'contracts', 'notional',
                               'entry_price', 'mark_price', 'liquidation_price', 
                               'unrealized_pnl', 'margin_mode', 'leverage', 
                               'opened_at', 'closed_at', 'pnl', 'status', 
                               'additional_info', 'raw_data', 'contractSize',
                               'stop_loss_price', 'take_profit_price', 
                               'stop_loss_order_id', 'take_profit_order_id']
                
                invalid_keys = [key for key in converted_position.keys() if key not in valid_columns]
                if invalid_keys:
                    self.logger.warning(f"유효하지 않은 키 발견: {invalid_keys}. 제거합니다.")
                    for key in invalid_keys:
                        del converted_position[key]
                
                # 새 포지션 삽입
                fields = list(converted_position.keys())
                placeholders = ['?' for _ in fields]
                query = f"INSERT INTO positions ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
                values = [converted_position[k] for k in fields]
                cursor.execute(query, values)
            
            conn.commit()
            self.logger.info(f"{len(positions)}개의 포지션을 저장했습니다.")
            return True
            
        except Exception as e:
            self.logger.error(f"포지션 저장 오류: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
