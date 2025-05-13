#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 사용자 모델
from flask_login import UserMixin

class User(UserMixin):
    """사용자 인증을 위한 모델 클래스"""
    
    def __init__(self, id, username, password_hash, email=None, is_admin=False):
        """
        사용자 모델 초기화
        
        Args:
            id (int): 사용자 ID
            username (str): 사용자명
            password_hash (str): 암호화된 비밀번호
            email (str, optional): 이메일 주소
            is_admin (bool, optional): 관리자 여부
        """
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.is_admin = is_admin
