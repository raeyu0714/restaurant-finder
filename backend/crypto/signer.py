import base64
import json
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from .keys import load_private_key, load_public_key


def build_signed_data(restaurants: list, parsed_query: dict, timestamp: str) -> str:
    """
    Builds the canonical JSON string to be signed.
    Deterministic: sort_keys=True, no map_html or signature fields included.
    """
    payload = {
        "restaurants": sorted(
            [r if isinstance(r, dict) else r.model_dump() for r in restaurants],
            key=lambda x: x["id"]
        ),
        "parsed_query": parsed_query if isinstance(parsed_query, dict) else parsed_query.model_dump(),
        "timestamp": timestamp,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sign(data: str, private_key_pem: str) -> str:
    """Signs data with RSA-PSS SHA-256. Returns base64-encoded signature."""
    private_key = load_private_key(private_key_pem)
    signature = private_key.sign(
        data.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=32,  # fixed — must match SubtleCrypto {saltLength: 32}
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("ascii")


def verify(data: str, signature_b64: str, public_key_pem: str) -> bool:
    """Verifies RSA-PSS SHA-256 signature. Returns True if valid."""
    public_key = load_public_key(public_key_pem)
    try:
        public_key.verify(
            base64.b64decode(signature_b64),
            data.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=32,
            ),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False
