## Containerization
You should be able to build a docker container for the Desolate Frontiers Discord Frontend with this command:
```sh
op run --env-file op_discord_prod.env --no-masking -- docker compose -f compose.df_discord.yml up -d --build
```

### environment
In order to run that, you need an `op_discord_prod.env` should look something like this:
```env
LOG_LEVEL = "INFO"

DF_API_HOST = "http://70.90.116.204:8001"  # Official DF API

DISCORD_TOKEN = "op://Oori DevOps/Oori - Desolate Frontiers - Discord Bot/credential"  # Official DF bot/app

DF_GUILD_ID = "1225943320078057582"    # Desolate Frontiers server
DF_CHANNEL_ID = "1225943321067917406"  # #df-notifications
ALPHA_ROLE = "1276397166838939680"     # Alpha Tester role in DF server
BETA_ROLE = "1276393066684747796"      # Beta Tester role in DF server
```
You'll need to have the [1Password CLI tools](https://developer.1password.com/docs/cli/get-started/) installed to make this work ("Manual" reccomended over "Homebrew")
