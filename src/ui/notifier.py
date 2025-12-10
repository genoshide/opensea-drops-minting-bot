import aiohttp
import asyncio
from datetime import datetime
from src.config.settings import ConfigurationManager

class DiscordReporter:
    @staticmethod
    async def send_log(title: str, description: str, color: int, fields: list = []):
        cfg = ConfigurationManager()
        
        if not cfg.discord_enabled:
            return
        if not cfg.webhook_url:
            return

        embed = {
            "title": title,
            "description": description,
            "color": color, 
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Genoshide Enterprise Minter"},
            "fields": fields
        }

        payload = {
            "username": "Genoshide Bot",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
            "embeds": [embed]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(cfg.webhook_url, json=payload) as response:
                    if response.status not in (200, 204):
                        pass
        except Exception:
            pass

    @staticmethod
    async def notify_success(uid, wallet, tx_hash, qty, network):
        if network == "BASE": 
            url = f"https://basescan.org/tx/{tx_hash}"
        elif network == "BSC":
            url = f"https://bscscan.com/tx/{tx_hash}"
        elif network == "ARB":
            url = f"https://arbiscan.io/tx/{tx_hash}"
        elif network == "POLY":
            url = f"https://polygonscan.com/tx/{tx_hash}"
        elif network == "AVAX":
            url = f"https://snowtrace.io/tx/{tx_hash}"
        elif network == "OP":
            url = f"https://optimistic.etherscan.io/tx/{tx_hash}"
        elif network == "BERA":
            url = f"https://artio.beratrail.io/tx/{tx_hash}"
        elif network == "MONAD":
            url = f"https://testnet.monadexplorer.com/tx/{tx_hash}"
        else:
            url = f"https://etherscan.io/tx/{tx_hash}"

        await DiscordReporter.send_log(
            title="✅ MINT SUCCESS",
            description=f"**Wallet #{uid}** has successfully executed.",
            color=3066993,
            fields=[
                {"name": "Wallet", "value": f"`{wallet}`", "inline": True},
                {"name": "Quantity", "value": str(qty), "inline": True},
                {"name": "Network", "value": network, "inline": True},
                {"name": "Transaction", "value": f"[View on Explorer]({url})", "inline": False}
            ]
        )

    @staticmethod
    async def notify_transfer(uid, wallet, tx_hash, recipient):
        await DiscordReporter.send_log(
            title="🚀 ASSET CONSOLIDATED",
            description="The NFT has been successfully secured in a cold wallet.",
            color=15105570,
            fields=[
                {"name": "From", "value": f"`{wallet}`", "inline": True},
                {"name": "To Recipient", "value": f"`{recipient[:10]}...`", "inline": True},
                {"name": "TX Hash", "value": f"`{tx_hash}`", "inline": False}
            ]
        )