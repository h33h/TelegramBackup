"""Message processing and service message handling."""


async def get_total_message_count(client, entity):
    """Get total message count for an entity.
    
    Args:
        client: TelegramClient instance
        entity: Entity object (channel, group, chat, or user)
        
    Returns:
        int: Total number of messages, or 0 if unavailable
    """
    try:
        # Get just one message to access the total count
        result = await client.get_messages(entity, limit=1)
        
        # The result has a .total attribute with the total message count
        if hasattr(result, 'total'):
            return result.total
        return 0
    except Exception as e:
        print(f"Error getting total message count: {str(e)}")
        return 0


async def get_channel_name_from_message(client, message):
    """Get channel name from a message.
    
    Args:
        client: TelegramClient instance
        message: Message object
        
    Returns:
        Channel name or None
    """
    try:
        if hasattr(message, 'peer_id') and message.peer_id:
            channel_entity = await client.get_entity(message.peer_id)
            if hasattr(channel_entity, 'title'):
                return channel_entity.title
    except Exception as e:
        print(f"Error getting channel name: {str(e)}")
    return None


async def process_service_message(message, client):
    """Process service messages and return formatted text.
    
    Args:
        message: Message object with action attribute
        client: TelegramClient instance
        
    Returns:
        Tuple of (text, is_service_message)
    """
    if not hasattr(message, 'action') or not message.action:
        return None, False
    
    action_dict = message.action.to_dict()
    action_type = action_dict["_"]
    
    if action_type == "MessageActionChatAddUser":
        user_ids = action_dict.get("users", [])
        user_names = []
        for user_id in user_ids:
            try:
                user = await client.get_entity(user_id)
                if hasattr(user, "first_name") and user.first_name:
                    name = user.first_name
                    if hasattr(user, "last_name") and user.last_name:
                        name += f" {user.last_name}"
                else:
                    name = f"User {user_id}"
                user_names.append(name)
            except Exception as e:
                print(f"Error getting user {user_id}: {str(e)}")
                user_names.append(f"User {user_id}")
        text = f"<service>{', '.join(filter(None, user_names))} joined the group</service>"
        return text, True
        
    elif action_type == "MessageActionChatDeleteUser":
        user_id = action_dict.get("user_id")
        try:
            user = await client.get_entity(user_id)
            if hasattr(user, "first_name") and user.first_name:
                name = user.first_name
                if hasattr(user, "last_name") and user.last_name:
                    name += f" {user.last_name}"
            else:
                name = f"User {user_id}"
        except Exception as e:
            print(f"Error getting user {user_id}: {str(e)}")
            name = f"User {user_id}"
        text = f"<service>{name} left the group</service>"
        return text, True
        
    elif action_type == "MessageActionChatJoinedByLink":
        try:
            if message.sender:
                user_name = message.sender.first_name
                if hasattr(message.sender, "last_name") and message.sender.last_name:
                    user_name += f" {message.sender.last_name}"
            else:
                user_name = "Someone"
        except:
            user_name = "Someone"
        text = f"<service>{user_name} joined the group via invite link</service>"
        return text, True
        
    elif action_type == "MessageActionChannelCreate":
        title = action_dict.get("title", "this channel")
        text = f"<service>Channel {title} created</service>"
        return text, True
        
    elif action_type == "MessageActionChatCreate":
        title = action_dict.get("title", "this group")
        text = f"<service>Group {title} created</service>"
        return text, True
        
    elif action_type == "MessageActionGroupCall":
        if action_dict.get("duration"):
            text = f"<service>Group call ended</service>"
        else:
            text = f"<service>Group call started</service>"
        return text, True
        
    elif action_type == "MessageActionChatEditTitle":
        title = action_dict.get("title", "")
        text = f"<service>Group name changed to: {title}</service>"
        return text, True
    else:
        text = f"<service>Service message: {action_type}</service>"
        return text, True

