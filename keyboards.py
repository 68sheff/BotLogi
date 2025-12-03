"""
Клавиатуры для бота
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from database import Button, Category, Subcategory, Item, Product, Promocode
from sqlalchemy.orm import Session
import config


def get_main_keyboard(db: Session, user_id: int = None) -> ReplyKeyboardMarkup:
    """Главная клавиатура (динамическая из БД)"""
    buttons = db.query(Button).filter(Button.is_enabled == True).order_by(Button.position).all()
    builder = ReplyKeyboardBuilder()
    
    for button in buttons:
        builder.add(KeyboardButton(text=button.name))
    
    # Добавляем кнопку админ-панели для админов
    if user_id and user_id in config.ADMIN_IDS:
        builder.add(KeyboardButton(text="🔐 Админ-панель"))
    
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура админ-панели"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🔐 Админ-панель"))
    builder.add(KeyboardButton(text="◀️ Главное меню"))
    return builder.as_markup(resize_keyboard=True)


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Inline клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📊 Статистика", "admin_statistics"),
        ("💳 Платежка", "admin_payments"),
        ("💬 Ответы бота", "admin_responses"),
        ("🔘 Кнопки", "admin_buttons"),
        ("📦 Ассортимент", "admin_catalog"),
        ("📤 Загрузка товаров", "admin_upload"),
        ("👥 Пользователи", "admin_users"),
        ("📢 Рассылка", "admin_broadcast"),
        ("📢 Канал", "admin_channel"),
        ("🔧 Тех. работы", "admin_maintenance"),
        ("📋 Соглашение", "admin_agreement"),
        ("🎟 Промокоды", "admin_promocodes"),
        ("🔔 Уведомления", "admin_notifications"),
    ]
    
    for text, callback_data in buttons:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    builder.adjust(2)
    return builder.as_markup()


def get_categories_keyboard(db: Session) -> InlineKeyboardMarkup:
    """Клавиатура категорий"""
    categories = db.query(Category).filter(Category.is_visible == True).order_by(Category.position).all()
    builder = InlineKeyboardBuilder()
    
    for category in categories:
        builder.add(InlineKeyboardButton(
            text=category.name,
            callback_data=f"category_{category.id}"
        ))
    
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main"))
    builder.adjust(1)
    return builder.as_markup()


def get_subcategories_keyboard(db: Session, category_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подкатегорий"""
    subcategories = db.query(Subcategory).filter(
        Subcategory.category_id == category_id,
        Subcategory.is_visible == True
    ).order_by(Subcategory.position).all()
    
    builder = InlineKeyboardBuilder()
    
    for subcategory in subcategories:
        builder.add(InlineKeyboardButton(
            text=subcategory.name,
            callback_data=f"subcategory_{subcategory.id}"
        ))
    
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_categories"))
    builder.adjust(1)
    return builder.as_markup()


def get_items_keyboard(db: Session, subcategory_id: int) -> InlineKeyboardMarkup:
    """Клавиатура позиций"""
    subcategory = db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
    category_id = subcategory.category_id if subcategory else None
    
    items = db.query(Item).filter(
        Item.subcategory_id == subcategory_id,
        Item.is_visible == True
    ).order_by(Item.position).all()
    
    builder = InlineKeyboardBuilder()
    
    for item in items:
        # Проверяем наличие товара
        available_count = db.query(Product).filter(
            Product.item_id == item.id,
            Product.is_sold == False
        ).count()
        
        # Формируем текст кнопки: Название | цена | кол-во шт
        price_part = f"{item.price:.2f}$"
        qty_part = f"{available_count} шт"
        button_text = f"{item.name} | {price_part} | {qty_part}"
        
        if available_count == 0:
            if item.out_of_stock_behavior == 'hide':
                continue
            elif item.out_of_stock_behavior == 'show_no_button':
                builder.add(InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"item_info_{item.id}"
                ))
                continue
        
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"item_{item.id}"
        ))
    
    if category_id:
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_category_{category_id}"))
    else:
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_categories"))
    builder.adjust(1)
    return builder.as_markup()


def get_item_keyboard(db: Session, item_id: int, user_balance: float) -> InlineKeyboardMarkup:
    """Клавиатура товара"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        return None
    
    builder = InlineKeyboardBuilder()
    
    # Проверяем наличие
    available_count = db.query(Product).filter(
        Product.item_id == item.id,
        Product.is_sold == False
    ).count()
    
    if available_count > 0:
        if item.product_type == 'string':
            # Для строковых товаров - выбор количества
            builder.add(InlineKeyboardButton(text="1 шт", callback_data=f"buy_{item_id}_1"))
            if available_count >= 5:
                builder.add(InlineKeyboardButton(text="5 шт", callback_data=f"buy_{item_id}_5"))
            if available_count >= 10:
                builder.add(InlineKeyboardButton(text="10 шт", callback_data=f"buy_{item_id}_10"))
            builder.add(InlineKeyboardButton(text="Другое", callback_data=f"buy_custom_{item_id}"))
        else:
            # Для файловых товаров - одна кнопка
            builder.add(InlineKeyboardButton(text="Купить", callback_data=f"buy_{item_id}_1"))
    
    # Получаем subcategory_id для кнопки назад
    subcategory_id = item.subcategory_id
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_subcategory_{subcategory_id}"))
    builder.adjust(2)
    return builder.as_markup()


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура профиля"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="profile_balance"))
    builder.add(InlineKeyboardButton(text="📜 История покупок", callback_data="purchase_history"))
    builder.add(InlineKeyboardButton(text="🎟 Активировать промокод", callback_data="activate_promocode"))
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main"))
    builder.adjust(1)
    return builder.as_markup()


def get_purchase_history_keyboard(purchases, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Клавиатура истории покупок"""
    builder = InlineKeyboardBuilder()
    
    start = page * per_page
    end = start + per_page
    page_purchases = purchases[start:end]
    
    for purchase in page_purchases:
        builder.add(InlineKeyboardButton(
            text=f"Заказ #{purchase.id} - {purchase.created_at.strftime('%d.%m.%Y %H:%M')}",
            callback_data=f"purchase_{purchase.id}"
        ))
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"history_page_{page-1}"))
    if end < len(purchases):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"history_page_{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_profile"))
    builder.adjust(1)
    return builder.as_markup()


def get_purchase_keyboard(purchase_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для получения товара из покупки"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📥 Получить товар", callback_data=f"get_product_{purchase_id}"))
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_profile"))
    return builder.as_markup()


def get_admin_catalog_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления ассортиментом"""
    builder = InlineKeyboardBuilder()
    buttons = [
        ("➕ Создать категорию", "admin_create_category"),
        ("📝 Редактировать категорию", "admin_edit_category"),
        ("🗑 Удалить категорию", "admin_delete_category"),
        ("➕ Создать подкатегорию", "admin_create_subcategory"),
        ("📝 Редактировать подкатегорию", "admin_edit_subcategory"),
        ("🗑 Удалить подкатегорию", "admin_delete_subcategory"),
        ("➕ Создать позицию", "admin_create_item"),
        ("📝 Редактировать позицию", "admin_edit_item"),
        ("🗑 Удалить позицию", "admin_delete_item"),
    ]
    
    for text, callback_data in buttons:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
    builder.adjust(2)
    return builder.as_markup()


def get_admin_buttons_keyboard(db: Session) -> InlineKeyboardMarkup:
    """Клавиатура управления кнопками"""
    buttons = db.query(Button).order_by(Button.position).all()
    builder = InlineKeyboardBuilder()
    
    for button in buttons:
        status = "✅" if button.is_enabled else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {button.name}",
            callback_data=f"admin_button_{button.id}"
        ))
    
    builder.add(InlineKeyboardButton(text="➕ Добавить кнопку", callback_data="admin_add_button"))
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
    builder.adjust(1)
    return builder.as_markup()


def get_admin_promocodes_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления промокодами"""
    builder = InlineKeyboardBuilder()
    buttons = [
        ("➕ Создать промокод", "admin_create_promocode"),
        ("📝 Редактировать промокод", "admin_edit_promocode"),
        ("🗑 Удалить промокод", "admin_delete_promocode"),
        ("📊 Статистика промокодов", "admin_promocode_stats"),
    ]
    
    for text, callback_data in buttons:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
    builder.adjust(2)
    return builder.as_markup()


def get_confirm_keyboard(action: str, item_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    builder = InlineKeyboardBuilder()
    if item_id:
        builder.add(InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{action}_{item_id}"))
    else:
        builder.add(InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{action}"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_{action}"))
    return builder.as_markup()

