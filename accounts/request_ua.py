"""Client UA / Client Hints helpers shared by field desks."""


def prefer_mobile_client(request) -> bool:
    """True when the request likely comes from a phone — used for XOR table/cards."""
    ch = (request.headers.get('Sec-CH-UA-Mobile') or '').strip()
    if ch == '?1':
        return True
    if ch == '?0':
        return False
    ua = (request.META.get('HTTP_USER_AGENT') or '').lower()
    return any(tok in ua for tok in ('mobile', 'android', 'iphone', 'ipod', 'webos'))
