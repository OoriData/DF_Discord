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
DF_API_KEY = "DUMMY"

DF_MAP_RENDERER = "http://localhost:9100"

DISCORD_TOKEN = "SECRET REFERENCE TO THE TOKEN OF THE BOT YOU'RE TESTING WITH"  # Discord bot/app to use
# Find this as the "Copy Secret Reference" option in the dropdown for the credential in 1Password

# Server that is used as the presumed playerbase to send notifications to 
DF_GUILD_ID = "1119003654800822302"    # (oori dev server)
# Channel to send those notifications in
DF_CHANNEL_ID = "1179194033923432578"  # (#bot-attic)

WASTELANDER_ROLE = "1201669829140942970"  # "WASTELANDER test" role in oori dev server
ALPHA_ROLE = "1201669791866441748"        # "ALPHA test" role in oori dev server
BETA_ROLE = "1201669724987990096"         # "BETA test" role in oori dev server
```
You'll need to have the [1Password CLI tools](https://developer.1password.com/docs/cli/get-started/) installed to make this work ("Manual" reccomended over "Homebrew")


## Setup
### Venv
The Desolate Frontiers Discord App requires **Python 3.12**. It is highly reccomended to create a new virtual environment (venv) setup specifically for the DF Discord App.

To create a venv in the "standard" location of `~/.local/venv/`:
```sh
/usr/local/bin/python3.12 -m venv $HOME/.local/venv/df_discord
```
You can manually activate that with:
```sh
source $HOME/.local/venv/df_discord/bin/activate
```

### Libraries
Get the correct libraries installed to the venv:
```sh
pip install -U pip
pip install -U -r requirements.txt -c constraints.txt
```

### VSCode
To activate that in VSCode, open a python file and select the python version in the status bar in the bottom right in your VSCode window and click `Enter interpreter path...`, and enter:
```
~/.local/venv/df_discord/bin/python3.12
```
