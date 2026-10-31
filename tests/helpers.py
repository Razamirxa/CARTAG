import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from cartag.db import SessionLocal
from cartag.main import create_app
from cartag.models import Admin, OtpChallenge, Tag
from cartag.security import hash_password

PASSWORD = "correct horse battery"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin-password-1"

CARD = {"displayName": "Ali Raza"}
EMERGENCY_CARD = {
    "displayName": "Ali Raza",
    "emergencyEnabled": True,
    "bloodGroup": "O+",
    "emergencyName": "Sara Khan",
    "emergencyRelationship": "Wife",
    "emergencyPhone": "0345 7654321",
}


@dataclass
class MemorySms:
    messages: list[tuple[str, str]] = field(default_factory=list)

    def send(self, to_e164: str, message: str) -> None:
        self.messages.append((to_e164, message))

    def last_code(self, to: str) -> str:
        """The six-digit code from the most recent message sent to a number."""
        for number, message in reversed(self.messages):
            if number == to:
                found = re.search(r"\b(\d{6})\b", message)
                if found:
                    return found.group(1)
        raise AssertionError(f"No SMS code was sent to {to}")


def make_app(rate_limits: bool = False):
    sms = MemorySms()
    return create_app(sms=sms, enable_ip_rate_limits=rate_limits), sms


def client_for(app) -> TestClient:
    """A client with its own cookie jar, like one browser."""
    return TestClient(app)


def register_owner(app, sms: MemorySms, phone_input: str = "0300 1234567", name: str = "Ali Raza"):
    """Registers an owner through the real API. Returns (client holding the session, E.164 phone)."""
    client = client_for(app)
    registered = client.post("/api/auth/register", json={"phone": phone_input, "name": name, "password": PASSWORD})
    assert registered.status_code == 201, registered.text
    return client, registered.json()["user"]["phone"]


def create_admin(email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> Admin:
    with SessionLocal() as db:
        admin = Admin(email=email, name="Test Admin", password_hash=hash_password(password))
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin


def admin_client(app, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> TestClient:
    with SessionLocal() as db:
        exists = db.scalar(select(Admin).where(Admin.email == email))
    if exists is None:
        create_admin(email, password)
    client = client_for(app)
    res = client.post("/api/admin/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return client


def generate_batch(admin: TestClient, quantity: int, name: str = "Test batch"):
    """Generates a batch through the API. Returns (batch id, codes in serial order)."""
    res = admin.post("/api/admin/batches/generate", json={"name": name, "quantity": quantity})
    assert res.status_code == 201, res.text
    batch_id = res.json()["batch"]["id"]
    with SessionLocal() as db:
        codes = list(db.scalars(select(Tag.code).where(Tag.batch_id == batch_id).order_by(Tag.serial)))
    return batch_id, codes


def sell_batch(admin: TestClient, batch_id: str) -> int:
    """Marks every tag in the batch as sold, like a seller handing the stock over."""
    res = admin.post(f"/api/admin/batches/{batch_id}/mark-sold")
    assert res.status_code == 200, res.text
    return res.json()["changed"]


def skip_cooldown() -> None:
    """Pretends the earlier one-time codes were requested two hours ago, so the resend delay and hourly cap reset."""
    with SessionLocal() as db:
        db.execute(update(OtpChallenge).values(created_at=datetime.now(UTC) - timedelta(hours=2)))
        db.commit()


def activate(owner: TestClient, sms: MemorySms, phone: str, code: str, card: dict | None = CARD):
    """Runs the whole activation: asks for a code, reads it from the text message, turns the tag on."""
    skip_cooldown()
    sent = owner.post("/api/me/activation/otp")
    assert sent.status_code == 200, sent.text
    body = {"code": code, "otp": sms.last_code(phone)}
    if card is not None:
        body["card"] = card
    return owner.post("/api/me/tags/activate", json=body)
