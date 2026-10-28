import os
from concurrent.futures import ThreadPoolExecutor
import json

os.environ['DATABASE_URL'] = 'sqlite:////tmp/bitverde-tests.db'
os.environ['STAFF_PASSWORD'] = 'test-only-password-123'
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.models.models import TriviaSession
import pytest

@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as client:
        yield client

AUTH = ('staff', 'test-only-password-123')

def complete(client, success=True):
    start = client.post('/api/trivia/start', json={}).json()
    assert all('correct' not in q for q in start['questions'])
    with SessionLocal() as db:
        questions = json.loads(db.get(TriviaSession, start['session_id']).questions)
    answers = [q['correct'] for q in questions]
    if not success:
        answers[0] = 1 - answers[0]
    response = client.post('/api/trivia/'+start['session_id']+'/submit', json={'answers':answers})
    return start, answers, response.json()

def test_round_and_atomic_redemption(client):
    start, answers, result = complete(client)
    assert result['passed'] and result['token'].startswith('#0x')
    assert not result['canjeado']
    assert client.post('/api/trivia/'+start['session_id']+'/submit',json={'answers':answers}).status_code == 409
    assert client.post('/api/staff/redeem',json={'token':result['token']}).status_code == 401
    def redeem(_):
        return client.post('/api/staff/redeem',json={'token':result['token']},auth=AUTH).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(redeem,range(2))) == [200,409]
    assert client.get('/api/staff/token',params={'token':result['token']},auth=AUTH).json()['canjeado']
    metrics=client.get('/api/metrics').json()
    assert metrics['repaired']==1 and result['token'] not in json.dumps(metrics)

def test_failure_validation_and_expiry(client):
    _,_, result = complete(client,False)
    assert result['token'] is None and not result['passed']
    assert client.get('/api/metrics').json()['repaired']==0
    session=client.post('/api/trivia/start',json={}).json()['session_id']
    assert client.post(f'/api/trivia/{session}/submit',json={'answers':[-1,0,0]}).status_code==422
    from datetime import timedelta
    with SessionLocal() as db:
        row=db.get(TriviaSession,session)
        row.created_at-=timedelta(minutes=21)
        db.commit()
    assert client.post(f'/api/trivia/{session}/submit',json={'answers':[0,0,0]}).status_code==410

def test_donation_bytes_metrics_and_privacy(client):
    body={'alias':'María <script>', 'category':'Audífonos','quantity':2,'weight_kg':'0.250'}
    response=client.post('/api/donations',json=body)
    assert response.status_code==201
    data=response.json()
    payload=bytes.fromhex(data['payload_hex'])
    assert payload==bytes(int(x,2) for x in data['payload_binary'].split())
    assert json.loads(payload)['alias']==body['alias']
    metrics=client.get('/api/metrics').json()
    assert metrics['items']==2 and metrics['weight_kg']==0.25
    assert body['alias'] not in json.dumps(metrics)
    assert len(metrics['recent'][0]['binary'])==64
    for bad in [{'quantity':0},{'weight_kg':'-1'},{'category':'invalid'},{'alias':'  '},{'quantity':1.5}]:
        assert client.post('/api/donations',json=body|bad).status_code==422

def test_views_security_and_qr(client):
    for path in ['/','/registro','/dashboard','/health','/api/qr.svg','/static/js/app.js']:
        assert client.get(path).status_code==200
    assert client.get('/staff').status_code==401
    assert client.get('/staff',auth=AUTH).status_code==200
    assert client.get('/staff',auth=('staff','wrong')).status_code==401
    assert client.post('/api/trivia/start',json={},headers={'Origin':'https://evil.example'}).status_code==403
    assert '<svg' in client.get('/api/qr.svg').text
    assert client.get('/api/metrics').headers['cache-control']=='no-store'
    assert client.post('/api/staff/redeem',json={'token':'#0xMISSING-BIT'},auth=AUTH).status_code==404

OFFICIAL_CATEGORIES = [
    'Celulares', 'Cargadores', 'Cables', 'Teclados', 'Mouse',
    'Audífonos', 'Otros aparatos en desuso',
]
COLLECTION_POINT = 'Facultad de tecnología e innovación (Edificio A)'

@pytest.mark.parametrize('category', OFFICIAL_CATEGORIES)
def test_official_categories_persist(client, category):
    from app.models.models import Donation
    response = client.post('/api/donations', json={
        'alias': 'Campaña', 'category': category, 'quantity': 1, 'weight_kg': '0.125',
    })
    assert response.status_code == 201
    data = response.json()
    assert data['category'] == category
    assert json.loads(bytes.fromhex(data['payload_hex']))['category'] == category
    with SessionLocal() as db:
        assert db.get(Donation, data['ticket']).category.value == category

@pytest.mark.parametrize('category', [
    'Cables/Cargadores', 'Placas/Motherboards', 'Dispositivos pequeños', 'Baterías', 'Otros',
])
def test_previous_categories_rejected(client, category):
    assert client.post('/api/donations', json={
        'alias': 'Campaña', 'category': category, 'quantity': 1, 'weight_kg': '0.125',
    }).status_code == 422

def test_campaign_content_and_database_constraint(client):
    from html.parser import HTMLParser
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    class CategoryOptions(HTMLParser):
        def __init__(self):
            super().__init__()
            self.options = []
        def handle_starttag(self, tag, attrs):
            if tag == 'option':
                self.options.append(dict(attrs)['value'])

    parser = CategoryOptions()
    parser.feed(client.get('/registro').text)
    assert parser.options == OFFICIAL_CATEGORIES
    schema = client.get('/openapi.json').json()
    assert schema['components']['schemas']['Category']['enum'] == OFFICIAL_CATEGORIES
    for path in ['/', '/registro', '/dashboard', '/staff']:
        response = client.get(path, auth=AUTH)
        assert response.status_code == 200
        assert f'<meta name="collection-point" content="{COLLECTION_POINT}">' in response.text
        assert f'Punto de recolección: {COLLECTION_POINT}' in response.text
    # Raw SQL also has to obey the database constraint, bypassing Pydantic and ORM.
    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text("""INSERT INTO donations
                (id, alias, category, quantity, weight_kg, payload_hex, payload_binary, created_at)
                VALUES ('INVALID', 'Test', 'Baterías', 1, 0.1, '', '', CURRENT_TIMESTAMP)"""))
