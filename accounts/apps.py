from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        from . import checks  # noqa: F401
        from . import signals  # noqa: F401
