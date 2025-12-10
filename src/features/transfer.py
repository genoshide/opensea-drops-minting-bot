import asyncio
from web3 import AsyncWeb3
from eth_account.signers.local import LocalAccount
from src.config.settings import ContractSpecs
from src.ui.logger import Logger

class AssetRelay:
    def __init__(self, w3: AsyncWeb3, account: LocalAccount, uid: int, recipient: str):
        self.w3 = w3
        self.acct = account
        self.uid = uid
        self.recipient = recipient

    async def _estimate_and_send(self, contract, token_id):
        try:
            func = contract.functions.safeTransferFrom(self.acct.address, self.recipient, token_id)
            nonce = await self.w3.eth.get_transaction_count(self.acct.address)
            gas_price = await self.w3.eth.gas_price
            chain_id = await self.w3.eth.chain_id
            
            tx_data = await func.build_transaction({
                'from': self.acct.address,
                'gasPrice': int(gas_price * 1.1),
                'nonce': nonce,
                'chainId': chain_id
            })

            try:
                est_gas = await self.w3.eth.estimate_gas(tx_data)
                tx_data['gas'] = int(est_gas * 1.2)
            except Exception:
                tx_data['gas'] = 150000 

            signed = self.acct.sign_transaction(tx_data)
            tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
            Logger.log(self.uid, "INFO", f"[Relay] Transferring ID #{token_id} -> {self.recipient[:6]}... (Hash: {tx_hash.hex()[:10]}...)")
            await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            Logger.log(self.uid, "SUCCESS", f"[Relay] Transfer Confirmed: {tx_hash.hex()}")

        except Exception as e:
            Logger.log(self.uid, "ERROR", f"[Relay] Failed to send Token #{token_id}: {str(e)[:100]}")

    async def sweep_native_token(self, min_balance_eth):
        if not self.recipient: return

        try:
            balance_wei = await self.w3.eth.get_balance(self.acct.address)
            balance_eth = balance_wei / 1e18
            
            if balance_eth < min_balance_eth:
                Logger.log(self.uid, "INFO", f"[Sweeper] Bal too low ({balance_eth:.4f}). Skip sweeping.")
                return

            gas_price = await self.w3.eth.gas_price
            gas_limit = 21000
            gas_cost = gas_price * gas_limit
            
            value_to_send = balance_wei - int(gas_cost * 1.1)
            
            if value_to_send <= 0:
                Logger.log(self.uid, "WARNING", "[Sweeper] Balance not enough to cover gas.")
                return

            Logger.log(self.uid, "INFO", f"[Sweeper] Sweeping {value_to_send/1e18:.5f} ETH to Safe...")

            nonce = await self.w3.eth.get_transaction_count(self.acct.address)
            tx = {
                'nonce': nonce,
                'to': self.recipient,
                'value': value_to_send,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'chainId': await self.w3.eth.chain_id
            }

            signed = self.acct.sign_transaction(tx)
            tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
            
            Logger.log(self.uid, "SUCCESS", f"[Sweeper] Swept! TX: {tx_hash.hex()}")
            
        except Exception as e:
            Logger.log(self.uid, "ERROR", f"[Sweeper] Failed: {e}")

    async def execute_consolidation(self, nft_address: str, mint_receipt):
        if not self.recipient: return
        try:
            nft_contract = self.w3.eth.contract(address=nft_address, abi=ContractSpecs.ERC721_ABI)
            try: logs = nft_contract.events.Transfer().process_receipt(mint_receipt, errors='DISCARD')
            except: 
                Logger.log(self.uid, "WARNING", "[Relay] Failed to decode logs.")
                return
            
            token_ids = []
            for log in logs:
                if log['args']['to'].lower() == self.acct.address.lower():
                    token_ids.append(log['args']['tokenId'])

            if not token_ids:
                Logger.log(self.uid, "WARNING", "[Relay] No Token IDs found.")
                return

            Logger.log(self.uid, "INFO", f"[Relay] Detected {len(token_ids)} new asset(s). Consolidating...")
            for tid in token_ids:
                await self._estimate_and_send(nft_contract, tid)
                await asyncio.sleep(1.5)

        except Exception as e:
            Logger.log(self.uid, "ERROR", f"[Relay] Consolidation Error: {e}")