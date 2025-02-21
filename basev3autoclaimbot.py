import os
import requests
import time  # Added for delay functionality
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

# Load environment variables from .env file
load_dotenv()

# Connect to the Base Network using Alchemy
alchemy_base_url = f"https://base-mainnet.g.alchemy.com/v2/{os.getenv('ALCHEMY_API_KEY')}"
web3 = Web3(Web3.HTTPProvider(alchemy_base_url))
assert web3.is_connected(), "Failed to connect to the Base network."

# Set up your account
private_key = os.getenv("PRIVATE_KEY")
account = Account.from_key(private_key)

# Target wallet address
target_address = os.getenv("TARGET_WALLET_ADDRESS")

# Configurable claim threshold
CLAIM_THRESHOLD_USD = float(os.getenv("CLAIM_THRESHOLD", 1.00))  # Default is $1.00

# Uniswap V3 Position Manager Contract Address for Base
nft_position_manager_address = "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1"
nft_position_manager_abi = [
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "uint256", "name": "index", "type": "uint256"}
        ],
        "name": "tokenOfOwnerByIndex",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"}
        ],
        "name": "positions",
        "outputs": [
            {"internalType": "uint96", "name": "nonce", "type": "uint96"},
            {"internalType": "address", "name": "operator", "type": "address"},
            {"internalType": "address", "name": "token0", "type": "address"},
            {"internalType": "address", "name": "token1", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
            {"internalType": "int24", "name": "tickLower", "type": "int24"},
            {"internalType": "int24", "name": "tickUpper", "type": "int24"},
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "uint256", "name": "feeGrowthInside0LastX128", "type": "uint256"},
            {"internalType": "uint256", "name": "feeGrowthInside1LastX128", "type": "uint256"},
            {"internalType": "uint128", "name": "tokensOwed0", "type": "uint128"},
            {"internalType": "uint128", "name": "tokensOwed1", "type": "uint128"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint128", "name": "amount0Max", "type": "uint128"},
                    {"internalType": "uint128", "name": "amount1Max", "type": "uint128"}
                ],
                "internalType": "struct INonfungiblePositionManager.CollectParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "collect",
        "outputs": [
            {"internalType": "uint256", "name": "amount0", "type": "uint256"},
            {"internalType": "uint256", "name": "amount1", "type": "uint256"}
        ],
        "stateMutability": "payable",
        "type": "function"
    }
]

nft_position_manager_contract = web3.eth.contract(
    address=nft_position_manager_address,
    abi=nft_position_manager_abi
)

# Map token symbols to CoinGecko IDs
symbol_to_coingecko_id = {
    "WETH": "weth",
    "USDC": "usd-coin",
    # Add other mappings as needed
}

# Helper function to get token decimals and symbol
def get_token_decimals_and_symbol(token_address):
    try:
        token_contract = web3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=[
                {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"},
                {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
            ]
        )
        decimals = token_contract.functions.decimals().call()
        symbol = token_contract.functions.symbol().call()
        return decimals, symbol
    except Exception as e:
        print(f"Error fetching data for token {token_address}: {e}")
        return 18, "Unknown"  # Default to 18 decimals and "Unknown" if the call fails

# Helper function to get token USD value by CoinGecko ID
def get_token_price_usd_by_id(coin_id):
    try:
        response = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd"}
        )
        if response.status_code == 200:
            data = response.json()
            return data[coin_id]["usd"]
    except Exception as e:
        print(f"Error fetching price for CoinGecko ID {coin_id}: {e}")
    return 0.0  # Default to $0.00 if the call fails

# Main logic to fetch NFTs and simulate claims
def run_script():
    print("Fetching NFTs and simulating claims...")
    token_ids = []
    try:
        index = 0
        while True:
            token_id = nft_position_manager_contract.functions.tokenOfOwnerByIndex(target_address, index).call()
            token_ids.append(token_id)
            index += 1
    except Exception as e:
        print(f"Completed fetching token IDs: {token_ids} ({len(token_ids)} NFTs found).")

    for token_id in token_ids:
        try:
            position_info = nft_position_manager_contract.functions.positions(token_id).call()
            liquidity = position_info[7]

            if liquidity == 0:
                print(f"Token ID {token_id} is inactive. Skipping...")
                continue

            token0_address = position_info[2]
            token1_address = position_info[3]
            decimals0, symbol0 = get_token_decimals_and_symbol(token0_address)
            decimals1, symbol1 = get_token_decimals_and_symbol(token1_address)

            coin_id0 = symbol_to_coingecko_id.get(symbol0, "unknown")
            coin_id1 = symbol_to_coingecko_id.get(symbol1, "unknown")
            price0 = get_token_price_usd_by_id(coin_id0)
            price1 = get_token_price_usd_by_id(coin_id1)

            print(f"Simulating collect for Token ID {token_id}...")
            collect_result = nft_position_manager_contract.functions.collect({
                "tokenId": token_id,
                "recipient": target_address,
                "amount0Max": 2**128 - 1,
                "amount1Max": 2**128 - 1
            }).call({"from": account.address})

            amount0, amount1 = collect_result
            formatted_amount0 = f"{amount0 / (10 ** decimals0):,.6f}"
            formatted_amount1 = f"{amount1 / (10 ** decimals1):,.6f}"
            usd_value0 = price0 * (amount0 / (10 ** decimals0))
            usd_value1 = price1 * (amount1 / (10 ** decimals1))

            total_usd_value = usd_value0 + usd_value1
            print(f" - Claimable {symbol0}: {formatted_amount0} (${usd_value0:,.2f})")
            print(f" - Claimable {symbol1}: {formatted_amount1} (${usd_value1:,.2f})")
            print(f" - Claimable Value: ${total_usd_value:,.2f}")

            # Submit claim transaction if total value exceeds the threshold
            if total_usd_value >= CLAIM_THRESHOLD_USD:
                print(f"Submitting claim transaction for Token ID {token_id}...")
                txn = nft_position_manager_contract.functions.collect({
                    "tokenId": token_id,
                    "recipient": target_address,
                    "amount0Max": 2**128 - 1,
                    "amount1Max": 2**128 - 1
                }).build_transaction({
                    "from": account.address,
                    "nonce": web3.eth.get_transaction_count(account.address, "pending"),
                    "gas": 200000,
                    "gasPrice": web3.to_wei("0.03", "gwei"),
                })

                signed_txn = web3.eth.account.sign_transaction(txn, private_key)
                tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
                print(f"Transaction submitted: {web3.to_hex(tx_hash)}")
            else:
                print(f"Total value below threshold. Skipping claim for Token ID {token_id}.")

        except Exception as e:
            print(f"Error simulating collect for token ID {token_id}: {e}")

# Run the script every 5 minutes
while True:
    run_script()
    print("Waiting for 5 minutes before the next run...")
    time.sleep(300)  # 300 seconds = 5 minutes
