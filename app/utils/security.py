import bcrypt

def hash_password(plain: str) -> str:
    # Bcrypt requires bytes
    # Limit to 72 bytes as per bcrypt specification
    byte_pwd = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(byte_pwd, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        byte_pwd = plain.encode("utf-8")[:72]
        byte_hashed = hashed.encode("utf-8")
        return bcrypt.checkpw(byte_pwd, byte_hashed)
    except Exception:
        return False