# TelegramBackup - Advanced Backup Solution for Telegram Chats

TelegramBackup is a sophisticated tool designed for extracting, organizing, and archiving messages from your Telegram chats, channels, and groups. It offers a unique approach by not only storing message content but also preserving media, links, buttons, and metadata in an organized format. Whether you're looking to back up your personal chats, archive large channels, or extract important data from groups, **TelegramBackup** ensures a seamless and efficient process.

## Key Features

- **Comprehensive Backup**: TelegramBackup archives all forms of communication, including text messages, media files, forwarded messages, and message buttons.
- **User-Friendly Interaction**: Allows users to choose between backing up specific entities (users, channels, groups) or all available dialogs at once.
- **Media Download**: Offers the option to automatically download media files associated with messages, such as photos, videos, and documents.
- **HTML Output**: Generates clean, readable HTML files for easy navigation and visualization of backed-up messages.
- **SQL Database Storage**: All messages, media, and related data are stored in a local SQLite database, providing a structured and easily accessible archive.
- **Multiple Entity Support**: Supports users, channels, supergroups, and regular groups, ensuring that all your important data is captured.

## Additional Strengths

- **Data Integrity**: The tool uses a structured SQLite database to ensure that messages, media, and metadata are saved in an organized manner, allowing for future retrieval and analysis.
- **Jinja2 Templating for Customization** [Optional]: Using the Jinja2 template engine, TelegramBackup provides a customizable framework for generating HTML files, allowing you to modify how your backup looks based on your preferences.
- **Security-Oriented**: No private keys or sensitive data are stored on the server side. Everything is handled securely on your local machine.
- **Flood Control Management**: Implements Telegram API best practices to avoid overloading the server, handling flood wait errors efficiently.
- **Cross-Platform Compatibility**: Works on any platform that supports Python, making it easy to run the tool on Windows, macOS, or Linux.

## Installation

### Prerequisites
- Python 3+
- [Telethon](https://github.com/LonamiWebs/Telethon) - Python 3 MTProto library
- [Jinja2](https://palletsprojects.com/p/jinja/)
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)
  
To install the required libraries, use the following command:
```bash
pip3 install telethon jinja2 beautifulsoup4
```

### Setup

1. Clone the repository:
    ```bash
    git clone https://github.com/N4rr34n6/TelegramBackup.git
    ```
2. Navigate to the project directory:
    ```bash
    cd TelegramBackup
    ```
3. Install the required dependencies:
    ```bash
    pip3 install -r requirements.txt
    ```

## Usage

1. Run the script:
    ```bash
    python3 telegram_backup.py
    ```
2. Enter the Telegram phone number when prompted to start the session.
3. The script will list all available entities (Users, Channels, Groups) and save the list to `entities_list.txt`.
4. Choose whether to process a specific entity or all entities.
5. Decide whether you want to download media files along with the messages.
6. After completion, the messages are saved in an SQLite database, and an HTML file is generated for easy browsing.

### Example Output

```bash
$ python3 telegram_backup.py 
Enter the phone number: +34123456789
Please enter the code you received: 12345
Please enter your password: 
Signed in successfully as Marcos
Session started as Marcos

Users:
[...]

Channels:
[...]

Supergroups:
[...]

Groups:
[...]

Unknown:
[...]

The entity list has been saved in 'entities_list.txt'

Do you want to process a specific entity (E) or all entities (T)? E
Enter the number corresponding to the entity you want to process: 105
How many messages do you want to retrieve? (Press Enter for all): 
Do you want to download media files? (Y/N): Y

Processing: {channel} (ID: 0123456789)
Message 1 processeddd
All messages from {channel} have been processed.
HTML file generated: 0123456789_{channel}.html

Do you want to process another entity? (Y/N): y

Do you want to process a specific entity (E) or all entities (T)? e
Enter the number corresponding to the entity you want to process: 172
How many messages do you want to retrieve? (Press Enter for all): 
Do you want to download media files? (Y/N): y

Processing: ID: 0123456789 (ID: 0123456789)
The entity ID: 0123456789 (ID: 0123456789) is not accessible. It may have been deleted or you lack permission to access it.
```

## Customization

- **Templates**: You can customize the generated HTML file by modifying the Jinja2 template (`template.html`) provided in the repository.
- **Database Access**: The SQLite database is structured in a way that allows you to easily run SQL queries on the messages, media, and metadata.

## Technical Details

- **Message Processing**: TelegramBackup iterates through all messages of a selected entity, extracts their content, and stores them in an SQLite database. It also handles media download, message forwarding, and buttons associated with messages.
- **Flood Wait Handling**: The script implements flood control management by waiting for a specified time in case the Telegram API returns a flood error.
- **HTML Rendering**: Using Jinja2, TelegramBackup dynamically generates HTML files that can be easily viewed in any browser, preserving the structure of the original messages, including any media and buttons.

## Ethical Use and Legal Considerations

**TelegramBackup** is intended for personal use, enabling users to backup their own Telegram data. The misuse of this tool, such as unauthorized data extraction from accounts or channels where you do not have permission, is strictly prohibited. Ensure that all data you process with this tool complies with Telegram’s terms of service and local data protection laws.

## License

This script is provided under the GNU Affero General Public License v3.0. You can find the full license text in the [LICENSE](LICENSE) file.

---

With TelegramBackup, you have a comprehensive, customizable, and reliable solution for preserving your Telegram communications. Whether for personal archiving or professional data analysis, this tool offers unmatched flexibility and functionality.
