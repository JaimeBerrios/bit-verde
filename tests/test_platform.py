import os
from concurrent.futures import ThreadPoolExecutor
import json

os.environ['DATABASE_URL'] = 'sqlite:////tmp/bitverde-tests.db'
os.environ['STAFF_PASSWORD'] = 'test-only-password-123'
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.models.models import TriviaSession, Reward
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
    assert result['passed'] and result['token'].startswith('#BIT-')
    assert not result['canjeado']
    assert client.post('/api/trivia/'+start['session_id']+'/submit',json={'answers':answers}).json()['token'] == result['token']
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


def test_easy_questions_and_immediate_retry(client):
    start = client.post('/api/trivia/start', json={}).json()
    session = start['session_id']
    q = start['questions']
    assert len(q) == 3 and all('correct' not in item for item in q)
    assert 'laptop' in q[0]['prompt'] and 'AND' in q[0]['hint']
    assert 'celular' in q[1]['prompt'] and 'OR' in q[1]['hint']
    assert q[0]['options'] == ['1 - Enciende ✅', '0 - Apagado']
    assert q[1]['options'] == ['1 - Sí recibe carga ✅', '0 - No carga']
    for i in range(3):
        wrong = client.post(f'/api/trivia/{session}/answer', json={'question_index':i, 'answer':1})
        assert wrong.status_code == 200 and not wrong.json()['correct']
        assert 'Prueba otra vez' in wrong.json()['feedback']
        correct = client.post(f'/api/trivia/{session}/answer', json={'question_index':i, 'answer':0})
        assert correct.status_code == 200 and correct.json()['correct']
    with SessionLocal() as db:
        assert not db.get(TriviaSession, session).completed
        assert db.scalar(select(Reward.token)) is None
    failed = client.post(f'/api/trivia/{session}/submit', json={'answers':[1,0,0]}).json()
    assert not failed['passed'] and failed['token'] is None
    won = client.post(f'/api/trivia/{session}/submit', json={'answers':[0,0,0]}).json()
    assert won['passed'] and won['score'] == 3
    assert client.get('/api/metrics').json()['repaired'] == 1


def test_answer_validation_and_expiration(client):
    session = client.post('/api/trivia/start', json={}).json()['session_id']
    for body in [{'question_index':-1,'answer':0}, {'question_index':3,'answer':0},
                 {'question_index':0,'answer':2}, {'question_index':0,'answer':True},
                 {'question_index':False,'answer':0}]:
        assert client.post(f'/api/trivia/{session}/answer',json=body).status_code == 422
    assert client.post('/api/trivia/missing/answer',json={'question_index':0,'answer':0}).status_code == 404
    from datetime import timedelta
    with SessionLocal() as db:
        db.get(TriviaSession, session).created_at -= timedelta(minutes=21)
        db.commit()
    assert client.post(f'/api/trivia/{session}/answer',json={'question_index':0,'answer':0}).status_code == 410


def test_concurrent_submit_issues_one_reward(client):
    session = client.post('/api/trivia/start',json={}).json()['session_id']
    def finish(_):
        response = client.post(f'/api/trivia/{session}/submit', json={'answers':[0,0,0]})
        assert response.status_code == 200
        return response.json()['token']
    with ThreadPoolExecutor(max_workers=2) as executor:
        tokens = list(executor.map(finish, range(2)))
    assert tokens[0] == tokens[1]
    with SessionLocal() as db:
        assert len(db.scalars(select(Reward)).all()) == 1
    assert client.get('/api/metrics').json()['repaired'] == 1


def test_donation_reward_is_redeemable_without_inflating_repairs(client):
    result = client.post('/api/donations',json={
        'alias':'Visitante', 'category':'Celulares','quantity':1,'weight_kg':'0.2',
    }).json()
    token = result['token']
    assert token.startswith('#BIT-') and not result['canjeado']
    assert client.get('/api/staff/token',params={'token':token.lower()},auth=AUTH).json()['token'] == token
    assert client.get('/api/metrics').json()['repaired'] == 0
    def redeem(_):
        return client.post('/api/staff/redeem',json={'token':token},auth=AUTH).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(redeem,range(2))) == [200,409]
    assert client.get('/api/staff/token',params={'token':token},auth=AUTH).json()['canjeado']


def test_recent_ten_tokens_are_private_ordered_and_refreshable(client):
    from datetime import timedelta
    assert client.get('/api/staff/tokens').status_code == 401
    assert client.get('/api/staff/tokens',auth=('staff','wrong')).status_code == 401
    assert client.get('/api/staff/tokens',auth=AUTH).json() == {'tokens':[]}
    issued = []
    for i in range(12):
        _, _, result = complete(client)
        issued.append(result['token'])
    donation = client.post('/api/donations',json={
        'alias':'Alias privado','category':'Cables','quantity':1,'weight_kg':'0',
    }).json()
    issued.append(donation['token'])
    # The session start is not the prize generation time.
    with SessionLocal() as db:
        db.get(Reward, issued[0]).created_at += timedelta(days=1)
        db.commit()
    response = client.get('/api/staff/tokens',auth=AUTH)
    assert response.headers['cache-control'] == 'no-store'
    rows = response.json()['tokens']
    assert len(rows) == 10 and rows[0]['token'] == issued[0]
    assert rows[1]['token'] == issued[-1] and rows[1]['source'] == 'donation'
    assert 'Alias privado' not in response.text and 'source_id' not in response.text
    assert client.post('/api/staff/redeem',json={'token':rows[0]['token']},auth=AUTH).status_code == 200
    assert client.get('/api/staff/tokens',auth=AUTH).json()['tokens'][0]['canjeado']
    public = client.get('/api/metrics').text
    assert all(token not in public for token in issued)


def test_legacy_tokens_remain_usable(client):
    from app.models.models import now
    legacy = '#0xABCD1234-BIT'
    with SessionLocal() as db:
        db.add(TriviaSession(id='legacy', questions='[]', completed=True, score=3,
                             token=legacy, created_at=now()))
        db.commit()
    assert client.get('/api/staff/tokens',auth=AUTH).json()['tokens'][0]['token'] == legacy
    assert client.get('/api/staff/token',params={'token':legacy},auth=AUTH).status_code == 200
    assert client.post('/api/staff/redeem',json={'token':legacy},auth=AUTH).status_code == 200
    assert client.post('/api/staff/redeem',json={'token':legacy},auth=AUTH).status_code == 409


def test_new_ticket_and_staff_ui_templates(client):
    page = client.get('/').text
    assert 'game-progress' in page and 'menos de 45 segundos' in page
    assert 'game-message' in page
    staff_page = client.get('/staff',auth=AUTH).text
    assert 'Últimos 10 tokens' in staff_page and 'recent-tokens' in staff_page
    script = client.get('/static/js/app.js').text
    assert 'Copiar Token' in script and 'Jugar de nuevo' in script
    assert '¡Circuito Optimizado!' in script
    assert 'Pasa por tu Bus de Datos Saludable 🍓🍇' in script
