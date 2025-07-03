"""
거래 신호 모델 - 암호화폐 자동매매 봇

이 모듈은 거래 전략에서 생성된 거래 신호를 나타내는 TradeSignal 클래스를 구현합니다.
"""

from datetime import datetime
from dataclasses import dataclass, field, fields
from typing import Dict, Any, Optional, List
import uuid

@dataclass
class TradeSignal:
    """거래 신호 모델 클래스"""
    
    symbol: str
    direction: str  # 'long', 'short', 'close', 'hold'
    price: float
    strategy_name: str  # 신호를 생성한 전략 이름
    
    # 기본값이 있는 필드들
    timestamp: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    confidence: float = 0.0  # 신호의 신뢰도 (0.0 ~ 1.0)
    strength: float = 0.0  # 신호의 강도 (0.0 ~ 1.0)
    
    # 선택적 필드
    target_price: Optional[float] = None  # 목표 가격
    stop_loss: Optional[float] = None  # 손절매 가격
    take_profit: Optional[float] = None  # 이익실현 가격
    entry_window: Optional[int] = None  # 진입 유효 시간(초)
    suggested_quantity: Optional[float] = None  # 제안 수량
    timeframe: Optional[str] = None  # 신호가 생성된 타임프레임 (예: '1h', '4h', '1d')
    
    # 신호 처리 상태
    processed: bool = False  # 신호가 처리됐는지 여부
    executed: bool = False  # 신호에 따라 거래가 실행됐는지 여부
    execution_time: Optional[datetime] = None  # 신호가 실행된 시간
    execution_price: Optional[float] = None  # 실제 거래 가격
    associated_order_id: Optional[str] = None  # 연결된 주문 ID
    
    # 추가 필드
    indicators: Dict[str, Any] = field(default_factory=dict)  # 각종 지표 값
    tags: List[str] = field(default_factory=list)  # 신호 태그
    notes: Optional[str] = None  # 추가 설명
    additional_info: Dict[str, Any] = field(default_factory=dict)  # 기타 정보
    
    def to_dict(self) -> Dict[str, Any]:
        """신호를 딕셔너리로 변환"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'direction': self.direction,
            'price': self.price,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'strategy_name': self.strategy_name,
            'confidence': self.confidence,
            'strength': self.strength,
            'target_price': self.target_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'entry_window': self.entry_window,
            'suggested_quantity': self.suggested_quantity,
            'timeframe': self.timeframe,
            'processed': self.processed,
            'executed': self.executed,
            'execution_time': self.execution_time.isoformat() if isinstance(self.execution_time, datetime) and self.execution_time else None,
            'execution_price': self.execution_price,
            'associated_order_id': self.associated_order_id,
            'indicators': self.indicators,
            'tags': self.tags,
            'notes': self.notes,
            'additional_info': self.additional_info
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradeSignal':
        """딕셔너리에서 신호 객체 생성"""
        # datetime 문자열을 datetime 객체로 변환
        if isinstance(data.get('timestamp'), str):
            try:
                data['timestamp'] = datetime.fromisoformat(data['timestamp'])
            except (ValueError, TypeError):
                data['timestamp'] = datetime.now()
                
        if isinstance(data.get('execution_time'), str):
            try:
                data['execution_time'] = datetime.fromisoformat(data['execution_time'])
            except (ValueError, TypeError):
                data['execution_time'] = None
        
        # 필수 필드 확인
        required_fields = {'symbol', 'direction', 'price', 'strategy_name'}
        for field in required_fields:
            if field not in data:
                raise ValueError(f"필수 필드 누락: {field}")
        
        # 클래스 인스턴스 생성에 필요한 필드만 추출
        signal_data = {k: v for k, v in data.items() if k in [f.name for f in fields(cls)]}
        
        return cls(**signal_data)
    
    def mark_as_processed(self) -> None:
        """신호를 처리됨으로 표시"""
        self.processed = True
    
    def mark_as_executed(self, execution_price: float, order_id: Optional[str] = None) -> None:
        """신호를 실행됨으로 표시"""
        self.processed = True
        self.executed = True
        self.execution_time = datetime.now()
        self.execution_price = execution_price
        if order_id:
            self.associated_order_id = order_id
    
    def is_valid(self) -> bool:
        """신호가 유효한지 검사"""
        # 이미 처리된 신호인지 확인
        if self.processed:
            return False
            
        # 진입 유효 시간이 설정된 경우, 만료되었는지 확인
        if self.entry_window is not None:
            time_diff = (datetime.now() - self.timestamp).total_seconds()
            if time_diff > self.entry_window:
                return False
                
        # 동일한 가격에서 진입하기 어려운 시장 상황 고려
        # 실시간 가격과 신호 가격의 차이가 크면 신호가 무효할 수 있음
        # 여기서는 해당 로직 생략 (실제 사용시 구현 필요)
        
        return True
    
    def calculate_risk_reward_ratio(self) -> Optional[float]:
        """위험 대비 보상 비율 계산"""
        if not self.take_profit or not self.stop_loss:
            return None
            
        if self.direction == 'buy':
            reward = self.take_profit - self.price
            risk = self.price - self.stop_loss
        else:  # sell
            reward = self.price - self.take_profit
            risk = self.stop_loss - self.price
            
        if risk == 0:
            return None
            
        return abs(reward / risk)
