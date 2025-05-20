"""
주문 모델 - 암호화폐 자동매매 봇

이 모듈은 거래 주문을 나타내는 Order 클래스를 구현합니다.
"""

from datetime import datetime
from dataclasses import dataclass, field, fields
from typing import Dict, Any, Optional
import uuid

@dataclass
class Order:
    """주문 모델 클래스"""
    
    symbol: str
    type: str  # 'market', 'limit', 'stop', 'stop_limit' 등
    side: str  # 'buy' 또는 'sell'
    amount: float
    price: float
    status: str = 'open'  # 'open', 'closed', 'canceled', 'rejected'
    timestamp: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 선택적 필드
    order_id: Optional[str] = None  # 외부 거래소 주문 ID
    filled: float = 0.0  # 채워진 수량
    remaining: Optional[float] = None  # 남은 수량
    cost: Optional[float] = None  # 주문 비용 (price * filled)
    fee: Optional[float] = None  # 수수료
    average: Optional[float] = None  # 평균 체결 가격
    
    position_id: Optional[str] = None  # 연결된 포지션 ID
    close_position: bool = False  # 포지션 종료 주문인지 여부
    is_test: bool = False  # 테스트 주문인지 여부
    
    # 추가 정보
    additional_info: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """초기화 후 추가 필드 설정"""
        if self.remaining is None:
            self.remaining = self.amount
        if self.cost is None and self.filled > 0:
            self.cost = self.price * self.filled
        if self.average is None and self.filled > 0:
            self.average = (self.cost or 0) / self.filled if self.filled > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """주문을 딕셔너리로 변환"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'type': self.type,
            'side': self.side,
            'amount': self.amount,
            'price': self.price,
            'status': self.status,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'order_id': self.order_id,
            'filled': self.filled,
            'remaining': self.remaining,
            'cost': self.cost,
            'fee': self.fee,
            'average': self.average,
            'position_id': self.position_id,
            'close_position': self.close_position,
            'is_test': self.is_test,
            'additional_info': self.additional_info
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        """딕셔너리에서 주문 객체 생성"""
        # datetime 문자열을 datetime 객체로 변환
        if isinstance(data.get('timestamp'), str):
            try:
                data['timestamp'] = datetime.fromisoformat(data['timestamp'])
            except (ValueError, TypeError):
                data['timestamp'] = datetime.now()
        
        # 필수 필드 확인
        required_fields = {'symbol', 'type', 'side', 'amount', 'price'}
        for field in required_fields:
            if field not in data:
                raise ValueError(f"필수 필드 누락: {field}")
        
        # 클래스 인스턴스 생성에 필요한 필드만 추출
        order_data = {k: v for k, v in data.items() if k in [f.name for f in fields(cls)]}
        
        return cls(**order_data)
    
    def update(self, data: Dict[str, Any]) -> None:
        """주문 정보 업데이트"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
                
        # 파생 필드 계산
        if self.filled > 0:
            if self.cost is None:
                self.cost = self.price * self.filled
            if self.average is None:
                self.average = self.cost / self.filled if self.filled > 0 else 0
                
        # 남은 수량 계산
        if self.remaining is None:
            self.remaining = self.amount - self.filled
        
        # 모두 채워졌는지 확인하여 상태 업데이트
        if self.filled >= self.amount and self.status == 'open':
            self.status = 'closed'
            self.remaining = 0
    
    def is_filled(self) -> bool:
        """주문이 완전히 채워졌는지 확인"""
        return self.filled >= self.amount
    
    def is_open(self) -> bool:
        """주문이 아직 열려 있는지 확인"""
        return self.status == 'open'
    
    def is_canceled(self) -> bool:
        """주문이 취소되었는지 확인"""
        return self.status == 'canceled'
    
    def is_rejected(self) -> bool:
        """주문이 거부되었는지 확인"""
        return self.status == 'rejected'
    
    def calculate_notional_value(self) -> float:
        """주문의 명목 가치 계산"""
        return self.price * self.amount
