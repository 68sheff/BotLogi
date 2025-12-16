"""
Обработчики для пользователей
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
from database import (
    User, Category, Subcategory, Item, Product, Purchase, Payment,
    Promocode, PromocodeActivation, get_db
)
import keyboards as kb
import utils
import config
from datetime import datetime
import aiohttp
import os


router = Router()


def get_or_create_user(db, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> User:
    """Получить или создать пользователя"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        db.add(user)
        db.commit()
    else:
        # Обновляем данные пользователя
        if username is not None:
            user.username = username
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        db.commit()
    return user


from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

class BlockedUserMiddleware(BaseMiddleware):
    """Middleware для проверки блокировки пользователя"""
    async def __call__(self, handler, event, data):
        # Пропускаем админов
        if event.from_user.id in config.ADMIN_IDS:
            return await handler(event, data)
        
        db = next(get_db())
        try:
            is_blocked, block_type, block_reason = utils.check_user_blocked(db, event.from_user.id)
            if is_blocked:
                if block_type == 'silent':
                    # Тихий бан - просто не обрабатываем
                    return
                else:
                    # Обычный бан - показываем сообщение
                    if isinstance(event, Message):
                        await utils.send_blocked_message(event.bot, event.chat.id, block_reason)
                    elif isinstance(event, CallbackQuery) and event.message:
                        await utils.send_blocked_message(event.bot, event.message.chat.id, block_reason)
                    return
        finally:
            db.close()
        
        return await handler(event, data)


class PurchaseStates(StatesGroup):
    waiting_quantity = State()
    waiting_promocode = State()
    waiting_payment_amount = State()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    db = next(get_db())
    try:
        # Проверка блокировки
        is_blocked, block_type, block_reason = utils.check_user_blocked(db, message.from_user.id)
        if is_blocked:
            if block_type == 'silent':
                # Тихий бан - просто не отвечаем
                return
            else:
                # Обычный бан - показываем сообщение
                await utils.send_blocked_message(message.bot, message.chat.id, block_reason)
                return
        
        # Проверка тех. работ
        if utils.get_setting(db, "maintenance_mode", False):
            maintenance_text = utils.get_setting(db, "maintenance_text", config.TEXTS["maintenance"])
            await message.answer(maintenance_text)
            return
        
        # Проверка подписки
        if not await utils.check_channel_subscription(message.bot, message.from_user.id):
            channel_id = utils.get_setting(db, "required_channel_id", None)
            if channel_id:
                # Создаем inline кнопки
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                builder = InlineKeyboardBuilder()
                
                # Кнопка "Канал"
                if isinstance(channel_id, str) and channel_id.startswith('@'):
                    # Username канала
                    builder.add(InlineKeyboardButton(
                        text="📢 Канал",
                        url=f"https://t.me/{channel_id[1:]}"  # Убираем @
                    ))
                else:
                    # ID канала - получаем username канала или используем invite link
                    try:
                        chat_id = int(channel_id) if isinstance(channel_id, str) else channel_id
                        # Пытаемся получить информацию о канале
                        try:
                            chat = await message.bot.get_chat(chat_id)
                            if chat.username:
                                builder.add(InlineKeyboardButton(
                                    text="📢 Канал",
                                    url=f"https://t.me/{chat.username}"
                                ))
                            else:
                                # Для приватных каналов нужен invite link
                                invite_link = await message.bot.export_chat_invite_link(chat_id)
                                builder.add(InlineKeyboardButton(
                                    text="📢 Канал",
                                    url=invite_link
                                ))
                        except:
                            # Если не получилось, используем формат с ID
                            builder.add(InlineKeyboardButton(
                                text="📢 Канал",
                                url=f"https://t.me/c/{str(abs(chat_id))[4:]}"
                            ))
                    except:
                        builder.add(InlineKeyboardButton(
                            text="📢 Канал",
                            url=f"https://t.me/{channel_id}"
                        ))
                
                # Кнопка "Проверить подписку"
                builder.add(InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data="check_subscription"
                ))
                builder.adjust(1)
                
                await message.answer(config.TEXTS["no_subscription"], reply_markup=builder.as_markup())
            else:
                await message.answer(config.TEXTS["no_subscription"])
            return
        
        # Создание/получение пользователя
        user = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        start_text, start_photo = utils.get_bot_response_with_media(db, "start", config.TEXTS["start"])
        keyboard = kb.get_main_keyboard(db, message.from_user.id)
        if start_photo:
            await message.answer_photo(start_photo, caption=start_text, reply_markup=keyboard)
        else:
            await message.answer(start_text, reply_markup=keyboard)
    finally:
        db.close()


@router.message(F.text.in_([config.BUTTONS.get("buy", "🛒 Купить"), "🛒 Купить"]))
async def show_categories(message: Message):
    """Показать категории"""
    db = next(get_db())
    try:
        keyboard = kb.get_categories_keyboard(db)
        buy_text, buy_photo = utils.get_bot_response_with_media(db, "buy", "📦 Выберите категорию:")
        if buy_photo:
            await message.answer_photo(buy_photo, caption=buy_text, reply_markup=keyboard)
        else:
            await message.answer(buy_text, reply_markup=keyboard)
    finally:
        db.close()


@router.callback_query(F.data.startswith("category_"))
async def show_subcategories(callback: CallbackQuery):
    """Показать подкатегории"""
    category_id = int(callback.data.split("_")[1])
    db = next(get_db())
    try:
        category = db.query(Category).filter(Category.id == category_id).first()
        if not category:
            await callback.answer("Категория не найдена")
            return
        
        # Удаляем предыдущее сообщение
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        keyboard = kb.get_subcategories_keyboard(db, category_id)
        text = f"📂 {category.name}\n\n{category.description or ''}"
        
        if category.photo:
            try:
                await callback.message.answer_photo(category.photo, caption=text, reply_markup=keyboard)
            except Exception:
                await callback.message.answer(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("subcategory_"))
async def show_items(callback: CallbackQuery):
    """Показать позиции"""
    subcategory_id = int(callback.data.split("_")[1])
    db = next(get_db())
    try:
        subcategory = db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
        if not subcategory:
            await callback.answer("Подкатегория не найдена")
            return
        
        # Удаляем предыдущее сообщение
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        hide_out_of_stock = utils.get_setting(db, "hide_out_of_stock", False)
        keyboard = kb.get_items_keyboard(db, subcategory_id, hide_out_of_stock)
        text = f"📋 {subcategory.name}\n\n{subcategory.description or ''}"
        
        if subcategory.photo:
            try:
                await callback.message.answer_photo(subcategory.photo, caption=text, reply_markup=keyboard)
            except Exception:
                await callback.message.answer(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("item_"))
async def show_item(callback: CallbackQuery):
    """Показать товар"""
    item_id = int(callback.data.split("_")[1])
    db = next(get_db())
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            await callback.answer("Товар не найден")
            return
        
        # Удаляем предыдущее сообщение
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        user = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        available_count = db.query(Product).filter(
            Product.item_id == item.id,
            Product.is_sold == False
        ).count()
        
        # Категория -> Подкатегория
        if item.subcategory and item.subcategory.category:
            category_full = f"{item.subcategory.category.name} -> {item.subcategory.name}"
        elif item.subcategory:
            category_full = item.subcategory.name
        else:
            category_full = "Без категории"
        
        text = (
            f"💎 Категория: {category_full}\n\n"
            f"🛍️ Товар: {item.name}\n\n"
            f"💰 Стоимость: {item.price:.2f}$\n"
        )
        
        if item.product_type == 'string':
            text += f"⚙️ Доступное кол-во: {available_count} шт.\n"
        else:
            text += f"⚙️ Доступное кол-во: {'1 шт.' if available_count > 0 else '0 шт.'}\n"
        
        description_block = item.description.strip() if item.description else "Описание отсутствует."
        text += f"\n{description_block}"
        
        if available_count == 0:
            behavior = item.out_of_stock_behavior
            if behavior == 'show_no_stock':
                text += f"\n\n{utils.get_bot_response(db, 'product_out_of_stock', config.TEXTS['product_out_of_stock'])}"
            elif behavior == 'show_no_button':
                text += f"\n\n{utils.get_bot_response(db, 'product_out_of_stock', config.TEXTS['product_out_of_stock'])}"
        
        keyboard = kb.get_item_keyboard(db, item_id, user.balance if user else 0)
        
        if keyboard is None:
            # Получаем subcategory_id из item
            subcategory_id = item.subcategory_id
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_subcategory_{subcategory_id}")
            ]])
        
        if item.photo:
            try:
                await callback.message.answer_photo(item.photo, caption=text, reply_markup=keyboard)
            except Exception:
                # Если фото невалидно, отправляем без фото
                await callback.message.answer(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("item_info_"))
async def show_item_info(callback: CallbackQuery):
    """Показать информацию о товаре (без кнопки покупки)"""
    item_id = int(callback.data.split("_")[2])
    db = next(get_db())
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            await callback.answer("Товар не найден")
            return
        
        # Категория -> Подкатегория
        if item.subcategory and item.subcategory.category:
            category_full = f"{item.subcategory.category.name} -> {item.subcategory.name}"
        elif item.subcategory:
            category_full = item.subcategory.name
        else:
            category_full = "Без категории"
        
        description_block = item.description.strip() if item.description else "Описание отсутствует."
        
        text = (
            f"💎 Категория: {category_full}\n\n"
            f"🛍️ Товар: {item.name}\n\n"
            f"💰 Стоимость: {item.price:.2f}$\n"
            f"⚙️ Доступное кол-во: 0 шт.\n\n"
            f"{description_block}\n\n"
            f"❌ Товар временно недоступен"
        )
        
        # Получаем subcategory_id из item
        subcategory_id = item.subcategory_id
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_subcategory_{subcategory_id}")
        ]])
        
        if item.photo:
            try:
                await callback.message.answer_photo(item.photo, caption=text, reply_markup=keyboard)
            except Exception:
                # Если фото невалидно, отправляем без фото
                await callback.message.answer(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("buy_"))
async def process_purchase(callback: CallbackQuery, state: FSMContext):
    """Обработка покупки"""
    parts = callback.data.split("_")
    item_id = int(parts[1])
    quantity = int(parts[2]) if len(parts) > 2 else 1
    
    db = next(get_db())
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            await callback.answer("Товар не найден")
            return
        
        user = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        if user.is_blocked:
            await callback.answer("Пользователь заблокирован")
            return
        
        # Проверка наличия
        if item.product_type == 'string':
            available_products = db.query(Product).filter(
                Product.item_id == item.id,
                Product.is_sold == False
            ).limit(quantity).all()
            
            if len(available_products) < quantity:
                await callback.answer("Недостаточно товара в наличии")
                return
        else:
            available_product = db.query(Product).filter(
                Product.item_id == item.id,
                Product.is_sold == False
            ).first()
            
            if not available_product:
                await callback.answer("Товар закончился")
                return
            available_products = [available_product]
            quantity = 1
        
        total_price = item.price * quantity
        
        if user.balance < total_price:
            await callback.answer(config.TEXTS["insufficient_balance"])
            return
        
        # Создание покупки
        purchase = Purchase(
            user_id=user.id,
            item_id=item.id,
            quantity=quantity,
            total_price=total_price
        )
        db.add(purchase)
        
        # Списание баланса
        user.balance -= total_price
        
        # Помечаем товары как проданные
        if item.product_type == 'string':
            # Для строковых товаров помечаем все купленные
            for i, product in enumerate(available_products):
                product.is_sold = True
                product.sold_at = datetime.now()
                if i == 0:
                    purchase.product_id = product.id
        else:
            # Для файловых товаров берем первый
            product = available_products[0]
            product.is_sold = True
            product.sold_at = datetime.now()
            purchase.product_id = product.id
        
        db.commit()
        
        # Логирование
        utils.log_action(db, "purchase", user_id=user.id, data={
            "item_id": item.id,
            "quantity": quantity,
            "total_price": total_price
        })
        
        # Уведомление админу
        await utils.send_admin_notification(
            callback.bot,
            "new_purchase",
            f"Новая покупка!\nТовар: {item.name}\nСумма: {total_price} USDT",
            user_id=user.user_id,
            username=user.username
        )
        
        # Выдача товара
        success_text = utils.get_bot_response(db, "purchase_success", config.TEXTS["purchase_success"])
        await callback.message.answer(success_text)
        
        try:
            if item.product_type == 'string':
                # Выдача строк
                products_text = "\n".join([p.content for p in available_products])
                await callback.message.answer(f"📦 Ваш товар:\n\n{products_text}")
            else:
                # Выдача файла
                product = available_products[0]
                if product.file_id:
                    try:
                        await callback.message.answer_document(product.file_id)
                    except:
                        # Если file_id не работает, пробуем файл
                        if product.file_path and os.path.exists(product.file_path):
                            file = FSInputFile(product.file_path)
                            await callback.message.answer_document(file)
                elif product.file_path and os.path.exists(product.file_path):
                    file = FSInputFile(product.file_path)
                    await callback.message.answer_document(file)
        except Exception as e:
            # Если не удалось выдать сразу, пользователь сможет получить через историю
            pass
        
        await callback.answer("Покупка успешна!")
    finally:
        db.close()


@router.callback_query(F.data.startswith("buy_custom_"))
async def ask_custom_quantity(callback: CallbackQuery, state: FSMContext):
    """Запрос кастомного количества"""
    item_id = int(callback.data.split("_")[2])
    await state.set_state(PurchaseStates.waiting_quantity)
    await state.update_data(item_id=item_id)
    await callback.message.answer("Введите количество товара:")
    await callback.answer()


@router.message(PurchaseStates.waiting_quantity)
async def process_custom_quantity(message: Message, state: FSMContext):
    """Обработка кастомного количества"""
    try:
        quantity = int(message.text)
        if quantity <= 0:
            await message.answer("Количество должно быть больше 0")
            return
        
        data = await state.get_data()
        item_id = data.get("item_id")
        
        # Обрабатываем покупку напрямую
        db = next(get_db())
        try:
            item = db.query(Item).filter(Item.id == item_id).first()
            if not item:
                await message.answer("Товар не найден")
                await state.clear()
                return
            
            user = get_or_create_user(
                db,
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
            if user.is_blocked:
                await message.answer("Пользователь не найден или заблокирован")
                await state.clear()
                return
            
            # Проверка наличия
            available_products = db.query(Product).filter(
                Product.item_id == item.id,
                Product.is_sold == False
            ).limit(quantity).all()
            
            if len(available_products) < quantity:
                await message.answer("Недостаточно товара в наличии")
                await state.clear()
                return
            
            total_price = item.price * quantity
            
            if user.balance < total_price:
                await message.answer(config.TEXTS["insufficient_balance"])
                await state.clear()
                return
            
            # Создание покупки
            purchase = Purchase(
                user_id=user.id,
                item_id=item.id,
                quantity=quantity,
                total_price=total_price
            )
            db.add(purchase)
            
            # Списание баланса
            user.balance -= total_price
            
            # Помечаем товары как проданные
            for i, product in enumerate(available_products):
                product.is_sold = True
                product.sold_at = datetime.now()
                if i == 0:
                    purchase.product_id = product.id
            
            db.commit()
            
            # Логирование
            utils.log_action(db, "purchase", user_id=user.id, data={
                "item_id": item.id,
                "quantity": quantity,
                "total_price": total_price
            })
            
            # Уведомление админу
            await utils.send_admin_notification(
                message.bot,
                "new_purchase",
                f"Новая покупка!\nТовар: {item.name}\nСумма: {total_price} USDT",
                user_id=user.user_id,
                username=user.username
            )
            
            # Выдача товара
            success_text = utils.get_bot_response(db, "purchase_success", config.TEXTS["purchase_success"])
            await message.answer(success_text)
            
            try:
                products_text = "\n".join([p.content for p in available_products])
                await message.answer(f"📦 Ваш товар:\n\n{products_text}")
            except Exception as e:
                pass
            
            await state.clear()
        finally:
            db.close()
    except ValueError:
        await message.answer("Введите корректное число")


@router.message(F.text.in_([config.BUTTONS.get("profile", "👤 Профиль"), "👤 Профиль"]))
async def show_profile(message: Message):
    """Показать профиль"""
    db = next(get_db())
    try:
        user = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        text = utils.format_user_info(user)
        keyboard = kb.get_profile_keyboard()
        _, profile_photo = utils.get_bot_response_with_media(db, "profile", "")
        if profile_photo:
            await message.answer_photo(profile_photo, caption=text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)
    finally:
        db.close()


@router.callback_query(F.data == "purchase_history")
async def show_purchase_history(callback: CallbackQuery):
    """Показать историю покупок"""
    db = next(get_db())
    try:
        user = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        
        purchases = db.query(Purchase).filter(Purchase.user_id == user.id).order_by(Purchase.created_at.desc()).all()
        
        if not purchases:
            await callback.message.answer("История покупок пуста")
            await callback.answer()
            return
        
        keyboard = kb.get_purchase_history_keyboard(purchases)
        await callback.message.answer("📜 История покупок:", reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("purchase_"))
async def show_purchase_details(callback: CallbackQuery):
    """Показать детали покупки"""
    purchase_id = int(callback.data.split("_")[1])
    db = next(get_db())
    try:
        purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
        if not purchase:
            await callback.answer("Покупка не найдена")
            return
        
        user = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        if purchase.user_id != user.id:
            await callback.answer("Это не ваша покупка")
            return
        
        item = purchase.item
        text = f"📦 Заказ #{purchase.id}\n\n"
        text += f"Товар: {item.name}\n"
        text += f"Количество: {purchase.quantity}\n"
        text += f"Сумма: {purchase.total_price:.2f} USDT\n"
        text += f"Дата: {purchase.created_at.strftime('%d.%m.%Y %H:%M')}"
        
        keyboard = kb.get_purchase_keyboard(purchase_id)
        await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("get_product_"))
async def get_purchase_product(callback: CallbackQuery):
    """Получить товар из покупки"""
    purchase_id = int(callback.data.split("_")[2])
    db = next(get_db())
    try:
        purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
        if not purchase:
            await callback.answer("Покупка не найдена")
            return
        
        user = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        if purchase.user_id != user.id:
            await callback.answer("Это не ваша покупка")
            return
        
        item = purchase.item
        if item.product_type == 'string':
            # Получаем все проданные товары для этой покупки
            # Берем товары, которые были проданы в момент покупки
            products = db.query(Product).filter(
                Product.item_id == item.id,
                Product.is_sold == True,
                Product.sold_at <= purchase.created_at
            ).order_by(Product.sold_at.desc()).limit(purchase.quantity).all()
            
            if products:
                products_text = "\n".join([p.content for p in reversed(products)])
                await callback.message.answer(f"📦 Ваш товар:\n\n{products_text}")
            else:
                # Если не нашли по времени, берем любые проданные
                products = db.query(Product).filter(
                    Product.item_id == item.id,
                    Product.is_sold == True
                ).limit(purchase.quantity).all()
                if products:
                    products_text = "\n".join([p.content for p in products])
                    await callback.message.answer(f"📦 Ваш товар:\n\n{products_text}")
        else:
            product = purchase.product
            if product:
                if product.file_id:
                    await callback.message.answer_document(product.file_id)
                elif product.file_path:
                    file = FSInputFile(product.file_path)
                    await callback.message.answer_document(file)
        
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("history_page_"))
async def history_page(callback: CallbackQuery):
    """Навигация по страницам истории"""
    page = int(callback.data.split("_")[2])
    db = next(get_db())
    try:
        user = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        
        purchases = db.query(Purchase).filter(Purchase.user_id == user.id).order_by(Purchase.created_at.desc()).all()
        keyboard = kb.get_purchase_history_keyboard(purchases, page=page)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.message(F.text.in_([config.BUTTONS.get("balance", "💳 Пополнить баланс"), "💳 Пополнить баланс"]))
async def show_balance(message: Message, state: FSMContext):
    """Показать баланс и предложить пополнение"""
    db = next(get_db())
    try:
        user = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        await state.set_state(PurchaseStates.waiting_payment_amount)
        
        # Создаем клавиатуру с кнопкой отмены
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_payment_input"))
        builder.adjust(1)
        
        await message.answer(
            f"💰 Ваш баланс: {user.balance:.2f} USDT\n\nВведите сумму пополнения (минимум 1 USDT):",
            reply_markup=builder.as_markup()
        )
    finally:
        db.close()


@router.message(PurchaseStates.waiting_payment_amount)
async def process_payment_amount(message: Message, state: FSMContext):
    """Обработка суммы пополнения"""
    # Проверяем, что это не команда или кнопка
    if not message.text or message.text.startswith('/') or message.text == "🔐 Админ-панель":
        # Если это команда или кнопка, очищаем состояние и не обрабатываем
        await state.clear()
        return
    
    try:
        amount = float(message.text.replace(',', '.'))
        if amount < 1:
            await message.answer("Минимальная сумма пополнения: 1 USDT")
            return
        
        db = next(get_db())
        try:
            user = get_or_create_user(
                db,
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
            
            # Создание инвойса
            invoice = await utils.create_cryptobot_invoice(amount, user.user_id)
            if not invoice:
                await message.answer("Ошибка создания платежа. Попробуйте позже.")
                await state.clear()  # Очищаем состояние при ошибке
                return
            
            # Сохранение платежа
            payment = Payment(
                user_id=user.id,
                amount=amount,
                cryptobot_invoice_id=str(invoice.get("invoice_id")),
                status='pending'
            )
            db.add(payment)
            db.commit()
            
            # Сохраняем payment_id в состоянии для проверки
            await state.update_data(payment_id=payment.id, invoice_id=invoice.get("invoice_id"))
            
            # Создаем клавиатуру с кнопками
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_payment_{payment.id}"))
            builder.add(InlineKeyboardButton(text="✅ Проверить платеж", callback_data=f"check_payment_{payment.id}"))
            builder.adjust(1)
            
            payment_text = (
                f"{config.TEXTS['payment_link']}\n\n"
                f"💰 Сумма: {amount} USDT\n"
                f"🔗 Ссылка: {invoice.get('pay_url')}\n\n"
                f"⏰ У вас есть 15 минут на оплату\n"
                f"После оплаты нажмите кнопку 'Проверить платеж'"
            )
            
            await message.answer(payment_text, reply_markup=builder.as_markup())
            
            # Не очищаем состояние, чтобы можно было проверить платеж
        finally:
            db.close()
    except ValueError:
        await message.answer("❌ Введите корректное число (например: 10.50 или 10):")
        # Не очищаем состояние, чтобы пользователь мог попробовать снова


@router.message(F.text.in_([config.BUTTONS.get("faq", "❓ FAQ"), "❓ FAQ"]))
async def show_faq(message: Message):
    """Показать FAQ"""
    db = next(get_db())
    try:
        faq_text, faq_photo = utils.get_bot_response_with_media(db, "faq", config.TEXTS["faq"])
        if faq_photo:
            try:
                await message.answer_photo(faq_photo, caption=faq_text)
            except Exception:
                # Если фото невалидно, отправляем без фото
                await message.answer(faq_text)
        else:
            await message.answer(faq_text)
    finally:
        db.close()


@router.message(F.text.in_([config.BUTTONS.get("support", "💬 Поддержка"), "💬 Поддержка"]))
async def show_support(message: Message):
    """Показать поддержку"""
    db = next(get_db())
    try:
        support_text, support_photo = utils.get_bot_response_with_media(db, "support", config.TEXTS["support"])
        
        # Inline кнопка для перехода в поддержку
        support_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/Socks7")
        ]])
        
        if support_photo:
            try:
                await message.answer_photo(support_photo, caption=support_text, reply_markup=support_keyboard)
            except Exception:
                await message.answer(support_text, reply_markup=support_keyboard)
        else:
            await message.answer(support_text, reply_markup=support_keyboard)
    finally:
        db.close()


@router.message(F.text.in_([config.BUTTONS.get("user_agreement", "📋 Соглашение"), "📋 Соглашение"]))
async def show_user_agreement(message: Message):
    """Показать пользовательское соглашение"""
    db = next(get_db())
    try:
        agreement_text, agreement_photo = utils.get_bot_response_with_media(db, "user_agreement", config.TEXTS["user_agreement"])
        if agreement_photo:
            try:
                await message.answer_photo(agreement_photo, caption=agreement_text)
            except Exception:
                # Если фото невалидно, отправляем без фото
                await message.answer(agreement_text)
        else:
            await message.answer(agreement_text)
    finally:
        db.close()


@router.message(F.text)
async def handle_custom_button(message: Message):
    """Обработчик кастомных кнопок"""
    # Пропускаем команды
    if message.text.startswith('/'):
        return
    
    # Пропускаем админов полностью (их сообщения обрабатываются в admin_handlers)
    if message.from_user.id in config.ADMIN_IDS:
        return
    
    # Пропускаем стандартные кнопки (они обрабатываются отдельными обработчиками)
    standard_button_texts = [
        config.BUTTONS.get("buy", "🛒 Купить"),
        "🛒 Купить",
        config.BUTTONS.get("profile", "👤 Профиль"),
        "👤 Профиль",
        config.BUTTONS.get("faq", "❓ FAQ"),
        "❓ FAQ",
        config.BUTTONS.get("support", "💬 Поддержка"),
        "💬 Поддержка",
        config.BUTTONS.get("balance", "💳 Пополнить баланс"),
        "💳 Пополнить баланс",
        config.BUTTONS.get("user_agreement", "📋 Соглашение"),
        "📋 Соглашение",
        "🔐 Админ-панель"
    ]
    if message.text in standard_button_texts:
        return
    
    db = next(get_db())
    try:
        # Проверяем, есть ли кнопка с таким текстом
        button = db.query(Button).filter(
            Button.name == message.text,
            Button.is_enabled == True
        ).first()
        
        if button:
            # Стандартные действия обрабатываются отдельными обработчиками
            standard_actions = ["buy", "profile", "faq", "support", "balance", "user_agreement"]
            
            if button.action not in standard_actions:
                # Кастомное действие - используем ответ из BotResponse
                response_key = f"button_{button.action}"
                response_text, response_photo = utils.get_bot_response_with_media(db, response_key, f"Ответ для кнопки '{button.name}'")
                
                if response_photo:
                    try:
                        await message.answer_photo(response_photo, caption=response_text)
                    except Exception:
                        # Если фото невалидно, отправляем без фото
                        await message.answer(response_text)
                else:
                    await message.answer(response_text)
    finally:
        db.close()


@router.callback_query(F.data == "activate_promocode")
async def ask_promocode(callback: CallbackQuery, state: FSMContext):
    """Запрос промокода"""
    await state.set_state(PurchaseStates.waiting_promocode)
    await callback.message.answer("Введите промокод:")
    await callback.answer()


@router.message(PurchaseStates.waiting_promocode)
async def process_promocode(message: Message, state: FSMContext):
    """Обработка промокода"""
    promocode_text = message.text.upper().strip()
    db = next(get_db())
    try:
        promocode = db.query(Promocode).filter(Promocode.code == promocode_text).first()
        
        if not promocode or not promocode.is_active:
            await message.answer(config.TEXTS["promocode_invalid"])
            await state.clear()
            return
        
        if promocode.expires_at and promocode.expires_at < datetime.now():
            await message.answer(config.TEXTS["promocode_expired"])
            await state.clear()
            return
        
        if promocode.current_activations >= promocode.max_activations:
            await message.answer(config.TEXTS["promocode_used"])
            await state.clear()
            return
        
        user = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        if promocode.user_id_bound and promocode.user_id_bound != user.user_id:
            await message.answer(config.TEXTS["promocode_user_bound"])
            await state.clear()
            return
        
        # Активация промокода
        activation = PromocodeActivation(
            promocode_id=promocode.id,
            user_id=user.id
        )
        db.add(activation)
        
        promocode.current_activations += 1
        user.balance += promocode.amount
        user.total_deposits += promocode.amount
        
        db.commit()
        
        # Логирование
        utils.log_action(db, "promocode_activation", user_id=user.id, data={
            "promocode_id": promocode.id,
            "code": promocode.code,
            "amount": promocode.amount
        })
        
        await message.answer(f"{config.TEXTS['promocode_activated']}\nНачислено: {promocode.amount:.2f} USDT")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Вернуться в главное меню"""
    db = next(get_db())
    try:
        keyboard = kb.get_main_keyboard(db, callback.from_user.id)
        start_text, start_photo = utils.get_bot_response_with_media(db, "start", config.TEXTS["start"])
        if start_photo:
            try:
                await callback.message.answer_photo(start_photo, caption=start_text, reply_markup=keyboard)
            except Exception:
                # Если фото невалидно, отправляем без фото
                await callback.message.answer(start_text, reply_markup=keyboard)
        else:
            await callback.message.answer(start_text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    """Вернуться к категориям"""
    # Удаляем предыдущее сообщение
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    db = next(get_db())
    try:
        keyboard = kb.get_categories_keyboard(db)
        buy_text, buy_photo = utils.get_bot_response_with_media(db, "buy", "📦 Выберите категорию:")
        if buy_photo:
            await callback.message.answer_photo(buy_photo, caption=buy_text, reply_markup=keyboard)
        else:
            await callback.message.answer(buy_text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("back_to_category_"))
async def back_to_category(callback: CallbackQuery):
    """Вернуться к категории (показать подкатегории категории)"""
    try:
        category_id = int(callback.data.split("_")[3])
    except (ValueError, IndexError):
        await callback.answer("Ошибка навигации")
        return
    
    # Удаляем предыдущее сообщение
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    db = next(get_db())
    try:
        category = db.query(Category).filter(Category.id == category_id).first()
        if not category:
            await callback.answer("Категория не найдена")
            return
        
        keyboard = kb.get_subcategories_keyboard(db, category_id)
        text = f"📂 {category.name}\n\n{category.description or ''}"
        
        if category.photo:
            try:
                await callback.message.answer_photo(category.photo, caption=text, reply_markup=keyboard)
            except Exception:
                await callback.message.answer(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("back_to_subcategory_"))
async def back_to_subcategory(callback: CallbackQuery):
    """Вернуться к подкатегории"""
    try:
        subcategory_id = int(callback.data.split("_")[3])
    except (ValueError, IndexError):
        await callback.answer("Ошибка навигации")
        return
    
    # Удаляем предыдущее сообщение
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    db = next(get_db())
    try:
        subcategory = db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
        if not subcategory:
            await callback.answer("Подкатегория не найдена")
            return
        
        hide_out_of_stock = utils.get_setting(db, "hide_out_of_stock", False)
        keyboard = kb.get_items_keyboard(db, subcategory_id, hide_out_of_stock)
        text = f"📋 {subcategory.name}\n\n{subcategory.description or ''}"
        
        if subcategory.photo:
            try:
                await callback.message.answer_photo(subcategory.photo, caption=text, reply_markup=keyboard)
            except Exception:
                await callback.message.answer(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "back_to_items")
async def back_to_items(callback: CallbackQuery):
    """Вернуться к позициям (устаревший обработчик, используется back_to_subcategory)"""
    await callback.answer("Используйте кнопку 'Назад' в меню")


@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: CallbackQuery):
    """Вернуться в профиль"""
    db = next(get_db())
    try:
        user = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        
        text = utils.format_user_info(user)
        keyboard = kb.get_profile_keyboard()
        await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "profile_balance")
async def profile_balance(callback: CallbackQuery, state: FSMContext):
    """Пополнение баланса из профиля"""
    db = next(get_db())
    try:
        user = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        
        await state.set_state(PurchaseStates.waiting_payment_amount)
        
        # Создаем клавиатуру с кнопкой отмены
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_payment_input"))
        builder.adjust(1)
        
        await callback.message.answer(
            f"💰 Ваш баланс: {user.balance:.2f} USDT\n\nВведите сумму пополнения (минимум 1 USDT):",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "cancel_payment_input")
async def cancel_payment_input(callback: CallbackQuery, state: FSMContext):
    """Отмена ввода суммы пополнения"""
    await state.clear()
    await callback.message.edit_text("❌ Пополнение баланса отменено")
    await callback.answer("Пополнение отменено")


@router.callback_query(F.data.startswith("cancel_payment_"))
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    """Отмена платежа"""
    try:
        payment_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка")
        return
    
    db = next(get_db())
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            await callback.answer("Платеж не найден")
            return
        
        # Проверяем, что платеж принадлежит пользователю
        user = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        if payment.user_id != user.id:
            await callback.answer("Доступ запрещен")
            return
        
        # Если платеж еще не оплачен, можно отменить
        if payment.status == 'pending':
            # Просто очищаем состояние
            await state.clear()
            await callback.message.edit_text("❌ Платеж отменен")
            await callback.answer("Платеж отменен")
        else:
            await callback.answer("Платеж уже обработан")
    finally:
        db.close()


@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment(callback: CallbackQuery, state: FSMContext):
    """Проверка платежа"""
    try:
        payment_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка")
        return
    
    db = next(get_db())
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            await callback.answer("Платеж не найден")
            return
        
        # Проверяем, что платеж принадлежит пользователю
        user = get_or_create_user(
            db,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        if payment.user_id != user.id:
            await callback.answer("Доступ запрещен")
            return
        
        # Проверяем время (15 минут)
        from datetime import datetime, timedelta
        time_diff = datetime.now() - payment.created_at
        if time_diff > timedelta(minutes=15):
            await callback.answer("⏰ Время на оплату истекло. Создайте новый платеж.", show_alert=True)
            await state.clear()
            return
        
        # Проверяем статус платежа через CryptoBot API
        if payment.cryptobot_invoice_id:
            try:
                invoice_data = await utils.check_cryptobot_invoice(int(payment.cryptobot_invoice_id))
                
                if invoice_data and invoice_data.get("status") == "paid":
                    # Платеж оплачен
                    if payment.status != 'paid':
                        payment.status = 'paid'
                        payment.paid_at = datetime.now()
                        user.balance += payment.amount
                        db.commit()
                        
                        # Уведомление админу
                        await utils.send_admin_notification(
                            callback.bot,
                            "new_payment",
                            f"Новое пополнение!\nСумма: {payment.amount} USDT",
                            user_id=user.user_id,
                            username=user.username
                        )
                        
                        await callback.message.edit_text(
                            f"✅ Платеж успешно обработан!\n\n"
                            f"💰 Сумма: {payment.amount:.2f} USDT\n"
                            f"💳 Ваш баланс: {user.balance:.2f} USDT"
                        )
                        await callback.answer("Платеж успешно обработан!")
                        await state.clear()
                    else:
                        await callback.answer("✅ Платеж уже обработан", show_alert=True)
                elif invoice_data and invoice_data.get("status") == "expired":
                    # Платеж истек
                    await callback.answer("⏰ Время на оплату истекло. Создайте новый платеж.", show_alert=True)
                    await state.clear()
                else:
                    # Платеж еще не оплачен (active или другой статус)
                    await callback.answer("⏳ Платеж еще не получен. Попробуйте позже.", show_alert=True)
            except Exception as e:
                await callback.answer(f"❌ Ошибка проверки платежа: {str(e)}", show_alert=True)
        else:
            await callback.answer("❌ Ошибка: ID платежа не найден", show_alert=True)
    finally:
        db.close()


@router.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery):
    """Проверка подписки на канал"""
    db = next(get_db())
    try:
        # Проверяем подписку
        if await utils.check_channel_subscription(callback.bot, callback.from_user.id):
            await callback.answer("✅ Вы подписаны на канал!", show_alert=True)
            # Отправляем приветственное сообщение
            start_text, start_photo = utils.get_bot_response_with_media(db, "start", config.TEXTS["start"])
            keyboard = kb.get_main_keyboard(db, callback.from_user.id)
            if start_photo:
                await callback.message.answer_photo(start_photo, caption=start_text, reply_markup=keyboard)
            else:
                await callback.message.answer(start_text, reply_markup=keyboard)
        else:
            channel_id = utils.get_setting(db, "required_channel_id", None)
            if channel_id:
                # Обновляем кнопки
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                builder = InlineKeyboardBuilder()
                
                if isinstance(channel_id, str) and channel_id.startswith('@'):
                    builder.add(InlineKeyboardButton(
                        text="📢 Канал",
                        url=f"https://t.me/{channel_id[1:]}"
                    ))
                else:
                    try:
                        chat_id = int(channel_id) if isinstance(channel_id, str) else channel_id
                        # Пытаемся получить invite link
                        try:
                            chat = await callback.bot.get_chat(chat_id)
                            if chat.username:
                                builder.add(InlineKeyboardButton(
                                    text="📢 Канал",
                                    url=f"https://t.me/{chat.username}"
                                ))
                            else:
                                invite_link = await callback.bot.export_chat_invite_link(chat_id)
                                builder.add(InlineKeyboardButton(
                                    text="📢 Канал",
                                    url=invite_link
                                ))
                        except:
                            builder.add(InlineKeyboardButton(
                                text="📢 Канал",
                                url=f"https://t.me/c/{str(abs(chat_id))[4:]}"
                            ))
                    except:
                        builder.add(InlineKeyboardButton(
                            text="📢 Канал",
                            url=f"https://t.me/{channel_id}"
                        ))
                
                builder.add(InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data="check_subscription"
                ))
                builder.adjust(1)
                
                try:
                    await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
                except:
                    pass
                await callback.answer("❌ Вы не подписаны на канал", show_alert=True)
            else:
                await callback.answer("❌ Вы не подписаны на канал", show_alert=True)
    finally:
        db.close()

