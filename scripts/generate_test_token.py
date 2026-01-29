"""
Generate a fresh JWT token for testing
"""

from datetime import datetime, timedelta
from jose import jwt
import json

SECRET_KEY = "dev-secret-key-change-in-prod"  # From .env
ALGORITHM = "HS256"
EMAIL = "mohansaiteja.99@gmail.com"

def create_test_token(email: str, expires_in_minutes: int = 60):
    """Create a test JWT token"""
    expire = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
    to_encode = {
        "sub": email,
        "name": "Test User",
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

if __name__ == "__main__":
    # Generate token valid for 60 minutes
    token = create_test_token(EMAIL, 60)
    print("Fresh JWT Token (valid for 60 minutes):")
    print(token)
    print()
    
    # Save to file
    with open('fresh_token.txt', 'w') as f:
        f.write(token)
    print("✅ Saved to fresh_token.txt")
    
    # Decode to show payload
    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    print("\nToken Payload:")
    print(json.dumps(decoded, indent=2, default=str))
