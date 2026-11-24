import sys
import xml.etree.ElementTree as ET
r = ET.parse(sys.argv[1]).getroot()
a = '{http://schemas.android.com/apk/res/android}'
perms = sorted(x.get(a+'name', '') for x in r.findall('uses-permission'))
print('Merged manifest permissions:', perms)
assert 'android.permission.INTERNET' not in perms
assert 'android.permission.QUERY_ALL_PACKAGES' not in perms
queries = sorted(x.get(a+'name', '') for x in r.findall('./queries/package'))
print('Package visibility (<queries>):', queries)
assert not r.findall('./queries/intent'), 'only named <package> queries are expected'
for kind in ('service','provider'):
    for x in r.findall('./application/'+kind):
        print('Merged', kind, x.get(a+'name'), 'exported:', x.get(a+'exported'), 'permission:', x.get(a+'permission'))
        assert not any(s in (x.get(a+'name') or '').lower() for s in ('network','http','webview','connectivity'))
print('No INTERNET permission; services and providers listed above for review.')
