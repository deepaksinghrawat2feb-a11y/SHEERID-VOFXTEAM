"""
Database models and operations for the bot
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional

from config import Config

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    verification_count = Column(Integer, default=0)
    total_verifications = Column(Integer, default=0)
    successful_verifications = Column(Integer, default=0)
    
class Verification(Base):
    __tablename__ = "verifications"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    veteran_name = Column(String(200))
    veteran_data = Column(JSON)  # Store veteran data as JSON
    status = Column(String(50), default="pending")  # pending, processing, success, failed
    verification_id = Column(String(100))
    access_token = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    
class BotLog(Base):
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True)
    level = Column(String(20))  # INFO, WARNING, ERROR
    message = Column(Text)
    user_id = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
class BotSettings(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Database:
    def __init__(self):
        self.engine = create_engine(Config.DATABASE_URL)
        Base.metadata.create_all(self.engine)
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        
    def get_session(self):
        return self.Session()
        
    def get_or_create_user(self, user_id, username=None, first_name=None, last_name=None):
        session = self.get_session()
        try:
            user = session.query(User).filter(User.user_id == user_id).first()
            if not user:
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_admin=(user_id in Config.ADMIN_IDS),
                    last_active=datetime.utcnow()
                )
                session.add(user)
                session.commit()
            else:
                # Update last active
                user.last_active = datetime.utcnow()
                user.username = username or user.username
                user.first_name = first_name or user.first_name
                user.last_name = last_name or user.last_name
                session.commit()
            return user
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
            
    def create_verification(self, user_id, veteran_name, veteran_data, status="pending"):
        session = self.get_session()
        try:
            verification = Verification(
                user_id=user_id,
                veteran_name=veteran_name,
                veteran_data=veteran_data,
                status=status
            )
            session.add(verification)
            session.commit()
            return verification
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
            
    def update_verification_status(self, verification_id, status, verification_id_value=None, error_message=None):
        session = self.get_session()
        try:
            verification = session.query(Verification).get(verification_id)
            if verification:
                verification.status = status
                if verification_id_value:
                    verification.verification_id = verification_id_value
                if error_message:
                    verification.error_message = error_message
                if status in ["success", "failed"]:
                    verification.completed_at = datetime.utcnow()
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
            
    def get_verification(self, verification_id):
        session = self.get_session()
        try:
            return session.query(Verification).get(verification_id)
        finally:
            session.close()
            
    def get_user_verifications(self, user_id, limit=10):
        session = self.get_session()
        try:
            return session.query(Verification)\
                .filter(Verification.user_id == user_id)\
                .order_by(Verification.created_at.desc())\
                .limit(limit)\
                .all()
        finally:
            session.close()
            
    def get_verifications_count_today(self, user_id):
        session = self.get_session()
        try:
            today = datetime.utcnow().date()
            return session.query(Verification)\
                .filter(
                    Verification.user_id == user_id,
                    Verification.created_at >= datetime(today.year, today.month, today.day)
                )\
                .count()
        finally:
            session.close()
            
    def get_bot_statistics(self):
        session = self.get_session()
        try:
            today = datetime.utcnow().date()
            
            stats = {
                'total_users': session.query(User).count(),
                'active_users': session.query(User).filter(User.is_active == True).count(),
                'total_verifications': session.query(Verification).count(),
                'success_count': session.query(Verification).filter(Verification.status == 'success').count(),
                'failed_count': session.query(Verification).filter(Verification.status == 'failed').count(),
                'pending_count': session.query(Verification).filter(Verification.status == 'pending').count(),
                'today_count': session.query(Verification)\
                    .filter(Verification.created_at >= datetime(today.year, today.month, today.day))\
                    .count(),
                'uptime': 'N/A'  # Can be calculated from bot start time
            }
            return stats
        finally:
            session.close()
            
    def get_all_active_users(self):
        session = self.get_session()
        try:
            return session.query(User)\
                .filter(User.is_active == True)\
                .all()
        finally:
            session.close()
            
    def add_log(self, level, message, user_id=None):
        session = self.get_session()
        try:
            log = BotLog(
                level=level,
                message=message,
                user_id=user_id
            )
            session.add(log)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Failed to add log: {e}")
        finally:
            session.close()
            
    def get_settings(self, key, default=None):
        session = self.get_session()
        try:
            setting = session.query(BotSettings).filter(BotSettings.key == key).first()
            return setting.value if setting else default
        finally:
            session.close()
            
    def set_settings(self, key, value):
        session = self.get_session()
        try:
            setting = session.query(BotSettings).filter(BotSettings.key == key).first()
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = BotSettings(key=key, value=value)
                session.add(setting)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
