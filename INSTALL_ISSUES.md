# Решение проблемы установки на Python 3.14

## Проблема

При установке aiogram на Python 3.14 возникает ошибка компиляции `pydantic-core`, так как для этой версии Python нет предкомпилированных пакетов.

## Решения

### Вариант 1: Использовать Python 3.11 или 3.12 (РЕКОМЕНДУЕТСЯ)

1. Скачайте и установите Python 3.11 или 3.12 с [python.org](https://www.python.org/downloads/)
2. Создайте виртуальное окружение:
   ```bash
   python3.11 -m venv venv
   # или
   python3.12 -m venv venv
   ```
3. Активируйте окружение:
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```
4. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

### Вариант 2: Установить Rust (для компиляции)

1. Установите Rust с [rustup.rs](https://rustup.rs/)
2. Перезапустите терминал
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

### Вариант 3: Использовать Docker

Создайте Dockerfile с Python 3.12 и запустите бота в контейнере.

## Текущий статус

- Python 3.14: Требуется компиляция Rust
- Python 3.11/3.12: Работает из коробки ✅

