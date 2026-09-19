from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Registers the drf-spectacular extensions by import side effect.
        from core import schema  # noqa: F401
