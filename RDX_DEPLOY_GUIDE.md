# RDX deployment guide

## Recommended update

Replace the complete repository with this ZIP. The redesign changes Python,
HTML, metadata, and image assets together; uploading only one Python file will
leave parts of the old design in place.

Do not delete or rename these internal compatibility paths:

- `Deendayal_botz/`
- `plugins/Deendayal/`
- the existing MongoDB collection configured in `COLLECTION_NAME`

They are intentionally retained so streaming, imports, and previously indexed
files continue to work. Users and deployment logs show RDX branding.

## v5.9 secure clone system

This release adds user-created Auto Filter clone bots with encrypted tokens,
private per-clone media catalogues, owner settings, cross-page filters, HD
source-message delivery, Premium/referrals, verification, and signed permanent
stream/download links.

Read `CLONE_SYSTEM_SETUP.md` before enabling clone creation. The recommended
new environment value is:

```env
CLONE_MODE=True
CLONE_SECRET_KEY=your-stable-private-random-secret
CLONE_MAX_ACTIVE=10
CLONE_WORKERS=24
```

The main bot keeps using the existing `COLLECTION_NAME`. Clone files use new
MongoDB collections prefixed with `clone_`, so adding the system neither moves
nor re-indexes existing main-bot files.

For a manual update from v5.8, add/replace:

- complete `clone_system/` folder
- `plugins/clone_manager.py`
- `plugins/commands.py`
- `plugins/route.py`
- `bot.py`
- `info.py`
- `media_delivery.py`
- `Deendayal_botz/util/custom_dl.py`
- `requirements.txt`
- `app.json`
- `CLONE_SYSTEM_SETUP.md`

Replacing the complete repository is safer because the manager, web routes,
dependencies, and environment metadata must be deployed together.

## Files added

- `branding.py`
- `media_delivery.py`
- `search_filters.py`
- `assets/rdx-profile-logo.jpg`
- `assets/rdx-welcome-banner.jpg`
- `assets/rdx-no-results.jpg`
- `assets/rdx-join-channel.jpg`
- `assets/rdx-premium.jpg`
- `assets/rdx-verification.jpg`
- `assets/rdx-verified.jpg`
- `verification_ui.py`

## BotFather changes

The repository cannot change the Telegram profile automatically. In BotFather:

1. Use `/setuserpic` and upload `assets/rdx-profile-logo.jpg`.
2. Use `/setname` and set `RDX AUTO FILTER`.
3. Use `/setabouttext` for a short RDX description.
4. Use `/setdescription` for the full welcome description.
5. Use `/setcommands` to update the command menu.

Telegram button colors, chat wallpaper, and app font are controlled by the
Telegram client/theme and cannot be set by bot code.

## Thumbnail notes

- New channel posts save source chat/message and the largest thumbnail.
- Delivery first copies the original source post, preserving the best available
  Telegram thumbnail.
- If duplicate records exist across both MongoDB databases, delivery resolves
  the record containing the original source post before using cached media.
- Re-indexing a duplicate refreshes source-message and thumbnail metadata in
  both databases instead of creating another incomplete duplicate.
- Old rows without source IDs are searched in `CHANNELS` on first delivery.
  The bot verifies the Telegram file ID, copies that original post, and stores
  the recovered source IDs so later deliveries do not need another search.
- Cached-media fallback downloads and uploads the thumbnail as a fresh JPEG.
- Re-index only if the source post was deleted or channel search is unavailable.
- Keep the bot in every source/index channel.

Normal Telegram thumbnails are compressed by Telegram, so they cannot display
at full poster resolution.

## Poster and banner locations

The main RDX posters are local files, not hard-coded public links:

| Screen | Environment variable | Default file |
| --- | --- | --- |
| `/start` welcome | `PICS` | `assets/rdx-welcome-banner.jpg` |
| No results | `NOR_IMG` | `assets/rdx-no-results.jpg` |
| Spell check | `SPELL_IMG` | `assets/rdx-no-results.jpg` |
| Force subscribe | `FSUB_PICS` | `assets/rdx-join-channel.jpg` |
| Premium plans | `SUBSCRIPTION` | `assets/rdx-premium.jpg` |
| Verification required | `VERIFY_POSTER` | `assets/rdx-verification.jpg` |
| Verification completed | `VERIFIED_POSTER` | `assets/rdx-verified.jpg` |
| Bot profile logo | BotFather `/setuserpic` | `assets/rdx-profile-logo.jpg` |

The central defaults are declared in `branding.py`, then mapped to the runtime
variables in `info.py`. Any poster can be overridden with an HTTPS image URL in
the deployment environment. The profile logo must still be changed manually
through BotFather.

## English verification system

All verification screens and buttons are English-only. Every file-delivery
route uses the same shared template, so users no longer receive different or
malformed messages depending on the selected file link.

```env
VERIFY=True
VERIFY_ACCESS_HOURS=24
VERIFY_TOKEN_MINUTES=15
VERIFY_NOTICE_DELETE_SECONDS=180
VERIFY_TIMEZONE=Asia/Kolkata
VERIFY_POSTER=assets/rdx-verification.jpg
VERIFIED_POSTER=assets/rdx-verified.jpg
HOW_TO_VERIFY=https://t.me/your_verification_tutorial
DEENDAYAL_VERIFIED_LOG=-100xxxxxxxxxx
SHORTLINK_URL=your-shortener-domain.com
SHORTLINK_API=your-shortener-api-key
```

Verification links are one-use, expire after `VERIFY_TOKEN_MINUTES`, and are
stored in MongoDB so an ordinary bot restart does not invalidate a pending
link. Successful free access lasts for `VERIFY_ACCESS_HOURS`. Premium users
continue to bypass verification.

## Search-filter fixes

- Dual Audio matches `DUAL`, `Dual Audio`, and separator variants.
- Multi Audio matches `MULTI`, `Multi Audio`, `Multiple Audio`, and variants.
- Language buttons accept abbreviations and full names, such as `HIN`/`Hindi`
  and `ENG`/`English`.
- Episode searches accept `S01E01`, `S01 E01`, `S01-E1`, and
  `Season 01 Episode 01`.
- The episode menu scans every matching database result and displays only
  episodes that exist, with the number of matching files beside each episode.
- Combined packs such as `E13-E16`, `E13 to 16`, and `E13 16 COMBINED` are
  returned when any covered episode is selected.
- Season, Episode, Language, and Quality selections remain active together and
  can be replaced independently.
- Filtering runs in MongoDB before pagination, so matching files are not missed
  when they appear after the first result page.

If the previous RDX ZIP is already deployed, the runtime files required for
this filter update are:

- `search_filters.py` (new file in the repository root)
- `database/ia_filterdb.py`
- `plugins/pmfilter.py`
- `utils.py`

## Responsive button fix

The July 30 screen recording showed that the episode menu could open, but an
episode selection such as `E02` could then remain unchanged. The cause was not
the episode matcher: search and file-delivery handlers were keeping Pyrogram
workers occupied during the full 5–10 minute auto-delete delay. Once all
workers were occupied, button callbacks waited in the update queue.

This release keeps the same auto-delete behaviour but schedules cleanup in the
background, allowing the handler to return immediately. It also safely updates
both text and photo/caption result messages. If Telegram cannot edit the
existing message, the bot sends a replacement result instead of leaving the
button apparently unresponsive.

For a manual update from the immediately previous ZIP, replace:

- `plugins/pmfilter.py`
- `plugins/commands.py`
- `utils.py`
- `branding.py`
- the complete `assets/` folder

Replacing the complete repository ZIP is recommended. No environment variable,
MongoDB collection, or re-index is required for this button update.

## Start screen and animation

The private `/start` screen now always tries the configured `PICS` image, then
the bundled RDX welcome banner, and finally a text-only welcome. A failed or
slow animation cleanup can no longer block the welcome message.

Optional environment variables:

```env
START_ANIMATION=True
START_ANIMATION_STYLE=cinema
```

Available styles are `cinema`, `neon`, and `minimal`. Set
`START_ANIMATION=False` to disable the loader completely.

For a manual verification update to v5.7, replace/add:

- `info.py`
- `utils.py`
- `database/verify_db.py`
- `plugins/commands.py`
- `verification_ui.py`
- `app.json`
- `assets/rdx-verification.jpg`
- `assets/rdx-verified.jpg`

For the earlier v5.5 to v5.6 filter update, replace:

- `search_filters.py`
- `plugins/pmfilter.py`

The full ZIP also contains updated tests and documentation. No environment
variable or collection-name change is required.

## Required security values

Configure all real credentials as environment variables. Do not put them in
`info.py` or commit them to a public repository:

- `BOT_TOKEN`
- `API_ID`
- `API_HASH`
- `DATABASE_URI`
- `DATABASE_URI2`
- `SHORTLINK_API`

If an earlier public commit contained real credentials, rotate the bot token,
database password, and shortener API key before redeploying.
