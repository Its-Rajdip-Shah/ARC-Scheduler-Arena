"""The two-step authentication flow (FR-01, FR-02, FR-03, FR-15).

Password and TOTP are separate requests, and the only thing linking them is a
short-lived mfa_pending token. That token names a real user and is validly
signed, so the project-wide authentication class refuses it everywhere except
the one endpoint below that expects it in the request body.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from . import totp
from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    MFAEnrolConfirmSerializer,
    MFAVerifySerializer,
    RegisterSerializer,
    UserSerializer,
)
from .tokens import FULL_ACCESS_SCOPE, MFAEnrolmentToken, MFAPendingToken

User = get_user_model()


def _issue_token_pair(user):
    refresh = RefreshToken.for_user(user)
    # Copied onto every access token derived from this refresh token, so a
    # refreshed session keeps its scope without re-running the MFA step.
    refresh['scope'] = FULL_ACCESS_SCOPE
    refresh['is_admin'] = user.is_admin
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


def _parse(token_class, raw, expired_code):
    try:
        return token_class(raw)
    except TokenError:
        raise AuthenticationFailed(
            'This token is invalid or has expired. Please start again.',
            code=expired_code,
        )


class PublicAuthView(APIView):
    """Base for the endpoints that run before a session exists.

    They register no authenticator on purpose: a client may still be holding a
    stale access token, and that must not stop it logging in again. DRF
    downgrades a 401 to 403 when a view has no authenticator to name in a
    WWW-Authenticate header, so the header is supplied here to keep the
    status codes honest.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'


class RegisterView(PublicAuthView):
    """POST /api/auth/register/ (FR-01)."""

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: inline_serializer(
                'RegisterResponse',
                {
                    'user': UserSerializer(),
                    'enrolment_token': serializers.CharField(),
                    'mfa': inline_serializer(
                        'MFAEnrolment',
                        {
                            'secret': serializers.CharField(),
                            'provisioning_uri': serializers.CharField(),
                            'qr_png_base64': serializers.CharField(),
                        },
                    ),
                },
            )
        },
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.create_user(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
        )

        # Held in the signed token, not the database, until the user proves
        # they scanned it. An abandoned registration therefore cannot log in.
        secret = totp.generate_secret()
        enrolment = MFAEnrolmentToken.for_user(user)
        enrolment['secret'] = secret
        uri = totp.provisioning_uri(user.email, secret)

        return Response(
            {
                'user': UserSerializer(user).data,
                'enrolment_token': str(enrolment),
                'mfa': {
                    'secret': secret,
                    'provisioning_uri': uri,
                    'qr_png_base64': totp.qr_png_base64(uri),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class MFAEnrolConfirmView(PublicAuthView):
    """POST /api/auth/mfa/enroll/confirm/ (FR-01)."""

    @extend_schema(
        request=MFAEnrolConfirmSerializer,
        responses=inline_serializer(
            'MFAEnrolConfirmResponse',
            {'enrolled': serializers.BooleanField(), 'user': UserSerializer()},
        ),
    )
    def post(self, request):
        serializer = MFAEnrolConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = _parse(
            MFAEnrolmentToken,
            serializer.validated_data['enrolment_token'],
            'enrolment_token_invalid',
        )
        user = User.objects.filter(pk=token.get('user_id')).first()
        if user is None:
            raise AuthenticationFailed('User not found.', code='user_not_found')
        if user.mfa_enabled:
            raise PermissionDenied('MFA is already set up for this account.',
                                   code='mfa_already_enrolled')

        secret = token.get('secret')
        if not totp.verify(secret, serializer.validated_data['code'], user.pk):
            raise AuthenticationFailed('That code is not valid.', code='invalid_totp')

        user.totp_secret_encrypted = secret
        user.save(update_fields=['totp_secret_encrypted'])

        return Response({'enrolled': True, 'user': UserSerializer(user).data})


class LoginView(PublicAuthView):
    """POST /api/auth/login/ - step one (FR-02)."""

    require_admin = False

    @extend_schema(
        request=LoginSerializer,
        responses=inline_serializer(
            'LoginResponse',
            {
                'mfa_required': serializers.BooleanField(),
                'mfa_token': serializers.CharField(help_text='Valid for 5 minutes.'),
            },
        ),
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = User.objects.normalize_email(serializer.validated_data['email'])
        user = User.objects.filter(email__iexact=email).first()

        # Credentials are checked before anything else, so that a wrong
        # password cannot be used to discover whether an account exists or
        # whether it is locked.
        if user is None or not user.check_password(serializer.validated_data['password']):
            raise AuthenticationFailed('Incorrect email address or password.',
                                       code='invalid_credentials')

        if self.require_admin and not user.is_admin:
            raise PermissionDenied('This account is not an administrator.',
                                   code='not_an_administrator')

        if user.is_locked:
            raise PermissionDenied('This account has been locked by an administrator.',
                                   code='account_locked')

        if not user.mfa_enabled:
            raise PermissionDenied('Finish setting up multi-factor authentication first.',
                                   code='mfa_enrolment_required')

        pending = MFAPendingToken.for_user(user)
        pending['admin_login'] = self.require_admin
        return Response({'mfa_required': True, 'mfa_token': str(pending)})


class AdminLoginView(LoginView):
    """POST /api/auth/admin/login/ - the separate administrator entry point
    required by FR-15."""

    require_admin = True


class MFAVerifyView(PublicAuthView):
    """POST /api/auth/login/mfa/ - step two (FR-02)."""

    require_admin = False

    @extend_schema(
        request=MFAVerifySerializer,
        responses=inline_serializer(
            'TokenPairResponse',
            {
                'access': serializers.CharField(),
                'refresh': serializers.CharField(),
                'user': UserSerializer(),
            },
        ),
    )
    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = _parse(
            MFAPendingToken,
            serializer.validated_data['mfa_token'],
            'mfa_token_invalid',
        )
        user = User.objects.filter(pk=token.get('user_id')).first()
        if user is None:
            raise AuthenticationFailed('User not found.', code='user_not_found')

        # An administrator token must not be redeemable on the ordinary
        # endpoint, or the other way round.
        if bool(token.get('admin_login')) != self.require_admin:
            raise PermissionDenied('This token belongs to a different login flow.',
                                   code='wrong_login_flow')

        if self.require_admin and not user.is_admin:
            raise PermissionDenied('This account is not an administrator.',
                                   code='not_an_administrator')

        # Re-checked here because an administrator may have locked the account
        # during the few minutes the mfa_token is alive.
        if user.is_locked:
            raise PermissionDenied('This account has been locked by an administrator.',
                                   code='account_locked')

        if not totp.verify(user.totp_secret_encrypted, serializer.validated_data['code'], user.pk):
            raise AuthenticationFailed('That code is not valid.', code='invalid_totp')

        # Updates last_login, which FR-16's active-user count reads.
        user_logged_in.send(sender=user.__class__, request=request, user=user)

        return Response({**_issue_token_pair(user), 'user': UserSerializer(user).data})


class AdminMFAVerifyView(MFAVerifyView):
    """POST /api/auth/admin/login/mfa/ (FR-15)."""

    require_admin = True


class LogoutView(APIView):
    """POST /api/auth/logout/ - blacklists the refresh token."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=LogoutSerializer, responses={205: None})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data['refresh']).blacklist()
        except TokenError:
            raise AuthenticationFailed('That refresh token is not valid.',
                                       code='invalid_refresh_token')
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    """GET /api/auth/me/ - the signed-in account."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)
