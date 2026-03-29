# TruVerify

TruVerify is a blockchain-backed credential verification and AI recruiter-assist platform.

It combines:

- On-chain eSeal verification (SHA-256 hash against smart contract ledger)
- Resume-to-role fit scoring with PyTorch + SentenceTransformers
- Role-aware strategic signal extraction with spaCy
- Session-based auth pages (Sign Up, Sign In, Settings, Logout)

## Features

- Blockchain verification:
  Hashes uploaded PDF and verifies it against `TruVerifySeal` on-chain.
- AI fit scoring:
  Uses semantic matching and professional-signal analysis.
- Recruiter-style output:
  Returns candidate classification (for example, `Qualified and Verified`), credibility summary, strategic signals, and explainable checks.
- Noise suppression:
  Hobbies/extracurricular text cannot reduce professional fit score; culture-fit is additive only.
- Authenticated dashboard:
  Sign in to use the verification workspace.

## Project Structure

```text
contracts/
  TruVerifySeal.sol
ai/
  authenticity.py
  matcher.py
backend/
  abi/
    TruVerifySeal.json
  static/
    app.js
    auth.css
    styles.css
  templates/
    index.html
    signin.html
    signup.html
    settings.html
    logout.html
  main.py
scripts/
  deploy_local.py
  issue_sample_cert.py
sample_data/
requirements.txt
.env.example
```

## API Routes

- `POST /api/verify-and-match`
- `POST /verify` (compatibility alias; same logic as `/api/verify-and-match`)
- `GET /api/demo`
- `GET /api/health`

## Auth Routes

- `GET/POST /signup`
- `GET/POST /signin`
- `GET/POST /settings`
- `GET /logout`

## Local Setup

### 1) Create and Activate Virtual Environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 2) Install Dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure Environment

Create `.env` from `.env.example` and set values:

```env
RPC_URL=http://127.0.0.1:8545
CONTRACT_ADDRESS=0xYourContractAddress
APP_SECRET_KEY=replace-with-a-random-secret
```

### 4) Start Local Blockchain (Ganache)

```bash
npx ganache --server.port 8545 --wallet.mnemonic "test test test test test test test test test test test junk" --chain.chainId 31337
```

### 5) Deploy Contract Locally

```bash
python scripts/deploy_local.py
```

Copy printed `CONTRACT_ADDRESS=...` into `.env`.

### 6) (Optional) Issue Sample Certificate

```bash
python scripts/issue_sample_cert.py
```

### 7) Run App

Windows (Git Bash-safe command):

```bash
C:/Users/<your-user>/AppData/Local/Programs/Python/Python312/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

or generic command:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

Open:

- `http://127.0.0.1:8001/`

## End-to-End Flow

1. User signs in.
2. Upload PDF CV and provide Job Description.
3. Backend computes SHA-256 and verifies on blockchain.
4. If verified, backend extracts CV text and runs recruiter scoring.
5. UI shows AI match, strategic signals, and authenticity summary.

## Important Behavior Notes

- Blockchain verification confirms document hash integrity on ledger.
- It does not independently verify each claim against third-party issuers unless an issuer workflow is integrated.
- Current app includes demo-friendly auto-seal behavior in backend verification flow; disable it for strict production enforcement.

## Production Recommendations

- Restrict certificate issuance to authorized issuer roles.
- Disable auto-seal in verify flow.
- Rotate strong `APP_SECRET_KEY` and issuer private keys.
- Add tests for `ai/matcher.py` and `ai/authenticity.py` scoring behavior.
