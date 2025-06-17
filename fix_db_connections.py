#!/usr/bin/env python3
"""
데이터베이스 연결 문제를 수정하는 스크립트
"""

import re

def fix_db_manager():
    # db_manager.py 파일 읽기
    with open('src/db_manager.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. import 섹션에 contextmanager 추가
    import_section = content.split('class DatabaseManager')[0]
    if 'from contextlib import contextmanager' not in import_section:
        import_lines = import_section.split('\n')
        for i, line in enumerate(import_lines):
            if line.startswith('from pathlib import Path'):
                import_lines.insert(i+1, 'from contextlib import contextmanager')
                break
        new_import_section = '\n'.join(import_lines)
        content = content.replace(import_section, new_import_section)
    
    # 2. db_connection_manager import 추가
    if 'from src.db_connection_manager import get_db_connection' not in content:
        import_lines = content.split('\n')
        for i, line in enumerate(import_lines):
            if line.startswith('from pathlib import Path'):
                import_lines.insert(i+1, 'from src.db_connection_manager import get_db_connection')
                break
        content = '\n'.join(import_lines)
    
    # 3. _thread_local 변수 제거
    content = re.sub(r'^# 스레드 로컬 스토리지.*\n_thread_local = threading\.local\(\)\n', '', content, flags=re.MULTILINE)
    
    # 4. _get_connection 메서드를 새로운 구현으로 교체
    old_get_connection = r'def _get_connection\(self\):[\s\S]*?return _thread_local\.conn, _thread_local\.cursor'
    new_get_connection = '''def _get_connection(self):
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
        
        return conn, cursor'''
    
    content = re.sub(old_get_connection, new_get_connection, content, flags=re.DOTALL)
    
    # 5. __init__ 메서드 수정
    init_pattern = r'(# 데이터베이스 연결 및 테이블 생성[\s\S]*?)conn, cursor = self\._get_connection\(\)[\s\S]*?self\._create_tables\(conn, cursor\)'
    init_replacement = r'\1with get_db_connection(self.db_path) as (conn, cursor):\n            self._create_tables(conn, cursor)\n            conn.commit()'
    content = re.sub(init_pattern, init_replacement, content)
    
    # 6. save_position 메서드에 finally 블록 추가
    save_position_pattern = r'(def save_position\(self, position_data\):[\s\S]*?)except Exception as e:[\s\S]*?return False'
    
    def save_position_replacement(match):
        method_content = match.group(0)
        if 'finally:' not in method_content:
            # finally 블록 추가
            method_content = re.sub(
                r'(except Exception as e:[\s\S]*?return False)',
                r'\1\n        finally:\n            if \'conn\' in locals() and conn:\n                conn.close()',
                method_content
            )
        return method_content
    
    content = re.sub(save_position_pattern, save_position_replacement, content, flags=re.DOTALL)
    
    # 7. save_positions 메서드에도 finally 블록 추가
    save_positions_pattern = r'(def save_positions\(self, positions_list\):[\s\S]*?)except Exception as e:[\s\S]*?return False'
    
    def save_positions_replacement(match):
        method_content = match.group(0)
        if 'finally:' not in method_content:
            method_content = re.sub(
                r'(except Exception as e:[\s\S]*?return False)',
                r'\1\n        finally:\n            if \'conn\' in locals() and conn:\n                conn.close()',
                method_content
            )
        return method_content
    
    content = re.sub(save_positions_pattern, save_positions_replacement, content, flags=re.DOTALL)
    
    # 파일 저장
    with open('src/db_manager.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("db_manager.py 수정 완료!")

if __name__ == "__main__":
    fix_db_manager()
