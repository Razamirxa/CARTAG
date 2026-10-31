from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from cartag.db import get_db
from cartag.deps import (
    ip_hash,
    limit_activate,
    limit_otp,
    require_user,
    session_token,
    sms_dep,
    tag_code_param,
)
from cartag.models import User
from cartag.routers.auth import public_user
from cartag.schemas import (
    ActivateTagIn,
    ContactCardIn,
    DeleteAccountIn,
    PhoneChangeConfirmIn,
    PhoneChangeRequestIn,
    UpdateProfileIn,
)
from cartag.services import account as account_service
from cartag.services.audit import Actor, audit
from cartag.services.cards import card_view, upsert_card
from cartag.services.sms import SmsProvider
from cartag.services.tags import activate_tag, get_owned_tag, list_owned_tags, owner_tag_view, set_owned_tag_on

router = APIRouter(prefix="/me", tags=["owner"], dependencies=[Depends(require_user)])


@router.patch("")
def update_profile(body: UpdateProfileIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    user.name = body.name
    audit(db, Actor.user(user.id), "user.update_profile", "User", user.id)
    db.commit()
    return {"user": public_user(user)}


# ---------- contact card ----------
@router.get("/card")
def get_card(user: User = Depends(require_user)):
    return {"card": card_view(user.card)}


@router.put("/card")
def put_card(body: ContactCardIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    card = upsert_card(db, user, body)
    db.commit()
    return {"card": card_view(card)}


# ---------- tags ----------
@router.get("/tags")
def my_tags(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return {"tags": [owner_tag_view(t) for t in list_owned_tags(db, user.id)]}


@router.post("/activation/otp", dependencies=[Depends(limit_otp)])
def activation_otp(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    sms: SmsProvider = Depends(sms_dep),
):
    """Texts a one-time code to the owner's mobile number. They enter it to turn a tag on."""
    resend = account_service.send_activation_code(db, user, ip_hash(request), sms)
    return {"ok": True, "resendAfterSeconds": resend}


# Registered before "/tags/{code}" so "activate" is never read as a code.
@router.post("/tags/activate", status_code=201, dependencies=[Depends(limit_activate)])
def activate(body: ActivateTagIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return {"tag": owner_tag_view(activate_tag(db, user, body))}


@router.get("/tags/{code}")
def my_tag(code: str = Depends(tag_code_param), user: User = Depends(require_user), db: Session = Depends(get_db)):
    return {"tag": owner_tag_view(get_owned_tag(db, user.id, code))}


@router.post("/tags/{code}/turn-off")
def turn_off(code: str = Depends(tag_code_param), user: User = Depends(require_user), db: Session = Depends(get_db)):
    return {"tag": owner_tag_view(set_owned_tag_on(db, user, code, False))}


@router.post("/tags/{code}/turn-on")
def turn_on(code: str = Depends(tag_code_param), user: User = Depends(require_user), db: Session = Depends(get_db)):
    return {"tag": owner_tag_view(set_owned_tag_on(db, user, code, True))}


# ---------- mobile number ----------
@router.post("/phone/change/request", dependencies=[Depends(limit_otp)])
def phone_change_request(
    body: PhoneChangeRequestIn,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    sms: SmsProvider = Depends(sms_dep),
):
    resend = account_service.start_phone_change(db, user, body.phone, body.password, ip_hash(request), sms)
    return {"ok": True, "resendAfterSeconds": resend}


@router.post("/phone/change/confirm")
def phone_change_confirm(
    body: PhoneChangeConfirmIn,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    account_service.confirm_phone_change(db, user, body.phone, body.otp, session_token(request))
    return {"user": public_user(user)}


# ---------- closing the account ----------
@router.get("/delete-request")
def get_delete_request(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return {"request": account_service.deletion_view(account_service.pending_deletion(db, user))}


@router.post("/delete-request", status_code=201)
def post_delete_request(body: DeleteAccountIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    request = account_service.request_deletion(db, user, body.password, body.reason)
    return {"request": account_service.deletion_view(request)}
