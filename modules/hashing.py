import hashlib


def sha256_hash(content):
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()
