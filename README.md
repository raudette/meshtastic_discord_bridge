# meshtastic_discord_bridge

A Discord bot which bridges discussions between a Discord channel and a Meshtastic mesh through a locally connected radio

## Requirements

- Python
- A supported Meshtastic radio connected via USB 
- Discord key and a channel

## Installation and Startup

Get a Discord Bot account and invite the bot to a server.  [Instructions](https://discordpy.readthedocs.io/en/stable/discord.html)

Fill in the values for your environment in sampledotenvfile, and rename to .env 

```
python3 -m pip install -r requirements.txt
python meshtastic_discord_bridge.py
```

## Usage

You can now interact with Meshtastic through Discord.

```
$sendprimary <message> sends a message up to 225 characters to the the primary channel
$send nodenum=########### <message> sends a message up to 225 characters to nodenum ###########
$activenodes will list all nodes seen in the last 15 minutes
```

## Screenshot

![Interacting with Meshtastic through Discord](/DiscordScreenshot.png)

