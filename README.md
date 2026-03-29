# TruVerify

TruVerify is a decentralized credential verification and AI semantic matching system.

## What this includes

- **eSeal Layer (Blockchain):** Solidity contract that stores immutable SHA-256 certificate hashes with issuer, student wallet, and UTC timestamp.
- **Match Engine (AI):** Python module using `SentenceTransformer` (`all-mpnet-base-v2`) and PyTorch cosine similarity.
- **Integration Layer:** FastAPI app that uploads a PDF CV, computes SHA-256, verifies the eSeal on-chain via Web3.py, then computes AI match score against a job description.
- **Frontend:** Modern, responsive UI served by FastAPI.

## Project Structure

```text
contracts/
  TruVerifySeal.sol
ai/
  matcher.py
backend/
  abi/TruVerifySeal.json
  static/
    app.js
    styles.css
  templates/
    index.html
  main.py
.env.example
requirements.txt
```

## 1) Deploy the Smart Contract

You can deploy `contracts/TruVerifySeal.sol` to any EVM testnet (e.g., Sepolia) using Remix or Hardhat.

Contract features:

- `issueCertificate(bytes32 certificateHash, address studentWallet)`
- `verifyCertificate(bytes32 certificateHash)`
- Unique+immutable hash enforcement through mapping + existence guard.

After deployment, copy the contract address.

## 2) Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
RPC_URL=https://your-rpc-url
CONTRACT_ADDRESS=0xYourDeployedContractAddress
```

## 3) Install Dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 4) Run the API + Frontend

From project root:

```bash
uvicorn backend.main:app --reload
```

Open:

- `http://127.0.0.1:8000/`

## 5) End-to-End Flow

1. Upload a PDF CV.
2. API computes SHA-256 hash.
3. API calls smart contract `verifyCertificate` with hash.
4. If verified, API extracts text and computes CV↔JD semantic match.
5. UI displays verification result and score.

## Example: Certificate Hash Input to Contract

If your backend computed:

```text
4d8f...ab12  (64 hex chars)
```

It is sent on-chain as:

```text
0x4d8f...ab12
```

which maps to `bytes32` in Solidity.

## Notes

- For production, add authentication and role management for issuer APIs.
- Consider storing certificate metadata in IPFS and anchoring CID hash on-chain.
- Large transformer models can be memory-intensive; use a worker queue for high throughput.
