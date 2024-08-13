```
╔═════════════════════════════════════════════════════╗
║ ┏┳┓┏━┓┏━┓┏━┓┳  ┏━┓┏┳┓┏━┓  ┏━┓┳━┓┏━┓┏┓┏┏┳┓┳┏━┓┳━┓┏━┓ ║
║  ┃┃┣┫ ┗━┓┃ ┃┃  ┣━┫ ┃ ┣┫   ┣┫ ┣┳┛┃ ┃┃┃┃ ┃ ┃┣┫ ┣┳┛┗━┓ ║
║ ╺┻┛┗━┛┗━┛┗━┛┻━┛┻ ┻ ┻ ┗━┛  ┗  ┻┗━┗━┛┛┗┛ ┻ ┻┗━┛┻┗━┗━┛ ║
╚═════════════════════════════════════════════════════╝
```

# Desolate Frontiers Discord Frontend
## Running the Discord frontend
To run the Desolate Frontiers Discord frontend, you can use this command (from the `body/df_discord/` folder):
```
op run --env-file op_discord.env -- python -m body.df_discord.df_discord
```

To do that, you'll need a `body/df_discord/op_discord.env` that looks somethin like this:
```
DF_API_HOST = "http://localhost:1337"

DISCORD_TOKEN = "REFERENCE TO THE TOKEN OF THE BOT YOU'RE TESTING WITH"
```

## Containerization
You should be able to build a docker container for the Desolate Frontiers Discord Frontend with this command:
```
op run --env-file op_discord_prod.env -- docker compose -f compose.df_discord.yml up -d --build
```

### environment
In order to run that, you need an `op_discord_prod.env` should look something like this:
```env
DF_API_HOST = "http://sofola:1337"

DISCORD_TOKEN = "op://Oori DevOps/Oori - Desolate Frontiers - Discord Bot/credential"
```
