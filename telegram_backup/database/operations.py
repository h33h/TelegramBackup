"""Database operations for saving and querying messages."""

import json
from bs4 import BeautifulSoup
from telegram_backup.utils import extract_user_id, get_emoji_string


async def get_web_preview_data(message):
    """Extract web preview data from a message."""
    from telethon.tl.types import MessageMediaWebPage
    
    preview_data = {
        'title': None,
        'description': None,
        'url': None,
        'site_name': None,
        'image_url': None
    }
    
    if hasattr(message, 'web_preview') and message.web_preview:
        if hasattr(message.web_preview, 'title'):
            preview_data['title'] = message.web_preview.title
        if hasattr(message.web_preview, 'description'):
            preview_data['description'] = message.web_preview.description
        if hasattr(message.web_preview, 'url'):
            preview_data['url'] = message.web_preview.url
        if hasattr(message.web_preview, 'site_name'):
            preview_data['site_name'] = message.web_preview.site_name
        if hasattr(message.web_preview, 'image'):
            preview_data['image_url'] = message.web_preview.image
    
    elif isinstance(message.media, MessageMediaWebPage) and message.media.webpage:
        webpage = message.media.webpage
        if hasattr(webpage, 'title'):
            preview_data['title'] = webpage.title
        if hasattr(webpage, 'description'):
            preview_data['description'] = webpage.description
        if hasattr(webpage, 'url'):
            preview_data['url'] = webpage.url
        if hasattr(webpage, 'site_name'):
            preview_data['site_name'] = webpage.site_name
        if hasattr(webpage, 'photo'):
            preview_data['image_url'] = "web_preview_photo"
    
    return json.dumps(preview_data) if any(preview_data.values()) else None


async def save_message_to_db(cursor, entity_id, message, extraction_time, media_file_id=None,
                             file_id=None, file_unique_id=None, file_size=None):
    """Save a complete message to the database with all its data.
    
    Args:
        cursor: Database cursor
        entity_id: Entity (chat/channel) ID
        message: Telethon message object
        extraction_time: ISO format timestamp
        media_file_id: ID from media_files table (if media exists)
        file_id: Telegram file ID
        file_unique_id: Telegram unique file ID
        file_size: File size in bytes
    """
    message_dict = message.to_dict()
    id = message_dict["id"]
    date = message_dict["date"].isoformat()
    text = message_dict.get("message", None)
    media_type = None
    is_service_message = False
    is_voice_message = False
    is_pinned = message.pinned
    
    # Handle service messages
    if hasattr(message, 'action') and message.action:
        action_dict = message.action.to_dict()
        action_type = action_dict["_"]
        is_service_message = True
        # Service message processing would go here if needed
    
    # Handle media type and voice messages
    if message.media:
        media_type = message_dict["media"]["_"]
        if media_type == "MessageMediaDocument":
            if hasattr(message.media, "document") and hasattr(message.media.document, "attributes"):
                for attr in message.media.document.attributes:
                    if hasattr(attr, "_") and attr._ == "DocumentAttributeAudio":
                        if hasattr(attr, "voice") and attr.voice:
                            is_voice_message = True
    
    web_preview = await get_web_preview_data(message)
    forwarded = str(message.fwd_from) if message.fwd_from else None
    from_id = str(message.from_id)
    user_id = extract_user_id(from_id)
    views = message.views
    
    # Get sender name
    sender_name = None
    if message.sender:
        if hasattr(message.sender, 'first_name') and message.sender.first_name:
            sender_name = message.sender.first_name
            if hasattr(message.sender, 'last_name') and message.sender.last_name:
                sender_name += f" {message.sender.last_name}"
        elif hasattr(message.sender, 'title'):
            sender_name = message.sender.title
    
    reply_to_msg_id = message.reply_to_msg_id if message.reply_to_msg_id else None
    quote_text = None
    if hasattr(message, 'reply_to') and message.reply_to:
        if hasattr(message.reply_to, 'quote_text'):
            quote_text = message.reply_to.quote_text
    
    # Handle reactions
    reactions_json = None
    if hasattr(message, 'reactions') and message.reactions:
        reactions_list = []
        for reaction in message.reactions.results:
            emoji = get_emoji_string(reaction.reaction)
            count = reaction.count
            reactions_list.append({"emoji": emoji, "count": count})
            cursor.execute("INSERT OR IGNORE INTO reactions VALUES (?, ?, ?, ?)",
                          (int(id), int(entity_id), str(emoji), int(count)))
        reactions_json = json.dumps(reactions_list)
    
    # Insert message
    cursor.execute("""
    INSERT OR IGNORE INTO messages 
    (id, entity_id, date, text, media_type, forwarded, from_id, views, 
    sender_name, reply_to_msg_id, reactions, web_preview, extraction_time, is_service_message,
    is_voice_message, is_pinned, user_id, file_id, file_unique_id, file_size, media_file_id) 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (int(id), int(entity_id), date, text, media_type, forwarded, from_id, 
         views if views is not None else 0, sender_name, 
         int(reply_to_msg_id) if reply_to_msg_id is not None else None, 
         reactions_json, web_preview, extraction_time, is_service_message, is_voice_message, is_pinned, user_id,
         file_id, file_unique_id, file_size, media_file_id))
    
    # Update media_file_id if message already existed and we have a media file
    # INSERT OR IGNORE doesn't update existing rows, so we need explicit UPDATE
    if media_file_id is not None:
        cursor.execute("""
        UPDATE messages 
        SET media_file_id = ?,
            file_id = COALESCE(?, file_id),
            file_unique_id = COALESCE(?, file_unique_id),
            file_size = COALESCE(?, file_size)
        WHERE id = ? AND entity_id = ?
        """, (media_file_id, file_id, file_unique_id, file_size, int(id), int(entity_id)))
    
    # Handle replies
    if reply_to_msg_id:
        cursor.execute("INSERT OR IGNORE INTO replies VALUES (?, ?, ?, ?)",
                      (int(id), int(entity_id), int(reply_to_msg_id), quote_text))
    
    # Handle buttons
    if message.buttons:
        for i, row in enumerate(message.buttons):
            for j, button in enumerate(row):
                cursor.execute("INSERT OR IGNORE INTO buttons VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (int(id), int(entity_id), int(i), int(j), str(button.text), 
                                str(button.data) if button.data else None, 
                                str(button.url) if button.url else None))
    
    # Extract links from text
    if text and not is_service_message:
        soup = BeautifulSoup(text, "html.parser")
        for link in soup.find_all('a'):
            cursor.execute("INSERT OR IGNORE INTO buttons VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (int(id), int(entity_id), 0, 0, str(link.text), None, str(link.get('href'))))


def get_last_message_id(cursor, entity_id):
    """Get the ID of the last message for an entity."""
    cursor.execute("SELECT MAX(id) FROM messages WHERE entity_id = ?", (entity_id,))
    result = cursor.fetchone()
    return result[0] if result[0] is not None else 0

