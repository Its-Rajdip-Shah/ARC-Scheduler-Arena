"""Scoped JWTs for the two-step login (FR-01, FR-02, FR-15).

Three token kinds circulate, and only one of them may reach a protected
endpoint:

- enrolment: issued by register, carries the freshly generated TOTP secret
  and is exchanged for a stored secret once the user proves they scanned it.
- mfa_pending: issued once a password is accepted, exchanged for real tokens
  once a TOTP code is accepted.
- access / refresh: the ordinary pair, marked ``scope="full"``.

SimpleJWT stamps a token_type claim and refuses to parse a token as the wrong
class, so the separation is enforced by the signature rather than by a
convention the views have to remember.
"""

from datetime import timedelta

from rest_framework_simplejwt.tokens import Token

#: Marks a token as usable on ordinary endpoints. Anything else is refused by
#: accounts.authentication.ArcJWTAuthentication.
FULL_ACCESS_SCOPE = 'full'


class MFAEnrolmentToken(Token):
    """Proves a just-registered account owns this pending TOTP secret.

    The secret rides inside the token rather than the database so that an
    account which never completes enrolment cannot log in. The token is signed
    but not encrypted; that is acceptable here because the same response also
    shows the user the secret and its QR code.
    """

    token_type = 'mfa_enrol'
    lifetime = timedelta(minutes=15)


class MFAPendingToken(Token):
    """Proves a password was accepted. Worthless anywhere but the TOTP step."""

    token_type = 'mfa_pending'
    lifetime = timedelta(minutes=5)
