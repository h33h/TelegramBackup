# TelegramBackup - Advanced Backup Solution for Telegram Chats

TelegramBackup is a sophisticated tool designed for extracting, organizing, and archiving messages from your Telegram chats, channels, and groups. It offers a unique approach by not only storing message content but also preserving media, links, buttons, and metadata in an organized format. Whether you're looking to back up your personal chats, archive large channels, or extract important data from groups, **TelegramBackup** ensures a seamless and efficient process.

## Key Features

- **Comprehensive Backup**: TelegramBackup archives all forms of communication, including text messages, media files, forwarded messages, and message buttons.
- **Contact Extraction**: Capability to extract and save complete contact lists in CSV format.
- **Session Management**: Enhanced security with automatic session closure and service message cleanup.
- **User-Friendly Interaction**: Allows users to choose between backing up specific entities (users, channels, groups) or all available dialogs at once.
- **Complete Media Download**: Automatically downloads all file types associated with messages, including photos, videos, documents, voice messages, and any other attachments.
- **HTML Output**: Generates clean, readable HTML files for easy navigation and visualization of backed-up messages.
- **SQL Database Storage**: All messages, media, and related data are stored in a local SQLite database, providing a structured and easily accessible archive.
- **Multiple Entity Support**: Supports users, channels, supergroups, and regular groups, ensuring that all your important data is captured.

## Installation

### Prerequisites
- Python 3.6 or higher
- Internet connection
- Telegram account

### Setup Instructions

1. **Clone the repository**:
    ```bash
    git clone https://github.com/N4rr34n6/TelegramBackup.git
    ```

2. **Navigate to the project directory**:
    ```bash
    cd TelegramBackup
    ```

3. **Install the required dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    
    If the requirements.txt file is missing, install these packages:
    ```bash
    pip install telethon jinja2 beautifulsoup4
    ```

## Getting Telegram API Credentials

Before using TelegramBackup, you need to obtain your own Telegram API credentials:

1. **Visit the Telegram API Development Tools**:
   - Go to https://my.telegram.org
   - Log in with your Telegram account

2. **Create a New Application**:
   - Click on "API Development tools"
   - Fill out the form with your application details (you can use "TelegramBackup" for app title and short name)
   - Click "Create application"

3. **Get Your API Credentials**:
   - After creating the application, you'll see your **api_id** (a number) and **api_hash** (a string)
   - Keep these values secure - they're associated with your Telegram account

4. **Configure TelegramBackup**:
   - Open the `telegram_backup.py` file in a text editor
   - Locate these lines near the beginning of the file:
     ```python
     api_id = ********
     api_hash = ********************************
     ```
   - Replace them with your actual credentials:
     ```python
     api_id = 12345678  # Replace with your own api_id (numbers only, no quotes)
     api_hash = "abcdef1234567890abcdef1234567890"  # Replace with your own api_hash (in quotes)
     ```
   - Save the file

> **IMPORTANT**: The `api_id` must be an integer without quotes, and the `api_hash` must be a string with quotes.

## Usage

1. **Run the script**:
    ```bash
    python telegram_backup.py
    ```

2. **First-Time Login**:
   - Enter your Telegram phone number when prompted (include country code, e.g., +12345678900)
   - You'll receive a code on your Telegram app - enter this code when prompted
   - If you have two-factor authentication enabled, you'll need to enter your password

3. **Managing Contacts and Entities**:
   - The script will automatically extract your contacts and save them to a CSV file
   - It will generate a list of all available entities (users, channels, groups) and save it to a CSV file
   - Review the entity list in your console to identify which ones you want to backup

4. **Backup Options**:
   Choose from the menu options:
   - **[E] Process a specific entity**: Backup a single chat, channel, or group
   - **[T] Process all entities**: Backup everything
   - **[D] Delete Telegram service messages**: Clean up service messages
   - **[X] Close current session**: End the current session securely
   - **[S] Exit**: Exit the program

5. **When processing entities**:
   - You can specify how many messages to retrieve (leave blank for all)
   - Choose whether to download all media files (Y/N)
   - For large chats, consider processing in batches to avoid timeouts

6. **Accessing Your Backup**:
   - Messages are stored in an SQLite database (`.db` file)
   - An HTML file is generated for easy browsing of messages
   - Media files are saved in the `media/[entity_id]/` directory

## Handling Large Backups

If you're backing up chats with hundreds of thousands of messages:

1. **Start with a smaller batch**: First try backing up a limited number (e.g., 1000) to test
2. **Ensure adequate storage**: Media files can consume significant disk space
3. **Run in a stable environment**: Avoid using USB drives or removable storage for the backup process
4. **Be patient**: Large backups can take considerable time depending on your internet connection

## Troubleshooting

### Common Issues and Solutions

1. **Syntax Error with API Credentials**:
   - Ensure `api_id` is an integer without quotes
   - Ensure `api_hash` is a string with quotes
   - Double-check that you saved the file after making changes

2. **Connection Errors**:
   - Verify your internet connection
   - Check if Telegram is accessible in your region
   - Some networks may block Telegram's API servers

3. **Permission Errors**:
   - Run the script from a location where you have read/write permissions
   - Avoid running from USB drives or network shares if possible

4. **Missing Dependencies**:
   - If you get import errors, verify that all required packages are installed
   - Try running `pip install -r requirements.txt` again

5. **Session File Issues**:
   - If you get errors related to the `.session` file, delete it and start a new session
   - These files are stored in the same directory as the script

### Advanced Tips

- **Customizing HTML Output**: You can modify the `template.html` file to change how the exported HTML looks
- **Working with the Database**: The SQLite database can be opened with tools like DB Browser for SQLite if you want to perform custom queries
- **Automating Backups**: Consider setting up a scheduled task to run the script periodically

## Technical Details

- **Message Processing**: TelegramBackup iterates through all messages of a selected entity, extracts their content, and stores them in an SQLite database. It also handles media download, message forwarding, and buttons associated with messages.
- **Flood Wait Handling**: The script implements flood control management by waiting for a specified time in case the Telegram API returns a flood error.
- **HTML Rendering**: Using Jinja2, TelegramBackup dynamically generates HTML files that can be easily viewed in any browser, preserving the structure of the original messages, including any media and buttons.

## Ethical Use and Legal Considerations

**TelegramBackup** is intended for personal use, enabling users to backup their own Telegram data. The misuse of this tool, such as unauthorized data extraction from accounts or channels where you do not have permission, is strictly prohibited. Ensure that all data you process with this tool complies with Telegram's terms of service and local data protection laws.

## License

This script is provided under the GNU Affero General Public License v3.0. You can find the full license text in the [LICENSE](LICENSE) file.

---

With TelegramBackup, you have a comprehensive, customizable, and reliable solution for preserving your Telegram communications. Whether for personal archiving or professional data analysis, this tool offers unmatched flexibility and functionality.
