import urllib.request
import urllib.error

req = urllib.request.Request('http://127.0.0.1:8000/api/stats/recommendations/')
try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code}")
    print(e.read().decode())
except Exception as e:
    print(e)
