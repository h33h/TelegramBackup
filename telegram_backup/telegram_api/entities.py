"""Entity (chats/channels/users) discovery and listing."""

import os
import csv
from telethon.tl.types import User, Channel, Chat, ChannelForbidden
from telegram_backup.config import BACKUP_DIR


async def discover_entities(client):
    """Discover and categorize all entities (chats, channels, groups).
    
    Args:
        client: TelegramClient instance
        
    Returns:
        Dictionary with categorized entities
    """
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
    
    return entities


async def save_entities_to_csv(entities, phone_number):
    """Save discovered entities to CSV file with consistent ordering.
    
    Args:
        entities: Dictionary of categorized entities
        phone_number: Phone number for filename
        
    Returns:
        Path to the created CSV file
    """
    # Ensure backup directory exists
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    entities_filename = os.path.join(BACKUP_DIR, f"entities_{phone_number}.csv")
    
    with open(entities_filename, "w", encoding="utf-8-sig", newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        
        csv_writer.writerow(["Index", "Type", "Name", "ID"])
        
        index = 0
        # Use consistent category order
        category_order = ["Channels", "Supergroups", "Groups", "Users", "Unknown"]
        
        for category in category_order:
            if category in entities:
                # Sort entities within category by name
                sorted_entities = sorted(entities[category], key=lambda x: x[1].lower())
                for id, name, _ in sorted_entities:
                    csv_writer.writerow([index, category, name, id])
                    index += 1

    return entities_filename


def get_flat_entity_list(entities):
    """Flatten entities dictionary into a single list with consistent ordering.
    
    Entities are sorted by:
    1. Category (Channels, Supergroups, Groups, Users, Unknown)
    2. Name (alphabetically within each category)
    
    Args:
        entities: Dictionary of categorized entities
        
    Returns:
        Flat list of all entities in consistent order
    """
    # Define category order for consistent display
    category_order = ["Channels", "Supergroups", "Groups", "Users", "Unknown"]
    
    flat_list = []
    for category in category_order:
        if category in entities:
            # Sort entities within category by name (case-insensitive)
            sorted_entities = sorted(entities[category], key=lambda x: x[1].lower())
            flat_list.extend(sorted_entities)
    
    return flat_list

