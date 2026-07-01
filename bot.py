import os
import logging
import requests
import sqlite3
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

# TARGET CHANNEL ID
TARGET_CHANNEL_ID = "4317496781"

# Persistent Storage Path
PERSISTENT_DIR = "data"
DB_NAME = os.path.join(PERSISTENT_DIR, "reseller_bot.db")
os.makedirs(PERSISTENT_DIR, exist_ok=True)

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0)")
    c.execute("CREATE TABLE IF NOT EXISTS auto_channels (channel_id TEXT PRIMARY KEY, user_id INTEGER)")
    conn.commit()
    conn.close()

def get_user_bal(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (uid,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0.0

def update_bal(uid, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, uid))
    conn.commit()
    conn.close()

def get_channel_owner(cid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM auto_channels WHERE channel_id = ?", (cid,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def add_channel(cid, uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO auto_channels (channel_id, user_id) VALUES (?, ?)", (cid, uid))
    conn.commit()
    conn.close()

# ==================== SMM FUNCTIONS ====================
def place_smm_order(link, qty, service_id):
    payload = {"key": SMM_API_KEY, "action": "add", "service": service_id, "link": link, "quantity": qty}
    try:
        r = requests.post(SMM_API_URL, data=payload, timeout=15)
        return r.json()
    except Exception as e:
        logger.error(f"SMM Error: {e}")
        return {"error": str(e)}

# ==================== BOT START ====================
bot = TelegramClient("reseller_session", API_ID, API_HASH)
user_states = {}

@bot.on(events.NewMessage())
async def main_handler(event):
    uid = event.sender_id
    text = event.text.strip() if event.text else ""

    # 1. CHANNEL POST DETECTION (DEBUG MODE)
    if event.is_channel:
        chat_id = str(abs(event.chat_id))
        if chat_id.startswith("100"): chat_id = chat_id[3:]
        
        logger.info(f"POST DETECTED: {chat_id}")
        
        # Immediate Debug Notification to Admin
        await bot.send_message(ADMIN_ID, f"📢 **Post Detected!**\nChannel ID: `{chat_id}`\nEvent ID: `{event.id}`")

        owner_id = get_channel_owner(chat_id)
        if chat_id == TARGET_CHANNEL_ID or owner_id:
            reg_uid = owner_id if owner_id else ADMIN_ID
            try:
                chat = await event.get_chat()
                if hasattr(chat, 'username') and chat.username:
                    post_link = f"https://t.me/{chat.username}/{event.id}"
                    service_id = SMM_SERVICE_ID
                else:
                    post_link = f"https://t.me/c/{chat_id}/{event.id}"
                    service_id = SMM_PRIVATE_SERVICE_ID
                
                cost = (AUTO_VIEW_QTY / 1000) * PRICE_PER_1000
                balance = get_user_bal(reg_uid)
                
                if balance < cost:
                    await bot.send_message(reg_uid, f"⚠️ **Low Balance!**\nPost: {post_link}")
                    return

                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, place_smm_order, post_link, AUTO_VIEW_QTY, service_id)
                
                if res and "order" in res:
                    update_bal(reg_uid, -cost)
                    await bot.send_message(reg_uid, f"✅ **Auto-Order!**\n🔗 {post_link}\n🆔 `{res['order']}`")
                else:
                    await bot.send_message(ADMIN_ID, f"❌ **SMM Panel Error:**\n`{res}`")
            except Exception as e:
                await bot.send_message(ADMIN_ID, f"❌ **Handler Error:**\n`{e}`")
        return

    # 2. PRIVATE MESSAGES (REST OF THE FEATURES)
    if event.is_private:
        if text == "/start":
            bal = get_user_bal(uid)
            welcome_text = (f"🚀 **Welcome to Premium View Booster!**\n\n💰 **Your Balance:** `₹{bal:.2f}`\n📈 **Price:** `₹{PRICE_PER_1000} per 1000 views`")
            buttons = [[Button.inline("🚀 Order Views (Manual)", data="order")],
                       [Button.inline("🤖 Auto-View Setup", data="auto_setup")],
                       [Button.inline("💳 Add Funds", data="add_funds"), Button.inline("📊 My Account", data="account")]]
            if uid == ADMIN_ID: buttons.append([Button.inline("🛠 Admin Panel", data="admin")])
            await event.respond(welcome_text, buttons=buttons)
            return

        if text.startswith("/addbal") and uid == ADMIN_ID:
            try:
                parts = text.split(); tid, amt = int(parts[1]), float(parts[2])
                update_bal(tid, amt); await event.respond(f"✅ Added ₹{amt}")
            except: await event.respond("❌ Usage: `/addbal <id> <amount>`")
            return

        if event.fwd_from:
            try:
                fid = event.fwd_from.from_id
                if hasattr(fid, 'channel_id'):
                    cid = str(fid.channel_id)
                    add_channel(cid, uid)
                    await event.respond(f"✅ **Channel Registered!**\nID: `{cid}`")
                return
            except: pass

        if uid in user_states:
            state = user_states[uid]
            if state == "wait_link":
                user_states[uid] = {"state": "wait_qty", "link": text}
                await event.respond("🔢 **Enter Quantity:**")
            elif isinstance(state, dict) and state.get("state") == "wait_qty":
                try:
                    qty = int(text); link = state["link"]; cost = (qty / 1000) * PRICE_PER_1000
                    balance = get_user_bal(uid)
                    if balance < cost: user_states.pop(uid); return await event.respond("⚠️ Low Balance!")
                    user_states.pop(uid); msg = await event.respond("⏳ Processing...")
                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(None, place_smm_order, link, qty, SMM_PRIVATE_SERVICE_ID if "/c/" in link else SMM_SERVICE_ID)
                    if res and "order" in res:
                        update_bal(uid, -cost); await msg.edit(f"✅ **Order Successful!** ID: `{res['order']}`")
                    else: await msg.edit(f"❌ Failed: {res.get('error')}")
                except: await event.respond("❌ Invalid Quantity.")

@bot.on(events.CallbackQuery())
async def callback(event):
    data = event.data.decode(); uid = event.sender_id
    if data == "order":
        user_states[uid] = "wait_link"; await event.respond("🔗 **Send the Channel Post Link:**")
    elif data == "auto_setup":
        await event.respond("🤖 **Auto-View Setup Instructions...**")
    elif data == "add_funds":
        await event.respond(f"💳 Contact Admin: @YourUsername\nUser ID: `{uid}`")
    elif data == "account":
        bal = get_user_bal(uid); await event.respond(f"👤 **Account Details:**\n\n• **User ID:** `{uid}`\n• **Balance:** `₹{bal:.2f}`")
    elif data == "admin" and uid == ADMIN_ID:
        await event.respond("🛠 **Admin Panel:**\nUse `/addbal <id> <amount>`", buttons=[Button.inline("🔙 Back", data="back")])
    elif data == "back":
        user_states.pop(uid, None)
        bal = get_user_bal(uid)
        welcome_text = (f"🚀 **Welcome back!**\n💰 **Balance:** `₹{bal:.2f}`")
        buttons = [[Button.inline("🚀 Order Views (Manual)", data="order")],
                   [Button.inline("🤖 Auto-View Setup", data="auto_setup")],
                   [Button.inline("💳 Add Funds", data="add_funds"), Button.inline("📊 My Account", data="account")]]
        if uid == ADMIN_ID: buttons.append([Button.inline("🛠 Admin Panel", data="admin")])
        await event.respond(welcome_text, buttons=buttons)

async def main():
    init_db()
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot Started - Debug Mode Active")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
