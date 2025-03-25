import os
import re
import time
import sqlite3
import asyncio
import warnings
import csv
from telethon import TelegramClient, events, errors
from telethon.tl.types import User, Channel, Chat, ChannelForbidden
from jinja2 import Environment, FileSystemLoader
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from telethon.tl.functions.contacts import GetContactsRequest

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

api_id = ******** 
api_hash = ********************************

def get_url_from_forwarded(forwarded):
    if forwarded is None:
        return None
    match = re.search(r"channel_id=(\d+).*channel_post=(\d+)", forwarded)
    if match:
        channel_id, channel_post = match.groups()
        return f"https://t.me/c/{channel_id}/{channel_post}"
    return None

def sanitize_filename(filename):
    return re.sub(r'[^\w\-_\. ]', '_', filename)

async def get_contacts(client, phone_number):
    print("Extracting contacts list...")
    
    contacts_filename = f"contacts_{phone_number}.csv"
    
    try:
        result = await client(GetContactsRequest(hash=0))
        contacts = result.contacts
        users = {user.id: user for user in result.users}

        with open(contacts_filename, "w", encoding="utf-8", newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            
            csv_writer.writerow(["Index", "Name", "Phone", "Username", "ID"])
            
            for i, contact in enumerate(contacts):
                user = users.get(contact.user_id, None)
                
                if isinstance(user, User):
                    name_parts = []
                    if user.first_name:
                        name_parts.append(user.first_name)
                    if user.last_name:
                        name_parts.append(user.last_name)
                    name = " ".join(name_parts) if name_parts else "No name"
                    
                    phone = user.phone or "Private"
                    username = f"@{user.username}" if user.username else "No username"
                    user_id = user.id
                else:
                    name = "Deleted user"
                    phone = "Not available"
                    username = "Not available"
                    user_id = contact.user_id

                csv_writer.writerow([i, name, phone, username, user_id])
                
                contact_info = (
                    f"{i}: {name} | "
                    f"Phone: {phone} | "
                    f"Username: {username} | "
                    f"ID: {user_id}"
                )
                print(contact_info)

        print(f"\n{len(contacts)} contacts extracted. List saved in '{contacts_filename}'")
        return contacts

    except Exception as e:
        print(f"Error getting contacts: {str(e)}")
        return []

async def close_current_session(client):
    print("Closing current session...")
    try:
        await asyncio.sleep(5)
        # First try to delete service messages
        await delete_telegram_service_messages(client)
        
        # Then log out
        await client.log_out()
        print("Current session closed successfully.")
        return True
    except Exception as e:
        print(f"Error closing session: {str(e)}")
        return False

async def delete_telegram_service_messages(client):
    print("Attempting to delete recent Telegram service messages...")
    try:
        # Get Telegram service chat (usually the first dialog with Telegram's official account)
        service_entity = None
        async for dialog in client.iter_dialogs():
            if dialog.name == "Telegram" or (hasattr(dialog.entity, 'username') and dialog.entity.username == "telegram"):
                service_entity = dialog.entity
                break
        
        if not service_entity:
            print("Could not find Telegram service chat.")
            return
        
        # Get recent messages (last 15) and delete login code/notification messages
        count = 0
        async for message in client.iter_messages(service_entity, limit=15):
            # Check if message has text content
            if not message.text:
                continue
                
            # Look for specific patterns in service messages
            message_text = message.text.lower()
            if any(keyword in message_text for keyword in 
                  ["login code", "código de inicio", "new login", "nuevo inicio", 
                   "new device", "nuevo dispositivo", "detected a login", 
                   "we detected", "hemos detectado", "active sessions", "terminate that session"]):
                try:
                    await client.delete_messages(service_entity, message.id)
                    count += 1
                    print(f"Deleted service message ID: {message.id}")
                except Exception as e:
                    print(f"Could not delete message ID {message.id}: {str(e)}")
        
        print(f"Deleted {count} service messages.")
    except Exception as e:
        print(f"Error deleting service messages: {str(e)}")
        
    # Small delay to ensure deletion processes complete
    await asyncio.sleep(1)

async def main():
    phone_number = input("Enter your phone number: ")
    client = TelegramClient(phone_number, api_id, api_hash)
    
    await client.start(phone=phone_number)
    me = await client.get_me()
    print(f"Session started as {me.first_name}")
    
    # Delete service messages right after login
    await delete_telegram_service_messages(client)
    
    await get_contacts(client, phone_number)

    entities = {
        "Users": [],
        "Channels": [],
        "Supergroups": [],
        "Groups": [],
        "Unknown": []
    }

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if isinstance(entity, User):
            entity_type = "Users"
            name = entity.first_name
        elif isinstance(entity, Channel):
            entity_type = "Channels" if entity.broadcast else "Supergroups"
            name = entity.title
        elif isinstance(entity, Chat):
            entity_type = "Groups"
            name = entity.title
        elif isinstance(entity, ChannelForbidden):
            entity_type = "Unknown"
            name = f"ID: {entity.id}"
        else:
            entity_type = "Unknown"
            name = f"ID: {entity.id}"
        
        entities[entity_type].append((entity.id, name, entity))

    entities_filename = f"entities_{phone_number}.csv"
    
    with open(entities_filename, "w", encoding="utf-8", newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        
        csv_writer.writerow(["Index", "Type", "Name", "ID"])
        
        index = 0
        for category, entity_list in entities.items():
            print(f"\n{category}:")
            
            for id, name, _ in entity_list:
                csv_writer.writerow([index, category, name, id])
                
                line = f"{index}: {name} (ID: {id})"
                if category == "Unknown":
                    print(f"\033[1m{line}\033[0m")  
                else:
                    print(line)
                index += 1

    print(f"\nThe entity list has been saved in '{entities_filename}'")

    while True:
        choice = input("\nWhat would you like to do?\n[E] Process specific entity\n[T] Process all entities\n[D] Delete Telegram service messages\n[X] Close current session\n[S] Exit\nOption: ").lower()
        
        if choice == 'e':
            selected_index = int(input("Enter the number corresponding to the entity you want to process: "))
            flat_entities = [entity for category in entities.values() for entity in category]
            limit = input("How many messages do you want to retrieve? (Press Enter for all): ")
            limit = int(limit) if limit.isdigit() else None
            download_media = input("Do you want to download media files? (Y/N): ").lower() == 'y'
            await process_entity(client, *flat_entities[selected_index], limit=limit, download_media=download_media)
        elif choice == 't':
            limit = input("How many messages do you want to retrieve per entity? (Press Enter for all): ")
            limit = int(limit) if limit.isdigit() else None
            download_media = input("Do you want to download media files? (Y/N): ").lower() == 'y'
            
            for category in entities.values():
                for entity in category:
                    await process_entity(client, *entity, limit=limit, download_media=download_media)
        elif choice == 'd':
            await delete_telegram_service_messages(client)
        elif choice == 'x':
            session_closed = await close_current_session(client)
            if session_closed:
                print("Program terminated due to session closure.")
                return
        elif choice == 's':
            print("\nAutomatically closing session before exiting...")
            await close_current_session(client)
            break

        if choice != 's':
            continue_processing = input("\nDo you want to perform another operation? (Y/N): ").lower()
            if continue_processing != 'y':
                print("\nAutomatically closing session before exiting...")
                await close_current_session(client)
                break

    print("Program terminated. Thank you for using the Telegram extractor!")
    
    if client.is_connected():
        print("Closing session before exiting...")
        await close_current_session(client)

async def process_entity(client, entity_id, entity_name, entity, limit=None, download_media=False):
    print(f"\nProcessing: {entity_name} (ID: {entity_id})")
    
    if isinstance(entity, ChannelForbidden):
        print(f"The entity {entity_name} (ID: {entity_id}) is not accessible. It may have been deleted or you lack permission to access it.")
        return

    sanitized_name = sanitize_filename(f"{entity_id}_{entity_name}")
    db_name = f"{sanitized_name}.db"
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY,
        date TEXT,
        text TEXT,
        media_type TEXT,
        media_file TEXT,
        forwarded TEXT,
        from_id TEXT,
        views INTEGER
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS buttons (
        message_id INTEGER,
        row INTEGER,
        column INTEGER,
        text TEXT,
        data TEXT,
        url TEXT,
        UNIQUE(message_id, row, column)
    )""")

    try:
        async for message in client.iter_messages(entity, limit=limit):
            message_dict = message.to_dict()
            id = message_dict["id"]
            date = message_dict["date"].isoformat()
            text = message_dict.get("message", None)
            media_type = None
            media_file = None
            
            if message.media:
                media_type = message_dict["media"]["_"]
                if download_media:
                    try:
                        media_file = await message.download_media(file=f"media/{entity_id}/")
                    except Exception as e:
                        print(f"Error downloading media from message {id}: {e}")
            
            forwarded = str(message.fwd_from) if message.fwd_from else None
            from_id = str(message.from_id)
            views = message.views
            
            cursor.execute("INSERT OR REPLACE INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (id, date, text, media_type, media_file, forwarded, from_id, views))
            
            if message.buttons:
                for i, row in enumerate(message.buttons):
                    for j, button in enumerate(row):
                        cursor.execute("INSERT OR IGNORE INTO buttons VALUES (?, ?, ?, ?, ?, ?)",
                                       (id, i, j, button.text, button.data, button.url))
            
            if text:
                soup = BeautifulSoup(text, "html.parser")
                for link in soup.find_all('a'):
                    cursor.execute("INSERT OR IGNORE INTO buttons VALUES (?, ?, ?, ?, ?, ?)",
                                   (id, 0, 0, link.text, None, link['href']))
            
            conn.commit()
            
            print(f"Message {id} processed", end='\r')
        
        print(f"\nAll messages from {entity_name} have been processed.")
    except errors.FloodWaitError as e:
        print(f'A flood error occurred. Waiting {e.seconds} seconds before continuing.')
        await asyncio.sleep(e.seconds)
    except errors.ChannelPrivateError:
        print(f"Cannot access entity {entity_name} (ID: {entity_id}). It may be private or you may have been banned.")
    finally:
        conn.close()
    
    generate_html(db_name, sanitized_name)

def generate_html(db_name, chat_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT m.*, GROUP_CONCAT(b.text || ',' || b.url, '|') as buttons FROM messages m LEFT JOIN buttons b ON m.id = b.message_id GROUP BY m.id ORDER BY m.date DESC")
    messages = cursor.fetchall()
    conn.close()

    env = Environment(loader=FileSystemLoader('./'))
    template = env.get_template('template.html')
    
    output = template.render(
        chat_name=chat_name,
        messages=messages,
        os=os,
        get_url_from_forwarded=get_url_from_forwarded
    )
    
    with open(f"{chat_name}.html", "w", encoding='utf-8') as f:
        f.write(output)
    
    print(f"HTML file generated: {chat_name}.html")

if __name__ == "__main__":
    asyncio.run(main())
