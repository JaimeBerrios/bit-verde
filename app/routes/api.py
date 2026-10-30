import json
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO
import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, Response, Header
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, update, func, union_all, literal
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.core.partners import ECO_TECH_URL
from app.core.security import staff, same_origin
from app.models.models import Donation, DonationRequest, TriviaSession, Reward, now
from app.schemas.schemas import Answers, DonationInput, Redemption, QuestionAnswer
from app.services.trivia import questions
from app.services.eco_tech import statistics as eco_tech_statistics

router = APIRouter(prefix="/api")

def active_session(db, session_id):
    session = db.get(TriviaSession, session_id)
    if not session:
        raise HTTPException(404, "Ronda inexistente")
    if session.created_at.replace(tzinfo=timezone.utc) < now() - timedelta(minutes=20):
        raise HTTPException(410, "La ronda expiró; inicia otra")
    return session


def new_reward(source, source_id):
    return Reward(token="#BIT-" + secrets.token_hex(8).upper(), source=source, source_id=source_id)


def trivia_result(session):
    return {"score": session.score, "passed": session.score == 3, "token": session.token,
            "canjeado": session.redeemed,
            "feedback": [x["explanation"] for x in json.loads(session.questions)]}


@router.post("/trivia/start", dependencies=[Depends(same_origin)])
def start(db: Session = Depends(get_db)):
    q = questions()
    session = TriviaSession(id=secrets.token_hex(24), questions=json.dumps(q))
    db.add(session)
    db.commit()
    return {"session_id": session.id,
            "questions": [{key: x.get(key, "") for key in ("prompt", "options", "hint")} for x in q],
            "passing_score": 3}


@router.post("/trivia/{session_id}/answer", dependencies=[Depends(same_origin)])
def check_answer(session_id: str, body: QuestionAnswer, db: Session = Depends(get_db)):
    session = active_session(db, session_id)
    question = json.loads(session.questions)[body.question_index]
    if body.answer >= len(question["options"]):
        raise HTTPException(422, "Respuesta fuera de rango")
    correct = body.answer == question["correct"]
    return {"correct": correct, "feedback": question["explanation"] if correct else
            "Prueba otra vez. " + question.get("hint", "Lee las opciones con calma.")}


@router.post("/trivia/{session_id}/submit", dependencies=[Depends(same_origin)])
def submit(session_id: str, body: Answers, db: Session = Depends(get_db)):
    session = active_session(db, session_id)
    q = json.loads(session.questions)
    if any(answer < 0 or answer >= len(question["options"]) for answer, question in zip(body.answers, q)):
        raise HTTPException(422, "Respuesta fuera de rango")
    if session.completed:
        # A lost response may be retried without minting another reward.
        return trivia_result(session)
    score = sum(a == x["correct"] for a, x in zip(body.answers, q))
    if score < 3:
        return {"score": score, "passed": False, "token": None, "canjeado": False,
                "feedback": [x["explanation"] for x in q]}
    reward = new_reward("trivia", session_id)
    changed = db.execute(update(TriviaSession).where(
        TriviaSession.id == session_id, TriviaSession.completed.is_(False)
    ).values(completed=True, score=score, token=reward.token))
    if changed.rowcount != 1:
        db.rollback()
        return trivia_result(db.get(TriviaSession, session_id))
    db.add(reward)
    db.commit()
    return trivia_result(db.get(TriviaSession, session_id))

@router.post("/donations", status_code=201, dependencies=[Depends(same_origin)])
def donate(body: DonationInput, db: Session = Depends(get_db),
           idempotency_key: str | None = Header(default=None, min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")):
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    def previous_result(request):
        if request.fingerprint != fingerprint:
            raise HTTPException(409, "Este intento corresponde a otra entrega. Recupera los datos originales antes de reintentar.")
        donation = db.get(Donation, request.donation_id)
        reward = db.scalar(select(Reward).where(Reward.source_id == donation.id))
        return donation_result(donation, reward)
    if idempotency_key:
        previous = db.get(DonationRequest, idempotency_key)
        if previous:
            return previous_result(previous)
    record_id = secrets.token_hex(8).upper()
    payload = json.dumps({"id": record_id, **body.model_dump(mode="json")}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    donation = Donation(id=record_id, alias=body.alias, category=body.category.value, quantity=body.quantity, weight_kg=body.weight_kg, payload_hex=payload.hex().upper(), payload_binary=" ".join(f"{b:08b}" for b in payload))
    reward = new_reward("donation", record_id)
    db.add_all([donation, reward])
    if idempotency_key:
        db.add(DonationRequest(key=idempotency_key, fingerprint=fingerprint, donation_id=record_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = db.get(DonationRequest, idempotency_key) if idempotency_key else None
        if previous:
            return previous_result(previous)
        raise
    return donation_result(donation, reward)


def donation_result(donation, reward):
    return {"ticket": donation.id, "token": reward.token, "canjeado": reward.redeemed,
            "alias": donation.alias, "category": donation.category, "quantity": donation.quantity,
            "weight_kg": str(donation.weight_kg), "created_at": donation.created_at.replace(tzinfo=timezone.utc).isoformat(),
            "payload_hex": donation.payload_hex, "payload_binary": donation.payload_binary}

@router.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    totals = db.execute(select(func.count(Donation.id), func.coalesce(func.sum(Donation.quantity),0), func.coalesce(func.sum(Donation.weight_kg),0))).one()
    repaired = db.scalar(select(func.count()).select_from(TriviaSession).where(TriviaSession.score == 3))
    donations = db.scalars(select(Donation).order_by(Donation.created_at.desc()).limit(6)).all()
    return {"registrations": totals[0], "items": totals[1], "weight_kg": float(totals[2]), "repaired": repaired, "recent": [{"id": d.id, "hex": "0x"+d.id, "binary": f"{int(d.id,16):064b}"} for d in donations]}

@router.get("/qr.svg")
def qr():
    return qr_response(settings.public_url)

@router.get("/eco-tech-qr.svg")
def eco_tech_qr():
    return qr_response(ECO_TECH_URL)

@router.get("/eco-tech/metrics")
def eco_tech_metrics():
    try:
        return eco_tech_statistics()
    except ValueError as error:
        raise HTTPException(503, str(error)) from error

def qr_response(url):
    picture = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=4)
    output = BytesIO()
    picture.save(output)
    return Response(output.getvalue(), media_type="image/svg+xml")

def normalized(token):
    return token.strip().upper().replace("#0X", "#0x")

@router.get("/staff/tokens", dependencies=[Depends(staff)])
def recent_tokens(db: Session = Depends(get_db)):
    # Include legacy trivia tokens without changing existing tables or records.
    current = select(Reward.token, Reward.source, Reward.created_at, Reward.redeemed)
    legacy = select(TriviaSession.token, literal("trivia").label("source"),
                    TriviaSession.created_at, TriviaSession.redeemed).where(
                        TriviaSession.token.is_not(None),
                        ~TriviaSession.token.in_(select(Reward.token)))
    recent = union_all(current, legacy).subquery()
    rows = db.execute(select(recent).order_by(recent.c.created_at.desc(), recent.c.token.desc()).limit(10)).mappings()
    return {"tokens": [{"token": row["token"], "source": row["source"],
                         "created_at": row["created_at"].replace(tzinfo=timezone.utc).isoformat(),
                         "canjeado": row["redeemed"]} for row in rows]}


@router.get("/staff/token", dependencies=[Depends(staff)])
def lookup(token: str, db: Session = Depends(get_db)):
    value = normalized(token)
    row = db.get(Reward, value) or db.scalar(select(TriviaSession).where(TriviaSession.token == value))
    if not row:
        raise HTTPException(404, "Token no encontrado")
    return {"token": row.token, "canjeado": row.redeemed}


@router.post("/staff/redeem", dependencies=[Depends(staff), Depends(same_origin)])
def redeem(body: Redemption, db: Session = Depends(get_db)):
    token = normalized(body.token)
    model = Reward if db.get(Reward, token) else TriviaSession
    redeemed_at = now()
    result = db.execute(update(model).where(model.token == token, model.redeemed.is_(False))
                        .values(redeemed=True, redeemed_at=redeemed_at))
    if result.rowcount != 1:
        db.rollback()
        exists = db.scalar(select(model.token).where(model.token == token))
        raise HTTPException(409 if exists else 404, "Token ya canjeado" if exists else "Token no encontrado")
    if model is Reward:
        db.execute(update(TriviaSession).where(TriviaSession.token == token)
                   .values(redeemed=True, redeemed_at=redeemed_at))
    db.commit()
    return {"token": token, "canjeado": True}
