import pytest
from triage.detect import predict_flow_text

@pytest.mark.parametrize('text,expected', [
    ('normal port scan of 200 different ports', 'uncertain'),
    ('port scan of 200 ports from unknown IP', 1),
    ('scheduled backup every 5 minutes to NAS', 0),
    ('routine heartbeat every 60 seconds to update server', 0),
    ('normal beacon to C2 server every 5 minutes', 'uncertain'),
    ('beacon to unknown host every 5 minutes', 1),
    ('routine login attempts: 300 failed SSH logins', 'uncertain'),
    ('normal update check rejected by firewall', 0),
    ('repeated connections rejected from one IP', 'uncertain'),
    ('routine job obtained root shell', 1),
    ('300 failed SSH logins from one IP', 1),
    ('repeated failed login attempts from one IP', 1),
    ('successful login attempt from the admin workstation', 0),
    ('there were no login attempts', 0),
    ('zero login attempts in the last hour', 0),
    ("user's login attempt was authenticated", 0),
    ('database login attempt succeeded', 0),
    ('failed SSH logins from one IP', 1),
    ('repeated failed SSH logins', 1),
    ('no failed SSH logins', 0),
    ('without repeated failed login attempts', 0),
    ('successful backup. 300 failed SSH logins', 1),
    ('backup completed. 300 failed SSH logins were authenticated', 1),
    ('300 failed SSH logins followed by a successful login', 1),
    ('300 failed SSH logins then attacker authenticated as admin', 1),
    ('0 failed SSH logins', 0),
    ('1 login attempt', 0),
    ('2 login attempts', 0),
    ('5 logins from office IP', 0),
    ('300 successful logins from the office', 0),
    ('Accepted sessions: 0\n300 failed SSH logins', 1),
    ('1,234 failed logins', 1),
    ('1 successful login', 0),
    ('0 successful logins', 0),
    ('failed passwords', 1),
    ('brute force was not successful', 1),
    ('successful brute force', 1),
    ('brute force succeeded', 1),
    ('password guessing was successful', 1),
    ('brute force detected, authenticated users excluded', 1),
    ('brute force detected excluding authenticated sessions', 1),
    ("this isn't a port scan", 0),
    ("it isn't a flood", 0),
    ("this wasn't a port scan", 0),
    ("these aren't port scans", 0),
    ("these weren't port scans", 0),
    ("didn't find failed SSH logins", 0),
    ('did not find failed SSH logins', 0),
    ('without any port scan', 0),
    ('no evidence of a port scan', 0),
    ('no sign of any port scan', 0),
    ('no reconnaissance or brute force seen', 0),
    ('not a normal port scan', 'uncertain'),
    ('normal traffic, no port scan', 0),
    ('this is not a port scan', 0),
    # Negation of "normal" leaves the scan itself ambiguous.
    ('not a normal port scan of 200 ports', 'uncertain'),
    ('routine least privilege review of the service account', 0),
    ('privilege escalation', 1),
    ('elevated privileges', 1),
    ('gained root', 1),
    ('callback to unknown host', 1),
    ('connections at regular intervals', 1),
])
def test_flow_policy(text, expected):
    assert predict_flow_text(text)[0] == expected


def test_failure_then_success_evidence():
    _, _, evidence = predict_flow_text('300 failed SSH logins followed by a successful login')
    assert any('possible compromise' in item for item in evidence)


def test_large_login_count_does_not_raise():
    assert predict_flow_text('9' * 5000 + ' login attempts')[0] == 1


def test_success_on_next_line_is_not_login_outcome():
    label, _, evidence = predict_flow_text('300 failed SSH logins\nsuccessful backup')
    assert label == 1 and all('possible compromise' not in item for item in evidence)


def test_negation_does_not_cross_newline():
    assert predict_flow_text('no evidence of\nport scan')[0] == 1


@pytest.mark.parametrize('text', [
    '300 failed SSH logins followed by a login that was not successful',
    '300 failed SSH logins, authenticated users excluded',
    '300 failed SSH logins excluding authenticated sessions',
    '300 failed SSH logins followed by no successful login',
])
def test_no_compromise_evidence_for_negated_or_excluded_success(text):
    label, _, evidence = predict_flow_text(text)
    assert label == 1 and all('possible compromise' not in item for item in evidence)


@pytest.mark.parametrize('text', ['9,' * 32500, '1,' * 16000 + 'x'])
def test_malformed_numeric_tokens_are_fast(text):
    import time
    start = time.monotonic()
    predict_flow_text(text)
    assert time.monotonic() - start < 0.5
