from accounts.models import FIELD_INSPECTOR_POSITIONS
from units.models import StaticSettlement


def static_settlements(request):
    """
    Expose StaticSettlement rows for the Housing Units sidebar dropdown.
    Settlement 1 is hardcoded in the template (live interactive map).
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'static_settlements': []}

    # Field sidebar does not list static settlements — skip the query.
    if getattr(user, 'position', None) in FIELD_INSPECTOR_POSITIONS:
        return {'static_settlements': []}

    return {
        'static_settlements': list(
            StaticSettlement.objects.order_by('number').values('id', 'number')
        ),
    }
