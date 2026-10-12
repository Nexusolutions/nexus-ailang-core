"""Stdlib `crypto` — API de criptografía (T2 — FASE 35).

FASE 35 del prompt maestro. Usa `cryptography` library (auditada, no inventada).

Operaciones:
  hash        — SHA-256, SHA-512, SHA-3, BLAKE2
  hmac        — HMAC-SHA256
  random      — bytes aleatorios criptográficamente seguros
  sign        — Ed25519 sign/verify
  keygen      — generar claves Ed25519
  kdf         — key derivation (HKDF, PBKDF2)
  cipher      — AES-256-GCM encrypt/decrypt (simétrico)
  secure_store — almacenamiento seguro con Fernet

Capabilities requeridas:
  Todas las operaciones requieren `crypto.use` capability.

Política:
  No inventar algoritmos. Usar implementaciones auditadas de `cryptography`.
  Separar: Language API → Provider → Backend (cryptography lib).
"""
from __future__ import annotations

import hashlib
import hmac as _hmac
import os
import secrets
from typing import Any, Dict, Optional, Tuple

from ailang.runtime.capabilities import require


def _require_crypto():
    """Importa cryptography de forma perezosa, con error claro si no está."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.fernet import Fernet
        return {
            "hashes": hashes,
            "serialization": serialization,
            "ed25519": ed25519,
            "hkdf": HKDF,
            "pbkdf2": PBKDF2HMAC,
            "aesgcm": AESGCM,
            "fernet": Fernet,
        }
    except ImportError as e:
        raise RuntimeError(
            f"cryptography no instalado. Instala con: pip install cryptography. Causa: {e}"
        )


# --- Hash ---

def sha256(data) -> str:
    """SHA-256 hash. Retorna hex string. Requiere `crypto.use`."""
    require("crypto.use", op_desc="crypto.sha256()")
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha512(data) -> str:
    """SHA-512 hash. Retorna hex string."""
    require("crypto.use", op_desc="crypto.sha512()")
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha512(data).hexdigest()


def blake2b(data, digest_size=32) -> str:
    """BLAKE2b hash. Retorna hex string."""
    require("crypto.use", op_desc="crypto.blake2b()")
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.blake2b(data, digest_size=int(digest_size)).hexdigest()


# --- HMAC ---

def hmac_sha256(key, data) -> str:
    """HMAC-SHA256. Retorna hex string."""
    require("crypto.use", op_desc="crypto.hmac_sha256()")
    if isinstance(key, str):
        key = key.encode("utf-8")
    if isinstance(data, str):
        data = data.encode("utf-8")
    return _hmac.new(key, data, hashlib.sha256).hexdigest()


# --- Random ---

def random_bytes(n=32) -> bytes:
    """Bytes aleatorios criptográficamente seguros."""
    require("crypto.use", op_desc="crypto.random_bytes()")
    return secrets.token_bytes(int(n))


def random_hex(n=32) -> str:
    """Hex string aleatorio criptográficamente seguro."""
    require("crypto.use", op_desc="crypto.random_hex()")
    return secrets.token_hex(int(n))


def random_token(n=32) -> str:
    """Token URL-safe aleatorio."""
    require("crypto.use", op_desc="crypto.random_token()")
    return secrets.token_urlsafe(int(n))


# --- Ed25519 Sign/Verify ---

def generate_keypair() -> Dict[str, str]:
    """Genera par de claves Ed25519. Retorna {private: hex, public: hex}."""
    require("crypto.use", op_desc="crypto.generate_keypair()")
    crypto = _require_crypto()
    priv = crypto["ed25519"].Ed25519PrivateKey.generate()
    pub = priv.public_key()
    priv_bytes = priv.private_bytes(
        encoding=crypto["serialization"].Encoding.Raw,
        format=crypto["serialization"].PrivateFormat.Raw,
        encryption_algorithm=crypto["serialization"].NoEncryption(),
    )
    pub_bytes = pub.public_bytes(
        encoding=crypto["serialization"].Encoding.Raw,
        format=crypto["serialization"].PublicFormat.Raw,
    )
    return {
        "private": priv_bytes.hex(),
        "public": pub_bytes.hex(),
    }


def sign(private_key_hex, data) -> str:
    """Firma datos con clave privada Ed25519. Retorna signature hex."""
    require("crypto.use", op_desc="crypto.sign()")
    crypto = _require_crypto()
    priv_bytes = bytes.fromhex(str(private_key_hex))
    priv = crypto["ed25519"].Ed25519PrivateKey.from_private_bytes(priv_bytes)
    if isinstance(data, str):
        data = data.encode("utf-8")
    signature = priv.sign(data)
    return signature.hex()


def verify(public_key_hex, signature_hex, data) -> bool:
    """Verifica firma Ed25519. Retorna True si es válida, False si no."""
    require("crypto.use", op_desc="crypto.verify()")
    crypto = _require_crypto()
    from cryptography.exceptions import InvalidSignature
    pub_bytes = bytes.fromhex(str(public_key_hex))
    sig_bytes = bytes.fromhex(str(signature_hex))
    pub = crypto["ed25519"].Ed25519PublicKey.from_public_bytes(pub_bytes)
    if isinstance(data, str):
        data = data.encode("utf-8")
    try:
        pub.verify(sig_bytes, data)
        return True
    except InvalidSignature:
        return False


# --- Key Derivation ---

def hkdf(secret, salt=None, info=b"", length=32) -> str:
    """HKDF-SHA256 key derivation. Retorna hex string."""
    require("crypto.use", op_desc="crypto.hkdf()")
    crypto = _require_crypto()
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    if isinstance(salt, str):
        salt = salt.encode("utf-8")
    if isinstance(info, str):
        info = info.encode("utf-8")
    hkdf = crypto["hkdf"](
        algorithm=crypto["hashes"].SHA256(),
        length=int(length),
        salt=salt,
        info=info,
    )
    derived = hkdf.derive(secret)
    return derived.hex()


def pbkdf2(password, salt, iterations=100000, length=32) -> str:
    """PBKDF2-HMAC-SHA256 key derivation. Retorna hex string."""
    require("crypto.use", op_desc="crypto.pbkdf2()")
    crypto = _require_crypto()
    if isinstance(password, str):
        password = password.encode("utf-8")
    if isinstance(salt, str):
        salt = salt.encode("utf-8")
    kdf = crypto["pbkdf2"](
        algorithm=crypto["hashes"].SHA256(),
        length=int(length),
        salt=salt,
        iterations=int(iterations),
    )
    derived = kdf.derive(password)
    return derived.hex()


# --- Symmetric Encryption (AES-256-GCM) ---

def aes_encrypt(key_hex, plaintext, aad=None) -> Dict[str, str]:
    """AES-256-GCM encrypt. Requiere key de 32 bytes (64 hex).

    Retorna {nonce: hex, ciphertext: hex} (nonce es aleatorio por encrypt).
    """
    require("crypto.use", op_desc="crypto.aes_encrypt()")
    crypto = _require_crypto()
    key = bytes.fromhex(str(key_hex))
    # AUD-073: wrap ValueError in AILangRuntimeError
    if len(key) != 32:
        from ailang.lang.errors import AILangValueError
        raise AILangValueError(
            "AES-256 requiere key de 32 bytes (64 hex chars)"
        )
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")
    if isinstance(aad, str):
        aad = aad.encode("utf-8")
    aesgcm = crypto["aesgcm"](key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext, aad)
    return {"nonce": nonce.hex(), "ciphertext": ct.hex()}


def aes_decrypt(key_hex, nonce_hex, ciphertext_hex, aad=None) -> bytes:
    """AES-256-GCM decrypt. Retorna plaintext bytes."""
    require("crypto.use", op_desc="crypto.aes_decrypt()")
    crypto = _require_crypto()
    # AUD-074: wrap cryptography.exceptions.InvalidTag in AILangRuntimeError
    try:
        key = bytes.fromhex(str(key_hex))
        nonce = bytes.fromhex(str(nonce_hex))
        ct = bytes.fromhex(str(ciphertext_hex))
        if isinstance(aad, str):
            aad = aad.encode("utf-8")
        aesgcm = crypto["aesgcm"](key)
        return aesgcm.decrypt(nonce, ct, aad)
    except Exception as e:
        # InvalidTag, ValueError, etc. — wrap in AILangRuntimeError
        from ailang.lang.errors import AILangRuntimeError
        if isinstance(e, AILangRuntimeError):
            raise
        raise AILangRuntimeError(f"crypto.aes_decrypt failed: {e}", code="E073")


# --- Secure Storage (Fernet) ---

def generate_fernet_key() -> str:
    """Genera clave Fernet (URL-safe base64)."""
    require("crypto.use", op_desc="crypto.generate_fernet_key()")
    crypto = _require_crypto()
    return crypto["fernet"].generate_key().decode("ascii")


def fernet_encrypt(key, data) -> str:
    """Encripta con Fernet (AES-128-CBC + HMAC-SHA256). Retorna token string."""
    require("crypto.use", op_desc="crypto.fernet_encrypt()")
    crypto = _require_crypto()
    if isinstance(key, str):
        key = key.encode("ascii")
    if isinstance(data, str):
        data = data.encode("utf-8")
    f = crypto["fernet"](key)
    return f.encrypt(data).decode("ascii")


def fernet_decrypt(key, token) -> bytes:
    """Desencripta token Fernet. Retorna plaintext bytes."""
    require("crypto.use", op_desc="crypto.fernet_decrypt()")
    crypto = _require_crypto()
    if isinstance(key, str):
        key = key.encode("ascii")
    if isinstance(token, str):
        token = token.encode("ascii")
    f = crypto["fernet"](key)
    return f.decrypt(token)


# --- Module exports ---

_exports = {
    "sha256": sha256, "sha512": sha512, "blake2b": blake2b,
    "hmac_sha256": hmac_sha256,
    "random_bytes": random_bytes, "random_hex": random_hex, "random_token": random_token,
    "generate_keypair": generate_keypair,
    "sign": sign, "verify": verify,
    "hkdf": hkdf, "pbkdf2": pbkdf2,
    "aes_encrypt": aes_encrypt, "aes_decrypt": aes_decrypt,
    "generate_fernet_key": generate_fernet_key,
    "fernet_encrypt": fernet_encrypt, "fernet_decrypt": fernet_decrypt,
}
