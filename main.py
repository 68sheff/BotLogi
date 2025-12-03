"""
Главный файл бота
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database import init_db
from handlers import user_handlers, admin_handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOGS_DIR / 'bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def check_payments(bot: Bot):
    """Периодическая проверка платежей"""
    from database import SessionLocal, Payment, User
    from datetime import datetime
    import utils
    
    while True:
        try:
            db = SessionLocal()
            try:
                pending_payments = db.query(Payment).filter(Payment.status == 'pending').all()
                
                for payment in pending_payments:
                    invoice = await utils.check_cryptobot_invoice(int(payment.cryptobot_invoice_id))
                    
                    if invoice and invoice.get('status') == 'paid':
                        payment.status = 'paid'
                        payment.paid_at = datetime.now()
                        
                        user = db.query(User).filter(User.id == payment.user_id).first()
                        if user:
                            user.balance += payment.amount
                            user.total_deposits += payment.amount
                            
                            # Уведомление пользователю
                            try:
                                await bot.send_message(
                                    user.user_id,
                                    f"{config.TEXTS['payment_success']}\n"
                                    f"Зачислено: {payment.amount:.2f} USDT"
                                )
                            except:
                                pass
                            
                            # Уведомление админу
                            await utils.send_admin_notification(
                                bot,
                                "new_payment",
                                f"Новое пополнение!\nСумма: {payment.amount} USDT",
                                user_id=user.user_id,
                                username=user.username
                            )
                            
                            # Логирование
                            utils.log_action(db, "payment", user_id=user.id, data={
                                "amount": payment.amount,
                                "payment_id": payment.id
                            })
                
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Ошибка проверки платежей: {e}")
        
        await asyncio.sleep(30)  # Проверка каждые 30 секунд


async def main():
    """Главная функция"""
    # Инициализация БД
    logger.info("Инициализация базы данных...")
    init_db()
    logger.info("База данных инициализирована")
    
    # Загрузка настроек из БД в config
    from database import SessionLocal
    import utils
    db = SessionLocal()
    try:
        # Загружаем токен CryptoBot из БД
        cryptobot_token = utils.get_setting(db, "cryptobot_token", None)
        if cryptobot_token:
            config.CRYPTOBOT_TOKEN = cryptobot_token
            logger.info("Токен CryptoBot загружен из БД")
        else:
            logger.info("Токен CryptoBot не найден в БД, используется из config.py")
        
        # Загружаем ID канала из БД
        channel_id = utils.get_setting(db, "required_channel_id", None)
        if channel_id:
            config.REQUIRED_CHANNEL_ID = channel_id if isinstance(channel_id, int) or (isinstance(channel_id, str) and channel_id.lstrip('-').isdigit()) else channel_id
    finally:
        db.close()
    
    # Создание бота и диспетчера
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация роутеров
    # Важно: сначала админ-роутер, чтобы админские команды обрабатывались первыми
    dp.include_router(admin_handlers.router)
    
    # Добавляем middleware для проверки блокировки в user_handlers
    user_handlers.router.message.middleware(user_handlers.BlockedUserMiddleware())
    user_handlers.router.callback_query.middleware(user_handlers.BlockedUserMiddleware())
    
    dp.include_router(user_handlers.router)
    
    # Запуск проверки платежей в фоне
    asyncio.create_task(check_payments(bot))
    
    # Запуск бота
    logger.info("Запуск бота...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        logger.info("Возможно, другой экземпляр бота уже запущен. Остановите его и попробуйте снова.")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")

