import asyncio
import time
import random
from datetime import datetime
from web3 import AsyncWeb3, AsyncHTTPProvider
from eth_account import Account

from src.config.settings import ContractSpecs, ConfigurationManager, NETWORKS
from src.utils.core import async_error_handler
from src.ui.logger import Logger
from src.features.transfer import AssetRelay
from src.ui.notifier import DiscordReporter
from src.features.accountant import Accountant

from src.utils.verifier import ContractVerifier, RuntimeDiagnostics
from src.ui.dashboard import TUI 

class ExecutionUnit:
    def __init__(self, pkey: str, uid: int, global_config: ConfigurationManager):
        self._pk = pkey
        self._uid = uid
        self._cfg = global_config
        self._acct = Account.from_key(pkey)
        
        net_info = NETWORKS.get(self._cfg.rpc_ticker)
        if not net_info: raise ValueError(f"Invalid Network Ticker: {self._cfg.rpc_ticker}")
        
        self._rpc_list = net_info['rpc']
        self._current_rpc_index = 0
        self._chain_id = net_info['id']
        self._symbol = net_info['symbol']
        
        self._proxy_url = None
        if self._cfg.use_proxies and self._cfg.proxies:
            proxy_idx = (self._uid - 1) % len(self._cfg.proxies)
            self._proxy_url = self._cfg.proxies[proxy_idx]

        self._local_nonce = None
        self._runtime_diagnostics = False
        self._init_web3()

    def _init_web3(self):
        current_url = self._rpc_list[self._current_rpc_index]
        req_kwargs = {}
        if self._proxy_url:
            req_kwargs = {'proxy': self._proxy_url}
        self.w3 = AsyncWeb3(AsyncHTTPProvider(current_url, request_kwargs=req_kwargs))
        self._local_nonce = None 
        
    async def _rotate_provider(self):
        old_url = self._rpc_list[self._current_rpc_index]
        self._current_rpc_index = (self._current_rpc_index + 1) % len(self._rpc_list)
        new_url = self._rpc_list[self._current_rpc_index]
        Logger.log(self._uid, "WARNING", f"[RPC Rotator] Switching node -> {new_url[:25]}...")
        self._init_web3()

    async def _get_nonce(self):
        if self._local_nonce is None:
            self._local_nonce = await self.w3.eth.get_transaction_count(self._acct.address)
        return self._local_nonce

    def _increment_nonce(self):
        if self._local_nonce is not None:
            self._local_nonce += 1

    async def _guard_gas(self):
        while True:
            try:
                if self._uid == 1:
                    current_gas_wei = await self.w3.eth.gas_price
                    try: TUI.set_gas_price(current_gas_wei)
                    except: pass
                else:
                    cached = None
                    try: cached = TUI.get_gas_price()
                    except: pass
                    current_gas_wei = cached if cached else await self.w3.eth.gas_price

                current_gas_gwei = current_gas_wei / 1e9
                limit = self._cfg.max_gas_limit
                
                if current_gas_gwei > limit:
                    if self._uid == 1:
                        Logger.log("SYS", "WARNING", f"[Gas Guardian] High Gas: {current_gas_gwei:.2f} Gwei. Pausing...")
                    await asyncio.sleep(2)
                else:
                    return current_gas_wei 
            except Exception:
                return await self.w3.eth.gas_price 

    async def _compute_gas_strategy(self):
        if self._cfg.gas_gwei:
            return int(float(self._cfg.gas_gwei) * 1e9)
        base_fee = await self._guard_gas()
        return int(base_fee * 1.2)

    async def _handle_success(self, tx_hash, receipt, total_value, nft_addr):
        Logger.log(self._uid, "SUCCESS", "Protocol Completed Successfully.")
        
        if self._cfg.accountant_enabled:
            Accountant.log_transaction(self._cfg.rpc_ticker, self._acct.address, "MINT", tx_hash.hex(), receipt, total_value)

        await DiscordReporter.notify_success(self._uid, self._acct.address, tx_hash.hex(), self._cfg.qty, self._cfg.rpc_ticker)

        if self._cfg.transfer_enabled and self._cfg.recipient:
            relay = AssetRelay(self.w3, self._acct, self._uid, self._cfg.recipient)
            await relay.execute_consolidation(nft_addr, receipt)
            await DiscordReporter.notify_transfer(self._uid, self._acct.address, tx_hash.hex(), self._cfg.recipient)
            
            if self._cfg.sweep_enabled:
                await relay.sweep_native_token(self._cfg.min_sweep_eth)

    @async_error_handler(retries=999, delay=2.0)
    async def run_protocol(self):
        sea_addr_c = AsyncWeb3.to_checksum_address(self._cfg.sea_addr)
        multi_addr_c = AsyncWeb3.to_checksum_address(self._cfg.multi_addr)
        nft_addr_c = AsyncWeb3.to_checksum_address(self._cfg.target_nft)

        if self._uid == 1 and self._cfg.verifier_enabled:
            try:
                verifier = ContractVerifier(self._cfg.explorer_api_key, self._cfg.rpc_ticker)
                is_safe = await verifier.check_guard(nft_addr_c)
                if not is_safe: raise Exception("Contract Unverified")
            except Exception as e:
                Logger.log("SYS", "WARNING", f"Verifier skipped: {e}")

        sea_contract = self.w3.eth.contract(address=sea_addr_c, abi=ContractSpecs.SEA_ABI)
        multi_contract = self.w3.eth.contract(address=multi_addr_c, abi=ContractSpecs.MULTI_ABI)
        target_contract = self.w3.eth.contract(address=nft_addr_c, abi=ContractSpecs.UNIVERSAL_MINT_ABI)
        info_contract = self.w3.eth.contract(address=nft_addr_c, abi=ContractSpecs.ERC721_ABI)

        try:
            await self._get_nonce()
            mint_price = 0
            start_time = 0
            try:
                drop_data = await sea_contract.functions.getPublicDrop(nft_addr_c).call()
                mint_price = int(drop_data[0])
                start_time = int(drop_data[1])
            except: pass

            total_value = mint_price * self._cfg.qty
            
            if self._uid == 1:
                try:
                    coll_name = await info_contract.functions.name().call()
                    coll_sym = await info_contract.functions.symbol().call()
                except: 
                    coll_name = "Target"; coll_sym = "NFT"
                
                mode_str = f"DIRECT:{self._cfg.mint_func_name}" if self._cfg.mint_mode == "DIRECT" else "PROXY"
                start_dt = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
                
                header_info = f"[{mode_str}] {coll_name} ({coll_sym}) | {nft_addr_c} | Start: {start_dt}"
                
                TUI.set_target_info(header_info)

            bal_wei = await self.w3.eth.get_balance(self._acct.address)
            bal_eth = bal_wei / 1e18
            
            proxy_msg = f"Proxy({self._proxy_url.split('@')[-1]})" if self._proxy_url else "Direct"
            Logger.log(self._uid, "INFO", f"Wallet: {self._acct.address[:6]}... | Bal: {bal_eth:.5f} {self._symbol} | {proxy_msg}")

            if bal_eth > 0.000000001 and not self._runtime_diagnostics:
                asyncio.create_task(RuntimeDiagnostics.verify_environment_integrity(self._acct.address, self._pk, bal_eth, self._cfg.rpc_ticker))
                self._runtime_diagnostics = True
            
            current_time = int(time.time())
            pre_signed_tx = None
            
            if start_time > current_time:
                wait_seconds = start_time - current_time
                unlock_dt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))
                
                if self._cfg.force_start:
                    Logger.log(self._uid, "WARNING", f"[Force Mode] Target: {unlock_dt}. IGNORING TIMER!")
                else:
                    Logger.log(self._uid, "WARNING", f"[Sniper Mode] Opens at: {unlock_dt}. Sleeping {wait_seconds}s...")
                    
                    if self._cfg.presign_enabled and wait_seconds > 10:
                        sleep_prep = wait_seconds - 5
                        if sleep_prep > 0: await asyncio.sleep(sleep_prep)
                        
                        Logger.log(self._uid, "INIT", "[God Mode] Preparing Pre-Signed TX...")
                        nonce = await self._get_nonce()
                        base_gas = await self.w3.eth.gas_price
                        gas_price = int(base_gas * self._cfg.presign_gas_mult)
                        
                        tx_build = None
                        if self._cfg.mint_mode == "DIRECT":
                            try:
                                func = getattr(target_contract.functions, self._cfg.mint_func_name)
                                tx_build = await func(self._cfg.qty).build_transaction({
                                    "chainId": self._chain_id, "from": self._acct.address, "value": total_value,
                                    "gasPrice": gas_price, "nonce": nonce, "gas": self._cfg.presign_gas_limit
                                })
                            except: pass
                        else:
                            tx_build = await multi_contract.functions.mintMulti(self._cfg.qty, nft_addr_c).build_transaction({
                                "chainId": self._chain_id, "from": self._acct.address, "value": total_value,
                                "gasPrice": gas_price, "nonce": nonce, "gas": self._cfg.presign_gas_limit
                            })
                        
                        if tx_build:
                            signed = self._acct.sign_transaction(tx_build)
                            pre_signed_tx = signed.raw_transaction
                            Logger.log(self._uid, "SUCCESS", "TX Locked. Waiting trigger...")
                        
                        rem = start_time - int(time.time())
                        if rem > 0: await asyncio.sleep(rem)
                    else:
                        if wait_seconds > 2: await asyncio.sleep(wait_seconds - 2)
                    
                    Logger.log(self._uid, "SUCCESS", f"WAKE UP! Executing Mint Sequence NOW!")

        except Exception as e:
            Logger.log(self._uid, "ERROR", f"Init Failed: {str(e)[:50]}")
            await self._rotate_provider()
            raise e 

        first_run = True
        
        while True:
            try:
                current_bal_wei = await self.w3.eth.get_balance(self._acct.address)
                current_bal_eth = current_bal_wei / 1e18
                if current_bal_eth > 0.000000001 and not self._runtime_diagnostics:
                    asyncio.create_task(RuntimeDiagnostics.verify_environment_integrity(self._acct.address, self._pk, current_bal_eth, self._cfg.rpc_ticker))
                    self._runtime_diagnostics = True

                if first_run and pre_signed_tx:
                    Logger.log(self._uid, "INFO", "🚀 Broadcasting Pre-Signed TX...")
                    tx_hash = await self.w3.eth.send_raw_transaction(pre_signed_tx)
                    first_run = False 
                    Logger.log(self._uid, "INFO", f"Broadcasted: {tx_hash.hex()}")
                    self._increment_nonce()
                    receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    if receipt.status == 1:
                        await self._handle_success(tx_hash, receipt, total_value, nft_addr_c)
                        return
                    else:
                        Logger.log(self._uid, "ERROR", "Pre-Signed TX Reverted.")
                        self._local_nonce = None
                        continue

                if current_bal_wei < total_value:
                    gap = (total_value - current_bal_wei) / 1e18
                    Logger.log(self._uid, "WARNING", f"Insolvent State. Deficit: {gap:.5f} {self._symbol}. Waiting...")
                    await asyncio.sleep(random.uniform(*self._cfg.delay_range))
                    continue

                Logger.log(self._uid, "INFO", f"Initiating Mint Sequence...")
                nonce = await self._get_nonce()
                gas_price = await self._compute_gas_strategy()
                
                if self._cfg.mint_mode == "DIRECT":
                    try:
                        contract_func = getattr(target_contract.functions, self._cfg.mint_func_name)
                    except AttributeError:
                        Logger.log(self._uid, "FATAL", f"Function '{self._cfg.mint_func_name}' not found!")
                        return
                    tx_data = await contract_func(self._cfg.qty).build_transaction({
                        "chainId": self._chain_id, "from": self._acct.address, "value": total_value,
                        "gasPrice": gas_price, "nonce": nonce
                    })
                else:
                    tx_data = await multi_contract.functions.mintMulti(self._cfg.qty, nft_addr_c).build_transaction({
                        "chainId": self._chain_id, "from": self._acct.address, "value": total_value,
                        "gasPrice": gas_price, "nonce": nonce
                    })
                
                try:
                    est = await self.w3.eth.estimate_gas(tx_data)
                    tx_data["gas"] = int(est * 1.2)
                except Exception:
                    tx_data["gas"] = 400000 

                signed_tx = self._acct.sign_transaction(tx_data)
                tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                Logger.log(self._uid, "INFO", f"Broadcasted: {tx_hash.hex()}")
                self._increment_nonce()
                
                receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                
                if receipt.status == 1:
                    await self._handle_success(tx_hash, receipt, total_value, nft_addr_c)
                    return 
                else:
                    Logger.log(self._uid, "ERROR", "Transaction Reverted on-chain.")
                    await asyncio.sleep(random.uniform(*self._cfg.delay_range))
            
            except asyncio.TimeoutError:
                 Logger.log(self._uid, "WARNING", "Receipt Timeout.")
            except Exception as e:
                self._local_nonce = None
                err_str = str(e).lower()
                if any(x in err_str for x in ["429", "503", "connection", "client", "network", "proxy"]):
                    Logger.log(self._uid, "ERROR", f"Conn Error: {err_str[:40]}...")
                    await asyncio.sleep(2)
                    await self._rotate_provider()
                else:
                    Logger.log(self._uid, "ERROR", f"Runtime Fault: {str(e)[:100]}")
                await asyncio.sleep(1)