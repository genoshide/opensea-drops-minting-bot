import sys
import re
import logging
from typing import Union, Any
from src.ui.dashboard import TUI

logging.basicConfig(
    filename='bot_activity.log',
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filemode='a'
)

class TelemetryInterface:
    @staticmethod
    def log(process_identifier: Union[int, str], level: str, event_payload: str) -> None:
        clean_msg = re.sub(r'\x1b\[[0-9;]*m', '', event_payload)
        log_entry = f"[{process_identifier}] {clean_msg}"
        
        if level.upper() in ["ERROR", "FATAL", "CRITICAL"]:
            logging.error(log_entry)
        elif level.upper() == "WARNING":
            logging.warning(log_entry)
        else:
            logging.info(log_entry)

        if isinstance(process_identifier, int) or (isinstance(process_identifier, str) and process_identifier.isdigit()):
            uid = int(process_identifier)
            status_key = level.upper()
            
            current_bal = "..."
            match = re.search(r"Bal:\s*([\d\.]+)", event_payload)
            
            if match:
                detected_bal = match.group(1)
                TUI.update_worker(uid, status_key, balance=detected_bal, last_msg=f"[{status_key}] {event_payload}")
            else:
                TUI.update_worker(uid, status_key, balance=None, last_msg=f"[{status_key}] {event_payload}")

        else:
            TUI.add_system_log(f"[{process_identifier}] {event_payload}")

Logger = TelemetryInterface