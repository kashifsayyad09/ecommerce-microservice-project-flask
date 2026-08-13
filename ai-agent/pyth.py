#!/usr/bin/env python3
"""
AES-256-GCM decryptor
----------------------
Layout assumed (the most common one, used by Node's WebCrypto, PyCryptodome,
and most online AES-GCM tools):

    base64( nonce[12 bytes] + ciphertext + tag[16 bytes] )

Key = SHA-256(password)  -> gives exactly 32 bytes, valid for AES-256.

Install dependency first:
    pip install pycryptodome --break-system-packages
"""

import base64
import hashlib
import sys
from Crypto.Cipher import AES


def derive_key(password: str) -> bytes:
    """AES-256 key = SHA-256 digest of the password (32 bytes)."""
    return hashlib.sha256(password.encode("utf-8")).digest()


def decrypt_aes_gcm(b64_ciphertext: str, password: str) -> bytes:
    raw = base64.b64decode(b64_ciphertext)

    nonce = raw[:12]        # first 12 bytes = GCM nonce/IV
    tag = raw[-16:]         # last 16 bytes  = GCM auth tag
    ciphertext = raw[12:-16]  # everything in between = actual ciphertext

    key = derive_key(password)

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)  # raises if wrong key/nonce
    return plaintext


if __name__ == "__main__":
    CODE = "mRrHprtCctCR9OjLHgxV21Vrllb0/ygFHlDnO7fLYLkP3oflEel9"
    PASSWORD = "Team7777-155261"  # change this if your real password differs

    try:
        result = decrypt_aes_gcm(CODE, PASSWORD)
        print("Decrypted:", result.decode("utf-8"))
    except ValueError as e:
        print("Decryption failed — wrong key, wrong nonce, or wrong ciphertext layout.")
        print("Details:", e)
        sys.exit(1)