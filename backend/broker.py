from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .database import get_db
from .models import User, UpstoxAccount, UpstoxStatus
from .auth import get_current_user
from .config import settings
import httpx
from datetime import datetime, timedelta, timezone
import base64
import logging
from cryptography.fernet import Fernet
import hashlib

# Configure Logger
logger = logging.getLogger("api.broker")

router = APIRouter(prefix="/api/broker", tags=["broker"])

# Encryption Helper
def get_fernet():
    # Derive a 32-byte URL-safe base64 key from the app secret
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def encrypt(data: str) -> bytes:
    if not data: return b""
    f = get_fernet()
    return f.encrypt(data.encode())

def decrypt(data: bytes) -> str:
    if not data: return ""
    f = get_fernet()
    return f.decrypt(data).decode()

@router.get("/upstox/auth-url")
async def get_upstox_auth_url(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    logger.debug(f"Generating Upstox auth URL for user: {user.email}")
    stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
    result = await db.execute(stmt)
    account = result.scalars().first()
    
    if not account or not account.api_key:
        raise HTTPException(status_code=400, detail="No Upstox secrets found")
        
    api_key = decrypt(account.api_key)
    redirect_uri = account.redirect_uri
    
    auth_url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}"
    return {"auth_url": auth_url}

@router.get("/status")
async def get_broker_status(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    logger.debug(f"Checking broker status for user: {user.email}")
    
    # Check if account exists
    stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
    result = await db.execute(stmt)
    account = result.scalars().first()
    
    if not account:
        return {"status": UpstoxStatus.NO_SECRETS}
    
    # Check if token expired (if valid)
    if account.status == UpstoxStatus.TOKEN_VALID and account.token_expiry:
        # Check expiry
        if account.token_expiry.replace(tzinfo=None) < datetime.utcnow():
            logger.error(f"[auth] ❌ REST token expired for user={user.email}")
            account.status = UpstoxStatus.TOKEN_EXPIRED
            await db.commit()
            return {"status": UpstoxStatus.TOKEN_EXPIRED}
        else:
            logger.debug(f"[auth] ✅ REST token validation successful for user={user.email}")

    return {"status": account.status, "token_expiry": account.token_expiry, "feed_entitlement": account.feed_entitlement}

@router.post("/upstox/save-secrets")
async def save_secrets(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    data = await request.json()
    api_key = data.get("api_key", "").strip()
    api_secret = data.get("api_secret", "").strip()
    redirect_uri = data.get("redirect_uri", "").strip()
    access_token = data.get("access_token", "").strip() if data.get("access_token") else None # Optional manual token
    
    if not api_key or not api_secret or not redirect_uri:
        raise HTTPException(status_code=400, detail="Missing fields")
    
    # 📌 1️⃣ AUTH & TOKEN LIFECYCLE LOGS
    logger.info(f"[auth] Saving Upstox secrets for user={user.email}")
    
    encrypted_key = encrypt(api_key)
    encrypted_secret = encrypt(api_secret)
    encrypted_token = None
    token_expiry = None
    status = UpstoxStatus.SECRETS_SAVED
    is_new_token = False

    # If manual token provided, verify it immediately
    if access_token:
        logger.info(f"[auth] Manual access token provided for user={user.email} - verifying")
        is_new_token = True
        profile_url = "https://api.upstox.com/v2/user/profile"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(profile_url, headers=headers)
            if resp.status_code == 200:
                logger.info(f"[auth] ✅ REST token validation successful for user={user.email}")
                encrypted_token = encrypt(access_token)
                status = UpstoxStatus.TOKEN_VALID
                token_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
                logger.info(f"[auth] Token expiry set to {token_expiry.isoformat()}")
            else:
                logger.error(f"[auth] ❌ REST token validation failed for user={user.email}: {resp.status_code}")
                raise HTTPException(status_code=400, detail="Invalid Access Token")

    # Check if exists
    stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
    result = await db.execute(stmt)
    account = result.scalars().first()
    
    if account:
        logger.info(f"[auth] Updating existing account for user={user.email}")
        account.api_key = encrypted_key
        account.api_secret = encrypted_secret
        account.redirect_uri = redirect_uri
        account.status = status
        if encrypted_token:
            account.access_token = encrypted_token
            account.token_expiry = token_expiry
            # Reset feed entitlement on new token
            account.feed_entitlement = 0
            logger.info(f"[auth] Feed entitlement reset to UNKNOWN (0) due to new token")
    else:
        logger.info(f"[auth] Creating new account for user={user.email}")
        account = UpstoxAccount(
            user_id=user.id,
            api_key=encrypted_key,
            api_secret=encrypted_secret,
            redirect_uri=redirect_uri,
            status=status,
            access_token=encrypted_token,
            token_expiry=token_expiry,
            feed_entitlement=0  # Default to unknown
        )
        db.add(account)
        logger.info(f"[auth] Feed entitlement initialized to UNKNOWN (0)")
    
    await db.commit()
    logger.info(f"[auth] ✅ Secrets saved successfully for user={user.email}, status={status}")
    return {"status": "success", "message": "Secrets saved", "broker_status": status}

from fastapi.responses import RedirectResponse

@router.get("/upstox/callback")
async def upstox_callback(code: str, state: str = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    logger.info(f"Upstox callback triggered for user: {user.email}")
    
    stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
    result = await db.execute(stmt)
    account = result.scalars().first()
    
    if not account:
        logger.error("Callback received but no Upstox account found")
        # Redirect to account page with error?
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/account?error=no_account_setup")
        
    api_key = decrypt(account.api_key)
    api_secret = decrypt(account.api_secret)
    redirect_uri = account.redirect_uri
    
    # Exchange Code
    token_url = "https://api.upstox.com/v2/login/authorization/token"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "code": code,
        "client_id": api_key,
        "client_secret": api_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    
    async with httpx.AsyncClient() as client:
        logger.debug("Exchanging code for token with Upstox")
        resp = await client.post(token_url, data=data, headers=headers)
        
        if resp.status_code != 200:
            logger.error(f"Upstox Token Error: {resp.text}")
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/account?error=token_exchange_failed")
            
        token_data = resp.json()
        access_token = token_data.get("access_token")
        
        # Verify Token (User Profile)
        profile_url = "https://api.upstox.com/v2/user/profile"
        auth_headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        profile_resp = await client.get(profile_url, headers=auth_headers)
        
        if profile_resp.status_code != 200:
             logger.error("Token verification failed (Profile fetch error)")
             return RedirectResponse(url=f"{settings.FRONTEND_URL}/account?error=token_verification_failed")
            
        logger.info("Token verified successfully via Profile API")
        
        # Save Token
        account.access_token = encrypt(access_token)
        account.status = UpstoxStatus.TOKEN_VALID
        # Use timezone-aware datetime to prevent frontend timezone issues
        from datetime import timezone
        account.token_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
        
        await db.commit()
        
        logger.info(f"Token saved. Redirecting to Trade Page.")
        # Add timestamp to force frontend to re-check broker status
        import time
        ts = int(time.time())
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/trade?broker_connected={ts}")

@router.post("/upstox/verify-connection")
async def verify_connection(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    data = await request.json()
    code = data.get("code")
    manual_token = data.get("access_token")

    if not code and not manual_token:
        raise HTTPException(status_code=400, detail="Must provide either Auth Code or Access Token")

    logger.info(f"Verifying connection for user {user.email}")
    
    # Get Account
    stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
    result = await db.execute(stmt)
    account = result.scalars().first()
    
    if not account:
        raise HTTPException(status_code=400, detail="No API secrets found. Save secrets first.")

    api_key = decrypt(account.api_key)
    api_secret = decrypt(account.api_secret)
    redirect_uri = account.redirect_uri

    access_token = manual_token

    # If code provided, exchange it
    if code and not access_token:
        # Heuristic: If code is unusually long (> 30 chars), treat as token
        if len(code) > 30:
             logger.info("Provided 'code' seems to be an access token")
             access_token = code
        else:
            token_url = "https://api.upstox.com/v2/login/authorization/token"
            headers = {
                "accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            token_data = {
                "code": code,
                "client_id": api_key,
                "client_secret": api_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }
            
            async with httpx.AsyncClient() as client:
                logger.debug("Exchanging manual code for token")
                resp = await client.post(token_url, data=token_data, headers=headers)
                
                if resp.status_code == 200:
                    access_token = resp.json().get("access_token")
                else:
                    # RACE CONDITION CHECK: 
                    # If code exchange failed (e.g. invalid grant), check if DB already has a valid token 
                    # updated very recently (e.g. by auto-redirect flow running in background).
                    if account.status == UpstoxStatus.TOKEN_VALID and account.token_expiry:
                         # Ensure it's not expired
                         if account.token_expiry > datetime.utcnow():
                             logger.info("Code exchange failed BUT valid token exists in DB. Assuming race condition handled.")
                             return {"status": "TOKEN_VALID", "message": "Already connected"}
                    
                    logger.error(f"Code exchange failed: {resp.text}")
                    raise HTTPException(status_code=400, detail="Invalid Auth Code or Code Expired")

    if not access_token:
         raise HTTPException(status_code=400, detail="Failed to obtain access token")

    # Verify Token (Profile + Market Data Access)
    # 1. Profile Check (Basic Validity)
    profile_url = "https://api.upstox.com/v2/user/profile"
    auth_headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    async with httpx.AsyncClient() as client:
        logger.info(f"Verifying token via Profile API for user {user.email}")
        profile_resp = await client.get(profile_url, headers=auth_headers)
        
        if profile_resp.status_code != 200:
             logger.error(f"Profile verification failed: {profile_resp.status_code} {profile_resp.text}")
             raise HTTPException(status_code=400, detail="Token verification failed (Invalid Token)")

        # 2. Market Data Check (Strict Validity for Streamer)
        # The Streamer requires valid API Key association and Market Data permissions.
        # We fetch a simple LTP quote to verify this scope.
        logger.info("Verifying token via Market Quote API (LTP)")
        # Use a common instrument like Nifty 50 or just check if API accepts the token
        market_url = "https://api.upstox.com/v2/market-quote/ltp?instrument_key=NSE_INDEX|Nifty 50"
        
        # NOTE: Streamer uses x-api-key, but REST API uses Bearer. 
        # If REST API works, permissions are likely fine.
        market_resp = await client.get(market_url, headers=auth_headers)
        
        if market_resp.status_code == 403:
             logger.error(f"Market Data verification failed (403): {market_resp.text}")
             raise HTTPException(status_code=403, detail="Token valid but lacks Market Data permission (Check API Key/Scope)")
        elif market_resp.status_code == 401:
             logger.error(f"Market Data verification failed (401): {market_resp.text}")
             raise HTTPException(status_code=401, detail="Token invalid for Market Data")
        
        # We don't strictly enforce 200 here as market might be closed or instrument invalid, 
        # but 403/401 is a definite fail. 200 or 400 (Bad Request) is acceptable for Auth check.
        logger.info(f"Market Data check response: {market_resp.status_code}")
             
        # Save validated token
        account.access_token = encrypt(access_token)
        account.status = UpstoxStatus.TOKEN_VALID
        account.token_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
        await db.commit()
        
        return {"status": "TOKEN_VALID", "message": "Connection verified (Profile + Market Access)"}

@router.post("/upstox/disconnect")
async def disconnect_broker(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    logger.info(f"Disconnecting broker for user {user.email}")
    stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
    result = await db.execute(stmt)
    account = result.scalars().first()
    
    if account:
        account.access_token = None
        account.token_expiry = None
        account.status = UpstoxStatus.NO_SECRETS # Or SECRETS_SAVED if we want to keep keys
        # User requested "Clears status -> NO_SECRETS"
        # I should probably clear everything to contain "NO_SECRETS" semantics?
        # Or just clear token and set NO_SECRETS? 
        # If I keep keys but status is NO_SECRETS, UI might be confused.
        # Let's clear keys too to be true "NO_SECRETS".
        account.api_key = b""
        account.api_secret = b""
        
        await db.commit()
        logger.info("Broker disconnected and secrets cleared")
    
    return {"status": "disconnected"}
