from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ..database import get_db
from ..models import User, Trade
from ..auth import get_current_user
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/api/trade", tags=["trade"])
logger = logging.getLogger("api.trade")

class PlaceOrderRequest(BaseModel):
    instrument_key: str
    instrument_name: str
    symbol: str # NIFTY, etc.
    strike_price: float
    option_type: str # CE/PE
    trade_type: str # BUY/SELL
    quantity: int
    expiry_date: str # Optional
    price: float # Entry Price (LTP)

class ClosePositionRequest(BaseModel):
    trade_id: int
    exit_price: float

@router.post("/place")
async def place_order(
    request: PlaceOrderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Placing order for {user.email}: {request.instrument_name}")
    
    # Calculate required margin if simplified? 
    # For now, just check balance for BUY
    cost = request.price * request.quantity
    if request.trade_type == "BUY":
        if user.virtual_balance < cost:
            raise HTTPException(status_code=400, detail="Insufficient Balance")
        
        user.virtual_balance -= cost

    # Create Trade
    new_trade = Trade(
        user_id=user.id,
        symbol=request.symbol,
        instrument_name=request.instrument_name,
        instrument_key=request.instrument_key,
        trade_type=request.trade_type,
        option_type=request.option_type,
        strike_price=request.strike_price,
        expiry_date=request.expiry_date,
        entry_price=request.price,
        quantity=request.quantity,
        status="OPEN"
    )
    
    db.add(new_trade)
    await db.commit()
    await db.refresh(new_trade)
    
    return {"status": "success", "message": "Order Placed", "trade": new_trade, "new_balance": user.virtual_balance}

@router.get("/positions")
async def get_positions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Trade).filter(Trade.user_id == user.id, Trade.status == "OPEN")
    result = await db.execute(stmt)
    trades = result.scalars().all()
    return {"trades": trades}

@router.post("/close")
async def close_position(
    request: ClosePositionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Trade).filter(Trade.id == request.trade_id, Trade.user_id == user.id)
    result = await db.execute(stmt)
    trade = result.scalars().first()
    
    if not trade or trade.status != "OPEN":
        raise HTTPException(status_code=400, detail="Invalid Trade or already closed")
        
    logger.info(f"Closing trade {trade.id} at {request.exit_price}")
    
    trade.exit_price = request.exit_price
    trade.status = "CLOSED"
    
    # P&L Calculation
    # BUY: (Exit - Entry) * Qty
    # SELL: (Entry - Exit) * Qty
    if trade.trade_type == "BUY":
        pnl = (request.exit_price - trade.entry_price) * trade.quantity
        # Credit back principal + pnl
        # Principal was deducted on entry.
        # So credit: (Entry * Qty) + PnL = Exit * Qty
        credit = request.exit_price * trade.quantity
        user.virtual_balance += credit
    else:
        # SELL (Shorting)
        # Assuming margin was blocked? simplified:
        # PnL = (Entry - Exit) * Qty
        pnl = (trade.entry_price - request.exit_price) * trade.quantity
        # If margin blocked, release it +/- PnL
        # For simple simulator, if we didn't block margin for sell (risky), we just add PnL?
        # Let's assume simplified: Just credit PnL? 
        # Or better: (Entry * Qty) + PnL? 
        # Wait, if I sold at 100, I got 100 * Qty cash (theoretically). 
        # But usually in simulators we block margin.
        # Let's treat SELL as: PnL is added/subtracted to balance.
        user.virtual_balance += pnl

    trade.pnl = pnl
    await db.commit()
    
    return {"status": "success", "message": "Position Closed", "pnl": pnl, "new_balance": user.virtual_balance}
