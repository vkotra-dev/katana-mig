from __future__ import annotations

import bcrypt


def hash_password(plain_text: str) -> str:
    hashed = bcrypt.hashpw(plain_text.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_text: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_text.encode("utf-8"), password_hash.encode("utf-8"))
