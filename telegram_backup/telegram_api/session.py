"""Session management and cleanup."""

import asyncio


async def close_current_session(client):
    """Close and logout from current Telegram session.
    
    Args:
        client: TelegramClient instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    print("Closing current session...")
    try:
        await asyncio.sleep(5)
        
        await client.log_out()
        print("Current session closed successfully.")
        return True
    except Exception as e:
        print(f"Error closing session: {str(e)}")
        try:
            await client.disconnect()
            print("Disconnected but could not log out completely.")
        except:
            pass
        return False

