#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 백업 복원 관리자

import os
import sys
import json
import time
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path

from src.logging_config import get_logger
from src.backup_manager import get_backup_manager, BackupManager
from src.recovery_manager import RecoveryManager
from src.event_manager import get_event_manager, EventType
from src.config import DATA_DIR

class BackupRestoreManager:
    """
    백업 복원 관리자
    
    백업 시스템과 복구 관리자를 통합하여 안정적인 백업 복원 메커니즘을 제공합니다.
    특징:
    1. 자동 백업 복원 처리
    2. 데이터 무결성 검증
    3. 우선순위 기반 복원 전략
    4. 복원 과정 롤백 지원
    """
    
    def __init__(self, auto_restore: bool = True, data_verification: bool = True):
        """
        백업 복원 관리자 초기화
        
        Args:
            auto_restore: 초기화 시 자동 복원 수행 여부
            data_verification: 복원 전/후 데이터 검증 수행 여부
        """
        self.logger = get_logger('backup_restore')
        
        # 관련 매니저들 참조
        self.backup_manager = get_backup_manager()
        self.recovery_manager = RecoveryManager()
        self.event_manager = get_event_manager()
        
        # 설정
        self.auto_restore = auto_restore
        self.data_verification = data_verification
        self.restore_strategy = 'latest_first'  # 'latest_first', 'full_preferred', 'state_only'
        
        # 복원 진행 상태 및 기록
        self.restore_in_progress = False
        self.last_restore_attempt = None
        self.restore_history = []
        self.restore_failures = []
        
        # 복원 디렉토리
        self.restore_dir = os.path.join(DATA_DIR, 'restore')
        os.makedirs(self.restore_dir, exist_ok=True)
        
        # 이벤트 구독
        self._register_event_handlers()
        
        self.logger.info("백업 복원 관리자 초기화 완료")
        
        # 자동 복원 수행
        if self.auto_restore:
            self.auto_restore_from_backup()
    
    def _register_event_handlers(self):
        """이벤트 관리자에 이벤트 핸들러 등록"""
        # 백업 복원 이벤트 구독
        self.event_manager.subscribe(EventType.BACKUP_RESTORED, self._handle_backup_restored)
        # 시스템 오류 이벤트 구독
        self.event_manager.subscribe(EventType.API_ERROR, self._handle_system_error)
        self.event_manager.subscribe(EventType.NETWORK_ERROR, self._handle_system_error)
        self.event_manager.subscribe(EventType.DATABASE_ERROR, self._handle_system_error)
        
        self.logger.debug("이벤트 핸들러 등록 완료")
    
    def auto_restore_from_backup(self) -> Tuple[bool, Dict[str, Any]]:
        """
        가장 적합한 백업에서 자동 복원
        
        Returns:
            Tuple[bool, Dict[str, Any]]: (성공 여부, 결과 정보)
        """
        self.logger.info("자동 백업 복원 시작")
        
        # 이미 복원 중인 경우 중복 복원 방지
        if self.restore_in_progress:
            self.logger.warning("이미 복원 작업이 진행 중입니다")
            return False, {"error": "Restore already in progress"}
        
        try:
            self.restore_in_progress = True
            self.last_restore_attempt = datetime.now()
            
            # 복원 전략에 따라 백업 선택
            backup_file = self._select_best_backup()
            if not backup_file:
                self.logger.warning("적합한 백업 파일을 찾을 수 없습니다")
                self.restore_in_progress = False
                
                # 복원 실패 기록
                self._record_restore_attempt(False, None, "No suitable backup found")
                return False, {"error": "No suitable backup found"}
            
            # 백업 파일 복원
            success, restore_data = self.restore_from_backup(backup_file)
            
            # 복원 기록
            self._record_restore_attempt(success, backup_file, 
                                        restore_data.get('error', '') if not success else '')
            
            # 복원 상태 초기화
            self.restore_in_progress = False
            
            if success:
                self.logger.info(f"자동 백업 복원 성공: {backup_file}")
                return True, restore_data
            else:
                self.logger.error(f"자동 백업 복원 실패: {restore_data.get('error', '알 수 없는 오류')}")
                return False, restore_data
                
        except Exception as e:
            self.logger.error(f"자동 복원 중 예외 발생: {e}")
            self.logger.debug(traceback.format_exc())
            
            # 복원 상태 초기화
            self.restore_in_progress = False
            
            # 복원 실패 기록
            self._record_restore_attempt(False, None, str(e))
            
            return False, {"error": str(e)}
    
    def restore_from_backup(self, backup_file: str) -> Tuple[bool, Dict[str, Any]]:
        """
        특정 백업 파일에서 복원
        
        Args:
            backup_file: 백업 파일 경로
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (성공 여부, 복원 데이터 또는 오류 정보)
        """
        self.logger.info(f"백업 파일 복원 시작: {backup_file}")
        
        # 백업 파일 존재 확인
        if not os.path.exists(backup_file):
            return False, {"error": f"Backup file not found: {backup_file}"}
        
        try:
            # 백업 파일 읽기
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # 메타데이터 검증
            metadata = backup_data.get('_metadata', {})
            if not metadata:
                return False, {"error": "Invalid backup file: missing metadata"}
            
            # 백업 유형 확인
            backup_type = metadata.get('backup_type')
            
            # 복원 전 현재 상태 스냅샷 저장 (롤백 대비)
            self._save_pre_restore_snapshot()
            
            # 백업 유형별 복원 처리
            if backup_type == self.backup_manager.BACKUP_TYPE_FULL:
                return self._restore_full_backup(backup_data)
            elif backup_type == self.backup_manager.BACKUP_TYPE_STATE:
                return self._restore_state_backup(backup_data)
            elif backup_type == self.backup_manager.BACKUP_TYPE_CONFIG:
                return self._restore_config_backup(backup_data)
            else:
                return False, {"error": f"Unsupported backup type: {backup_type}"}
                
        except json.JSONDecodeError as e:
            self.logger.error(f"백업 파일 파싱 오류: {e}")
            return False, {"error": f"Invalid JSON format: {str(e)}"}
        except Exception as e:
            self.logger.error(f"백업 복원 중 오류 발생: {e}")
            self.logger.debug(traceback.format_exc())
            return False, {"error": str(e)}
    
    def _restore_full_backup(self, backup_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        전체 백업 데이터 복원
        
        Args:
            backup_data: 백업 데이터
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (성공 여부, 결과 데이터)
        """
        try:
            # 백업 데이터에서 필요한 정보 추출
            state_data = backup_data.get('state', {})
            portfolio_data = backup_data.get('portfolio', {})
            positions_data = backup_data.get('positions', {})
            config_data = backup_data.get('config', {})
            
            # 데이터 유효성 검증
            if not state_data or not portfolio_data:
                return False, {"error": "Invalid backup data: missing required components"}
            
            # 복원 순서: 설정 -> 포트폴리오 -> 포지션 -> 거래 상태
            
            # 1. 설정 복원
            if config_data:
                self._restore_config_data(config_data)
            
            # 2. 포트폴리오 복원
            portfolio_restored = self._restore_portfolio_data(portfolio_data)
            if not portfolio_restored:
                return False, {"error": "Failed to restore portfolio data"}
            
            # 3. 포지션 데이터 복원
            positions_restored = self._restore_positions_data(positions_data)
            
            # 4. 거래 상태 복원
            state_restored = self._restore_bot_state(state_data)
            
            # 복원 결과 이벤트 발행
            self.event_manager.publish(EventType.BACKUP_RESTORED, {
                'backup_type': 'full',
                'timestamp': datetime.now().isoformat(),
                'components_restored': {
                    'config': bool(config_data),
                    'portfolio': portfolio_restored,
                    'positions': positions_restored,
                    'state': state_restored
                }
            })
            
            return True, {
                'components_restored': {
                    'config': bool(config_data),
                    'portfolio': portfolio_restored,
                    'positions': positions_restored,
                    'state': state_restored
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"전체 백업 복원 중 오류: {e}")
            self._rollback_restore()
            return False, {"error": str(e)}
    
    def _restore_state_backup(self, backup_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        상태 백업 데이터 복원
        
        Args:
            backup_data: 백업 데이터
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (성공 여부, 결과 데이터)
        """
        try:
            # 백업 데이터에서 상태 데이터 추출 시도 - 다양한 키 이름 확인
            state_data = backup_data.get('state', {})
            
            # 'state' 키가 없는 경우 'state_data' 키 확인
            if not state_data and 'state_data' in backup_data:
                state_data = backup_data.get('state_data', {})
                self.logger.info("'state' 키 대신 'state_data' 키를 사용하여 상태 복원 시도")
            
            portfolio_data = backup_data.get('portfolio', {})
            
            # 상태 데이터가 없지만 복원을 계속 시도
            if not state_data:
                self.logger.warning("백업에 상태 데이터가 없습니다. 빈 상태로 초기화합니다.")
                state_data = {}
            
            # 포트폴리오 데이터가 있으면 복원
            portfolio_restored = False
            if portfolio_data:
                portfolio_restored = self._restore_portfolio_data(portfolio_data)
            else:
                self.logger.warning("백업에 포트폴리오 데이터가 없습니다.")
            
            # 봇 상태 복원
            state_restored = self._restore_bot_state(state_data)
            
            # 복원 결과 이벤트 발행
            self.event_manager.publish(EventType.BACKUP_RESTORED, {
                'backup_type': 'state',
                'timestamp': datetime.now().isoformat(),
                'components_restored': {
                    'portfolio': portfolio_restored,
                    'state': state_restored
                }
            })
            
            return True, {
                'components_restored': {
                    'portfolio': portfolio_restored,
                    'state': state_restored
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"상태 백업 복원 중 오류: {e}")
            self._rollback_restore()
            return False, {"error": str(e)}
    
    def _restore_config_backup(self, backup_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        설정 백업 데이터 복원
        
        Args:
            backup_data: 백업 데이터
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (성공 여부, 결과 데이터)
        """
        try:
            config_data = backup_data.get('config', {})
            
            if not config_data:
                return False, {"error": "Invalid config backup: missing config data"}
            
            # 설정 데이터 복원
            config_restored = self._restore_config_data(config_data)
            
            # 복원 결과 이벤트 발행
            self.event_manager.publish(EventType.BACKUP_RESTORED, {
                'backup_type': 'config',
                'timestamp': datetime.now().isoformat(),
                'components_restored': {
                    'config': config_restored
                }
            })
            
            return True, {
                'components_restored': {
                    'config': config_restored
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"설정 백업 복원 중 오류: {e}")
            return False, {"error": str(e)}
    
    def _restore_portfolio_data(self, portfolio_data: Dict[str, Any]) -> bool:
        """
        포트폴리오 데이터 복원
        
        Args:
            portfolio_data: 포트폴리오 데이터
            
        Returns:
            bool: 성공 여부
        """
        try:
            from src.db_manager import DatabaseManager
            db = DatabaseManager()
            
            # 자산 정보 저장
            if 'base_currency' in portfolio_data and 'base_balance' in portfolio_data:
                db.save_balance(portfolio_data['base_currency'], portfolio_data['base_balance'])
                
            if 'quote_currency' in portfolio_data and 'quote_balance' in portfolio_data:
                db.save_balance(portfolio_data['quote_currency'], portfolio_data['quote_balance'])
            
            # 거래 내역
            if 'trade_history' in portfolio_data and isinstance(portfolio_data['trade_history'], list):
                for trade in portfolio_data['trade_history']:
                    # 이미 존재하는 거래는 건너뛰기
                    if not db.get_trade(trade.get('id')):
                        db.save_trade(trade)
            
            self.logger.info("포트폴리오 데이터 복원 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"포트폴리오 데이터 복원 중 오류: {e}")
            return False
    
    def _restore_positions_data(self, positions_data: Dict[str, Any]) -> bool:
        """
        포지션 데이터 복원
        
        Args:
            positions_data: 포지션 데이터
            
        Returns:
            bool: 성공 여부
        """
        try:
            from src.db_manager import DatabaseManager
            db = DatabaseManager()
            
            # 열린 포지션 복원
            if 'positions' in positions_data and isinstance(positions_data['positions'], list):
                for position in positions_data['positions']:
                    # 이미 존재하는 포지션은 건너뛰기
                    if not db.get_position(position.get('id')):
                        db.save_position(position)
            
            self.logger.info("포지션 데이터 복원 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"포지션 데이터 복원 중 오류: {e}")
            return False
    
    def _restore_bot_state(self, state_data: Dict[str, Any]) -> bool:
        """
        봇 상태 데이터 복원
        
        Args:
            state_data: 상태 데이터
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 복구 관리자를 통해 봇 상태 저장
            state_to_save = {
                'trading_active': state_data.get('trading_active', False),
                'last_signal': state_data.get('last_signal', 0),
                'auto_sl_tp_enabled': state_data.get('auto_sl_tp_enabled', False),
                'restored_from_backup': True,
                'restored_at': datetime.now().isoformat()
            }
            
            self.recovery_manager.save_bot_state(state_to_save)
            self.logger.info("봇 상태 데이터 복원 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"봇 상태 복원 중 오류: {e}")
            return False
    
    def _restore_config_data(self, config_data: Dict[str, Any]) -> bool:
        """
        설정 데이터 복원
        
        Args:
            config_data: 설정 데이터
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 설정 파일 저장 경로
            config_dir = os.path.join(DATA_DIR, 'config')
            os.makedirs(config_dir, exist_ok=True)
            
            restored_config_file = os.path.join(config_dir, 'restored_config.json')
            
            # 설정 데이터 저장
            with open(restored_config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"설정 데이터 복원 완료: {restored_config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"설정 복원 중 오류: {e}")
            return False
    
    def _select_best_backup(self) -> Optional[str]:
        """
        복원 전략에 따라 최적의 백업 파일 선택
        
        Returns:
            Optional[str]: 선택된 백업 파일 경로 또는 None
        """
        try:
            # 전체 백업 목록 가져오기
            backups = self.backup_manager.list_backups()
            
            if not backups:
                return None
            
            if self.restore_strategy == 'latest_first':
                # 전체 > 상태 > 설정 순으로 최신 백업 선택
                for backup_type in [self.backup_manager.BACKUP_TYPE_FULL, 
                                   self.backup_manager.BACKUP_TYPE_STATE,
                                   self.backup_manager.BACKUP_TYPE_CONFIG]:
                    if backup_type in backups and backups[backup_type]:
                        return backups[backup_type][0]['file_path']  # 최신 백업 선택
                
            elif self.restore_strategy == 'full_preferred':
                # 전체 백업 중 최신 것 선택
                if self.backup_manager.BACKUP_TYPE_FULL in backups and backups[self.backup_manager.BACKUP_TYPE_FULL]:
                    return backups[self.backup_manager.BACKUP_TYPE_FULL][0]['file_path']
                
                # 없으면 상태 백업 중 최신 것 선택
                if self.backup_manager.BACKUP_TYPE_STATE in backups and backups[self.backup_manager.BACKUP_TYPE_STATE]:
                    return backups[self.backup_manager.BACKUP_TYPE_STATE][0]['file_path']
            
            elif self.restore_strategy == 'state_only':
                # 상태 백업만 고려
                if self.backup_manager.BACKUP_TYPE_STATE in backups and backups[self.backup_manager.BACKUP_TYPE_STATE]:
                    return backups[self.backup_manager.BACKUP_TYPE_STATE][0]['file_path']
            
            # 기본적으로 어떤 백업이든 최신 것 선택
            for backup_type in backups:
                if backups[backup_type]:
                    return backups[backup_type][0]['file_path']
            
            return None
            
        except Exception as e:
            self.logger.error(f"최적의 백업 선택 중 오류: {e}")
            return None
    
    def _save_pre_restore_snapshot(self):
        """복원 전 현재 상태 스냅샷 저장 (롤백용)"""
        try:
            # 기본 스냅샷 데이터 구조 생성
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'balances': {},
                'positions': [],  # 'open_positions'에서 'positions'로 변경
                'bot_state': {}
            }
            
            # 안전하게 각 정보 수집 시도
            try:
                from src.db_manager import DatabaseManager
                db = DatabaseManager()
                
                # 현재 계정 잔고 가져오기 시도
                try:
                    snapshot['balances'] = db.get_balances()
                except Exception as e:
                    self.logger.warning(f"잔고 정보 가져오기 실패: {e}")
                
                # 현재 포지션 정보 가져오기 시도
                try:
                    snapshot['positions'] = db.get_positions(status='open')  # 통일된 메서드 사용
                except Exception as e:
                    self.logger.warning(f"포지션 정보 가져오기 실패: {e}")
                
                # 봇 상태 정보 가져오기 시도
                try:
                    snapshot['bot_state'] = db.load_bot_state() or {}
                except Exception as e:
                    self.logger.warning(f"봇 상태 정보 가져오기 실패: {e}")
            
            except Exception as db_error:
                self.logger.warning(f"DB 연결 중 오류: {db_error}")
            
            # 스냅샷 파일 저장
            snapshot_file = os.path.join(self.restore_dir, 
                                   f'pre_restore_snapshot_{int(time.time())}.json')
            
            with open(snapshot_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"복원 전 스냅샷 저장 완료: {snapshot_file}")
            
        except Exception as e:
            self.logger.error(f"복원 전 스냅샷 저장 중 오류: {e}")
    
    def _rollback_restore(self):
        """복원 실패 시 이전 상태로 롤백"""
        try:
            self.logger.warning("복원 실패로 인한 롤백 시작")
            
            # 가장 최근 스냅샷 찾기
            snapshots = sorted([f for f in os.listdir(self.restore_dir) 
                               if f.startswith('pre_restore_snapshot_')],
                              reverse=True)
            
            if not snapshots:
                self.logger.warning("롤백할 스냅샷을 찾을 수 없습니다")
                return False
            
            snapshot_file = os.path.join(self.restore_dir, snapshots[0])
            
            # 스냅샷 로드
            with open(snapshot_file, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)
            
            # 롤백 수행
            from src.db_manager import DatabaseManager
            db = DatabaseManager()
            
            # 잔액 복원
            if 'balances' in snapshot:
                for currency, balance in snapshot['balances'].items():
                    db.save_balance(currency, balance['amount'])
            
            # 포지션 복원
            if 'positions' in snapshot:  # 'open_positions'에서 'positions'로 변경
                for position in snapshot['positions']:
                    db.save_position(position)
            # 이전 버전 호환성을 위한 처리
            elif 'open_positions' in snapshot:
                for position in snapshot['open_positions']:
                    db.save_position(position)
            
            # 봇 상태 복원
            if 'bot_state' in snapshot and snapshot['bot_state']:
                self.recovery_manager.save_bot_state(snapshot['bot_state'])
            
            self.logger.info("롤백 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"롤백 중 오류 발생: {e}")
            return False
    
    def _record_restore_attempt(self, success: bool, backup_file: Optional[str], error_message: str = ''):
        """
        복원 시도 기록
        
        Args:
            success: 성공 여부
            backup_file: 백업 파일 경로
            error_message: 오류 메시지 (실패 시)
        """
        try:
            restore_record = {
                'timestamp': datetime.now().isoformat(),
                'success': success,
                'backup_file': backup_file,
                'error': error_message if not success else '',
                'strategy': self.restore_strategy
            }
            
            self.restore_history.append(restore_record)
            
            if not success:
                self.restore_failures.append(restore_record)
            
            # 로그 파일에 기록
            log_file = os.path.join(self.restore_dir, 'restore_history.json')
            
            # 기존 기록 로드
            history = []
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                except:
                    history = []
            
            # 새 기록 추가
            history.append(restore_record)
            
            # 저장
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"복원 시도 기록 중 오류: {e}")
    
    def _handle_backup_restored(self, data: Dict[str, Any]):
        """
        백업 복원 완료 이벤트 처리
        
        Args:
            data: 이벤트 데이터
        """
        self.logger.info(f"백업 복원 완료 이벤트: {data.get('backup_type')}")
    
    def _handle_system_error(self, data: Dict[str, Any]):
        """
        시스템 오류 이벤트 처리 (잠재적 자동 복구 트리거)
        
        Args:
            data: 이벤트 데이터
        """
        # 실패한 작업 수에 따라 자동 복구 트리거
        error_type = data.get('event_type', '')
        error_message = data.get('error', '')
        
        self.logger.warning(f"시스템 오류 발생: {error_type} - {error_message}")
        
        # TODO: 오류 횟수에 따른 자동 복구 논리 구현
        # 현재는 바로 자동 복구를 시도하지 않고, 오류 기록만 남김

# 전역 백업 복원 관리자 인스턴스
backup_restore_manager = None

def get_backup_restore_manager() -> BackupRestoreManager:
    """
    전역 백업 복원 관리자 인스턴스 반환
    
    Returns:
        BackupRestoreManager: 백업 복원 관리자 인스턴스
    """
    global backup_restore_manager
    if backup_restore_manager is None:
        backup_restore_manager = BackupRestoreManager()
    return backup_restore_manager

# 테스트 코드
if __name__ == "__main__":
    print("=== 백업 및 복원 시스템 테스트 ===\n")
    
    # 자동 복원 비활성화로 시작
    restore_manager = BackupRestoreManager(auto_restore=False)
    
    # 1. 백업 목록 테스트
    print("1. 백업 목록 테스트")
    backups = restore_manager.backup_manager.list_backups()
    
    print("\n사용 가능한 백업:")
    has_backups = False
    for backup_type, backup_list in backups.items():
        print(f"\n== {backup_type} 백업 ({len(backup_list)}개) ==")
        if backup_list:
            has_backups = True
            for i, backup in enumerate(backup_list[:3]):  # 최대 3개만 표시
                print(f" {i+1}. {backup['file_name']} ({backup['size_kb']}KB, {backup['created_at']})")
    
    # 2. 백업 생성 테스트
    print("\n\n2. 백업 생성 테스트")
    # 테스트용 데이터 생성
    test_data = {
        'timestamp': datetime.now().isoformat(),
        'test_id': f'test_{int(time.time())}',
        'system_info': {
            'platform': 'test_platform',
            'memory': '8GB',
            'cpu': 'test_cpu',
            'python_version': sys.version
        },
        'portfolio': {
            'base_currency': 'USDT',
            'base_balance': 1000.0,
            'positions': []
        }
    }
    
    # 상태 백업 생성
    state_backup = restore_manager.backup_manager.create_backup(
        restore_manager.backup_manager.BACKUP_TYPE_STATE, test_data)
    
    if state_backup:
        print(f"\n상태 백업 생성 성공: {os.path.basename(state_backup)}")
    else:
        print("\n상태 백업 생성 실패")
    
    # 3. 백업 선택 테스트
    print("\n\n3. 백업 선택 테스트")
    restore_manager.restore_strategy = 'latest_first'
    backup_file = restore_manager._select_best_backup()
    
    if backup_file:
        print(f"\n선택된 백업 파일: {os.path.basename(backup_file)}")
    else:
        print("\n복원할 백업을 찾을 수 없습니다. 백업을 먼저 생성해주세요.")
        exit(0)
    
    # 4. 백업 복원 테스트 (자동 응답)
    print("\n\n4. 백업 복원 테스트 (자동)")
    # 복원 수행 (자동)
    print(f"\n'{os.path.basename(backup_file)}' 백업에서 자동 복원 시도 중...")
    
    success, result = restore_manager.restore_from_backup(backup_file)
    
    if success:
        restored = result.get('components_restored', {})
        print(f"\n복원 성공! 복원된 구성요소:")
        for component, restored_status in restored.items():
            print(f" - {component}: {'성공' if restored_status else '실패'}")
    else:
        print(f"\n복원 실패: {result.get('error', '알 수 없는 오류')}")
    
    # 5. 자동 복원 테스트
    print("\n\n5. 자동 복원 전략 테스트")
    print("\n다양한 복원 전략 테스트:")
    
    for strategy in ['latest_first', 'full_preferred', 'state_only']:
        restore_manager.restore_strategy = strategy
        backup_file = restore_manager._select_best_backup()
        
        if backup_file:
            print(f" - {strategy}: {os.path.basename(backup_file)} 선택")
        else:
            print(f" - {strategy}: 적합한 백업 없음")
    
    print("\n=== 테스트 완료 ===\n")
