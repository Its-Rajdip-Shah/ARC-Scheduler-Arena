"""Authentication flow tests (FR-01, FR-02, FR-03, FR-15, FR-16).

Every assertion checks the machine-readable ``error.code`` from the shared
envelope rather than the prose message, so rewording an error cannot silently
turn a rejection test green.
"""

import pytest

from accounts.tokens import MFAEnrolmentToken, MFAPendingToken
from accounts.totp import verify

from .conftest import PASSWORD, code_for, expired_token, login_through_mfa, make_user

pytestmark = pytest.mark.django_db

REGISTER = '/api/auth/register/'
ENROL = '/api/auth/mfa/enroll/confirm/'
LOGIN = '/api/auth/login/'
LOGIN_MFA = '/api/auth/login/mfa/'
ADMIN_LOGIN = '/api/auth/admin/login/'
ADMIN_LOGIN_MFA = '/api/auth/admin/login/mfa/'
REFRESH = '/api/auth/token/refresh/'
LOGOUT = '/api/auth/logout/'
ME = '/api/auth/me/'


def code(response):
    return response.data['error']['code']


def fields(response):
    return response.data['error']['fields']


# --------------------------------------------------------------------------
# Registration and enrolment (FR-01)
# --------------------------------------------------------------------------

def test_register_returns_a_qr_code_and_leaves_mfa_incomplete(api):
    response = api.post(REGISTER, {'email': 'new@example.com', 'password': PASSWORD}, format='json')

    assert response.status_code == 201
    assert response.data['user']['email'] == 'new@example.com'
    assert response.data['mfa']['provisioning_uri'].startswith('otpauth://totp/ARC:')
    assert response.data['mfa']['qr_png_base64']
    # The secret is only in the signed token until the user proves they
    # scanned it, so the account cannot log in yet.
    assert response.data['user']['mfa_enabled'] is False


def test_register_never_exposes_the_stored_secret_field(api):
    response = api.post(REGISTER, {'email': 'new@example.com', 'password': PASSWORD}, format='json')
    assert 'totp_secret_encrypted' not in response.data['user']
    assert 'password' not in response.data['user']


@pytest.mark.parametrize(
    'payload, bad_field',
    [
        ({'password': PASSWORD}, 'email'),
        ({'email': 'not-an-email', 'password': PASSWORD}, 'email'),
        ({'email': 'new@example.com'}, 'password'),
        ({'email': 'new@example.com', 'password': '123'}, 'password'),
    ],
)
def test_register_rejects_bad_input(api, payload, bad_field):
    response = api.post(REGISTER, payload, format='json')
    assert response.status_code == 400
    assert bad_field in fields(response)


def test_register_rejects_a_duplicate_email(api, user):
    response = api.post(REGISTER, {'email': user.email, 'password': PASSWORD}, format='json')
    assert response.status_code == 400
    assert 'email' in fields(response)


def test_enrolment_stores_the_secret(api):
    registered = api.post(
        REGISTER, {'email': 'new@example.com', 'password': PASSWORD}, format='json'
    ).data
    secret = registered['mfa']['secret']

    response = api.post(
        ENROL,
        {'enrolment_token': registered['enrolment_token'], 'code': code_for(secret)},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['enrolled'] is True
    assert response.data['user']['mfa_enabled'] is True


def test_enrolment_rejects_a_wrong_code(api):
    registered = api.post(
        REGISTER, {'email': 'new@example.com', 'password': PASSWORD}, format='json'
    ).data

    response = api.post(
        ENROL,
        {'enrolment_token': registered['enrolment_token'], 'code': '000000'},
        format='json',
    )

    assert response.status_code == 401
    assert code(response) == 'invalid_totp'


def test_enrolment_rejects_an_expired_token(api, user, secret):
    response = api.post(
        ENROL,
        {'enrolment_token': expired_token(MFAEnrolmentToken, user, secret=secret),
         'code': code_for(secret)},
        format='json',
    )
    assert response.status_code == 401
    assert code(response) == 'enrolment_token_invalid'


# --------------------------------------------------------------------------
# Login step one: credentials (FR-02)
# --------------------------------------------------------------------------

def test_login_returns_an_mfa_token_not_an_access_token(api, user):
    response = api.post(LOGIN, {'email': user.email, 'password': PASSWORD}, format='json')

    assert response.status_code == 200
    assert response.data['mfa_required'] is True
    assert 'mfa_token' in response.data
    assert 'access' not in response.data
    assert 'refresh' not in response.data


def test_login_rejects_a_wrong_password(api, user):
    response = api.post(LOGIN, {'email': user.email, 'password': 'wrong-password'}, format='json')
    assert response.status_code == 401
    assert code(response) == 'invalid_credentials'


def test_login_rejects_an_unknown_email(api, db):
    response = api.post(LOGIN, {'email': 'nobody@example.com', 'password': PASSWORD}, format='json')
    assert response.status_code == 401
    assert code(response) == 'invalid_credentials'


def test_login_rejects_a_locked_account(api, user):
    user.is_locked = True
    user.save(update_fields=['is_locked'])

    response = api.post(LOGIN, {'email': user.email, 'password': PASSWORD}, format='json')

    assert response.status_code == 403
    assert code(response) == 'account_locked'


def test_a_locked_account_is_not_revealed_by_a_wrong_password(api, user):
    """Checking the password first stops login being an oracle for which
    accounts exist or are locked."""
    user.is_locked = True
    user.save(update_fields=['is_locked'])

    locked = api.post(LOGIN, {'email': user.email, 'password': 'wrong'}, format='json')
    unknown = api.post(LOGIN, {'email': 'nobody@example.com', 'password': 'wrong'}, format='json')

    assert locked.status_code == unknown.status_code == 401
    assert code(locked) == code(unknown) == 'invalid_credentials'


def test_login_refuses_an_account_that_never_finished_enrolment(api, unenrolled):
    response = api.post(LOGIN, {'email': unenrolled.email, 'password': PASSWORD}, format='json')
    assert response.status_code == 403
    assert code(response) == 'mfa_enrolment_required'


# --------------------------------------------------------------------------
# Login step two: TOTP (FR-02)
# --------------------------------------------------------------------------

def test_mfa_step_issues_a_usable_token_pair(api, user, secret):
    body = login_through_mfa(api, user, secret)

    assert body['user']['email'] == user.email
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {body["access"]}')
    assert api.get(ME).status_code == 200


def test_mfa_step_updates_last_login_for_the_admin_dashboard(api, user, secret):
    assert user.last_login is None
    login_through_mfa(api, user, secret)
    user.refresh_from_db()
    assert user.last_login is not None


def test_mfa_step_rejects_a_wrong_code(api, user, secret):
    step_one = api.post(LOGIN, {'email': user.email, 'password': PASSWORD}, format='json')

    response = api.post(
        LOGIN_MFA, {'mfa_token': step_one.data['mfa_token'], 'code': '000000'}, format='json'
    )

    assert response.status_code == 401
    assert code(response) == 'invalid_totp'


def test_mfa_step_rejects_a_replayed_code(api, user, secret):
    """pyotp accepts a code for its whole validity window, so a second use of
    the same code must be refused by the replay guard."""
    first = api.post(LOGIN, {'email': user.email, 'password': PASSWORD}, format='json')
    reused = code_for(secret)
    assert api.post(
        LOGIN_MFA, {'mfa_token': first.data['mfa_token'], 'code': reused}, format='json'
    ).status_code == 200

    second = api.post(LOGIN, {'email': user.email, 'password': PASSWORD}, format='json')
    response = api.post(
        LOGIN_MFA, {'mfa_token': second.data['mfa_token'], 'code': reused}, format='json'
    )

    assert response.status_code == 401
    assert code(response) == 'invalid_totp'


def test_mfa_step_rejects_an_expired_mfa_token(api, user, secret):
    response = api.post(
        LOGIN_MFA,
        {'mfa_token': expired_token(MFAPendingToken, user, admin_login=False),
         'code': code_for(secret)},
        format='json',
    )
    assert response.status_code == 401
    assert code(response) == 'mfa_token_invalid'


def test_mfa_step_rejects_an_account_locked_between_the_two_steps(api, user, secret):
    step_one = api.post(LOGIN, {'email': user.email, 'password': PASSWORD}, format='json')
    user.is_locked = True
    user.save(update_fields=['is_locked'])

    response = api.post(
        LOGIN_MFA,
        {'mfa_token': step_one.data['mfa_token'], 'code': code_for(secret)},
        format='json',
    )

    assert response.status_code == 403
    assert code(response) == 'account_locked'


# --------------------------------------------------------------------------
# Token scope: the MFA step must not be bypassable (FR-02, FR-03)
# --------------------------------------------------------------------------

def test_an_mfa_pending_token_cannot_reach_a_protected_endpoint(api, user):
    """The whole point of the scope check. This token is validly signed and
    names a real user, so without the scope check it would be a complete
    bypass of the TOTP step."""
    step_one = api.post(LOGIN, {'email': user.email, 'password': PASSWORD}, format='json')

    api.credentials(HTTP_AUTHORIZATION=f'Bearer {step_one.data["mfa_token"]}')
    response = api.get(ME)

    assert response.status_code == 401
    assert code(response) in {'insufficient_token_scope', 'token_not_valid'}


def test_an_enrolment_token_cannot_reach_a_protected_endpoint(api, user, secret):
    token = MFAEnrolmentToken.for_user(user)
    token['secret'] = secret

    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    assert api.get(ME).status_code == 401


def test_protected_endpoints_require_a_token_at_all(api, db):
    assert api.get(ME).status_code == 401


def test_an_expired_access_token_is_rejected(api, user, secret):
    from rest_framework_simplejwt.tokens import AccessToken

    stale = expired_token(AccessToken, user, scope='full')
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {stale}')

    assert api.get(ME).status_code == 401


def test_locking_an_account_kills_a_live_session_immediately(api, user, secret):
    """FR-16: the lock must bite on the next request, not whenever the access
    token happens to expire."""
    body = login_through_mfa(api, user, secret)
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {body["access"]}')
    assert api.get(ME).status_code == 200

    user.is_locked = True
    user.save(update_fields=['is_locked'])

    response = api.get(ME)
    assert response.status_code == 401
    assert code(response) == 'account_locked'


# --------------------------------------------------------------------------
# Refresh and logout
# --------------------------------------------------------------------------

def test_refreshing_preserves_the_full_scope(api, user, secret):
    body = login_through_mfa(api, user, secret)

    refreshed = api.post(REFRESH, {'refresh': body['refresh']}, format='json')
    assert refreshed.status_code == 200

    api.credentials(HTTP_AUTHORIZATION=f'Bearer {refreshed.data["access"]}')
    assert api.get(ME).status_code == 200


def test_logout_blacklists_the_refresh_token(api, user, secret):
    body = login_through_mfa(api, user, secret)
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {body["access"]}')

    assert api.post(LOGOUT, {'refresh': body['refresh']}, format='json').status_code == 205
    assert api.post(REFRESH, {'refresh': body['refresh']}, format='json').status_code == 401


# --------------------------------------------------------------------------
# Administrator entry point (FR-15)
# --------------------------------------------------------------------------

def test_admin_login_rejects_a_standard_account(api, user):
    response = api.post(ADMIN_LOGIN, {'email': user.email, 'password': PASSWORD}, format='json')
    assert response.status_code == 403
    assert code(response) == 'not_an_administrator'


def test_admin_login_accepts_an_administrator(api, admin_user, secret):
    body = login_through_mfa(api, admin_user, secret, admin=True)
    assert body['user']['is_admin'] is True


def test_an_admin_mfa_token_is_not_redeemable_on_the_standard_endpoint(api, admin_user, secret):
    step_one = api.post(
        ADMIN_LOGIN, {'email': admin_user.email, 'password': PASSWORD}, format='json'
    )

    response = api.post(
        LOGIN_MFA,
        {'mfa_token': step_one.data['mfa_token'], 'code': code_for(secret)},
        format='json',
    )

    assert response.status_code == 403
    assert code(response) == 'wrong_login_flow'


def test_a_standard_mfa_token_is_not_redeemable_on_the_admin_endpoint(api, user, secret):
    step_one = api.post(LOGIN, {'email': user.email, 'password': PASSWORD}, format='json')

    response = api.post(
        ADMIN_LOGIN_MFA,
        {'mfa_token': step_one.data['mfa_token'], 'code': code_for(secret)},
        format='json',
    )

    assert response.status_code == 403
    assert code(response) == 'wrong_login_flow'


# --------------------------------------------------------------------------
# TOTP helper
# --------------------------------------------------------------------------

def test_verify_rejects_empty_input(secret):
    assert verify(secret, '') is False
    assert verify('', '123456') is False


def test_verify_accepts_a_current_code_once(db, secret):
    assert verify(secret, code_for(secret), user_id=1) is True
    assert verify(secret, code_for(secret), user_id=1) is False


def test_verify_without_a_user_id_does_not_consume_the_code(secret):
    """The enrolment path checks a code before a user is known to the guard."""
    assert verify(secret, code_for(secret)) is True
    assert verify(secret, code_for(secret)) is True
