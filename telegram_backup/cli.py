"""Command-line interface for Telegram Backup."""

from telethon.errors import FloodWaitError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from telegram_backup.telegram_api.client import create_client, start_client, start_client_with_qr, check_session_status
from telegram_backup.telegram_api.contacts import get_contacts
from telegram_backup.telegram_api.entities import discover_entities, save_entities_to_csv, get_flat_entity_list
from telegram_backup.telegram_api.session import close_current_session
from telegram_backup.processor import process_entity


console = Console()


async def run_cli():
    """Run the command-line interface for Telegram Backup."""
    console.print("\n[bold cyan]╔═══════════════════════════════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║[/bold cyan]          [bold white]Telegram Backup - Message Archiver[/bold white]           [bold cyan]║[/bold cyan]")
    console.print("[bold cyan]╚═══════════════════════════════════════════════════════════════╝[/bold cyan]\n")
    
    phone_number = Prompt.ask("[bold cyan]Enter your phone number[/bold cyan]")
    
    # Check session status
    session_exists, session_file, file_size = check_session_status(phone_number)
    
    if session_exists:
        status_panel = Panel(
            f"[green]✓ Session found:[/green] {session_file}\n"
            f"[green]  File size:[/green] {file_size:,} bytes\n"
            f"[green]  Status:[/green] Will use existing authorization",
            title="[bold green]Session Status[/bold green]",
            border_style="green"
        )
    else:
        status_panel = Panel(
            f"[yellow]✗ Session not found:[/yellow] {session_file}\n"
            f"[yellow]  Status:[/yellow] New authorization required",
            title="[bold yellow]Session Status[/bold yellow]",
            border_style="yellow"
        )
    
    console.print(status_panel)
    
    # Only ask for auth method if session doesn't exist
    auth_method = 'qr'  # Default
    if not session_exists:
        console.print()
        auth_panel = Panel(
            "[cyan]1[/cyan] 📱 QR-код (рекомендуется) - быстро и безопасно\n"
            "[cyan]2[/cyan] 📲 SMS-код - традиционный метод",
            title="[bold cyan]Выберите метод авторизации[/bold cyan]",
            border_style="cyan"
        )
        console.print(auth_panel)
        
        auth_choice = Prompt.ask(
            "[bold]Ваш выбор[/bold]",
            choices=["1", "2"],
            default="1"
        )
        auth_method = 'qr' if auth_choice == '1' else 'sms'
    
    # Create and start client
    client = create_client(phone_number)
    
    try:
        # Use existing session or chosen auth method
        if session_exists:
            # Try to use existing session with QR fallback
            me = await start_client_with_qr(client, phone_number)
        elif auth_method == 'qr':
            me = await start_client_with_qr(client, phone_number)
        else:
            me = await start_client(client, phone_number)
        
        # Success panel
        user_info = f"[green]User:[/green] {me.first_name} {me.last_name or ''}\n"
        if me.username:
            user_info += f"[green]Username:[/green] @{me.username}\n"
        user_info += f"[green]Phone:[/green] +{me.phone}\n"
        user_info += f"[green]User ID:[/green] {me.id}"
        
        success_panel = Panel(
            user_info,
            title="[bold green]✓ SUCCESSFUL CONNECTION[/bold green]",
            border_style="green"
        )
        console.print()
        console.print(success_panel)
        
    except FloodWaitError:
        if client.is_connected():
            await client.disconnect()
        return
    except Exception as e:
        console.print(f"\n[bold red]❌ Authorization error:[/bold red] {e}")
        if client.is_connected():
            await client.disconnect()
        return
    
    # Extract contacts
    console.print("\n[cyan]Extracting contacts...[/cyan]")
    await get_contacts(client, phone_number)

    # Discover entities
    console.print("[cyan]Discovering chats and channels...[/cyan]")
    entities = await discover_entities(client)
    await save_entities_to_csv(entities, phone_number)
    
    flat_entities = get_flat_entity_list(entities)
    
    # Display entities in a beautiful table
    display_entities_table(flat_entities)

    while True:
        console.print()
        menu_panel = Panel(
            "[cyan]E[/cyan] - Process specific entity\n"
            "[cyan]T[/cyan] - Process all entities\n"
            "[cyan]X[/cyan] - Close current session\n"
            "[cyan]S[/cyan] - Exit",
            title="[bold cyan]Main Menu[/bold cyan]",
            border_style="blue"
        )
        console.print(menu_panel)
        
        choice = Prompt.ask(
            "[bold]Choose an option[/bold]",
            choices=["e", "t", "x", "s"],
            default="e"
        ).lower()
        
        if choice == 'e':
            selected_index = Prompt.ask(
                "[bold]Enter the number of the entity you want to process[/bold]",
                default="0"
            )
            try:
                selected_index = int(selected_index)
                if selected_index < 0 or selected_index >= len(flat_entities):
                    console.print("[red]Invalid index. Please try again.[/red]")
                    continue
            except ValueError:
                console.print("[red]Invalid input. Please enter a number.[/red]")
                continue
            
            limit_str = Prompt.ask(
                "[bold]How many messages do you want to retrieve?[/bold]",
                default="all"
            )
            limit = int(limit_str) if limit_str.isdigit() else None
            
            download_media = Confirm.ask("[bold]Do you want to download media files?[/bold]", default=True)
            
            await process_entity(client, *flat_entities[selected_index], limit=limit, download_media=download_media)
            
        elif choice == 't':
            limit_str = Prompt.ask(
                "[bold]How many messages do you want to retrieve per entity?[/bold]",
                default="all"
            )
            limit = int(limit_str) if limit_str.isdigit() else None
            
            download_media = Confirm.ask("[bold]Do you want to download media files?[/bold]", default=True)
            
            for category in entities.values():
                for entity in category:
                    await process_entity(client, *entity, limit=limit, download_media=download_media)
                    
        elif choice == 'x':
            session_closed = await close_current_session(client)
            if session_closed:
                console.print("[yellow]Program terminated due to session closure.[/yellow]")
                return
                
        elif choice == 's':
            console.print("\n[cyan]Automatically closing session before exiting...[/cyan]")
            await close_current_session(client)
            break

        if choice != 's':
            continue_processing = Confirm.ask("\n[bold]Do you want to perform another operation?[/bold]", default=True)
            if not continue_processing:
                console.print("\n[cyan]Automatically closing session before exiting...[/cyan]")
                await close_current_session(client)
                break

    console.print("[bold green]Program terminated. Thank you for using the Telegram Backup![/bold green]")
    
    if client.is_connected():
        console.print("[cyan]Closing session before exiting...[/cyan]")
        await close_current_session(client)


def display_entities_table(flat_entities):
    """Display available entities in a formatted table.
    
    Args:
        flat_entities: List of (entity_id, entity_name, entity) tuples
    """
    table = Table(title="[bold cyan]Available Chats and Channels[/bold cyan]", show_lines=True)
    table.add_column("№", justify="center", style="cyan", width=6)
    table.add_column("ID", style="yellow", width=12)
    table.add_column("Name", style="green")
    table.add_column("Type", style="magenta", width=12)
    
    for i, (entity_id, entity_name, entity) in enumerate(flat_entities):
        entity_type = type(entity).__name__.replace("PeerChannel", "Channel").replace("PeerChat", "Chat").replace("PeerUser", "User")
        table.add_row(
            str(i),
            str(entity_id),
            entity_name,
            entity_type
        )
    
    console.print()
    console.print(table)

