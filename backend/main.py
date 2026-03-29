from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import secrets
from urllib.parse import quote_plus
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pypdf import PdfReader
from pydantic import BaseModel
from starlette.requests import Request
from web3 import Web3

from ai.authenticity import analyze_resume_authenticity
from ai.matcher import compute_match_score

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ABI_PATH = BASE_DIR / "abi" / "TruVerifySeal.json"

RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret-change-me")
AUTH_DB_PATH = BASE_DIR / "auth.db"

app = FastAPI(title="TruVerify API", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.add_middleware(SessionMiddleware, secret_key=APP_SECRET_KEY, max_age=60 * 60 * 24 * 7)


class VerificationResult(BaseModel):
    certificate_hash: str
    is_verified: bool
    issuer: str | None
    student_wallet: str | None
    issued_at_utc: str | None
    match_score_percent: float | None
    content_authenticity: dict[str, object] | None = None


def _db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_auth_db() -> None:
    with _db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def _hash_password(password: str, salt: str | None = None) -> str:
    real_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), real_salt.encode("utf-8"), 310000)
    return f"{real_salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    candidate = _hash_password(password, salt)
    return secrets.compare_digest(candidate, stored)


def _create_user(full_name: str, email: str, password: str) -> tuple[bool, str]:
    normalized_email = email.strip().lower()
    now_utc = datetime.now(timezone.utc).isoformat()
    password_hash = _hash_password(password)

    try:
        with _db_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (full_name, email, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (full_name.strip(), normalized_email, password_hash, now_utc, now_utc),
            )
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."


def _authenticate_user(email: str, password: str) -> sqlite3.Row | None:
    normalized_email = email.strip().lower()
    with _db_connection() as conn:
        row = conn.execute(
            "SELECT id, full_name, email, password_hash FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()
    if not row:
        return None
    if not _verify_password(password, row["password_hash"]):
        return None
    return row


def _current_user(request: Request) -> dict[str, object] | None:
    user = request.session.get("user")
    if not user:
        return None
    return {"id": int(user.get("id", 0)), "full_name": str(user.get("full_name", "")), "email": str(user.get("email", ""))}


def _require_user(request: Request) -> dict[str, object] | None:
    user = _current_user(request)
    if not user or not user.get("id"):
        return None
    return user


def _redirect(path: str, message: str | None = None) -> RedirectResponse:
    if message:
        return RedirectResponse(url=f"{path}?message={quote_plus(message)}", status_code=303)
    return RedirectResponse(url=path, status_code=303)


_init_auth_db()


def _extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    text_parts = []
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts).strip()


def _load_contract() -> tuple[Web3, object]:
    if not CONTRACT_ADDRESS:
        raise HTTPException(
            status_code=500,
            detail="CONTRACT_ADDRESS is not configured in environment.",
        )

    with ABI_PATH.open("r", encoding="utf-8") as f:
        abi = json.load(f)

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise HTTPException(
            status_code=500,
            detail=f"Unable to connect to RPC endpoint: {RPC_URL}",
        )

    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Contract initialization failed: {exc}") from exc

    return w3, contract


def _auto_seal_certificate(w3: Web3, contract: object, cert_hash_hex: str) -> None:
    """Auto-seal a certificate on-chain if not already sealed (demo mode)."""
    # Demo accounts (Ganache default)
    issuer_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    student_wallet = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"

    try:
        account = w3.eth.account.from_key(issuer_key)
        nonce = w3.eth.get_transaction_count(account.address)

        tx = contract.functions.issueCertificate(
            Web3.to_bytes(hexstr="0x" + cert_hash_hex),
            Web3.to_checksum_address(student_wallet),
        ).build_transaction(
            {
                "from": account.address,
                "nonce": nonce,
                "chainId": w3.eth.chain_id,
                "gas": 250000,
                "gasPrice": w3.eth.gas_price,
            }
        )

        signed = w3.eth.account.sign_transaction(tx, issuer_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)
    except Exception:
        # If sealing fails, continue anyway (might already exist)
        pass


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = _require_user(request)
    if not user:
        return _redirect("/signin", "Please sign in to continue.")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    if _current_user(request):
        return _redirect("/")
    return templates.TemplateResponse(
        "signup.html",
        {
            "request": request,
            "error": request.query_params.get("error", ""),
            "message": request.query_params.get("message", ""),
        },
    )


@app.post("/signup")
async def signup_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    if len(password) < 8:
        return _redirect("/signup", "Password must be at least 8 characters.")
    if password != confirm_password:
        return _redirect("/signup", "Passwords do not match.")

    ok, message = _create_user(full_name=full_name, email=email, password=password)
    if not ok:
        return _redirect("/signup", message)
    return _redirect("/signin", "Account created. Please sign in.")


@app.get("/signin", response_class=HTMLResponse)
def signin_page(request: Request):
    if _current_user(request):
        return _redirect("/")
    return templates.TemplateResponse(
        "signin.html",
        {
            "request": request,
            "error": request.query_params.get("error", ""),
            "message": request.query_params.get("message", ""),
        },
    )


@app.post("/signin")
async def signin_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    user = _authenticate_user(email=email, password=password)
    if not user:
        return _redirect("/signin", "Invalid email or password.")

    request.session["user"] = {
        "id": int(user["id"]),
        "full_name": str(user["full_name"]),
        "email": str(user["email"]),
    }
    return _redirect("/")


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    user = _require_user(request)
    if not user:
        return _redirect("/signin", "Please sign in to access settings.")

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "error": request.query_params.get("error", ""),
            "message": request.query_params.get("message", ""),
        },
    )


@app.post("/settings")
async def settings_submit(
    request: Request,
    full_name: str = Form(...),
    current_password: str = Form(""),
    new_password: str = Form(""),
    confirm_new_password: str = Form(""),
):
    user = _require_user(request)
    if not user:
        return _redirect("/signin", "Please sign in to access settings.")

    with _db_connection() as conn:
        db_user = conn.execute(
            "SELECT id, full_name, email, password_hash FROM users WHERE id = ?",
            (int(user["id"]),),
        ).fetchone()

    if not db_user:
        request.session.clear()
        return _redirect("/signin", "Session expired. Please sign in again.")

    update_password = bool(new_password.strip() or confirm_new_password.strip() or current_password.strip())
    password_hash = db_user["password_hash"]

    if update_password:
        if not _verify_password(current_password, db_user["password_hash"]):
            return _redirect("/settings", "Current password is incorrect.")
        if len(new_password) < 8:
            return _redirect("/settings", "New password must be at least 8 characters.")
        if new_password != confirm_new_password:
            return _redirect("/settings", "New passwords do not match.")
        password_hash = _hash_password(new_password)

    cleaned_name = full_name.strip()
    if not cleaned_name:
        return _redirect("/settings", "Full name cannot be empty.")

    now_utc = datetime.now(timezone.utc).isoformat()
    with _db_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET full_name = ?, password_hash = ?, updated_at = ?
            WHERE id = ?
            """,
            (cleaned_name, password_hash, now_utc, int(user["id"])),
        )

    request.session["user"] = {
        "id": int(db_user["id"]),
        "full_name": cleaned_name,
        "email": str(db_user["email"]),
    }
    return _redirect("/settings", "Settings updated successfully.")


@app.get("/logout", response_class=HTMLResponse)
def logout(request: Request):
    request.session.clear()
    return templates.TemplateResponse("logout.html", {"request": request})


@app.post("/api/verify-and-match", response_model=VerificationResult)
async def verify_and_match(
    cv_file: UploadFile = File(...),
    job_description: str = Form(...),
):
    if cv_file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported.")

    file_bytes = await cv_file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    certificate_hash = hashlib.sha256(file_bytes).hexdigest()
    cert_hash_bytes32 = "0x" + certificate_hash

    w3, contract = _load_contract()
    is_verified, issuer, student_wallet, issued_at = contract.functions.verifyCertificate(
        cert_hash_bytes32
    ).call()

    # Auto-seal if not found (demo mode)
    if not is_verified:
        _auto_seal_certificate(w3, contract, certificate_hash)
        # Re-verify after sealing
        is_verified, issuer, student_wallet, issued_at = contract.functions.verifyCertificate(
            cert_hash_bytes32
        ).call()

    if not is_verified:
        return VerificationResult(
            certificate_hash=certificate_hash,
            is_verified=False,
            issuer=None,
            student_wallet=None,
            issued_at_utc=None,
            match_score_percent=None,
            content_authenticity=None,
        )

    cv_text = _extract_pdf_text(file_bytes)
    if not cv_text:
        raise HTTPException(
            status_code=400,
            detail="Unable to extract text from PDF. Please upload a text-based PDF.",
        )

    score_data = compute_match_score(cv_text, job_description)
    authenticity_data = analyze_resume_authenticity(cv_text)

    issued_dt = datetime.fromtimestamp(issued_at, tz=timezone.utc)

    return VerificationResult(
        certificate_hash=certificate_hash,
        is_verified=True,
        issuer=issuer,
        student_wallet=student_wallet,
        issued_at_utc=issued_dt.isoformat(),
        match_score_percent=score_data["score_percent"],
        content_authenticity=authenticity_data,
    )


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "TruVerify API"}


@app.get("/api/demo", response_model=VerificationResult)
def demo() -> VerificationResult:
    """Returns a pre-computed demo verification result for quick showcasing."""
    return VerificationResult(
        certificate_hash="1ef47f984d8bb5d86ee7bf426c0451ff8f82e3068f61d8cd5a68af9e8a61e864",
        is_verified=True,
        issuer="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        student_wallet="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        issued_at_utc="2026-03-29T11:16:57+00:00",
        match_score_percent=79.78,
        content_authenticity={
            "score_percent": 86.0,
            "risk_level": "low",
            "summary": "Strong authenticity signals with consistent timeline and concrete evidence.",
            "red_flag_count": 0,
            "checks": [
                {
                    "name": "Year Consistency",
                    "status": "pass",
                    "details": "Timeline years look plausible.",
                },
                {
                    "name": "Core Sections",
                    "status": "pass",
                    "details": "Education and experience sections are present.",
                },
                {
                    "name": "Project Evidence",
                    "status": "pass",
                    "details": "Projects include technical/actionable details.",
                },
            ],
        },
    )
