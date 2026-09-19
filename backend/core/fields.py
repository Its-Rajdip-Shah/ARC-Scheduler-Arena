"""Model fields shared across the ARC apps."""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signals import setting_changed
from django.db import NotSupportedError, models
from django.dispatch import receiver


@lru_cache(maxsize=4)
def _build_fernet(key):
    return Fernet(key)


def get_fernet():
    """Return the Fernet instance built from ARC_FIELD_ENCRYPTION_KEY."""
    key = getattr(settings, 'ARC_FIELD_ENCRYPTION_KEY', '')
    if not key:
        raise ImproperlyConfigured(
            'ARC_FIELD_ENCRYPTION_KEY is not set. Generate one with '
            '`python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"` and export it before '
            'reading or writing encrypted fields.'
        )
    try:
        return _build_fernet(key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            'ARC_FIELD_ENCRYPTION_KEY is not a valid Fernet key. It must be '
            '32 url-safe base64-encoded bytes.'
        ) from exc


@receiver(setting_changed)
def _reset_fernet_cache(sender, setting, **kwargs):
    if setting == 'ARC_FIELD_ENCRYPTION_KEY':
        _build_fernet.cache_clear()


def token_length(plaintext_length):
    """Length of the Fernet token produced for a plaintext of this length."""
    raw = 57 + 16 * (plaintext_length // 16 + 1)
    return ((raw + 2) // 3) * 4


def max_plaintext_length(column_length):
    """Largest plaintext that still fits a column of the given size."""
    plaintext = 0
    while token_length(plaintext + 1) <= column_length:
        plaintext += 1
    return plaintext


class EncryptedCharField(models.CharField):
    """A CharField whose database column holds a Fernet token.

    Python-side values are always plaintext; encryption happens on the way
    into the database and decryption on the way out. ``max_length`` sizes the
    *column*, so it bounds the ciphertext rather than the plaintext: a
    varchar(255) column holds roughly 130 plaintext characters.

    Fernet uses a random IV, so the same plaintext encrypts to a different
    token every time. Equality lookups can therefore never match and are
    rejected rather than silently returning nothing.
    """

    description = 'Character field stored as a Fernet token'

    SUPPORTED_LOOKUPS = frozenset({'isnull'})

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, ''):
            return value
        token = get_fernet().encrypt(str(value).encode()).decode()
        if self.max_length is not None and len(token) > self.max_length:
            raise ValueError(
                f'Encrypted value for {self.model.__name__}.{self.name} is '
                f'{len(token)} characters, which exceeds the column size of '
                f'{self.max_length}. Plaintext is limited to '
                f'{max_plaintext_length(self.max_length)} characters.'
            )
        return token

    def from_db_value(self, value, expression, connection):
        if value in (None, ''):
            return value
        try:
            return get_fernet().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ValueError(
                f'Could not decrypt {self.model.__name__}.{self.name}. The '
                'stored token does not match ARC_FIELD_ENCRYPTION_KEY.'
            ) from exc

    def get_lookup(self, lookup_name):
        if lookup_name not in self.SUPPORTED_LOOKUPS:
            raise NotSupportedError(
                f'{type(self).__name__} does not support the "{lookup_name}" '
                'lookup because each value encrypts to a different token. '
                f'Only {sorted(self.SUPPORTED_LOOKUPS)} are available.'
            )
        return super().get_lookup(lookup_name)
