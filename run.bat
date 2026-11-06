```bat
@echo off
echo ===================================================
echo   Запуск симулятора КРК
echo ===================================================
echo.

:: Проверка, установлен ли Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Python не установлен или не добавлен в PATH!
    echo Пожалуйста, установите Python
    pause
    exit /b
)

:: Создание виртуального окружения, если его нет
if not exist ".venv" (
    echo [1/3] Создание виртуального окружения...
    python -m venv .venv
)

:: Активация и установка зависимостей
echo [2/3] Установка зависимостей (это может занять пару минут)...
call .venv\Scripts\activate
pip install -r requirements-dev.txt

:: Запуск приложения
echo [3/3] Запуск веб-интерфейса...
streamlit run app.py

pause