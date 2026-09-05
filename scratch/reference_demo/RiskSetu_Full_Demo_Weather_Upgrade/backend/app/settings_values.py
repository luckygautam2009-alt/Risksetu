"""Pure environment-value parsing, without loading credentials or storage."""

def parse_data_mode(value: str | None) -> str:
    mode = 'mock' if value is None else value.strip().lower()
    if mode not in {'mock', 'live'}:
        # Never echo the supplied value: a secret may have been pasted by mistake.
        raise RuntimeError(
            'Invalid DATA_MODE. Set its environment-variable value to exactly '
            'mock or live (without quotes or DATA_MODE=). '
            'An empty value is invalid. After changing hosted settings, redeploy. '
            'Live mode also requires Supabase configuration.'
        )
    return mode


def supabase_keys(environ):
    def pick(primary, legacy):
        return environ.get(primary, '').strip() or environ.get(legacy, '').strip()

    public = pick('SUPABASE_PUBLISHABLE_KEY', 'SUPABASE_ANON_KEY')
    secret = pick('SUPABASE_SECRET_KEY', 'SUPABASE_SERVICE_ROLE_KEY')
    if public.startswith('sb_secret_') or secret.startswith('sb_publishable_'):
        raise RuntimeError('Supabase public and server keys are in the wrong settings.')
    return public, secret


def supabase_service_headers(key):
    headers = {'apikey': key}
    # Modern opaque keys are not JWTs. Retain bearer auth for legacy JWTs.
    if not key.startswith('sb_secret_'):
        headers['Authorization'] = f'Bearer {key}'
    return headers
