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

## Setup

1. The API must be reachable by the listener: use the Cloudflare Worker (`KB_API_URL=https://ictkb-api.ictkb-api-worker.workers.dev`, `ADMIN_TOKEN` as set in the Worker). Photos need the `COHERE_API_KEY` secret on the Worker.
2. In `whatsapp-listener/`: `npm install`.
3. Link the number (once). The phone number is read from the environment and is never stored in the repository:

   ```bash
   PAIRING_PHONE=<number with country code, digits only> KB_API_URL=http://localhost:8000 ADMIN_TOKEN=<token> npm run link
   ```

   A code appears. On the phone: WhatsApp, Settings, Linked devices, Link a device, "Link with phone number instead", enter the code. When the log says "linked", stop the process.
4. Check the routing: `npm run groups` prints every group of the number, whether it is admin-only, and which route it matches. Fix `groups.json` if a route matches no group.
5. Run: `KB_API_URL=... ADMIN_TOKEN=... npm start`. Keep it running on an always-on machine (see the Docker service below).

The linked session is stored in `auth/`; it is a credential, is git-ignored, and must be kept private. If the phone does not open WhatsApp for about two weeks, WhatsApp unlinks the device and the listener logs "Logged out"; run `npm run link` again.

## Docker

`docker compose -f docker/docker-compose.yml --profile whatsapp up -d whatsapp` starts the listener with `auth/` and `state/` on a volume. Link the number first with `docker compose run --rm -e PAIRING_PHONE=... whatsapp npm run link`.

## Risks

Baileys is not an official WhatsApp client. WhatsApp can ban a number used with unofficial clients, and a protocol change can break the library until it is updated. Use a number that can be lost, and keep the listener passive (it never sends messages). Group administrators must agree that the number is a member.

## Tests

`npm test` runs the handler tests (routing, redaction, menu merging, edits, deletions, photos).
