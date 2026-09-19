"""Shared fixtures for the authentication tests."""

from datetime import timedelta

import pyotp
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.tokens import MFAPendingToken

User = get_user_model()

PASSWORD = 'corr3ct-horse-battery'


@pytest.fixture
def secret():
    return pyotp.random_base32()


def code_for(secret):
    return pyotp.TOTP(secret).now()


def make_user(email, secret=None, **flags):
    user = User.objects.create_user(email, PASSWORD, **flags)
    if secret:
        user.totp_secret_encrypted = secret
        user.save(update_fields=['totp_secret_encrypted'])
    return user


@pytest.fixture
def user(db, secret):
    """A fully enrolled ordinary account."""
    return make_user('alice@example.com', secret)


@pytest.fixture
def admin_user(db, secret):
    return make_user('admin@example.com', secret, is_admin=True)


@pytest.fixture
def unenrolled(db):
    """Registered but never completed TOTP setup."""
    return make_user('newbie@example.com')


def expired_token(token_class, user, **claims):
    """Mint a token of the given class whose exp is already in the past."""
    token = token_class.for_user(user)
    for key, value in claims.items():
        token[key] = value
    token.set_exp(
        from_time=timezone.now() - timedelta(hours=1),
        lifetime=timedelta(minutes=5),
    )
    return str(token)


def login_through_mfa(api, user, secret, admin=False):
    """Drive both login steps and return the response body."""
    prefix = '/api/auth/admin/login/' if admin else '/api/auth/login/'
    step_one = api.post(prefix, {'email': user.email, 'password': PASSWORD}, format='json')
    assert step_one.status_code == 200, step_one.data
    step_two = api.post(
        prefix + 'mfa/',
        {'mfa_token': step_one.data['mfa_token'], 'code': code_for(secret)},
        format='json',
    )
    assert step_two.status_code == 200, step_two.data
    return step_two.data


__all__ = [
    'PASSWORD', 'code_for', 'make_user', 'expired_token', 'login_through_mfa',
    'MFAPendingToken',
]
