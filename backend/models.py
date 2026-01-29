from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, LargeBinary, Enum, Float, DECIMAL, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from decimal import Decimal
import enum

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)

class UpstoxStatus(str, enum.Enum):
    NO_SECRETS = "NO_SECRETS"
    SECRETS_SAVED = "SECRETS_SAVED"
    TOKEN_VALID = "TOKEN_VALID"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"

class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    INSTANT = "INSTANT"

class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(str, enum.Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"

class TradeStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    public_user_id = Column(String(36), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255))
    profile_pic_url = Column(Text)
    last_login = Column(DateTime(timezone=True))
    last_active = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # ✅ CRITICAL FIX: Use DECIMAL for currency - no floating point errors
    virtual_balance = Column(DECIMAL(18, 2), default=50000.00, nullable=False)
    
    # Relationships
    upstox_account = relationship("UpstoxAccount", back_populates="user", uselist=False)
    orders = relationship("Order", back_populates="user")
    trades = relationship("Trade", back_populates="user")

class UpstoxAccount(Base, TimestampMixin):
    __tablename__ = "upstox_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Encrypted fields
    api_key = Column(LargeBinary, nullable=False)
    api_secret = Column(LargeBinary, nullable=False)
    redirect_uri = Column(Text, nullable=False)
    
    access_token = Column(LargeBinary, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    
    # WebSocket feed entitlement - separate from REST token validity
    # Default 0 (unavailable) until proven otherwise via on_feed_connected()
    # 1 = Market Data Feed permission enabled and verified
    # 0 = Feed unavailable or not yet verified
    feed_entitlement = Column(Integer, default=0, nullable=False)  # Using Integer for SQLite clarity
    
    status = Column(Enum(UpstoxStatus), default=UpstoxStatus.NO_SECRETS, nullable=False)

    user = relationship("User", back_populates="upstox_account")

class Order(Base, TimestampMixin):
    """Paper trading orders - FIRST CLASS entity"""
    __tablename__ = "orders"
    
    # ✅ MEDIUM FIX: Indexes for query performance
    __table_args__ = (
        Index('idx_user_status', 'user_id', 'status'),
        Index('idx_instrument_status', 'instrument_key', 'status'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    instrument_key = Column(String(100), nullable=False)
    
    side = Column(Enum(OrderSide), nullable=False)
    order_type = Column(Enum(OrderType), nullable=False)
    limit_price = Column(DECIMAL(18, 4), nullable=True)
    
    qty = Column(Integer, nullable=False)
    filled_qty = Column(Integer, default=0, nullable=False)
    avg_fill_price = Column(DECIMAL(18, 4), nullable=True)
    
    # ✅ EXECUTION REALISM (V4.0)
    expected_price = Column(DECIMAL(18, 4), nullable=True)
    slippage = Column(DECIMAL(18, 4), nullable=True)
    
    status = Column(Enum(OrderStatus), default=OrderStatus.OPEN, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="orders")
    trades = relationship("Trade", back_populates="order", foreign_keys="Trade.order_id")
    exit_trades = relationship("Trade", back_populates="exit_order", foreign_keys="Trade.exit_order_id")
    
    __table_args__ = (
        Index('idx_user_status', 'user_id', 'status'),
        Index('idx_instrument_status', 'instrument_key', 'status'),
    )

class Trade(Base, TimestampMixin):
    """Paper trading positions - DERIVED from filled orders"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    
    instrument_key = Column(String(100), nullable=False, index=True)
    side = Column(Enum(OrderSide), nullable=False)
    
    qty = Column(Integer, nullable=False)
    entry_price = Column(DECIMAL(18, 4), nullable=False)
    
    exit_price = Column(DECIMAL(18, 4), nullable=True)
    exit_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    
    status = Column(Enum(TradeStatus), default=TradeStatus.OPEN, nullable=False)
    realized_pnl = Column(DECIMAL(18, 4), nullable=True)
    
    closed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="trades")
    order = relationship("Order", back_populates="trades", foreign_keys=[order_id])
    exit_order = relationship("Order", back_populates="exit_trades", foreign_keys=[exit_order_id])
    
    __table_args__ = (
        Index('idx_user_status', 'user_id', 'status'),
        Index('idx_instrument', 'instrument_key'),
    )
