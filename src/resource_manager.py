#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 자원 관리 모듈

import os
import sys
import time
import gc
import logging
import threading
import traceback
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Tuple

from src.logging_config import get_logger
from src.memory_monitor import get_memory_monitor
from src.config import DATA_DIR

class ResourceManager:
    """
    시스템 자원 관리 클래스
    
    데이터프레임, 메모리 캐시, 임시 파일 등의 자원을 관리하고
    주기적으로 불필요한 자원을 정리합니다.
    """
    
    def __init__(
        self, 
        cleanup_interval: int = 3600,  # 1시간마다 정리
        max_dataframe_cache_size: int = 100,
        max_memory_usage_percent: float = 70.0
    ):
        """
        ResourceManager 초기화
        
        Args:
            cleanup_interval: 자원 정리 간격 (초)
            max_dataframe_cache_size: 데이터프레임 캐시 최대 크기
            max_memory_usage_percent: 허용 최대 메모리 사용률 (%)
        """
        self.logger = get_logger('resource_manager')
        self.cleanup_interval = cleanup_interval
        self.max_dataframe_cache_size = max_dataframe_cache_size
        self.max_memory_usage_percent = max_memory_usage_percent
        
        # 데이터프레임 캐시
        self.dataframe_cache = {}
        self.dataframe_cache_access = {}
        
        # 임시 파일 디렉토리
        self.temp_dir = os.path.join(DATA_DIR, 'temp')
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 자원 정리 스레드
        self.cleanup_active = False
        self.cleanup_thread = None
        
        # 메모리 모니터 연동
        self.memory_monitor = get_memory_monitor()
        
        # 메모리 모니터에 콜백 등록
        self.memory_monitor.register_cleanup_callback(self.cleanup_resources)
        
        self.logger.info("자원 관리자 초기화 완료")
    
    def start_cleanup_scheduler(self):
        """주기적 자원 정리 스케줄러 시작"""
        if self.cleanup_active:
            self.logger.warning("이미 자원 정리 스케줄러가 실행 중입니다.")
            return
        
        self.cleanup_active = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop)
        self.cleanup_thread.daemon = True
        self.cleanup_thread.start()
        
        self.logger.info(f"자원 정리 스케줄러 시작 (간격: {self.cleanup_interval}초)")
    
    def stop_cleanup_scheduler(self):
        """자원 정리 스케줄러 중지"""
        if not self.cleanup_active:
            return
        
        self.cleanup_active = False
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=2.0)
        
        self.logger.info("자원 정리 스케줄러 중지")
    
    def _cleanup_loop(self):
        """자원 정리 메인 루프"""
        while self.cleanup_active:
            try:
                # 메모리 사용량 확인
                memory_info = self.memory_monitor.get_memory_usage_summary()
                if memory_info['current']:
                    current_usage = memory_info['current']['process_percent']
                    self.logger.debug(f"현재 메모리 사용률: {current_usage:.1f}%")
                
                # 실행 조건: 1) 일정 시간마다 2) 메모리 임계치 초과 시
                self.cleanup_resources()
                
                # 다음 실행까지 대기
                time.sleep(self.cleanup_interval)
                
            except Exception as e:
                self.logger.error(f"자원 정리 중 오류: {e}")
                self.logger.debug(traceback.format_exc())
                time.sleep(60)  # 오류 발생 시 1분 대기
    
    def cleanup_resources(self):
        """모든 자원 정리 작업 수행"""
        self.logger.info("자원 정리 작업 시작...")
        
        # 1. 데이터프레임 캐시 정리
        self._cleanup_dataframe_cache()
        
        # 2. 임시 파일 정리
        self._cleanup_temp_files()
        
        # 3. 가비지 컬렉션 실행
        gc.collect()
        
        self.logger.info("자원 정리 작업 완료")
    
    def _cleanup_dataframe_cache(self):
        """
        데이터프레임 캐시 정리
        - 오래된 접근 순으로 캐시에서 제거
        """
        if not self.dataframe_cache:
            return
        
        initial_size = len(self.dataframe_cache)
        self.logger.debug(f"데이터프레임 캐시 정리 시작 (현재 {initial_size}개)")
        
        # 캐시 크기가 최대 크기보다 클 경우
        if len(self.dataframe_cache) > self.max_dataframe_cache_size:
            # 접근 시간 기준으로 정렬
            sorted_keys = sorted(
                self.dataframe_cache_access.keys(),
                key=lambda k: self.dataframe_cache_access.get(k, 0)
            )
            
            # 오래된 항목부터 제거
            items_to_remove = len(self.dataframe_cache) - self.max_dataframe_cache_size
            for key in sorted_keys[:items_to_remove]:
                if key in self.dataframe_cache:
                    del self.dataframe_cache[key]
                if key in self.dataframe_cache_access:
                    del self.dataframe_cache_access[key]
            
            self.logger.info(f"데이터프레임 캐시 정리: {items_to_remove}개 항목 제거")
    
    def _cleanup_temp_files(self):
        """
        임시 파일 정리
        - 일정 기간(7일) 이상 지난 파일 삭제
        """
        try:
            # 현재 시간
            now = datetime.now()
            
            # 정리 기준 시간 (7일 이전)
            cleanup_threshold = now - timedelta(days=7)
            
            # 임시 디렉토리 내 파일 목록
            files_removed = 0
            
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                
                # 파일이 아니거나 접근 불가능한 경우 건너뛰기
                if not os.path.isfile(file_path):
                    continue
                
                # 파일 수정 시간 확인
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                # 오래된 파일 삭제
                if file_mtime < cleanup_threshold:
                    try:
                        os.remove(file_path)
                        files_removed += 1
                    except Exception as e:
                        self.logger.error(f"임시 파일 삭제 오류 ({file_path}): {e}")
            
            if files_removed > 0:
                self.logger.info(f"임시 파일 정리: {files_removed}개 파일 삭제")
        
        except Exception as e:
            self.logger.error(f"임시 파일 정리 중 오류: {e}")
    
    def cache_dataframe(self, key: str, df: pd.DataFrame) -> bool:
        """
        데이터프레임을 캐시에 저장
        
        Args:
            key: 캐시 키
            df: 저장할 데이터프레임
        
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 기존 항목 제거
            if key in self.dataframe_cache:
                del self.dataframe_cache[key]
            
            # 새 항목 저장
            self.dataframe_cache[key] = df.copy()
            
            # 접근 시간 갱신
            self.dataframe_cache_access[key] = time.time()
            
            # 캐시 크기 확인 및 정리
            if len(self.dataframe_cache) > self.max_dataframe_cache_size:
                self._cleanup_dataframe_cache()
            
            return True
        
        except Exception as e:
            self.logger.error(f"데이터프레임 캐시 저장 오류 ({key}): {e}")
            return False
    
    def get_cached_dataframe(self, key: str) -> Optional[pd.DataFrame]:
        """
        캐시에서 데이터프레임 조회
        
        Args:
            key: 캐시 키
        
        Returns:
            Optional[pd.DataFrame]: 캐시된 데이터프레임 또는 None
        """
        if key in self.dataframe_cache:
            # 접근 시간 갱신
            self.dataframe_cache_access[key] = time.time()
            return self.dataframe_cache[key].copy()
        
        return None
    
    def remove_from_cache(self, key: str) -> bool:
        """
        캐시에서 항목 제거
        
        Args:
            key: 캐시 키
        
        Returns:
            bool: 제거 성공 여부
        """
        if key in self.dataframe_cache:
            del self.dataframe_cache[key]
            
            if key in self.dataframe_cache_access:
                del self.dataframe_cache_access[key]
            
            return True
        
        return False
    
    def clear_cache(self) -> int:
        """
        모든 캐시 항목 제거
        
        Returns:
            int: 제거된 항목 수
        """
        cache_size = len(self.dataframe_cache)
        self.dataframe_cache.clear()
        self.dataframe_cache_access.clear()
        
        self.logger.info(f"데이터프레임 캐시 초기화: {cache_size}개 항목 제거")
        return cache_size
    
    def get_temp_filepath(self, filename: str) -> str:
        """
        임시 파일 경로 생성
        
        Args:
            filename: 파일명
        
        Returns:
            str: 임시 파일 전체 경로
        """
        return os.path.join(self.temp_dir, filename)
    
    def optimize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        데이터프레임 메모리 사용량 최적화
        
        Args:
            df: 최적화할 데이터프레임
        
        Returns:
            pd.DataFrame: 최적화된 데이터프레임
        """
        if df is None or df.empty:
            return df
        
        try:
            result = df.copy()
            
            # 데이터 타입 최적화
            for col in result.select_dtypes(include=['int']).columns:
                # 값의 범위에 따라 적절한 정수 타입 선택
                c_min = result[col].min()
                c_max = result[col].max()
                
                if c_min >= 0:
                    if c_max < 255:
                        result[col] = result[col].astype(np.uint8)
                    elif c_max < 65535:
                        result[col] = result[col].astype(np.uint16)
                    elif c_max < 4294967295:
                        result[col] = result[col].astype(np.uint32)
                else:
                    if c_min > -128 and c_max < 127:
                        result[col] = result[col].astype(np.int8)
                    elif c_min > -32768 and c_max < 32767:
                        result[col] = result[col].astype(np.int16)
                    elif c_min > -2147483648 and c_max < 2147483647:
                        result[col] = result[col].astype(np.int32)
            
            # 부동 소수점 최적화
            for col in result.select_dtypes(include=['float']).columns:
                # 정밀도가 낮아도 되는 경우 float32 사용
                result[col] = result[col].astype(np.float32)
            
            return result
        
        except Exception as e:
            self.logger.error(f"데이터프레임 최적화 중 오류: {e}")
            return df
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """
        자원 사용 통계 조회
        
        Returns:
            Dict[str, Any]: 자원 사용 통계
        """
        return {
            'dataframe_cache': {
                'count': len(self.dataframe_cache),
                'max_size': self.max_dataframe_cache_size,
                'keys': list(self.dataframe_cache.keys())
            },
            'temp_files': {
                'count': len(os.listdir(self.temp_dir)),
                'path': self.temp_dir
            },
            'memory': self.memory_monitor.get_memory_usage_summary() if self.memory_monitor else None
        }

# 전역 자원 관리자 인스턴스
resource_manager = None

def get_resource_manager():
    """
    전역 자원 관리자 인스턴스 반환
    
    Returns:
        ResourceManager: 자원 관리자 인스턴스
    """
    global resource_manager
    if resource_manager is None:
        resource_manager = ResourceManager()
    return resource_manager

# 테스트 코드
if __name__ == "__main__":
    # 간단한 테스트
    manager = ResourceManager(cleanup_interval=10)
    manager.start_cleanup_scheduler()
    
    try:
        # 데이터프레임 캐시 테스트
        print("데이터프레임 캐시 테스트...")
        
        for i in range(5):
            # 테스트 데이터프레임 생성
            df = pd.DataFrame({
                'int_column': np.random.randint(0, 1000, size=10000),
                'float_column': np.random.random(10000),
                'date_column': pd.date_range(start='2023-01-01', periods=10000)
            })
            
            # 캐시에 저장
            key = f"test_df_{i}"
            manager.cache_dataframe(key, df)
            print(f"데이터프레임 '{key}' 캐시에 저장됨")
            
            # 최적화 테스트
            optimized_df = manager.optimize_dataframe(df)
            print(f"원본 데이터프레임 메모리: {df.memory_usage().sum() / 1024:.1f} KB")
            print(f"최적화 데이터프레임 메모리: {optimized_df.memory_usage().sum() / 1024:.1f} KB")
            
            time.sleep(2)
        
        # 캐시 조회
        stats = manager.get_resource_stats()
        print(f"자원 통계:\n{stats}")
        
        # 자원 정리 수행
        print("자원 정리 실행...")
        manager.cleanup_resources()
        
        # 캐시 초기화
        print("캐시 초기화...")
        cleared = manager.clear_cache()
        print(f"{cleared}개 항목 제거됨")
        
    except KeyboardInterrupt:
        print("\n테스트 중단")
    finally:
        manager.stop_cleanup_scheduler()
        print("자원 관리자 종료")
