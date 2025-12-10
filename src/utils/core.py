import sys
import os
import asyncio
import functools
import logging
from typing import Callable, Any
from web3 import __version__ as web3_version

class SystemCompliance:
    @staticmethod
    def assert_version(required: str = "7.12.0") -> None:
        if web3_version != required:
            raise SystemError(f"CRITICAL: Web3 Version Mismatch. Require {required}, Found {web3_version}")

    @staticmethod
    def cleanse_terminal():
        os.system("cls" if os.name == "nt" else "clear")

def async_error_handler(retries: int = 3, delay: float = 1.0):
    def decorator(func: Callable[..., Any]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            while attempt < retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    logging.error(f"[FaultGuard] {func.__name__} failed (Att {attempt}/{retries}): {str(e)[:50]}")
                    if attempt >= retries:
                        raise e
                    await asyncio.sleep(delay)
        return wrapper
    return decorator