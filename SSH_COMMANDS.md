# 🔧 Команды для SSH - Развертывание бота

Пошаговые команды для развертывания бота на VDS через SSH.

## 📋 Шаг 1: Подключение к VDS

```bash
ssh root@ВАШ_IP_АДРЕС
# или если у вас другой пользователь:
ssh username@ВАШ_IP_АДРЕС
```

**Пример:**
```bash
ssh root@123.45.67.89
```

---

## 📦 Шаг 2: Обновление системы и установка зависимостей

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python, pip, venv и Git
sudo apt install python3 python3-pip python3-venv git -y

# Проверка версии Python (должна быть 3.10+)
python3 --version
```

---

## 👤 Шаг 3: Создание пользователя для бота (рекомендуется)

```bash
# Создаем пользователя
sudo useradd -m -s /bin/bash botuser

# Переключаемся на пользователя
sudo su - botuser
```

---

## 📥 Шаг 4: Клонирование репозитория

```bash
# Переходим в домашнюю директорию
cd ~

# Клонируем ваш репозиторий
git clone https://github.com/68sheff/BotLogi.git bot_logi

# Переходим в директорию проекта
cd bot_logi
```

---

## 🚀 Шаг 5: Установка и настройка (автоматически)

```bash
# Делаем скрипт исполняемым
chmod +x deploy.sh

# Запускаем скрипт развертывания
./deploy.sh
```

**Или вручную:**

```bash
# Создаем виртуальное окружение
python3 -m venv venv

# Активируем виртуальное окружение
source venv/bin/activate

# Обновляем pip
pip install --upgrade pip

# Устанавливаем зависимости
pip install -r requirements.txt

# Создаем config.py из примера
cp config.py.example config.py
```

---

## ⚙️ Шаг 6: Настройка конфигурации

```bash
# Редактируем config.py
nano config.py
# или
vim config.py
```

**В файле укажите:**
- `BOT_TOKEN = "ваш_токен_от_BotFather"`
- `ADMIN_IDS = [ваш_telegram_id]`
- `CRYPTOBOT_TOKEN = "ваш_токен"` (опционально)

**Для выхода из nano:** `Ctrl+X`, затем `Y`, затем `Enter`  
**Для выхода из vim:** нажмите `Esc`, затем введите `:wq` и `Enter`

---

## 🗄️ Шаг 7: Инициализация базы данных

```bash
# Убедитесь, что виртуальное окружение активировано
source venv/bin/activate

# Инициализируем БД
python3 -c "from database import init_db; init_db(); print('✅ База данных инициализирована')"
```

---

## 🔄 Шаг 8: Настройка автозапуска через systemd

```bash
# Выйдите из пользователя botuser
exit

# Скопируйте service файл
sudo cp /home/botuser/bot_logi/bot-logi.service /etc/systemd/system/

# Отредактируйте пути (если нужно)
sudo nano /etc/systemd/system/bot-logi.service
```

**Проверьте, что в файле правильные пути:**
- `WorkingDirectory=/home/botuser/bot_logi`
- `ExecStart=/home/botuser/bot_logi/venv/bin/python3 /home/botuser/bot_logi/main.py`

```bash
# Перезагружаем systemd
sudo systemctl daemon-reload

# Включаем автозапуск
sudo systemctl enable bot-logi.service

# Запускаем сервис
sudo systemctl start bot-logi.service

# Проверяем статус
sudo systemctl status bot-logi.service
```

---

## ✅ Шаг 9: Проверка работы

```bash
# Просмотр логов в реальном времени
sudo journalctl -u bot-logi -f

# Или просмотр последних 50 строк
sudo journalctl -u bot-logi -n 50

# Проверка статуса
sudo systemctl status bot-logi
```

**Если все хорошо, вы увидите:**
- `Active: active (running)`
- В логах: `Запуск бота...` и `База данных инициализирована`

---

## 🔧 Полезные команды для управления

```bash
# Запуск бота
sudo systemctl start bot-logi

# Остановка бота
sudo systemctl stop bot-logi

# Перезапуск бота
sudo systemctl restart bot-logi

# Просмотр логов
sudo journalctl -u bot-logi -f

# Просмотр последних 100 строк логов
sudo journalctl -u bot-logi -n 100

# Отключение автозапуска
sudo systemctl disable bot-logi
```

---

## 🔄 Обновление кода

```bash
# Переключаемся на пользователя бота
sudo su - botuser

# Переходим в директорию проекта
cd ~/bot_logi

# Получаем обновления
git pull origin main

# Активируем виртуальное окружение
source venv/bin/activate

# Обновляем зависимости (если requirements.txt изменился)
pip install -r requirements.txt

# Выходим
exit

# Перезапускаем сервис
sudo systemctl restart bot-logi
```

---

## 🐛 Решение проблем

### Бот не запускается

```bash
# Проверьте логи
sudo journalctl -u bot-logi -n 50

# Проверьте права доступа
sudo chown -R botuser:botuser /home/botuser/bot_logi

# Проверьте, что config.py существует и заполнен
sudo su - botuser
cd ~/bot_logi
cat config.py | grep BOT_TOKEN
```

### Ошибка "Module not found"

```bash
sudo su - botuser
cd ~/bot_logi
source venv/bin/activate
pip install -r requirements.txt
```

### Бот падает сразу после запуска

```bash
# Проверьте токен в config.py
sudo su - botuser
cd ~/bot_logi
nano config.py
```

---

## 📝 Полный список команд (копируйте по порядку)

```bash
# 1. Подключение (выполните на своем компьютере)
# ssh root@ВАШ_IP

# 2. Обновление и установка
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git -y

# 3. Создание пользователя
sudo useradd -m -s /bin/bash botuser
sudo su - botuser

# 4. Клонирование
cd ~
git clone https://github.com/68sheff/BotLogi.git bot_logi
cd bot_logi

# 5. Развертывание
chmod +x deploy.sh
./deploy.sh

# 6. Настройка (отредактируйте config.py)
nano config.py

# 7. Инициализация БД
source venv/bin/activate
python3 -c "from database import init_db; init_db(); print('OK')"
exit

# 8. Настройка systemd
sudo cp bot-logi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bot-logi.service
sudo systemctl start bot-logi.service
sudo systemctl status bot-logi.service
```

---

**Готово!** Ваш бот должен работать. Проверьте его, отправив `/start` в Telegram.

