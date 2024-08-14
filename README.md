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
op run --env-file op_discord.env -- python -m discord_app.df_discord
```

### environment
To run that discord bot in a test environment, your `op_discord.env` should look something like this:
```env
DF_API_HOST = "http://localhost:1337"

DISCORD_TOKEN = "REFERENCE TO THE TOKEN OF THE BOT YOU'RE TESTING WITH"
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


## Containerization
You should be able to build a docker container for the Desolate Frontiers Discord Frontend with this command:
```sh
op run --env-file op_discord_prod.env -- docker compose -f compose.df_discord.yml up -d --build
```

### environment
In order to run that, you need an `op_discord_prod.env` should look something like this:
```env
DF_API_HOST = "http://sofola:1337"

DISCORD_TOKEN = "op://Oori DevOps/Oori - Desolate Frontiers - Discord Bot/credential"
```
You'll need to have the [1Password CLI tools](https://developer.1password.com/docs/cli/get-started/) installed to make this work ("Manual" reccomended over "Homebrew")
