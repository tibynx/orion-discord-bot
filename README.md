# ✨ Orion

Orion is a Discord server management and utility bot that provides various administrative and convenience features for Discord server owners and moderators.

## Features

* Message and thread management
* Manage webhooks
* Send messages as the bot or using a webhook
* Play audio files in voice channels
* Customize bot presence and activity
* Auto-expiring temporary roles
* Send messages and expressions as the bot

## Setup

### Prerequisites

1. Create an application on the [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" and give it a name.
   - Note down the Application ID for later.
   - Go to the "Bot" tab and click "Add Bot".
   - Under "TOKEN", click "Copy" to copy your bot token. (You might need to reset it to see it.)
   - You don't need to enable any Privileged Gateway Intents for the bot.
   > [!NOTE]
   > This bot intended to be used in only one server at a time. If you want to use it in multiple servers, you will need to create another bot with different bot tokens.
2. Invite the bot to a Discord server
   - You can use the premade link in the [invite section](#invite).

Now choose one of the following methods to run the bot!

### Docker

1. Pull the latest image from Docker Hub
   ```sh
   docker pull tibynx/orion:latest
   ```
2. Run the container with the required environment variables and volume mounts
   - See the configuration section below for details! Only required options are included in this example.
   - Change `/path/to/logs` to a directory on your host where you want to store the logs.
    ```sh
    docker run -d \
      --name=orion \
      -e BOT_TOKEN=your_bot_token_here \
      -v /path/to/logs:/app/logs \
      -v /path/to/temp_roles_db.json:/app/temp_roles_db.json \
      tibynx/orion:latest
    ```

### Source

1. Install **[Python 3.14 or newer](https://www.python.org/downloads/)**
2. Clone the repository and install all required packages!
   ```sh
   git clone https://github.com/tibynx/orion.git
   cd orion
   ```
   ```sh
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and configure your settings.
   - See the configuration section below for details!
   - **Do not share your `.env` file publicly!**
4. Invite the bot to a Discord server
   - You can use the premade link in the usage section.
5. Start the bot
   ```sh
   python main.py
   ```

### Configuration

|     Variable      | Description                                                                                     |
|:-----------------:|-------------------------------------------------------------------------------------------------|
|    `BOT_TOKEN`    | Your bot token. Do not share this with anyone!                                                  |
|  `SUCCESS_EMOJI`  | (Optional) The emoji the bot will use to indicate success.                                      |
|   `ERROR_EMOJI`   | (Optional) The emoji the bot will use in indicate issues.                                       |
| `PREVIOUS_EMOJI`  | (Optional) The emoji the bot will use for the previous button's icon.                           |
|   `NEXT_EMOJI`    | (Optional) The emoji the bot will use for the next button's icon.                               |
| `EXCLUDED_EMOJIS` | (Optional) A comma separated list of emojis (names or IDs) to exclude from the bot emojis list. |

## Usage

### Invite

Invite your bot to a server using this premade link! It already contains the proper permissions. Replace `YOUR_APP_ID` with your bot's application ID.

```text
https://discord.com/oauth2/authorize?client_id=YOUR_APP_ID&permissions=120796048384&integration_type=0&scope=bot+applications.commands
```

> [!TIP]
> You can restrict commands to specific roles/users and channels using Discord's Integrations menu inside the Server Settings.

### Mentioning Users and Roles

Due to Discord limitations, you cannot directly mention users or roles in the bot's response. However, you can use their IDs to create mentions. You'll need to enable Developer Mode in Discord to copy user and role IDs. To enable Developer Mode, go to User Settings > Advanced > Developer Mode.
If you want to mention `@everyone` or `@here`, simply write them in your message. But if you want to mention roles or specific users, you need to use their IDs in the following format: `<@&ROLE_ID>` for roles and `<@USER_ID>` for users. 

### Pinging mentions

For convenience, you can choose to ping the mentions by ticking the options in the message modal. The bot will not mention `@everyone` or `@here` by default.

### Using emojis

Emojis can be either a Unicode emoji (e.g., ✨) or a custom emoji in the format `<:EMOJI_NAME:EMOJI_ID>` (static) or `<a:EMOJI_NAME:EMOJI_ID>` (animated) (e.g., `<a:star:733395207222984794>`). The bot must be in the server where the custom emoji is from or added to the bot on the Discord Developer Portal to use it. Use the `/botemojis` command to see all the emojis the bot has.

### Formatting code blocks and text

Just like normal messages, you can format your text using Markdown syntax. You can make text **bold**, *italic*, ~~strikethrough~~, etc. The bot message will be formatted accordingly, but there is no preview.
