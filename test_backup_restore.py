#!/usr/bin/env python3
"""
백업 및 복구 시스템 테스트 스크립트
"""
import os
import time
import json
from datetime import datetime
from src.backup_restore import BackupRestoreManager, get_backup_restore_manager
from src.backup_manager import get_backup_manager

def test_backup_restore():
    """백업 및 복구 시스템 테스트"""
    print("=== 백업 및 복구 시스템 테스트 시작 ===")
    
    try:
        # 백업 복원 관리자 초기화
        backup_restore_manager = get_backup_restore_manager()
        backup_manager = get_backup_manager()
        print("✓ 백업 복원 관리자 초기화 성공")
        
        # 사용 가능한 백업 목록 조회
        try:
            backups = backup_manager.list_backups()
            print(f"사용 가능한 백업 수: {len(backups)}")
            
            if backups and len(backups) > 0:
                print(f"가장 최근 백업: {backups[0]}")
            else:
                print("사용 가능한 백업이 없습니다.")
        except Exception as e:
            print(f"백업 목록 조회 중 오류: {str(e)}")
            backups = []
        
        # 테스트용 임시 상태 데이터 생성
        test_state = {
            'state': {
                'trading_active': False,
                'last_signal': 0,
                'auto_sl_tp_enabled': True,
                'test_timestamp': datetime.now().isoformat()
            },
            'config': {
                'test_config': True,
                'test_value': 123
            },
            'positions': [],
            'trades': []
        }
        
        # 백업 생성 테스트 (backup_manager 사용)
        # 첫 번째 인자는 백업 유형, 두 번째 인자는 데이터
        backup_file = backup_manager.create_backup(backup_manager.BACKUP_TYPE_FULL, test_state)
        
        if backup_file:
            print(f"✓ 테스트 백업 생성 성공: {backup_file}")
        else:
            print("✗ 테스트 백업 생성 실패")
        
        # 백업 후 목록 다시 조회
        backups_after = backup_manager.list_backups()
        print(f"백업 후 사용 가능한 백업 수: {len(backups_after)}")
        
        # 백업 파일 존재 확인
        if backup_file and os.path.exists(backup_file):
            print(f"✓ 백업 파일이 존재합니다: {backup_file}")
            
            # 백업에서 복원 테스트
            success, restore_data = backup_restore_manager.restore_from_backup(backup_file)
            
            if success:
                print("✓ 백업에서 데이터 복원 성공")
                print(f"  - 복원 결과: {restore_data}")
            else:
                print(f"✗ 백업에서 데이터 복원 실패: {restore_data.get('error', '알 수 없는 오류')}")
        else:
            print("✗ 백업 파일이 생성되지 않았거나 존재하지 않습니다")
            # 복원 테스트를 건너뜁니다.
        
        # 자동 복원 테스트는 백업 파일이 있는 경우에만 수행
        if backups and len(backups) > 0:
            try:
                auto_success, auto_result = backup_restore_manager.auto_restore_from_backup()
                print(f"자동 복원 결과: {'성공' if auto_success else '실패'} - {auto_result}")
                
                # _select_best_backup 메서드 테스트
                try:
                    best_backup = backup_restore_manager._select_best_backup()
                    print(f"최적의 백업 파일: {best_backup}")
                except Exception as e:
                    print(f"최적의 백업 파일 선택 테스트 실패: {str(e)}")
            except Exception as e:
                print(f"자동 복원 테스트 중 오류 발생: {str(e)}")
        else:
            print("사용 가능한 백업이 없어 자동 복원 테스트를 건너뜁니다.")
            
        print("\n백업 및 복원 기본 기능 테스트 완료")
        
    except Exception as e:
        print(f"백업 및 복구 테스트 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("=== 백업 및 복구 시스템 테스트 완료 ===")

if __name__ == "__main__":
    test_backup_restore()
