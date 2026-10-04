import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

data = json.dumps({
    'session_id': 'test_utf8_final',
    'phone_hash': 'mock_hash_priya_01',
    'message': 'Where is my order'
}).encode('utf-8')

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/chat/message',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    r = urllib.request.urlopen(req, timeout=20)
    result = json.loads(r.read().decode('utf-8'))
    print('STATUS: 200 OK')
    print('REPLY:', result.get('reply', '')[:300])
    print('BUTTONS:', result.get('buttons'))
    print('ERROR field:', result.get('error'))
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8')
    print('HTTP ERROR:', e.code, body[:500])
except Exception as e:
    print('FAIL:', e)
