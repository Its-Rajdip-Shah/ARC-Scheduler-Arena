"""Request and response shapes for the authentication endpoints."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """The account as the frontend sees it. Never exposes the TOTP secret."""

    mfa_enabled = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'is_admin', 'is_locked', 'mfa_enabled', 'created_at', 'last_login']
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    """FR-01: a unique, well-formed email and a password that passes the
    configured validators."""

    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value


class MFAEnrolConfirmSerializer(serializers.Serializer):
    enrolment_token = serializers.CharField()
    code = serializers.CharField(min_length=6, max_length=6)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


class MFAVerifySerializer(serializers.Serializer):
    mfa_token = serializers.CharField()
    code = serializers.CharField(min_length=6, max_length=6)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
