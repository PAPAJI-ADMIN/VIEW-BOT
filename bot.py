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
# ID 2544: Telegram 100% AUTO Post views [5 Future Post] (Best for sub-10s delivery)
# ID 2544: Auto Post views [5 Future Post] (Best for 10s speed)
SMM_SERVICE_ID = "2544" # Telegram 100% AUTO Post views [5 Future Post] (for sub-10s delivery) 
SMM_PRIVATE_SERVICE_ID = "2544" # Telegram 100% AUTO Post views [5 Future Post] (for sub-10s delivery) 

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

    # 1. CHANNEL POST DETECTION (UNIVERSAL MATCHING)
    if event.is_channel:
        # Generate multiple ID formats to match against
        raw_id = str(event.chat_id)
        abs_id = str(abs(event.chat_id))
        no_prefix_id = abs_id[3:] if abs_id.startswith("100") else abs_id
        
        logger.info(f"POST DETECTED: Raw={raw_id}, Abs={abs_id}, Clean={no_prefix_id}")
        
        # Admin Alert for every post (to confirm bot is receiving messages)
        await bot.send_message(ADMIN_ID, f"📢 **Post Detected!**\nRaw ID: `{raw_id}`\nClean ID: `{no_prefix_id}`")

        # Check against hardcoded ID and database
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
            logger.info(f"MATCH FOUND! Owner: {owner_id}")
            try:
                chat = await event.get_chat()
                if hasattr(chat, 'username') and chat.username:
                    post_link = f"https://t.me/{chat.username}/{event.id}"
                    service_id = SMM_SERVICE_ID
                else:
                    post_link = f"https://t.me/c/{no_prefix_id}/{event.id}"
                    service_id = SMM_PRIVATE_SERVICE_ID
                
                cost = (AUTO_VIEW_QTY / 1000) * PRICE_PER_1000
                balance = get_user_bal(owner_id)
                
                if balance < cost:
                    await bot.send_message(owner_id, f"⚠️ **Low Balance!**\nPost: {post_link}")
                    return

                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, place_smm_order, post_link, AUTO_VIEW_QTY, service_id)
                
                if res and "order" in res:
                    update_bal(owner_id, -cost)
                    await bot.send_message(owner_id, f"✅ **Future Post Views Activated!**\n\n🔗 **Post:** {post_link}\n📈 **Views:** `{AUTO_VIEW_QTY}`\n💰 **Cost:** `₹{cost:.2f}`\n🆔 **Order ID:** `{res['order']}`\n\n*Views will appear instantly on your next 5 posts.*")
                else:
                    await bot.send_message(ADMIN_ID, f"❌ **SMM Error:**\n`{res}`")
            except Exception as e:
                await bot.send_message(ADMIN_ID, f"❌ **Error:**\n`{e}`")
        return

    # 2. PRIVATE MESSAGES
    if event.is_private:
        if text == "/start":
            bal = get_user_bal(uid)
            welcome_text = (f"🚀 **Welcome to Premium View Booster!**\n\n💰 **Your Balance:** `₹{bal:.2f}`\n📈 **Price:** `₹{PRICE_PER_1000} per 1000 views` (Future Post Views - Instant)")
            buttons = [[Button.inline("🚀 Order Views (Manual)", data="order")],
                       [Button.inline("🤖 Auto-View Setup", data="auto_setup")],
                       [Button.inline("💳 Add Funds (UPI)", data="add_funds"), Button.inline("📊 My Account", data="account")]]
            if uid == ADMIN_ID: buttons.append([Button.inline("🛠 Admin Panel", data="admin")])
            await event.respond(welcome_text, buttons=buttons)
            return

        if text.startswith("/addbal") and uid == ADMIN_ID:
            try:
                parts = text.split(); tid, amt = int(parts[1]), float(parts[2])
                update_bal(tid, amt); await event.respond(f"✅ Added ₹{amt}")
                await bot.send_message(tid, f"🎉 **Funds Added!**\n`₹{amt}` has been added to your balance.")
            except: await event.respond("❌ Usage: `/addbal <id> <amount>`")
            return

        if event.fwd_from:
            try:
                fid = event.fwd_from.from_id
                if hasattr(fid, 'channel_id'):
                    cid = str(fid.channel_id)
                    add_channel(cid, uid)
                    await event.respond(f"✅ **Channel Registered!**\nID: `{cid}`\n\nअब इस चैनल की हर नई पोस्ट पर ऑटोमैटिक व्यूज आयेंगे।")
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
        await event.respond("🤖 **Auto-View Setup Instructions:**\n\n1. मुझे अपने चैनल में **Admin** बनायें।\n2. चैनल से कोई भी एक पोस्ट मुझे **Forward** करें।\n3. उसके बाद हर नई पोस्ट पर ऑटोमैटिक व्यूज आयेंगे!")
    elif data == "add_funds":
        await event.respond(f"💳 **To Add Funds (UPI):**\n\nContact Admin: @YourUsername\nSend your User ID: `{uid}`")
    elif data == "account":
        bal = get_user_bal(uid); await event.respond(f"👤 **Account Details:**\n\n• **User ID:** `{uid}`\n• **Balance:** `₹{bal:.2f}`")
    elif data == "admin" and uid == ADMIN_ID:
        await event.respond("🛠 **Admin Panel:**\n\nUse `/addbal <id> <amount>` to add funds.", buttons=[Button.inline("🔙 Back", data="back")])
    elif data == "back":
        user_states.pop(uid, None)
        bal = get_user_bal(uid)
        welcome_text = (f"🚀 **Welcome back!**\n💰 **Balance:** `₹{bal:.2f}`")
        buttons = [[Button.inline("🚀 Order Views (Manual)", data="order")],
                   [Button.inline("🤖 Auto-View Setup", data="auto_setup")],
                   [Button.inline("💳 Add Funds (UPI)", data="add_funds"), Button.inline("📊 My Account", data="account")]]
        if uid == ADMIN_ID: buttons.append([Button.inline("🛠 Admin Panel", data="admin")])
        await event.respond(welcome_text, buttons=buttons)

async def main():
    init_db()
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot Started - Universal ID Matching Active")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
