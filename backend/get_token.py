import pymysql
import os
import sys
import hashlib
import base64
from cryptography.fernet import Fernet
import json

# DB Config
DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = "Sai@1234"
DB_NAME = "paper_trading"

# Secret
SECRET_KEY = "dev-secret-key-change-in-prod"

def get_fernet():
    key = hashlib.sha256(SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def decrypt(encrypted_data: bytes) -> str:
    if not encrypted_data: return ""
    f = get_fernet()
    return f.decrypt(encrypted_data).decode()

def get_token():
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
        cursor = conn.cursor()
        
        # Select
        cursor.execute("SELECT access_token FROM upstox_accounts WHERE status = 'TOKEN_VALID' LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            token_encrypted = row[0]
            # PyMySQL might return bytes or string depending on column type. 
            # If BLOB/LargeBinary, it's bytes.
            if isinstance(token_encrypted, str):
                # If it came as string (maybe latin1), encode? 
                # Ideally it should be bytes.
                pass
                
            token = decrypt(token_encrypted)
            print(token)
        else:
            print("NO_TOKEN")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_token()
