# RDX Auto Filter Anti-Bypass setup

The existing Auto Filter verification token remains user-bound, file-bound,
one-use and MongoDB-backed. This integration adds same-browser protection
around that Telegram verification link.

## Required Auto Filter deployment variables

```env
VERIFY=True
VERIFY_ACCESS_HOURS=24
VERIFY_TOKEN_MINUTES=15
ANTI_BYPASS_BASE_URL=https://imperial-arlee-hassanaly4201-b12957fd.koyeb.app
ANTI_BYPASS_API_KEY=PASTE_THE_ANTI_BYPASS_SERVICE_API_KEY_HERE
ANTI_BYPASS_REQUEST_TIMEOUT=20
```

`ANTI_BYPASS_API_KEY` must contain exactly the same value as `API_KEY` in the
Anti-Bypass Koyeb project. Do not use that project's `SECRET_KEY`, MongoDB
URI, shortener API key or bot token.

Redeploy or restart the Auto Filter bot after saving these variables.

## Shortener behavior

The Anti-Bypass service already performs the shortener step and validates its
callback. Therefore, a protected verification URL is not shortened again by
this bot.

Keep `SHORTLINK_URL` and `SHORTLINK_API`. Other bot features may still use
them, and the original verification flow uses them when both Anti-Bypass
variables are empty.

A partial, invalid or unreachable Anti-Bypass configuration fails closed:
the bot shows a temporary-unavailable message instead of exposing an
unprotected token link.

## Verification timing

- A newly generated verification link is valid for
  `VERIFY_TOKEN_MINUTES` (default: 15 minutes).
- A successful verification grants access for `VERIFY_ACCESS_HOURS`
  (default: 24 hours).
- The bot token and the Anti-Bypass protected link can each be used once.
