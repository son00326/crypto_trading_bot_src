"""
포지션 모델 - 암호화폐 자동매매 봇

이 모듈은 거래 포지션을 나타내는 Position 클래스를 구현합니다.
"""

from datetime import datetime
from dataclasses import dataclass, field, fields
from typing import List, Dict, Any, Optional
import uuid

@dataclass
class Position:
    """포지션 모델 클래스"""
    
    symbol: str
    side: str  # 'long' 또는 'short'
    amount: float
    entry_price: float
    opened_at: datetime = field(default_factory=datetime.now)
    status: str = 'open'  # 'open' 또는 'closed'
    leverage: float = 1.0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 선택적 필드
    exit_price: Optional[float] = None
    closed_at: Optional[datetime] = None
    pnl: float = 0.0
    liquidation_price: Optional[float] = None
    margin: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    auto_sl_tp: bool = False
    trailing_stop: bool = False
    trailing_stop_distance: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    contract_size: float = 1.0  # 계약 크기 추가
    
    # 추가 정보 및 부분 청산 내역
    partial_exits: List[Dict[str, Any]] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """포지션을 딕셔너리로 변환"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side,
            'amount': self.amount,
            'entry_price': self.entry_price,
            'opened_at': self.opened_at.isoformat() if isinstance(self.opened_at, datetime) else self.opened_at,
            'status': self.status,
            'leverage': self.leverage,
            'exit_price': self.exit_price,
            'closed_at': self.closed_at.isoformat() if isinstance(self.closed_at, datetime) and self.closed_at else None,
            'pnl': self.pnl,
            'liquidation_price': self.liquidation_price,
            'margin': self.margin,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'auto_sl_tp': self.auto_sl_tp,
            'trailing_stop': self.trailing_stop,
            'trailing_stop_distance': self.trailing_stop_distance,
            'trailing_stop_price': self.trailing_stop_price,
            'contract_size': self.contract_size,  # contract_size 추가
            'partial_exits': self.partial_exits,
            'additional_info': self.additional_info
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        """딕셔너리에서 포지션 객체 생성"""
        # datetime 문자열을 datetime 객체로 변환
        if isinstance(data.get('opened_at'), str):
            try:
                data['opened_at'] = datetime.fromisoformat(data['opened_at'])
            except (ValueError, TypeError):
                data['opened_at'] = datetime.now()
                
        if isinstance(data.get('closed_at'), str):
            try:
                data['closed_at'] = datetime.fromisoformat(data['closed_at'])
            except (ValueError, TypeError):
                data['closed_at'] = None
        
        # 필수 필드가 없는 경우 기본값 설정
        required_fields = {'symbol', 'side', 'amount', 'entry_price'}
        for field in required_fields:
            if field not in data:
                raise ValueError(f"필수 필드 누락: {field}")
        
        # 클래스 인스턴스 생성에 필요한 필드만 추출
        position_data = {k: v for k, v in data.items() if k in [f.name for f in fields(cls)]}
        
        return cls(**position_data)
    
    def calculate_current_value(self, current_price: float) -> float:
        """현재 포지션 가치 계산"""
        return self.amount * current_price
    
    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """미실현 손익 계산"""
        if self.side == 'long':
            return (current_price - self.entry_price) * self.amount
        elif self.side == 'short':
            return (self.entry_price - current_price) * self.amount
        return 0
    
    def calculate_unrealized_pnl_percentage(self, current_price: float) -> float:
        """미실현 손익 백분율 계산"""
        if self.side == 'long':
            return ((current_price - self.entry_price) / self.entry_price) * 100
        elif self.side == 'short':
            return ((self.entry_price - current_price) / self.entry_price) * 100
        return 0
    
    def update_trailing_stop(self, current_price: float) -> bool:
        """트레일링 스탑 가격 업데이트"""
        if not self.trailing_stop or not self.trailing_stop_distance:
            return False
            
        if self.side == 'long':
            new_trailing_stop = current_price - self.trailing_stop_distance
            if not self.trailing_stop_price or new_trailing_stop > self.trailing_stop_price:
                self.trailing_stop_price = new_trailing_stop
                return True
        elif self.side == 'short':
            new_trailing_stop = current_price + self.trailing_stop_distance
            if not self.trailing_stop_price or new_trailing_stop < self.trailing_stop_price:
                self.trailing_stop_price = new_trailing_stop
                return True
                
        return False
    
    def should_close_position(self, current_price: float) -> tuple[bool, str]:
        """포지션을 종료해야 하는지 확인"""
        if self.status != 'open':
            return False, "이미 종료된 포지션"
            
        # 스탑로스 확인
        if self.auto_sl_tp and self.stop_loss:
            if (self.side == 'long' and current_price <= self.stop_loss) or \
               (self.side == 'short' and current_price >= self.stop_loss):
                return True, "스탑로스 도달"
                
        # 익절 확인
        if self.auto_sl_tp and self.take_profit:
            if (self.side == 'long' and current_price >= self.take_profit) or \
               (self.side == 'short' and current_price <= self.take_profit):
                return True, "익절 가격 도달"
                
        # 트레일링 스탑 확인
        if self.trailing_stop and self.trailing_stop_price:
            if (self.side == 'long' and current_price <= self.trailing_stop_price) or \
               (self.side == 'short' and current_price >= self.trailing_stop_price):
                return True, "트레일링 스탑 도달"
                
        return False, ""
        
    def set_auto_sl_tp(self, stop_loss: Optional[float] = None, take_profit: Optional[float] = None, 
                      trailing_stop: bool = False, trailing_stop_distance: Optional[float] = None):
        """자동 손절매/이익실현 설정"""
        if stop_loss:
            self.stop_loss = stop_loss
            
        if take_profit:
            self.take_profit = take_profit
            
        self.trailing_stop = trailing_stop
        if trailing_stop_distance:
            self.trailing_stop_distance = trailing_stop_distance
            
        self.auto_sl_tp = bool(stop_loss or take_profit or trailing_stop)
        
    def close_position(self, exit_price: float, exit_time: datetime = None):
        """포지션 종료"""
        if self.status == 'closed':
            return False
            
        self.status = 'closed'
        self.exit_price = exit_price
        self.closed_at = exit_time or datetime.now()
        
        # 손익 계산
        if self.side == 'long':
            self.pnl = (exit_price - self.entry_price) * self.amount
        else:  # short
            self.pnl = (self.entry_price - exit_price) * self.amount
            
        return True
        
    def add_partial_exit(self, exit_data: Dict[str, Any]):
        """부분 청산 정보 추가"""
        self.partial_exits.append(exit_data)
        # 남은 수량 업데이트
        if 'amount' in exit_data:
            self.amount -= exit_data['amount']
    
    # Backward compatibility를 위한 속성 별칭
    @property
    def quantity(self) -> float:
        """amount의 별칭 (backward compatibility)"""
        return self.amount
    
    @quantity.setter
    def quantity(self, value: float):
        """amount의 별칭 (backward compatibility)"""
        self.amount = value
    
    @property
    def contracts(self) -> float:
        """amount의 별칭 (backward compatibility)"""
        return self.amount * self.contract_size
    
    @contracts.setter
    def contracts(self, value: float):
        """amount의 별칭 (backward compatibility)"""
        self.amount = value / self.contract_size
    
    @property
    def unrealized_profit(self) -> float:
        """미실현 손익 (status가 open인 경우 pnl 반환)"""
        return self.pnl if self.status == 'open' else 0.0
    
    @property
    def realized_profit(self) -> float:
        """실현 손익 (status가 closed인 경우 pnl 반환)"""
        return self.pnl if self.status == 'closed' else 0.0
    
    @classmethod
    def from_dict_compatible(cls, data: Dict[str, Any]) -> 'Position':
        """
        딕셔너리에서 포지션 객체 생성 (backward compatibility)
        quantity, contracts 등의 별칭 필드를 자동 변환
        """
        # 데이터 복사
        position_data = data.copy()
        
        # 별칭 처리
        if 'quantity' in position_data and 'amount' not in position_data:
            position_data['amount'] = position_data.pop('quantity')
        elif 'contracts' in position_data and 'amount' not in position_data:
            contract_size = position_data.get('contract_size', 1.0)
            position_data['amount'] = position_data.pop('contracts') / contract_size
        
        # unrealized_profit/realized_profit 처리
        if 'unrealized_profit' in position_data or 'realized_profit' in position_data:
            if 'pnl' not in position_data:
                position_data['pnl'] = position_data.get('unrealized_profit', 0) + position_data.get('realized_profit', 0)
            position_data.pop('unrealized_profit', None)
            position_data.pop('realized_profit', None)
        
        # created_at을 opened_at으로 변환
        if 'created_at' in position_data and 'opened_at' not in position_data:
            position_data['opened_at'] = position_data.pop('created_at')
        
        return cls.from_dict(position_data)
    
    def to_dict_compatible(self, use_aliases: bool = False) -> Dict[str, Any]:
        """
        포지션을 딕셔너리로 변환 (backward compatibility)
        use_aliases=True인 경우 별칭 필드도 포함
        """
        result = self.to_dict()
        
        if use_aliases:
            # 별칭 추가
            result['quantity'] = self.quantity
            result['contracts'] = self.contracts
            if self.status == 'open':
                result['unrealized_profit'] = self.pnl
            elif self.status == 'closed':
                result['realized_profit'] = self.pnl
        
        return result
