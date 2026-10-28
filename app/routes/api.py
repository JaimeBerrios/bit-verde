import json
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO
import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.core.security import staff, same_origin
from app.models.models import Donation, TriviaSession, now
from app.schemas.schemas import Answers, DonationInput, Redemption
from app.services.trivia import questions

router = APIRouter(prefix="/api")

@router.post("/trivia/start", dependencies=[Depends(same_origin)])
def start(db: Session = Depends(get_db)):
    q = questions()
    session = TriviaSession(id=secrets.token_hex(24), questions=json.dumps(q))
    db.add(session)
    db.commit()
    return {"session_id": session.id, "questions": [{"prompt": x["prompt"], "options": x["options"]} for x in q], "passing_score": 3}

@router.post("/trivia/{session_id}/submit", dependencies=[Depends(same_origin)])
def submit(session_id: str, body: Answers, db: Session = Depends(get_db)):
    session = db.get(TriviaSession, session_id)
    if not session:
        raise HTTPException(404, "Ronda inexistente")
    if session.created_at.replace(tzinfo=timezone.utc) < now() - timedelta(minutes=20):
        raise HTTPException(410, "La ronda expiró; inicia otra")
    q = json.loads(session.questions)
    if any(answer < 0 or answer >= len(question["options"]) for answer, question in zip(body.answers, q)):
        raise HTTPException(422, "Respuesta fuera de rango")
    score = sum(a == x["correct"] for a, x in zip(body.answers, q))
    token = "#0x" + secrets.token_hex(8).upper() + "-BIT" if score == 3 else None
    changed = db.execute(update(TriviaSession).where(TriviaSession.id == session_id, TriviaSession.completed.is_(False)).values(completed=True, score=score, token=token))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Esta ronda ya fue respondida")
    db.commit()
    return {"score": score, "passed": score == 3, "token": token, "canjeado": False, "feedback": [x["explanation"] for x in q]}

@router.post("/donations", status_code=201, dependencies=[Depends(same_origin)])
def donate(body: DonationInput, db: Session = Depends(get_db)):
    record_id = secrets.token_hex(8).upper()
    payload = json.dumps({"id": record_id, **body.model_dump(mode="json")}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    donation = Donation(id=record_id, alias=body.alias, category=body.category.value, quantity=body.quantity, weight_kg=body.weight_kg, payload_hex=payload.hex().upper(), payload_binary=" ".join(f"{b:08b}" for b in payload))
    db.add(donation)
    db.commit()
    return {"ticket": record_id, **body.model_dump(mode="json"), "created_at": donation.created_at.isoformat(), "payload_hex": donation.payload_hex, "payload_binary": donation.payload_binary}

@router.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    totals = db.execute(select(func.count(Donation.id), func.coalesce(func.sum(Donation.quantity),0), func.coalesce(func.sum(Donation.weight_kg),0))).one()
    repaired = db.scalar(select(func.count()).select_from(TriviaSession).where(TriviaSession.score == 3))
    donations = db.scalars(select(Donation).order_by(Donation.created_at.desc()).limit(6)).all()
    return {"registrations": totals[0], "items": totals[1], "weight_kg": float(totals[2]), "repaired": repaired, "recent": [{"id": d.id, "hex": "0x"+d.id, "binary": f"{int(d.id,16):064b}"} for d in donations]}

@router.get("/qr.svg")
def qr():
    picture = qrcode.make(settings.public_url, image_factory=qrcode.image.svg.SvgPathImage, border=4)
    output = BytesIO()
    picture.save(output)
    return Response(output.getvalue(), media_type="image/svg+xml")

def normalized(token):
    return token.strip().upper().replace("#0X", "#0x")

@router.get("/staff/token", dependencies=[Depends(staff)])
def lookup(token: str, db: Session = Depends(get_db)):
    row = db.scalar(select(TriviaSession).where(TriviaSession.token == normalized(token)))
    if not row:
        raise HTTPException(404, "Token no encontrado")
    return {"token": row.token, "canjeado": row.redeemed}

@router.post("/staff/redeem", dependencies=[Depends(staff), Depends(same_origin)])
def redeem(body: Redemption, db: Session = Depends(get_db)):
    token = normalized(body.token)
    result = db.execute(update(TriviaSession).where(TriviaSession.token == token, TriviaSession.redeemed.is_(False)).values(redeemed=True, redeemed_at=now()))
    if result.rowcount != 1:
        db.rollback()
        exists = db.scalar(select(TriviaSession.id).where(TriviaSession.token == token))
        raise HTTPException(409 if exists else 404, "Token ya canjeado" if exists else "Token no encontrado")
    db.commit()
    return {"token": token, "canjeado": True}
