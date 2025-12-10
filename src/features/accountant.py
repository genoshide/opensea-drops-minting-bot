import csv
import os
import threading
from datetime import datetime

class Accountant:
    _lock = threading.Lock()
    _filename = "history.csv"

    @staticmethod
    def _init_file():
        if not os.path.exists(Accountant._filename):
            with open(Accountant._filename, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Network", "Wallet", "Action", "Tx Hash", 
                    "Gas Used", "Gas Price (Gwei)", "Gas Cost (Native)", "Mint Cost (Native)", "Total Spent (Native)"
                ])

    @staticmethod
    def log_transaction(network, wallet, action, tx_hash, receipt, mint_cost_wei):
        try:
            with Accountant._lock:
                Accountant._init_file()
                
                gas_used = receipt['gasUsed']
                effective_gas_price = receipt['effectiveGasPrice']
                gas_cost_wei = gas_used * effective_gas_price
                
                total_spent_wei = gas_cost_wei + mint_cost_wei
                
                gas_cost_native = gas_cost_wei / 1e18
                mint_cost_native = mint_cost_wei / 1e18
                total_spent_native = total_spent_wei / 1e18
                gas_price_gwei = effective_gas_price / 1e9
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                with open(Accountant._filename, mode='a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        timestamp, 
                        network, 
                        wallet, 
                        action, 
                        tx_hash,
                        gas_used,
                        f"{gas_price_gwei:.2f}",
                        f"{gas_cost_native:.6f}",
                        f"{mint_cost_native:.6f}",
                        f"{total_spent_native:.6f}"
                    ])
                    
        except Exception as e:
            print(f"[Accountant Error] Failed to record log: {e}")