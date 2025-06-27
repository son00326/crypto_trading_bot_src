"""
포트폴리오 관리 모듈 - 암호화폐 자동매매 봇

이 모듈은 포트폴리오 관리 로직을 담당하는 PortfolioManager 클래스를 구현합니다.
TradingAlgorithm에서 포트폴리오 관련 로직을 분리하여 책임을 명확히 합니다.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Union, List, Tuple

from src.error_handlers import (
    simple_error_handler, safe_execution, api_error_handler,
    network_error_handler, db_error_handler, trade_error_handler
)
from src.event_manager import get_event_manager, EventType

# 로거 설정
logger = logging.getLogger('portfolio_manager')

class PortfolioManager:
    """포트폴리오 관리 클래스"""
    
    def __init__(self, exchange_api, db_manager, symbol, initial_balance=None, test_mode=False):
        """
        포트폴리오 관리자 초기화
        
        Args:
            exchange_api: 거래소 API 인스턴스
            db_manager: 데이터베이스 관리자 인스턴스
            symbol (str): 거래 심볼 (예: 'BTC/USDT')
            initial_balance (float, optional): 초기 잔액 (테스트 모드에서만 사용)
            test_mode (bool): 테스트 모드 여부
        """
        self.exchange_api = exchange_api
        self.db = db_manager
        self.symbol = symbol
        self.test_mode = test_mode
        
        # 기본 심볼 구성 요소 분리
        self.base_currency = symbol.split('/')[0]  # BTC, ETH 등
        self.quote_currency = symbol.split('/')[1]  # USDT, USD 등
        
        # 포트폴리오 초기화
        self.portfolio = {
            'base_currency': self.base_currency,
            'quote_currency': self.quote_currency,
            'base_balance': 0,
            'quote_balance': initial_balance if initial_balance else 0,
            'positions': [],
            'trade_history': []
        }
        
        # 이벤트 관리자 참조
        self.event_manager = get_event_manager()
        
        # 초기 포트폴리오 상태 업데이트
        self.update_portfolio()
    
    @simple_error_handler(default_return=False)
    def update_portfolio(self):
        """
        포트폴리오 정보 업데이트
        
        Returns:
            bool: 성공 여부
        """
        try:
            if self.test_mode:
                # 테스트 모드에서는 포트폴리오 정보를 시뮬레이션
                return True
            
            # 실제 거래소에서 잔고 정보 가져오기
            balance = self.exchange_api.get_balance()
            
            if balance:
                base_currency = self.portfolio['base_currency']
                quote_currency = self.portfolio['quote_currency']
                
                # 기본 통화 잔고 (BTC, ETH 등)
                if base_currency in balance['free']:
                    self.portfolio['base_balance'] = float(balance['free'][base_currency])
                
                # 견적 통화 잔고 (USDT, USD 등)
                if quote_currency in balance['free']:
                    self.portfolio['quote_balance'] = float(balance['free'][quote_currency])
                
                logger.info(f"포트폴리오 업데이트: {base_currency}={self.portfolio['base_balance']}, {quote_currency}={self.portfolio['quote_balance']}")
                
                # 데이터베이스에 잔액 정보 저장
                try:
                    self.db.save_balances(balance)
                    logger.info("데이터베이스에 잔액 정보 저장 완료")
                except Exception as db_error:
                    logger.error(f"데이터베이스 잔액 저장 중 오류: {db_error}")
            
            # 포트폴리오 업데이트 이벤트 발행
            self.event_manager.publish(EventType.PORTFOLIO_UPDATED, {
                'portfolio': self.portfolio,
                'symbol': self.symbol,
                'updated_at': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"포트폴리오 업데이트 중 오류 발생: {e}")
            return False
        
        return True
    
    @simple_error_handler(default_return=False)
    def update_portfolio_after_trade(self, trade_type, price, quantity, fee=None, is_test=None):
        """
        거래 후 포트폴리오 업데이트
        
        Args:
            trade_type (str): 거래 유형 ('buy' 또는 'sell')
            price (float): 거래 가격
            quantity (float): 거래 수량
            fee (float, optional): 수수료, None인 경우 기본값 사용
            is_test (bool, optional): 테스트 모드 여부, None인 경우 현재 객체 상태 사용
            
        Returns:
            bool: 성공 여부
        """
        # 테스트 모드 여부 확인
        test_mode = is_test if is_test is not None else self.test_mode
        
        # 기본 수수료 계산 (0.1%)
        if fee is None:
            fee = price * quantity * 0.001
            
        # 거래 유형에 따른 포트폴리오 업데이트
        if trade_type.lower() == 'buy':
            # 매수 거래
            self.portfolio['base_balance'] += quantity
            self.portfolio['quote_balance'] -= (price * quantity) + fee
        elif trade_type.lower() == 'sell':
            # 매도 거래
            self.portfolio['base_balance'] -= quantity
            self.portfolio['quote_balance'] += (price * quantity) - fee
        
        # 실제 모드인 경우 실제 잔고 업데이트 시도
        if not test_mode:
            self.update_portfolio()
        
        # 데이터베이스에 잔고 정보 저장
        self.db.save_balance(self.portfolio['base_currency'], self.portfolio['base_balance'])
        self.db.save_balance(self.portfolio['quote_currency'], self.portfolio['quote_balance'])
        
        logger.info(f"거래 후 포트폴리오 업데이트: {trade_type}, 가격={price}, 수량={quantity}, 수수료={fee if fee else '기본값'}")
        
        # 거래 실행 이벤트 발행
        self.event_manager.publish(EventType.TRADE_EXECUTED, {
            'trade': {
                'type': trade_type,
                'price': price,
                'quantity': quantity,
                'fee': fee,
                'symbol': self.symbol,
                'timestamp': datetime.now().isoformat()
            },
            'portfolio': self.portfolio
        })
        
        return True
    
    @db_error_handler(retry_count=3)
    def update_position_after_exit(self, order, order_time, price, actual_quantity, percentage, position_id=None, additional_exit_info=None):
        """
        포지션 청산 후 포지션 정보 업데이트
        
        Args:
            order (dict): 주문 정보
            order_time (datetime): 주문 시간
            price (float): 종료 가격
            actual_quantity (float): 실제 청산된 수량
            percentage (float): 포지션 청산 비율 (0.0-1.0)
            position_id (str, optional): 특정 포지션 ID
            additional_exit_info (dict, optional): 추가 종료 정보 (자동 손절매/이익실현 관련)
        """
        target_position_id = position_id
        found_position = False
        
        for i, position in enumerate(self.portfolio['positions']):
            if position['status'] == 'open' and position['side'] == 'long':
                found_position = True
                
                # 지정된 position_id가 있으면 해당 포지션만 처리
                if target_position_id and position.get('id') != target_position_id:
                    continue
                    
                # 수익/손실 계산
                pnl = (price - position['entry_price']) * actual_quantity
                profit_pct = (price - position['entry_price']) / position['entry_price'] * 100
                
                # 부분 청산인 경우
                if percentage < 1.0:
                    # 수량 및 평균 진입가 조정
                    remaining_amount = position['amount'] - actual_quantity
                    logger.info(f"포지션 부분 청산: {actual_quantity} 청산, {remaining_amount} 남음")
                    
                    # 포트폴리오 업데이트 - 남은 수량 반영
                    self.portfolio['positions'][i]['amount'] = remaining_amount
                    self.portfolio['positions'][i]['partial_exits'] = self.portfolio['positions'][i].get('partial_exits', []) + [{
                        'time': order_time.isoformat(),
                        'price': price,
                        'amount': actual_quantity,
                        'percentage': percentage,
                        'pnl': pnl,
                        'profit_pct': profit_pct
                    }]
                else:
                    # 전체 청산인 경우
                    self.portfolio['positions'][i]['closed_at'] = order_time.isoformat()
                    self.portfolio['positions'][i]['status'] = 'closed'
                    self.portfolio['positions'][i]['pnl'] = pnl
                    self.portfolio['positions'][i]['exit_price'] = price
                
                # 추가 종료 정보 처리
                exit_info = {
                    'exit_price': price,
                    'profit_pct': (price - position['entry_price']) / position['entry_price'] * 100,
                    'exit_order_id': order['id']
                }
                
                # 자동 종료(손절매/이익실현) 정보가 있는 경우 추가
                if additional_exit_info:
                    exit_info.update({
                        'exit_type': additional_exit_info.get('exit_type', 'manual'),
                        'exit_reason': additional_exit_info.get('exit_reason', ''),
                        'auto_exit': additional_exit_info.get('auto_exit', False)
                    })
                    
                    # 로그 추가
                    exit_type = additional_exit_info.get('exit_type', 'manual')
                    logger.info(f"자동 종료 실행: {exit_type}, 이유: {additional_exit_info.get('exit_reason', '')}")
                
                # 데이터베이스 업데이트 데이터 준비
                # 포지션 ID 가져오기
                pos_id = None
                if 'id' in position:
                    pos_id = position['id']
                
                # 데이터베이스 업데이트 데이터 구성
                update_data = {
                    'additional_info': exit_info
                }
                
                # 부분 청산이냐 전체 청산이냐에 따라 다른 데이터 추가
                if percentage < 1.0:
                    # 부분 청산인 경우
                    partial_exit_data = {
                        'time': order_time.isoformat(),
                        'price': price,
                        'amount': actual_quantity,
                        'percentage': percentage,
                        'pnl': (price - position['entry_price']) * actual_quantity,
                        'exit_type': additional_exit_info.get('exit_type', 'manual') if additional_exit_info else 'manual',
                        'exit_reason': additional_exit_info.get('exit_reason', '') if additional_exit_info else ''
                    }
                    
                    # 기존 부분 청산 이력 업데이트
                    update_data['partial_exits'] = position.get('partial_exits', []) + [partial_exit_data]
                    update_data['amount'] = position['amount'] - actual_quantity
                    logger.info(f"부분 청산 정보 업데이트: {percentage:.1%}, 남은 수량: {update_data['amount']}")
                else:
                    # 전체 청산인 경우
                    update_data.update({
                        'closed_at': order_time.isoformat(),
                        'status': 'closed',
                        'pnl': (price - position['entry_price']) * position['amount'],
                        'exit_price': price
                    })
                    logger.info(f"포지션 전체 청산 정보 업데이트")
                
                # 데이터베이스에 업데이트
                if pos_id:
                    # 이미 ID가 있는 경우
                    self.db.update_position(pos_id, update_data)
                else:
                    # 데이터베이스에서 포지션 찾기
                    open_positions = self.db.get_open_positions(self.symbol)
                    for op in open_positions:
                        if op['status'] == 'open' and op['side'] == 'long':
                            self.db.update_position(op['id'], update_data)
                            break
                break
                
        # 거래 내역 추가
        trade_record = {
            'symbol': self.symbol,
            'side': 'sell',
            'order_type': 'market',
            'amount': actual_quantity,
            'price': price,
            'cost': price * actual_quantity,
            'fee': price * actual_quantity * 0.001,
            'timestamp': order_time.isoformat(),
            'position_id': position_id,
            'additional_info': {
                'order_id': order['id'],
                'test_mode': self.test_mode
            }
        }
        self.portfolio['trade_history'].append(trade_record)
        
        # 데이터베이스에 거래 내역 저장
        self.db.save_trade(trade_record)
        
        # 현재 상태 저장
        self.save_state()
        
        if self.test_mode:
            logger.info(f"[테스트] 매도 주문 실행: 가격={price}, 수량={actual_quantity}, 수익={price * actual_quantity}")
    
    @simple_error_handler(default_return=[])
    @api_error_handler(retry_count=3, max_delay=20)
    def get_open_positions_data(self):
        """
        현재 열린 포지션 데이터 반환 (백업용)
        
        Returns:
            Dict: 열린 포지션 정보
        """
        try:
            symbol = self.symbol  # 현재 설정된 심볼 사용
            open_positions = self.get_open_positions(symbol)
            
            return {
                'count': len(open_positions),
                'positions': open_positions,
                'symbol': symbol,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"열린 포지션 데이터 수집 중 오류: {e}")
            return {'count': 0, 'positions': []}
    
    def get_recent_trades(self, limit=50):
        """
        최근 거래 내역 반환 (백업용)
        
        Args:
            limit: 반환할 거래 수
            
        Returns:
            List: 거래 내역 목록
        """
        try:
            trades = self.db.get_trades(self.symbol, limit=limit)
            return trades
        except Exception as e:
            logger.error(f"최근 거래 내역 조회 중 오류: {e}")
            return []
    
    def get_open_positions(self, symbol=None):
        """
        현재 열린 포지션 목록 조회
        
        Args:
            symbol (str, optional): 거래 심볼 (None인 경우 모든 심볼)
            
        Returns:
            list: 포지션 목록
        """
        # 조회할 심볼 결정
        symbol = symbol or self.symbol
        
        # 1. 테스트 모드인 경우 - 메모리에서 가져오기
        if self.test_mode:
            # 메모리 내 포트폴리오에서 열린 포지션만 필터링
            open_positions = [p for p in self.portfolio['positions'] if p['status'] == 'open']
            
            # 심볼이 지정된 경우 필터링
            if symbol:
                open_positions = [p for p in open_positions if p['symbol'] == symbol]
                
            return open_positions
            
        # 2. 실제 모드인 경우
        try:
            # 거래소 API를 통해 열린 포지션 정보 가져오기
            # 선물 거래인 경우
            if hasattr(self.exchange_api, 'is_futures') and self.exchange_api.is_futures:
                try:
                    positions = self.exchange_api.get_positions(symbol)
                    # 포지션 정보 가공
                    result = []
                    for pos in positions:
                        if abs(float(pos['contracts'])) > 0:  # 계약 수량이 있는 경우만
                            position_info = {
                                'id': f"pos_{pos['symbol']}_{pos['side']}",
                                'symbol': pos['symbol'],
                                'side': pos['side'].lower(),
                                'amount': abs(float(pos['contracts'])),
                                'entry_price': float(pos['entryPrice']),
                                'liquidation_price': float(pos.get('liquidationPrice', 0)),
                                'margin': float(pos.get('initialMargin', 0)),
                                'leverage': float(pos.get('leverage', 1)),
                                'status': 'open',
                                'pnl': float(pos.get('unrealizedPnl', 0)),
                                'opened_at': datetime.fromtimestamp(pos.get('timestamp', 0)/1000).isoformat() if 'timestamp' in pos else datetime.now().isoformat()
                            }
                            result.append(position_info)
                    return result
                except Exception as e:
                    logger.error(f"선물 포지션 조회 오류: {e}")
                    # 실패 시 데이터베이스에서 가져오기
                    return self.db.get_open_positions(symbol)
            else:
                # 현물 거래는 데이터베이스에서만 포지션 관리
                return self.db.get_open_positions(symbol)
        except Exception as e:
            logger.error(f"포지션 조회 과정에서 예상치 못한 오류: {e}")
            return []
    
    def save_state(self):
        """
        현재 포트폴리오 상태를 저장
        
        Returns:
            bool: 성공 여부
        """
        try:
            self.db.save_balance(self.portfolio['base_currency'], self.portfolio['base_balance'])
            self.db.save_balance(self.portfolio['quote_currency'], self.portfolio['quote_balance'])
            
            logger.info("포트폴리오 상태 저장 완료")
            return True
        except Exception as e:
            logger.error(f"포트폴리오 상태 저장 중 오류 발생: {e}")
            return False
    
    @simple_error_handler(default_return=None)
    def get_portfolio_status(self):
        """
        현재 포트폴리오 상태 정보 반환
        
        Returns:
            dict: 포트폴리오 상태 정보
        """
        try:
            if not self.test_mode:
                # 실제 모드에서는 최신 잔고 정보 가져오기
                self.update_portfolio()
                
            # 현재 심볼에 대한 열린 포지션 정보 추가
            open_positions = self.get_open_positions(self.symbol)
            
            # 포트폴리오 상태 구성
            portfolio_status = {
                'base_currency': self.portfolio['base_currency'],
                'quote_currency': self.portfolio['quote_currency'],
                'base_balance': self.portfolio['base_balance'],
                'quote_balance': self.portfolio['quote_balance'],
                'positions': open_positions,
                'symbol': self.symbol,
                'timestamp': datetime.now().isoformat()
            }
            
            return portfolio_status
            
        except Exception as e:
            logger.error(f"포트폴리오 상태 조회 중 오류 발생: {e}")
            return None
    
    def add_position(self, position):
        """
        포트폴리오에 새 포지션 추가
        
        Args:
            position (dict): 포지션 정보
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 포지션이 없는지 확인
            for existing_pos in self.portfolio['positions']:
                if existing_pos.get('id') == position.get('id'):
                    logger.warning(f"포지션 ID '{position.get('id')}'가 이미 존재합니다")
                    return False
            
            # 새 포지션 추가
            self.portfolio['positions'].append(position)
            logger.info(f"새 포지션 추가됨: {position.get('id')}, 심볼: {position.get('symbol')}, 수량: {position.get('amount')}")
            
            # 포지션 오픈 이벤트 발행
            self.event_manager.publish(EventType.POSITION_OPENED, {
                'position': position,
                'position_id': position.get('id'),
                'timestamp': datetime.now().isoformat()
            })
            
            return True
        except Exception as e:
            logger.error(f"포지션 추가 중 오류 발생: {e}")
            return False
    
    def add_trade_record(self, trade):
        """
        포트폴리오에 거래 기록 추가
        
        Args:
            trade (dict): 거래 정보
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 거래 기록 추가
            self.portfolio['trade_history'].append(trade)
            # 데이터베이스에 저장
            self.db.save_trade(trade)
            return True
        except Exception as e:
            logger.error(f"거래 기록 추가 중 오류 발생: {e}")
            return False
    
    @safe_execution(retry_count=1)
    def calculate_position_size(self, price, risk_manager=None):
        """
        위험 관리 설정에 따른 포지션 크기 계산
        
        Args:
            price (float): 현재 가격
            risk_manager: 위험 관리자 인스턴스 (선택적)
            
        Returns:
            float: 매수/매도할 수량
        """
        try:
            # 사용 가능한 자산
            available_balance = self.portfolio['quote_balance']
            
            # RiskManager를 통한 포지션 크기 계산
            if risk_manager:
                quantity = risk_manager.calculate_position_size(available_balance, price)
            else:
                # 간단한 기본값 로직 (가용 자산의 30% 사용)
                quantity = (available_balance * 0.3) / price
            
            # 최소 주문 수량 확인 (거래소마다 다름)
            min_quantity = 0.0001  # 예시 값, 실제로는 거래소별로 다름
            
            if quantity < min_quantity:
                logger.warning(f"계산된 수량({quantity})이 최소 주문 수량({min_quantity})보다 작습니다.")
                return 0
            
            return quantity
        
        except Exception as e:
            logger.error(f"포지션 크기 계산 중 오류 발생: {e}")
            return 0
