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
    ('login attempts from one IP', 1),
    ('callback to unknown host', 1),
    ('connections at regular intervals', 1),
])
def test_flow_policy(text, expected):
    assert predict_flow_text(text)[0] == expected
