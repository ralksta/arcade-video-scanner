import hashlib
import binascii

def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)

stored_hash_hex = "eea2f4b07a0d4a153487c2d7798aecf19c50369508f8f6efca6527066ad7008c"
stored_salt_hex = "5b2c6f2a036ccd2cbb42552ebc267bc2"
password_attempt = "admin"

print(f"Stored Hash (Hex): {stored_hash_hex}")
print(f"Stored Salt (Hex): {stored_salt_hex}")
print(f"Password Attempt:  {password_attempt}")

try:
    salt_bytes = binascii.unhexlify(stored_salt_hex)
    print(f"Salt Bytes: {salt_bytes}")
    
    new_hash_bytes = hash_password(password_attempt, salt_bytes)
    new_hash_hex = binascii.hexlify(new_hash_bytes).decode('ascii')
    
    print(f"Calc Hash (Hex):   {new_hash_hex}")
    
    if new_hash_hex == stored_hash_hex:
        print("✅ MATCH")
    else:
        print("❌ MISMATCH")

except Exception as e:
    print(f"Error: {e}")
