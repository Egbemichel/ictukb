# WhatsApp listener

A small Node service that watches the official, admin-only WhatsApp groups listed in `groups.json` and sends what they post to the knowledge base through `POST /v1/admin/notes`. It uses the unofficial Baileys library over a linked device. There is no approval step: a post is searchable by chatbots as soon as it is received.

## What it does

| Group (matched by name) | Post type | Expiry |
|---|---|---|
| ICTU Community (Announcements) | announcement | 14 days |
| Students Union | student-life-post | 14 days |
| ICTU Food Order & Pick-Up | canteen-menu | its own day |
| ICT U SPORTS COMMUNITY | student-life-post | 14 days |

- Text messages and photo captions are posted. A photo (menu board, poster) is read by a vision model; the post is labelled "Read automatically from a photo".
- Several menu messages on one day are combined into one menu for that day. A deleted message is removed from it; an edited message is updated.
- Only messages from group admins are used: in an admin-only group every message qualifies; in a group where members can write, a message must come from one of its admins (`onlyAdminMessages`). Groups are matched by their own name.
- Before anything leaves the listener, phone numbers and @mentions are removed, and email addresses outside the official domains are removed.
- Voice notes, stickers, videos without captions and documents are ignored.
- Only the message id and the id of the resulting post are stored locally (`state/`), plus the current days' menu lines.

## Where the session lives

The linked-device session and the post bookkeeping are stored in the knowledge base database (table `wa_state`), reached through the Worker's admin endpoints `/v1/admin/wa-state/get` and `/set`. The host needs only `KB_API_URL` and `ADMIN_TOKEN`; it never holds the database password and needs no disk. A restart or a move to another host reconnects without a new pairing code. `AUTH_STORE=file` keeps the session in `./auth` instead (local use).

Only one process may use the session at a time. If a second instance connects, WhatsApp closes the first with "connection replaced"; the older instance logs it and exits.

## Setup

1. The API is the Cloudflare Worker (`KB_API_URL=https://ictkb-api.ictkb-api-worker.workers.dev`); `ADMIN_TOKEN` is the Worker's admin token.
2. Link the number once (the phone number is read from the environment and is never stored in the repository):

   ```bash
   cd whatsapp-listener && npm install
   KB_API_URL=... ADMIN_TOKEN=... PAIRING_PHONE=<country code and number, digits only> npm run link
   ```

   A code appears. On the phone: WhatsApp, Settings, Linked devices, Link a device, "Link with phone number instead", enter the code. When the log says "linked", stop the process.
3. Check the routing: `npm run groups` prints every group of the number, how many admins it has, and which route it matches.
4. Run it: `KB_API_URL=... ADMIN_TOKEN=... npm start`. It serves `GET /healthz` on `$PORT` (default 8080).
5. `npm run logout` unlinks the device. If WhatsApp logs the device out (for example after about two weeks without the phone opening WhatsApp), run `npm run link` again.

## Free hosting without your own machine

No free host is guaranteed to stay up. The listener is built to tolerate restarts, because its state is in Neon. Two options that need no payment card:

**Render (free web service).** Render dashboard, New, Blueprint, choose this repository (`render.yaml` is read automatically) and enter `ADMIN_TOKEN`. The free instance sleeps after 15 minutes without a request, so the Cloudflare Worker pings it every 5 minutes: set `LISTENER_URL` in `cloudflare-worker/wrangler.toml` to the Render address with `/healthz` (for example `https://ictkb-whatsapp.onrender.com/healthz`) and run `wrangler deploy`.

**Hugging Face Space (Docker).** Create a Space with the Docker SDK, add the repository files that `docker/Dockerfile.whatsapp` copies (`whatsapp-listener/` and the Dockerfile as `Dockerfile`), add a README header with `sdk: docker` and `app_port: 8080`, and set the secrets `ADMIN_TOKEN` and `KB_API_URL`. Free Spaces sleep after 48 hours without visits; the same keep-alive ping prevents it.

Cloud hosts use datacenter IP addresses, which WhatsApp is more likely to flag than a home connection; keep the listener passive (it never sends messages).

## Risks

Baileys is not an official WhatsApp client. WhatsApp can ban a number used with unofficial clients, and a protocol change can break the library until it is updated. Use a number that can be lost, and keep the listener passive (it never sends messages). Group administrators must agree that the number is a member.

## Tests

`npm test` runs the handler tests (routing, redaction, menu merging, edits, deletions, photos) and the session store tests.
