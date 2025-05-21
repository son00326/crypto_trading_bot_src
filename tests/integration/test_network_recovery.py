#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 네트워크 복구 통합 테스트

import os
import sys
import unittest
import time
import logging
import threading
from unittest import mock
from datetime import datetime, timedelta

# 프로젝트 루트 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.exchange_api import ExchangeAPI
from src.network_recovery import NetworkRecoveryManager
from src.config import DEFAULT_EXCHANGE, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME

# 테스트용 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('network_recovery_test')

class TestNetworkRecovery(unittest.TestCase):
    """네트워크 복구 시스템 통합 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        # 테스트용 API 인스턴스 생성
        self.exchange_api = ExchangeAPI(
            exchange_id=DEFAULT_EXCHANGE,
            symbol=DEFAULT_SYMBOL,
            timeframe=DEFAULT_TIMEFRAME,
            market_type='spot'
        )
        
        # 네트워크 복구 관리자 직접 접근
        self.network_recovery = self.exchange_api.network_recovery
        
        logger.info(f"테스트 준비 완료: {DEFAULT_EXCHANGE}, {DEFAULT_SYMBOL}")
    
    def tearDown(self):
        """테스트 정리"""
        # 리소스 정리
        if hasattr(self, 'exchange_api'):
            self.exchange_api.close()
    
    def test_basic_connection(self):
        """기본 연결 테스트"""
        # 현재 시세 조회로 연결 테스트
        ticker = self.exchange_api.get_ticker()
        
        # 결과 확인
        self.assertIsNotNone(ticker, "시세 정보가 조회되어야 합니다")
        self.assertIn('last', ticker, "시세 정보에 'last' 필드가 있어야 합니다")
        logger.info(f"마지막 가격: {ticker['last']}")
    
    def test_network_recovery_initialization(self):
        """네트워크 복구 관리자 초기화 테스트"""
        # 네트워크 복구 관리자 존재 확인
        self.assertIsNotNone(self.network_recovery, "네트워크 복구 관리자가 초기화되어야 합니다")
        
        # 엔드포인트 등록 확인
        self.assertIn(DEFAULT_EXCHANGE, self.network_recovery.alternative_endpoints)
        logger.info(f"엔드포인트 등록 확인: {self.network_recovery.alternative_endpoints[DEFAULT_EXCHANGE]}")
    
    def test_connection_check(self):
        """연결 확인 테스트"""
        # 연결 상태 확인
        connection_status = self.network_recovery.check_connection(DEFAULT_EXCHANGE)
        
        # 결과 확인
        self.assertTrue(connection_status, "연결 상태가 정상이어야 합니다")
        logger.info(f"연결 상태: {connection_status}")
    
    @mock.patch('requests.get')
    def test_recovery_from_connection_error(self, mock_get):
        """연결 오류에서 복구 테스트"""
        import requests
        
        # 연결 오류 시뮬레이션 (첫 번째 요청은 실패, 두 번째 요청은 성공)
        mock_response_success = mock.Mock()
        mock_response_success.status_code = 200
        
        # 첫 요청은 연결 오류
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("연결 오류 시뮬레이션"),
            mock_response_success
        ]
        
        # 연결 확인 (실패 예상)
        with self.assertLogs(level='WARNING'):
            connection_status = self.network_recovery.check_connection(DEFAULT_EXCHANGE)
            self.assertFalse(connection_status, "연결 오류가 감지되어야 합니다")
        
        # 복구 시도
        recovery_success = self.network_recovery._attempt_recovery(DEFAULT_EXCHANGE)
        
        # 결과 확인
        self.assertTrue(recovery_success, "복구가 성공해야 합니다")
        logger.info(f"복구 결과: {recovery_success}")
    
    @mock.patch('src.network_recovery.NetworkRecoveryManager._switch_endpoint')
    def test_endpoint_switching(self, mock_switch):
        """엔드포인트 전환 테스트"""
        # 엔드포인트 전환 모의 설정
        mock_switch.return_value = True
        
        # 복구 시도 (전환이 호출되는지 확인)
        self.network_recovery._recover_from_connection_reset(DEFAULT_EXCHANGE)
        
        # 엔드포인트 전환 호출 확인
        mock_switch.assert_called_once_with(DEFAULT_EXCHANGE)
        logger.info("엔드포인트 전환 성공")
    
    def test_monitoring_thread(self):
        """모니터링 스레드 테스트"""
        # 모니터링 시작 (이미 시작되었을 수 있음)
        if not self.network_recovery.monitoring:
            self.network_recovery.start_monitoring()
        
        # 모니터링 스레드 확인
        self.assertTrue(self.network_recovery.monitoring, "모니터링이 활성화되어야 합니다")
        self.assertIsNotNone(self.network_recovery.monitor_thread, "모니터링 스레드가 생성되어야 합니다")
        self.assertTrue(self.network_recovery.monitor_thread.is_alive(), "모니터링 스레드가 실행 중이어야 합니다")
        
        logger.info("모니터링 스레드 동작 확인")
        
        # 잠시 실행 후 중지
        time.sleep(2)
        self.network_recovery.stop_monitoring()
        
        # 중지 확인
        self.assertFalse(self.network_recovery.monitoring, "모니터링이 중지되어야 합니다")
    
    def test_integration_with_api_call(self):
        """API 호출과의 통합 테스트"""
        # API 호출로 연결 확인
        ohlcv = self.exchange_api.get_ohlcv(limit=5)
        
        # 결과 확인
        self.assertIsNotNone(ohlcv, "OHLCV 데이터가 반환되어야 합니다")
        self.assertTrue(len(ohlcv) > 0, "OHLCV 데이터가 있어야 합니다")
        logger.info(f"가장 최근 가격: {ohlcv.iloc[-1]['close']}")

# 이 파일을 직접 실행할 경우
if __name__ == '__main__':
    # 테스트 시작 전 안내
    print("=" * 70)
    print("네트워크 복구 시스템 통합 테스트를 시작합니다.")
    print("=" * 70)
    
    # 테스트 실행
    unittest.main(verbosity=2)
