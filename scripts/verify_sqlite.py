import sys
import os

# Create dummy config context if needed, but easier to just import existing
sys.path.append(os.getcwd())

from arcade_scanner.database.user_store import UserStore, user_db
from arcade_scanner.models.user import User

def verify_sqlite():
    print("🧪 Verifying SQLite UserStore...")
    
    # Check DB file existence
    db_path = user_db.db_path
    if not os.path.exists(db_path):
        print(f"❌ Database file {db_path} not found!")
        return
    print(f"✅ Database file found: {db_path}")
    
    # Check Admin
    admin = user_db.get_user("admin")
    if not admin:
        print("❌ Admin user not found!")
        return
    print(f"✅ Admin user found. Is Admin: {admin.is_admin}")
    
    # Test Create/Read
    test_user = User(
        username="test_sqlite_user",
        password_hash="dummy",
        salt="dummy"
    )
    test_user.data.favorites = ["/path/to/fav"]
    
    print("Adding test user...")
    user_db.add_user(test_user)
    
    retrieved = user_db.get_user("test_sqlite_user")
    if not retrieved:
        print("❌ Failed to retrieve test user!")
        return
        
    if retrieved.data.favorites != ["/path/to/fav"]:
        print(f"❌ Data mismatch! Got: {retrieved.data.favorites}")
        return
        
    print("✅ Test user stored and retrieved successfully.")
    print("🎉 SQLite migration verification passed!")

if __name__ == "__main__":
    verify_sqlite()
