import hashlib
import secrets
import datetime
from sqlalchemy.orm import Session
from database.models import User, UserSession

# 100,000 iterations is recommended for PBKDF2 HMAC-SHA256
ITERATIONS = 100000

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """
    Hash a password using PBKDF2 HMAC-SHA256.
    Returns (password_hash_hex, salt_hex).
    """
    if salt is None:
        # Generate a random 16-byte salt as a hex string
        salt_bytes = secrets.token_bytes(16)
        salt = salt_bytes.hex()
    else:
        salt_bytes = bytes.fromhex(salt)
        
    pwd_bytes = password.encode('utf-8')
    
    # Hash
    dk = hashlib.pbkdf2_hmac('sha256', pwd_bytes, salt_bytes, ITERATIONS)
    password_hash = dk.hex()
    
    return password_hash, salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """
    Verify if the password matches the hash.
    """
    check_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(check_hash, password_hash)

def generate_token() -> str:
    """
    Generate a cryptographically secure session token.
    """
    return secrets.token_hex(32)

def create_session(db: Session, user_id: int) -> str:
    """
    Create a new user session in the database.
    Expires in 7 days.
    """
    token = generate_token()
    expires_at = datetime.datetime.now() + datetime.timedelta(days=7)
    
    session = UserSession(
        token=token,
        user_id=user_id,
        expires_at=expires_at
    )
    db.add(session)
    db.commit()
    return token

def verify_session(db: Session, token: str) -> User:
    """
    Verify if the session token is valid and not expired.
    Returns the User if valid, else None.
    """
    if not token:
        return None
        
    session = db.query(UserSession).filter(UserSession.token == token).first()
    if not session:
        return None
        
    # Check expiration
    if session.expires_at < datetime.datetime.now():
        db.delete(session)
        db.commit()
        return None
        
    # Get user
    user = db.query(User).filter(User.id == session.user_id).first()
    return user

def delete_session(db: Session, token: str) -> bool:
    """
    Delete the session token (logout).
    """
    if not token:
        return False
    session = db.query(UserSession).filter(UserSession.token == token).first()
    if session:
        db.delete(session)
        db.commit()
        return True
    return False
