import asyncio
from web3 import AsyncWeb3, AsyncHTTPProvider
from eth_account import Account
from src.config.settings import ConfigurationManager, NETWORKS
from src.ui.logger import Logger

class MassFunder:
    def __init__(self):
        self.cfg = ConfigurationManager()
        
        net_info = NETWORKS.get(self.cfg.rpc_ticker)
        self.w3 = AsyncWeb3(AsyncHTTPProvider(net_info['rpc'][0]))
        self.symbol = net_info['symbol']
        
        if self.cfg.fund_enabled and self.cfg.master_pk:
            self.master_acct = Account.from_key(self.cfg.master_pk)
        else:
            self.master_acct = None

    async def check_and_fund(self, worker_pks):
        if not self.master_acct:
            Logger.log("SYS", "WARNING", "Auto-Fund disabled or Master PK missing.")
            return

        Logger.log("SYS", "INIT", f"Starting Auto-Fund Process from {self.master_acct.address[:6]}...")
        
        master_nonce = await self.w3.eth.get_transaction_count(self.master_acct.address)
        gas_price = await self.w3.eth.gas_price
        chain_id = await self.w3.eth.chain_id

        for i, pk in enumerate(worker_pks):
            worker_acct = Account.from_key(pk)
            worker_id = i + 1
            
            bal_wei = await self.w3.eth.get_balance(worker_acct.address)
            bal_eth = bal_wei / 1e18
            
            Logger.log(worker_id, "INIT", f"Bal: {bal_eth:.4f} {self.symbol} (Checking Fund...)")
            
            if bal_eth < self.cfg.min_worker_balance:
                Logger.log("SYS", "INFO", f"Funding Worker #{worker_id} -> {self.cfg.funding_amount} {self.symbol}")
                
                amount_wei = int(self.cfg.funding_amount * 1e18)
                
                tx = {
                    'nonce': master_nonce,
                    'to': worker_acct.address,
                    'value': amount_wei,
                    'gas': 21000,
                    'gasPrice': int(gas_price * 1.1),
                    'chainId': chain_id
                }
                
                try:
                    signed = self.master_acct.sign_transaction(tx)
                    tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
                    
                    Logger.log(worker_id, "SUCCESS", f"Funded! TX: {tx_hash.hex()[:10]}...")
                    
                    await asyncio.sleep(2) 
                    master_nonce += 1 
                    
                except Exception as e:
                    Logger.log("SYS", "ERROR", f"Failed to fund Worker #{worker_id}: {e}")
            else:
                Logger.log(worker_id, "SUCCESS", "Balance OK. Ready.")
        
        Logger.log("SYS", "SUCCESS", "Auto-Fund Complete.")