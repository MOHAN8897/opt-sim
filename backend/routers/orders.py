from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime

from ..database import get_db
from ..auth import get_current_user
from ..models import User, Order, Trade, OrderType, OrderSide, OrderStatus, TradeStatus
from ..execution_engine import ExecutionEngine, check_pending_orders
import logging

from ..instrument_manager import instrument_manager

logger = logging.getLogger("api.orders")

router = APIRouter(prefix="/api/orders", tags=["orders"])

# ============ REQUEST/RESPONSE MODELS ============

class CreateOrderRequest(BaseModel):
    instrument_key: str
    side: OrderSide
    order_type: OrderType
    qty: int
    limit_price: Optional[Decimal] = None
    simulated_price: Optional[Decimal] = None # For backtesting/paper trading when live data unavailable

from sqlalchemy.orm import selectinload

# ... imports ... [Assuming imports are at the top, I need to check where to insert selectinload]
# Actually I can replace the query blocks.

class OrderResponse(BaseModel):
    id: int
    instrument_key: str
    side: str
    order_type: str
    qty: int
    filled_qty: int
    avg_fill_price: Optional[Decimal]
    limit_price: Optional[Decimal]
    status: str
    created_at: datetime
    updated_at: datetime
    
    # Enhanced Fields
    trading_symbol: Optional[str] = None
    name: Optional[str] = None
    
    # ✅ V4.0 Execution Realism
    expected_price: Optional[Decimal] = None
    slippage: Optional[Decimal] = None

    class Config:
        from_attributes = True

class TradeResponse(BaseModel):
    id: int
    instrument_key: str
    side: str
    qty: int
    entry_price: Decimal
    exit_price: Optional[Decimal]
    status: str
    realized_pnl: Optional[Decimal]
    created_at: datetime
    closed_at: Optional[datetime]
    
    # Enhanced Fields
    trading_symbol: Optional[str] = None
    strike_price: Optional[float] = None
    option_type: Optional[str] = None
    expiry_date: Optional[str] = None
    name: Optional[str] = None
    
    # ✅ V4.0 Execution Realism (Available via Order)
    slippage: Optional[Decimal] = None
    expected_price: Optional[Decimal] = None

    class Config:
        from_attributes = True

# ... endpoints ...

@router.get("/active", response_model=List[OrderResponse])
async def get_active_orders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all active (OPEN or PARTIAL) orders for the user"""
    result = await db.execute(
        select(Order).filter(
            Order.user_id == user.id,
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL])
        ).order_by(Order.created_at.desc())
    )
    
    orders = result.scalars().all()
    # Enrich with details
    response = []
    for order in orders:
        resp = OrderResponse.from_orm(order)
        details = instrument_manager.get_instrument_details(order.instrument_key)
        if details:
            resp.trading_symbol = details.get("trading_symbol")
            resp.name = details.get("name")
        response.append(resp)
        
    return response


@router.get("/history", response_model=List[OrderResponse])
async def get_order_history(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get order history (all orders)"""
    result = await db.execute(
        select(Order).filter(
            Order.user_id == user.id
        ).order_by(Order.created_at.desc()).limit(limit)
    )
    
    orders = result.scalars().all()
    
    # Enrich with details
    response = []
    for order in orders:
        resp = OrderResponse.from_orm(order)
        details = instrument_manager.get_instrument_details(order.instrument_key)
        if details:
            resp.trading_symbol = details.get("trading_symbol")
            resp.name = details.get("name")
        response.append(resp)
        
    return response

# ... cancel_order ...

@router.get("/trades", response_model=List[TradeResponse])
async def get_open_trades(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all open trades (positions)"""
    # ✅ FIX: Eager load 'order' to access slippage details
    result = await db.execute(
        select(Trade).filter(
            Trade.user_id == user.id,
            Trade.status == TradeStatus.OPEN
        ).options(selectinload(Trade.order)).order_by(Trade.created_at.desc())
    )
    
    trades = result.scalars().all()
    
    # Enrich with Instrument Details
    response = []
    for trade in trades:
        resp = TradeResponse.from_orm(trade)
        
        # Populate Execution Details from Order
        if trade.order:
            resp.expected_price = trade.order.expected_price
            resp.slippage = trade.order.slippage
        
        # Fetch details from manager
        details = instrument_manager.get_instrument_details(trade.instrument_key)
        if details:
            resp.trading_symbol = details.get("trading_symbol")
            resp.strike_price = details.get("strike")
            resp.option_type = details.get("option_type")
            resp.expiry_date = details.get("expiry")
            resp.name = details.get("name")
        
        response.append(resp)
        
    return response


@router.get("/trades/history", response_model=List[TradeResponse])
async def get_trade_history(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get trade history (Closed Trades)"""
    result = await db.execute(
        select(Trade).filter(
            Trade.user_id == user.id,
            Trade.status == TradeStatus.CLOSED
        ).order_by(Trade.closed_at.desc()).limit(limit)
    )
    
    trades = result.scalars().all()
    
    # Enrich with Instrument Details
    response = []
    for trade in trades:
        resp = TradeResponse.from_orm(trade)
        
        # Fetch details from manager
        details = instrument_manager.get_instrument_details(trade.instrument_key)
        if details:
            resp.trading_symbol = details.get("trading_symbol")
            resp.strike_price = details.get("strike")
            resp.option_type = details.get("option_type")
            resp.expiry_date = details.get("expiry")
            resp.name = details.get("name")
        
        response.append(resp)
        
    return response


class ExitTradeRequest(BaseModel):
    exit_price: Optional[Decimal] = None

@router.post("/trades/{trade_id}/exit")
async def exit_trade(
    trade_id: int,
    exit_req: ExitTradeRequest, 
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Exit an open trade (create reverse order)"""
    result = await db.execute(
        select(Trade).filter(
            Trade.id == trade_id,
            Trade.user_id == user.id
        )
    )
    
    trade = result.scalars().first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade.status != TradeStatus.OPEN:
        raise HTTPException(status_code=400, detail="Trade is not open")
    
    # Create reverse order
    exit_side = OrderSide.SELL if trade.side == OrderSide.BUY else OrderSide.BUY
    
    exit_order = Order(
        user_id=user.id,
        instrument_key=trade.instrument_key,
        side=exit_side,
        order_type=OrderType.MARKET,
        qty=trade.qty,
        status=OrderStatus.OPEN
        # We don't set limit_price since it's a MARKET exit
    )
    
    db.add(exit_order)
    await db.commit()
    await db.refresh(exit_order)
    
    # Execute immediately using the standard Engine
    # The Engine handles:
    # 1. Matching against the existing Open Trade (FIFO Netting)
    # 2. Closing the Trade
    # 3. Calculating PnL
    # 4. Updating User Balance
    
    engine = ExecutionEngine(db)
    try:
        # Pass the user-provided exit price as 'simulated_price' 
        # to ensure execution happens even if market data is missing/stale.
        await engine.execute_order(exit_order, simulated_price=exit_req.exit_price)
        await db.refresh(exit_order)
        await db.refresh(user)
        # Refresh trade to see if it closed
        await db.refresh(trade)
        
        msg = "Exit Order Placed"
        if exit_order.status == OrderStatus.FILLED:
            msg = f"Trade Closed. PnL: {trade.realized_pnl if trade.realized_pnl else 0}"
            
        return {
            "success": True, 
            "exit_order_id": exit_order.id, 
            "new_balance": user.virtual_balance,
            "message": msg,
            "trade_status": trade.status
        }
    
    except Exception as e:
        logger.error(f"Error executing exit order: {e}", exc_info=True)
        # Even if execution fails, the order is created. User can try again or check orders.
        # But we should probably raise to inform frontend.
        raise HTTPException(status_code=500, detail=f"Exit Execution Failed: {str(e)}")


@router.post("", response_model=OrderResponse)
async def create_order(
    req: CreateOrderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new order.
    Handles /api/orders (no slash) directly to avoid 307 Redirects.
    """
    logger.info(f"📝 [create_order] Received order request from {user.email}: {req.dict()}")
    
    try:
        # 1. Validation
        if req.qty <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be positive")
            
        # 2. Create Order Record
        new_order = Order(
            user_id=user.id,
            instrument_key=req.instrument_key,
            side=req.side,
            order_type=req.order_type,
            qty=req.qty,
            limit_price=req.limit_price,
            status=OrderStatus.OPEN
            # simulated_price is passed to execution engine, not stored in Order DB model
        )
        
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)
        logger.info(f"✅ [create_order] Order persisted with ID: {new_order.id}")
        
        # 3. Execute Order
        engine = ExecutionEngine(db)
        await engine.execute_order(new_order, simulated_price=req.simulated_price)
        
        # 4. Refresh & Return
        await db.refresh(new_order)
        logger.info(f"🚀 [create_order] Execution complete for Order {new_order.id}. Status: {new_order.status}")
        
        return new_order

    except Exception as e:
        logger.error(f"❌ [create_order] Failed to create/execute order: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Order creation failed: {str(e)}")

@router.post("/", include_in_schema=False)
async def create_order_slash(
    req: CreateOrderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Redirect/Alias for trailing slash"""
    return await create_order(req, user, db)
