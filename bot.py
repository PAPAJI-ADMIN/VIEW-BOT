import os
import logging
import requests
import sqlite3
import asyncio
import datetime
from telethon import TelegramClient, events, Button

# ==================== 💎 PREMIUM CONFIGURATION 💎 ====================
API_ID = int(os.getenv("API_ID", "30208136"))
API_HASH = os.getenv("API_HASH", "8d13aabfe7e3b2c24ad507edb48f27a5")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8eeafab20782b8c9ac67c580c1d36c2c")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8211510972"))
ADMIN_USERNAME = "@YourUsername"

# --- SMM PANEL SETTINGS (SMMFurious - UPI Supported) ---
SMM_API_URL = "https://smmfurious.com/api/v2"
SMM_API_KEY = "21a356d044975d8013d5fe0fda04891fb307d7ac"

# --- SERVICE SETTINGS (TRUE 10s SPEED - FUTURE POSTS) ---
# ID 20957: Telegram Future Post Views [ 5 Posts ]
# This service monitors the channel and sends views instantly upon posting.
SMM_SERVICE_ID = "20130" 

# --- BUSINESS PRICING ---
# Cost is very low, selling at ₹5.00 for the 5-post package
PRICE_PER_PACKAGE = 5.0
AUTO_VIEW_QTY = 100 
POSTS_COUNT = 5

# ==================== 🛠 SYSTEM INITIALIZATION 🛠 ====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PERSISTENT_DIR = "data"
DB_NAME = os.path.join(PERSISTENT_DIR, "premium_reseller_fix.db")

def init_db():
    if not os.path.exists(PERSISTENT_DIR):
        os.makedirs(PERSISTENT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, total_spent REAL DEFAULT 0.0, total_orders INTEGER DEFAULT 0, joined_date TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS auto_channels (channel_id TEXT PRIMARY KEY, user_id INTEGER, active_until_post_id INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS processed_posts (post_id TEXT PRIMARY KEY, timestamp TEXT)")
    conn.commit()
    conn.close()

def db_exec(query, params=(), fetchone=False, commit=False):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchone() if fetchone else c.fetchall()
    except Exception as e:
        logger.error(f"DB Error: {e}")
        return None
    finally:
        conn.close()

# ==================== 🚀 CORE SMM ENGINE 🚀 ====================
async def call_smm_api(link, qty, posts, service_id):
    # For Future Posts, the link should be the channel username or link
    payload = {
        "key": SMM_API_KEY, 
        "action": "add", 
        "service": service_id, 
        "link": link, 
        "quantity": qty,
        "posts": posts
    }
    try:
        loop = asyncio.get_event_loop()
        r = await loop.run_in_executor(None, lambda: requests.post(SMM_API_URL, data=payload, timeout=12))
        return r.json()
    except Exception as e:
        logger.error(f"SMM API Error: {e}")
        return {"error": str(e)}

# ==================== 🤖 PREMIUM BOT ENGINE 🤖 ====================
bot = TelegramClient("premium_final_fix_session", API_ID, API_HASH)

@bot.on(events.NewMessage())
async def handle_messages(event):
    uid = event.sender_id
    if not uid: return

    # --- 1. ULTRA-FAST DETECTION (SUB-10s LOGIC) ---
    if event.is_channel:
        # For Future Posts, we only need to order ONCE. 
        # The panel then handles the next 5 posts automatically.
        return 

    # --- 2. PRIVATE INTERFACE ---
    if event.is_private:
        text = event.text.strip() if event.text else ""
        user = db_exec("SELECT * FROM users WHERE user_id = ?", (uid,), fetchone=True)
        if not user:
            db_exec("INSERT INTO users (user_id, balance, joined_date) VALUES (?, 0.0, ?)", 
                   (uid, datetime.datetime.now().strftime("%Y-%m-%d")), commit=True)
            user = (uid, 0.0, 0.0, 0, datetime.datetime.now().strftime("%Y-%m-%d"))

        if text == "/start":
            welcome = (f"💎 **PREMIUM 10s VIEW BOOSTER** 💎\n\n"
                       f"👤 **User ID:** `{uid}`\n"
                       f"💰 **Balance:** `₹{user[1]:.2f}`\n"
                       f"⚡ **Speed:** `Guaranteed <10 Seconds` (Future Post Mode)")
            buttons = [
                [Button.inline("🚀 Start 10s Views (5 Posts)", data="start_10s")],
                [Button.inline("💳 Add Funds", data="add_funds"), Button.inline("📊 My Statistics", data="stats")],
                [Button.inline("📞 Support", data="support")]
            ]
            if uid == ADMIN_ID: buttons.append([Button.inline("🛠 Admin Panel", data="admin_panel")])
            await event.respond(welcome, buttons=buttons)
            return

        if text.startswith("/addbal") and uid == ADMIN_ID:
            try:
                parts = text.split(); target_id, amount = int(parts[1]), float(parts[2])
                db_exec("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id), commit=True)
                await event.respond(f"✅ Added `₹{amount}` to `{target_id}`.")
                await bot.send_message(target_id, f"🎉 Funds Added: `₹{amount}`")
            except: await event.respond("❌ Usage: `/addbal <id> <amount>`")
            return

@bot.on(events.CallbackQuery())
async def on_callback(event):
    data = event.data.decode(); uid = event.sender_id
    user = db_exec("SELECT * FROM users WHERE user_id = ?", (uid,), fetchone=True)
    
    if data == "start_10s":
        await event.respond("🔗 Please **Forward a post** from the channel where you want 10s views.")
    
    elif data == "add_funds":
        await event.respond(f"💳 **Add Funds:** Send ID `{uid}` to {ADMIN_USERNAME} (UPI Accepted).")
        
    elif data == "stats":
        await event.respond(f"📊 **STATS**\nID: `{uid}`\nBalance: `₹{user[1]:.2f}`\nOrders: `{user[3]}`")
        
    elif data == "support": 
        await event.respond(f"📞 Support: {ADMIN_USERNAME}")
        
    elif data == "admin_panel" and uid == ADMIN_ID:
        await event.respond(f"🛠 **ADMIN PANEL**\nUse `/addbal <id> <amount>`.")

@bot.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.fwd_from))
async def handle_forward(event):
    uid = event.sender_id
    user = db_exec("SELECT balance FROM users WHERE user_id = ?", (uid,), fetchone=True)
    if not user or user[0] < PRICE_PER_PACKAGE:
        return await event.respond("❌ Insufficient Balance! (Need ₹5.00)")
    
    try:
        fid = event.fwd_from.from_id
        if hasattr(fid, 'channel_id'):
            chat = await event.get_chat()
            # Get channel link/username
            channel_entity = await bot.get_entity(fid.channel_id)
            channel_link = f"https://t.me/{channel_entity.username}" if channel_entity.username else f"https://t.me/c/{str(fid.channel_id)[4:]}"
            
            msg = await event.respond("⏳ Activating 10s Instant Views...")
            res = await call_smm_api(channel_link, AUTO_VIEW_QTY, POSTS_COUNT, SMM_SERVICE_ID)
            
            if res and "order" in res:
                db_exec("UPDATE users SET balance = balance - ?, total_spent = total_spent + ?, total_orders = total_orders + 1 WHERE user_id = ?", 
                       (PRICE_PER_PACKAGE, PRICE_PER_PACKAGE, uid), commit=True)
                await msg.edit(f"✅ **10s Views Activated!**\n\n📺 **Channel:** {channel_link}\n📈 **Views:** {AUTO_VIEW_QTY} per post\n📝 **Posts:** Next 5 posts\n🆔 **Order ID:** `{res['order']}`\n\n*Views will hit instantly as soon as you post!*")
            else:
                await msg.edit(f"❌ Failed: {res.get('error')}")
    except Exception as e:
        await event.respond(f"❌ Error: {str(e)}")

# ==================== 🏁 BOT START 🏁 ====================
async def main():
    try:
        init_db()
        await bot.start(bot_token=BOT_TOKEN)
        print("💎 10s SPEED BOT STARTED 💎")
        await bot.run_until_disconnected()
    except Exception as e:
        logger.error(f"FATAL: {e}")
        await asyncio.sleep(5)
        await main()

if __name__ == "__main__":
    try: asyncio.run(main())
    except: pass
