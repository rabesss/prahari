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
