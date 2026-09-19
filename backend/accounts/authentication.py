"""Project-wide JWT authentication (FR-02, FR-03, FR-16)."""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings

from .tokens import FULL_ACCESS_SCOPE


class ArcJWTAuthentication(JWTAuthentication):
    """JWTAuthentication with two extra refusals.

    First, a token must carry ``scope="full"``. A half-authenticated
    mfa_pending token would otherwise be a complete bypass of the TOTP step,
    since it is a validly signed JWT naming a real user.

    Second, the account is re-read on every request and refused while locked.
    Checking only at login would leave an administrator's lock (FR-16)
    ineffective until the user's existing access token happened to expire.
    """

    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        if token.get('scope') != FULL_ACCESS_SCOPE:
            raise InvalidToken({
                'detail': 'This token cannot be used to access the API.',
                'code': 'insufficient_token_scope',
            })
        return token

    def get_user(self, validated_token):
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise InvalidToken({
                'detail': 'The token identifies no user.',
                'code': 'missing_user_claim',
            })

        try:
            user = self.user_model.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except self.user_model.DoesNotExist:
            raise AuthenticationFailed('User not found.', code='user_not_found')

        if user.is_locked:
            raise AuthenticationFailed(
                'This account has been locked by an administrator.',
                code='account_locked',
            )

        return user
