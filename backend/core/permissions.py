"""Permission classes shared across the ARC apps."""

from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Allow access only to objects belonging to the requesting user.

    Queryset scoping (see core.mixins.UserScopedMixin) is the primary FR-03
    control; this is the object-level backstop for views that look objects up
    outside a scoped queryset.
    """

    message = 'You do not have access to this object.'

    owner_field = 'user'

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if obj == user:
            return True
        return getattr(obj, getattr(view, 'owner_field', self.owner_field), None) == user


class IsAdminAccount(BasePermission):
    """Allow access only to accounts flagged as ARC administrators (FR-15, FR-16).

    This checks the ERD's ``is_admin`` column rather than Django's ``is_staff``.
    """

    message = 'Administrator permission is required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, 'is_admin', False))
