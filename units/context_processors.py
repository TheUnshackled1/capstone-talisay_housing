from units.models import StaticSettlement


def static_settlements(request):
    """
    Expose StaticSettlement rows for the Housing Units sidebar dropdown.
    Settlement 1 is hardcoded in the template (live interactive map).
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'static_settlements': []}

    return {
        'static_settlements': list(
            StaticSettlement.objects.order_by('number').only('id', 'number')
        ),
    }
