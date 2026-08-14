import bcrypt


def hash_password(password: str) -> str:
    # Convert password to bytes
    password_bytes = password.encode("utf-8")

    # bcrypt maximum is 72 bytes
    password_bytes = password_bytes[:72]

    # Generate salt and hash
    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    )

    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    password_bytes = password.encode("utf-8")

    # Same 72-byte limit
    password_bytes = password_bytes[:72]

    return bcrypt.checkpw(
        password_bytes,
        hashed_password.encode("utf-8")
    )