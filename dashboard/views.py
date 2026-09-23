from django.shortcuts import render
from django.core.cache import cache
from intake.models import Barangay, Applicant
from units.models import HousingUnit
from applications.models import Application

# Cache TTL for homepage stats: 10 minutes.
# These are display-only counters — minor staleness is acceptable.
_HOME_STATS_CACHE_KEY = 'homepage_stats_v1'
_HOME_STATS_TTL = 600  # 10 minutes


def home(request):
    """Homepage with dynamic stats from database.

    Stats are cached for 10 minutes so the four COUNT(*) queries don't
    fire on every page load (previously 4 uncached DB hits per request).
    """
    stats = cache.get(_HOME_STATS_CACHE_KEY)
    if stats is None:
        stats = {
            'barangays_count': Barangay.objects.filter(is_active=True).count(),
            'applicants_count': Applicant.objects.count(),
            'housing_units_count': HousingUnit.objects.count(),
            'applications_count': Application.objects.count(),
        }
        cache.set(_HOME_STATS_CACHE_KEY, stats, _HOME_STATS_TTL)

    return render(request, 'staff/index.html', stats)
