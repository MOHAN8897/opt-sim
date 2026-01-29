# Context: This module handles all Authentication logic including:
# 1. Google OAuth2 Flow (Login -> Redirect -> Callback)
# 2. JWT Token Generation (creating secure access tokens)
# 3. Session Management (Inactivity timeouts, user validation)
from fastapi import APIRouter, Request, Response, Depends, HTTPException, status
from authlib.integrations.starlette_client import OAuth
from jose import jwt
from datetime import datetime, timedelta
from .config import settings
from pydantic import BaseModel
import httpx
import logging
import redis

# Context: Configure logger for auth module
logger = logging.getLogger("api.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Initialize Redis connection for session state persistence
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=1,  # Use different db for OAuth state
    decode_responses=True,
    socket_connect_timeout=5
)

oauth = OAuth()

# Custom configuration for OAuth with Redis state storage
class RedisSessionBackend:
    def __init__(self, redis_client):
        self.redis_client = redis_client
    
    def put(self, name, value, ttl=600):
        """Store session state in Redis"""
        self.redis_client.setex(f"oauth_state:{name}", ttl, value)
    
    def get(self, name):
        """Retrieve session state from Redis"""
        return self.redis_client.get(f"oauth_state:{name}")
    
    def delete(self, name):
        """Delete session state from Redis"""
        self.redis_client.delete(f"oauth_state:{name}")

# Set up session for OAuth
oauth._backend = RedisSessionBackend(redis_client)

oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)
logger.info("OAuth client registered for Google with Redis state storage")

def create_access_token(data: dict):
    logger.debug(f"Creating access token for: {data.get('sub', 'unknown')}")
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    logger.info(f"Access token created for {data.get('sub', 'unknown')}, expires at {expire.isoformat()}")
    return encoded_jwt



@router.get("/login")
async def login(request: Request):
    # Context: Initiates the Google OAuth flow. Redirects user to Google's consent screen.
    # Force account selection every time to allow users to choose different accounts
    logger.info(f"Login request received from {request.client.host}")
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    logger.debug(f"OAuth redirect URI configured as: {redirect_uri}")
    
    try:
        # Add prompt=select_account to force account selection
        logger.info("Attempting to generate Google OAuth redirect URL...")
        response = await oauth.google.authorize_redirect(
            request, 
            redirect_uri,
            prompt="select_account"  # Forces Google to show account picker
        )
        logger.info("Google OAuth redirect generated successfully. Redirecting user.")
        return response
    except Exception as e:
        logger.error(f"Failed to generate OAuth redirect: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OAuth Handshake Failed: {str(e)}")

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .database import get_db
from .models import User

# Session timeout: 20 minutes
SESSION_TIMEOUT_MINUTES = 20

def get_current_user_token(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.JWTError:
        return None



@router.get("/google/callback")
async def auth_callback(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    logger.info("OAuth callback received from Google")
    try:
        token = await oauth.google.authorize_access_token(request, leeway=60)
        user_info = token.get('userinfo')
        
        if not user_info:
            logger.error("Failed to get user info from Google OAuth")
            raise HTTPException(status_code=400, detail="Failed to get user info")
        
        # Check if user exists
        email = user_info['email']
        logger.info(f"Processing OAuth callback for user: {email}")
        logger.debug(f"User info from Google: name={user_info.get('name')}, email={email}")
        
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()
        
        # Google provides 'picture' field
        profile_pic = user_info.get('picture')

        now = datetime.utcnow()

        if not user:
            logger.info(f"Creating new user: {email}")
            import uuid
            user = User(
                email=email, 
                name=user_info['name'],
                public_user_id=str(uuid.uuid4()),
                profile_pic_url=profile_pic,
                last_active=now
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"New user created with ID: {user.public_user_id}")
        else:
            logger.info(f"Existing user login: {email} (ID: {user.public_user_id})")
            # Update fields
            user.last_login = now
            user.last_active = now
            if profile_pic:
                user.profile_pic_url = profile_pic
            await db.commit()
            await db.refresh(user)
        
        # Create session token
        # Store minimal info in JWT, rely on DB for rest
        access_token = create_access_token(data={"sub": user.email, "name": user.name})
        
        # Set cookie (Redirect to frontend)
        logger.info(f"Setting cookie and redirecting user {email} to trade page")
        response = Response(status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False, # Dev only
            samesite="lax",
            path="/",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        response.headers["Location"] = f"{settings.FRONTEND_URL}/auth/callback"
        return response
    except Exception as e:
        logger.error(f"Error in OAuth callback: {str(e)}", exc_info=True)
        raise

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token:
        # Check Authorization header (Bearer token)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        logger.warning(f"Auth check failed: No access_token cookie or Bearer header found. Cookies: {list(request.cookies.keys())}")
        raise HTTPException(status_code=401, detail="Not authenticated - No token")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        
        if not email:
            logger.warning(f"Auth check failed: Token missing 'sub' field. Payload keys: {list(payload.keys())}")
            raise HTTPException(status_code=401, detail="Invalid token - Missing email")
        
        # Fetch user
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()
        
        if not user:
            logger.warning(f"Auth check failed: User not found in database for email: {email}")
            raise HTTPException(status_code=401, detail="User not found")
             
        now = datetime.utcnow()
        if user.last_active:
            # Check inactivity (20 mins)
            last_active = user.last_active
            if last_active.tzinfo:
                last_active = last_active.replace(tzinfo=None)
            
            time_diff = (now - last_active).total_seconds()
            logger.debug(f"Session check for {email}: now={now.isoformat()}, last_active={last_active.isoformat()}, diff={time_diff:.1f}s")
            
            if time_diff > (SESSION_TIMEOUT_MINUTES * 60):
                logger.warning(f"Auth check failed: Session expired for {email}. Inactive for {time_diff:.0f}s (limit: {SESSION_TIMEOUT_MINUTES*60}s)")
                raise HTTPException(status_code=401, detail=f"Session expired due to inactivity ({int(time_diff/60)} minutes)")
            
            # Debounce updates: Only update if > 60 seconds elapsed
            if time_diff > 60 or time_diff < -60: # Handle slight clock drifts
                user.last_active = now
                await db.commit()
                logger.debug(f"Updated last_active for {email}")
        else:
            # First time setting it if missing
            user.last_active = now
            await db.commit()
            logger.debug(f"Set initial last_active for {email}")
        
        logger.debug(f"Auth check successful for {email}")
        return user
        
    except jwt.ExpiredSignatureError:
        logger.warning(f"Auth check failed: JWT token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError as e:
        logger.warning(f"Auth check failed: JWT decode error - {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token - {type(e).__name__}")

@router.get("/me")
async def read_users_me(user: User = Depends(get_current_user), request: Request = None):
    # Get session expiry from token for display (optional, can just use fixed time)
    # We'll re-decode token just to get 'exp' if needed, or just return user data
    token = request.cookies.get("access_token") if request else None
    session_expires_at = None
    if token:
         try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            exp_timestamp = payload.get('exp')
            session_expires_at = datetime.utcfromtimestamp(exp_timestamp).isoformat() + 'Z' if exp_timestamp else None
         except:
            pass

    return {
        "user": {
            "public_user_id": user.public_user_id,
            "email": user.email,
            "name": user.name,
            "profile_pic": user.profile_pic_url,
            "virtual_balance": user.virtual_balance
        },
        "session_expires_at": session_expires_at
    }

@router.post("/logout")
async def logout(response: Response):
    logger.info("Logout requested - deleting access token cookie")
    response.delete_cookie("access_token")
    return {"success": True}

@router.get("/token")
async def get_token(user: User = Depends(get_current_user), request: Request = None):
    """Expose access token for WebSocket authentication"""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="No token found")
    return {"access_token": token}
