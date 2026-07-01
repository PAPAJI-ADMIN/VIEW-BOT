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

# SMM Panel Config - UPDATED TO LUVSMM (UPI SUPPORTED)
# Website: https://luvsmm.com (Add funds via PhonePe/Paytm/GPay)
SMM_API_URL = "https://luvsmm.com/api/v2"
SMM_API_KEY = "de3115e273234223a01a392efef95be5" 

# FASTEST SERVICE IDs FOR LUVSMM (Instant/0-Start)
# ID 423: Telegram Post view - INSTANT⚡| SUPERFAST (₹6.00 approx per 1k)
# ID 2544: Auto Post views [5 Future Post] (Best for 10s speed)
SMM_SERVICE_ID = "423" 
SMM_PRIVATE_SERVICE_ID = "423" 

# Pricing for your users
PRICE_PER_1000 = 25.0 # Selling price
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

    # 1. CHANNEL POST DETECTION
    if event.is_channel:
        raw_id = str(event.chat_id)
        abs_id = str(abs(event.chat_id))
        no_prefix_id = abs_id[3:] if abs_id.startswith("100") else abs_id
        
        owner_id = None
        for cid in [raw_id, abs_id, no_prefix_id, f"-100{no_prefix_id}"]:
            if cid == TARGET_CHANNEL_ID:
                owner_id = ADMIN_ID
                break
            db_owner = get_channel_owner(cid)
            if db_owner:
                owner_id = db_owner
                break
        
        if owner_id:
            try:
                chat = await event.get_chat()
                if hasattr(chat, 'username') and chat.username:
                    post_link = f"https://t.me/{chat.username}/{event.id}"
                else:
                    post_link = f"https://t.me/c/{no_prefix_id}/{event.id}"
                
                cost = (AUTO_VIEW_QTY / 1000) * PRICE_PER_1000
                balance = get_user_bal(owner_id)
                
                if balance < cost:
                    return

                # Using 423 for Instant/Superfast Start
                res = await asyncio.get_event_loop().run_in_executor(None, place_smm_order, post_link, AUTO_VIEW_QTY, SMM_SERVICE_ID)
                
                if res and "order" in res:
                    update_bal(owner_id, -cost)
                    await bot.send_message(owner_id, f"✅ **Instant Views Added!**\n🆔 Order: `{res['order']}`")
            except Exception as e:
                logger.error(f"Error: {e}")
        return

    # 2. PRIVATE MESSAGES
    if event.is_private:
        if text == "/start":
            bal = get_user_bal(uid)
            welcome_text = (f"🚀 **Premium View Booster (UPI Supported)**\n\n💰 **Balance:** `₹{bal:.2f}`\n📈 **Price:** `₹{PRICE_PER_1000}/1k` (Instant)")
            buttons = [[Button.inline("🚀 Order Views", data="order")],
                       [Button.inline("🤖 Auto-View Setup", data="auto_setup")],
                       [Button.inline("💳 Add Funds (UPI)", data="add_funds"), Button.inline("📊 My Account", data="account")]]
            await event.respond(welcome_text, buttons=buttons)
            return
        # ... rest of the handlers ...

async def main():
    init_db()
    await bot.start(bot_token=BOT_TOKEN)
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
