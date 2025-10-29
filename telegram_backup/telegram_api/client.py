"""Telegram client initialization and management."""

import os
import qrcode
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telegram_backup.config import API_ID, API_HASH


def check_session_status(phone_number):
    """Check if a session file exists for the given phone number.
    
    Args:
        phone_number: Phone number to check session for
        
    Returns:
        tuple: (exists: bool, file_path: str, file_size: int or None)
    """
    session_file = f"{phone_number}.session"
    exists = os.path.exists(session_file)
    
    if exists:
        file_size = os.path.getsize(session_file)
        return True, session_file, file_size
    
    return False, session_file, None


async def start_client_with_qr(client, phone_number):
    """Start the Telegram client using QR code authentication.
    
    This method displays a QR code in the terminal that can be scanned
    with the Telegram mobile app to log in without SMS codes.
    
    Args:
        client: TelegramClient instance
        phone_number: Phone number (used for session naming only)
        
    Returns:
        User object representing the logged-in user
        
    Raises:
        Exception: Various connection/authentication errors
    """
    session_file = f"{phone_number}.session"
    session_exists = os.path.exists(session_file)
    
    if session_exists:
        print(f"✓ Найден файл сессии: {session_file}")
        print("  Попытка использовать существующую авторизацию...")
    else:
        print(f"✗ Файл сессии не найден: {session_file}")
        print("  Потребуется QR-авторизация...")
    
    # Connect to Telegram
    await client.connect()
    
    # Check if already authorized
    if await client.is_user_authorized():
        print("✓ Сессия валидна! Авторизация не требуется.")
        me = await client.get_me()
        print(f"✓ Вошли как: {me.first_name} {me.last_name or ''} (@{me.username or 'no username'})")
        return me
    
    # Need to authorize with QR code
    print("\n" + "="*70)
    print("QR-КОД АВТОРИЗАЦИЯ")
    print("="*70)
    print("\n📱 Откройте Telegram на телефоне:")
    print("   1. Перейдите в Настройки → Устройства → Подключить устройство")
    print("   2. Отсканируйте QR-код ниже\n")
    
    qr_login = await client.qr_login()
    
    # Generate and display QR code
    def display_qr(url):
        """Display QR code in terminal."""
        qr = qrcode.QRCode(border=2)
        qr.add_data(url)
        qr.make()
        qr.print_ascii(invert=True)
        print(f"\n🔗 Или откройте ссылку: {url}\n")
    
    # Display the initial QR code
    display_qr(qr_login.url)
    
    try:
        # Wait for QR code to be scanned
        print("⏳ Ожидание сканирования QR-кода...")
        print("   (QR-код обновляется автоматически каждые 30 секунд)\n")
        
        # This will wait until QR is scanned or regenerate it if it expires
        me = await qr_login.wait()
        
        print("\n" + "="*70)
        print("✓ УСПЕШНАЯ АВТОРИЗАЦИЯ ЧЕРЕЗ QR-КОД!")
        print("="*70)
        
        return me
        
    except SessionPasswordNeededError:
        print("\n⚠️  Требуется двухфакторная аутентификация (2FA)")
        password = input("Введите ваш пароль 2FA: ")
        await client.sign_in(password=password)
        me = await client.get_me()
        return me


def create_client(phone_number):
    """Create and return a Telegram client.
    
    Uses the same session file for each phone number to avoid re-authentication.
    Telethon handles concurrent access to session files safely through file locking.
    
    Args:
        phone_number: Phone number for authentication
        
    Returns:
        TelegramClient instance with consistent session name
    """
    # Use phone number directly as session name for reusability
    # This allows multiple parallel processes to share the same authenticated session
    session_name = str(phone_number)
    
    client = TelegramClient(session_name, API_ID, API_HASH, receive_updates=False)
    return client


async def start_client(client, phone_number):
    """Start the Telegram client and authenticate.
    
    Intelligently handles session management:
    - Checks if valid session already exists
    - Only prompts for authentication if needed
    - Provides clear feedback about session status
    
    Args:
        client: TelegramClient instance
        phone_number: Phone number for authentication
        
    Returns:
        User object representing the logged-in user
        
    Raises:
        FloodWaitError: When Telegram API requires waiting due to rate limiting
    """
    session_file = f"{phone_number}.session"
    session_exists = os.path.exists(session_file)
    
    if session_exists:
        print(f"✓ Найден файл сессии: {session_file}")
        print("  Попытка использовать существующую авторизацию...")
    else:
        print(f"✗ Файл сессии не найден: {session_file}")
        print("  Потребуется новая авторизация...")
    
    try:
        # Connect to Telegram
        await client.connect()
        
        # Check if already authorized
        if await client.is_user_authorized():
            print("✓ Сессия валидна! Авторизация не требуется.")
            me = await client.get_me()
            print(f"✓ Вошли как: {me.first_name} {me.last_name or ''} (@{me.username or 'no username'})")
            return me
        
        # Need to authorize
        print("⚠ Сессия невалидна или отсутствует.")
        print("  Запрашиваем код подтверждения от Telegram...")
        
        # This will prompt for code if session is invalid
        await client.start(phone=phone_number)
        me = await client.get_me()
        print(f"✓ Успешная авторизация как: {me.first_name} {me.last_name or ''}")
        return me
        
    except FloodWaitError as e:
        wait_time_seconds = e.seconds
        wait_time_hours = wait_time_seconds / 3600
        wait_time_minutes = (wait_time_seconds % 3600) / 60
        
        print(f"\n{'='*70}")
        print(f"⚠️  TELEGRAM API RATE LIMIT ERROR")
        print(f"{'='*70}")
        print(f"\nTelegram требует подождать перед следующей попыткой входа.")
        print(f"\nВремя ожидания:")
        print(f"  • {wait_time_seconds} секунд")
        print(f"  • ~{wait_time_hours:.1f} часов {wait_time_minutes:.0f} минут")
        print(f"\nПричина: слишком много попыток отправки кода подтверждения.")
        print(f"\nРешение:")
        print(f"  1. Подождите указанное время")
        print(f"  2. Попробуйте снова через ~{wait_time_hours:.1f} часов")
        print(f"  3. Не пытайтесь входить повторно до истечения времени ожидания")
        print(f"\n💡 Совет: Если у вас есть валидная сессия, проблема может быть")
        print(f"   в том, что сессия устарела. После ожидания программа создаст")
        print(f"   новую сессию, которая будет работать без повторных запросов кода.")
        print(f"\n{'='*70}\n")
        raise

