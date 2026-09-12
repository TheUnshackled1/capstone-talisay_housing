from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

from accounts import views as accounts_views
from intake import views as intake_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path('auth/google/login/', accounts_views.tha_google_oauth_login, name='google_login'),
    path('auth/', include('allauth.urls')),
    path("", include("dashboard.urls")),
    path("", include("accounts.urls")),
    path("intake/", include("intake.urls")),
    path("applications/", include("applications.urls")),
    path("documents/", include("documents.urls")),
    path("units/", include("units.urls")),
    path("cases/", include("cases.urls")),

    # Public — Applicant status tracker (no login required, SMS deep link)
    # Clean short URL: talisayihms.com/status/APP-20260827-1234/
    path("status/<str:ref>/", intake_views.applicant_status_tracker, name='applicant_status_tracker'),
]

# Serve user uploads in both dev and production. WhiteNoise only covers STATIC_ROOT,
# so MEDIA_ROOT (a mounted Volume on Railway) needs its own route.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
