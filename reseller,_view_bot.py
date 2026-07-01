import os
import logging
import requests
import aiosqlite
import asyncio
from telethon import TelegramClient, events, Button

# ==================== CONFIGURATION ====================
API_ID = int(os.getenv("API_ID", "24802699"))
API_HASH = os.getenv("API_HASH", "8d13aabfe7e3b2c24ad507edb48f27a5")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8984858421:AAEXIitPHROELbyiVK91x4SDnaBwdVlUYC8")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8211510972"))

# SMM Panel Config
SMM_API_URL = os.getenv("SMM_API_URL", "https://smmmain.com/api/v2")
SMM_API_KEY = os.getenv("SMM_API_KEY", "YOUR_API_KEY")
SMM_SERVICE_ID = os.getenv("SMM_SERVICE_ID", "123") # Service ID for views

# Pricing (Price per 1000 views in your currency, e.g., ₹20)
PRICE_PER_1000 = float(os.getenv("PRICE_PER_1000", "20.0"))

# Persistent Storage Path for Railway
PERSISTENT_DIR = os.getenv("DB_PERSISTENT_DIR", os.path.join(os.getcwd(), "data"))
DB_NAME = os.path.join(PERSISTENT_DIR, "reseller_bot.db")

# Ensure the persistent directory exists
os.makedirs(PERSISTENT_DIR, exist_ok=True)
logger.info(f"Database will be stored at: {DB_NAME}")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = TelegramClient("reseller_session", API_ID, API_HASH)

# ==================== DATABASE ====================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0)")
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
def place_smm_order(link, quantity):
    payload = {
        "key": SMM_API_KEY,
        "action": "add",
        "service": SMM_SERVICE_ID,
        "link": link,
        "quantity": quantity
    }
    try:
        response = requests.post(SMM_API_URL, data=payload)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# ==================== BOT HANDLERS ====================
@bot.on(events.NewMessage(pattern=\'/start\'))
async def start(event):
    uid = event.sender_id
    balance = await get_user(uid)
    
    welcome_text = f"🚀 **Welcome to Premium View Booster!**\n\n💰 **Your Balance:** `₹{balance:.2f}`\n📈 **Price:** `₹{PRICE_PER_1000} per 1000 views`"
    
    buttons = [
        [Button.inline("🚀 Order Views", data="order")],
        [Button.inline("💳 Add Funds", data="add_funds"), Button.inline("📊 My Account", data="account")]
    ]
    
    if uid == ADMIN_ID:
        buttons.append([Button.inline("🛠 Admin Panel", data="admin")])
        
    await event.respond(welcome_text, buttons=buttons)

@bot.on(events.CallbackQuery())
async def callback(event):
    data = event.data.decode()
    uid = event.sender_id
    
    if data == "order":
        user_states[uid] = "wait_link"
        await event.respond("🔗 **Send the Channel Post Link:**\nExample: `https://t.me/c/123456/789` (private) or `https://t.me/channel/789` (public)")
    
    elif data == "add_funds":
        await event.respond(f"💳 **To Add Funds:**\n\nContact Admin: @YourUsername\nSend your User ID: `{uid}`\n\n*Automatic payment integration can be added later!*")
    
    elif data == "account":
        balance = await get_user(uid)
        await event.respond(f"👤 **Account Details:**\n\n• **User ID:** `{uid}`\n• **Balance:** `₹{balance:.2f}`")

    elif data == "admin" and uid == ADMIN_ID:
        await event.respond("🛠 **Admin Panel:**\n\nUse `/addbal <user_id> <amount>` to add funds to a user.", buttons=[Button.inline("🔙 Back", data="back")])

    elif data == "back":
        await start(event)

user_states = {}
@bot.on(events.NewMessage())
async def msg_handler(event):
    uid = event.sender_id
    if uid not in user_states:
        # Handle Admin Commands
        if event.text.startswith("/addbal") and uid == ADMIN_ID:
            try:
                parts = event.text.split()
                target_id = int(parts[1])
                amount = float(parts[2])
                await update_balance(target_id, amount)
                await event.respond(f"✅ Added `₹{amount}` to user `{target_id}`")
                await bot.send_message(target_id, f"🎉 **Funds Added!**\n`₹{amount}` has been added to your balance.")
            except: await event.respond("❌ Usage: `/addbal <user_id> <amount>`")
        return
    
    state = user_states[uid]
    
    if state == "wait_link":
        link = event.text.strip()
        user_states[uid] = {"state": "wait_qty", "link": link}
        await event.respond(f"🔢 **Enter Quantity:**\n(Minimum 100, Price: ₹{PRICE_PER_1000}/1k)")
    
    elif isinstance(state, dict) and state.get("state") == "wait_qty":
        try:
            qty = int(event.text.strip())
            if qty < 100: return await event.respond("❌ Minimum quantity is 100.")
            
            link = state["link"]
            cost = (qty / 1000) * PRICE_PER_1000
            balance = await get_user(uid)
            
            if balance < cost:
                return await event.respond(f"⚠️ **Insufficient Balance!**\nCost: `₹{cost:.2f}`\nYour Balance: `₹{balance:.2f}`\n\nPlease add funds first.")
            
            user_states.pop(uid)
            msg = await event.respond("⏳ **Processing your order...**")
            
            # Place SMM Order
            order = place_smm_order(link, qty)
            
            if "order" in order:
                await update_balance(uid, -cost)
                await msg.edit(f"✅ **Order Successful!**\n\n• **Order ID:** `{order['order']}`\n• **Quantity:** `{qty}`\n• **Cost:** `₹{cost:.2f}`\n\nViews will start increasing shortly!")
            else:
                await msg.edit(f"❌ **Order Failed!**\nError: `{order.get('error', 'Panel Error')}`")
        except ValueError: await event.respond("❌ Please enter a valid number.")

# ==================== RUN ====================
async def main():
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        # Exit or handle the error appropriately
        return
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Reseller Bot Started")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
