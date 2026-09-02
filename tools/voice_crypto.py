from __future__ import annotations

import argparse
import base64
import os
import secrets
import struct
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


MAGIC = b"IAVOICE1"
ITERATIONS = 390000


def read_passphrase(args: argparse.Namespace) -> str:
    if args.create_passphrase:
        value = secrets.token_urlsafe(48)
        args.passphrase_file.write_text(value, encoding="utf-8")
        return value
    if args.passphrase_env:
        value = os.getenv(args.passphrase_env)
        if not value:
            raise RuntimeError(f"Environment variable is empty: {args.passphrase_env}")
        return value
    if args.passphrase_file and args.passphrase_file.exists():
        return args.passphrase_file.read_text(encoding="utf-8").strip()
    raise RuntimeError("Provide --passphrase-file or --passphrase-env.")


def key_from_passphrase(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_file(input_path: Path, output_path: Path, passphrase: str) -> None:
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = key_from_passphrase(passphrase, salt)
    encrypted = AESGCM(key).encrypt(nonce, input_path.read_bytes(), None)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(
        MAGIC
        + struct.pack(">I", ITERATIONS)
        + salt
        + nonce
        + base64.b64encode(encrypted)
    )


def decrypt_file(input_path: Path, output_path: Path, passphrase: str) -> None:
    data = input_path.read_bytes()
    if not data.startswith(MAGIC):
        raise RuntimeError("Unsupported encrypted voice file format.")
    offset = len(MAGIC)
    iterations = struct.unpack(">I", data[offset : offset + 4])[0]
    if iterations != ITERATIONS:
        raise RuntimeError(f"Unsupported KDF iteration count: {iterations}")
    offset += 4
    salt = data[offset : offset + 16]
    offset += 16
    nonce = data[offset : offset + 12]
    offset += 12
    encrypted = base64.b64decode(data[offset:])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(AESGCM(key_from_passphrase(passphrase, salt)).decrypt(nonce, encrypted, None))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Encrypt/decrypt the owned Chatterbox voice sample.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("encrypt", "decrypt"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--input", required=True, type=Path)
        cmd.add_argument("--output", required=True, type=Path)
        cmd.add_argument("--passphrase-file", type=Path)
        cmd.add_argument("--passphrase-env")
        cmd.add_argument("--create-passphrase", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    passphrase = read_passphrase(args)
    if args.command == "encrypt":
        encrypt_file(args.input, args.output, passphrase)
        print(f"Encrypted voice sample: {args.output}")
    else:
        decrypt_file(args.input, args.output, passphrase)
        print(f"Decrypted voice sample: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
