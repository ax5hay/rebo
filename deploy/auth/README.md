# Standalone login (B-036)

The bot never handles passwords. In `auth.mode: headers` it trusts the identity a gateway puts on
each request. For a standalone install that gateway is **oauth2-proxy** (already in
`compose.prod.yml`); it signs people in with any OIDC identity provider.

## Roles from groups

| IdP group | Role in the bot |
|---|---|
| `reportsbot-owners` | owner (configuration) |
| `reportsbot-admins` | admin (shared knowledge, review, requests) |
| anyone else who can sign in | user |

The names are fixed (no configuration). Behind the proxy the bot takes the user from
`X-Forwarded-Email` (or `-User`) and the role only from `X-Forwarded-Groups`; any `X-User-*` header a
client sends is ignored. Checked on 2026-10-21 against oauth2-proxy v7.15.5: a forged
`X-Forwarded-Groups` / `X-Forwarded-Email` from the client does not reach the bot (the proxy strips
them), while a forged `X-User-Role` does reach it, which is why the bot ignores it there. The bot
must not be reachable except through the proxy (`compose.prod.yml` publishes only the proxy).

## You already have an IdP (Entra ID, Google Workspace, Okta, Keycloak, …)

In `.env`, set the oauth2-proxy variables for your provider (see the oauth2-proxy provider docs):
`OAUTH2_PROXY_PROVIDER=oidc`, `OAUTH2_PROXY_OIDC_ISSUER_URL`, `OAUTH2_PROXY_CLIENT_ID`,
`OAUTH2_PROXY_CLIENT_SECRET`, `OAUTH2_PROXY_COOKIE_SECRET` (32 random bytes),
`OAUTH2_PROXY_REDIRECT_URL=https://<bot>/oauth2/callback`, `OAUTH2_PROXY_SCOPE="openid email profile groups"`
(the groups scope or claim name differs per IdP; set `OAUTH2_PROXY_OIDC_GROUPS_CLAIM`), and
`OAUTH2_PROXY_EMAIL_DOMAINS` to your domain. Create the two groups above in the IdP.

## No IdP: Pocket ID

`compose.pocket-id.yml` adds Pocket ID v2.18.0 (passkey sign-in, OIDC, BSD-2-Clause; released
2026-10-04) and points the proxy at it:

1. Set `POCKET_ID_URL` and `BOT_URL` (public HTTPS URLs; passkeys need HTTPS) in `.env`.
2. `docker compose -f compose.prod.yml -f deploy/auth/compose.pocket-id.yml up -d`
3. Open `<POCKET_ID_URL>/setup`, register the first admin passkey.
4. In Pocket ID: add an OIDC client with callback `<BOT_URL>/oauth2/callback`; copy its id and
   secret into `.env` as `OAUTH2_PROXY_CLIENT_ID` / `_CLIENT_SECRET`; set `OAUTH2_PROXY_COOKIE_SECRET`.
5. Create the groups `reportsbot-admins` and `reportsbot-owners`, add people, restart `auth`.

Not run end to end here: passkey sign-in needs a browser, HTTPS and a real domain. The compose file
validates; the header behaviour above was tested with oauth2-proxy and a header-echo upstream.
