import os
import re
import time
import sqlite3
import asyncio
import warnings
from telethon import TelegramClient, events, errors
from telethon.tl.types import User, Channel, Chat, ChannelForbidden
from jinja2 import Environment, FileSystemLoader
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

# Suppress BeautifulSoup warnings
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

api_id = 12345678 
api_hash = "5b2e9d8079f14b3b987b6f5cfeb6d92a"

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

async def main():
    phone_number = input("Enter your phone number: ")
    client = TelegramClient(phone_number, api_id, api_hash)
    
    await client.start(phone=phone_number)
    me = await client.get_me()
    print(f"Session started as {me.first_name}")

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

    # Display and save the entity list
    with open("entities_list.txt", "w", encoding="utf-8") as f:
        index = 0
        for category, entity_list in entities.items():
            print(f"\n{category}:")
            f.write(f"\n{category}:\n")
            for id, name, _ in entity_list:
                line = f"{index}: {name} (ID: {id})"
                if category == "Unknown":
                    print(f"\033[1m{line}\033[0m")  # Bold for unknown entities
                else:
                    print(line)
                f.write(line + "\n")
                index += 1

    print("\nThe entity list has been saved in 'entities_list.txt'")

    while True:
        choice = input("\nDo you want to process a specific entity (E) or all entities (T)? ").lower()
        
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
        else:
            print("Invalid option. Please choose 'E' or 'T'.")
            continue

        continue_processing = input("\nDo you want to process another entity? (Y/N): ").lower()
        if continue_processing != 'y':
            break

    print("Program terminated. Thank you for using the Telegram scraper!")

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
