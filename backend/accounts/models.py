"""ARC user accounts (FR-01, FR-02, FR-03, FR-15, FR-16)."""

from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Length
from django.utils import timezone

from core.fields import EncryptedCharField


class UserQuerySet(models.QuerySet):
    def admins(self):
        return self.filter(is_admin=True)

    def locked(self):
        return self.filter(is_locked=True)

    def active_since(self, days=7):
        """Users who logged in within the window - FR-16's 'active users'."""
        return self.filter(last_login__gte=timezone.now() - timedelta(days=days))

    def mfa_enrolled(self):
        """Users who finished TOTP setup (FR-01).

        Tested by ciphertext length, because EncryptedCharField refuses
        content lookups outright: every value encrypts to a different token,
        so an ``exact`` or ``gt`` comparison against the column would quietly
        return the wrong answer. Length is the one thing about the stored
        token that still means something.
        """
        return self.annotate(
            _secret_length=Length('totp_secret_encrypted')
        ).filter(_secret_length__gt=0)


class UserManager(BaseUserManager.from_queryset(UserQuerySet)):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('An email address is required.')
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_admin', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields['is_admin'] = True
        extra_fields['is_locked'] = False
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser):
    """An ARC account, mapped onto the report's User table.

    PermissionsMixin is deliberately not used: it would add is_superuser,
    groups and user_permissions columns that the ERD does not have. Django
    admin only needs is_staff, is_superuser and the has_*_perm methods, so
    those are derived from is_admin below and cost no extra columns.
    """

    id = models.BigAutoField(primary_key=True, db_column='user_id')
    email = models.EmailField(max_length=255, unique=True)
    # Widened from AbstractBaseUser's 128 to match the report's VARCHAR(255).
    password = models.CharField(max_length=255, db_column='password_hash')
    # NOT NULL per the report; empty until the user finishes TOTP enrolment,
    # which FR-01 places after registration.
    totp_secret_encrypted = EncryptedCharField(max_length=255, blank=True, default='')
    is_admin = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True, db_column='last_login_at')

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        ordering = ['email']

    def __str__(self):
        return self.email

    @property
    def mfa_enabled(self):
        """True once a TOTP secret has been stored (FR-01)."""
        return bool(self.totp_secret_encrypted)

    @property
    def is_active(self):
        """Django's auth backends refuse inactive users, which is how FR-16's
        account lock blocks login."""
        return not self.is_locked

    @property
    def is_staff(self):
        return self.is_admin

    @property
    def is_superuser(self):
        return self.is_admin

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return self.is_admin
