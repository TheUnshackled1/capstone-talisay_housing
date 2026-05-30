"""
ISF population counts from Module 4 lot awards (GK Masterlist / housing units source).

Counts beneficiary heads and household members on units with an active LotAward,
plus legacy occupant_name rows when no award record exists.
"""

from django.db.models import Prefetch

from units.models import HousingUnit, LotAward, RelocationSite


def resolve_isf_population_site(site_id_param):
    """
    Parse analytics site filter.

    Returns (site_or_none, site_id_token) where site_or_none is None for all sites.
    """
    raw = (site_id_param or 'all').strip()
    if not raw or raw.lower() == 'all':
        return None, 'all'
    site = RelocationSite.objects.filter(id=raw, is_active=True).first()
    if site:
        return site, str(site.id)
    return None, 'all'


def isf_population_stats(site=None):
    """
    Aggregate ISF population for analytics charts.

    site: RelocationSite instance, or None for all active relocation sites.
    """
    active_award_qs = (
        LotAward.objects.filter(status='active')
        .select_related('application__applicant')
        .prefetch_related('application__applicant__household_members')
    )
    units_qs = HousingUnit.objects.select_related('site')
    if site is not None:
        units_qs = units_qs.filter(site=site)
    else:
        units_qs = units_qs.filter(site__is_active=True)

    units = units_qs.prefetch_related(Prefetch('lot_awards', queryset=active_award_qs))

    total_isf = 0
    total_population = 0
    male_count = 0
    female_count = 0
    awarded_units = 0

    def _count_person(sex):
        nonlocal total_population, male_count, female_count
        total_population += 1
        if sex == 'M':
            male_count += 1
        elif sex == 'F':
            female_count += 1

    for unit in units:
        active_award = None
        for award in unit.lot_awards.all():
            if award.status == 'active':
                active_award = award
                break

        if active_award:
            awarded_units += 1
            applicant = getattr(active_award.application, 'applicant', None)
            if applicant:
                total_isf += 1
                _count_person(applicant.sex)
                for member in applicant.household_members.all():
                    _count_person(member.sex)
                continue

        occupant = (unit.occupant_name or '').strip()
        if occupant:
            total_isf += 1
            _count_person(None)

    site_name = site.name if site else 'All relocation sites'
    site_id = str(site.id) if site else 'all'

    return {
        'total_isf': total_isf,
        'total_population': total_population,
        'male_household': male_count,
        'female_household': female_count,
        'male_count': male_count,
        'female_count': female_count,
        'awarded_units': awarded_units,
        'total_housing_units': units_qs.count(),
        'site_id': site_id,
        'site_name': site_name,
    }
