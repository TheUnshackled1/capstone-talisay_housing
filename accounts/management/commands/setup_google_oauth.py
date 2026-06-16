"""
Bootstrap django.contrib.sites Site and allauth SocialApp for Google OAuth.

Usage:
    python manage.py setup_google_oauth

Requires GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env.
Redirect URI for dev: http://localhost:8000/auth/google/login/callback/
"""

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = 'Configure Site domain and Google SocialApp from environment variables'

    def add_arguments(self, parser):
        parser.add_argument(
            '--site-domain',
            default='localhost:8000',
            help='Site domain for OAuth redirects (default: localhost:8000)',
        )
        parser.add_argument(
            '--site-name',
            default='IHSMS Local',
            help='Human-readable Site name',
        )

    def handle(self, *args, **options):
        client_id = (getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '') or '').strip()
        secret = (getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', '') or '').strip()
        if not client_id or not secret:
            raise CommandError(
                'Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env first.'
            )

        site_id = getattr(settings, 'SITE_ID', 1)
        site, _ = Site.objects.update_or_create(
            pk=site_id,
            defaults={
                'domain': options['site_domain'],
                'name': options['site_name'],
            },
        )
        self.stdout.write(self.style.SUCCESS(f'Site {site.pk}: {site.domain} ({site.name})'))

        google_apps = list(SocialApp.objects.filter(provider='google').order_by('pk'))
        if len(google_apps) > 1:
            for duplicate in google_apps[1:]:
                duplicate.delete()
            self.stdout.write(
                self.style.WARNING(f'Removed {len(google_apps) - 1} duplicate Google SocialApp row(s).')
            )

        app, created = SocialApp.objects.update_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': client_id,
                'secret': secret,
            },
        )
        app.sites.set([site])
        verb = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{verb} Google SocialApp (client_id …{client_id[-8:]})'))
        self.stdout.write(
            self.style.NOTICE(
                '\nGoogle Cloud redirect URI:\n'
                f'  http://{site.domain}/auth/google/login/callback/\n'
            )
        )
