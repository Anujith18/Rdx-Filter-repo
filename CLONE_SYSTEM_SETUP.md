# RDX Auto Filter Clone System

## Main-bot admin ON/OFF

Admins listed in `ADMINS` see `🤖 CLONE SYSTEM: ON/OFF` on the main bot
start screen and in `/clones`. The live choice is saved in MongoDB and survives
restarts. OFF blocks new clone creation but does not stop existing clone bots.
`CLONE_MODE=False` remains the hard environment-level shutdown and cannot be
overridden from Telegram.

Clone search results are shown as full original-filename clickable text links.
Quality, language, season, episode, combined-files and pagination controls stay
as navigation buttons.

## What this release adds

The main RDX bot can create and run user-owned Auto Filter clone bots inside
the same worker. Each clone has an isolated MongoDB catalogue identified by its
Telegram bot ID. A clone cannot search, edit, stream, or delete another clone's
files.

The main bot provides:

- Create or Manage Own Clone
- secure BotFather token intake
- activate, deactivate, restart, status, and delete controls
- automatic recovery of active clones after a worker restart
- global owner commands for listing and controlling clones

Each clone provides:

- English `/start`, Help, About, and owner-only Settings
- private and group Auto Filter search
- cross-page Episode, Season, Language, Quality, and Combined filters
- private index channels and automatic indexing of new posts
- bulk indexing with `/index CHANNEL_ID LAST_MESSAGE_ID`
- source-message copy delivery for the best Telegram thumbnail
- custom start message, poster, caption, buttons, update and support links
- log channel, extra admins, force subscribe, auto-delete, and content protect
- shortlink verification, per-clone Premium, and referral rewards
- signed permanent Stream and Download URLs

## Required deployment settings

Clone mode is enabled by default. Set a stable encryption secret before users
create clones:

```env
CLONE_MODE=True
CLONE_SECRET_KEY=replace-this-with-a-long-random-private-value
CLONE_MAX_ACTIVE=10
CLONE_WORKERS=24
CLONE_REQUIRE_PREMIUM=False
CLONE_SEARCH_PAGE_SIZE=10
CLONE_SEARCH_SCAN_LIMIT=3000
```

Generate a suitable secret locally:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Never publish or casually change `CLONE_SECRET_KEY`. Changing it prevents the
worker from decrypting tokens that were stored with the previous key. When the
variable is omitted, the code derives a compatibility key from the main bot
credentials, but an explicit stable value is safer.

## User clone creation

1. The user taps `CREATE / MANAGE OWN CLONE` in the main bot.
2. The user creates a new bot through BotFather.
3. The user sends or forwards the complete BotFather token message.
4. The main bot deletes that Telegram message, validates the token by starting
   the clone, encrypts the token, and stores the clone record.
5. The user opens the clone and sends `/settings`.

The first release intentionally allows one clone per user. Set
`CLONE_REQUIRE_PREMIUM=True` if only main-bot Premium users may create clones.

## Configure a clone

Open the clone bot and use `/settings`. The owner can configure:

- Start Message and Start Poster
- custom URL button, Updates link, and Support link
- Log Channel
- Index Channels
- additional Admin user IDs
- PM Search and Group Search modes
- Verification, shortener domain/API, and tutorial
- Custom Caption
- Force Subscribe channels
- fallback thumbnail
- Auto Delete and deletion time
- Protect Content
- Stream and Download

The clone must be an administrator in every configured private index, log, and
force-subscribe channel. Force-subscribe input uses one channel per line:

```text
-1001234567890|https://t.me/example_channel
```

## Index files

New document, video, and audio posts in a configured Index Channel are indexed
automatically. To index existing posts:

```text
/index -1001234567890 5000
```

The first argument is the channel ID and the second is the last message ID to
scan. Bulk indexing runs in the background so search buttons remain responsive.

## Clone Premium and referrals

Clone owners and authorized clone admins can use:

```text
/addpremium USER_ID DAYS
/removepremium USER_ID
```

Premium clone users bypass clone verification. Referral links award 10 points
for each unique referred user; reaching each 100-point milestone grants 30
days of clone Premium.

## Main owner commands

Main-bot admins can use:

```text
/clones
/clone_start BOT_ID
/clone_stop BOT_ID
/clone_delete BOT_ID
```

## Capacity and safety

Every active clone is a separate Telegram client. Do not configure unlimited
clones on one small Heroku worker. Start with `CLONE_MAX_ACTIVE=5` or `10`,
observe memory and CPU, and increase only after load testing.

Deleting a clone removes its settings, users, Premium entries, verification
tokens, referral entries, and private indexed media from MongoDB. It cannot
revoke the BotFather token; the user must use BotFather `/revoke` to invalidate
that token completely.

Never share screenshots containing a real bot token. If a token appears in a
screenshot or public message, revoke it immediately in BotFather.
