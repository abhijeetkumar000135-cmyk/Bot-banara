import os
import telebot
from telebot import types
import sqlite3
import qrcode
from io import BytesIO
import random
from keep_alive import keep_alive  # 24/7 लाइव रखने के लिए

# --- कॉन्फ़िगरेशन ---
BOT_TOKEN = "8773587737:AAETKKc0UA6PIijkyMPj9xo9BwnonPnNrTQ"
BOT_ID = 8429344650          # आपकी बोट आईडी
ADMIN_USERNAME = "sheinkamallik"  # बिना @ के यूजरनेम (वेरिफिकेशन के लिए आसान)
ADMIN_PASSWORD = "ABHIJEET125"
UPI_ID = "abhijeet06@fam"

bot = telebot.TeleBot(BOT_TOKEN)

# --- डेटाबेस सेटअप ---
def init_db():
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    # यूजर्स टेबल
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)''')
    # प्रोडक्ट्स टेबल
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL, description TEXT, file_id TEXT)''')
    # ऑर्डर्स टेबल
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, user_id INTEGER, product_id INTEGER, utr TEXT, status TEXT)''')
    # एडमिन आईडी स्टोर करने के लिए (डायनामिक वेरिफिकेशन)
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_config (key TEXT PRIMARY KEY, value INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- हेल्पर फंक्शन्स ---
def generate_order_id():
    # Abh-12-67 फॉर्मेट में यूनीक आईडी जनरेट करना
    num1 = random.randint(10, 99)
    num2 = random.randint(10, 99)
    return f"Abh-{num1}-{num2}"

def generate_upi_qr(price, order_id):
    upi_url = f"upi://pay?pa={UPI_ID}&pn=AbhijeetStore&am={price}&cu=INR&tn=Order_{order_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

def get_stored_admin_id():
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM admin_config WHERE key = 'admin_id'")
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def set_stored_admin_id(user_id):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO admin_config (key, value) VALUES ('admin_id', ?)", (user_id,))
    conn.commit()
    conn.close()

# --- स्टेट मैनेजमेंट ---
admin_sessions = {}  # {'user_id': True}
user_states = {}    # स्टेप-बाय-स्टेप इनपुट के लिए

# --- कमांड्स हैंडलर ---

def register_user(message):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (message.from_user.id, message.from_user.username))
    # अगर सही एडमिन यूजरनेम वाला बंदा /start करता है, तो उसकी आईडी ऑटो-सेव हो जाएगी
    if message.from_user.username and message.from_user.username.lower() == ADMIN_USERNAME.lower():
        set_stored_admin_id(message.from_user.id)
    conn.commit()
    conn.close()

@bot.message_handler(commands=['start', 'menu'])
def send_menu(message):
    register_user(message)
    text = "👋 *Welcome to Abhijeet's Digital Store!* \n\nनीचे दिए गए मेनू का उपयोग करें या कमांड्स टाइप करें:\n/services - सभी प्रोडक्ट्स देखें\n/history - अपनी खरीदारी का इतिहास देखें\n/help - सपोर्ट के लिए संपर्क करें"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🛒 Services", "📜 History", "📞 Help", "🔐 Admin Section")
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['services'])
def show_services(message):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, description FROM products")
    products = cursor.fetchall()
    conn.close()
    
    if not products:
        bot.send_message(message.chat.id, "🚫 वर्तमान में कोई प्रोडक्ट उपलब्ध नहीं है।")
        return
        
    for prod in products:
        p_id, name, price, desc = prod
        text = f"📦 *Product:* {name}\n💰 *Price:* ₹{price}\n📝 *Description:* {desc}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text=f"Buy {name} 🛒", callback_data=f"buy_{p_id}"))
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['history'])
def show_history(message):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("SELECT orders.order_id, products.name, products.price, orders.status FROM orders JOIN products ON orders.product_id = products.id WHERE orders.user_id = ?", (message.from_user.id,))
    orders = cursor.fetchall()
    conn.close()
    
    if not orders:
        bot.send_message(message.chat.id, "❌ आपने अभी तक कोई ऑर्डर नहीं दिया है।")
        return
        
    history_text = "📜 *Your Order History:*\n\n"
    for order in orders:
        o_id, p_name, price, status = order
        status_emoji = "✅ Approved" if status == "approved" else ("❌ Cancelled" if status == "cancelled" else "⏳ Pending Verification")
        history_text += f"🆔 *Order ID:* `{o_id}`\n📦 *Product:* {p_name} (₹{price})\n📊 *Status:* {status_emoji}\n\n"
    
    bot.send_message(message.chat.id, history_text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.send_message(message.chat.id, f"📞 किसी भी समस्या या सहायता के लिए एडमिन @{ADMIN_USERNAME} से संपर्क करें।")

# --- टेक्स्ट मैचिंग (कीबोर्ड बटन्स) ---
@bot.message_handler(func=lambda m: m.text in ["🛒 Services", "📜 History", "📞 Help", "🔐 Admin Section"])
def keyboard_handler(message):
    if message.text == "🛒 Services":
        show_services(message)
    elif message.text == "📜 History":
        show_history(message)
    elif message.text == "📞 Help":
        send_help(message)
    elif message.text == "🔐 Admin Section":
        actual_admin_id = get_stored_admin_id()
        if (actual_admin_id and message.from_user.id == actual_admin_id) or admin_sessions.get(message.from_user.id):
            show_admin_panel(message.chat.id)
        else:
            bot.send_message(message.chat.id, "🔑 इस सेक्शन को अनलॉक करने के लिए एडमिन पासवर्ड डालें:")
            user_states[message.from_user.id] = 'waiting_for_password'

# --- पासवर्ड और एडमिन लॉजिक ---
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'waiting_for_password')
def check_password(message):
    if message.text == ADMIN_PASSWORD:
        admin_sessions[message.from_user.id] = True
        set_stored_admin_id(message.from_user.id) # आपकी असली ID को सुरक्षित सेव कर लेगा
        user_states[message.from_user.id] = None
        bot.send_message(message.chat.id, "🔓 पासवर्ड सही है! एडमिन पैनल अनलॉक हो गया।")
        show_admin_panel(message.chat.id)
    else:
        bot.send_message(message.chat.id, "❌ गलत पासवर्ड! दोबारा कोशिश करें।")

def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Add Product", callback_data="admin_add"),
        types.InlineKeyboardButton("➖ Remove Product", callback_data="admin_remove"),
        types.InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")
    )
    bot.send_message(chat_id, "🛠 *Admin Panel*", parse_mode="Markdown", reply_markup=markup)

# --- ब्रॉडकास्ट कमांड (/broadcast <message>) ---
@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    actual_admin_id = get_stored_admin_id()
    if message.from_user.id != actual_admin_id and not admin_sessions.get(message.from_user.id):
        return
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        bot.send_message(message.chat.id, "⚠️ प्रारूप: `/broadcast आपका संदेश यहाँ लिखें`", parse_mode="Markdown")
        return
    execute_broadcast(text, message.from_user.id)

def execute_broadcast(text, admin_id):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    count = 0
    for user in users:
        try:
            bot.send_message(user[0], f"📢 *Important Broadcast:*\n\n{text}", parse_mode="Markdown")
            count += 1
        except Exception:
            pass
    bot.send_message(admin_id, f"✅ ब्रॉडकास्ट पूरा हुआ। {count} यूजर्स को मैसेज भेजा गया।")

# --- कॉलबैक क्वेरी (इनलाइन बटन्स) हैंडलर ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    if call.data.startswith("buy_"):
        p_id = call.data.split("_")[1]
        order_id = generate_order_id()
        
        conn = sqlite3.connect('store.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name, price FROM products WHERE id = ?", (p_id,))
        prod = cursor.fetchone()
        conn.close()
        
        if prod:
            name, price = prod
            qr_img = generate_upi_qr(price, order_id)
            
            conn = sqlite3.connect('store.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO orders (order_id, user_id, product_id, utr, status) VALUES (?, ?, ?, ?, ?)", (order_id, user_id, p_id, 'PENDING', 'pending'))
            conn.commit()
            conn.close()
            
            bot.send_photo(
                call.message.chat.id, 
                qr_img, 
                caption=f"🆔 *Order ID:* `{order_id}`\n📦 *Item:* {name}\n💰 *Amount:* ₹{price}\n\n🛑 ऊपर दिए गए क्यूआर कोड को स्कैन करके पेमेंट करें।\n\n👇 भुगतान करने के बाद, कृपया **12-डिजिट का UTR नंबर** यहाँ टाइप करें:"
            )
            user_states[user_id] = f"waiting_for_utr_{order_id}"
            
    elif call.data == "admin_add":
        bot.send_message(call.message.chat.id, "📝 प्रोडक्ट का नाम भेजें:")
        user_states[user_id] = "add_prod_name"
        
    elif call.data == "admin_remove":
        conn = sqlite3.connect('store.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM products")
        prods = cursor.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup()
        for p in prods:
            markup.add(types.InlineKeyboardButton(p[1], callback_data=f"del_{p[0]}"))
        bot.send_message(call.message.chat.id, "❌ डिलीट करने के लिए प्रोडक्ट चुनें:", reply_markup=markup)
        
    elif call.data.startswith("del_"):
        p_id = call.data.split("_")[1]
        conn = sqlite3.connect('store.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (p_id,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "Product Removed Successfully!")
        bot.edit_message_text("✅ प्रोडक्ट हटा दिया गया है।", call.message.chat.id, call.message.message_id)

    elif call.data == "admin_broadcast":
        bot.send_message(call.message.chat.id, "📢 सभी यूजर्स को भेजा जाने वाला संदेश टाइप करें:")
        user_states[user_id] = "waiting_for_broadcast_text"
        
    elif call.data.startswith("approve_") or call.data.startswith("cancel_"):
        action, order_id = call.data.split("_")
        
        conn = sqlite3.connect('store.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, product_id FROM orders WHERE order_id = ?", (order_id,))
        order_data = cursor.fetchone()
        
        if order_data:
            buyer_id, prod_id = order_data
            cursor.execute("SELECT name, file_id FROM products WHERE id = ?", (prod_id,))
            prod_name, file_id = cursor.fetchone()
            
            if action == "approve":
                cursor.execute("UPDATE orders SET status = 'approved' WHERE order_id = ?", (order_id,))
                conn.commit()
                
                bot.send_message(buyer_id, f"✅ आपका भुगतान स्वीकृत (Approved) हो गया है! Order ID: `{order_id}`\n🎁 यहाँ आपका प्रोडक्ट है:")
                try:
                    bot.send_document(buyer_id, file_id)
                except Exception:
                    bot.send_message(buyer_id, f"📝 *Product Code/Link:* \n`{file_id}`", parse_mode="Markdown")
                
                bot.edit_message_text(f"✅ Order {order_id} Approved!", call.message.chat.id, call.message.message_id)
                
            elif action == "cancel":
                cursor.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = ?", (order_id,))
                conn.commit()
                bot.send_message(buyer_id, f"❌ आपका भुगतान अस्वीकार (Cancelled) कर दिया गया है। Order ID: `{order_id}`।")
                bot.edit_message_text(f"❌ Order {order_id} Cancelled.", call.message.chat.id, call.message.message_id)
                
        conn.close()

# --- यूजर और एडमिन इनपुट प्रोसेसिंग ---
@bot.message_handler(func=lambda m: True, content_types=['text', 'document'])
def handle_all_inputs(message):
    user_id = message.from_user.id
    state = user_states.get(user_id, "")
    actual_admin_id = get_stored_admin_id()
    
    if str(state).startswith("waiting_for_utr_"):
        order_id = state.split("_")[3]
        utr = message.text
        
        if not utr or len(utr) != 12 or not utr.isdigit():
            bot.send_message(message.chat.id, "⚠️ अमान्य UTR! कृपया सटीक 12 अंकों का ट्रांजैक्शन UTR नंबर ही भेजें:")
            return
            
        conn = sqlite3.connect('store.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET utr = ? WHERE order_id = ?", (utr, order_id))
        cursor.execute("SELECT name, price FROM products WHERE id = (SELECT product_id FROM orders WHERE order_id = ?)", (order_id,))
        prod_name, price = cursor.fetchone()
        conn.commit()
        conn.close()
        
        user_states[user_id] = None
        bot.send_message(message.chat.id, f"⏳ धन्यवाद! आपका UTR `{utr}` वेरिफिकेशन के लिए भेज दिया गया है। मैन्युअल वेरिफिकेशन के बाद प्रोडक्ट ऑटोमैटिक मिल जाएगा।")
        
        # एडमिन वेरिफिकेशन के लिए अलर्ट भेजना
        username = f"@{message.from_user.username}" if message.from_user.username else f"[User](tg://user?id={user_id})"
        admin_markup = types.InlineKeyboardMarkup()
        admin_markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{order_id}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}")
        )
        
        # अगर एडमिन ने बोट में कभी भी पासवर्ड डाला है या /start किया है, तो उसे सीधा वेरिफिकेशन मैसेज जाएगा
        if actual_admin_id:
            bot.send_message(
                actual_admin_id, 
                f"🔔 *New Payment Received!*\n\n👤 *Buyer:* {username}\n🆔 *Order ID:* `{order_id}`\n📦 *Product:* {prod_name}\n💰 *Price:* ₹{price}\n🔢 *UTR:* `{utr}`", 
                parse_mode="Markdown", 
                reply_markup=admin_markup
            )
        else:
            print("⚠️ Admin ID still not linked. Admin needs to type password in bot first.")

    elif state == "add_prod_name":
        user_states[user_id] = {"name": message.text, "state": "add_prod_price"}
        bot.send_message(message.chat.id, "💰 प्रोडक्ट का मूल्य (Price in INR) भेजें:")
        
    elif isinstance(state, dict) and state.get("state") == "add_prod_price":
        try:
            price = float(message.text)
            state["price"] = price
            state["state"] = "add_prod_desc"
            user_states[user_id] = state
            bot.send_message(message.chat.id, "📝 प्रोडक्ट का विवरण (Description) भेजें:")
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ कृपया केवल नंबर भेजें ( can be decimal like 150 ):")
            
    elif isinstance(state, dict) and state.get("state") == "add_prod_desc":
        state["desc"] = message.text
        state["state"] = "add_prod_file"
        user_states[user_id] = state
        bot.send_message(message.chat.id, "📂 अब प्रोडक्ट फाइल (APK) अपलोड करें या उसका रिडीम कोड/टेक्स्ट यहाँ टाइप करें:")
        
    elif isinstance(state, dict) and state.get("state") == "add_prod_file":
        if message.content_type == 'document':
            file_id = message.document.file_id
        else:
            file_id = message.text
            
        conn = sqlite3.connect('store.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO products (name, price, description, file_id) VALUES (?, ?, ?, ?)", 
                       (state["name"], state["price"], state["desc"], file_id))
        conn.commit()
        conn.close()
        
        user_states[user_id] = None
        bot.send_message(message.chat.id, "✅ प्रोडक्ट सफलतापूर्वक जोड़ दिया गया है!")

    elif state == "waiting_for_broadcast_text":
        user_states[user_id] = None
        execute_broadcast(message.text, message.from_user.id)

# --- बोट रनिंग लॉजिक ---
if __name__ == '__main__':
    keep_alive()  # वेब सर्वर शुरू करें 
    print("Bot is starting without any lagging...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
  
