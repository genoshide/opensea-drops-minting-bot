from rich.table import Table
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich import box
from datetime import datetime

class TUIManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TUIManager, cls).__new__(cls)
            cls._instance.console = Console()
            cls._instance.worker_status = {}
            cls._instance.system_logs = []
            cls._instance.target_info = "Initializing..."
            
            cls._instance.global_gas_price = None 
            
        return cls._instance

    def set_gas_price(self, wei):
        self.global_gas_price = int(wei)

    def get_gas_price(self):
        return self.global_gas_price

    def update_worker(self, uid, status, balance=None, last_msg=""):
        old_data = self.worker_status.get(uid, {"balance": "Checking...", "last_msg": ""})
        
        new_bal = balance if balance is not None else old_data['balance']
        
        self.worker_status[uid] = {
            "status": status,
            "balance": new_bal, 
            "last_msg": last_msg,
            "time": datetime.now().strftime("%H:%M:%S")
        }

    def add_system_log(self, msg):
        time_str = datetime.now().strftime("%H:%M:%S")
        self.system_logs.append(f"[{time_str}] {msg}")
        if len(self.system_logs) > 8:
            self.system_logs.pop(0)

    def set_target_info(self, info_str):
        self.target_info = info_str

    def generate_layout(self):
        layout = Layout()
        
        header_text = Text(self.target_info, justify="center", style="bold cyan")
        
        table = Table(box=box.ROUNDED, expand=True, title="[bold green]WORKER SQUADRON - Opensea drop bot by GENOSHIDE[/bold green]")
        table.add_column("ID", justify="center", style="cyan", no_wrap=True, width=4)
        table.add_column("Time", justify="center", style="dim", width=8)
        table.add_column("Wallet Balance", justify="right", style="green", width=15)
        table.add_column("Status / Activity", justify="left")

        for uid in sorted(self.worker_status.keys()):
            data = self.worker_status[uid]
            
            status_style = "white"
            status_text = str(data['status']).upper()
            
            if "SUCCESS" in status_text: status_style = "bold green"
            elif "ERROR" in status_text or "FATAL" in status_text: status_style = "bold red"
            elif "WARNING" in status_text: status_style = "yellow"
            elif "INIT" in status_text: status_style = "blue"
            
            msg_colored = f"[{status_style}]{data['last_msg']}[/{status_style}]"
            
            table.add_row(
                str(uid),
                data['time'],
                str(data['balance']),
                msg_colored
            )

        log_content = "\n".join(self.system_logs)
        
        log_panel = Panel(
            log_content, 
            title="[bold yellow]System Event Logs[/bold yellow]", 
            border_style="yellow",
            subtitle="[bold red]CTRL+C to EXIT[/bold red]",
            subtitle_align="right"
        )

        layout.split(
            Layout(Panel(header_text, style="white on black"), size=3),
            Layout(table),
            Layout(log_panel, size=10)
        )
        return layout

TUI = TUIManager()