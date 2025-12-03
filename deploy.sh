#!/bin/bash
# Скрипт для быстрого развертывания бота на VDS

set -e

echo "🚀 Начало развертывания Telegram бота..."

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не установлен. Установите его: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

# Проверка версии Python
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Требуется Python 3.10 или выше. Установлен: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION найден"

# Проверка наличия python3-venv
if ! python3 -m venv --help &> /dev/null; then
    echo "⚠️  python3-venv не установлен. Попытка установки..."
    if command -v sudo &> /dev/null; then
        sudo apt install -y python3-venv || {
            echo "❌ Не удалось установить python3-venv. Установите вручную:"
            echo "   sudo apt install python3-venv"
            exit 1
        }
    else
        echo "❌ Требуется sudo для установки python3-venv"
        echo "   Выполните: sudo apt install python3-venv"
        exit 1
    fi
fi

# Создание виртуального окружения
if [ ! -f "venv/bin/activate" ]; then
    echo "📦 Создание виртуального окружения..."
    # Удаляем старую директорию, если она есть, но неполная
    if [ -d "venv" ]; then
        echo "   Удаление неполного виртуального окружения..."
        rm -rf venv
    fi
    python3 -m venv venv
    if [ ! -f "venv/bin/activate" ]; then
        echo "❌ Не удалось создать виртуальное окружение"
        exit 1
    fi
fi

# Активация виртуального окружения
echo "🔌 Активация виртуального окружения..."
source venv/bin/activate

# Обновление pip
echo "⬆️ Обновление pip..."
pip install --upgrade pip

# Установка зависимостей
echo "📥 Установка зависимостей..."
pip install -r requirements.txt

# Проверка config.py
if [ ! -f "config.py" ]; then
    if [ -f "config.py.example" ]; then
        echo "📝 Создание config.py из примера..."
        cp config.py.example config.py
        echo "⚠️  ВАЖНО: Отредактируйте config.py и укажите свои токены!"
        echo "   nano config.py"
    else
        echo "❌ config.py не найден и config.py.example тоже отсутствует!"
        exit 1
    fi
else
    echo "✅ config.py найден"
fi

# Создание директорий
echo "📁 Создание необходимых директорий..."
mkdir -p logs uploads

# Инициализация БД
echo "🗄️  Инициализация базы данных..."
python3 -c "from database import init_db; init_db(); print('✅ База данных инициализирована')"

echo ""
echo "✅ Развертывание завершено!"
echo ""
echo "📋 Следующие шаги:"
echo "   1. Отредактируйте config.py: nano config.py"
echo "   2. Запустите бота: python3 main.py"
echo "   3. Или настройте systemd (см. DEPLOY.md)"
echo ""

