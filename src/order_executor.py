"""
주문 실행 모듈 - 암호화폐 자동매매 봇

이 모듈은 실제 주문 실행을 담당하는 OrderExecutor 클래스를 구현합니다.
TradingAlgorithm에서 주문 관련 로직을 분리하여 책임을 명확히 합니다.
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Union, List, Tuple

from src.models.position import Position
from src.error_handlers import (
    simple_error_handler, safe_execution, api_error_handler,
    network_error_handler, db_error_handler, trade_error_handler
)

# 로거 설정
logger = logging.getLogger('order_executor')

class OrderExecutor:
    """주문 실행 클래스"""
    
    def __init__(self, exchange_api, db_manager, symbol, test_mode=False):
        """
        주문 실행기 초기화
        
        Args:
            exchange_api: 거래소 API 인스턴스
            db_manager: 데이터베이스 관리자 인스턴스
            symbol (str): 거래 심볼 (예: 'BTC/USDT')
            test_mode (bool): 테스트 모드 여부
        """
        self.exchange_api = exchange_api
        self.db = db_manager
        self.symbol = symbol
        self.test_mode = test_mode
        self.min_order_qty = self._get_min_order_qty()
        self.logger = logger  # 로거 참조
        
        # 기본 심볼 구성 요소 분리
        self.base_currency = symbol.split('/')[0]  # BTC, ETH 등
        self.quote_currency = symbol.split('/')[1]  # USDT, USD 등
    
    def _get_min_order_qty(self) -> float:
        """거래소의 최소 주문 수량 가져오기"""
        try:
            market_info = self.exchange_api.get_market_info(self.symbol)
            if market_info and 'limits' in market_info and 'amount' in market_info['limits']:
                return market_info['limits']['amount']['min']
            return 0.001  # 기본값
        except Exception as e:
            self.logger.error(f"최소 주문 수량 가져오기 실패: {e}")
            return 0.001  # 오류 발생 시 기본값 사용
    
    @api_error_handler(retry_count=2, max_delay=5)
    def get_current_price(self, symbol=None):
        """
        현재 시장 가격을 조회합니다.
        
        Args:
            symbol (str, optional): 조회할 심볼. None일 경우 기본 심볼 사용
            
        Returns:
            float: 현재 가격. 오류 발생시 0 반환
        """
        try:
            target_symbol = symbol or self.symbol
            ticker = self.exchange_api.get_ticker(target_symbol)
            
            if ticker and 'last' in ticker:
                return float(ticker['last'])
            else:
                self.logger.warning(f"{target_symbol}의 현재 가격 정보를 찾을 수 없습니다.")
                return 0
        except Exception as e:
            self.logger.error(f"현재 가격 조회 중 오류: {e}")
            return 0
    
    def _simulate_order(self, order_time, side, price, quantity, percentage=1.0):
        """
        주문 시뮬레이션 통합 메서드
        
        Args:
            order_time (datetime): 주문 시간
            side (str): 주문 유형 ('buy' 또는 'sell')
            price (float): 가격
            quantity (float): 수량
            percentage (float, optional): 포지션 청산 비율 (매도 시에만 사용)
            
        Returns:
            dict: 시뮬레이션된 주문 객체
        """
        order_id = f"test_{side.lower()}_{order_time.timestamp()}"
        
        order = {
            'id': order_id,
            'datetime': order_time.isoformat(),
            'symbol': self.symbol,
            'type': 'market',
            'side': side.lower(),
            'price': price,
            'amount': quantity,
            'cost': price * quantity,
            'fee': price * quantity * 0.001,  # 0.1% 수수료 가정
            'status': 'closed'
        }
        
        # 매도 주문인 경우 청산 비율 추가
        if side.lower() == 'sell':
            order['percentage_sold'] = percentage
            
        return order
    
    @trade_error_handler(retry_count=2, max_delay=10)
    def execute_buy(self, price, quantity, portfolio, additional_info=None, close_position=False, position_id=None):
        """
        매수 주문 실행
        
        Args:
            price (float): 매수 가격
            quantity (float): 매수 수량
            portfolio (dict): 포트폴리오 정보
            additional_info (dict, optional): 추가 정보 (자동 손절매/이익실현 등에 의한 포지션 종료 정보)
            close_position (bool, optional): 숏 포지션 종료를 위한 매수인지 여부
            position_id (str, optional): 포지션 ID (종료 시 사용)
        
        Returns:
            dict: 주문 결과
        """
        try:
            order_time = datetime.now()
            
            self.logger.info("=" * 60)
            self.logger.info("매수 주문 실행 시작")
            self.logger.info(f"  - 심볼: {self.symbol}")
            self.logger.info(f"  - 가격: {price}")
            self.logger.info(f"  - 수량: {quantity}")
            self.logger.info(f"  - 예상 금액: {price * quantity:.2f} {self.quote_currency}")
            self.logger.info(f"  - 모드: {'테스트' if self.test_mode else '실거래'}")
            self.logger.info(f"  - 포지션 종료: {close_position}")
            if additional_info:
                self.logger.info(f"  - 추가 정보: {additional_info}")
            self.logger.info("=" * 60)
            
            # 포지션 종료인지 여부 검사 (숏 포지션 청산)
            if close_position:
                # 포지션 ID가 지정된 경우 해당 포지션을 찾아서 종료 처리
                if position_id and portfolio['positions']:
                    for idx, pos in enumerate(portfolio['positions']):
                        if pos.get('id') == position_id or pos.get('position_id') == position_id:
                            self.logger.info(f"숏 포지션 청산: ID={position_id}, 가격={price}, 수량={quantity}")
                            # 포지션 상태 업데이트
                            portfolio['positions'][idx]['status'] = 'closed'
                            portfolio['positions'][idx]['closed_at'] = order_time.isoformat()
                            
                            # 데이터베이스에 포지션 업데이트
                            self.db.update_position(position_id, {
                                'status': 'closed',
                                'closed_at': order_time.isoformat(),
                                'close_price': price
                            })
                            break
                            
            if self.test_mode:
                self.logger.info(f"[테스트 모드] 실제 주문을 실행하지 않고 시뮬레이션합니다.")
                self.logger.info(f"[테스트 모드] 매수 주문 시뮬레이션: 가격={price}, 수량={quantity}")
                # 테스트 모드에서는 주문을 시뮬레이션
                order = self._simulate_order(order_time, 'buy', price, quantity)
                
                # 포트폴리오 업데이트는 호출자가 담당
                
                # 숏 포지션 청산이 아닌 경우에만 새 포지션 생성
                if not close_position:
                    # 추가 정보 처리
                    position_additional_info = {
                        'order_id': order['id'],
                        'test_mode': True
                    }
                    
                    # 사용자 정의 추가 정보가 있는 경우 병합
                    if additional_info:
                        position_additional_info.update(additional_info)
                        
                    # Position 객체 생성
                    position = Position(
                        id=f"pos_{int(time.time() * 1000)}",  # 고유 ID 생성
                        symbol=self.symbol,
                        side='long',
                        amount=quantity,  # 표준 필드명 사용
                        entry_price=price,
                        leverage=self.exchange_api.leverage if hasattr(self.exchange_api, 'leverage') else 1,
                        opened_at=order_time,
                        status='open',
                        additional_info=position_additional_info
                    )
                    
                    # 포트폴리오에 새 포지션 추가 (딕셔너리로 변환)
                    portfolio['positions'].append(position.to_dict())
                    
                    # 데이터베이스에 포지션 저장
                    self.db.save_position(position)
                    
                    self.logger.info(f"[테스트 모드] 새로운 롱 포지션 생성: 가격={price}, 수량={quantity}")
                
                # 거래 내역 추가
                trade_record = {
                    'symbol': self.symbol,
                    'side': 'buy',
                    'order_type': 'market',
                    'amount': quantity,
                    'price': price,
                    'cost': price * quantity,
                    'fee': price * quantity * 0.001,
                    'timestamp': order_time.isoformat(),
                    'additional_info': {
                        'order_id': order['id'],
                        'test_mode': True
                    }
                }
                
                # 데이터베이스에 거래 내역 저장
                self.db.save_trade(trade_record)
                
                self.logger.info(f"[테스트] 매수 주문 실행: 가격={price}, 수량={quantity}, 비용={price * quantity}")
                return order
                
            else:
                # 실제 거래소 주문 실행
                try:
                    # 거래소 API를 통한 실제 매수 주문
                    order = self.exchange_api.create_market_buy_order(
                        symbol=self.symbol,
                        amount=quantity
                    )
                    
                    self.logger.info(f"매수 주문 성공: {order['id']}, 가격: {price}, 수량: {quantity}")
                    
                    # 숏 포지션 청산이 아닌 경우 포지션 생성
                    if not close_position:
                        # 추가 정보 처리
                        position_additional_info = {
                            'order_id': order['id'],
                            'test_mode': False
                        }
                        
                        # 사용자 정의 추가 정보가 있뜸 경우 병합
                        if additional_info:
                            position_additional_info.update(additional_info)
                            
                        # Position 객체 생성
                        position = Position(
                            id=f"pos_{order['id']}",  # 주문 ID로 포지션 ID 생성
                            symbol=self.symbol,
                            side='long',
                            amount=quantity,  # 표준 필드명 사용
                            entry_price=price,
                            leverage=self.exchange_api.leverage if hasattr(self.exchange_api, 'leverage') else 1,
                            opened_at=order_time,
                            status='open',
                            additional_info=position_additional_info
                        )
                        
                        # 포트폴리오에 포지션 추가 (딕셔너리로 변환)
                        portfolio['positions'].append(position.to_dict())
                        
                        # 데이터베이스에 포지션 저장
                        self.db.save_position(position)
                        
                        self.logger.info(f"새로운 롱 포지션 생성: 가격={price}, 수량={quantity}")
                    
                    # 거래 내역 추가
                    trade_record = {
                        'symbol': self.symbol,
                        'side': 'buy',
                        'order_type': 'market',
                        'amount': quantity,
                        'price': price,
                        'cost': price * quantity,
                        'fee': order.get('fee', {}).get('cost', price * quantity * 0.001),
                        'timestamp': order_time.isoformat(),
                        'additional_info': {
                            'order_id': order['id'],
                            'test_mode': False
                        }
                    }
                    
                    # 데이터베이스에 거래 내역 저장
                    self.db.save_trade(trade_record)
                    
                    return order
                    
                except Exception as e:
                    self.logger.error(f"매수 주문 실행 중 오류 발생: {e}")
                    return None
                
        except Exception as e:
            self.logger.error(f"매수 주문 처리 중 오류 발생: {e}")
            return None
    
    @trade_error_handler(retry_count=2, max_delay=10)
    def execute_sell(self, price, quantity, portfolio, additional_exit_info=None, percentage=1.0, position_id=None):
        """
        매도 주문 실행
        
        Args:
            price (float): 매도 가격
            quantity (float): 매도 수량
            portfolio (dict): 포트폴리오 정보
            additional_exit_info (dict, optional): 추가 종료 정보 (자동 손절매/이익실현 관련)
            percentage (float, optional): 포지션 청산 비율 (0.0-1.0)
            position_id (str, optional): 특정 포지션 ID (지정 시 해당 포지션만 처리)
        
        Returns:
            dict: 주문 결과
        """
        try:
            order_time = datetime.now()
            
            # 청산 수량 설정 및 검증
            actual_quantity = quantity
            is_partial = percentage < 1.0
            
            # 부분 청산 설정
            if is_partial:
                actual_quantity = quantity * percentage
            
            # 최소 주문 수량 확인
            min_order_qty = self.min_order_qty
            if actual_quantity < min_order_qty:
                self.logger.warning(f"계산된 매도 수량({actual_quantity})이 최소 주문 수량({min_order_qty})보다 작아 주문을 중단합니다.")
                return None
        
            # 포지션 잔여량 검증
            remaining = quantity - actual_quantity
            if 0 < remaining < min_order_qty:
                self.logger.warning(f"잔여량이 최소 주문 수량보다 작음. 전량 청산으로 변경: {remaining} < {min_order_qty}")
                actual_quantity = quantity
                percentage = 1.0
                is_partial = False
                
            if actual_quantity <= 0:
                self.logger.warning("청산할 수량이 0 이하입니다.")
                return None
                
            # 현재 가격 확인
            current_price = price if price > 0 else self.get_current_price(self.symbol)
            
            if current_price <= 0:
                self.logger.error("유효하지 않은 현재 가격")
                return None
                
            self.logger.info("=" * 60)
            self.logger.info("매도 주문 실행 시작")
            self.logger.info(f"  - 심볼: {self.symbol}")
            self.logger.info(f"  - 가격: {current_price}")
            self.logger.info(f"  - 수량: {actual_quantity}")
            self.logger.info(f"  - 예상 금액: {current_price * actual_quantity:.2f} {self.quote_currency}")
            self.logger.info(f"  - 모드: {'테스트' if self.test_mode else '실거래'}")
            self.logger.info(f"  - 청산 비율: {percentage * 100:.1f}%")
            self.logger.info(f"  - 부분 청산: {'예' if is_partial else '아니오'}")
            if position_id:
                self.logger.info(f"  - 포지션 ID: {position_id}")
            if additional_exit_info:
                self.logger.info(f"  - 추가 정보: {additional_exit_info}")
            self.logger.info("=" * 60)
            
            # 포지션 찾기 및 업데이트
            position_found = False
            if position_id and portfolio.get('positions'):
                for idx, pos in enumerate(portfolio['positions']):
                    if pos.get('id') == position_id or pos.get('position_id') == position_id:
                        position_found = True
                        
                        if is_partial:
                            # 부분 청산의 경우 수량 업데이트
                            self.logger.info(f"부분 청산: ID={position_id}, 비율={percentage * 100:.1f}%")
                            portfolio['positions'][idx]['contracts'] = remaining
                            
                            # 데이터베이스에 포지션 업데이트
                            self.db.update_position(position_id, {
                                'contracts': remaining,
                                'last_updated': order_time.isoformat()
                            })
                        else:
                            # 전체 청산의 경우 포지션 종료
                            self.logger.info(f"전체 청산: ID={position_id}")
                            portfolio['positions'][idx]['status'] = 'closed'
                            portfolio['positions'][idx]['closed_at'] = order_time.isoformat()
                            portfolio['positions'][idx]['close_price'] = current_price
                            
                            # 데이터베이스에 포지션 업데이트
                            self.db.update_position(position_id, {
                                'status': 'closed',
                                'closed_at': order_time.isoformat(),
                                'close_price': current_price
                            })
                        break
            
            if position_id and not position_found:
                self.logger.warning(f"포지션 ID {position_id}를 찾을 수 없습니다.")
            
            if self.test_mode:
                self.logger.info(f"[테스트 모드] 실제 주문을 실행하지 않고 시뮬레이션합니다.")
                self.logger.info(f"[테스트 모드] 매도 주문 시뮬레이션: 가격={current_price}, 수량={actual_quantity}")
                # 테스트 모드에서는 주문을 시뮬레이션
                order = self._simulate_order(order_time, 'sell', current_price, actual_quantity, percentage)
                
                # 테스트 모드에서도 거래 내역 저장
                trade_record = {
                    'symbol': self.symbol,
                    'side': 'sell',
                    'order_type': 'market',
                    'amount': actual_quantity,
                    'price': current_price,
                    'cost': current_price * actual_quantity,
                    'fee': current_price * actual_quantity * 0.001,  # 0.1% 수수료
                    'timestamp': order_time.isoformat(),
                    'additional_info': {
                        'order_id': order['id'],
                        'test_mode': True,
                        'percentage': percentage,
                        'is_partial': is_partial
                    }
                }
                
                # additional_exit_info가 있으면 추가
                if additional_exit_info:
                    trade_record['additional_info'].update(additional_exit_info)
                
                # 데이터베이스에 거래 내역 저장
                self.db.save_trade(trade_record)
                
                return order
            else:
                try:
                    # 거래소 API를 통한 실제 매도 주문
                    order = self.exchange_api.create_market_sell_order(
                        symbol=self.symbol,
                        amount=actual_quantity
                    )
                    
                    self.logger.info(f"매도 주문 성공: {order['id']}, 가격: {current_price}, 수량: {actual_quantity}")
                    
                    # 거래 내역 추가
                    trade_record = {
                        'symbol': self.symbol,
                        'side': 'sell',
                        'order_type': 'market',
                        'amount': actual_quantity,
                        'price': current_price,
                        'cost': current_price * actual_quantity,
                        'fee': order.get('fee', {}).get('cost', current_price * actual_quantity * 0.001),
                        'timestamp': order_time.isoformat(),
                        'additional_info': {
                            'order_id': order['id'],
                            'test_mode': False,
                            'percentage': percentage,
                            'is_partial': is_partial
                        }
                    }
                    
                    # additional_exit_info가 있으면 추가
                    if additional_exit_info:
                        trade_record['additional_info'].update(additional_exit_info)
                    
                    # 데이터베이스에 거래 내역 저장
                    self.db.save_trade(trade_record)
                    
                    return order
                    
                except Exception as e:
                    self.logger.error(f"매도 주문 실행 중 오류 발생: {e}")
                    return None
                
        except Exception as e:
            self.logger.error(f"매도 주문 처리 중 오류 발생: {e}")
            return None
    
    @trade_error_handler(retry_count=3, max_delay=15)
    def close_position(self, position_id, portfolio, symbol=None, side=None, amount=None, reason=None):
        """
        포지션 청산
        
        Args:
            position_id (str): 포지션 ID
            portfolio (dict): 포트폴리오 정보
            symbol (str, optional): 거래 심볼 (지정하지 않으면 기본값 사용)
            side (str, optional): 포지션 방향 ('long' 또는 'short')
            amount (float, optional): 청산할 수량 (지정하지 않으면 전체 청산)
            reason (str, optional): 청산 이유
            
        Returns:
            dict: 주문 결과 또는 None (실패 시)
        """
        try:
            # 현재 포지션 찾기
            target_position = None
            for pos in portfolio['positions']:
                if pos.get('id') == position_id or pos.get('position_id') == position_id:
                    if pos['status'] == 'open':
                        target_position = pos
                        break
            
            if not target_position:
                self.logger.warning(f"포지션 {position_id}를 찾을 수 없거나 이미 종료됨")
                return None
            
            # 심볼, 포지션 방향, 수량 정보 설정
            symbol = symbol or target_position.get('symbol', self.symbol)
            side = side or target_position.get('side', 'long')
            position_amount = target_position.get('amount', 0)
            
            # 청산할 수량 확인
            if amount is None or amount >= position_amount:
                amount = position_amount
                partial = False
            else:
                partial = True
            
            if amount <= 0:
                self.logger.warning("청산할 수량이 0 이하입니다.")
                return None
                
            # 현재 가격 확인
            current_price = self.exchange_api.get_current_price(symbol)
            
            if current_price <= 0:
                self.logger.error("유효하지 않은 현재 가격")
                return None
                
            # 청산 실행
            self.logger.info(f"포지션 {position_id} 청산 시도: {symbol}, {side}, 수량={amount}, 이유={reason}")
            
            # 추가 종료 정보
            additional_exit_info = {
                'exit_type': 'manual' if not reason else 'auto',
                'exit_reason': reason or '수동 종료',
                'auto_exit': bool(reason)
            }
            
            # 포지션 방향에 따른 주문 방향 결정
            if side.lower() == 'long':
                # 롱 포지션 청산 = 매도
                percentage = amount / position_amount if partial else 1.0
                return self.execute_sell(
                    price=current_price,
                    quantity=amount,
                    portfolio=portfolio,
                    additional_exit_info=additional_exit_info,
                    percentage=percentage,
                    position_id=position_id
                )
            else:
                # 숏 포지션 청산 = 매수
                return self.execute_buy(
                    price=current_price,
                    quantity=amount,
                    portfolio=portfolio,
                    additional_info=additional_exit_info,
                    close_position=True,
                    position_id=position_id
                )
                
        except Exception as e:
            self.logger.error(f"포지션 청산 중 오류 발생: {e}")
            return None
