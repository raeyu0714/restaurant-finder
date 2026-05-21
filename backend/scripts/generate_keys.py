"""
One-time RSA-2048 key generation script.
Run from the project root:  python backend/scripts/generate_keys.py
Writes keys/private_key.pem and keys/public_key.pem.
WARNING: never commit these files to git.
"""
import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
KEYS_DIR     = os.path.join(PROJECT_ROOT, "keys")


def generate():
    os.makedirs(KEYS_DIR, exist_ok=True)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_path = os.path.join(KEYS_DIR, "private_key.pem")
    pub_path  = os.path.join(KEYS_DIR, "public_key.pem")

    with open(priv_path, "wb") as f:
        f.write(private_pem)
    with open(pub_path, "wb") as f:
        f.write(public_pem)

    print(f"[✓] Private key → {priv_path}")
    print(f"[✓] Public key  → {pub_path}")
    print()
    print("Next steps:")
    print("  1. Copy the contents of keys/public_key.pem into frontend/js/config.js")
    print("  2. Set RSA_PRIVATE_KEY_PEM and RSA_PUBLIC_KEY_PEM in your .env file")
    print("  3. Add keys/ to .gitignore (already done if you cloned this repo)")
    print()
    print("=== Public key (paste into frontend/js/config.js) ===")
    print(public_pem.decode())


if __name__ == "__main__":
    generate()
