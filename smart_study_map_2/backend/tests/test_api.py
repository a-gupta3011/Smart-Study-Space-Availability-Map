from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json().get('status') == 'ok'

def test_rooms_all():
    r = client.get('/rooms/all')
    assert r.status_code == 200
    assert isinstance(r.json(), list)
