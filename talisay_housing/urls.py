from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("", include("accounts.urls")),
    path("intake/", include("intake.urls")),
    path("applications/", include("applications.urls")),
    path("documents/", include("documents.urls")),
    path("units/", include("units.urls")),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
