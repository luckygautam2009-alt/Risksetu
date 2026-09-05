import pytest
from app.settings_values import parse_data_mode


@pytest.mark.parametrize('value, expected', [
    (None, 'mock'), ('mock', 'mock'), ('live', 'live'),
    (' MOCK \r\n', 'mock'), ('\tlive\n', 'live'),
])
def test_mode_normalizes_surrounding_whitespace(value, expected):
    assert parse_data_mode(value) == expected


@pytest.mark.parametrize('value', ['', '   ', 'production', 'DATA_MODE=mock', '"mock"'])
def test_invalid_modes_are_not_silently_converted_to_mock(value):
    with pytest.raises(RuntimeError, match='Set its environment-variable value to exactly'):
        parse_data_mode(value)


def test_invalid_mode_does_not_echo_a_misplaced_secret():
    misplaced_secret = 'private-value-not-for-logs'
    with pytest.raises(RuntimeError) as error:
        parse_data_mode(misplaced_secret)
    assert misplaced_secret not in str(error.value)


from app.settings_values import supabase_keys, supabase_service_headers


def test_modern_keys_take_precedence_and_trim_whitespace():
    assert supabase_keys({'SUPABASE_PUBLISHABLE_KEY': ' sb_publishable_test ',
                          'SUPABASE_SECRET_KEY': ' sb_secret_test ',
                          'SUPABASE_ANON_KEY': 'old-public',
                          'SUPABASE_SERVICE_ROLE_KEY': 'old-server'}) == ('sb_publishable_test', 'sb_secret_test')


def test_blank_modern_keys_fall_back_to_legacy():
    assert supabase_keys({'SUPABASE_PUBLISHABLE_KEY': ' ',
                          'SUPABASE_ANON_KEY': 'old-public',
                          'SUPABASE_SERVICE_ROLE_KEY': 'old-server'}) == ('old-public', 'old-server')


@pytest.mark.parametrize('settings', [
    {'SUPABASE_PUBLISHABLE_KEY': 'sb_secret_test'},
    {'SUPABASE_ANON_KEY': 'sb_secret_test'},
    {'SUPABASE_SECRET_KEY': 'sb_publishable_test'},
])
def test_swapped_keys_rejected_without_echoing_values(settings):
    with pytest.raises(RuntimeError) as error:
        supabase_keys(settings)
    assert all(value not in str(error.value) for value in settings.values())


def test_modern_secret_is_not_sent_as_a_jwt():
    assert supabase_service_headers('sb_secret_test') == {'apikey': 'sb_secret_test'}


def test_legacy_service_key_retains_bearer_auth():
    assert supabase_service_headers('legacy.jwt.test') == {
        'apikey': 'legacy.jwt.test', 'Authorization': 'Bearer legacy.jwt.test'}
