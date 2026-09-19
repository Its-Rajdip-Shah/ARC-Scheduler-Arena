"""TOTP secret generation and verification (FR-01, FR-02, FR-15)."""

import base64
import io

import pyotp
import qrcode
from django.core.cache import cache

ISSUER = 'ARC'

#: pyotp's window either side of the current 30-second step, to tolerate clock
#: drift between the phone and the server.
VALID_WINDOW = 1

#: A code stays valid across VALID_WINDOW steps, so a used code is remembered
#: for slightly longer than that span to close the replay gap.
REPLAY_BLOCK_SECONDS = 30 * (2 * VALID_WINDOW + 1) + 5


def generate_secret():
    return pyotp.random_base32()


def provisioning_uri(email, secret):
    """The otpauth:// URI an authenticator app scans."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_png_base64(uri):
    """The same URI as a base64 PNG, for clients that render an image."""
    buffer = io.BytesIO()
    qrcode.make(uri).save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()


def verify(secret, code, user_id=None):
    """Check a six-digit code, refusing one that was already spent.

    pyotp alone would accept the same code repeatedly for its whole validity
    window, so anyone who observed it could replay it. Spent codes are
    remembered in the cache until they expire, which needs no extra column on
    the User table.
    """
    if not (secret and code):
        return False

    if not pyotp.TOTP(secret).verify(code, valid_window=VALID_WINDOW):
        return False

    if user_id is not None:
        key = f'arc:totp:used:{user_id}:{code}'
        # add() is atomic and fails when the key is already present.
        if not cache.add(key, True, timeout=REPLAY_BLOCK_SECONDS):
            return False

    return True
