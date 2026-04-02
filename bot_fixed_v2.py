import telebot
import sqlite3

BOT_TOKEN = "8618418873:AAGj69OdSBQSw9SoezAkard1w11etcFH2gM"
ADMIN_ID = 1181665099

print("🚀 Запуск бота...")
bot = telebot.TeleBot(BOT_TOKEN)

# Хранилище состояний для добавления товара
user_states = {}

def init_db():
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, 
        price INTEGER, 
        quantity INTEGER,
        description TEXT DEFAULT '',
        category TEXT DEFAULT '',
        file_id TEXT DEFAULT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, 
        balance INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, 
        product_name TEXT, 
        price INTEGER,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print("✅ База данных готова")

def get_balance(uid):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

def update_balance(uid, amount):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
    if c.rowcount == 0:
        c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (uid, amount))
    conn.commit()
    conn.close()

def buy_product(pid, uid):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("SELECT name, price, quantity FROM products WHERE id=?", (pid,))
    p = c.fetchone()
    if not p or p[2] <= 0:
        conn.close()
        return False, "Товар закончился"
    balance = get_balance(uid)
    if balance < p[1]:
        conn.close()
        return False, f"Не хватает {p[1] - balance} руб."
    c.execute("UPDATE products SET quantity = quantity - 1 WHERE id=?", (pid,))
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (p[1], uid))
    c.execute("INSERT INTO orders (user_id, product_name, price) VALUES (?, ?, ?)", (uid, p[0], p[1]))
    conn.commit()
    conn.close()
    return True, f"Вы купили {p[0]} за {p[1]} руб."

def delete_product(pid):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (pid,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_all_products_admin():
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products ORDER BY id DESC")
    products = c.fetchall()
    conn.close()
    return products

def get_statistics():
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM products")
    products = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders")
    orders = c.fetchone()[0]
    c.execute("SELECT SUM(price) FROM orders")
    total = c.fetchone()[0] or 0
    conn.close()
    return users, products, orders, total

# Клавиатуры
def main_keyboard(user_id):
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🛍 Каталог", "💰 Баланс")
    kb.add("🛒 Мои покупки", "ℹ️ О нас")
    if user_id == ADMIN_ID:
        kb.add("⚙️ Админ панель")
    return kb

def admin_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("➕ Добавить товар", "🗑 Удалить товар")
    kb.add("📦 Все товары", "📊 Статистика")
    kb.add("👥 Пользователи", "💰 Пополнить баланс")
    kb.add("◀️ Назад")
    return kb

@bot.message_handler(commands=['start'])
def start(m):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (m.chat.id,))
    conn.commit()
    conn.close()
    bot.send_message(
        m.chat.id, 
        f"👋 Привет, {m.from_user.first_name}!\n\n"
        f"Добро пожаловать в магазин!\n"
        f"💰 Ваш баланс: {get_balance(m.chat.id)} руб.",
        reply_markup=main_keyboard(m.chat.id)
    )

@bot.message_handler(func=lambda m: m.text == "🛍 Каталог")
def catalog(m):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE quantity > 0")
    products = c.fetchall()
    conn.close()
    
    if not products:
        bot.send_message(m.chat.id, "😕 Товаров нет в наличии.")
        return
    
    for p in products:
        text = f"📦 <b>{p[1]}</b>\n"
        if p[4]:
            text += f"📝 {p[4]}\n"
        if p[5]:
            text += f"🏷 {p[5]}\n"
        text += f"💰 Цена: {p[2]} руб.\n"
        text += f"📦 Осталось: {p[3]} шт."
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(f"✅ Купить за {p[2]} руб.", callback_data=f"buy_{p[0]}"))
        bot.send_message(m.chat.id, text, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💰 Баланс")
def balance(m):
    bot.send_message(m.chat.id, f"💰 Ваш баланс: {get_balance(m.chat.id)} руб.")

@bot.message_handler(func=lambda m: m.text == "🛒 Мои покупки")
def my_orders(m):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("SELECT product_name, price, date FROM orders WHERE user_id=? ORDER BY date DESC LIMIT 10", (m.chat.id,))
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        bot.send_message(m.chat.id, "📭 У вас пока нет покупок.")
        return
    
    text = "🛒 Ваши покупки:\n\n"
    for o in orders:
        date_str = o[2][:10] if o[2] else "дата неизвестна"
        text += f"📦 {o[0]} - {o[1]} руб.\n📅 {date_str}\n\n"
    bot.send_message(m.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "ℹ️ О нас")
def about(m):
    bot.send_message(
        m.chat.id,
        "ℹ️ <b>Магазин автопродаж</b>\n\n"
        "Мы продаем цифровые товары.\n"
        "После оплаты товар приходит автоматически.\n\n"
        "📞 По вопросам: @support",
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda m: m.text == "⚙️ Админ панель" and m.chat.id == ADMIN_ID)
def admin_panel(m):
    # Очищаем состояние если было
    if m.chat.id in user_states:
        del user_states[m.chat.id]
    bot.send_message(m.chat.id, "⚙️ Админ панель", reply_markup=admin_keyboard())

# Добавить товар
@bot.message_handler(func=lambda m: m.text == "➕ Добавить товар" and m.chat.id == ADMIN_ID)
def add_product_start(m):
    user_states[m.chat.id] = {'step': 'name'}
    msg = bot.send_message(m.chat.id, "📝 Введите название товара:")
    bot.register_next_step_handler(msg, add_product_name)

def add_product_name(m):
    uid = m.chat.id
    
    # Если нажали "Назад"
    if m.text == "◀️ Назад":
        if uid in user_states:
            del user_states[uid]
        bot.send_message(uid, "Главное меню", reply_markup=main_keyboard(uid))
        return
    
    if uid not in user_states:
        bot.send_message(uid, "Главное меню", reply_markup=main_keyboard(uid))
        return
    
    user_states[uid]['name'] = m.text
    user_states[uid]['step'] = 'desc'
    msg = bot.send_message(uid, "📝 Введите описание товара (или 'пропустить'):")
    bot.register_next_step_handler(msg, add_product_desc)

def add_product_desc(m):
    uid = m.chat.id
    
    if m.text == "◀️ Назад":
        if uid in user_states:
            del user_states[uid]
        bot.send_message(uid, "Главное меню", reply_markup=main_keyboard(uid))
        return
    
    if uid not in user_states:
        bot.send_message(uid, "Главное меню", reply_markup=main_keyboard(uid))
        return
    
    desc = m.text if m.text != 'пропустить' else ''
    user_states[uid]['desc'] = desc
    user_states[uid]['step'] = 'category'
    msg = bot.send_message(uid, "🏷 Введите категорию (или 'пропустить'):")
    bot.register_next_step_handler(msg, add_product_category)

def add_product_category(m):
    uid = m.chat.id
    
    if m.text == "◀️ Назад":
        if uid in user_states:
            del user_states[uid]
        bot.send_message(uid, "Главное меню", reply_markup=main_keyboard(uid))
        return
    
    if uid not in user_states:
        bot.send_message(uid, "Главное меню", reply_markup=main_keyboard(uid))
        return
    
    category = m.text if m.text != 'пропустить' else ''
    user_states[uid]['category'] = category
    user_states[uid]['step'] = 'price'
    msg = bot.send_message(uid, "💰 Введите цену (только число):")
    bot.register_next_step_handler(msg, add_product_price)

def add_product_price(m):
    uid = m.chat.id
    
    if m.text == "◀️ Назад":
        if uid in user_states:
            del user_states[uid]
        bot.send_message(uid, "Главное меню", reply_markup=main_keyboard(uid))
        return
    
    if uid not in user_states:
        bot.send_message(uid, "Главное меню", reply_markup=main_keyboard(uid))
        return
    
    try:
        price = int(m.text)
        user_states[uid]['price'] = price
        user_states[uid]['step'] = 'quantity'
        msg = bot.send_message(uid, "📦 Введите количество:")
        bot.register_next_step_handler(msg, add_product_quantity)
    except:
        bot.send_message(uid, "❌ Введите число!")
        msg = bot.send_message(uid, "💰 Введите цену (только число):")
        bot.register_next_step_handler(msg, add_product_price)

def add_product_quantity(m):
    uid = m.chat.id
    
    if m.text == "◀️ Назад":
        if uid in user_states:
            del user_states[uid]
        bot.send_message(uid, "Главное меню", reply_markup=main_keyboard(uid))
        return
    
    if uid not in user_states:
        bot.send_message(uid, "Главное меню", reply_markup=main_keyboard(uid))
        return
    
    try:
        qty = int(m.text)
        state = user_states[uid]
        
        conn = sqlite3.connect('shop.db')
        c = conn.cursor()
        c.execute("INSERT INTO products (name, description, category, price, quantity) VALUES (?, ?, ?, ?, ?)",
                  (state['name'], state['desc'], state['category'], state['price'], qty))
        conn.commit()
        product_id = c.lastrowid
        conn.close()
        
        bot.send_message(uid, f"✅ Товар '{state['name']}' добавлен! (ID: {product_id})")
        del user_states[uid]
        bot.send_message(uid, "Главное меню", reply_markup=main_keyboard(uid))
    except:
        bot.send_message(uid, "❌ Введите число!")
        msg = bot.send_message(uid, "📦 Введите количество:")
        bot.register_next_step_handler(msg, add_product_quantity)

# Удалить товар
@bot.message_handler(func=lambda m: m.text == "🗑 Удалить товар" and m.chat.id == ADMIN_ID)
def delete_product_start(m):
    msg = bot.send_message(m.chat.id, "🗑 Введите ID товара для удаления:\n\nЧтобы узнать ID, нажмите '📦 Все товары'")
    bot.register_next_step_handler(msg, delete_product_by_id)

def delete_product_by_id(m):
    if m.text == "◀️ Назад":
        bot.send_message(m.chat.id, "Главное меню", reply_markup=main_keyboard(m.chat.id))
        return
    
    try:
        pid = int(m.text)
        if delete_product(pid):
            bot.send_message(m.chat.id, f"✅ Товар с ID {pid} успешно удален!")
        else:
            bot.send_message(m.chat.id, f"❌ Товар с ID {pid} не найден!")
    except:
        bot.send_message(m.chat.id, "❌ Введите корректный ID товара!")

# Все товары (админ)
@bot.message_handler(func=lambda m: m.text == "📦 Все товары" and m.chat.id == ADMIN_ID)
def admin_products(m):
    products = get_all_products_admin()
    if not products:
        bot.send_message(m.chat.id, "📦 Нет товаров.")
        return
    
    text = "📋 <b>Все товары:</b>\n\n"
    for p in products:
        text += f"🆔 ID: {p[0]}\n"
        text += f"📦 {p[1]}\n"
        text += f"💰 {p[2]} руб.\n"
        text += f"📦 Остаток: {p[3]} шт.\n"
        text += f"🏷 {p[5] or 'нет категории'}\n"
        text += "─" * 20 + "\n"
    
    bot.send_message(m.chat.id, text, parse_mode='HTML')

# Статистика
@bot.message_handler(func=lambda m: m.text == "📊 Статистика" and m.chat.id == ADMIN_ID)
def stats(m):
    users, products, orders, total = get_statistics()
    text = f"📊 Статистика магазина:\n\n"
    text += f"👥 Пользователей: {users}\n"
    text += f"📦 Товаров: {products}\n"
    text += f"🛒 Заказов: {orders}\n"
    text += f"💰 Выручка: {total} руб."
    bot.send_message(m.chat.id, text)

# Пользователи
@bot.message_handler(func=lambda m: m.text == "👥 Пользователи" and m.chat.id == ADMIN_ID)
def users_list(m):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("SELECT user_id, balance FROM users ORDER BY balance DESC")
    users = c.fetchall()
    conn.close()
    
    text = "👥 Пользователи:\n\n"
    for u in users[:20]:
        text += f"🆔 {u[0]} - 💰 {u[1]} руб.\n"
    bot.send_message(m.chat.id, text)

# Пополнить баланс
@bot.message_handler(func=lambda m: m.text == "💰 Пополнить баланс" and m.chat.id == ADMIN_ID)
def add_balance_start(m):
    msg = bot.send_message(m.chat.id, "Введите ID пользователя и сумму через пробел:\nПример: 1181665099 1000")
    bot.register_next_step_handler(msg, add_balance)

def add_balance(m):
    if m.text == "◀️ Назад":
        bot.send_message(m.chat.id, "Главное меню", reply_markup=main_keyboard(m.chat.id))
        return
    
    try:
        uid, amount = m.text.split()
        amount = int(amount)
        update_balance(int(uid), amount)
        bot.send_message(m.chat.id, f"✅ Баланс пользователя {uid} пополнен на {amount} руб.")
    except:
        bot.send_message(m.chat.id, "❌ Ошибка! Используйте: ID сумма")

# Назад
@bot.message_handler(func=lambda m: m.text == "◀️ Назад" and m.chat.id == ADMIN_ID)
def back_to_main(m):
    # Очищаем состояние если было
    if m.chat.id in user_states:
        del user_states[m.chat.id]
    bot.send_message(m.chat.id, "Главное меню", reply_markup=main_keyboard(m.chat.id))

# Обработчик покупки
@bot.callback_query_handler(func=lambda call: True)
def handle_buy(call):
    if call.data.startswith("buy_"):
        pid = int(call.data.split("_")[1])
        success, msg = buy_product(pid, call.from_user.id)
        if success:
            bot.answer_callback_query(call.id, "✅ Покупка успешна!")
            bot.send_message(call.from_user.id, f"✅ {msg}")
        else:
            bot.answer_callback_query(call.id, msg, show_alert=True)

if __name__ == '__main__':
    init_db()
    
    # Добавляем тестовые товары если их нет
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        products = [
            ("Сумка кожаная", 2500, 10, "Кожаная сумка черного цвета", "Аксессуары"),
            ("Футболка", 1200, 15, "Хлопковая футболка с принтом", "Одежда"),
            ("Кроссовки Nike", 5000, 5, "Оригинальные кроссовки, размер 42", "Обувь"),
            ("Ключ Windows 11", 1500, 100, "Лицензионный ключ активации", "Софт"),
        ]
        for p in products:
            c.execute("INSERT INTO products (name, price, quantity, description, category) VALUES (?, ?, ?, ?, ?)",
                      (p[0], p[1], p[2], p[3], p[4]))
        print("✅ Добавлены тестовые товары")
    conn.commit()
    conn.close()
    
    # Пополняем баланс админа
    update_balance(ADMIN_ID, 10000)
    
    print("✅ Бот готов к работе!")
    print("📱 Откройте Telegram и отправьте /start")
    print("")
    print("🔧 Функции:")
    print("  - 🛍 Каталог товаров")
    print("  - 💰 Баланс пользователя")
    print("  - 🛒 Мои покупки")
    print("  - 🗑 Удаление товаров (админ)")
    print("  - ➕ Добавление товаров (админ)")
    print("  - ◀️ Кнопка 'Назад' работает на всех этапах")
    
    bot.infinity_polling()