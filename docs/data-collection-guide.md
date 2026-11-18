# Data collection guide

The chatbot is only as good as its data. This guide describes how collectors work. The complete list of items is in [upload-checklist.md](upload-checklist.md); it is generated from `schema/catalog.yml`.

## 1. What is collected automatically

The website crawler reads pages (programs, entry requirements, faculties, academic calendar, application page) and recent news from ictuniversity.org every day. Collectors need not retype these. They must still check the crawled content against the offices, because the offices win in a disagreement.

## 2. What collectors do

Three kinds of work remain, shown as sections 1 to 4 of the checklist.

### 2.1 Upload files

1. Obtain the original file (PDF, Word, Excel) or a sharp photograph. Do not retype documents.
2. Name it `category_topic_YYYY-MM-DD.ext` and place it in `incoming/<category>/`. The checklist gives the exact name for every item.
3. Run `ictkb intake`. For each file it uploads the original to Cloudinary, extracts the text into `content/<category>/_extracted/`, and attaches the file to the matching document. A new draft document is created when none exists.
4. Open the document and replace the attachment description placeholder with one sentence that says what the file is and what it is used for. For an image, this description is the searchable text, so be specific: "Photograph of the ground floor sign pointing to admissions on the left and finance straight ahead".
5. Commit the document and the extracted text file. The original stays out of Git.

Dry run: `ictkb intake --dry-run`. Without Cloudinary credentials use `ictkb intake --local`; the file is registered, and the Cloudinary id is created when the maintainer uploads it later.

### 2.2 Answer the written questions

Each stub in `content/` lists the questions that the document must answer as headings. Write the answer under each heading, using the conditions that matter: who, when, how much, which office, how long, which form. When finished:

1. Fill `source_type`, `source_url` if any, `collected_by` and `collected_on`.
2. Set `confirmed_in_writing: true` once an office has confirmed in writing anything it first said verbally.
3. Set `owner` and `verified_by` to GitHub handles, `last_verified` to the date of checking, and `status: verified`.
4. Run `ictkb validate`.

### 2.3 Fill the Google Sheets

For each sheet listed in section 2 of the checklist, create a Google Sheet, paste the header row from `templates/sheets/<name>.csv`, fill the rows, share it as "Anyone with the link can view", and send the id to the infrastructure owner for `sources/sheets.yml`. Rules: one row per fact, no merged cells, no blank header cells, and consistent spelling of program, year and semester values because they define the grouping (for example always `Software Engineering`, `Year 2`, `S1`).

### 2.4 Confirmations

Some items are confirmations from an office (section 4 of the checklist). Obtain them in writing (email or signed note), attach the proof as a file under the relevant document, and record the date.

## 3. Collection rules

1. Every item records its source (office, person or URL), the date collected, and the collector's GitHub handle.
2. Keep original files. Photographs must be sharp and readable. ERP screenshots are one per step, in order, with any real password hidden.
3. Name files `category_topic_YYYY-MM-DD.ext`.
4. If an office only says something verbally, write it down and get it confirmed in writing.
5. If the website and an office disagree, the office or the official document wins; note the conflict in `conflict_note`.
6. Official contacts only. No personal numbers or private emails without the person's written consent.

## 4. Order of work

1. Priority P0 items (fees and installments, course registration, transcript, timetables, ERP login, announcements, contacts, academic regulations, academic calendar).
2. Priority P1 items.
3. Priority P2 items.

After each batch, run `python eval/run_eval.py`. The report lists which golden questions are still not covered and which fail, which tells collectors what to collect next.

## 5. Quality checklist for a document

- The answer to each heading can be understood without the rest of the document.
- Amounts include the currency; dates include the year; deadlines name the semester.
- Process steps are numbered and name the office and the form.
- Nothing is written that the source does not state.
- The document says what is not available, for example "There is no refund after the second week", when that is the rule.

## 6. Daily posts: canteen menu, bus updates and announcements

The canteen menu, bus information and announcements are published in WhatsApp groups, not in a document or sheet. A designated maintainer copies the message and posts it into the knowledge base. Each post expires automatically, so a chatbot never repeats yesterday's menu.

From the repository root (one command per message):

```bash
ictkb post canteen-menu --by YOUR-HANDLE --text "Rice and beans 500 FCFA, ..."
ictkb post bus-update --by YOUR-HANDLE --title "Route 2 delayed" --text "..."
ictkb post announcement --by YOUR-HANDLE --title "Classes resume Monday" --text "..."
```

Use `--file message.txt` for a long message, `--date YYYY-MM-DD` for another day, and `--until YYYY-MM-DD` to set the last valid day. A menu is valid for its own day only; bus updates for 7 days and announcements for 14 days unless `--until` is given. Posting a second menu for the same day replaces the first.

Messages with email addresses outside the official domains are refused. Do not post personal phone numbers or private information.

The same function is available to a phone shortcut, Google Form or script through `POST /v1/admin/notes` with the admin token (fields: kind, text, by, title, date, until). Expired posts are removed by `ictkb notes-prune`, which also runs daily in the scheduled workflow.

The posts can also be created automatically: the WhatsApp listener (`whatsapp-listener/`) watches the official admin-only groups and posts their messages without any manual step. See its README.
