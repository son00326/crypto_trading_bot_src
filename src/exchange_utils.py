"""
거래소 유틸리티 모듈 - 암호화폐 자동매매 봇

이 모듈은 다양한 거래소별 기능 및 계산 방식을 구현합니다.
- 마진 계산
- 레버리지 관리
- 거래소별 특수 기능
"""

import logging
import traceback

# 로깅 설정
logger = logging.getLogger('crypto_bot.exchange_utils')

class MarginCalculator:
    """거래소별 마진 계산 유틸리티 클래스"""
    
    @staticmethod
    def calculate_margin_level(exchange_id, account_info):
        """
        거래소별 마진 레벨 계산
        
        Args:
            exchange_id (str): 거래소 ID
            account_info (dict): 계정 정보
            
        Returns:
            float: 마진 레벨 (값이 낮을수록 청산 위험이 높음)
        """
        try:
            # 바이낸스 마진 계산 방식
            if exchange_id.lower() == 'binance':
                return MarginCalculator._calculate_binance_margin_level(account_info)
            
            # 바이비트 마진 계산 방식
            elif exchange_id.lower() == 'bybit':
                return MarginCalculator._calculate_bybit_margin_level(account_info)
                
            # FTX 마진 계산 방식
            elif exchange_id.lower() == 'ftx':
                return MarginCalculator._calculate_ftx_margin_level(account_info)
                
            # 기타 거래소
            else:
                # 일반적인 계산 방식 사용
                return MarginCalculator._calculate_generic_margin_level(account_info)
                
        except Exception as e:
            logger.error(f"마진 레벨 계산 중 오류: {e}")
            logger.error(traceback.format_exc())
            return float('inf')  # 오류 발생 시 안전한 값 반환
    
    @staticmethod
    def _calculate_binance_margin_level(account_info):
        """
        바이낸스 마진 레벨 계산
        마진 레벨 = (지갑 잔고 + 미실현 손익) / 유지 증거금
        """
        try:
            # 필요한 데이터 추출
            wallet_balance = float(account_info.get('wallet_balance', account_info.get('totalWalletBalance', 0)))
            unrealized_pnl = float(account_info.get('unrealized_pnl', account_info.get('totalUnrealizedProfit', 0)))
            maintenance_margin = float(account_info.get('maintenance_margin', account_info.get('totalMaintenanceMargin', 0)))
            
            # 유효성 검사
            if wallet_balance <= 0:
                logger.warning(f"유효하지 않은 지갑 잔고: {wallet_balance}")
                return float('inf')
                
            if maintenance_margin <= 0:
                logger.debug(f"유지 증거금이 0 또는 음수입니다: {maintenance_margin}")
                return float('inf')
            
            # 마진 레벨 계산
            margin_level = (wallet_balance + unrealized_pnl) / maintenance_margin
            
            logger.info(f"바이낸스 마진 레벨: {margin_level:.4f} (지갑 잔고: {wallet_balance}, 미실현 손익: {unrealized_pnl}, 유지 증거금: {maintenance_margin})")
            return margin_level
            
        except Exception as e:
            logger.error(f"바이낸스 마진 레벨 계산 중 오류: {e}")
            logger.error(traceback.format_exc())
            return float('inf')
    
    @staticmethod
    def _calculate_bybit_margin_level(account_info):
        """
        바이비트 마진 레벨 계산
        마진 레벨 = 가용 잔고 / 초기 증거금
        """
        try:
            # 필요한 데이터 추출 (바이비트는 다른 키 사용)
            available_balance = float(account_info.get('available_balance', account_info.get('availableBalance', 0)))
            wallet_balance = float(account_info.get('wallet_balance', account_info.get('walletBalance', 0)))
            position_margin = float(account_info.get('position_margin', account_info.get('positionMargin', 0)))
            
            # 유효성 검사
            if wallet_balance <= 0:
                logger.warning(f"유효하지 않은 지갑 잔고: {wallet_balance}")
                return float('inf')
                
            if position_margin <= 0:
                logger.debug(f"포지션 증거금이 0 또는 음수입니다: {position_margin}")
                return float('inf')
            
            # 마진 레벨 계산
            margin_level = available_balance / position_margin
            
            logger.info(f"바이비트 마진 레벨: {margin_level:.4f} (가용 잔고: {available_balance}, 포지션 증거금: {position_margin})")
            return margin_level
            
        except Exception as e:
            logger.error(f"바이비트 마진 레벨 계산 중 오류: {e}")
            logger.error(traceback.format_exc())
            return float('inf')
    
    @staticmethod
    def _calculate_ftx_margin_level(account_info):
        """
        FTX 마진 레벨 계산
        마진 레벨 = 가용 담보 / 필요 담보
        """
        try:
            # 필요한 데이터 추출 (FTX는 다른 키 사용)
            collateral = float(account_info.get('collateral', account_info.get('freeCollateral', 0)))
            required_margin = float(account_info.get('required_margin', account_info.get('totalPositionSize', 0))) * 0.05  # 대략적인 계산
            
            # 유효성 검사
            if collateral <= 0:
                logger.warning(f"유효하지 않은 담보 잔고: {collateral}")
                return float('inf')
                
            if required_margin <= 0:
                logger.debug(f"필요 증거금이 0 또는 음수입니다: {required_margin}")
                return float('inf')
            
            # 마진 레벨 계산
            margin_level = collateral / required_margin
            
            logger.info(f"FTX 마진 레벨: {margin_level:.4f} (담보: {collateral}, 필요 증거금: {required_margin})")
            return margin_level
            
        except Exception as e:
            logger.error(f"FTX 마진 레벨 계산 중 오류: {e}")
            logger.error(traceback.format_exc())
            return float('inf')
    
    @staticmethod
    def _calculate_generic_margin_level(account_info):
        """
        일반적인 마진 레벨 계산 (다른 거래소에 적용 가능)
        """
        try:
            # 최대한 다양한 키를 시도하여 필요한 값 추출
            wallet_balance = float(account_info.get('wallet_balance', 
                                  account_info.get('walletBalance', 
                                  account_info.get('balance', 
                                  account_info.get('equity', 0)))))
            
            unrealized_pnl = float(account_info.get('unrealized_pnl', 
                                  account_info.get('unrealizedPnl', 
                                  account_info.get('pnl', 0))))
            
            maintenance_margin = float(account_info.get('maintenance_margin', 
                                      account_info.get('maintenanceMargin', 
                                      account_info.get('margin', 0))))
            
            # 유효성 검사
            if wallet_balance <= 0:
                logger.warning(f"유효하지 않은 지갑 잔고: {wallet_balance}")
                return float('inf')
                
            if maintenance_margin <= 0:
                logger.debug(f"유지 증거금이 0 또는 음수입니다: {maintenance_margin}")
                return float('inf')
            
            # 마진 레벨 계산
            margin_level = (wallet_balance + unrealized_pnl) / maintenance_margin
            
            logger.info(f"일반 마진 레벨: {margin_level:.4f} (지갑 잔고: {wallet_balance}, 미실현 손익: {unrealized_pnl}, 유지 증거금: {maintenance_margin})")
            return margin_level
            
        except Exception as e:
            logger.error(f"일반 마진 레벨 계산 중 오류: {e}")
            logger.error(traceback.format_exc())
            return float('inf')


class LeverageManager:
    """거래소별 레버리지 관리 유틸리티 클래스"""
    
    @staticmethod
    def adjust_leverage(exchange_api, symbol, target_leverage, max_allowed=100):
        """
        거래소 API를 통해 레버리지 조정
        
        Args:
            exchange_api: 거래소 API 인스턴스
            symbol (str): 심볼
            target_leverage (int/float): 목표 레버리지
            max_allowed (int): 허용된 최대 레버리지
            
        Returns:
            tuple: (성공 여부, 새 레버리지, 메시지)
        """
        try:
            # 입력값 검증
            try:
                target_leverage = float(target_leverage)
                if target_leverage <= 0:
                    return False, 0, "레버리지는 0보다 커야 합니다"
                
                target_leverage = int(min(target_leverage, max_allowed))
            except ValueError:
                return False, 0, f"유효하지 않은 레버리지 값: {target_leverage}"
            
            # 현재 레버리지 가져오기
            current_leverage = LeverageManager.get_current_leverage(exchange_api, symbol)
            
            if current_leverage == target_leverage:
                logger.info(f"레버리지가 이미 {target_leverage}x로 설정되어 있습니다")
                return True, current_leverage, f"레버리지가 이미 {target_leverage}x로 설정되어 있습니다"
            
            # 거래소 API를 통해 레버리지 변경
            result = exchange_api.set_leverage(symbol=symbol, leverage=target_leverage)
            
            if result:
                logger.info(f"레버리지 변경 성공: {current_leverage}x → {target_leverage}x")
                return True, target_leverage, f"레버리지 변경 성공: {current_leverage}x → {target_leverage}x"
            else:
                logger.warning(f"레버리지 변경 실패: {symbol}, 목표 레버리지: {target_leverage}x")
                return False, current_leverage, "레버리지 변경 작업이 실패했습니다"
                
        except Exception as e:
            logger.error(f"레버리지 조정 중 오류: {e}")
            logger.error(traceback.format_exc())
            return False, 0, f"레버리지 조정 오류: {str(e)}"
    
    @staticmethod
    def get_current_leverage(exchange_api, symbol):
        """
        현재 설정된 레버리지 가져오기
        
        Args:
            exchange_api: 거래소 API 인스턴스
            symbol (str): 심볼
            
        Returns:
            int: 현재 레버리지, 오류 시 0 반환
        """
        try:
            # API를 통해 현재 레버리지 정보 가져오기
            position_info = exchange_api.get_position_info(symbol)
            
            if position_info:
                # 다양한 키를 시도하여 레버리지 값 추출
                leverage = position_info.get('leverage', 
                           position_info.get('Leverage', 
                           position_info.get('leverageLevel', 1)))
                
                try:
                    leverage = int(float(leverage))
                    logger.info(f"{symbol}의 현재 레버리지: {leverage}x")
                    return leverage
                except (ValueError, TypeError):
                    logger.warning(f"유효하지 않은 레버리지 값: {leverage}")
                    return 1  # 기본값
            else:
                logger.warning(f"{symbol}의 포지션 정보를 가져올 수 없습니다")
                return 1  # 기본값
                
        except Exception as e:
            logger.error(f"현재 레버리지 조회 중 오류: {e}")
            logger.error(traceback.format_exc())
            return 1  # 기본값
    
    @staticmethod
    def calculate_safe_leverage(current_margin_level, current_leverage, min_leverage=1, max_leverage=100):
        """
        마진 레벨에 기반한 안전한 레버리지 계산
        
        Args:
            current_margin_level (float): 현재 마진 레벨
            current_leverage (int): 현재 레버리지
            min_leverage (int): 최소 레버리지
            max_leverage (int): 최대 레버리지
            
        Returns:
            int: 안전한 레버리지 값
        """
        try:
            # 마진 레벨에 따른 안전 레버리지 계산
            # 마진 레벨이 낮을수록 더 낮은 레버리지 권장
            if current_margin_level <= 1.05:  # 매우 위험
                safe_leverage = min(5, current_leverage // 2)
            elif current_margin_level <= 1.2:  # 위험
                safe_leverage = min(10, current_leverage * 3 // 4)
            elif current_margin_level <= 1.5:  # 주의
                safe_leverage = min(20, current_leverage)
            else:  # 안전
                safe_leverage = current_leverage
            
            # 최소/최대 제한 적용
            safe_leverage = max(min_leverage, min(safe_leverage, max_leverage))
            
            logger.info(f"안전 레버리지 계산: 현재 마진 레벨={current_margin_level:.2f}, 현재 레버리지={current_leverage}x, 안전 레버리지={safe_leverage}x")
            return safe_leverage
            
        except Exception as e:
            logger.error(f"안전 레버리지 계산 중 오류: {e}")
            logger.error(traceback.format_exc())
            return min(current_leverage, 5)  # 오류 시 보수적 값 반환
