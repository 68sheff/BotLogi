"""
Утилиты для бота
"""

import aiohttp
import json
from datetime import datetime
from database import Log, Setting, User, BotResponse, get_db
from sqlalchemy.orm import Session
import config


async def check_channel_subscription(bot, user_id: int) -> bool:
    """Проверка подписки на канал"""
    from database import SessionLocal
    db = SessionLocal()
    try:
        channel_enabled = get_setting(db, "channel_subscription_enabled", False)
        if not channel_enabled:
            return True
        
        channel_id = get_setting(db, "required_channel_id", None)
        if not channel_id:
            return True
    finally:
        db.close()
    
    if user_id in config.ADMIN_IDS:
        return True
    
    try:
        # Парсим channel_id (может быть строкой или числом)
        if isinstance(channel_id, str):
            if channel_id.startswith('@'):
                chat_id = channel_id
            else:
                try:
                    chat_id = int(channel_id)
                except ValueError:
                    return False
        else:
            chat_id = channel_id
        
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        # Если ошибка - разрешаем доступ (чтобы не блокировать пользователей)
        print(f"Ошибка проверки подписки: {e}")
        return True


async def create_cryptobot_invoice(amount: float, user_id: int) -> dict:
    """Создание инвойса в CryptoBot"""
    if not config.CRYPTOBOT_TOKEN:
        return None
    
    url = f"{config.CRYPTOBOT_API_URL}/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": config.CRYPTOBOT_TOKEN
    }
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"Пополнение баланса для пользователя {user_id}",
        "paid_btn_name": "viewItem",
        "paid_btn_url": f"https://t.me/{config.BOT_TOKEN.split(':')[0]}",
        "hidden": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                result = await response.json()
                if result.get("ok"):
                    return result.get("result")
                return None
    except Exception as e:
        print(f"Ошибка создания инвойса: {e}")
        return None


async def check_cryptobot_invoice(invoice_id: int) -> dict:
    """Проверка статуса инвойса"""
    if not config.CRYPTOBOT_TOKEN:
        return None
    
    url = f"{config.CRYPTOBOT_API_URL}/getInvoices"
    headers = {
        "Crypto-Pay-API-Token": config.CRYPTOBOT_TOKEN
    }
    params = {
        "invoice_ids": str(invoice_id)
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                result = await response.json()
                if result.get("ok"):
                    invoices = result.get("result", {}).get("items", [])
                    if invoices:
                        return invoices[0]
                return None
    except Exception as e:
        print(f"Ошибка проверки инвойса: {e}")
        return None


def log_action(db: Session, log_type: str, user_id: int = None, admin_id: int = None, data: dict = None):
    """Логирование действия"""
    log = Log(
        log_type=log_type,
        user_id=user_id,
        admin_id=admin_id,
        data=json.dumps(data, ensure_ascii=False) if data else None
    )
    db.add(log)
    db.commit()


def get_setting(db: Session, key: str, default=None):
    """Получить настройку"""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        try:
            # Пытаемся преобразовать в bool
            if setting.value.lower() in ['true', 'false']:
                return setting.value.lower() == 'true'
            return setting.value
        except:
            return setting.value
    return default


def set_setting(db: Session, key: str, value):
    """Установить настройку"""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        setting.value = str(value)
    else:
        setting = Setting(key=key, value=str(value))
        db.add(setting)
    db.commit()


def get_bot_response(db: Session, key: str, default: str = "") -> str:
    """Получить ответ бота (только текст)"""
    response = db.query(BotResponse).filter(BotResponse.key == key).first()
    return response.text if response else default


def get_bot_response_with_media(db: Session, key: str, default: str = ""):
    """Получить ответ бота с медиа (возвращает tuple: (text, photo_id))"""
    response = db.query(BotResponse).filter(BotResponse.key == key).first()
    if response:
        return (response.text or default, response.photo)
    return (default, None)


def format_user_info(user: User) -> str:
    """Форматирование информации о пользователе"""
    return f"""👤 Профиль

🆔 ID: {user.user_id}
👤 Ник: @{user.username or 'не указан'}
💰 Баланс: {user.balance:.2f} USDT
💳 Всего пополнено: {user.total_deposits:.2f} USDT
📅 Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}
{'🚫 Заблокирован' if user.is_blocked else '✅ Активен'}"""


def format_statistics(db: Session) -> str:
    """Форматирование статистики"""
    from database import Purchase, Payment, Product
    
    total_users = db.query(User).count()
    total_purchases = db.query(Purchase).count()
    total_payments = db.query(Payment).filter(Payment.status == 'paid').all()
    total_revenue = sum(p.amount for p in total_payments)
    
    # Остатки товаров
    total_products = db.query(Product).filter(Product.is_sold == False).count()
    sold_products = db.query(Product).filter(Product.is_sold == True).count()
    
    return f"""📊 Статистика

👥 Пользователей: {total_users}
🛒 Покупок: {total_purchases}
💳 Пополнений: {len(total_payments)}
💰 Выручка: {total_revenue:.2f} USDT
📦 Товаров в наличии: {total_products}
✅ Продано товаров: {sold_products}"""


def check_user_blocked(db: Session, user_id: int) -> tuple[bool, str, str]:
    """
    Проверка блокировки пользователя
    Возвращает: (is_blocked, block_type, block_reason)
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user or not user.is_blocked:
        return (False, None, None)
    return (True, user.block_type or 'normal', user.block_reason or '')


async def send_blocked_message(bot, chat_id: int, block_reason: str = ""):
    """Отправка сообщения о блокировке"""
    db = next(get_db())
    try:
        appeal_text = get_bot_response(db, "block_appeal", "Для апелляции - @Flyovv")
        
        message_text = "Вам был ограничен доступ к данному боту"
        if block_reason:
            message_text += f"\n\nПричина:\n{block_reason}"
        if appeal_text:
            message_text += f"\n\n{appeal_text}"
        
        await bot.send_message(chat_id, message_text)
    finally:
        db.close()


async def send_admin_notification(bot, notification_type: str, message: str, user_id: int = None, username: str = None):
    """Отправка уведомления админу"""
    from database import SessionLocal, User
    db = SessionLocal()
    try:
        if get_setting(db, f"notify_{notification_type}", True):
            # Формируем информацию о пользователе
            user_info = ""
            if user_id:
                # Получаем username из БД, если не передан
                if not username:
                    user = db.query(User).filter(User.user_id == user_id).first()
                    if user:
                        username = user.username
                
                user_info = f"\n👤 ID: {user_id}"
                if username:
                    user_info += f"\n📱 Username: @{username}"
                elif not username:
                    user_info += "\n📱 Username: не указан"
            
            full_message = f"🔔 {message}{user_info}"
            
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, full_message)
                except:
                    pass
    finally:
        db.close()

