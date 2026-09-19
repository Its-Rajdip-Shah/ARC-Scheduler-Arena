"""Serializer fields shared across the ARC apps."""

from rest_framework import serializers


class UserScopedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """A primary-key relation restricted to the requesting user's own rows.

    Scoping a viewset's queryset stops a user *reading* another user's data,
    but does nothing about a payload that names a foreign primary key. Without
    this field a user could POST another user's ``parent`` or ``tag``, then
    read the foreign title back out of the response. Use it for every relation
    a client is allowed to name.
    """

    default_error_messages = {
        'does_not_exist': 'Invalid pk "{pk_value}" - object does not exist.',
    }

    def __init__(self, **kwargs):
        self.user_field = kwargs.pop('user_field', 'user')
        super().__init__(**kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return queryset.none()
        return queryset.filter(**{self.user_field: user})
