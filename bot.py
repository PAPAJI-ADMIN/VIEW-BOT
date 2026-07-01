import os
import logging
import requests
import sqlite3
import asyncio
import datetime
from telethon import TelegramClient, events, Button

# ==================== 💎 PREMIUM CONFIGURATION 💎 ====================
# [!] Credentials restored from your original code to fix the invalid api_id error
API_ID = 30208136
API_HASH = "8d13aabfe7e3b2c24ad507edb48f27a5"
BOT_TOKEN = "8eeafab20782b8c9ac67c580c1d36c2c"
ADMIN_ID = 8211510972
ADMIN_USERNAME = "@YourUsername" # Change this for support

# --- SMM PANEL SETTINGS (LuvSMM - UPI Supported) ---
SMM_API_URL = "https://luvsmm.com/api/v2"
SMM_API_KEY = "de3115e273234223a01a392efef95be5"

# --- SERVICE SETTINGS (ULTRA-FAST 10s START) ---
# ID 638: Telegram Post Views [ Max Unlimited ] | Instant Start (Ultrafast)
SMM_SERVICE_ID = "638" 
SMM_PRIVATE_SERVICE_ID = "638"

# --- BUSINESS PRICING ---
PRICE_PER_1000 = 25.0
AUTO_VIEW_QTY = 100
MIN_ORDER = 10
MAX_ORDER = 100000

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
    payload = {"key": SMM_API_KEY, "action": "add", "service": service_id, "link": link, "quantity": qty}
    try:
        loop = asyncio.get_event_loop()
        r = await loop.run_in_executor(None, lambda: requests.post(SMM_API_URL, data=payload, timeout=12))
        return r.json()
    except Exception as e:
        logger.error(f"SMM API Error: {e}")
        return {"error": str(e)}

# ==================== 🤖 PREMIUM BOT ENGINE 🤖 ====================
# We use the correct credentials and a stable session name
bot = TelegramClient("premium_v2_final_session", API_ID, API_HASH)
user_states = {}

@bot.on(events.NewMessage())
async def handle_messages(event):
    uid = event.sender_id
    if not uid: return

    # --- 1. ULTRA-FAST DETECTION (SUB-10s LOGIC) ---
    if event.is_channel:
        abs_id = str(abs(event.chat_id))
        no_prefix_id = abs_id[3:] if abs_id.startswith("100") else abs_id
        post_uid = f"{no_prefix_id}_{event.id}"
        
        if db_exec("SELECT 1 FROM processed_posts WHERE post_id = ?", (post_uid,), fetchone=True):
            return

        owner_data = db_exec("SELECT user_id FROM auto_channels WHERE channel_id IN (?, ?, ?)", 
                            (str(event.chat_id), abs_id, no_prefix_id), fetchone=True)
        
        # Admin Target Channel Check
        if not owner_data and str(event.chat_id) in ["-1004317496781", "4317496781"]:
            owner_id = ADMIN_ID
        elif owner_data:
            owner_id = owner_data[0]
        else:
            return

        db_exec("INSERT INTO processed_posts (post_id, timestamp) VALUES (?, ?)", 
               (post_uid, datetime.datetime.now().isoformat()), commit=True)
        
        try:
            chat = await event.get_chat()
            post_link = f"https://t.me/{chat.username}/{event.id}" if chat.username else f"https://t.me/c/{no_prefix_id}/{event.id}"
            user_info = db_exec("SELECT balance FROM users WHERE user_id = ?", (owner_id,), fetchone=True)
            balance = user_info[0] if user_info else 0.0
            cost = (AUTO_VIEW_QTY / 1000) * PRICE_PER_1000
            
            if balance < cost:
                await bot.send_message(owner_id, f"❌ **Insufficient Balance!**\n\nPost: {post_link}\nRequired: `₹{cost:.2f}`\nYour Balance: `₹{balance:.2f}`")
                return

            res = await call_smm_api(post_link, AUTO_VIEW_QTY, SMM_SERVICE_ID)
            
            if res and "order" in res:
                order_id = str(res['order'])
                db_exec("UPDATE users SET balance = balance - ?, total_spent = total_spent + ?, total_orders = total_orders + 1 WHERE user_id = ?", 
                       (cost, cost, owner_id), commit=True)
                db_exec("INSERT INTO orders (order_id, user_id, link, qty, cost, status, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (order_id, owner_id, post_link, AUTO_VIEW_QTY, cost, "Success", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                
                success_msg = (f"🚀 **INSTANT BOOST ACTIVATED!**\n\n"
                               f"🔗 **Post:** [View Post]({post_link})\n"
                               f"📈 **Quantity:** `{AUTO_VIEW_QTY}` Views\n"
                               f"💰 **Cost:** `₹{cost:.2f}`\n"
                               f"🆔 **Order ID:** `{order_id}`\n\n"
                               f"✨ *Views will start appearing within 10 seconds!*")
                await bot.send_message(owner_id, success_msg, link_preview=False)
            else:
                await bot.send_message(ADMIN_ID, f"⚠️ **SMM API Error for User {owner_id}:**\n`{res}`")
        except Exception as e:
            logger.error(f"Detection Loop Error: {e}")
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
                       f"Welcome back! Boost your Telegram presence with the fastest views in the market.\n\n"
                       f"👤 **User ID:** `{uid}`\n"
                       f"💰 **Balance:** `₹{user[1]:.2f}`\n"
                       f"⚡ **Speed:** `10-Second Start` (0-Start Service)\n\n"
                       f"Choose an option below to continue:")
            buttons = [
                [Button.inline("🚀 Manual Order", data="manual_order"), Button.inline("🤖 Auto-View Setup", data="auto_setup")],
                [Button.inline("💳 Add Funds", data="add_funds"), Button.inline("📊 My Statistics", data="stats")],
                [Button.inline("📜 Order History", data="history"), Button.inline("📞 Support", data="support")]
            ]
            if uid == ADMIN_ID: buttons.append([Button.inline("🛠 Admin Control Panel", data="admin_panel")])
            await event.respond(welcome, buttons=buttons)
            return

        if text.startswith("/addbal") and uid == ADMIN_ID:
            try:
                parts = text.split()
                target_id, amount = int(parts[1]), float(parts[2])
                db_exec("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id), commit=True)
                await event.respond(f"✅ **Balance Updated!**\nAdded `₹{amount}` to User `{target_id}`.")
                await bot.send_message(target_id, f"🎉 **Payment Received!**\n`₹{amount}` has been added to your wallet. Enjoy boosting!")
            except:
                await event.respond("❌ **Usage:** `/addbal <user_id> <amount>`")
            return

        if event.fwd_from:
            try:
                fwd = event.fwd_from
                if hasattr(fwd.from_id, 'channel_id'):
                    cid = str(fwd.from_id.channel_id)
                    db_exec("INSERT OR REPLACE INTO auto_channels (channel_id, user_id) VALUES (?, ?)", (cid, uid), commit=True)
                    await event.respond(f"✅ **Channel Linked Successfully!**\n\n"
                                       f"📍 **Channel ID:** `{cid}`\n"
                                       f"🚀 **Status:** Active\n\n"
                                       f"Every new post in this channel will now receive **{AUTO_VIEW_QTY} views** automatically.")
                else:
                    await event.respond("❌ Please forward a message from a **Channel**.")
            except Exception as e:
                await event.respond(f"❌ Error linking channel: {e}")
            return

        if uid in user_states:
            state = user_states[uid]
            if state == "wait_link":
                user_states[uid] = {"step": "wait_qty", "link": text}
                await event.respond(f"🔗 **Link Received.**\n\nEnter quantity (Min: {MIN_ORDER}, Max: {MAX_ORDER}):")
            elif isinstance(state, dict) and state.get("step") == "wait_qty":
                try:
                    qty = int(text)
                    if qty < MIN_ORDER or qty > MAX_ORDER:
                        return await event.respond(f"❌ Quantity must be between {MIN_ORDER} and {MAX_ORDER}.")
                    link = state["link"]
                    cost = (qty / 1000) * PRICE_PER_1000
                    if user[1] < cost:
                        user_states.pop(uid)
                        return await event.respond(f"⚠️ **Low Balance!**")
                    user_states.pop(uid)
                    msg = await event.respond("⏳ **Processing...**")
                    res = await call_smm_api(link, qty, SMM_SERVICE_ID)
                    if res and "order" in res:
                        db_exec("UPDATE users SET balance = balance - ?, total_spent = total_spent + ?, total_orders = total_orders + 1 WHERE user_id = ?", 
                               (cost, cost, uid), commit=True)
                        await msg.edit(f"✅ **Order Successful!** ID: `{res['order']}`")
                    else:
                        await msg.edit(f"❌ **Order Failed:** {res.get('error', 'Unknown Error')}")
                except:
                    await event.respond("❌ Please enter a valid number.")
            return

@bot.on(events.CallbackQuery())
async def on_callback(event):
    data = event.data.decode()
    uid = event.sender_id
    user = db_exec("SELECT * FROM users WHERE user_id = ?", (uid,), fetchone=True)
    if data == "manual_order":
        user_states[uid] = "wait_link"
        await event.respond("🔗 **Send the Post Link:**")
    elif data == "auto_setup":
        await event.respond(f"🤖 **Auto-View Setup:**\n1. Add me as Admin.\n2. Forward a post.\n3. Every new post gets `{AUTO_VIEW_QTY}` views.")
    elif data == "add_funds":
        await event.respond(f"💳 **ADD FUNDS (UPI):**\nSend screenshot and ID `{uid}` to {ADMIN_USERNAME}.")
    elif data == "stats":
        await event.respond(f"📊 **STATS**\nID: `{uid}`\nBalance: `₹{user[1]:.2f}`\nSpent: `₹{user[2]:.2f}`")
    elif data == "history":
        orders = db_exec("SELECT order_id, cost, date FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT 5", (uid,))
        if not orders: await event.respond("📜 No orders yet.")
        else:
            history = "📜 **LAST 5 ORDERS**\n\n"
            for o in orders: history += f"🆔 `{o[0]}` | `₹{o[1]:.2f}` | {o[2]}\n"
            await event.respond(history)
    elif data == "support": await event.respond(f"📞 Support: {ADMIN_USERNAME}")
    elif data == "admin_panel" and uid == ADMIN_ID:
        await event.respond(f"🛠 **ADMIN PANEL**\nUse `/addbal <id> <amount>`.")

# ==================== 🏁 BOT START 🏁 ====================
async def main():
    try:
        init_db()
        # Start bot with the correct credentials
        await bot.start(bot_token=BOT_TOKEN)
        print("💎 SMM PREMIUM RESELLER BOT V2 STARTED 💎")
        await bot.run_until_disconnected()
    except Exception as e:
        logger.error(f"FATAL ERROR: {e}")
        await asyncio.sleep(5)
        # Prevent infinite recursion in case of persistent auth error
        if "api_id" not in str(e).lower():
            await main()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except:
        pass
