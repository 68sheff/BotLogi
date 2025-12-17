"""
Модели базы данных
SQLite с использованием SQLAlchemy
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import text
from datetime import datetime
import json

Base = declarative_base()

# Создание движка БД
engine = create_engine(f'sqlite:///{__import__("config").DATABASE_PATH}', echo=False)
SessionLocal = sessionmaker(bind=engine)


class User(Base):
    """Пользователь"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    balance = Column(Float, default=0.0)
    total_deposits = Column(Float, default=0.0)
    is_blocked = Column(Boolean, default=False)
    block_type = Column(String(20), default='normal')  # 'normal' или 'silent'
    block_reason = Column(Text)  # Причина блокировки
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    purchases = relationship("Purchase", back_populates="user")
    promocode_activations = relationship("PromocodeActivation", back_populates="user")


class Category(Base):
    """Категория товаров"""
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    photo = Column(String(500))  # file_id или путь
    position = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    
    subcategories = relationship("Subcategory", back_populates="category", order_by="Subcategory.position")


class Subcategory(Base):
    """Подкатегория"""
    __tablename__ = 'subcategories'
    
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    photo = Column(String(500))
    position = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    
    category = relationship("Category", back_populates="subcategories")
    items = relationship("Item", back_populates="subcategory", order_by="Item.position")


class Item(Base):
    """Позиция товара"""
    __tablename__ = 'items'
    
    id = Column(Integer, primary_key=True)
    subcategory_id = Column(Integer, ForeignKey('subcategories.id'), nullable=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    photo = Column(String(500))
    position = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)
    product_type = Column(String(20), nullable=False)  # 'string' или 'file'
    out_of_stock_behavior = Column(String(50), default='show_no_stock')  # 'show_no_stock', 'hide', 'show_no_button'
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    subcategory = relationship("Subcategory", back_populates="items")
    category = relationship("Category", backref="items")
    products = relationship("Product", back_populates="item")
    purchases = relationship("Purchase", back_populates="item")


class Product(Base):
    """Товар (строка или файл)"""
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    content = Column(Text)  # Для строковых товаров - содержимое строки
    file_path = Column(String(500))  # Для файловых товаров - путь к файлу
    file_id = Column(String(500))  # Telegram file_id
    is_sold = Column(Boolean, default=False)
    sold_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    
    item = relationship("Item", back_populates="products")
    purchases = relationship("Purchase", back_populates="product")


class Purchase(Base):
    """Покупка"""
    __tablename__ = 'purchases'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'))
    quantity = Column(Integer, default=1)
    total_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="purchases")
    item = relationship("Item", back_populates="purchases")
    product = relationship("Product", back_populates="purchases")


class Payment(Base):
    """Платеж"""
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    cryptobot_invoice_id = Column(String(255))
    status = Column(String(50), default='pending')  # pending, paid, failed
    created_at = Column(DateTime, default=datetime.now)
    paid_at = Column(DateTime)


class Promocode(Base):
    """Промокод"""
    __tablename__ = 'promocodes'
    
    id = Column(Integer, primary_key=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    max_activations = Column(Integer, default=1)
    current_activations = Column(Integer, default=0)
    expires_at = Column(DateTime)
    user_id_bound = Column(Integer)  # Привязка к пользователю (опционально)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    
    activations = relationship("PromocodeActivation", back_populates="promocode")


class PromocodeActivation(Base):
    """Активация промокода"""
    __tablename__ = 'promocode_activations'
    
    id = Column(Integer, primary_key=True)
    promocode_id = Column(Integer, ForeignKey('promocodes.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    promocode = relationship("Promocode", back_populates="activations")
    user = relationship("User", back_populates="promocode_activations")


class Button(Base):
    """Кнопка главного меню"""
    __tablename__ = 'buttons'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    action = Column(String(100), nullable=False)  # buy, profile, faq, support, balance, user_agreement
    position = Column(Integer, default=0)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class BotResponse(Base):
    """Ответы бота (редактируемые тексты)"""
    __tablename__ = 'bot_responses'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    text = Column(Text, nullable=False)
    photo = Column(String(500))  # file_id для фото
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Log(Base):
    """Лог действий"""
    __tablename__ = 'logs'
    
    id = Column(Integer, primary_key=True)
    log_type = Column(String(100), nullable=False)  # purchase, payment, promocode_create, etc.
    user_id = Column(Integer)
    admin_id = Column(Integer)
    data = Column(Text)  # JSON данные
    created_at = Column(DateTime, default=datetime.now)


class Setting(Base):
    """Настройки бота"""
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(engine)
    
    # Миграции
    db = SessionLocal()
    try:
        from sqlalchemy import text as sql_text
        
        # Миграция: добавляем колонку photo в bot_responses если её нет
        result = db.execute(sql_text("PRAGMA table_info(bot_responses)"))
        columns = [row[1] for row in result]
        if 'photo' not in columns:
            db.execute(sql_text("ALTER TABLE bot_responses ADD COLUMN photo VARCHAR(500)"))
            db.commit()
            print("Миграция: добавлена колонка photo в bot_responses")
        
        # Миграция: добавляем колонки block_type и block_reason в users если их нет
        result = db.execute(sql_text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result]
        if 'block_type' not in columns:
            db.execute(sql_text("ALTER TABLE users ADD COLUMN block_type VARCHAR(20) DEFAULT 'normal'"))
            db.commit()
            print("Миграция: добавлена колонка block_type в users")
        if 'block_reason' not in columns:
            db.execute(sql_text("ALTER TABLE users ADD COLUMN block_reason TEXT"))
            db.commit()
            print("Миграция: добавлена колонка block_reason в users")
        
        # Миграция: добавляем колонку category_id в items если её нет
        result = db.execute(sql_text("PRAGMA table_info(items)"))
        columns = [row[1] for row in result]
        if 'category_id' not in columns:
            db.execute(sql_text("ALTER TABLE items ADD COLUMN category_id INTEGER REFERENCES categories(id)"))
            db.commit()
            print("Миграция: добавлена колонка category_id в items")
    except Exception as e:
        print(f"Ошибка при миграции: {e}")
        db.rollback()
    finally:
        db.close()
    
    # Создаем дефолтные ответы бота
    db = SessionLocal()
    try:
        default_responses = {
            "start": __import__("config").TEXTS["start"],
            "faq": __import__("config").TEXTS["faq"],
            "support": __import__("config").TEXTS["support"],
            "user_agreement": "Пользовательское соглашение",
            "purchase_success": __import__("config").TEXTS["purchase_success"],
            "product_out_of_stock": __import__("config").TEXTS["product_out_of_stock"],
            "maintenance": __import__("config").TEXTS["maintenance"],
            "block_appeal": "Для апелляции - @Flyovv",
        }
        
        for key, text in default_responses.items():
            if not db.query(BotResponse).filter(BotResponse.key == key).first():
                db.add(BotResponse(key=key, text=text))
        
        # Создаем дефолтные кнопки
        default_buttons = [
            ("buy", __import__("config").BUTTONS["buy"], 0),
            ("profile", __import__("config").BUTTONS["profile"], 1),
            ("faq", __import__("config").BUTTONS["faq"], 2),
            ("support", __import__("config").BUTTONS["support"], 3),
            ("balance", __import__("config").BUTTONS["balance"], 4),
            ("user_agreement", __import__("config").BUTTONS["user_agreement"], 5),
        ]
        
        for action, name, pos in default_buttons:
            if not db.query(Button).filter(Button.action == action).first():
                db.add(Button(name=name, action=action, position=pos))
        
        # Создаем дефолтные настройки
        default_settings = __import__("config").DEFAULT_SETTINGS
        for key, value in default_settings.items():
            if not db.query(Setting).filter(Setting.key == key).first():
                db.add(Setting(key=key, value=str(value)))
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Ошибка при инициализации БД: {e}")
    finally:
        db.close()


def get_db():
    """Получить сессию БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

