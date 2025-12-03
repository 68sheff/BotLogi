# ⚡ Быстрый старт - Развертывание на VDS

## 🎯 Краткая инструкция

### 1. Подготовка проекта для GitHub

```bash
# Убедитесь, что config.py не содержит реальных токенов
# Если содержит - удалите их перед коммитом

# Инициализируйте git (если еще не сделано)
git init

# Добавьте все файлы
git add .

# Сделайте коммит
git commit -m "Initial commit"

# Создайте репозиторий на GitHub и добавьте remote
git remote add origin https://github.com/ВАШ_USERNAME/ВАШ_РЕПОЗИТОРИЙ.git
git branch -M main
git push -u origin main
```

### 2. Подключение к VDS

```bash
ssh root@ВАШ_IP_АДРЕС
# или
ssh username@ВАШ_IP_АДРЕС
```

### 3. Установка на VDS

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python и Git
sudo apt install python3 python3-pip python3-venv git -y

# Создание пользователя (рекомендуется)
sudo useradd -m -s /bin/bash botuser
sudo su - botuser

# Клонирование репозитория
cd ~
git clone https://github.com/ВАШ_USERNAME/ВАШ_РЕПОЗИТОРИЙ.git bot_logi
cd bot_logi

# Запуск скрипта развертывания
chmod +x deploy.sh
./deploy.sh

# Настройка config.py
nano config.py
# Укажите свои токены:
# - BOT_TOKEN
# - ADMIN_IDS
# - CRYPTOBOT_TOKEN (опционально)
```

### 4. Настройка автозапуска

```bash
# Выйдите из пользователя botuser
exit

# Скопируйте service файл
sudo cp bot-logi.service /etc/systemd/system/

# Отредактируйте пути в service файле (если нужно)
sudo nano /etc/systemd/system/bot-logi.service
# Убедитесь, что пути правильные:
# WorkingDirectory=/home/botuser/bot_logi
# ExecStart=/home/botuser/bot_logi/venv/bin/python3 /home/botuser/bot_logi/main.py

# Активируйте сервис
sudo systemctl daemon-reload
sudo systemctl enable bot-logi.service
sudo systemctl start bot-logi.service

# Проверьте статус
sudo systemctl status bot-logi.service
```

### 5. Проверка работы

```bash
# Просмотр логов
sudo journalctl -u bot-logi -f

# Или логи из файла
tail -f /home/botuser/bot_logi/logs/bot.log
```

## 🔄 Обновление кода

```bash
sudo su - botuser
cd ~/bot_logi
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
exit
sudo systemctl restart bot-logi
```

## 📞 Полезные команды

```bash
# Управление сервисом
sudo systemctl start bot-logi    # Запуск
sudo systemctl stop bot-logi     # Остановка
sudo systemctl restart bot-logi  # Перезапуск
sudo systemctl status bot-logi    # Статус

# Просмотр логов
sudo journalctl -u bot-logi -f           # В реальном времени
sudo journalctl -u bot-logi -n 100       # Последние 100 строк
```

## ⚠️ Важно

1. **Не загружайте config.py с реальными токенами в GitHub!**
2. Используйте `config.py.example` как шаблон
3. Регулярно делайте резервные копии базы данных
4. Проверяйте логи при проблемах

---

📖 **Подробная инструкция:** [DEPLOY.md](DEPLOY.md)

