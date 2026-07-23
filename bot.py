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
ADMIN_USERNAME = "@MRADMIN_3"

# --- SMM PANEL SETTINGS (SMM Galaxy - UPI Supported) ---
# Note: Changed to the standard API v2 endpoint for SMM Galaxy
SMM_API_URL = "https://smmgalaxy.com/api/v2"
SMM_API_KEY = "df7666e0a2afd94643d90fb84cad3cbe"

# --- SERVICE SETTINGS (FAST & CHEAP) ---
# ID 14644: Telegram Post Views - Instant Start⚡
SMM_SERVICE_ID = "14644" 

# --- BUSINESS PRICING ---
PRICE_PER_1000 = 30.0 # Your selling price (₹30 for 1000 views)
AUTO_VIEW_QTY = 60
MIN_ORDER = 100

# ==================== 🛠 SYSTEM INITIALIZATION 🛠 ====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PERSISTENT_DIR = "data"
DB_NAME = os.path.join(PERSISTENT_DIR, "premium_reseller_final.db")

def init_db():
    if not os.path.exists(PERSISTENT_DIR):
        os.makedirs(PERSISTENT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, total_spent REAL DEFAULT 0.0, total_orders INTEGER DEFAULT 0, joined_date TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS auto_channels (channel_id TEXT PRIMARY KEY, user_id INTEGER, channel_name TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS processed_posts (post_id TEXT PRIMARY KEY, timestamp TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, user_id INTEGER, link TEXT, qty INTEGER, cost REAL, status TEXT, date TEXT)")
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
async def call_smm_api(link, qty, service_id):
    # Standard SMM Panel API v2 Payload
    payload = {
        "key": SMM_API_KEY, 
        "action": "add", 
        "service": service_id, 
        "link": link, 
        "quantity": qty
    }
    try:
        loop = asyncio.get_event_loop()
        # Using a POST request to the API endpoint
        r = await loop.run_in_executor(None, lambda: requests.post(SMM_API_URL, data=payload, timeout=15))
        response_json = r.json()
        logger.info(f"SMM API Response: {response_json}")
        return response_json
    except Exception as e:
        logger.error(f"SMM API Error: {e}")
        return {"error": str(e)}

# ==================== 🤖 PREMIUM BOT ENGINE 🤖 ====================
bot = TelegramClient("premium_final_complete_session", API_ID, API_HASH)
user_states = {}

@bot.on(events.NewMessage())
async def handle_messages(event):
    uid = event.sender_id
    if not uid: return

    # --- 1. AUTO-DETECTION FOR CHANNELS ---
    if event.is_channel:
        abs_id = str(abs(event.chat_id))
        no_prefix_id = abs_id[3:] if abs_id.startswith("100") else abs_id
        post_uid = f"{no_prefix_id}_{event.id}"
        
        # Check if already processed
        if db_exec("SELECT 1 FROM processed_posts WHERE post_id = ?", (post_uid,), fetchone=True):
            return

        # Check if channel is linked to a user
        owner_data = db_exec("SELECT user_id FROM auto_channels WHERE channel_id IN (?, ?, ?)", 
                            (str(event.chat_id), abs_id, no_prefix_id), fetchone=True)
        
        if owner_data:
            owner_id = owner_data[0]
            db_exec("INSERT INTO processed_posts (post_id, timestamp) VALUES (?, ?)", 
                   (post_uid, datetime.datetime.now().isoformat()), commit=True)
            
            try:
                chat = await event.get_chat()
                # Generate correct post link
                if chat.username:
                    post_link = f"https://t.me/{chat.username}/{event.id}"
                else:
                    post_link = f"https://t.me/c/{no_prefix_id}/{event.id}"
                
                user_info = db_exec("SELECT balance FROM users WHERE user_id = ?", (owner_id,), fetchone=True)
                balance = user_info[0] if user_info else 0.0
                
                cost = (AUTO_VIEW_QTY / 1000) * PRICE_PER_1000
                
                if balance >= cost:
                    res = await call_smm_api(post_link, AUTO_VIEW_QTY, SMM_SERVICE_ID)
                    if res and "order" in res:
                        db_exec("UPDATE users SET balance = balance - ?, total_spent = total_spent + ?, total_orders = total_orders + 1 WHERE user_id = ?", 
                               (cost, cost, owner_id), commit=True)
                        await bot.send_message(owner_id, f"🚀 **Views Sent!**\nPost: {post_link}\nQty: {AUTO_VIEW_QTY}\nCost: ₹{cost:.2f}")
                        await bot.send_message(ADMIN_ID, f"📢 **Admin Alert:** Auto-Order placed for {owner_id}\nLink: {post_link}\nOrder ID: `{res['order']}`")
                    else:
                        await bot.send_message(ADMIN_ID, f"⚠️ **Auto-View Error for {owner_id}:** {res}")
            except Exception as e:
                logger.error(f"Auto-View Processing Error: {e}")
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
            welcome = (f"💎 **PREMIUM VIEW BOOSTER PRO** 💎\n\n"
                       f"👤 **User ID:** `{uid}`\n"
                       f"💰 **Balance:** `₹{user[1]:.2f}`\n"
                       f"⚡ **Speed:** `Instant Start` (₹30/1k)")
            buttons = [
                [Button.inline("🚀 Manual Order", data="manual_order"), Button.inline("⚙️ Auto-View Setup", data="auto_setup")],
                [Button.inline("📊 My Statistics", data="stats"), Button.inline("📜 Order History", data="history")],
                [Button.inline("💳 Add Funds", data="add_funds"), Button.inline("📞 Support", data="support")]
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

        # Linking channel by forwarding a post
        if event.fwd_from:
            try:
                fid = event.fwd_from.from_id
                if hasattr(fid, 'channel_id'):
                    cid = str(fid.channel_id)
                    db_exec("INSERT OR REPLACE INTO auto_channels (channel_id, user_id) VALUES (?, ?)", (cid, uid), commit=True)
                    await event.respond(f"✅ **Channel Linked!** Auto-views (100 qty) activated for every new post.")
            except: pass
            return

        if uid in user_states:
            state = user_states[uid]
            if state == "wait_link":
                user_states[uid] = {"step": "wait_qty", "link": text}
                await event.respond(f"🔢 Enter quantity (Min {MIN_ORDER}):")
            elif isinstance(state, dict) and state.get("step") == "wait_qty":
                try:
                    qty = int(text); link = state["link"]
                    if qty < MIN_ORDER: return await event.respond(f"❌ Min order is {MIN_ORDER}.")
                    cost = (qty / 1000) * PRICE_PER_1000
                    if user[1] < cost: 
                        user_states.pop(uid)
                        return await event.respond("⚠️ Low Balance! Please add funds.")
                    
                    user_states.pop(uid)
                    msg = await event.respond("⏳ Processing your order with SMM Galaxy...")
                    res = await call_smm_api(link, qty, SMM_SERVICE_ID)
                    
                    if res and "order" in res:
                        db_exec("UPDATE users SET balance = balance - ?, total_spent = total_spent + ?, total_orders = total_orders + 1 WHERE user_id = ?", 
                               (cost, cost, uid), commit=True)
                        await msg.edit(f"✅ **Order Successful!**\nOrder ID: `{res['order']}`\nViews: {qty}\nCost: ₹{cost:.2f}")
                    else: 
                        await msg.edit(f"❌ **API Error:** {res.get('error', 'Unknown Error')}\nContact Support if balance was deducted.")
                except: await event.respond("❌ Invalid Quantity. Please enter a number.")
            return

@bot.on(events.CallbackQuery())
async def on_callback(event):
    data = event.data.decode(); uid = event.sender_id
    user = db_exec("SELECT * FROM users WHERE user_id = ?", (uid,), fetchone=True)
    if data == "manual_order":
        user_states[uid] = "wait_link"; await event.respond("🔗 Send the Telegram Post Link:")
    elif data == "auto_setup":
        await event.respond(f"🤖 **Auto-View Setup:**\n1. Add this bot as Admin to your channel.\n2. Forward any post from that channel to this chat.")
    elif data == "add_funds":
        await event.respond(f"💳 **Add Funds:**\nSend your User ID `{uid}` to {ADMIN_USERNAME} for UPI payment details.")
    elif data == "stats":
        await event.respond(f"📊 **USER STATISTICS**\nUser ID: `{uid}`\nBalance: `₹{user[1]:.2f}`\nTotal Orders: `{user[3]}`\nTotal Spent: `₹{user[2]:.2f}`")
    elif data == "history":
        await event.respond("📜 Use /start to see your current balance and options.")
    elif data == "support": await event.respond(f"📞 **Support:** Contact {ADMIN_USERNAME} for any issues.")
    elif data == "admin_panel" and uid == ADMIN_ID:
        await event.respond(f"🛠 **ADMIN PANEL**\nUse `/addbal <id> <amount>` to add funds to a user.")

# ==================== 🏁 BOT START 🏁 ====================
async def main():
    try:
        init_db()
        await bot.start(bot_token=BOT_TOKEN)
        print("💎 PREMIUM SMM BOT STARTED 💎")
        await bot.run_until_disconnected()
    except Exception as e:
        logger.error(f"FATAL ERROR: {e}")
        await asyncio.sleep(5)
        await main()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
