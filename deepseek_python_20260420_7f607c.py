import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# ==================== НАСТРОЙКИ ====================
TOKEN = "ВАШ_ТОКЕН_СЮДА"  # ← ВСТАВЬ ТОКЕН ОТ @BotFather
ADMIN_USER_ID = 123456789   # ← ТВОЙ Telegram ID

# Хранилище данных в файлах Render
DATA_PATH = '/tmp/shop_data/'
os.makedirs(DATA_PATH, exist_ok=True)

# ==================== КОНСТАНТЫ ====================
(NAME, PRICE, DESCRIPTION, PHOTO) = range(4)

# ==================== РАБОТА С ДАННЫМИ ====================
class DataManager:
    def __init__(self, path: str):
        self.path = path
        self.products_file = os.path.join(path, 'products.json')
        self.orders_file = os.path.join(path, 'orders.json')
        self.users_file = os.path.join(path, 'users.json')
        self._load_data()
    
    def _load_data(self):
        if os.path.exists(self.products_file):
            with open(self.products_file, 'r', encoding='utf-8') as f:
                self.products = json.load(f)
        else:
            self.products = {}
            self._save_products()
        
        if os.path.exists(self.orders_file):
            with open(self.orders_file, 'r', encoding='utf-8') as f:
                self.orders = json.load(f)
        else:
            self.orders = {}
            self._save_orders()
        
        if os.path.exists(self.users_file):
            with open(self.users_file, 'r', encoding='utf-8') as f:
                self.users = json.load(f)
        else:
            self.users = {}
            self._save_users()
    
    def _save_products(self):
        with open(self.products_file, 'w', encoding='utf-8') as f:
            json.dump(self.products, f, ensure_ascii=False, indent=2)
    
    def _save_orders(self):
        with open(self.orders_file, 'w', encoding='utf-8') as f:
            json.dump(self.orders, f, ensure_ascii=False, indent=2)
    
    def _save_users(self):
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)
    
    def add_product(self, product_id: str, data: dict):
        self.products[product_id] = data
        self._save_products()
    
    def update_product(self, product_id: str, data: dict):
        self.products[product_id] = data
        self._save_products()
    
    def delete_product(self, product_id: str):
        if product_id in self.products:
            del self.products[product_id]
            self._save_products()
    
    def get_product(self, product_id: str) -> Optional[dict]:
        return self.products.get(product_id)
    
    def get_all_products(self) -> dict:
        return self.products
    
    def add_order(self, order_id: str, data: dict):
        self.orders[order_id] = data
        self._save_orders()
    
    def update_order_status(self, order_id: str, status: str):
        if order_id in self.orders:
            self.orders[order_id]['status'] = status
            self._save_orders()
    
    def get_user_orders(self, user_id: int) -> list:
        return [(oid, data) for oid, data in self.orders.items() if data['user_id'] == user_id]
    
    def get_all_orders(self) -> dict:
        return self.orders
    
    def add_user(self, user_id: int, user_data: dict):
        self.users[str(user_id)] = user_data
        self._save_users()
    
    def get_all_users(self) -> list:
        return [(int(uid), data) for uid, data in self.users.items()]

db = DataManager(DATA_PATH)
carts: Dict[int, Dict[str, int]] = {}

# ==================== КЛАВИАТУРЫ ====================
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🛍️ Каталог", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="cart")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton("ℹ️ О магазине", callback_data="about")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_menu():
    keyboard = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add_product")],
        [InlineKeyboardButton("✏️ Управление товарами", callback_data="admin_manage_products")],
        [InlineKeyboardButton("📋 Все заказы", callback_data="admin_all_orders")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 В главное меню", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В главное меню", callback_data="back_main")]])

def back_to_admin():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]])

def back_to_catalog():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад в каталог", callback_data="catalog")]])

# ==================== ФОРМАТИРОВАНИЕ ====================
def format_product(product_id: str, product: dict) -> str:
    text = f"*{product['name']}*\n\n"
    text += f"💰 Цена: {product['price']} руб.\n"
    if product.get('description'):
        text += f"📝 Описание: {product['description']}\n"
    return text

def format_order(order_id: str, order: dict) -> str:
    status_emoji = {"new": "🆕", "processing": "⚙️", "ready": "✅", "completed": "🏁"}
    emoji = status_emoji.get(order['status'], '❓')
    
    text = f"📦 *Заказ #{order_id}* {emoji}\n\n"
    text += f"📅 Дата: {order['created_at']}\n"
    text += f"👤 Клиент: {order['user_name']}\n"
    if order.get('username'):
        text += f"📱 @{order['username']}\n"
    text += f"\n*Состав заказа:*\n"
    
    total = 0
    for item_id, qty in order['items'].items():
        product = db.get_product(item_id)
        if product:
            item_total = product['price'] * qty
            total += item_total
            text += f"• {product['name']} x{qty} = {item_total} руб.\n"
        else:
            text += f"• [Товар удален] x{qty}\n"
    
    text += f"\n💰 *Итого: {total} руб.*"
    return text

# ==================== КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    db.add_user(user.id, {
        'first_name': user.first_name,
        'username': user.username,
        'last_activity': datetime.now().isoformat()
    })
    
    welcome_text = (
        f"👋 *Добро пожаловать, {user.first_name}!*\n\n"
        f"🛒 Это магазин-бот. Вы можете:\n"
        f"• Смотреть каталог товаров\n"
        f"• Добавлять товары в корзину\n"
        f"• Оформлять заказы\n\n"
        f"После оформления заказа администратор свяжется с вами через Telegram."
    )
    
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return
    
    await update.message.reply_text("🔐 *Админ-панель*", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())

# ==================== ОСНОВНОЙ ОБРАБОТЧИК ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "back_main":
        await query.edit_message_text("🏠 *Главное меню*", parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())
        return
    
    elif data == "catalog":
        products = db.get_all_products()
        if not products:
            text = "🛍️ *Каталог пуст*\n\nТовары скоро появятся!"
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_main())
            return
        
        keyboard = []
        for pid, product in products.items():
            btn_text = f"{product['name']} - {product['price']}₽"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"product_{pid}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
        
        await query.edit_message_text("🛍️ *Каталог товаров*", parse_mode=ParseMode.MARKDOWN, 
                                      reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    elif data.startswith("product_"):
        product_id = data.replace("product_", "")
        product = db.get_product(product_id)
        
        if not product:
            await query.edit_message_text("❌ Товар не найден.", reply_markup=back_to_catalog())
            return
        
        text = format_product(product_id, product)
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить в корзину", callback_data=f"addtocart_{product_id}")],
            [InlineKeyboardButton("◀️ Назад к каталогу", callback_data="catalog")]
        ]
        
        if product.get('photo_file_id'):
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=product['photo_file_id'],
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await query.delete_message()
        else:
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, 
                                          reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    elif data.startswith("addtocart_"):
        product_id = data.replace("addtocart_", "")
        
        if user_id not in carts:
            carts[user_id] = {}
        
        carts[user_id][product_id] = carts[user_id].get(product_id, 0) + 1
        product = db.get_product(product_id)
        
        await query.answer(f"✅ {product['name']} добавлен в корзину!")
        return
    
    elif data == "cart":
        if user_id not in carts or not carts[user_id]:
            await query.edit_message_text("🛒 *Корзина пуста*", parse_mode=ParseMode.MARKDOWN, 
                                          reply_markup=back_to_catalog())
            return
        
        text = "*🛒 Ваша корзина:*\n\n"
        total = 0
        keyboard = []
        
        for product_id, qty in carts[user_id].items():
            product = db.get_product(product_id)
            if product:
                subtotal = product['price'] * qty
                total += subtotal
                text += f"• {product['name']} x{qty} = {subtotal} руб.\n"
                keyboard.append([
                    InlineKeyboardButton(f"➖ {product['name']}", callback_data=f"removeone_{product_id}"),
                    InlineKeyboardButton(f"❌", callback_data=f"removeall_{product_id}")
                ])
        
        text += f"\n💰 *Итого: {total} руб.*"
        keyboard.append([InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout")])
        keyboard.append([InlineKeyboardButton("🗑️ Очистить корзину", callback_data="clear_cart")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="catalog")])
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, 
                                      reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    elif data == "checkout":
        if user_id not in carts or not carts[user_id]:
            await query.edit_message_text("❌ Корзина пуста", reply_markup=back_to_catalog())
            return
        
        order_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(user_id)[-4:]
        
        order_data = {
            'user_id': user_id,
            'user_name': query.from_user.full_name,
            'username': query.from_user.username,
            'items': carts[user_id].copy(),
            'status': 'new',
            'created_at': datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        
        db.add_order(order_id, order_data)
        carts[user_id] = {}
        
        admin_text = f"🔔 *Новый заказ #{order_id}*\n\n"
        admin_text += f"👤 Клиент: {query.from_user.full_name}\n"
        if query.from_user.username:
            admin_text += f"📱 @{query.from_user.username}\n"
        
        keyboard = [[InlineKeyboardButton("📋 К заказу", callback_data=f"admin_order_{order_id}")]]
        
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=admin_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        client_text = (
            f"✅ *Заказ #{order_id} оформлен!*\n\n"
            f"Администратор свяжется с вами в ближайшее время.\n"
            f"Спасибо за заказ! 🛍️"
        )
        
        await query.edit_message_text(client_text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())
        return
    
    elif data == "my_orders":
        orders = db.get_user_orders(user_id)
        
        if not orders:
            await query.edit_message_text("📦 *У вас пока нет заказов*", parse_mode=ParseMode.MARKDOWN, 
                                          reply_markup=back_to_main())
            return
        
        keyboard = []
        for order_id, order in orders:
            status_text = {"new": "Новый", "processing": "В обработке", "ready": "Готов", "completed": "Завершен"}
            status = status_text.get(order['status'], order['status'])
            keyboard.append([
                InlineKeyboardButton(f"Заказ #{order_id} [{status}]", callback_data=f"view_order_{order_id}")
            ])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
        
        await query.edit_message_text("📦 *Ваши заказы:*", parse_mode=ParseMode.MARKDOWN, 
                                      reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    elif data.startswith("view_order_"):
        order_id = data.replace("view_order_", "")
        order = db.orders.get(order_id)
        
        if not order:
            await query.edit_message_text("❌ Заказ не найден", reply_markup=back_to_main())
            return
        
        text = format_order(order_id, order)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_main())
        return
    
    elif data == "about":
        text = (
            "🛒 *О нашем магазине*\n\n"
            "Мы предлагаем качественные товары по доступным ценам.\n\n"
            "📞 *Как заказать:*\n"
            "1. Выберите товары в каталоге\n"
            "2. Добавьте в корзину\n"
            "3. Оформите заказ\n\n"
            "После оформления администратор свяжется с вами через Telegram."
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_main())
        return
    
    elif data == "admin_panel":
        if user_id != ADMIN_USER_ID:
            return
        await query.edit_message_text("🔐 *Админ-панель*", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
        return
    
    elif data == "admin_all_orders":
        if user_id != ADMIN_USER_ID:
            return
        
        orders = db.get_all_orders()
        if not orders:
            await query.edit_message_text("📋 *Нет заказов*", parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_admin())
            return
        
        keyboard = []
        for order_id, order in orders.items():
            status_emoji = {"new": "🆕", "processing": "⚙️", "ready": "✅", "completed": "🏁"}
            emoji = status_emoji.get(order['status'], '')
            keyboard.append([
                InlineKeyboardButton(f"{emoji} Заказ #{order_id}", callback_data=f"admin_order_{order_id}")
            ])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
        
        await query.edit_message_text("📋 *Все заказы*", parse_mode=ParseMode.MARKDOWN, 
                                      reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    elif data.startswith("admin_order_"):
        if user_id != ADMIN_USER_ID:
            return
        
        order_id = data.replace("admin_order_", "")
        order = db.orders.get(order_id)
        
        if not order:
            await query.edit_message_text("❌ Заказ не найден", reply_markup=back_to_admin())
            return
        
        text = format_order(order_id, order)
        
        keyboard = [
            [InlineKeyboardButton("⚙️ В обработку", callback_data=f"orderstatus_{order_id}_processing")],
            [InlineKeyboardButton("✅ Готов", callback_data=f"orderstatus_{order_id}_ready")],
            [InlineKeyboardButton("🏁 Завершен", callback_data=f"orderstatus_{order_id}_completed")],
        ]
        
        if order.get('username'):
            keyboard.append([InlineKeyboardButton("💬 Написать клиенту", url=f"https://t.me/{order['username']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 К списку", callback_data="admin_all_orders")])
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    elif data.startswith("orderstatus_"):
        if user_id != ADMIN_USER_ID:
            return
        
        parts = data.split("_")
        order_id = parts[1]
        new_status = parts[2]
        
        db.update_order_status(order_id, new_status)
        
        order = db.orders.get(order_id)
        if order:
            status_text = {"processing": "в обработке", "ready": "готов", "completed": "завершен"}
            client_text = f"📦 *Статус заказа #{order_id} обновлен*\n\nНовый статус: *{status_text.get(new_status, new_status)}*"
            
            try:
                await context.bot.send_message(
                    chat_id=order['user_id'],
                    text=client_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
        
        await query.answer("✅ Статус обновлен")
        query.data = f"admin_order_{order_id}"
        await button_handler(update, context)
        return
    
    elif data == "admin_stats":
        if user_id != ADMIN_USER_ID:
            return
        
        users_count = len(db.users)
        products_count = len(db.products)
        orders_count = len(db.orders)
        
        status_counts = {"new": 0, "processing": 0, "ready": 0, "completed": 0}
        for order in db.orders.values():
            status = order.get('status', 'new')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        text = f"📊 *Статистика*\n\n"
        text += f"👥 Пользователей: {users_count}\n"
        text += f"🛍️ Товаров: {products_count}\n"
        text += f"📦 Всего заказов: {orders_count}\n"
        text += f"  🆕 Новых: {status_counts['new']}\n"
        text += f"  ⚙️ В обработке: {status_counts['processing']}\n"
        text += f"  ✅ Готовых: {status_counts['ready']}\n"
        text += f"  🏁 Завершенных: {status_counts['completed']}\n"
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_admin())
        return

# ==================== ЗАПУСК ====================
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🛒 Бот магазина запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()