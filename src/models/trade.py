"""
거래 기록 모델 - 암호화폐 자동매매 봇

이 모듈은 실행된 거래를 나타내는 Trade 클래스를 구현합니다.
"""

from datetime import datetime
from dataclasses import dataclass, field, fields
from typing import Dict, Any, Optional
import uuid

@dataclass
class Trade:
    """거래 기록 모델 클래스"""
    
    symbol: str
    side: str  # 'buy' 또는 'sell'
    order_type: str  # 'market', 'limit' 등
    amount: float
    price: float
    timestamp: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 선택적 필드
    cost: Optional[float] = None  # 거래 비용 (price * amount)
    fee: Optional[float] = None  # 수수료
    order_id: Optional[str] = None  # 연결된 주문 ID
    position_id: Optional[str] = None  # 연결된 포지션 ID
    is_test: bool = False  # 테스트 거래인지 여부
    
    # 추가 정보
    additional_info: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """초기화 후 추가 필드 설정"""
        if self.cost is None:
            self.cost = self.price * self.amount
            
        if self.fee is None:
            # 기본 수수료 예상치 (0.1%)
            self.fee = self.cost * 0.001
    
    def to_dict(self) -> Dict[str, Any]:
        """거래를 딕셔너리로 변환"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side,
            'order_type': self.order_type,
            'amount': self.amount,
            'price': self.price,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'cost': self.cost,
            'fee': self.fee,
            'order_id': self.order_id,
            'position_id': self.position_id,
            'is_test': self.is_test,
            'additional_info': self.additional_info
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Trade':
        """딕셔너리에서 거래 객체 생성"""
        # datetime 문자열을 datetime 객체로 변환
        if isinstance(data.get('timestamp'), str):
            try:
                data['timestamp'] = datetime.fromisoformat(data['timestamp'])
            except (ValueError, TypeError):
                data['timestamp'] = datetime.now()
        
        # 필수 필드 확인
        required_fields = {'symbol', 'side', 'order_type', 'amount', 'price'}
        for field in required_fields:
            if field not in data:
                raise ValueError(f"필수 필드 누락: {field}")
        
        # 클래스 인스턴스 생성에 필요한 필드만 추출
        trade_data = {k: v for k, v in data.items() if k in [f.name for f in fields(cls)]}
        
        return cls(**trade_data)
    
    def calculate_profit_loss(self, entry_price: float) -> float:
        """이익/손실 계산"""
        if self.side == 'buy':
            # 매수는 보통 진입이므로 이익/손실 계산이 의미가 없음
            return 0
        else:  # sell
            return (self.price - entry_price) * self.amount
    
    def calculate_profit_loss_percentage(self, entry_price: float) -> float:
        """이익/손실 백분율 계산"""
        if self.side == 'buy':
            # 매수는 보통 진입이므로 이익/손실 계산이 의미가 없음
            return 0
        else:  # sell
            return ((self.price - entry_price) / entry_price) * 100
