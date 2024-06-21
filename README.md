# Betulon

Betulon is a tool to import (new) Mastodon bookmarks to [betula](https://betula.mycorrhiza.wiki).

Since betula does not offer an API, it works by manipulating the database directly.

## Usage

Configure your environment:

```
cp .env.example .env
```

Customize it to your liking. To get the `MASTODON_ACCESS_TOKEN`:

- Login to your Mastodon instance (e.g., https://mastodon.social)
- Go to *Preference*, *Development*, *New Application*.
- Give it a name and give it the `read:bookmarks` scope.
- Submit it and then, by clicking its name, copy the Access Token.

Run it like so (in fish)

```
pip install -e .
# source your .env in your shell. If you use fish, `export (cat .env)`
export (cat .env); betulon
```

### Docker

If you wish to use it with Docker, first build it

```
$ docker build -t betulon -f Dockerfile .
```

Then update these variables in `.env`:

```
DB_PATH=/usr/src/app/database/links.betula
LOGS_PATH=/usr/src/app/logs
STATE_PATH=/usr/src/app/state
```

and run it like so

```
$ docker run \
    -v <db_path>:/usr/src/app/database \
    -v <logs_path>:/usr/src/app/logs \
    -v <state_path>:/usr/src/app/state \
    --env-file .env \
    --name betulon_container
    betulon:latest  
```

If you wish to have `cron` run it every hour, add the following to your crontab

```
00 * * * * docker container start betulon_container
```
