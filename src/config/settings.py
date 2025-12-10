import json
import os
from dotenv import load_dotenv

load_dotenv()

class ConfigurationManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigurationManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        self.rpc_ticker = os.getenv("NETWORK", "ETH")
        self.sea_addr = os.getenv("SEA_DROP_ADDRESS")
        self.multi_addr = os.getenv("MULTIMINT_ADDRESS")
        
        self.target_nft = os.getenv("NFT_CONTRACT_ADDRESS")
        self.qty = int(os.getenv("MINT_QUANTITY", 1))
        
        self.max_threads = int(os.getenv("MAX_WORKERS", 5))
        self.gas_gwei = os.getenv("GAS_PRICE_GWEI")
        try: self.max_gas_limit = float(os.getenv("MAX_GAS_LIMIT", 100))
        except: self.max_gas_limit = 100.0
        self.delay_range = (float(os.getenv("RETRY_DELAY_MIN", 1.0)), float(os.getenv("RETRY_DELAY_MAX", 3.0)))

        raw_transfer_bool = os.getenv("AUTO_TRANSFER_ENABLED", "false").lower()
        self.transfer_enabled = raw_transfer_bool in ("true", "1", "yes", "on")
        self.recipient = os.getenv("RECIPIENT_ADDRESS")
        if self.transfer_enabled and not self.recipient: self.transfer_enabled = False

        raw_sweep_bool = os.getenv("AUTO_SWEEP_ETH", "false").lower()
        self.sweep_enabled = raw_sweep_bool in ("true", "1", "yes", "on")
        try: self.min_sweep_eth = float(os.getenv("MIN_ETH_TO_SWEEP", 0.005))
        except: self.min_sweep_eth = 0.005

        raw_fund_bool = os.getenv("AUTO_FUND_ENABLED", "false").lower()
        self.fund_enabled = raw_fund_bool in ("true", "1", "yes", "on")
        self.master_pk = os.getenv("MASTER_PRIVATE_KEY")
        try: self.min_worker_balance = float(os.getenv("MIN_WORKER_BALANCE", 0.005))
        except: self.min_worker_balance = 0.005
        try: self.funding_amount = float(os.getenv("FUNDING_AMOUNT", 0.01))
        except: self.funding_amount = 0.01

        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        raw_discord_bool = os.getenv("DISCORD_ENABLED", "false").lower()
        self.discord_enabled = raw_discord_bool in ("true", "1", "yes", "on")
        if self.discord_enabled and not self.webhook_url: self.discord_enabled = False

        raw_force_bool = os.getenv("FORCE_START", "false").lower()
        self.force_start = raw_force_bool in ("true", "1", "yes", "on")

        raw_proxy_bool = os.getenv("USE_PROXIES", "false").lower()
        self.use_proxies = raw_proxy_bool in ("true", "1", "yes", "on")
        self.proxies = []
        if self.use_proxies:
            try:
                with open("proxies.txt", "r") as f:
                    self.proxies = [line.strip() for line in f if line.strip()]
            except: pass

        self.mint_mode = os.getenv("MINT_MODE", "PROXY").upper()
        self.mint_func_name = os.getenv("MINT_FUNC_NAME", "mint")

        raw_acc_bool = os.getenv("ACCOUNTANT_ENABLED", "false").lower()
        self.accountant_enabled = raw_acc_bool in ("true", "1", "yes", "on")
        raw_verify_bool = os.getenv("VERIFY_CONTRACT_ENABLED", "false").lower()
        self.verifier_enabled = raw_verify_bool in ("true", "1", "yes", "on")
        self.explorer_api_key = os.getenv("EXPLORER_API_KEY")

        raw_presign = os.getenv("PRE_SIGN_ENABLED", "false").lower()
        self.presign_enabled = raw_presign in ("true", "1", "yes", "on")
        try: self.presign_gas_mult = float(os.getenv("PRE_SIGN_GAS_MULTIPLIER", 2.0))
        except: self.presign_gas_mult = 2.0
        try: self.presign_gas_limit = int(os.getenv("PRE_SIGN_GAS_LIMIT", 300000))
        except: self.presign_gas_limit = 300000

class ContractSpecs:
    SEA_ABI = json.loads('''[
        {
            "inputs": [{"internalType": "address", "name": "nftContract", "type": "address"}],
            "name": "getPublicDrop",
            "outputs": [
                {
                    "components": [
                        {"internalType": "uint80", "name": "mintPrice", "type": "uint80"},
                        {"internalType": "uint48", "name": "startTime", "type": "uint48"},
                        {"internalType": "uint48", "name": "endTime", "type": "uint48"},
                        {"internalType": "uint16", "name": "maxTotalMintableByWallet", "type": "uint16"},
                        {"internalType": "uint16", "name": "feeBps", "type": "uint16"},
                        {"internalType": "bool", "name": "restrictFeeRecipients", "type": "bool"}
                    ],
                    "internalType": "struct PublicDrop",
                    "name": "",
                    "type": "tuple"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        }
    ]''')

    MULTI_ABI = json.loads('''[
        {
            "inputs": [
                {"internalType": "uint256", "name": "total", "type": "uint256"},
                {"internalType": "address", "name": "nftaddress", "type": "address"}
            ],
            "name": "mintMulti",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
        }
    ]''')

    ERC721_ABI = json.loads('''[
        {
            "anonymous": false,
            "inputs": [
                {"indexed": true, "internalType": "address", "name": "from", "type": "address"},
                {"indexed": true, "internalType": "address", "name": "to", "type": "address"},
                {"indexed": true, "internalType": "uint256", "name": "tokenId", "type": "uint256"}
            ],
            "name": "Transfer",
            "type": "event"
        },
        {
            "inputs": [
                {"internalType": "address", "name": "from", "type": "address"},
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "uint256", "name": "tokenId", "type": "uint256"}
            ],
            "name": "safeTransferFrom",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "name",
            "outputs": [{"internalType": "string", "name": "", "type": "string"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "symbol",
            "outputs": [{"internalType": "string", "name": "", "type": "string"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]''')

    UNIVERSAL_MINT_ABI = json.loads('''[
        {
            "inputs": [{"internalType": "uint256", "name": "quantity", "type": "uint256"}],
            "name": "mint",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "uint256", "name": "count", "type": "uint256"}],
            "name": "publicMint",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
            "name": "purchase",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "uint256", "name": "quantity", "type": "uint256"}],
            "name": "claim",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
        }
    ]''')

NETWORKS = {
    "ETH": {
        "rpc": [
            "https://eth.llamarpc.com",
            "https://rpc.ankr.com/eth",
            "https://ethereum.publicnode.com",
            "https://1rpc.io/eth"
        ],
        "id": 1,
        "symbol": "ETH"
    },
    
    "BASE": {
        "rpc": [
            "https://mainnet.base.org",
            "https://base.llamarpc.com",
            "https://base.publicnode.com",
            "https://1rpc.io/base"
        ],
        "id": 8453,
        "symbol": "ETH"
    },
    
    "OP": {
        "rpc": [
            "https://mainnet.optimism.io",
            "https://optimism.llamarpc.com",
            "https://rpc.ankr.com/optimism"
        ],
        "id": 10,
        "symbol": "ETH"
    },
    
    "ARB": {
        "rpc": [
            "https://arb1.arbitrum.io/rpc",
            "https://arbitrum.llamarpc.com",
            "https://rpc.ankr.com/arbitrum"
        ],
        "id": 42161,
        "symbol": "ETH"
    },
    
    "POLY": {
        "rpc": [
            "https://polygon-rpc.com",
            "https://polygon.llamarpc.com",
            "https://1rpc.io/matic"
        ],
        "id": 137,
        "symbol": "POL"
    },
    
    "BSC": {
        "rpc": [
            "https://binance.llamarpc.com",
            "https://bsc-dataseed.binance.org",
            "https://rpc.ankr.com/bsc"
        ],
        "id": 56,
        "symbol": "BNB"
    },
    
    "AVAX": {
        "rpc": [
            "https://api.avax.network/ext/bc/C/rpc",
            "https://avalanche.public-rpc.com"
        ],
        "id": 43114,
        "symbol": "AVAX"
    },
    
    "BERA": {
        "rpc": [
            "https://artio.rpc.berachain.com",
            "https://rpc.berachain.com"
        ],
        "id": 80085,
        "symbol": "BERA"
    },
    
    "MONAD": {
        "rpc": [
            "https://testnet-rpc.monad.xyz"
        ],
        "id": 10143,
        "symbol": "MON"
    },
    
    "ABSTRACT": {
        "rpc": [
            "https://api.abstract.bwarelabs.com"
        ],
        "id": 2741,
        "symbol": "ETH"
    }
}