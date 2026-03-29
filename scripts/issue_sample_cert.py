import hashlib
import json
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from web3 import Web3

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "sample_data" / "sample_cv.pdf"
ABI_PATH = ROOT / "backend" / "abi" / "TruVerifySeal.json"

RPC_URL = "http://127.0.0.1:8545"
CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
ISSUER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
STUDENT_WALLET = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"


def create_sample_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 740, "Rashi Kumar - Verified CV")
    c.drawString(72, 720, "Skills: Python, FastAPI, Solidity, Web3, NLP, PyTorch")
    c.drawString(72, 700, "Experience: Built decentralized credential verification systems")
    c.drawString(72, 680, "Education: B.Tech in Computer Science")
    c.save()


def main() -> None:
    create_sample_pdf(PDF_PATH)
    pdf_bytes = PDF_PATH.read_bytes()
    cert_hash = hashlib.sha256(pdf_bytes).hexdigest()

    abi = json.loads(ABI_PATH.read_text(encoding="utf-8"))

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise RuntimeError("RPC not reachable")

    account = w3.eth.account.from_key(ISSUER_KEY)
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)

    nonce = w3.eth.get_transaction_count(account.address)
    tx = contract.functions.issueCertificate(
        Web3.to_bytes(hexstr="0x" + cert_hash),
        Web3.to_checksum_address(STUDENT_WALLET),
    ).build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
            "gas": 250000,
            "gasPrice": w3.eth.gas_price,
        }
    )

    signed = w3.eth.account.sign_transaction(tx, ISSUER_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print(f"PDF_PATH={PDF_PATH}")
    print(f"CERT_HASH={cert_hash}")
    print(f"TX_HASH={receipt.transactionHash.hex()}")


if __name__ == "__main__":
    main()
