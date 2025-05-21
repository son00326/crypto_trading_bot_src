#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 백업 관리자 모듈

import os
import sys
import json
import time
import shutil
import logging
import threading
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path

from src.logging_config import get_logger
from src.config import DATA_DIR
from src.event_manager import get_event_manager, EventType

class BackupManager:
    """
    백업 및 복구 시스템 관리자 클래스
    
    거래 상태, 설정, 포지션 등의 중요 데이터를 주기적으로 백업하고,
    필요 시 복원하는 기능을 제공합니다.
    """
    
    # 백업 유형 정의
    BACKUP_TYPE_FULL = 'full'       # 전체 데이터 백업
    BACKUP_TYPE_STATE = 'state'     # 거래 상태만 백업
    BACKUP_TYPE_CONFIG = 'config'   # 설정만 백업
    BACKUP_TYPE_TRADES = 'trades'   # 거래 내역만 백업
    
    def __init__(
        self, 
        backup_dir: Optional[str] = None,
        backup_interval: int = 3600,  # 기본값: 1시간 간격
        max_backups: int = 24,        # 기본값: 최대 24개 백업 유지
        enable_auto_backup: bool = True
    ):
        """
        BackupManager 초기화
        
        Args:
            backup_dir: 백업 디렉토리 경로 (None인 경우 기본 경로 사용)
            backup_interval: 자동 백업 간격 (초)
            max_backups: 각 유형별 최대 백업 수
            enable_auto_backup: 자동 백업 활성화 여부
        """
        self.logger = get_logger('backup_manager')
        
        # 백업 디렉토리 설정
        if backup_dir is None:
            self.backup_dir = os.path.join(DATA_DIR, 'backups')
        else:
            self.backup_dir = backup_dir
        
        # 백업 디렉토리 생성
        self._create_backup_directories()
        
        # 설정
        self.backup_interval = backup_interval
        self.max_backups = max_backups
        self.enable_auto_backup = enable_auto_backup
        
        # 백업 스케줄러 상태
        self.scheduler_active = False
        self.scheduler_thread = None
        self.last_backup_time = {
            self.BACKUP_TYPE_FULL: None,
            self.BACKUP_TYPE_STATE: None,
            self.BACKUP_TYPE_CONFIG: None,
            self.BACKUP_TYPE_TRADES: None
        }
        
        # 백업 잠금
        self.backup_lock = threading.Lock()
        
        # 이벤트 관리자 참조
        self.event_manager = get_event_manager()
        
        # 이벤트 구독 등록
        self._register_event_handlers()
        
        # 초기화 로그
        self.logger.info(f"백업 관리자 초기화 완료. 백업 디렉토리: {self.backup_dir}")
        
        # 시작 시 자동 백업 스케줄러 활성화
        if self.enable_auto_backup:
            self.start_backup_scheduler()
    
    def _create_backup_directories(self):
        """백업 디렉토리 구조 생성"""
        # 메인 백업 디렉토리
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # 유형별 백업 디렉토리
        for backup_type in [self.BACKUP_TYPE_FULL, self.BACKUP_TYPE_STATE, 
                           self.BACKUP_TYPE_CONFIG, self.BACKUP_TYPE_TRADES]:
            type_dir = os.path.join(self.backup_dir, backup_type)
            os.makedirs(type_dir, exist_ok=True)
            
        self.logger.debug("백업 디렉토리 구조 생성 완료")
    
    def _register_event_handlers(self):
        """
        이벤트 관리자에 백업 관련 이벤트 핸들러 등록
        """
        # 포트폴리오 업데이트 이벤트 -> 상태 백업 생성
        self.event_manager.subscribe(EventType.PORTFOLIO_UPDATED, self._handle_portfolio_update)
        
        # 포지션 관련 이벤트 -> 상태 백업 생성
        self.event_manager.subscribe(EventType.POSITION_OPENED, self._handle_position_update)
        self.event_manager.subscribe(EventType.POSITION_CLOSED, self._handle_position_update)
        self.event_manager.subscribe(EventType.POSITION_UPDATED, self._handle_position_update)
        
        # 주문 관련 이벤트 -> 거래 백업 생성
        self.event_manager.subscribe(EventType.TRADE_EXECUTED, self._handle_trade_executed)
        
        # 시스템 이벤트 -> 전체 백업 생성
        self.event_manager.subscribe(EventType.SYSTEM_SHUTDOWN, self._handle_system_shutdown)
        
    def _handle_portfolio_update(self, event_data: Dict[str, Any]):
        """
        포트폴리오 업데이트 이벤트 처리
        
        Args:
            event_data: 이벤트 데이터
        """
        self.logger.debug(f"포트폴리오 업데이트 이벤트 받음: {event_data.get('updated_at')}")
        
        # 포트폴리오 백업이 필요한지 확인 (최근 백업 시간 기준)
        current_time = time.time()
        last_backup = self.last_backup_time.get(self.BACKUP_TYPE_STATE)
        
        # 마지막 백업 이후 일정 시간이 지났거나, 백업이 없는 경우
        if last_backup is None or (current_time - last_backup) > 300:  # 5분 간격
            self.logger.info("포트폴리오 업데이트로 인한 상태 백업 시작")
            
            # 백업 데이터 추가
            backup_data = self._collect_data_for_backup(self.BACKUP_TYPE_STATE)
            backup_data.update({
                'portfolio': event_data.get('portfolio', {}),
                'symbol': event_data.get('symbol', ''),
                'trigger': 'portfolio_update',
                'updated_at': event_data.get('updated_at')
            })
            
            # 백업 생성
            self.create_backup(self.BACKUP_TYPE_STATE, backup_data)
    
    def _handle_position_update(self, event_data: Dict[str, Any]):
        """
        포지션 변경 이벤트 처리
        
        Args:
            event_data: 이벤트 데이터
        """
        event_type = event_data.get('event_type', '')
        position_id = event_data.get('position_id', '')
        
        self.logger.debug(f"포지션 변경 이벤트 받음: {event_type}, 포지션 ID: {position_id}")
        
        # 포지션 열기/닫기의 경우 백업 생성
        if event_type in [EventType.POSITION_OPENED, EventType.POSITION_CLOSED]:
            self.logger.info(f"포지션 {event_type} 이벤트로 인한 상태 백업 시작")
            
            # 백업 데이터 추가
            backup_data = self._collect_data_for_backup(self.BACKUP_TYPE_STATE)
            backup_data.update({
                'position_event': event_type,
                'position_id': position_id,
                'position_data': event_data.get('position', {}),
                'trigger': 'position_update',
                'updated_at': datetime.now().isoformat()
            })
            
            # 백업 생성
            self.create_backup(self.BACKUP_TYPE_STATE, backup_data)
    
    def _handle_trade_executed(self, event_data: Dict[str, Any]):
        """
        거래 실행 이벤트 처리
        
        Args:
            event_data: 이벤트 데이터
        """
        trade_id = event_data.get('trade_id', '')
        order_id = event_data.get('order_id', '')
        
        self.logger.debug(f"거래 실행 이벤트 받음: 거래 ID {trade_id}, 주문 ID {order_id}")
        
        # 거래 데이터 백업
        self.logger.info("거래 실행으로 인한 거래 백업 시작")
        
        # 백업 데이터 추가
        backup_data = {
            'trade': event_data.get('trade', {}),
            'order': event_data.get('order', {}),
            'symbol': event_data.get('symbol', ''),
            'timestamp': event_data.get('timestamp', datetime.now().isoformat()),
            'type': event_data.get('type', ''),
            'trigger': 'trade_executed'
        }
        
        # 백업 생성
        self.create_backup(self.BACKUP_TYPE_TRADES, backup_data)
    
    def _handle_system_shutdown(self, event_data: Dict[str, Any]):
        """
        시스템 종료 이벤트 처리
        
        Args:
            event_data: 이벤트 데이터
        """
        self.logger.info("시스템 종료 이벤트 받음: 전체 백업 시작")
        
        # 전체 백업 데이터 추가
        backup_data = self._collect_data_for_backup(self.BACKUP_TYPE_FULL)
        backup_data.update({
            'shutdown_time': datetime.now().isoformat(),
            'uptime': event_data.get('uptime', 0),
            'memory_usage': event_data.get('memory_usage', {}),
            'trigger': 'system_shutdown'
        })
        
        # 백업 생성
        self.create_backup(self.BACKUP_TYPE_FULL, backup_data)
        
        self.logger.debug("백업 관리자: 이벤트 핸들러 등록 완료")
    
    def start_backup_scheduler(self):
        """자동 백업 스케줄러 시작"""
        if self.scheduler_active:
            self.logger.warning("백업 스케줄러가 이미 실행 중입니다.")
            return
        
        self.scheduler_active = True
        self.scheduler_thread = threading.Thread(target=self._backup_scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        self.logger.info(f"자동 백업 스케줄러 시작 (간격: {self.backup_interval}초)")
    
    def stop_backup_scheduler(self):
        """자동 백업 스케줄러 중지"""
        if not self.scheduler_active:
            return
        
        self.scheduler_active = False
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=2.0)
        
        self.logger.info("자동 백업 스케줄러 중지됨")
    
    def _backup_scheduler_loop(self):
        """자동 백업 스케줄러 메인 루프"""
        while self.scheduler_active:
            try:
                # 상태 백업 (매 간격마다)
                self.create_backup(self.BACKUP_TYPE_STATE)
                
                # 설정 백업 (매 3번째 간격마다)
                if (int(time.time()) // self.backup_interval) % 3 == 0:
                    self.create_backup(self.BACKUP_TYPE_CONFIG)
                
                # 전체 백업 (매 24번째 간격마다 - 하루에 한 번)
                if (int(time.time()) // self.backup_interval) % 24 == 0:
                    self.create_backup(self.BACKUP_TYPE_FULL)
                
                # 다음 백업까지 대기
                time.sleep(self.backup_interval)
                
            except Exception as e:
                self.logger.error(f"백업 스케줄러 오류: {e}")
                self.logger.debug(traceback.format_exc())
                time.sleep(60)  # 오류 발생 시 1분 대기
    
    def create_backup(self, backup_type: str, data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        백업 생성
        
        Args:
            backup_type: 백업 유형 (BACKUP_TYPE_* 상수 중 하나)
            data: 백업할 데이터 (None인 경우 자동으로 수집)
        
        Returns:
            str: 생성된 백업 파일 경로 또는 None (실패 시)
        """
        with self.backup_lock:
            try:
                # 백업 유형 검증
                if backup_type not in [self.BACKUP_TYPE_FULL, self.BACKUP_TYPE_STATE, 
                                       self.BACKUP_TYPE_CONFIG, self.BACKUP_TYPE_TRADES]:
                    self.logger.error(f"알 수 없는 백업 유형: {backup_type}")
                    return None
                
                # 타임스탬프 생성
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{backup_type}_{timestamp}.json"
                backup_path = os.path.join(self.backup_dir, backup_type, filename)
                
                # 백업 데이터 수집
                backup_data = data
                if backup_data is None:
                    backup_data = self._collect_data_for_backup(backup_type)
                
                # 메타데이터 추가
                backup_data['_metadata'] = {
                    'backup_type': backup_type,
                    'timestamp': timestamp,
                    'version': '1.0',
                    'created_at': datetime.now().isoformat()
                }
                
                # 백업 저장
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)
                
                # 백업 시간 기록
                self.last_backup_time[backup_type] = datetime.now()
                
                # 백업 파일 수 관리 (오래된 백업 제거)
                self._cleanup_old_backups(backup_type)
                
                self.logger.info(f"{backup_type} 백업 생성 완료: {backup_path}")
                
                # 백업 생성 이벤트 발행
                self.event_manager.publish(EventType.BACKUP_CREATED, {
                    'backup_type': backup_type,
                    'backup_path': backup_path,
                    'backup_size': os.path.getsize(backup_path)
                })
                
                return backup_path
                
            except Exception as e:
                self.logger.error(f"{backup_type} 백업 생성 중 오류 발생: {e}")
                self.logger.debug(traceback.format_exc())
                return None
    
    def _collect_data_for_backup(self, backup_type: str) -> Dict[str, Any]:
        """
        백업 유형에 따른 데이터 수집
        
        Args:
            backup_type: 백업 유형
            
        Returns:
            Dict[str, Any]: 수집된 데이터
        """
        # 공통 기본 데이터
        data = {
            'timestamp': datetime.now().isoformat(),
            'backup_type': backup_type,
            'version': '1.1',
            'system_info': self._get_system_info()
        }
        
        # 백업 유형에 따른 데이터 추가
        # 현재 실행 중인 TradingAlgorithm 인스턴스가 없어 직접 가져올 수 없으니
        # 최근 이벤트에서 수집한 데이터를 활용
        
        # 최근 이벤트에서 수집한 데이터
        recent_events = self.event_manager.get_recent_events(50)
        
        # 최근 포트폴리오 업데이트 이벤트 찾기
        portfolio_events = [e for e in recent_events if e['type'] == 'PORTFOLIO_UPDATED']
        last_portfolio = portfolio_events[-1]['data'] if portfolio_events else {}
        
        # 최근 포지션 관련 이벤트 찾기
        position_events = [e for e in recent_events 
                          if e['type'] in ['POSITION_OPENED', 'POSITION_CLOSED', 'POSITION_UPDATED']]
        positions_data = [e['data'] for e in position_events] if position_events else []
        
        # 최근 거래 이벤트 찾기
        trade_events = [e for e in recent_events if e['type'] == 'TRADE_EXECUTED']
        trades_data = [e['data'].get('trade', {}) for e in trade_events] if trade_events else []
        
        # 백업 유형별 데이터 수집
        if backup_type == self.BACKUP_TYPE_FULL:
            # 전체 데이터 백업
            from src.db_manager import DatabaseManager
            db = DatabaseManager()
            
            data.update({
                'portfolio': last_portfolio.get('portfolio', {}),
                'positions': {
                    'open': db.get_open_positions(),
                    'recent_updates': positions_data[-10:] if positions_data else []  # 최근 10개
                },
                'trades': db.get_trades(limit=50),  # 최근 50개 거래
                'settings': self._get_app_settings(),
                'system_state': self._get_system_state()
            })
        
        elif backup_type == self.BACKUP_TYPE_STATE:
            # 거래 상태 백업
            # 트레이딩 상태 및 포트폴리오 정보 가져오기
            trading_state = self._get_trading_state()
            
            # 상태 데이터 구성 (백업 복원 시 'state' 키가 필요함)
            state_data = {
                'timestamp': datetime.now().isoformat(),
                'trading_mode': 'automated',
                'is_running': True,
                'last_update': datetime.now().isoformat(),
                'trading_info': trading_state
            }
            
            # DB에서 최신 봇 상태 가져오기
            try:
                from src.db_manager import DatabaseManager
                db = DatabaseManager()
                bot_state = db.load_bot_state()  # load_bot_state 메서드 사용
                if bot_state:
                    state_data.update(bot_state)
            except Exception as e:
                self.logger.warning(f"DB에서 봇 상태 가져오기 실패: {e}")
            
            data.update({
                'state': state_data,  # 복원에 필요한 기본 'state' 키 추가
                'portfolio': last_portfolio.get('portfolio', {}),
                'positions': {
                    'recent_events': positions_data[-5:] if positions_data else []  # 최근 5개
                },
                'trading_state': trading_state
            })
        
        elif backup_type == self.BACKUP_TYPE_CONFIG:
            # 설정 백업
            data.update({
                'settings': self._get_app_settings()
            })
        
        elif backup_type == self.BACKUP_TYPE_TRADES:
            # 거래 내역 백업
            data.update({
                'trades': trades_data[-20:] if trades_data else []  # 최근 20개
            })
        
        return data
        
    def _get_system_info(self) -> Dict[str, Any]:
        """
        시스템 정보 수집
        """
        import platform
        import psutil
        
        try:
            return {
                'os': platform.system(),
                'version': platform.version(),
                'python': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'hostname': platform.node()
            }
        except Exception as e:
            self.logger.error(f"시스템 정보 수집 중 오류: {e}")
            return {'error': 'Failed to collect system info'}
    
    def _get_app_settings(self) -> Dict[str, Any]:
        """
        애플리케이션 설정 정보 수집
        """
        try:
            # 원래는 동적으로 애플리케이션 설정을 가져와야 하지만 예시로 고정값 반환
            from src.config import DATA_DIR, DEFAULT_EXCHANGE, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, RISK_MANAGEMENT
            
            return {
                'data_dir': DATA_DIR,
                'default_exchange': DEFAULT_EXCHANGE,
                'default_symbol': DEFAULT_SYMBOL,
                'default_timeframe': DEFAULT_TIMEFRAME,
                'risk_management': RISK_MANAGEMENT
            }
        except Exception as e:
            self.logger.error(f"설정 정보 수집 중 오류: {e}")
            return {'error': 'Failed to collect app settings'}
    
    def _get_system_state(self) -> Dict[str, Any]:
        """
        시스템 상태 정보 수집
        """
        try:
            import psutil
            
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_usage': dict(psutil.virtual_memory()._asdict()),
                'disk_usage': dict(psutil.disk_usage('/')._asdict()),
                'boot_time': psutil.boot_time(),
                'process_count': len(psutil.pids())
            }
        except Exception as e:
            self.logger.error(f"시스템 상태 정보 수집 중 오류: {e}")
            return {'error': 'Failed to collect system state'}
    
    def _get_trading_state(self) -> Dict[str, Any]:
        """
        거래 활동 상태 정보 수집
        """
        try:
            # 최근 이벤트에서 거래 활동 관련 데이터 추출
            trading_events = self.event_manager.get_recent_events(20)
            
            # 최근 시스템 이벤트
            system_events = [e for e in trading_events 
                             if e['type'] in ['SYSTEM_STARTUP', 'SYSTEM_SHUTDOWN', 'MEMORY_WARNING']]
            
            return {
                'last_events': [e['type'] for e in trading_events[-10:]],
                'system_events': system_events,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"거래 활동 상태 정보 수집 중 오류: {e}")
            return {'error': 'Failed to collect trading state'}
    
    def _cleanup_old_backups(self, backup_type: str):
        """
        오래된 백업 제거
        
        Args:
            backup_type: 백업 유형
        """
        try:
            backup_dir = os.path.join(self.backup_dir, backup_type)
            backup_files = []
            
            # 백업 파일 목록 수집
            for f in os.listdir(backup_dir):
                if f.startswith(f"{backup_type}_") and f.endswith(".json"):
                    file_path = os.path.join(backup_dir, f)
                    backup_files.append((file_path, os.path.getmtime(file_path)))
            
            # 날짜순 정렬 (오래된 것부터)
            backup_files.sort(key=lambda x: x[1])
            
            # 최대 백업 수를 초과하는 경우 오래된 백업 제거
            while len(backup_files) > self.max_backups:
                oldest_file = backup_files.pop(0)
                try:
                    os.remove(oldest_file[0])
                    self.logger.debug(f"오래된 백업 제거: {oldest_file[0]}")
                except Exception as e:
                    self.logger.error(f"백업 제거 중 오류: {e}")
                    
        except Exception as e:
            self.logger.error(f"오래된 백업 정리 중 오류: {e}")
    
    def list_backups(self, backup_type: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        사용 가능한 백업 목록 반환
        
        Args:
            backup_type: 특정 백업 유형 (None인 경우 모든 유형)
        
        Returns:
            Dict[str, List[Dict[str, Any]]]: 백업 유형별 목록
        """
        result = {}
        
        try:
            # 조회할 백업 유형 선택
            backup_types = [backup_type] if backup_type else [
                self.BACKUP_TYPE_FULL, self.BACKUP_TYPE_STATE, 
                self.BACKUP_TYPE_CONFIG, self.BACKUP_TYPE_TRADES
            ]
            
            # 백업 유형별 파일 목록 수집
            for btype in backup_types:
                backup_dir = os.path.join(self.backup_dir, btype)
                if not os.path.exists(backup_dir):
                    result[btype] = []
                    continue
                
                backups = []
                for f in os.listdir(backup_dir):
                    if f.startswith(f"{btype}_") and f.endswith(".json"):
                        file_path = os.path.join(backup_dir, f)
                        
                        # 백업 메타데이터 추출
                        try:
                            with open(file_path, 'r') as bf:
                                data = json.load(bf)
                                metadata = data.get('_metadata', {})
                        except:
                            metadata = {}
                        
                        file_info = {
                            'file_name': f,
                            'file_path': file_path,
                            'timestamp': metadata.get('timestamp', ''),
                            'created_at': metadata.get('created_at', ''),
                            'version': metadata.get('version', ''),
                            'size_kb': round(os.path.getsize(file_path) / 1024, 2)
                        }
                        backups.append(file_info)
                
                # 최신 순으로 정렬
                backups.sort(key=lambda x: x['created_at'] if x['created_at'] else '', reverse=True)
                result[btype] = backups
            
            return result
            
        except Exception as e:
            self.logger.error(f"백업 목록 조회 중 오류: {e}")
            self.logger.debug(traceback.format_exc())
            return {}
    
    def restore_from_backup(self, backup_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        백업에서 상태 복원
        
        Args:
            backup_path: 백업 파일 경로
        
        Returns:
            Tuple[bool, Dict[str, Any]]: 성공 여부와 복원된 데이터 또는 오류 정보
        """
        try:
            if not os.path.exists(backup_path):
                return False, {'error': f"백업 파일이 존재하지 않음: {backup_path}"}
            
            # 백업 파일 읽기
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            # 메타데이터 검증
            metadata = backup_data.get('_metadata', {})
            if not metadata:
                return False, {'error': "백업 파일에 메타데이터가 없음"}
            
            # 백업 유형 확인
            backup_type = metadata.get('backup_type')
            if not backup_type:
                return False, {'error': "백업 유형을 확인할 수 없음"}
            
            # 복원 로직은 다음 단계에서 구현
            # 현재는 백업 데이터만 반환
            self.logger.info(f"백업 파일 읽기 성공: {backup_path} (유형: {backup_type})")
            
            # 백업 복원 이벤트 발행
            self.event_manager.publish(EventType.BACKUP_RESTORED, {
                'backup_type': backup_type,
                'backup_path': backup_path,
                'metadata': metadata
            })
            
            return True, {
                'backup_data': backup_data,
                'backup_type': backup_type,
                'metadata': metadata
            }
            
        except Exception as e:
            self.logger.error(f"백업에서 복원 중 오류: {e}")
            self.logger.debug(traceback.format_exc())
            return False, {'error': str(e)}
    
    def get_latest_backup(self, backup_type: str) -> Optional[str]:
        """
        특정 유형의 최신 백업 파일 경로 반환
        
        Args:
            backup_type: 백업 유형
        
        Returns:
            Optional[str]: 최신 백업 파일 경로
        """
        try:
            backup_dir = os.path.join(self.backup_dir, backup_type)
            if not os.path.exists(backup_dir):
                return None
            
            backup_files = []
            for f in os.listdir(backup_dir):
                if f.startswith(f"{backup_type}_") and f.endswith(".json"):
                    file_path = os.path.join(backup_dir, f)
                    backup_files.append((file_path, os.path.getmtime(file_path)))
            
            if not backup_files:
                return None
            
            # 최신 파일 선택 (수정 시간 기준)
            backup_files.sort(key=lambda x: x[1], reverse=True)
            return backup_files[0][0]
            
        except Exception as e:
            self.logger.error(f"최신 백업 조회 중 오류: {e}")
            return None

# 전역 백업 관리자 인스턴스
backup_manager = None

def get_backup_manager() -> BackupManager:
    """
    전역 백업 관리자 인스턴스 반환
    
    Returns:
        BackupManager: 백업 관리자 인스턴스
    """
    global backup_manager
    if backup_manager is None:
        backup_manager = BackupManager()
    return backup_manager

# 테스트 코드
    # 이벤트 기반 백업 핸들러 메서드
    def _handle_portfolio_update(self, data):
        """
        포트폴리오 업데이트 이벤트 처리
        """
        try:
            self.logger.debug("포트폴리오 업데이트 감지: 백업 디레이 설정")
            # 포트폴리오 업데이트마다 백업하지 않고 마지막 백업 이후 일정 시간이 지난 경우에만 백업
            last_backup_time = self.last_backup_time[self.BACKUP_TYPE_STATE]
            
            if last_backup_time is None or (datetime.now() - last_backup_time).total_seconds() > 300:  # 5분마다 백업
                self._delayed_state_backup()
        except Exception as e:
            self.logger.error(f"포트폴리오 업데이트 백업 처리 중 오류: {e}")
    
    def _handle_position_update(self, data):
        """
        포지션 변경 이벤트 처리
        """
        try:
            # 포지션 업데이트는 중요하여 즉시 백업 생성
            self.logger.debug(f"포지션 변경 감지 - 유형: {data.get('event_type')}")
            self._delayed_state_backup(delay=5)  # 5초 뒤 백업 (연속적인 업데이트 중복 방지)
        except Exception as e:
            self.logger.error(f"포지션 변경 백업 처리 중 오류: {e}")
    
    def _handle_trade_executed(self, data):
        """
        거래 실행 이벤트 처리
        """
        try:
            self.logger.debug("거래 실행 감지: 거래 백업 생성")
            
            # 거래 이력 백업 (별도 파일로 저장)
            trade_data = {'trades': [data.get('trade', {})], 'last_update': time.time()}
            
            # 거래 백업 생성
            self.create_backup(self.BACKUP_TYPE_TRADES, trade_data)
            
            # 다음 백업을 위한 상태 백업도 생성
            self._delayed_state_backup(delay=5)
        except Exception as e:
            self.logger.error(f"거래 백업 처리 중 오류: {e}")
    
    def _handle_system_shutdown(self, data):
        """
        시스템 종료 이벤트 처리
        """
        try:
            self.logger.info("시스템 종료 감지: 전체 백업 생성")
            
            # 시스템 종료 시 전체 백업 생성
            self.create_backup(self.BACKUP_TYPE_FULL, data.get('state', {}))
        except Exception as e:
            self.logger.error(f"시스템 종료 백업 처리 중 오류: {e}")
    
    def _delayed_state_backup(self, delay=30):
        """
        지정된 지연 시간 후 상태 백업 생성
        
        Args:
            delay: 지연 시간 (초)
        """
        def delayed_backup():
            try:
                time.sleep(delay)
                # TODO: 어떤 데이터를 백업할지는 다음 단계에서 설정
                self.create_backup(self.BACKUP_TYPE_STATE, {})
            except Exception as e:
                self.logger.error(f"지연 백업 실행 중 오류: {e}")
        
        
        # 다른 스레드에서 백업 실행
        backup_thread = threading.Thread(target=delayed_backup)
        backup_thread.daemon = True
        backup_thread.start()

if __name__ == "__main__":
    # 간단한 테스트
    manager = BackupManager(backup_interval=10, max_backups=5)
    
    # 백업 생성 테스트
    for backup_type in [BackupManager.BACKUP_TYPE_FULL, BackupManager.BACKUP_TYPE_STATE]:
        test_data = {
            'test_data': f"Test data for {backup_type}",
            'timestamp': datetime.now().isoformat()
        }
        backup_path = manager.create_backup(backup_type, test_data)
        print(f"백업 생성 완료: {backup_path}")
    
    # 백업 목록 조회 테스트
    backups = manager.list_backups()
    print("\n백업 목록:")
    for btype, blist in backups.items():
        print(f"\n[{btype}] - {len(blist)}개 백업:")
        for b in blist:
            print(f"  - {b['file_name']} ({b['size_kb']}KB, {b['created_at']})")
    
    # 최신 백업 조회 테스트
    latest = manager.get_latest_backup(BackupManager.BACKUP_TYPE_STATE)
    if latest:
        print(f"\n최신 상태 백업: {latest}")
        
        # 복원 테스트
        success, restore_data = manager.restore_from_backup(latest)
        if success:
            print(f"복원 성공: {restore_data['backup_type']}")
        else:
            print(f"복원 실패: {restore_data.get('error')}")
    
    # 자동 백업 스케줄러 테스트
    print("\n자동 백업 스케줄러 테스트 (10초 간격)...")
    manager.start_backup_scheduler()
    
    try:
        # 30초 동안 실행
        for i in range(3):
            time.sleep(10)
            print(f"... {(i+1)*10}초 경과")
        
    except KeyboardInterrupt:
        print("\n테스트 중단")
    finally:
        manager.stop_backup_scheduler()
        print("백업 스케줄러 중지")
