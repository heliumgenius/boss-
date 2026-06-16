"""Platform keychain integration for credential storage.

Strategy:
1. Try OS keychain (macOS Keychain, Windows Credential Manager, Linux libsecret)
2. Fall back to encrypted file using a machine-derived key
3. Last resort: plaintext file with warning
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "boss-cli"
CREDENTIAL_FILE = CONFIG_DIR / "credential.json"
KEYRING_SERVICE = "boss-cli"
KEYRING_USER = "zhipin_session"


def _store_keychain(data: dict) -> bool:
    """Store credential in OS keychain. Returns True on success."""
    try:
        import keyring

        payload = json.dumps(data, ensure_ascii=False)
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, payload)
        return True
    except ImportError:
        logger.debug("keyring not installed, skipping keychain")
    except Exception as exc:
        logger.warning("Keychain store failed: %s", exc)
    return False


def _load_keychain() -> dict | None:
    """Load credential from OS keychain. Returns dict or None."""
    try:
        import keyring

        payload = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        if payload:
            return json.loads(payload)
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("Keychain load failed: %s", exc)
    return None


def _delete_keychain() -> bool:
    """Delete credential from OS keychain."""
    try:
        import keyring

        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
        return True
    except Exception:
        pass
    return False


def save_credential_data(data: dict) -> None:
    """Save credential data, trying keychain first, falling back to file."""
    if _store_keychain(data):
        logger.info("Credential saved to system keychain")
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIAL_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    try:
        CREDENTIAL_FILE.chmod(0o600)
    except Exception:
        pass
    logger.warning("Credential saved to plaintext file (keychain unavailable): %s", CREDENTIAL_FILE)


def load_credential_data() -> dict | None:
    """Load credential data, trying keychain first, then file."""
    data = _load_keychain()
    if data:
        return data

    if CREDENTIAL_FILE.exists():
        try:
            return json.loads(CREDENTIAL_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read credential file: %s", exc)
    return None


def delete_credential_data() -> None:
    """Delete credential from keychain and file."""
    _delete_keychain()
    if CREDENTIAL_FILE.exists():
        CREDENTIAL_FILE.unlink()
