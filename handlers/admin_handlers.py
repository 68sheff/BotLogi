"""
Обработчики для админов
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import (
    User, Category, Subcategory, Item, Product, Purchase, Payment,
    Promocode, PromocodeActivation, Button, BotResponse, Setting, Log, get_db
)
import keyboards as kb
import utils
import config
from datetime import datetime
import json
import csv
import io
import os
import asyncio


router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    return user_id in config.ADMIN_IDS


class AdminStates(StatesGroup):
    # Управление ответами
    editing_response = State()
    
    # Управление кнопками
    creating_button_name = State()
    editing_button_name = State()
    editing_button_action = State()
    editing_button_position = State()
    
    # Ассортимент
    creating_category = State()
    editing_category_name = State()
    editing_category_description = State()
    editing_category_photo = State()
    editing_category_desc = State()
    creating_subcategory = State()
    editing_subcategory_name = State()
    editing_subcategory_photo = State()
    editing_subcategory_desc = State()
    creating_item = State()
    editing_item_name = State()
    editing_item_price = State()
    editing_item_description = State()
    
    # Загрузка товаров
    uploading_products = State()
    
    # Пользователи
    searching_user = State()
    editing_user_balance = State()
    blocking_user = State()
    setting_block_type = State()
    setting_block_reason = State()
    
    # Рассылка
    broadcasting = State()
    
    # Промокоды
    creating_promocode = State()
    editing_promocode_code = State()
    editing_promocode_amount = State()
    editing_promocode_max_activations = State()
    editing_promocode_expires_at = State()
    creating_promocode_user = State()
    
    # Настройки
    setting_maintenance_text = State()
    setting_channel_id = State()
    setting_cryptobot_token = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Открыть админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer(config.TEXTS["admin_only"])
        return
    
    # Очищаем состояние, если оно было установлено
    await state.clear()
    
    keyboard = kb.get_admin_panel_keyboard()
    await message.answer(config.ADMIN_TEXTS["panel"], reply_markup=keyboard)


@router.message(F.text == "🔐 Админ-панель")
async def show_admin_panel(message: Message, state: FSMContext):
    """Показать админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer(config.TEXTS["admin_only"])
        return
    
    # Очищаем состояние, если оно было установлено
    await state.clear()
    
    keyboard = kb.get_admin_panel_keyboard()
    await message.answer(config.ADMIN_TEXTS["panel"], reply_markup=keyboard)


# ========== СТАТИСТИКА ==========

@router.callback_query(F.data == "admin_statistics")
async def show_statistics(callback: CallbackQuery):
    """Показать статистику"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        stats_text = utils.format_statistics(db)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📊 Экспорт статистики", callback_data="admin_export_stats"),
            InlineKeyboardButton(text="👥 Экспорт пользователей", callback_data="admin_export_users")
        ], [
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")
        ]])
        await callback.message.answer(stats_text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "admin_export_stats")
async def export_statistics(callback: CallbackQuery):
    """Экспорт статистики"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        purchases = db.query(Purchase).all()
        
        # CSV экспорт
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "User ID", "Item ID", "Quantity", "Price", "Date"])
        
        for purchase in purchases:
            writer.writerow([
                purchase.id,
                purchase.user_id,
                purchase.item_id,
                purchase.quantity,
                purchase.total_price,
                purchase.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ])
        
        file_content = output.getvalue().encode('utf-8-sig')
        file = BufferedInputFile(file_content, filename="statistics.csv")
        await callback.message.answer_document(file)
        await callback.answer("Статистика экспортирована")
    finally:
        db.close()


@router.callback_query(F.data == "admin_export_users")
async def export_users(callback: CallbackQuery):
    """Экспорт пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        users = db.query(User).all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["User ID", "Username", "Balance", "Total Deposits", "Created At"])
        
        for user in users:
            writer.writerow([
                user.user_id,
                user.username or "",
                user.balance,
                user.total_deposits,
                user.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ])
        
        file_content = output.getvalue().encode('utf-8-sig')
        file = BufferedInputFile(file_content, filename="users.csv")
        await callback.message.answer_document(file)
        await callback.answer("Пользователи экспортированы")
    finally:
        db.close()


# ========== УПРАВЛЕНИЕ ОТВЕТАМИ БОТА ==========

@router.callback_query(F.data == "admin_responses")
async def show_responses_menu(callback: CallbackQuery):
    """Меню управления ответами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        responses = db.query(BotResponse).all()
        text = "💬 Управление ответами бота:\n\n"
        
        builder = InlineKeyboardBuilder()
        response_keys = ["start", "buy", "profile", "faq", "support", "user_agreement", "purchase_success", 
                        "product_out_of_stock", "maintenance", "block_appeal"]
        
        # Добавляем стандартные ответы (показываем все, даже если записи нет в БД)
        for key in response_keys:
            builder.add(InlineKeyboardButton(
                text=f"✏️ {key}",
                callback_data=f"admin_edit_response_{key}"
            ))
        
        # Добавляем ответы для кастомных кнопок
        custom_responses = db.query(BotResponse).filter(BotResponse.key.like("button_%")).all()
        for response in custom_responses:
            action = response.key.replace("button_", "")
            builder.add(InlineKeyboardButton(
                text=f"✏️ Кнопка: {action}",
                callback_data=f"admin_edit_response_{response.key}"
            ))
        
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
        builder.adjust(1)
        
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_edit_response_"))
async def edit_response(callback: CallbackQuery, state: FSMContext):
    """Редактирование ответа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    key = callback.data.replace("admin_edit_response_", "")
    db = next(get_db())
    try:
        response = db.query(BotResponse).filter(BotResponse.key == key).first()
        if response:
            await callback.message.answer(
                f"Текущий текст для '{key}':\n\n{response.text}\n\nОтправьте новый текст:"
            )
        else:
            await callback.message.answer(f"Отправьте текст для '{key}':")
        
        await state.set_state(AdminStates.editing_response)
        await state.update_data(response_key=key)
        await callback.answer()
    finally:
        db.close()


@router.message(AdminStates.editing_response, F.photo)
async def save_response_with_photo(message: Message, state: FSMContext):
    """Сохранение ответа с фото"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    key = data.get("response_key")
    
    db = next(get_db())
    try:
        response = db.query(BotResponse).filter(BotResponse.key == key).first()
        photo_id = message.photo[-1].file_id if message.photo else None
        text = message.caption or ""
        
        if response:
            response.text = text
            response.photo = photo_id
        else:
            response = BotResponse(key=key, text=text, photo=photo_id)
            db.add(response)
        
        db.commit()
        utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
            "action": "edit_response",
            "key": key
        })
        
        await message.answer("✅ Ответ с фото сохранен!")
        await state.clear()
    finally:
        db.close()


@router.message(AdminStates.editing_response)
async def save_response(message: Message, state: FSMContext):
    """Сохранение ответа"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    key = data.get("response_key")
    
    db = next(get_db())
    try:
        response = db.query(BotResponse).filter(BotResponse.key == key).first()
        if response:
            response.text = message.text or ""
        else:
            response = BotResponse(key=key, text=message.text or "")
            db.add(response)
        
        db.commit()
        utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
            "action": "edit_response",
            "key": key
        })
        
        await message.answer("✅ Ответ сохранен!")
        await state.clear()
    finally:
        db.close()


# ========== УПРАВЛЕНИЕ КНОПКАМИ ==========

@router.callback_query(F.data == "admin_buttons")
async def show_buttons_menu(callback: CallbackQuery):
    """Меню управления кнопками"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    keyboard = kb.get_admin_buttons_keyboard(next(get_db()))
    await callback.message.answer("🔘 Управление кнопками:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_add_button")
async def add_button(callback: CallbackQuery, state: FSMContext):
    """Добавление новой кнопки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    await state.set_state(AdminStates.creating_button_name)
    await callback.message.answer("Введите название новой кнопки:")
    await callback.answer()


@router.message(AdminStates.creating_button_name)
async def save_button_name(message: Message, state: FSMContext):
    """Сохранение названия кнопки и запрос действия"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text or message.text.startswith('/'):
        return
    
    button_name = message.text.strip()
    await state.set_state(AdminStates.editing_button_action)
    await state.update_data(button_name=button_name)
    
    # Список доступных действий
    actions = ["buy", "profile", "faq", "support", "balance", "user_agreement"]
    text = "Выберите действие для кнопки:\n\n"
    text += "buy - Купить\n"
    text += "profile - Профиль\n"
    text += "faq - FAQ\n"
    text += "support - Поддержка\n"
    text += "balance - Пополнить баланс\n"
    text += "user_agreement - Соглашение\n\n"
    text += "Или введите действие вручную:"
    
    await message.answer(text)


@router.message(AdminStates.editing_button_action)
async def save_button_action(message: Message, state: FSMContext):
    """Сохранение действия кнопки и создание кнопки"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text or message.text.startswith('/'):
        return
    
    action = message.text.strip().lower()
    data = await state.get_data()
    button_name = data.get("button_name")
    
    db = next(get_db())
    try:
        # Получаем максимальную позицию
        max_pos = db.query(Button).count()
        
        button = Button(
            name=button_name,
            action=action,
            position=max_pos,
            is_enabled=True
        )
        db.add(button)
        db.commit()
        
        utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
            "action": "create_button",
            "button_id": button.id
        })
        
        await message.answer(f"✅ Кнопка '{button_name}' создана!")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_button_") & ~F.data.startswith("admin_button_edit_") & ~F.data.startswith("admin_button_toggle_") & ~F.data.startswith("admin_button_delete_") & ~F.data.startswith("admin_add_button"))
async def edit_button_menu(callback: CallbackQuery):
    """Меню редактирования кнопки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    # Парсим button_id из формата admin_button_123
    parts = callback.data.split("_")
    if len(parts) >= 3:
        try:
            button_id = int(parts[2])
        except ValueError:
            await callback.answer("Ошибка: неверный формат")
            return
    else:
        await callback.answer("Ошибка: неверный формат")
        return
    db = next(get_db())
    try:
        button = db.query(Button).filter(Button.id == button_id).first()
        if not button:
            await callback.answer("Кнопка не найдена")
            return
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="✏️ Изменить название",
            callback_data=f"admin_button_edit_name_{button_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="⚙️ Изменить действие",
            callback_data=f"admin_button_edit_action_{button_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="↕️ Изменить порядок",
            callback_data=f"admin_button_edit_position_{button_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="✅ Включить" if not button.is_enabled else "❌ Выключить",
            callback_data=f"admin_button_toggle_{button_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"admin_button_delete_{button_id}"
        ))
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_buttons"))
        builder.adjust(1)
        
        await callback.message.answer(
            f"Кнопка: {button.name}\nДействие: {button.action}\nПозиция: {button.position}\nСтатус: {'Включена' if button.is_enabled else 'Выключена'}",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_button_toggle_"))
async def toggle_button(callback: CallbackQuery):
    """Включить/выключить кнопку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    button_id = int(callback.data.split("_")[3])
    db = next(get_db())
    try:
        button = db.query(Button).filter(Button.id == button_id).first()
        if button:
            button.is_enabled = not button.is_enabled
            db.commit()
            await callback.answer("✅ Изменено")
            await show_buttons_menu(callback)
        else:
            await callback.answer("Кнопка не найдена")
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_button_edit_name_"))
async def edit_button_name(callback: CallbackQuery, state: FSMContext):
    """Редактирование названия кнопки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    button_id = int(callback.data.split("_")[3])
    await state.set_state(AdminStates.editing_button_name)
    await state.update_data(button_id=button_id)
    await callback.message.answer("Введите новое название кнопки:")
    await callback.answer()


@router.message(AdminStates.editing_button_name)
async def save_button_name(message: Message, state: FSMContext):
    """Сохранение названия кнопки"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text or message.text.startswith('/'):
        return
    
    data = await state.get_data()
    button_id = data.get("button_id")
    new_name = message.text.strip()
    
    db = next(get_db())
    try:
        button = db.query(Button).filter(Button.id == button_id).first()
        if button:
            button.name = new_name
            db.commit()
            
            utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                "action": "edit_button_name",
                "button_id": button_id
            })
            
            await message.answer(f"✅ Название кнопки изменено на '{new_name}'")
            await state.clear()
        else:
            await message.answer("❌ Кнопка не найдена")
            await state.clear()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_button_edit_action_"))
async def edit_button_action(callback: CallbackQuery, state: FSMContext):
    """Редактирование действия кнопки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    button_id = int(callback.data.split("_")[3])
    await state.set_state(AdminStates.editing_button_action)
    await state.update_data(button_id=button_id)
    
    text = "Введите новое действие для кнопки:\n\n"
    text += "Стандартные действия:\n"
    text += "buy - Купить\n"
    text += "profile - Профиль\n"
    text += "faq - FAQ\n"
    text += "support - Поддержка\n"
    text += "balance - Пополнить баланс\n"
    text += "user_agreement - Соглашение\n\n"
    text += "Или введите кастомное действие:"
    
    await callback.message.answer(text)
    await callback.answer()


@router.message(AdminStates.editing_button_action)
async def save_button_action(message: Message, state: FSMContext):
    """Сохранение действия кнопки"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text or message.text.startswith('/'):
        return
    
    data = await state.get_data()
    button_id = data.get("button_id")
    new_action = message.text.strip().lower()
    
    db = next(get_db())
    try:
        button = db.query(Button).filter(Button.id == button_id).first()
        if button:
            old_action = button.action
            button.action = new_action
            db.commit()
            
            # Если действие кастомное (не стандартное), создаем ответ бота для него
            standard_actions = ["buy", "profile", "faq", "support", "balance", "user_agreement"]
            if new_action not in standard_actions:
                # Проверяем, есть ли уже ответ для этого действия
                response = db.query(BotResponse).filter(BotResponse.key == f"button_{new_action}").first()
                if not response:
                    # Создаем дефолтный ответ
                    response = BotResponse(
                        key=f"button_{new_action}",
                        text=f"Ответ для кнопки '{button.name}'"
                    )
                    db.add(response)
                    db.commit()
            
            utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                "action": "edit_button_action",
                "button_id": button_id,
                "old_action": old_action,
                "new_action": new_action
            })
            
            await message.answer(f"✅ Действие кнопки изменено на '{new_action}'")
            if new_action not in standard_actions:
                await message.answer(f"💡 Вы можете настроить ответ для этой кнопки в разделе 'Ответы бота' (ключ: button_{new_action})")
            await state.clear()
        else:
            await message.answer("❌ Кнопка не найдена")
            await state.clear()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_button_delete_"))
async def delete_button(callback: CallbackQuery):
    """Удаление кнопки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    button_id = int(callback.data.split("_")[3])
    db = next(get_db())
    try:
        button = db.query(Button).filter(Button.id == button_id).first()
        if button:
            button_name = button.name
            db.delete(button)
            db.commit()
            
            utils.log_action(db, "admin_action", admin_id=callback.from_user.id, data={
                "action": "delete_button",
                "button_id": button_id
            })
            
            await callback.answer(f"✅ Кнопка '{button_name}' удалена")
            await show_buttons_menu(callback)
        else:
            await callback.answer("❌ Кнопка не найдена")
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_button_edit_position_"))
async def edit_button_position(callback: CallbackQuery, state: FSMContext):
    """Редактирование позиции кнопки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    button_id = int(callback.data.split("_")[3])
    await state.set_state(AdminStates.editing_button_position)
    await state.update_data(button_id=button_id)
    await callback.message.answer("Введите новую позицию кнопки (число, чем меньше - тем выше):")
    await callback.answer()


@router.message(AdminStates.editing_button_position)
async def save_button_position(message: Message, state: FSMContext):
    """Сохранение позиции кнопки"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text or message.text.startswith('/'):
        return
    
    try:
        new_position = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректное число")
        return
    
    data = await state.get_data()
    button_id = data.get("button_id")
    
    db = next(get_db())
    try:
        button = db.query(Button).filter(Button.id == button_id).first()
        if button:
            button.position = new_position
            db.commit()
            
            utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                "action": "edit_button_position",
                "button_id": button_id,
                "new_position": new_position
            })
            
            await message.answer(f"✅ Позиция кнопки изменена на {new_position}")
            await state.clear()
        else:
            await message.answer("❌ Кнопка не найдена")
            await state.clear()
    finally:
        db.close()


# ========== АССОРТИМЕНТ ==========

@router.callback_query(F.data == "admin_catalog")
async def show_catalog_menu(callback: CallbackQuery):
    """Меню управления ассортиментом"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    keyboard = kb.get_admin_catalog_keyboard()
    await callback.message.answer("📦 Управление ассортиментом:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_create_category")
async def create_category(callback: CallbackQuery, state: FSMContext):
    """Создание категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    await state.set_state(AdminStates.creating_category)
    await callback.message.answer("Введите название категории:")
    await callback.answer()


@router.message(AdminStates.creating_category, F.photo)
async def save_category_with_photo(message: Message, state: FSMContext):
    """Сохранение категории с фото"""
    if not is_admin(message.from_user.id):
        return
    
    db = next(get_db())
    try:
        max_pos = db.query(Category).count()
        photo_id = message.photo[-1].file_id if message.photo else None
        
        category = Category(
            name=message.caption or "Без названия",
            photo=photo_id,
            position=max_pos
        )
        db.add(category)
        db.commit()
        
        utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
            "action": "create_category",
            "category_id": category.id
        })
        
        await message.answer(f"✅ Категория '{category.name}' создана!")
        await state.clear()
    finally:
        db.close()


@router.message(AdminStates.creating_category)
async def save_category_name(message: Message, state: FSMContext):
    """Сохранение названия категории"""
    if not is_admin(message.from_user.id):
        return
    
    db = next(get_db())
    try:
        # Получаем максимальную позицию
        max_pos = db.query(Category).count()
        
        category = Category(
            name=message.text,
            position=max_pos
        )
        db.add(category)
        db.commit()
        
        utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
            "action": "create_category",
            "category_id": category.id
        })
        
        await message.answer(f"✅ Категория '{category.name}' создана!")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data == "admin_create_subcategory")
async def create_subcategory(callback: CallbackQuery, state: FSMContext):
    """Создание подкатегории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        categories = db.query(Category).all()
        if not categories:
            await callback.message.answer("Сначала создайте категории")
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        for category in categories:
            builder.add(InlineKeyboardButton(
                text=category.name,
                callback_data=f"admin_create_subcat_{category.id}"
            ))
        
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_catalog"))
        builder.adjust(1)
        
        await callback.message.answer("Выберите категорию для подкатегории:", reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_create_subcat_"))
async def create_subcategory_for_category(callback: CallbackQuery, state: FSMContext):
    """Создание подкатегории для выбранной категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    category_id = int(callback.data.split("_")[3])
    await state.set_state(AdminStates.creating_subcategory)
    await state.update_data(category_id=category_id)
    await callback.message.answer("Введите название подкатегории (можно отправить фото с подписью):")
    await callback.answer()


@router.message(AdminStates.creating_subcategory, F.photo)
async def save_subcategory_with_photo(message: Message, state: FSMContext):
    """Сохранение подкатегории с фото"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    category_id = data.get("category_id")
    
    db = next(get_db())
    try:
        max_pos = db.query(Subcategory).filter(Subcategory.category_id == category_id).count()
        photo_id = message.photo[-1].file_id if message.photo else None
        
        subcategory = Subcategory(
            category_id=category_id,
            name=message.caption or "Без названия",
            photo=photo_id,
            position=max_pos
        )
        db.add(subcategory)
        db.commit()
        
        utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
            "action": "create_subcategory",
            "subcategory_id": subcategory.id
        })
        
        await message.answer(f"✅ Подкатегория '{subcategory.name}' создана!")
        await state.clear()
    finally:
        db.close()


@router.message(AdminStates.creating_subcategory)
async def save_subcategory_name(message: Message, state: FSMContext):
    """Сохранение названия подкатегории"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    category_id = data.get("category_id")
    
    db = next(get_db())
    try:
        max_pos = db.query(Subcategory).filter(Subcategory.category_id == category_id).count()
        
        subcategory = Subcategory(
            category_id=category_id,
            name=message.text,
            position=max_pos
        )
        db.add(subcategory)
        db.commit()
        
        utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
            "action": "create_subcategory",
            "subcategory_id": subcategory.id
        })
        
        await message.answer(f"✅ Подкатегория '{subcategory.name}' создана!")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data == "admin_create_item")
async def create_item(callback: CallbackQuery, state: FSMContext):
    """Создание позиции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        categories = db.query(Category).all()
        if not categories:
            await callback.message.answer("Сначала создайте категории")
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        
        # Добавляем категории (для позиций без подкатегории)
        for category in categories:
            builder.add(InlineKeyboardButton(
                text=f"📁 {category.name}",
                callback_data=f"admin_create_item_cat_{category.id}"
            ))
        
        # Добавляем подкатегории
        subcategories = db.query(Subcategory).all()
        for subcategory in subcategories:
            category = subcategory.category
            builder.add(InlineKeyboardButton(
                text=f"  └ {category.name} > {subcategory.name}",
                callback_data=f"admin_create_item_subcat_{subcategory.id}"
            ))
        
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_catalog"))
        builder.adjust(1)
        
        await callback.message.answer("Выберите куда добавить позицию:\n\n📁 - напрямую в категорию\n└ - в подкатегорию", reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_create_item_cat_"))
async def create_item_for_category(callback: CallbackQuery, state: FSMContext):
    """Создание позиции напрямую в категории (без подкатегории)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    category_id = int(callback.data.split("_")[4])
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📝 Строковый товар", callback_data=f"admin_item_type_string_cat_{category_id}"))
    builder.add(InlineKeyboardButton(text="📁 Файловый товар", callback_data=f"admin_item_type_file_cat_{category_id}"))
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_create_item"))
    
    await callback.message.answer("Выберите тип товара:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_create_item_subcat_"))
async def create_item_for_subcategory(callback: CallbackQuery, state: FSMContext):
    """Создание позиции для выбранной подкатегории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    subcategory_id = int(callback.data.split("_")[4])
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📝 Строковый товар", callback_data=f"admin_item_type_string_sub_{subcategory_id}"))
    builder.add(InlineKeyboardButton(text="📁 Файловый товар", callback_data=f"admin_item_type_file_sub_{subcategory_id}"))
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_create_item"))
    
    await callback.message.answer("Выберите тип товара:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_item_type_"))
async def set_item_type(callback: CallbackQuery, state: FSMContext):
    """Установка типа товара и запрос названия"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    parts = callback.data.split("_")
    product_type = parts[3]  # string или file
    target_type = parts[4]   # cat или sub
    target_id = int(parts[5])
    
    await state.set_state(AdminStates.creating_item)
    if target_type == "cat":
        await state.update_data(category_id=target_id, subcategory_id=None, product_type=product_type)
    else:
        await state.update_data(subcategory_id=target_id, category_id=None, product_type=product_type)
    await callback.message.answer(f"Введите название позиции (тип: {product_type}):")
    await callback.answer()


@router.message(AdminStates.creating_item)
async def save_item_name(message: Message, state: FSMContext):
    """Сохранение названия позиции"""
    if not is_admin(message.from_user.id):
        return
    
    # Обработка отмены
    if message.text and message.text.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        await message.answer("❌ Создание позиции отменено")
        return
    
    data = await state.get_data()
    subcategory_id = data.get("subcategory_id")
    product_type = data.get("product_type")
    
    if not message.text or not message.text.strip():
        await message.answer("❌ Название не может быть пустым. Введите название позиции:")
        return
    
    await state.set_state(AdminStates.editing_item_price)
    await state.update_data(
        item_name=message.text.strip(),
        subcategory_id=subcategory_id,
        product_type=product_type
    )
    await message.answer("Введите цену товара (число, например: 10.5):\n\n💡 Для отмены отправьте /cancel")


@router.message(AdminStates.editing_item_description, F.photo)
async def save_item_with_photo(message: Message, state: FSMContext):
    """Сохранение позиции с фото"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    editing_existing = data.get("editing_existing", False)
    item_id = data.get("item_id")
    
    if editing_existing and item_id:
        # Редактирование существующей позиции
        description = message.caption or ""
        photo_id = message.photo[-1].file_id if message.photo else None
        
        db = next(get_db())
        try:
            item = db.query(Item).filter(Item.id == item_id).first()
            if item:
                if description.strip():
                    item.description = description
                if photo_id:
                    item.photo = photo_id
                db.commit()
                
                utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                    "action": "edit_item_photo_desc",
                    "item_id": item_id
                })
                
                await message.answer("✅ Описание и фото обновлены!")
            await state.clear()
        finally:
            db.close()
    else:
        # Создание новой позиции
        subcategory_id = data.get("subcategory_id")
        product_type = data.get("product_type")
        item_name = data.get("item_name")
        price = data.get("item_price")
        description = message.caption or ""
        photo_id = message.photo[-1].file_id if message.photo else None
        
        if not description.strip():
            await message.answer("Описание обязательно! Введите описание в подписи к фото:")
            return
        
        db = next(get_db())
        try:
            category_id = data.get("category_id")
            
            if subcategory_id:
                max_pos = db.query(Item).filter(Item.subcategory_id == subcategory_id).count()
            else:
                max_pos = db.query(Item).filter(Item.category_id == category_id, Item.subcategory_id == None).count()
            
            item = Item(
                subcategory_id=subcategory_id,
                category_id=category_id,
                name=item_name,
                description=description,
                price=price,
                product_type=product_type,
                photo=photo_id,
                position=max_pos
            )
            db.add(item)
            db.commit()
            
            utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                "action": "create_item",
                "item_id": item.id
            })
            
            await message.answer(f"✅ Позиция '{item.name}' создана!")
            await state.clear()
        finally:
            db.close()


@router.message(AdminStates.editing_item_description)
async def save_item_description(message: Message, state: FSMContext):
    """Сохранение описания и создание позиции"""
    if not is_admin(message.from_user.id):
        return
    
    # Обработка отмены
    if message.text and message.text.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        await message.answer("❌ Создание позиции отменено")
        return
    
    if not message.text or not message.text.strip():
        await message.answer("❌ Описание обязательно! Введите описание:\n\n💡 Для отмены отправьте /cancel")
        return
    
    data = await state.get_data()
    description = message.text.strip()
    editing_existing = data.get("editing_existing", False)
    item_id = data.get("item_id")
    
    db = next(get_db())
    try:
        if editing_existing and item_id:
            # Обновление описания существующей позиции
            item = db.query(Item).filter(Item.id == item_id).first()
            if item:
                item.description = description
                db.commit()
                
                utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                    "action": "edit_item_description",
                    "item_id": item_id
                })
                
                await message.answer("✅ Описание обновлено!")
            await state.clear()
            return
        
        # Создание новой позиции
        subcategory_id = data.get("subcategory_id")
        category_id = data.get("category_id")
        product_type = data.get("product_type")
        item_name = data.get("item_name")
        price = data.get("item_price")
        
        # Проверка наличия всех необходимых данных
        if (not subcategory_id and not category_id) or not product_type or not item_name or price is None:
            await message.answer("❌ Ошибка: не все данные сохранены. Начните создание позиции заново.")
            await state.clear()
            db.close()
            return
        
        if subcategory_id:
            max_pos = db.query(Item).filter(Item.subcategory_id == subcategory_id).count()
        else:
            max_pos = db.query(Item).filter(Item.category_id == category_id, Item.subcategory_id == None).count()
        
        item = Item(
            subcategory_id=subcategory_id,
            category_id=category_id,
            name=item_name,
            description=description,
            price=price,
            product_type=product_type,
            position=max_pos
        )
        db.add(item)
        db.commit()
        
        utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
            "action": "create_item",
            "item_id": item.id
        })
        
        await message.answer(f"✅ Позиция '{item.name}' создана!")
        await state.clear()
    finally:
        db.close()


# ========== РЕДАКТИРОВАНИЕ ПОЗИЦИИ ==========

@router.callback_query(F.data == "admin_edit_item")
async def edit_item_menu(callback: CallbackQuery):
    """Меню редактирования позиции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        items = db.query(Item).all()
        if not items:
            await callback.message.answer("Нет позиций для редактирования")
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        for item in items:
            subcategory = item.subcategory
            category = subcategory.category if subcategory else None
            text = f"{item.name}"
            if category and subcategory:
                text = f"{category.name} > {subcategory.name} > {item.name}"
            builder.add(InlineKeyboardButton(
                text=text,
                callback_data=f"admin_edit_item_{item.id}"
            ))
        
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_catalog"))
        builder.adjust(1)
        
        await callback.message.answer("Выберите позицию для редактирования:", reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_edit_item_"))
async def edit_item(callback: CallbackQuery, state: FSMContext):
    """Редактирование позиции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    item_id = int(callback.data.split("_")[3])
    db = next(get_db())
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            await callback.answer("Позиция не найдена")
            return
        
        text = f"📦 Позиция: {item.name}\n\n"
        text += f"Описание: {item.description or 'Нет описания'}\n"
        text += f"Цена: {item.price:.2f} USDT\n"
        text += f"Тип: {item.product_type}\n\n"
        text += "Что хотите изменить?"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="✏️ Название", callback_data=f"admin_item_edit_name_{item_id}"))
        builder.add(InlineKeyboardButton(text="📝 Описание", callback_data=f"admin_item_edit_desc_{item_id}"))
        builder.add(InlineKeyboardButton(text="💰 Цена", callback_data=f"admin_item_edit_price_{item_id}"))
        builder.add(InlineKeyboardButton(text="📷 Фото", callback_data=f"admin_item_edit_photo_{item_id}"))
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_edit_item"))
        builder.adjust(2)
        
        if item.photo:
            await callback.message.answer_photo(item.photo, caption=text, reply_markup=builder.as_markup())
        else:
            await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_item_edit_name_"))
async def edit_item_name(callback: CallbackQuery, state: FSMContext):
    """Редактирование названия позиции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    item_id = int(callback.data.split("_")[4])
    await state.set_state(AdminStates.editing_item_name)
    await state.update_data(item_id=item_id)
    await callback.message.answer("Введите новое название:")
    await callback.answer()


@router.message(AdminStates.editing_item_name)
async def save_item_name_edit(message: Message, state: FSMContext):
    """Сохранение нового названия позиции"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    item_id = data.get("item_id")
    
    db = next(get_db())
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if item:
            item.name = message.text
            db.commit()
            
            utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                "action": "edit_item_name",
                "item_id": item_id
            })
            
            await message.answer("✅ Название обновлено!")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_item_edit_desc_"))
async def edit_item_description_menu(callback: CallbackQuery, state: FSMContext):
    """Редактирование описания позиции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    item_id = int(callback.data.split("_")[4])
    await state.set_state(AdminStates.editing_item_description)
    await state.update_data(item_id=item_id, editing_existing=True)
    await callback.message.answer("Введите новое описание (можно отправить фото с подписью):")
    await callback.answer()


@router.message(AdminStates.editing_item_description, F.photo)
async def save_item_description_with_photo(message: Message, state: FSMContext):
    """Сохранение описания с фото"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    item_id = data.get("item_id")
    editing_existing = data.get("editing_existing", False)
    
    if editing_existing and item_id:
        # Редактирование существующей позиции
        description = message.caption or ""
        photo_id = message.photo[-1].file_id if message.photo else None
        
        if not description.strip():
            await message.answer("Описание обязательно! Введите описание:")
            return
        
        db = next(get_db())
        try:
            item = db.query(Item).filter(Item.id == item_id).first()
            if item:
                item.description = description
                if photo_id:
                    item.photo = photo_id
                db.commit()
                
                utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                    "action": "edit_item_description",
                    "item_id": item_id
                })
                
                await message.answer("✅ Описание и фото обновлены!")
            await state.clear()
        finally:
            db.close()
    else:
        # Создание новой позиции - уже обработано выше
        pass


@router.callback_query(F.data.startswith("admin_item_edit_price_"))
async def edit_item_price_menu(callback: CallbackQuery, state: FSMContext):
    """Редактирование цены позиции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    item_id = int(callback.data.split("_")[4])
    await state.set_state(AdminStates.editing_item_price)
    await state.update_data(item_id=item_id, editing_existing=True)
    await callback.message.answer("Введите новую цену:")
    await callback.answer()


@router.message(AdminStates.editing_item_price)
async def save_item_price(message: Message, state: FSMContext):
    """Сохранение цены позиции и запрос описания"""
    if not is_admin(message.from_user.id):
        return
    
    # Обработка отмены
    if message.text and message.text.lower() in ['/cancel', 'отмена', 'cancel']:
        await state.clear()
        await message.answer("❌ Создание позиции отменено")
        return
    
    # Проверяем, что это не команда или кнопка
    if not message.text or message.text.startswith('/'):
        return
    
    data = await state.get_data()
    editing_existing = data.get("editing_existing", False)
    item_id = data.get("item_id")
    
    try:
        price = float(message.text.replace(',', '.'))
        if price < 0:
            await message.answer("❌ Цена не может быть отрицательной. Введите положительное число:")
            return
    except ValueError:
        await message.answer("❌ Введите корректное число для цены (например: 10.50 или 10):")
        return
    
    if editing_existing and item_id:
        # Редактирование существующей позиции
        db = next(get_db())
        try:
            item = db.query(Item).filter(Item.id == item_id).first()
            if item:
                item.price = price
                db.commit()
                
                utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                    "action": "edit_item_price",
                    "item_id": item_id
                })
                
                await message.answer("✅ Цена обновлена!")
            await state.clear()
        finally:
            db.close()
    else:
        # Создание новой позиции - запрос описания
        # Сохраняем все предыдущие данные
        await state.set_state(AdminStates.editing_item_description)
        await state.update_data(
            item_price=price,
            editing_existing=False,
            subcategory_id=data.get("subcategory_id"),
            product_type=data.get("product_type"),
            item_name=data.get("item_name")
        )
        await message.answer("Введите описание товара (обязательно):\n\n💡 Для отмены отправьте /cancel")


@router.callback_query(F.data.startswith("admin_item_edit_photo_"))
async def edit_item_photo(callback: CallbackQuery, state: FSMContext):
    """Редактирование фото позиции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    item_id = int(callback.data.split("_")[4])
    await state.set_state(AdminStates.editing_item_description)
    await state.update_data(item_id=item_id, editing_existing=True, editing_photo_only=True)
    await callback.message.answer("Отправьте новое фото:")
    await callback.answer()


# ========== ЗАГРУЗКА ТОВАРОВ ==========

@router.callback_query(F.data == "admin_upload")
async def show_upload_menu(callback: CallbackQuery):
    """Меню загрузки товаров"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        items = db.query(Item).all()
        if not items:
            await callback.message.answer("Сначала создайте позиции в ассортименте")
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        for item in items:
            builder.add(InlineKeyboardButton(
                text=f"{item.name} ({item.product_type})",
                callback_data=f"admin_upload_item_{item.id}"
            ))
        
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
        builder.adjust(1)
        
        await callback.message.answer("Выберите позицию для загрузки товаров:", reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_upload_item_"))
async def upload_item_products(callback: CallbackQuery, state: FSMContext):
    """Загрузка товаров для позиции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    item_id = int(callback.data.split("_")[3])
    db = next(get_db())
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            await callback.answer("Позиция не найдена")
            return
        
        await state.set_state(AdminStates.uploading_products)
        await state.update_data(item_id=item_id)
        
        if item.product_type == 'string':
            await callback.message.answer(
                f"Отправьте .txt файл с логами для позиции '{item.name}'.\n"
                "Каждая строка файла будет одним товаром."
            )
        else:
            await callback.message.answer(
                f"Отправьте файл для позиции '{item.name}'."
            )
        await callback.answer()
    finally:
        db.close()


@router.message(AdminStates.uploading_products, F.document)
async def process_uploaded_file(message: Message, state: FSMContext):
    """Обработка загруженного файла"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    item_id = data.get("item_id")
    
    db = next(get_db())
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            await message.answer("Позиция не найдена")
            await state.clear()
            return
        
        file = await message.bot.get_file(message.document.file_id)
        
        if item.product_type == 'string':
            # Для строковых товаров - загружаем .txt и разбиваем по строкам
            if not message.document.file_name.endswith('.txt'):
                await message.answer("Для строковых товаров нужен .txt файл")
                await state.clear()
                return
            
            # Скачиваем файл
            file_path = config.UPLOADS_DIR / f"{item_id}_{datetime.now().timestamp()}.txt"
            await message.bot.download_file(file.file_path, file_path)
            
            # Читаем и создаем товары
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            count = 0
            for line in lines:
                line = line.strip()
                if line:
                    product = Product(
                        item_id=item_id,
                        content=line
                    )
                    db.add(product)
                    count += 1
            
            db.commit()
            
            utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                "action": "upload_products",
                "item_id": item_id,
                "count": count
            })
            
            await message.answer(f"✅ Загружено {count} товаров!")
        else:
            # Для файловых товаров - сохраняем файл
            file_path = config.UPLOADS_DIR / f"{item_id}_{datetime.now().timestamp()}_{message.document.file_name}"
            await message.bot.download_file(file.file_path, file_path)
            
            product = Product(
                item_id=item_id,
                file_path=str(file_path),
                file_id=message.document.file_id
            )
            db.add(product)
            db.commit()
            
            utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                "action": "upload_product",
                "item_id": item_id
            })
            
            await message.answer("✅ Файл загружен!")
        
        await state.clear()
    finally:
        db.close()


# ========== ПЛАТЕЖКА ==========

@router.callback_query(F.data == "admin_payments")
async def show_payments_menu(callback: CallbackQuery):
    """Меню управления платежкой"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        total_payments = db.query(Payment).filter(Payment.status == 'paid').count()
        total_amount = sum(p.amount for p in db.query(Payment).filter(Payment.status == 'paid').all())
        pending_payments = db.query(Payment).filter(Payment.status == 'pending').count()
        
        text = f"""💳 Управление платежкой

✅ Оплачено платежей: {total_payments}
💰 Общая сумма: {total_amount:.2f} USDT
⏳ Ожидают оплаты: {pending_payments}

Токен CryptoBot: {'✅ Настроен' if config.CRYPTOBOT_TOKEN else '❌ Не настроен'}"""
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⚙️ Настроить токен", callback_data="admin_set_cryptobot_token"))
        builder.add(InlineKeyboardButton(text="📋 История платежей", callback_data="admin_payment_history"))
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
        builder.adjust(1)
        
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "admin_set_cryptobot_token")
async def set_cryptobot_token(callback: CallbackQuery, state: FSMContext):
    """Настройка токена CryptoBot"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    await state.set_state(AdminStates.setting_cryptobot_token)
    await callback.message.answer("Отправьте токен CryptoBot:")
    await callback.answer()


@router.message(AdminStates.setting_cryptobot_token)
async def save_cryptobot_token(message: Message, state: FSMContext):
    """Сохранение токена CryptoBot"""
    if not is_admin(message.from_user.id):
        return
    
    token = message.text.strip()
    db = next(get_db())
    try:
        utils.set_setting(db, "cryptobot_token", token)
        # Также обновляем в config (для текущей сессии)
        config.CRYPTOBOT_TOKEN = token
        
        utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
            "action": "set_cryptobot_token"
        })
        
        await message.answer("✅ Токен CryptoBot сохранен!")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data == "admin_payment_history")
async def show_payment_history(callback: CallbackQuery):
    """История платежей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        payments = db.query(Payment).order_by(Payment.created_at.desc()).limit(20).all()
        
        if not payments:
            await callback.message.answer("История платежей пуста")
            await callback.answer()
            return
        
        text = "📋 Последние платежи:\n\n"
        for payment in payments:
            user = db.query(User).filter(User.id == payment.user_id).first()
            status_emoji = "✅" if payment.status == 'paid' else "⏳" if payment.status == 'pending' else "❌"
            text += f"{status_emoji} {payment.amount:.2f} USDT - User {user.user_id if user else 'N/A'}\n"
            text += f"   {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_payments"))
        
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


# ========== ПОЛЬЗОВАТЕЛИ ==========

@router.callback_query(F.data == "admin_users")
async def show_users_menu(callback: CallbackQuery, state: FSMContext):
    """Меню управления пользователями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    await state.set_state(AdminStates.searching_user)
    await callback.message.answer("Введите для поиска:\n- ID пользователя (число)\n- Username (@username или username)")
    await callback.answer()


@router.message(AdminStates.searching_user)
async def search_user(message: Message, state: FSMContext):
    """Поиск пользователя"""
    if not is_admin(message.from_user.id):
        return
    
    search_query = message.text.strip()
    db = next(get_db())
    try:
        user = None
        
        # Если начинается с @, ищем по username
        if search_query.startswith('@'):
            username = search_query[1:]  # Убираем @
            user = db.query(User).filter(User.username == username).first()
        # Если это число, ищем по user_id
        elif search_query.isdigit():
            user_id = int(search_query)
            user = db.query(User).filter(User.user_id == user_id).first()
        # Иначе пытаемся найти по username без @
        else:
            user = db.query(User).filter(User.username == search_query).first()
        
        if not user:
            await message.answer("Пользователь не найден. Попробуйте:\n- ID пользователя (число)\n- Username (@username или username)")
            await state.clear()
            return
        
        text = utils.format_user_info(user)
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"admin_edit_balance_{user.id}"))
        block_text = "🚫 Заблокировать"
        if user.is_blocked:
            block_type_text = "тихий" if user.block_type == 'silent' else "обычный"
            block_text = f"✅ Разблокировать ({block_type_text})"
        builder.add(InlineKeyboardButton(
            text=block_text,
            callback_data=f"admin_toggle_block_{user.id}"
        ))
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
        builder.adjust(1)
        
        await message.answer(text, reply_markup=builder.as_markup())
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_edit_balance_"))
async def edit_user_balance(callback: CallbackQuery, state: FSMContext):
    """Изменение баланса пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    user_db_id = int(callback.data.split("_")[3])
    await state.set_state(AdminStates.editing_user_balance)
    await state.update_data(user_db_id=user_db_id)
    await callback.message.answer("Введите новый баланс:")
    await callback.answer()


@router.message(AdminStates.editing_user_balance)
async def save_user_balance(message: Message, state: FSMContext):
    """Сохранение баланса пользователя"""
    if not is_admin(message.from_user.id):
        return
    
    # Проверяем, что это не команда или кнопка
    if not message.text or message.text.startswith('/'):
        return
    
    try:
        balance = float(message.text.replace(',', '.'))
        if balance < 0:
            await message.answer("❌ Баланс не может быть отрицательным. Введите положительное число:")
            return
        
        data = await state.get_data()
        user_db_id = data.get("user_db_id")
        
        if not user_db_id:
            await message.answer("❌ Ошибка: пользователь не найден. Попробуйте снова.")
            await state.clear()
            return
        
        db = next(get_db())
        try:
            user = db.query(User).filter(User.id == user_db_id).first()
            if user:
                user.balance = balance
                db.commit()
                
                utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                    "action": "edit_user_balance",
                    "user_id": user.user_id,
                    "new_balance": balance
                })
                
                await message.answer(f"✅ Баланс пользователя {user.user_id} изменен на {balance:.2f} USDT")
            else:
                await message.answer("❌ Пользователь не найден")
            await state.clear()
        finally:
            db.close()
    except ValueError:
        await message.answer("❌ Введите корректное число для баланса (например: 100.50 или 100):")
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении баланса: {str(e)}")
        await state.clear()


@router.callback_query(F.data.startswith("admin_toggle_block_"))
async def toggle_user_block(callback: CallbackQuery, state: FSMContext):
    """Блокировка/разблокировка пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    user_db_id = int(callback.data.split("_")[3])
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_db_id).first()
        if user:
            if user.is_blocked:
                # Разблокировка
                user.is_blocked = False
                user.block_type = None
                user.block_reason = None
                db.commit()
                
                utils.log_action(db, "admin_action", admin_id=callback.from_user.id, data={
                    "action": "unblock_user",
                    "user_id": user.user_id
                })
                
                await callback.answer("✅ Пользователь разблокирован")
            else:
                # Блокировка - запрашиваем тип
                await state.set_state(AdminStates.setting_block_type)
                await state.update_data(user_db_id=user_db_id)
                
                builder = InlineKeyboardBuilder()
                builder.add(InlineKeyboardButton(text="🔴 Обычный бан", callback_data="block_type_normal"))
                builder.add(InlineKeyboardButton(text="🔇 Тихий бан", callback_data="block_type_silent"))
                builder.adjust(1)
                
                await callback.message.answer(
                    f"Выберите тип блокировки для пользователя {user.user_id} (@{user.username or 'нет'}):",
                    reply_markup=builder.as_markup()
                )
                await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("block_type_"))
async def set_block_type(callback: CallbackQuery, state: FSMContext):
    """Установка типа блокировки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    block_type = callback.data.split("_")[2]  # normal или silent
    data = await state.get_data()
    user_db_id = data.get("user_db_id")
    
    await state.set_state(AdminStates.setting_block_reason)
    await state.update_data(block_type=block_type)
    
    if block_type == 'silent':
        # Для тихого бана не нужна причина
        db = next(get_db())
        try:
            user = db.query(User).filter(User.id == user_db_id).first()
            if user:
                user.is_blocked = True
                user.block_type = 'silent'
                user.block_reason = None
                db.commit()
                
                utils.log_action(db, "admin_action", admin_id=callback.from_user.id, data={
                    "action": "block_user",
                    "user_id": user.user_id,
                    "block_type": "silent"
                })
                
                await callback.message.edit_text(f"✅ Пользователь {user.user_id} заблокирован (тихий бан)")
                await callback.answer()
                await state.clear()
        finally:
            db.close()
    else:
        await callback.message.edit_text("Введите причину блокировки:")
        await callback.answer()


@router.message(AdminStates.setting_block_reason)
async def save_block_reason(message: Message, state: FSMContext):
    """Сохранение причины блокировки"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text or message.text.startswith('/'):
        return
    
    block_reason = message.text.strip()
    data = await state.get_data()
    user_db_id = data.get("user_db_id")
    block_type = data.get("block_type", "normal")
    
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_db_id).first()
        if user:
            user.is_blocked = True
            user.block_type = block_type
            user.block_reason = block_reason
            db.commit()
            
            utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                "action": "block_user",
                "user_id": user.user_id,
                "block_type": block_type,
                "block_reason": block_reason
            })
            
            await message.answer(f"✅ Пользователь {user.user_id} заблокирован (обычный бан)\nПричина: {block_reason}")
            await state.clear()
        else:
            await message.answer("❌ Пользователь не найден")
    finally:
        db.close()


# ========== РАССЫЛКА ==========

@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Начало рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    await state.set_state(AdminStates.broadcasting)
    await callback.message.answer(
        "Отправьте сообщение для рассылки (текст, фото с подписью или медиа).\n"
        "После отправки выберите фильтр получателей."
    )
    await callback.answer()


@router.message(AdminStates.broadcasting, F.photo)
async def broadcast_with_photo(message: Message, state: FSMContext):
    """Рассылка с фото"""
    if not is_admin(message.from_user.id):
        return
    
    photo_id = message.photo[-1].file_id
    text = message.caption or ""
    
    await state.update_data(broadcast_photo=photo_id, broadcast_text=text)
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="👥 Всем", callback_data="broadcast_all"))
    builder.add(InlineKeyboardButton(text="✅ Покупавшим", callback_data="broadcast_buyers"))
    builder.add(InlineKeyboardButton(text="❌ Не покупавшим", callback_data="broadcast_non_buyers"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel"))
    builder.adjust(1)
    
    await message.answer("Выберите получателей:", reply_markup=builder.as_markup())


@router.message(AdminStates.broadcasting)
async def broadcast_text(message: Message, state: FSMContext):
    """Рассылка текста"""
    if not is_admin(message.from_user.id):
        return
    
    await state.update_data(broadcast_text=message.text, broadcast_photo=None)
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="👥 Всем", callback_data="broadcast_all"))
    builder.add(InlineKeyboardButton(text="✅ Покупавшим", callback_data="broadcast_buyers"))
    builder.add(InlineKeyboardButton(text="❌ Не покупавшим", callback_data="broadcast_non_buyers"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel"))
    builder.adjust(1)
    
    await message.answer("Выберите получателей:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("broadcast_"))
async def process_broadcast(callback: CallbackQuery, state: FSMContext):
    """Обработка рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    if callback.data == "broadcast_cancel":
        await callback.message.answer("Рассылка отменена")
        await state.clear()
        await callback.answer()
        return
    
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    photo_id = data.get("broadcast_photo")
    
    db = next(get_db())
    try:
        if callback.data == "broadcast_all":
            users = db.query(User).filter(User.is_blocked == False).all()
        elif callback.data == "broadcast_buyers":
            users = db.query(User).join(Purchase).filter(User.is_blocked == False).distinct().all()
        else:  # broadcast_non_buyers
            buyers_ids = db.query(Purchase.user_id).distinct().subquery()
            users = db.query(User).filter(
                User.is_blocked == False,
                ~User.id.in_(db.query(buyers_ids))
            ).all()
        
        await callback.message.answer(f"Начинаю рассылку для {len(users)} пользователей...")
        
        success = 0
        failed = 0
        
        for user in users:
            try:
                if photo_id:
                    await callback.bot.send_photo(user.user_id, photo_id, caption=text)
                else:
                    await callback.bot.send_message(user.user_id, text)
                success += 1
            except:
                failed += 1
            await asyncio.sleep(0.05)  # Задержка между сообщениями
        
        utils.log_action(db, "admin_action", admin_id=callback.from_user.id, data={
            "action": "broadcast",
            "filter": callback.data,
            "success": success,
            "failed": failed
        })
        
        await callback.message.answer(f"✅ Рассылка завершена!\nУспешно: {success}\nОшибок: {failed}")
        await state.clear()
        await callback.answer()
    finally:
        db.close()


# ========== ПРОМОКОДЫ ==========

@router.callback_query(F.data == "admin_promocodes")
async def show_promocodes_menu(callback: CallbackQuery):
    """Меню управления промокодами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    keyboard = kb.get_admin_promocodes_keyboard()
    await callback.message.answer("🎟 Управление промокодами:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_promocode_stats")
async def show_promocode_stats(callback: CallbackQuery):
    """Статистика промокодов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return

    db = next(get_db())
    try:
        promocodes = db.query(Promocode).order_by(Promocode.created_at.desc()).limit(20).all()

        if not promocodes:
            await callback.message.answer("Промокоды не найдены")
            await callback.answer()
            return

        text = "📊 Статистика промокодов (последние 20):\n\n"
        for promo in promocodes:
            activations = db.query(PromocodeActivation).filter(PromocodeActivation.promocode_id == promo.id).count()
            expires_text = promo.expires_at.strftime("%d.%m.%Y") if promo.expires_at else "без срока"
            bind_text = str(promo.user_id_bound) if promo.user_id_bound else "нет"
            status = "✅" if promo.is_active else "❌"
            text += (
                f"{status} {promo.code}\n"
                f"Сумма: {promo.amount:.2f} | Активаций: {activations}/{promo.max_activations}\n"
                f"Действует до: {expires_text} | Привязка: {bind_text}\n\n"
            )

        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_promocodes"))

        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "admin_create_promocode")
async def create_promocode(callback: CallbackQuery, state: FSMContext):
    """Создание промокода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    await state.set_state(AdminStates.creating_promocode)
    await callback.message.answer("Введите код промокода:")
    await callback.answer()


# --- Создание промокода (пошагово) ---

@router.message(AdminStates.creating_promocode)
async def set_promocode_code(message: Message, state: FSMContext):
    """Получение кода промокода"""
    if not is_admin(message.from_user.id):
        return

    code = message.text.strip().upper()
    if not code:
        await message.answer("Код не может быть пустым. Введите код промокода:")
        return

    db = next(get_db())
    try:
        if db.query(Promocode).filter(Promocode.code == code).first():
            await message.answer("❌ Такой промокод уже существует. Введите другой код:")
            return
    finally:
        db.close()

    await state.update_data(promocode_code=code)
    await state.set_state(AdminStates.editing_promocode_amount)
    await message.answer("Введите сумму промокода (число):")


@router.message(AdminStates.editing_promocode_amount)
async def set_promocode_amount(message: Message, state: FSMContext):
    """Получение суммы промокода"""
    if not is_admin(message.from_user.id):
        return

    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректную сумму (положительное число):")
        return

    await state.update_data(promocode_amount=amount)
    await state.set_state(AdminStates.editing_promocode_max_activations)
    await message.answer("Введите максимальное количество активаций (целое число):")


@router.message(AdminStates.editing_promocode_max_activations)
async def set_promocode_activations(message: Message, state: FSMContext):
    """Получение количества активаций"""
    if not is_admin(message.from_user.id):
        return

    try:
        max_activations = int(message.text)
        if max_activations <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректное количество активаций (положительное целое число):")
        return

    await state.update_data(promocode_max=max_activations)
    await state.set_state(AdminStates.editing_promocode_expires_at)
    await message.answer("Введите дату окончания в формате ДД.ММ.ГГГГ или 'нет', если без ограничения:")


@router.message(AdminStates.editing_promocode_expires_at)
async def set_promocode_expiration(message: Message, state: FSMContext):
    """Получение даты окончания"""
    if not is_admin(message.from_user.id):
        return

    text = message.text.strip().lower()
    expires_at = None
    if text not in ["нет", "no", "0"]:
        try:
            expires_at = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        except ValueError:
            await message.answer("Введите дату в формате ДД.ММ.ГГГГ или 'нет':")
            return

    await state.update_data(promocode_expires=expires_at)
    await state.set_state(AdminStates.creating_promocode_user)
    await message.answer("Введите user_id для привязки или 'нет':")


@router.message(AdminStates.creating_promocode_user)
async def finalize_promocode(message: Message, state: FSMContext):
    """Создание промокода и сохранение в БД"""
    if not is_admin(message.from_user.id):
        return

    text = message.text.strip().lower()
    user_id_bound = None
    if text not in ["нет", "no", "0"]:
        try:
            user_id_bound = int(text)
        except ValueError:
            await message.answer("Введите user_id (число) или 'нет':")
            return

    data = await state.get_data()
    code = data.get("promocode_code")
    amount = data.get("promocode_amount")
    max_activations = data.get("promocode_max")
    expires_at = data.get("promocode_expires")

    db = next(get_db())
    try:
        promocode = Promocode(
            code=code,
            amount=amount,
            max_activations=max_activations,
            expires_at=expires_at,
            user_id_bound=user_id_bound,
            is_active=True
        )
        db.add(promocode)
        db.commit()

        utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
            "action": "create_promocode",
            "code": code
        })

        expires_text = expires_at.strftime("%d.%m.%Y") if expires_at else "без ограничения"
        bind_text = str(user_id_bound) if user_id_bound else "нет"
        await message.answer(
            f"✅ Промокод создан!\n\n"
            f"Код: {code}\n"
            f"Сумма: {amount:.2f}\n"
            f"Активаций: {max_activations}\n"
            f"Действует до: {expires_text}\n"
            f"Привязка к пользователю: {bind_text}"
        )
        await state.clear()
    finally:
        db.close()


# ========== ТЕХ. РАБОТЫ ==========

@router.callback_query(F.data == "admin_maintenance")
async def toggle_maintenance(callback: CallbackQuery):
    """Включить/выключить тех. работы"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        current_mode = utils.get_setting(db, "maintenance_mode", False)
        new_mode = not current_mode
        utils.set_setting(db, "maintenance_mode", new_mode)
        
        status = "включен" if new_mode else "выключен"
        await callback.message.answer(f"✅ Режим тех. работ {status}")
        await callback.answer()
    finally:
        db.close()


# ========== КАНАЛ-ПОДПИСКА ==========

@router.callback_query(F.data == "admin_channel")
async def show_channel_menu(callback: CallbackQuery):
    """Меню управления каналом-подпиской"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        channel_id = utils.get_setting(db, "required_channel_id", None)
        channel_enabled = utils.get_setting(db, "channel_subscription_enabled", False)
        
        text = "📢 Управление каналом-подпиской\n\n"
        text += f"Статус: {'✅ Включена' if channel_enabled else '❌ Выключена'}\n"
        if channel_id:
            text += f"ID канала: {channel_id}\n"
        else:
            text += "ID канала: не настроен\n"
        text += "\nДля работы проверки подписки бот должен быть администратором канала."
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="✅ Включить" if not channel_enabled else "❌ Выключить",
            callback_data="admin_toggle_channel"
        ))
        builder.add(InlineKeyboardButton(text="⚙️ Настроить канал", callback_data="admin_set_channel"))
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
        builder.adjust(1)
        
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "admin_toggle_channel")
async def toggle_channel_subscription(callback: CallbackQuery):
    """Включить/выключить обязательную подписку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        current = utils.get_setting(db, "channel_subscription_enabled", False)
        channel_id = utils.get_setting(db, "required_channel_id", None)
        
        if not channel_id and not current:
            await callback.answer("⚠️ Сначала настройте ID канала!")
            return
        
        utils.set_setting(db, "channel_subscription_enabled", not current)
        
        # Обновляем в config
        if not current and channel_id:
            if channel_id.startswith('@') or (isinstance(channel_id, str) and channel_id.lstrip('-').isdigit()):
                try:
                    config.REQUIRED_CHANNEL_ID = int(channel_id) if channel_id.lstrip('-').isdigit() else channel_id
                except:
                    config.REQUIRED_CHANNEL_ID = channel_id
        elif current:
            config.REQUIRED_CHANNEL_ID = None
        
        status = "включена" if not current else "выключена"
        await callback.answer(f"✅ Обязательная подписка {status}")
        await show_channel_menu(callback)
    finally:
        db.close()


@router.callback_query(F.data == "admin_set_channel")
async def set_channel_id(callback: CallbackQuery, state: FSMContext):
    """Настройка ID канала"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    await state.set_state(AdminStates.setting_channel_id)
    await callback.message.answer(
        "Отправьте ID канала или username канала (например: @channel или -1001234567890).\n\n"
        "Как получить ID канала:\n"
        "1. Добавьте бота в админы канала\n"
        "2. Перешлите любое сообщение из канала боту @userinfobot\n"
        "3. Или используйте формат @username для публичных каналов"
    )
    await callback.answer()


@router.message(AdminStates.setting_channel_id)
async def save_channel_id(message: Message, state: FSMContext):
    """Сохранение ID канала"""
    if not is_admin(message.from_user.id):
        return
    
    channel_input = message.text.strip()
    
    # Парсим ID канала
    channel_id = None
    if channel_input.startswith('@'):
        # Username канала
        channel_id = channel_input
    elif channel_input.startswith('-'):
        # ID канала (отрицательное число)
        try:
            channel_id = int(channel_input)
        except ValueError:
            await message.answer("Неверный формат ID. Используйте формат: -1001234567890 или @channel")
            return
    else:
        # Пробуем как число
        try:
            channel_id = int(channel_input)
            if channel_id > 0:
                channel_id = -channel_id  # Каналы имеют отрицательные ID
        except ValueError:
            await message.answer("Неверный формат. Используйте формат: -1001234567890 или @channel")
            return
    
    # Проверяем доступ бота к каналу
    try:
        if isinstance(channel_id, int):
            chat = await message.bot.get_chat(channel_id)
        else:
            chat = await message.bot.get_chat(channel_id)
        
        # Проверяем, что бот админ
        try:
            bot_member = await message.bot.get_chat_member(chat.id, message.bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                await message.answer(
                    "⚠️ Бот не является администратором канала!\n"
                    "Добавьте бота в администраторы канала для работы проверки подписки."
                )
                await state.clear()
                return
        except Exception as e:
            await message.answer(
                f"⚠️ Не удалось проверить права бота в канале.\n"
                f"Убедитесь, что бот добавлен в администраторы канала.\n\n"
                f"Ошибка: {str(e)}"
            )
            await state.clear()
            return
        
        db = next(get_db())
        try:
            # Сохраняем ID канала
            if isinstance(channel_id, int):
                utils.set_setting(db, "required_channel_id", str(channel_id))
            else:
                utils.set_setting(db, "required_channel_id", channel_id)
            
            # Обновляем в config
            config.REQUIRED_CHANNEL_ID = channel_id
            
            utils.log_action(db, "admin_action", admin_id=message.from_user.id, data={
                "action": "set_channel_id",
                "channel_id": str(channel_id)
            })
            
            await message.answer(f"✅ Канал настроен: {chat.title or channel_id}")
            await state.clear()
        finally:
            db.close()
    except Exception as e:
        await message.answer(f"❌ Ошибка: не удалось получить информацию о канале. Проверьте ID и права бота.\n\nОшибка: {str(e)}")
        await state.clear()


# ========== РЕДАКТИРОВАНИЕ КАТЕГОРИЙ/ПОДКАТЕГОРИЙ ==========

@router.callback_query(F.data == "admin_edit_category")
async def edit_category_menu(callback: CallbackQuery):
    """Меню редактирования категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        categories = db.query(Category).order_by(Category.position).all()
        if not categories:
            await callback.message.answer("Нет категорий для редактирования")
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        for category in categories:
            builder.add(InlineKeyboardButton(
                text=category.name,
                callback_data=f"admin_edit_cat_{category.id}"
            ))
        
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_catalog"))
        builder.adjust(1)
        
        await callback.message.answer("Выберите категорию для редактирования:", reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.regexp(r"^admin_edit_cat_\d+$"))
async def edit_category_options(callback: CallbackQuery):
    """Опции редактирования категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    category_id = int(callback.data.split("_")[3])
    db = next(get_db())
    try:
        category = db.query(Category).filter(Category.id == category_id).first()
        if not category:
            await callback.answer("Категория не найдена")
            return
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"admin_editcatname_{category_id}"))
        builder.add(InlineKeyboardButton(text="🖼 Изменить фото", callback_data=f"admin_editcatphoto_{category_id}"))
        builder.add(InlineKeyboardButton(text="📝 Изменить описание", callback_data=f"admin_editcatdesc_{category_id}"))
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_edit_category"))
        builder.adjust(1)
        
        text = f"📁 Категория: {category.name}\n"
        if category.description:
            text += f"Описание: {category.description[:100]}...\n" if len(category.description) > 100 else f"Описание: {category.description}\n"
        
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_editcatname_"))
async def edit_category_name_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования названия категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    category_id = int(callback.data.split("_")[1])
    await state.set_state(AdminStates.editing_category_name)
    await state.update_data(category_id=category_id)
    await callback.message.answer("Введите новое название категории:")
    await callback.answer()


@router.message(AdminStates.editing_category_name)
async def edit_category_name_save(message: Message, state: FSMContext):
    """Сохранение нового названия категории"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    category_id = data.get("category_id")
    
    db = next(get_db())
    try:
        category = db.query(Category).filter(Category.id == category_id).first()
        if category:
            category.name = message.text.strip()
            db.commit()
            await message.answer(f"✅ Название категории изменено на '{category.name}'")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_editcatphoto_"))
async def edit_category_photo_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования фото категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    category_id = int(callback.data.split("_")[1])
    await state.set_state(AdminStates.editing_category_photo)
    await state.update_data(category_id=category_id)
    await callback.message.answer("Отправьте новое фото для категории:")
    await callback.answer()


@router.message(AdminStates.editing_category_photo, F.photo)
async def edit_category_photo_save(message: Message, state: FSMContext):
    """Сохранение нового фото категории"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    category_id = data.get("category_id")
    
    db = next(get_db())
    try:
        category = db.query(Category).filter(Category.id == category_id).first()
        if category:
            category.photo = message.photo[-1].file_id
            db.commit()
            await message.answer("✅ Фото категории обновлено!")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_editcatdesc_"))
async def edit_category_desc_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования описания категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    category_id = int(callback.data.split("_")[1])
    await state.set_state(AdminStates.editing_category_desc)
    await state.update_data(category_id=category_id)
    await callback.message.answer("Введите новое описание категории:")
    await callback.answer()


@router.message(AdminStates.editing_category_desc)
async def edit_category_desc_save(message: Message, state: FSMContext):
    """Сохранение нового описания категории"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    category_id = data.get("category_id")
    
    db = next(get_db())
    try:
        category = db.query(Category).filter(Category.id == category_id).first()
        if category:
            category.description = message.text.strip()
            db.commit()
            await message.answer("✅ Описание категории обновлено!")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data == "admin_edit_subcategory")
async def edit_subcategory_menu(callback: CallbackQuery):
    """Меню редактирования подкатегории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        subcategories = db.query(Subcategory).all()
        if not subcategories:
            await callback.message.answer("Нет подкатегорий для редактирования")
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        for subcategory in subcategories:
            category = subcategory.category
            builder.add(InlineKeyboardButton(
                text=f"{category.name} > {subcategory.name}",
                callback_data=f"admin_edit_subcat_{subcategory.id}"
            ))
        
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_catalog"))
        builder.adjust(1)
        
        await callback.message.answer("Выберите подкатегорию для редактирования:", reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.regexp(r"^admin_edit_subcat_\d+$"))
async def edit_subcategory_options(callback: CallbackQuery):
    """Опции редактирования подкатегории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    subcategory_id = int(callback.data.split("_")[3])
    db = next(get_db())
    try:
        subcategory = db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
        if not subcategory:
            await callback.answer("Подкатегория не найдена")
            return
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"admin_editsubcatname_{subcategory_id}"))
        builder.add(InlineKeyboardButton(text="🖼 Изменить фото", callback_data=f"admin_editsubcatphoto_{subcategory_id}"))
        builder.add(InlineKeyboardButton(text="📝 Изменить описание", callback_data=f"admin_editsubcatdesc_{subcategory_id}"))
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_edit_subcategory"))
        builder.adjust(1)
        
        text = f"📂 Подкатегория: {subcategory.name}\n"
        if subcategory.description:
            text += f"Описание: {subcategory.description[:100]}...\n" if len(subcategory.description) > 100 else f"Описание: {subcategory.description}\n"
        
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_editsubcatname_"))
async def edit_subcategory_name_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования названия подкатегории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    subcategory_id = int(callback.data.split("_")[1])
    await state.set_state(AdminStates.editing_subcategory_name)
    await state.update_data(subcategory_id=subcategory_id)
    await callback.message.answer("Введите новое название подкатегории:")
    await callback.answer()


@router.message(AdminStates.editing_subcategory_name)
async def edit_subcategory_name_save(message: Message, state: FSMContext):
    """Сохранение нового названия подкатегории"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    subcategory_id = data.get("subcategory_id")
    
    db = next(get_db())
    try:
        subcategory = db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
        if subcategory:
            subcategory.name = message.text.strip()
            db.commit()
            await message.answer(f"✅ Название подкатегории изменено на '{subcategory.name}'")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_editsubcatphoto_"))
async def edit_subcategory_photo_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования фото подкатегории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    subcategory_id = int(callback.data.split("_")[1])
    await state.set_state(AdminStates.editing_subcategory_photo)
    await state.update_data(subcategory_id=subcategory_id)
    await callback.message.answer("Отправьте новое фото для подкатегории:")
    await callback.answer()


@router.message(AdminStates.editing_subcategory_photo, F.photo)
async def edit_subcategory_photo_save(message: Message, state: FSMContext):
    """Сохранение нового фото подкатегории"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    subcategory_id = data.get("subcategory_id")
    
    db = next(get_db())
    try:
        subcategory = db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
        if subcategory:
            subcategory.photo = message.photo[-1].file_id
            db.commit()
            await message.answer("✅ Фото подкатегории обновлено!")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_editsubcatdesc_"))
async def edit_subcategory_desc_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования описания подкатегории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    subcategory_id = int(callback.data.split("_")[1])
    await state.set_state(AdminStates.editing_subcategory_desc)
    await state.update_data(subcategory_id=subcategory_id)
    await callback.message.answer("Введите новое описание подкатегории:")
    await callback.answer()


@router.message(AdminStates.editing_subcategory_desc)
async def edit_subcategory_desc_save(message: Message, state: FSMContext):
    """Сохранение нового описания подкатегории"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    subcategory_id = data.get("subcategory_id")
    
    db = next(get_db())
    try:
        subcategory = db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
        if subcategory:
            subcategory.description = message.text.strip()
            db.commit()
            await message.answer("✅ Описание подкатегории обновлено!")
        await state.clear()
    finally:
        db.close()


# ========== УДАЛЕНИЕ КАТЕГОРИЙ/ПОДКАТЕГОРИЙ/ПОЗИЦИЙ ==========

@router.callback_query(F.data == "admin_delete_category")
async def delete_category_menu(callback: CallbackQuery):
    """Меню удаления категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        categories = db.query(Category).all()
        if not categories:
            await callback.message.answer("Нет категорий для удаления")
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        for category in categories:
            builder.add(InlineKeyboardButton(
                text=f"🗑 {category.name}",
                callback_data=f"admin_del_cat_{category.id}"
            ))
        
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_catalog"))
        builder.adjust(1)
        
        await callback.message.answer("Выберите категорию для удаления:", reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_del_cat_"))
async def confirm_delete_category(callback: CallbackQuery):
    """Подтверждение удаления категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    category_id = int(callback.data.split("_")[3])
    db = next(get_db())
    try:
        category = db.query(Category).filter(Category.id == category_id).first()
        if not category:
            await callback.answer("Категория не найдена")
            return
        
        # Считаем связанные объекты
        subcats_count = db.query(Subcategory).filter(Subcategory.category_id == category_id).count()
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"admin_confirm_del_cat_{category_id}"
        ))
        builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_delete_category"))
        builder.adjust(1)
        
        text = f"⚠️ Удалить категорию '{category.name}'?\n\n"
        if subcats_count > 0:
            text += f"Внимание: будут удалены {subcats_count} подкатегорий и все связанные позиции!"
        
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_confirm_del_cat_"))
async def execute_delete_category(callback: CallbackQuery):
    """Удаление категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    category_id = int(callback.data.split("_")[4])
    db = next(get_db())
    try:
        category = db.query(Category).filter(Category.id == category_id).first()
        if not category:
            await callback.answer("Категория не найдена")
            return
        
        category_name = category.name
        
        # Удаляем связанные подкатегории и позиции
        subcategories = db.query(Subcategory).filter(Subcategory.category_id == category_id).all()
        for subcat in subcategories:
            # Удаляем позиции подкатегории
            db.query(Item).filter(Item.subcategory_id == subcat.id).delete()
        
        # Удаляем подкатегории
        db.query(Subcategory).filter(Subcategory.category_id == category_id).delete()
        
        # Удаляем категорию
        db.delete(category)
        db.commit()
        
        utils.log_action(db, "admin_action", admin_id=callback.from_user.id, data={
            "action": "delete_category",
            "category_id": category_id,
            "category_name": category_name
        })
        
        await callback.message.answer(f"✅ Категория '{category_name}' удалена!")
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "admin_delete_subcategory")
async def delete_subcategory_menu(callback: CallbackQuery):
    """Меню удаления подкатегории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        subcategories = db.query(Subcategory).all()
        if not subcategories:
            await callback.message.answer("Нет подкатегорий для удаления")
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        for subcat in subcategories:
            category = subcat.category
            text = f"🗑 {category.name} > {subcat.name}" if category else f"🗑 {subcat.name}"
            builder.add(InlineKeyboardButton(
                text=text,
                callback_data=f"admin_del_subcat_{subcat.id}"
            ))
        
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_catalog"))
        builder.adjust(1)
        
        await callback.message.answer("Выберите подкатегорию для удаления:", reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_del_subcat_"))
async def confirm_delete_subcategory(callback: CallbackQuery):
    """Подтверждение удаления подкатегории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    subcat_id = int(callback.data.split("_")[3])
    db = next(get_db())
    try:
        subcat = db.query(Subcategory).filter(Subcategory.id == subcat_id).first()
        if not subcat:
            await callback.answer("Подкатегория не найдена")
            return
        
        items_count = db.query(Item).filter(Item.subcategory_id == subcat_id).count()
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"admin_confirm_del_subcat_{subcat_id}"
        ))
        builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_delete_subcategory"))
        builder.adjust(1)
        
        text = f"⚠️ Удалить подкатегорию '{subcat.name}'?\n\n"
        if items_count > 0:
            text += f"Внимание: будут удалены {items_count} позиций!"
        
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_confirm_del_subcat_"))
async def execute_delete_subcategory(callback: CallbackQuery):
    """Удаление подкатегории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    subcat_id = int(callback.data.split("_")[4])
    db = next(get_db())
    try:
        subcat = db.query(Subcategory).filter(Subcategory.id == subcat_id).first()
        if not subcat:
            await callback.answer("Подкатегория не найдена")
            return
        
        subcat_name = subcat.name
        
        # Удаляем позиции
        db.query(Item).filter(Item.subcategory_id == subcat_id).delete()
        
        # Удаляем подкатегорию
        db.delete(subcat)
        db.commit()
        
        utils.log_action(db, "admin_action", admin_id=callback.from_user.id, data={
            "action": "delete_subcategory",
            "subcategory_id": subcat_id,
            "subcategory_name": subcat_name
        })
        
        await callback.message.answer(f"✅ Подкатегория '{subcat_name}' удалена!")
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "admin_delete_item")
async def delete_item_menu(callback: CallbackQuery):
    """Меню удаления позиции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        items = db.query(Item).all()
        if not items:
            await callback.message.answer("Нет позиций для удаления")
            await callback.answer()
            return
        
        builder = InlineKeyboardBuilder()
        for item in items:
            subcat = item.subcategory
            category = subcat.category if subcat else None
            if category and subcat:
                text = f"🗑 {category.name} > {subcat.name} > {item.name}"
            else:
                text = f"🗑 {item.name}"
            builder.add(InlineKeyboardButton(
                text=text,
                callback_data=f"admin_del_item_{item.id}"
            ))
        
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_catalog"))
        builder.adjust(1)
        
        await callback.message.answer("Выберите позицию для удаления:", reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_del_item_"))
async def confirm_delete_item(callback: CallbackQuery):
    """Подтверждение удаления позиции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    item_id = int(callback.data.split("_")[3])
    db = next(get_db())
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            await callback.answer("Позиция не найдена")
            return
        
        products_count = db.query(Product).filter(Product.item_id == item_id).count()
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"admin_confirm_del_item_{item_id}"
        ))
        builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_delete_item"))
        builder.adjust(1)
        
        text = f"⚠️ Удалить позицию '{item.name}'?\n\n"
        if products_count > 0:
            text += f"Внимание: будут удалены {products_count} товаров!"
        
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_confirm_del_item_"))
async def execute_delete_item(callback: CallbackQuery):
    """Удаление позиции"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    item_id = int(callback.data.split("_")[4])
    db = next(get_db())
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            await callback.answer("Позиция не найдена")
            return
        
        item_name = item.name
        
        # Удаляем покупки связанные с позицией
        db.query(Purchase).filter(Purchase.item_id == item_id).delete()
        
        # Удаляем товары
        db.query(Product).filter(Product.item_id == item_id).delete()
        
        # Удаляем позицию
        db.delete(item)
        db.commit()
        
        utils.log_action(db, "admin_action", admin_id=callback.from_user.id, data={
            "action": "delete_item",
            "item_id": item_id,
            "item_name": item_name
        })
        
        await callback.message.answer(f"✅ Позиция '{item_name}' удалена!")
        await callback.answer()
    finally:
        db.close()


# ========== НАВИГАЦИЯ ==========

# ========== ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ ==========

@router.callback_query(F.data == "admin_agreement")
async def show_agreement_menu(callback: CallbackQuery):
    """Меню управления пользовательским соглашением"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        response = db.query(BotResponse).filter(BotResponse.key == "user_agreement").first()
        text = "📋 Управление пользовательским соглашением\n\n"
        if response:
            text += f"Текущий текст:\n{response.text[:200]}..." if len(response.text) > 200 else f"Текущий текст:\n{response.text}"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="✏️ Редактировать", callback_data="admin_edit_response_user_agreement"))
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
        builder.adjust(1)
        
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


# ========== СКРЫТИЕ ТОВАРОВ БЕЗ НАЛИЧИЯ ==========

@router.callback_query(F.data == "admin_hide_out_of_stock")
async def toggle_hide_out_of_stock(callback: CallbackQuery):
    """Включить/выключить скрытие товаров без наличия"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        current = utils.get_setting(db, "hide_out_of_stock", False)
        utils.set_setting(db, "hide_out_of_stock", not current)
        
        status = "включено" if not current else "выключено"
        await callback.message.answer(f"✅ Скрытие товаров без наличия {status}")
        await callback.answer()
    finally:
        db.close()


# ========== УВЕДОМЛЕНИЯ ==========

@router.callback_query(F.data == "admin_notifications")
async def show_notifications_menu(callback: CallbackQuery):
    """Меню управления уведомлениями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        notify_purchase = utils.get_setting(db, "notify_new_purchase", True)
        notify_payment = utils.get_setting(db, "notify_new_payment", True)
        notify_stock = utils.get_setting(db, "notify_out_of_stock", True)
        
        text = "🔔 Управление уведомлениями\n\n"
        text += f"Новая покупка: {'✅' if notify_purchase else '❌'}\n"
        text += f"Новое пополнение: {'✅' if notify_payment else '❌'}\n"
        text += f"Товар закончился: {'✅' if notify_stock else '❌'}\n\n"
        text += "Выберите уведомление для изменения:"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text=f"{'✅' if notify_purchase else '❌'} Новая покупка",
            callback_data="admin_toggle_notify_purchase"
        ))
        builder.add(InlineKeyboardButton(
            text=f"{'✅' if notify_payment else '❌'} Новое пополнение",
            callback_data="admin_toggle_notify_payment"
        ))
        builder.add(InlineKeyboardButton(
            text=f"{'✅' if notify_stock else '❌'} Товар закончился",
            callback_data="admin_toggle_notify_stock"
        ))
        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
        builder.adjust(1)
        
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "admin_toggle_notify_purchase")
async def toggle_notify_purchase(callback: CallbackQuery):
    """Включить/выключить уведомления о покупках"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        current = utils.get_setting(db, "notify_new_purchase", True)
        utils.set_setting(db, "notify_new_purchase", not current)
        await callback.answer(f"✅ Уведомления о покупках {'включены' if not current else 'выключены'}")
        await show_notifications_menu(callback)
    finally:
        db.close()


@router.callback_query(F.data == "admin_toggle_notify_payment")
async def toggle_notify_payment(callback: CallbackQuery):
    """Включить/выключить уведомления о пополнениях"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        current = utils.get_setting(db, "notify_new_payment", True)
        utils.set_setting(db, "notify_new_payment", not current)
        await callback.answer(f"✅ Уведомления о пополнениях {'включены' if not current else 'выключены'}")
        await show_notifications_menu(callback)
    finally:
        db.close()


@router.callback_query(F.data == "admin_toggle_notify_stock")
async def toggle_notify_stock(callback: CallbackQuery):
    """Включить/выключить уведомления о закончившихся товарах"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    db = next(get_db())
    try:
        current = utils.get_setting(db, "notify_out_of_stock", True)
        utils.set_setting(db, "notify_out_of_stock", not current)
        await callback.answer(f"✅ Уведомления о закончившихся товарах {'включены' if not current else 'выключены'}")
        await show_notifications_menu(callback)
    finally:
        db.close()


@router.callback_query(F.data == "admin_panel")
async def back_to_admin_panel(callback: CallbackQuery):
    """Вернуться в админ-панель"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен")
        return
    
    keyboard = kb.get_admin_panel_keyboard()
    await callback.message.answer(config.ADMIN_TEXTS["panel"], reply_markup=keyboard)
    await callback.answer()

