#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 이벤트 관리자 모듈

import time
import threading
import logging
from typing import Dict, Any, List, Callable, Optional
from enum import Enum, auto

from src.logging_config import get_logger

# 이벤트 유형 정의
class EventType(Enum):
    # 포트폴리오 이벤트
    PORTFOLIO_UPDATED = auto()
    BALANCE_CHANGED = auto()
    
    # 거래 이벤트
    TRADE_EXECUTED = auto()
    ORDER_CREATED = auto()
    ORDER_FILLED = auto()
    ORDER_CANCELED = auto()
    
    # 포지션 이벤트
    POSITION_OPENED = auto()
    POSITION_CLOSED = auto()
    POSITION_UPDATED = auto()
    STOP_LOSS_TRIGGERED = auto()
    TAKE_PROFIT_TRIGGERED = auto()
    
    # 시스템 이벤트
    SYSTEM_STARTUP = auto()
    SYSTEM_SHUTDOWN = auto()
    MEMORY_WARNING = auto()
    SYSTEM_RECOVERY = auto()  # 시스템 복구 이벤트 추가
    API_ERROR = auto()
    NETWORK_ERROR = auto()
    DATABASE_ERROR = auto()
    TRADING_ERROR = auto()  # 거래 오류 이벤트 추가
    
    # 백업 이벤트
    BACKUP_CREATED = auto()
    BACKUP_RESTORED = auto()

class EventManager:
    """
    이벤트 관리 시스템
    
    거래 알고리즘 내 다양한 컴포넌트 간의 이벤트 기반 통신을 관리합니다.
    구독자 패턴(Observer Pattern)을 구현하여 느슨한 결합(Loose Coupling)을 유지합니다.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """싱글톤 패턴 구현"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """이벤트 관리자 초기화"""
        if self._initialized:
            return
            
        self.logger = get_logger('event_manager')
        self.subscribers = {}  # event_type -> [callbacks]
        self.event_history = []  # 최근 이벤트 기록
        self.max_history = 100  # 최대 이벤트 기록 수
        self._initialized = True
        self.logger.info("이벤트 관리자 초기화 완료")
    
    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """
        특정 이벤트 유형에 콜백 함수 등록
        
        Args:
            event_type: 구독할 이벤트 유형
            callback: 이벤트 발생 시 호출할 콜백 함수
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)
            self.logger.debug(f"{event_type.name} 이벤트에 콜백 등록됨")
    
    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """
        특정 이벤트 유형에서 콜백 함수 제거
        
        Args:
            event_type: 구독 취소할 이벤트 유형
            callback: 제거할 콜백 함수
        """
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
            self.logger.debug(f"{event_type.name} 이벤트에서 콜백 제거됨")
    
    def publish(self, event_type: EventType, data: Optional[Dict[str, Any]] = None) -> None:
        """
        이벤트 발행
        
        Args:
            event_type: 발행할 이벤트 유형
            data: 이벤트와 함께 전달할 데이터
        """
        if data is None:
            data = {}
        
        # 이벤트 타임스탬프 추가
        data['timestamp'] = time.time()
        data['event_type'] = event_type.name
        
        # 이벤트 기록
        self._add_to_history(event_type, data)
        
        # 구독자들에게 알림
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    self.logger.error(f"{event_type.name} 이벤트 처리 중 오류: {e}")
        
        self.logger.debug(f"{event_type.name} 이벤트 발행됨")
    
    def _add_to_history(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """
        이벤트 기록에 추가
        
        Args:
            event_type: 이벤트 유형
            data: 이벤트 데이터
        """
        event_record = {
            'type': event_type.name,
            'timestamp': data['timestamp'],
            'data': data
        }
        
        self.event_history.append(event_record)
        
        # 최대 기록 수 유지
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)
    
    def get_recent_events(self, count: int = 10, event_type: Optional[EventType] = None) -> List[Dict[str, Any]]:
        """
        최근 이벤트 기록 조회
        
        Args:
            count: 조회할 이벤트 수
            event_type: 특정 이벤트 유형만 필터링 (None인 경우 모든 이벤트)
            
        Returns:
            List[Dict[str, Any]]: 최근 이벤트 목록
        """
        if event_type is None:
            return self.event_history[-count:]
        
        # 특정 유형 이벤트만 필터링
        filtered = [e for e in self.event_history if e['type'] == event_type.name]
        return filtered[-count:]
    
    def clear_history(self) -> None:
        """이벤트 기록 초기화"""
        self.event_history = []
        self.logger.debug("이벤트 기록이 초기화됨")

# 싱글톤 인스턴스 접근 함수
def get_event_manager() -> EventManager:
    """
    이벤트 관리자 인스턴스 반환
    
    Returns:
        EventManager: 싱글톤 이벤트 관리자 인스턴스
    """
    return EventManager()
