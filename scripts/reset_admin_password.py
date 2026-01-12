import os
import sys
import hashlib
import binascii

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arcade_scanner.database.user_store import user_db, UserStore
from arcade_scanner.models.user import User

def reset_password(username="admin", new_password="admin"):
    print(f"🔧 Resetting password for '{username}'...")
    
    # Reload from disk to be sure
    # user_db.load() # user_db is a singleton, might need forcing?
    # Actually, verify if user_db is loaded.
    
    user = user_db.get_user(username)
    if not user:
        print(f"❌ User '{username}' not found. Creating it.")
        salt = os.urandom(16)
        pwd_hash = user_db.hash_password(new_password, salt)
        user = User(
            username=username,
            password_hash=binascii.hexlify(pwd_hash).decode('ascii'),
            salt=binascii.hexlify(salt).decode('ascii'),
            is_admin=True
        )
    else:
        print(f"👤 User found. Updating password.")
        salt = os.urandom(16)
        pwd_hash = user_db.hash_password(new_password, salt)
        user.password_hash = binascii.hexlify(pwd_hash).decode('ascii')
        user.salt = binascii.hexlify(salt).decode('ascii')
    
    user_db.add_user(user)
    print(f"✅ Password for '{username}' set to '{new_password}'")

if __name__ == "__main__":
    reset_password()
