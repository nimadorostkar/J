# === FILE: backend/wallet/consumers.py ===
"""WebSocket consumer that pushes wallet, reward, and notification events."""
import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class WalletConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return
        self.user = user
        self.group_name = f"wallet_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "userId": str(user.id)})

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        if action == "ping":
            await self.send_json({"type": "pong"})

    # ── Group event handlers (called via channel_layer.group_send) ──
    async def balance_update(self, event):
        await self.send_json({
            "type": "balance_update",
            "hCoins": event["h_coins"],
            "usdtBalance": event["usdt_balance"],
        })

    async def reward_claimable(self, event):
        await self.send_json({"type": "reward_claimable"})

    async def transaction_update(self, event):
        await self.send_json({
            "type": "transaction_update",
            "id": event["id"],
            "status": event["status"],
            "txType": event.get("tx_type"),
        })

    async def notification(self, event):
        await self.send_json({
            "type": "notification",
            "id": event.get("id"),
            "title": event["title"],
            "body": event["body"],
            "notificationType": event.get("notification_type", "system"),
        })

    async def commission_received(self, event):
        await self.send_json({
            "type": "commission_received",
            "amount": event["amount"],
            "level": event["level"],
            "fromUser": event["from_user"],
        })
