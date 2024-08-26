```
╔═════════════════════════════════════════════════════════════════════════════════════╗
║ ┏┳┓┏━┓┏━┓┏━┓┳  ┏━┓┏┳┓┏━┓  ┏━┓┳━┓┏━┓┏┓┏┏┳┓┳┏━┓┳━┓┏━┓  ┏┳┓┳┏━┓┏━┓┏━┓┳━┓┏┳┓  ┏━┓┏━┓┏━┓ ║
║  ┃┃┣┫ ┗━┓┃ ┃┃  ┣━┫ ┃ ┣┫   ┣┫ ┣┳┛┃ ┃┃┃┃ ┃ ┃┣┫ ┣┳┛┗━┓   ┃┃┃┗━┓┃  ┃ ┃┣┳┛ ┃┃  ┣━┫┣━┛┣━┛ ║
║ ╺┻┛┗━┛┗━┛┗━┛┻━┛┻ ┻ ┻ ┗━┛  ┗  ┻┗━┗━┛┛┗┛ ┻ ┻┗━┛┻┗━┗━┛  ━┻┛┻┗━┛┗━┛┗━┛┻┗━╺┻┛  ┻ ┻┻  ┻   ║
╚═════════════════════════════════════════════════════════════════════════════════════╝
```
# Desolate Frontiers Discord Frontend
## Running the Discord frontend
To run the Desolate Frontiers Discord frontend, you can use this command (from the root folder):
```sh
source $HOME/.local/venv/df_discord/bin/activate
op run --env-file op_discord.env --no-masking -- python -m discord_app.df_discord
```

### environment (internal version, remove before open-source)
To run that discord bot in a test environment, your `op_discord.env` should look something like this:
```env
LOG_LEVEL = "INFO"

DF_API_HOST = "http://localhost:1337"

DISCORD_TOKEN = "SECRET REFERENCE TO THE TOKEN OF THE BOT YOU'RE TESTING WITH"  # Discord bot/app to use
# Find this as the "Copy Secret Reference" option in the dropdown for the credential in 1Password

# Server that is used as the presumed playerbase to send notifications to 
DF_GUILD_ID = "1119003654800822302"    # (oori dev server)
# Channel to send those notifications in
DF_CHANNEL_ID = "1179194033923432578"  # (#bot-attic)
```
You'll need to have the [1Password CLI tools](https://developer.1password.com/docs/cli/get-started/) installed to make this work ("Manual" reccomended over "Homebrew")


## Setup
### Venv
DF requires python **3.12**. Highly advised to get a new virtual environment setup specifically for DF. To create a venv in the oori "standard" location of your `.local/venv/`:
```sh
/usr/local/bin/python3.12 -m venv $HOME/.local/venv/df_discord
source $HOME/.local/venv/desolate_frontiers/bin/activate
```

### Libraries
Get the correct libraries installed to the venv:
```sh
pip install -U pip
pip install -U -r requirements.txt -c constraints.txt
```
