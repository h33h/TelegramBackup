"""Contact extraction and management."""

import os
import csv
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.types import User
from telegram_backup.config import BACKUP_DIR


async def get_contacts(client, phone_number):
    """Extract contacts list from Telegram.
    
    Args:
        client: TelegramClient instance
        phone_number: Phone number for filename
        
    Returns:
        List of contacts
    """
    # Ensure backup directory exists
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    contacts_filename = os.path.join(BACKUP_DIR, f"contacts_{phone_number}.csv")
    
    try:
        result = await client(GetContactsRequest(hash=0))
        contacts = result.contacts
        users = {user.id: user for user in result.users}

        with open(contacts_filename, "w", encoding="utf-8-sig", newline='') as csvfile:
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

        return contacts

    except Exception as e:
        return []

