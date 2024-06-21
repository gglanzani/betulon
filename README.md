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
docker build -t betulon -f Dockerfile .
```

And then

```
docker run \
  -v <db_path>:/usr/src/app/database \
  -v <logs_path>:/usr/src/app/logs \
  -v <state_path>:/usr/src/app/state \
  --env-file .env \
  betulon:latest  
```
