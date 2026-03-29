from pathlib import Path

from solcx import compile_source, install_solc
from web3 import Web3

SOLC_VERSION = "0.8.24"
RPC_URL = "http://127.0.0.1:8545"
PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def main() -> None:
    contract_path = Path(__file__).resolve().parents[1] / "contracts" / "TruVerifySeal.sol"
    source = contract_path.read_text(encoding="utf-8")

    install_solc(SOLC_VERSION)
    compiled = compile_source(
        source,
        output_values=["abi", "bin"],
        solc_version=SOLC_VERSION,
    )

    _, contract_interface = compiled.popitem()
    abi = contract_interface["abi"]
    bytecode = contract_interface["bin"]

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise RuntimeError(f"Unable to connect to RPC at {RPC_URL}")

    account = w3.eth.account.from_key(PRIVATE_KEY)
    nonce = w3.eth.get_transaction_count(account.address)

    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = contract.constructor().build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
            "gas": 2_500_000,
            "gasPrice": w3.eth.gas_price,
        }
    )

    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print(f"CONTRACT_ADDRESS={receipt.contractAddress}")


if __name__ == "__main__":
    main()
