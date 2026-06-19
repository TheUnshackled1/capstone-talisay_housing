"""Development middleware for local OAuth host canonicalization."""

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class LocalhostCanonicalizationMiddleware:
    """
    In DEBUG, redirect 127.0.0.1 to localhost so django-allauth sends a redirect_uri
    that matches Google Cloud Console entries registered for localhost.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG and request.get_host().startswith('127.0.0.1'):
            host = request.get_host()
            port = host.split(':', 1)[1] if ':' in host else ''
            canonical_host = f'localhost:{port}' if port else 'localhost'
            url = request.build_absolute_uri(request.get_full_path())
            url = url.replace(f'://{host}', f'://{canonical_host}', 1)
            return HttpResponsePermanentRedirect(url)
        return self.get_response(request)
