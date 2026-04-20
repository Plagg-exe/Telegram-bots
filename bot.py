import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# НАСТРОЙКИ
TOKEN = "8648569718:AAHj0k7RawW0D7nyv-iOi4j7YlPBc2kn6vU"
ADMIN_USER_ID = 8586031338

# ДАННЫЕ
DATA_PATH = '/tmp/shop_data/'
os.makedirs(DATA_PATH, exist_ok=True)

class DataManager:
    def __init__(self, path):
        self.path = path
        self.products_file = os.path.join(path, 'products.json')
        self.orders_file = os.path.join(path, 'orders.json')
        self.users_file = os.path.join(path, 'users.json')
        self.products = {}
        self.orders = {}
        self.users = {}
        self._load_data()
    
    def _load_data(self):
        if os.path.exists(self.products_file):
            with open(self.products_file, 'r', encoding='utf-8') as f:
                self.products = json.load(f)
        if os.path.exists(self.orders_file):
            with open(self.orders_file, 'r', encoding='utf-8') as f:
                self.orders = json.load(f)
        if os.path.exists(self.users_file):
            with open(self.users_file, 'r', encoding='utf-8') as f:
                self.users = json.load(f)
    
    def _save_products(self):
        with open(self.products_file, 'w', encoding='utf-8') as f:
            json.dump(self.products, f)
    
    def _save_orders(self):
        with open(self.orders_file, 'w', encoding='utf-8') as f:
            json.dump(self.orders, f)
    
    def _save_users(self):
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(self.users, f)
    
    def add_product(self, pid, data):
        self.products[pid] = data
        self._save_products()
    
    def get_product(self, pid):
        return self.products.get(pid)
    
    def get_all_products(self):
        return self.products
    
    def add_order(self, oid, data):
        self.orders[oid] = data
        self._save_orders()
    
    def update_order_status(self, oid, status):
        if oid in self.orders:
            self.orders[oid]['status'] = status
            self._save_orders()
    
    def get_user_orders(self, uid):
        return [(oid, data) for oid, data in self.orders.items() if data['user_id'] == uid]
    
    def get_all_orders(self):
        return self.orders
    
    def add_user(self, uid, data):
        self.users[str(uid)] = data
        self._save_users()
    
    def get_all_users(self):
        return [(int(uid), data) for uid, data in self.users.items()]

db = DataManager(DATA_PATH)
carts = {}

# КЛАВИАТУРЫ
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🛍️ Каталог", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="cart")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_menu():
    keyboard = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton("📋 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")]
    ]
    return InlineKeyboardMarkup(keyboard)

# КОМАНДЫ
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, {'name': user.full_name, 'username': user.username})
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\nДобро пожаловать в магазин!",
        reply_markup=main_menu()
    )

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Нет доступа")
        return
    await update.message.reply_text("🔐 Админ-панель", reply_markup=admin_menu())

# ОБРАБОТЧИК КНОПОК
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "catalog":
        products = db.get_all_products()
        if not products:
            await query.edit_message_text("🛍️ Каталог пуст", reply_markup=main_menu())
            return
        keyboard = []
        for pid, p in products.items():
            keyboard.append([InlineKeyboardButton(f"{p['name']} - {p['price']}₽", callback_data=f"product_{pid}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        await query.edit_message_text("🛍️ *Каталог*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "back":
        await query.edit_message_text("🏠 Главное меню", reply_markup=main_menu())
    
    elif data == "admin_stats":
        if user_id != ADMIN_USER_ID:
            return
        text = f"📊 Статистика:\n👥 Пользователей: {len(db.users)}\n🛍️ Товаров: {len(db.products)}\n📦 Заказов: {len(db.orders)}"
        await query.edit_message_text(text, reply_markup=admin_menu())

# ЗАПУСК
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🛒 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()