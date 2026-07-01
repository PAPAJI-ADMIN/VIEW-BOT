import os
import logging
import requests
import aiosqlite
import re
import asyncio
from telethon import TelegramClient, events, Button

# ==================== CONFIGURATION ====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

API_ID = int(os.getenv("API_ID", "30208136"))
API_HASH = os.getenv("API_HASH", "8d13aabfe7e3b2c24ad507edb48f27a5")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8eeafab20782b8c9ac67c580c1d36c2c")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8211510972"))

# SMM Panel Config
SMM_API_URL = "https://finesmmpanel.com/api/v2"
SMM_API_KEY = "9050b7173d7b59058c21edd5328fcaf2"
SMM_SERVICE_ID = "3923" # Instant Public Views
SMM_PRIVATE_SERVICE_ID = "3919" # Private/HQ Views

# Pricing
PRICE_PER_1000 = 25.0
AUTO_VIEW_QTY = 100 

# Persistent Storage Path
PERSISTENT_DIR = "data"
DB_NAME = os.path.join(PERSISTENT_DIR, "reseller_bot.db")
os.makedirs(PERSISTENT_DIR, exist_ok=True)

bot = TelegramClient("reseller_session", API_ID, API_HASH)

# ==================== DATABASE ====================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0)")
        await db.execute("CREATE TABLE IF NOT EXISTS auto_channels (channel_id TEXT PRIMARY KEY, user_id INTEGER)")
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id, balance) VALUES (?, 0.0)", (user_id,))
                await db.commit()
                return 0.0
            return row[0]

async def update_balance(user_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

# ==================== SMM FUNCTIONS ====================
def place_smm_order(link, quantity, service_id):
    payload = {
        "key": SMM_API_KEY, "action": "add", "service": service_id, "link": link, "quantity": quantity
    }
    try:
        response = requests.post(SMM_API_URL, data=payload, timeout=15)
        return response.json()
    except Exception as e:
        logger.error(f"SMM Error: {e}")
        return {"error": str(e)}

# ==================== BOT HANDLERS ====================
user_states = {}

@bot.on(events.NewMessage())
async def unified_handler(event):
    uid = event.sender_id
    text = event.text.strip() if event.text else ""

    # 1. HANDLE CHANNEL POSTS (MOST IMPORTANT)
    if event.is_channel:
        raw_cid = str(abs(event.chat_id))
        # Remove -100 prefix if present for database matching
        if raw_cid.startswith("100"): raw_cid = raw_cid[3:]
        
        logger.info(f"DETECTED POST IN CHANNEL: {raw_cid}")

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT user_id FROM auto_channels WHERE channel_id = ?", (raw_cid,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    reg_uid = row[0]
                    logger.info(f"MATCH FOUND FOR USER: {reg_uid}")
                    try:
                        chat = await event.get_chat()
                        is_pub = bool(chat.username)
                        link = f"https://t.me/{chat.username}/{event.id}" if is_pub else f"https://t.me/c/{raw_cid}/{event.id}"
                        service_id = SMM_SERVICE_ID if is_pub else SMM_PRIVATE_SERVICE_ID
                        
                        cost = (AUTO_VIEW_QTY / 1000) * PRICE_PER_1000
                        balance = await get_user(reg_uid)
                        
                        if balance < cost:
                            await bot.send_message(reg_uid, f"⚠️ **Low Balance!**\nPost: {link}")
                            return

                        loop = asyncio.get_event_loop()
                        res = await loop.run_in_executor(None, place_smm_order, link, AUTO_VIEW_QTY, service_id)
                        
                        if res and "order" in res:
                            await update_balance(reg_uid, -cost)
                            await bot.send_message(reg_uid, f"✅ **Auto-Order Placed!**\n\n🔗 **Post:** {link}\n📈 **Views:** `{AUTO_VIEW_QTY}`\n💰 **Cost:** `₹{cost:.2f}`\n🆔 **Order ID:** `{res['order']}`")
                        else:
                            logger.error(f"Order Placement Failed: {res}")
                    except Exception as e:
                        logger.error(f"Channel Handler Error: {e}")
        return

    # 2. HANDLE PRIVATE MESSAGES (ADMIN, REGISTRATION, ORDERS)
    if event.is_private:
        # Start Command
        if text == "/start":
            balance = await get_user(uid)
            welcome_text = (
                f"🚀 **Welcome to Premium View Booster!**\n\n"
                f"💰 **Your Balance:** `₹{balance:.2f}`\n"
                f"📈 **Price:** `₹{PRICE_PER_1000} per 1000 views`"
            )
            buttons = [[Button.inline("🚀 Order Views (Manual)", data="order")],
                       [Button.inline("🤖 Auto-View Setup", data="auto_setup")],
                       [Button.inline("💳 Add Funds", data="add_funds"), Button.inline("📊 My Account", data="account")]]
            if uid == ADMIN_ID: buttons.append([Button.inline("🛠 Admin Panel", data="admin")])
            await event.respond(welcome_text, buttons=buttons)
            return

        # Admin Command
        if text.startswith("/addbal") and uid == ADMIN_ID:
            try:
                parts = text.split(); target_id, amount = int(parts[1]), float(parts[2])
                await update_balance(target_id, amount); await event.respond(f"✅ Added ₹{amount}")
            except: await event.respond("❌ Usage: `/addbal <id> <amount>`")
            return

        # Channel Registration via Forward
        if event.fwd_from:
            try:
                fwd_id = event.fwd_from.from_id
                if hasattr(fwd_id, 'channel_id'):
                    cid = str(fwd_id.channel_id)
                    async with aiosqlite.connect(DB_NAME) as db:
                        await db.execute("INSERT OR REPLACE INTO auto_channels (channel_id, user_id) VALUES (?, ?)", (cid, uid))
                        await db.commit()
                    await event.respond(f"✅ **Channel Registered!**\nID: `{cid}`\n\nअब इस चैनल की हर नई पोस्ट पर ऑटोमैटिक व्यूज आयेंगे।")
                    logger.info(f"Registered Channel {cid} for user {uid}")
                return
            except Exception as e: logger.error(f"Reg Error: {e}")

        # Manual Order State Handling
        if uid in user_states:
            state = user_states[uid]
            if state == "wait_link":
                user_states[uid] = {"state": "wait_qty", "link": text}
                await event.respond("🔢 **Enter Quantity:**")
            elif isinstance(state, dict) and state.get("state") == "wait_qty":
                try:
                    qty = int(text); link = state["link"]; cost = (qty / 1000) * PRICE_PER_1000
                    balance = await get_user(uid)
                    if balance < cost: user_states.pop(uid); return await event.respond("⚠️ Low Balance!")
                    user_states.pop(uid); msg = await event.respond("⏳ Processing...")
                    loop = asyncio.get_event_loop()
                    order = await loop.run_in_executor(None, place_smm_order, link, qty, SMM_PRIVATE_SERVICE_ID if "/c/" in link else SMM_SERVICE_ID)
                    if order and "order" in order:
                        await update_balance(uid, -cost); await msg.edit(f"✅ **Order Success!** ID: `{order['order']}`")
                    else: await msg.edit(f"❌ Failed: {order.get('error')}")
                except: await event.respond("❌ Invalid Quantity.")

@bot.on(events.CallbackQuery())
async def callback(event):
    data = event.data.decode(); uid = event.sender_id
    if data == "order":
        user_states[uid] = "wait_link"; await event.respond("🔗 **Send the Channel Post Link:**")
    elif data == "auto_setup":
        await event.respond("🤖 **Auto-View Setup:**\n1. मुझे Admin बनायें।\n2. कोई भी पोस्ट **Forward** करें।")
    elif data == "add_funds":
        await event.respond(f"💳 Contact Admin: @YourUsername\nUser ID: `{uid}`")
    elif data == "account":
        balance = await get_user(uid); await event.respond(f"👤 **User ID:** `{uid}`\n💰 **Balance:** `₹{balance:.2f}`")
    elif data == "admin" and uid == ADMIN_ID:
        await event.respond("🛠 **Admin Panel:**\nUse `/addbal <id> <amount>`", buttons=[Button.inline("🔙 Back", data="back")])
    elif data == "back":
        user_states.pop(uid, None); await start_manual(event)

async def start_manual(event):
    uid = event.sender_id; balance = await get_user(uid)
    welcome_text = (f"🚀 **Welcome back!**\n💰 **Balance:** `₹{balance:.2f}`")
    buttons = [[Button.inline("🚀 Order Views (Manual)", data="order")],
               [Button.inline("🤖 Auto-View Setup", data="auto_setup")],
               [Button.inline("💳 Add Funds", data="add_funds"), Button.inline("📊 My Account", data="account")]]
    if uid == ADMIN_ID: buttons.append([Button.inline("🛠 Admin Panel", data="admin")])
    await event.respond(welcome_text, buttons=buttons)

async def main():
    await init_db()
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot Started - Unified Handler Mode")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
