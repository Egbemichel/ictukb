# ICT University Knowledge Base API: User Manual

Version 1.0, 18 November 2026

This manual explains how to connect a chatbot, a web page or any other program to the ICT University knowledge base. It assumes no earlier experience with the system. Follow sections 1 to 4 to make a first successful request in about ten minutes, and sections 5 to 8 to turn the answers into a working chatbot.

Contents

1. What the knowledge base is and what it can answer
2. Before you start: the address and an API key
3. Your first request
4. Understanding the response
5. Building a chatbot step by step
6. The other endpoints
7. Limits, errors and good practice
8. Troubleshooting
9. Reference: every endpoint, field and value
10. For maintainers: issuing and revoking keys

---

## 1. What the knowledge base is and what it can answer

The knowledge base is a database of official information about ICT University, kept up to date by the student project team. You send it a question in plain English or French; it returns the passages of official documents that best answer the question, together with the document title, a link to the source, the date the information was last checked, and a judgement of whether the passages really contain the answer.

It does not write answers. Your program (the chatbot) takes the returned passages, together with the student's question, and produces the final reply, for example with a language model of your choice. This design keeps the facts in one place: when an office changes a fee or a deadline, every chatbot gives the new answer without being changed.

**Information currently available** (as of 18 November 2026):

| Area | Examples of what is covered |
|---|---|
| About the university | Overview, official contacts, academic regulations (grading scale, GPA, attendance), academic calendar |
| Admissions | How to apply, Bachelor and Masters entry requirements, transfer and international students, application fee |
| Programs | List of programs of both faculties, duration, delivery, courses and lecturers of the Fall 2026 timetable |
| Procedures | Course registration, add and drop, resits, transcripts, complaints, deferment, change of program, internships |
| Finance | Tuition and installment plan, bank accounts, proof of payment, late payment, clearance |
| ERP | Login, password reset, registration, results, fees, requests, support |
| Campus | Location and map link |
| Timetables | Fall 2026 undergraduate lecture timetable, examination period |
| People | University leadership, lecturers per course |
| Live posts | Canteen menu, announcements, student life and bus updates, posted by the official WhatsApp groups as they appear (these expire automatically) |

**Not yet available:** the full fee schedule per program, application deadlines, the office directory, floor plans, staff and head-of-department lists, PhD programs, the examination timetable (published as a notice during the examination period), and bus routes. For these questions the system answers that the information is not available yet, and your chatbot should tell the student to ask the Admissions office.

**Never stored:** personal data (grades, fee balances, identity numbers) and private phone numbers. A question such as "What is my fee balance?" correctly returns no answer.

## 2. Before you start: the address and an API key

**Base address:** `https://ictkb-api.ictkb-api-worker.workers.dev`

Every endpoint except `/v1/health` requires an API key sent in the header `X-API-Key`.

**Requesting a key.** Open an issue titled "API key request" in the project repository, `https://github.com/Egbemichel/ictukb/issues`, giving your name, your class and what you are building. A maintainer creates a key for you and sends it privately. The key is shown only once, so store it immediately. A key identifies your chatbot, allows 60 requests per minute and can be switched off by the maintainers if it is misused. It protects the service from overload; it is not a secret between you and the university, but you should still keep it private.

**Keep the key out of public code.** Never commit it to a public repository and never place it in the JavaScript of a web page. Store it in an environment variable (see the examples below) or in your hosting provider's secret settings.

To check the service is running, which needs no key:

```bash
curl https://ictkb-api.ictkb-api-worker.workers.dev/v1/health
```

A healthy service answers with `"status": "ok"`.

## 3. Your first request

### 3.1 With curl

Replace `YOUR_KEY` with your key.

```bash
curl -X POST https://ictkb-api.ictkb-api-worker.workers.dev/v1/search \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Can I pay my fees in installments?"}'
```

On Windows PowerShell:

```powershell
curl.exe -X POST https://ictkb-api.ictkb-api-worker.workers.dev/v1/search `
  -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" `
  -d '{\"query\": \"Can I pay my fees in installments?\"}'
```

### 3.2 With Python

Install the `requests` library (`pip install requests`), then save this as `try_search.py`:

```python
import os
import requests

API = "https://ictkb-api.ictkb-api-worker.workers.dev"
KEY = os.environ["KB_API_KEY"]          # set it first: see below

response = requests.post(
    f"{API}/v1/search",
    headers={"X-API-Key": KEY},
    json={"query": "Can I pay my fees in installments?", "top_k": 3},
    timeout=60,
)
response.raise_for_status()
data = response.json()

print("confidence:", data["confidence"])
for item in data["results"]:
    print(f'{item["similarity"]:.2f}  {item["document"]["title"]}')
    print("   ", item["text"][:150].replace("\n", " "))
```

Set the key in the terminal before running it:

```bash
export KB_API_KEY=YOUR_KEY        # macOS and Linux
set KB_API_KEY=YOUR_KEY           # Windows command prompt
$env:KB_API_KEY="YOUR_KEY"        # Windows PowerShell
python try_search.py
```

### 3.3 With JavaScript (Node.js 18 or newer)

```javascript
const API = "https://ictkb-api.ictkb-api-worker.workers.dev";
const KEY = process.env.KB_API_KEY;

const response = await fetch(`${API}/v1/search`, {
  method: "POST",
  headers: { "X-API-Key": KEY, "Content-Type": "application/json" },
  body: JSON.stringify({ query: "Can I pay my fees in installments?", top_k: 3 }),
});
if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
const data = await response.json();
console.log(data.confidence, data.results.map((r) => r.document.title));
```

Save it as `try_search.mjs` and run `node try_search.mjs`.

## 4. Understanding the response

A search returns this structure (shortened):

```json
{
  "confidence": "high",
  "verification": "strong-match",
  "results": [
    {
      "chunk_id": 412,
      "text": "Paying tuition in installments | Can I pay my fees in installments?\n\nYes. Tuition is paid in three installments: ...",
      "heading_path": "Can I pay my fees in installments?",
      "score": 0.0325,
      "similarity": 0.75,
      "document": {
        "id": "finance-installments",
        "title": "Paying tuition in installments",
        "category": "finance",
        "source_url": null,
        "attachments": [],
        "last_verified": "2026-11-18",
        "freshness_tier": "semester",
        "status": "verified",
        "stale": false
      }
    }
  ]
}
```

### 4.1 The most important field: `confidence`

| Value | Meaning | What your chatbot should do |
|---|---|---|
| `high` | The returned passages contain the answer. | Answer from the passages. |
| `low` | The passages are related but do not state the answer, or the question is outside the university's information (weather, personal data, predictions). | Do not answer from them. Say the information is not available and suggest the relevant office. You may mention the titles of the closest documents. |
| `none` | Nothing matched. | Say the information is not available. |

`confidence` is checked, not just estimated. A very strong match is accepted immediately, a very weak one is rejected, and the cases in between are judged by a small language model that reads the passages and answers yes or no. Checked on the project's 103 test questions, 100% of the questions that should not be answered were correctly marked `low`, and 82% of answerable questions were marked `high`. The rest were marked `low` although an answer existed. For those, your chatbot says it does not know, which is safe but not helpful, so you may show the closest passages with a cautious sentence.

### 4.2 `verification`: how the confidence was decided

| Value | Meaning |
|---|---|
| `strong-match` | The best passage was so similar to the question that no check was needed (always `high`). |
| `weak-match` | The best passage was too different from the question (always `low`). |
| `model` | A language model read the passages and judged them. |
| `fallback` | The model check was unavailable, so a similarity threshold was used. |
| `similarity` | You turned verification off with `"verify": false`. |
| `none` | No results. |

### 4.3 Each result

| Field | Meaning |
|---|---|
| `text` | The passage. It begins with the document title and the heading, then the content. Give this text to your language model. |
| `heading_path` | The section of the document, for example "Fees > Installments". Most headings are phrased as questions. |
| `similarity` | Cosine similarity between the question and the passage, 0 to 1. Useful for debugging; do not use it to decide whether to answer (use `confidence`). |
| `score` | Internal ranking score. Results are sorted by it; ignore the value. |
| `document.id` | Stable identifier of the document. Use it to cite, cache or open the whole document. |
| `document.title` | Human-readable title for citations. |
| `document.category` | One of the 13 categories (section 9.4). |
| `document.source_url` | The web page the information came from, or `null`. |
| `document.attachments` | Original files (PDF, images) with `description` and a download `url`. Show them to the student when relevant. |
| `document.last_verified` | The date a person last checked the information. Show it for fees, deadlines and timetables. |
| `document.freshness_tier` | How often the document must be re-checked: `realtime` (1 day), `daily` (7), `semester` (120), `static` (365). |
| `document.stale` | `true` when the document is past its check date. Warn the student that it may be out of date. |

Several results can come from the same document. They are different passages of it, ordered by relevance.

## 5. Building a chatbot step by step

A retrieval chatbot repeats four steps for every question: retrieve, check, build the prompt, answer.

```
student question
      |
      v
1. retrieve  --> POST /v1/search
      |
2. check     --> confidence is "high"?   no --> "I do not have that information; ask the Admissions office"
      | yes
3. prompt    --> instructions + passages + question
      |
4. answer    --> your language model --> reply with sources
```

### 5.1 Step 1: a small client

Create `kb.py`:

```python
import os
import time
import requests

API = os.environ.get("KB_API_URL", "https://ictkb-api.ictkb-api-worker.workers.dev")
KEY = os.environ["KB_API_KEY"]
HEADERS = {"X-API-Key": KEY}


def _post(path, payload, tries=4):
    """POST with retries for rate limits (429) and temporary server errors (5xx)."""
    for attempt in range(tries):
        r = requests.post(f"{API}{path}", headers=HEADERS, json=payload, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            wait = int(r.headers.get("Retry-After", 2 ** attempt))
            time.sleep(min(wait, 30))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("The knowledge base is not responding. Try again later.")


def search(query, top_k=5, **filters):
    """filters: category=..., program_level='bachelor'|'masters'|'phd', language='en'|'fr'."""
    body = {"query": query, "top_k": top_k}
    if filters:
        body["filters"] = filters
    return _post("/v1/search", body)


def feedback(verdict, query=None, document_id=None, chunk_id=None, note=None):
    """verdict: 'wrong' | 'missing' | 'outdated' | 'helpful'."""
    return _post("/v1/feedback", {"verdict": verdict, "query": query, "document_id": document_id,
                                  "chunk_id": chunk_id, "note": note})
```

### 5.2 Step 2: decide whether to answer

```python
NOT_AVAILABLE = ("I do not have that information yet. Please ask the Admissions office "
                 "(admissions@ictuniversity.edu.cm) or the office concerned.")


def retrieve(question):
    found = kb.search(question, top_k=5)
    if found["confidence"] != "high":
        return None, found          # nothing reliable: do not let the model guess
    return found["results"], found
```

Do not skip this check. Without it a language model will often invent a confident answer to a question the data does not cover, such as a personal fee balance or the date of an event that has not been announced.

### 5.3 Step 3: build the prompt

```python
SYSTEM = """You are the ICT University student assistant.
Answer only from the SOURCES below. If the sources do not state the answer, say so and suggest asking
the relevant office. Never guess amounts, dates, names or deadlines.
Reply in the language of the question (English or French). Keep the answer short and clear.
Cite sources with their number, for example [1].
If a source is marked "may be out of date", tell the student to confirm with the office."""


def group_by_document(results):
    """Several passages can come from one document; give each document one number."""
    groups = {}
    for r in results:
        d = r["document"]
        groups.setdefault(d["id"], {"doc": d, "texts": []})["texts"].append(r["text"])
    return list(groups.values())


def build_prompt(question, results):
    blocks = []
    for i, g in enumerate(group_by_document(results), 1):
        d = g["doc"]
        flag = " (may be out of date)" if d["stale"] else ""
        blocks.append(f'[{i}] {d["title"]}, checked {d["last_verified"]}{flag}\n' + "\n\n".join(g["texts"]))
    return "SOURCES\n\n" + "\n\n".join(blocks) + f"\n\nQUESTION\n{question}"
```

### 5.4 Step 4: ask your language model and add the sources

Your program calls the model you have been given access to. The function below is the only part you must adapt:

```python
def call_model(system, user):
    """Send `system` and `user` to your language model and return its text reply.
    Replace the body with the call for the service you use."""
    raise NotImplementedError("connect your language model here")


def answer(question):
    results, found = retrieve(question)
    if results is None:
        return NOT_AVAILABLE
    reply = call_model(SYSTEM, build_prompt(question, results))
    sources = []
    for i, g in enumerate(group_by_document(results), 1):
        d = g["doc"]
        line = f'[{i}] {d["title"]}'
        if d["source_url"]:
            line += f' ({d["source_url"]})'
        sources.append(line)
        for a in d["attachments"]:
            if a.get("url"):
                sources.append(f'    File: {a["description"][:80]} {a["url"]}')
    return reply + "\n\nSources:\n" + "\n".join(sources)
```

A complete command-line chatbot:

```python
import kb

if __name__ == "__main__":
    print("ICT University assistant. Type 'quit' to stop.")
    while True:
        q = input("> ").strip()
        if q.lower() in {"quit", "exit"}:
            break
        if q:
            print(answer(q))
```

To test everything before connecting a model, make `call_model` return `user` (it prints the prompt your model would receive). When the prompt looks right, connect the model.

### 5.5 Handling follow-up questions

A student may write "And for Masters?" after asking about fees. The search endpoint has no memory, so rewrite the question into a standalone one before searching. Ask your model:

```python
CONDENSE = ("Rewrite the last question so that it can be understood without the conversation. "
            "Return only the rewritten question, in the same language.")


def standalone(history, question):
    if not history:
        return question
    turns = "\n".join(f"{role}: {text}" for role, text in history[-6:])
    return call_model(CONDENSE, f"{turns}\nLast question: {question}").strip()
```

Then call `retrieve(standalone(history, question))`.

### 5.6 Using filters

Filters narrow the search. They are optional and rarely needed.

```python
kb.search("entry requirements", category="admissions", program_level="masters")
```

Use `program_level` when the student has told you their level. Avoid the `language` filter: most documents are in English and a French question is answered correctly from them, so filtering by `fr` would hide most results.

### 5.7 Reporting wrong answers

Give the student a way to flag a bad answer and send it back; the maintainers read these reports and fix the documents.

```python
kb.feedback("wrong", query=question, document_id=results[0]["document"]["id"], note="The date is outdated")
```

### 5.8 A web or mobile front end

Do not call the API directly from a web page or a phone app, because the key would be visible to anyone who opens the page. Put a small server between them. A minimal Node.js proxy:

```javascript
// server.mjs: npm install express, then KB_API_KEY=... node server.mjs
import express from "express";
const app = express();
app.use(express.json());

app.post("/api/search", async (req, res) => {
  const r = await fetch("https://ictkb-api.ictkb-api-worker.workers.dev/v1/search", {
    method: "POST",
    headers: { "X-API-Key": process.env.KB_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ query: String(req.body.query ?? "").slice(0, 500), top_k: 5 }),
  });
  res.status(r.status).json(await r.json());
});

app.listen(3000);
```

Your front end calls `/api/search` on your own server.

## 6. The other endpoints

### 6.1 Read one document in full

```bash
curl https://ictkb-api.ictkb-api-worker.workers.dev/v1/documents/finance-installments -H "X-API-Key: YOUR_KEY"
```

Returns the document's metadata and all its passages in order (`chunks`). Use it when you want to show the complete page behind an answer.

### 6.2 List documents

```bash
curl "https://ictkb-api.ictkb-api-worker.workers.dev/v1/documents?category=finance&limit=20&offset=0" -H "X-API-Key: YOUR_KEY"
```

### 6.3 List categories with their document counts

```bash
curl https://ictkb-api.ictkb-api-worker.workers.dev/v1/categories -H "X-API-Key: YOUR_KEY"
```

Useful for building a menu such as "Choose a topic".

### 6.4 Freshness of the data

```bash
curl https://ictkb-api.ictkb-api-worker.workers.dev/v1/freshness -H "X-API-Key: YOUR_KEY"
```

Returns, for each category, the number of documents, how many are past their check date, and the time of the last change.

### 6.5 Send feedback

```bash
curl -X POST https://ictkb-api.ictkb-api-worker.workers.dev/v1/feedback \
  -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"verdict": "outdated", "query": "when does registration close", "document_id": "procedures-course-registration", "note": "New deadline announced"}'
```

## 7. Limits, errors and good practice

**Limits.** 60 requests per minute per key. A request over the limit receives status 429 and a `Retry-After` header. Questions are 2 to 1000 characters. `top_k` is at most 20; 3 to 5 passages are enough for a chatbot. A search normally answers in about one second; when the model check is needed it can take a few seconds. Identical questions repeated within five minutes are answered instantly from a cache.

**Errors.** Errors return a JSON body such as `{"detail": "Invalid or revoked API key"}`.

| Status | Meaning | What to do |
|---|---|---|
| 401 | Missing, wrong or revoked key | Check the `X-API-Key` header. Ask the maintainers if the key was revoked. |
| 404 | Unknown document or address | Check the spelling of the document id. |
| 422 | Invalid request, for example a query shorter than 2 characters | Correct the request body. |
| 429 | Too many requests | Wait for `Retry-After` seconds and retry. |
| 500 or 503 | Temporary fault in the service or one of its providers | Retry after a few seconds; the client in section 5.1 does this automatically. |

**Good practice.**

1. Always check `confidence` before answering. This one rule prevents most wrong answers.
2. Pass only the returned passages to your model and instruct it to answer only from them.
3. Show the document titles and links as sources, and show `last_verified` for fees, deadlines, timetables, the canteen menu and announcements.
4. Warn when `stale` is true.
5. Send one search per student question; cache answers in your own application when many students ask the same thing.
6. Do not send personal data (names, matricule numbers, balances) to the API. It stores only the question you send in feedback reports.
7. Answer in the language of the question.
8. Tell students that the assistant can be wrong and that the offices are the final authority.

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `401 Missing X-API-Key header` | The header is absent or misspelled | Send `X-API-Key: YOUR_KEY` exactly. |
| `401 Invalid or revoked API key` | Wrong key, extra space, or the key was switched off | Copy the key again without spaces or quotes; ask a maintainer. |
| `KeyError: 'KB_API_KEY'` in Python | The environment variable is not set in this terminal | Set it in the same terminal where you run the program. |
| Every answer is "I do not have that information" | The questions concern topics not yet in the data | Try a known topic, for example "How do I request a transcript?" Check the list in section 1. |
| An answer is missing details that the office knows | The data has a gap | Send feedback with verdict `missing`; the maintainers add it. |
| The answer is out of date | The document was not re-checked | Look at `last_verified`; send feedback with verdict `outdated`. |
| Slow first request | The service wakes up or the model check runs | Normal; later identical questions are instant. Set a client timeout of 60 seconds. |
| `429` errors while testing | More than 60 requests in a minute | Slow down, or cache answers. |
| French question returns English text | Most documents are written in English | Expected. Instruct your model to reply in the student's language. |

If a problem persists, open an issue in the repository with the question you asked, the `confidence` and `verification` values returned, and the time.

## 9. Reference: every endpoint, field and value

### 9.1 Authentication

Header `X-API-Key: <your key>` on every request except `GET /v1/health`.

### 9.2 `POST /v1/search`

Request body:

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string, 2 to 1000 characters | yes | The student's question, in English or French. |
| `top_k` | integer, 1 to 20 | no (5) | Number of passages to return. |
| `filters.category` | string | no | One of the categories in 9.4. |
| `filters.program_level` | `bachelor`, `masters` or `phd` | no | Documents for that level and documents for all levels. |
| `filters.language` | `en` or `fr` | no | Language of the document (see 5.6). |
| `verify` | boolean | no (true) | `false` skips the model check and decides `confidence` by similarity only (faster, less accurate). |

Response: `confidence`, `verification`, `results[]` as described in section 4.

### 9.3 Other endpoints

| Method and path | Description |
|---|---|
| `GET /v1/health` | No key. Returns `status`, `version`, `environment`, `documents`, `chunks`, `embedding_model`. |
| `GET /v1/documents/{id}` | One document with all passages. 404 if unknown. |
| `GET /v1/documents?category=&limit=&offset=` | List of documents (`id`, `title`, `category`, `freshness_tier`, `last_verified`). `limit` up to 200. |
| `GET /v1/categories` | The categories with `id`, `label`, `description`, `documents`. |
| `GET /v1/freshness` | Per category: `documents`, `stale`, `last_update`. |
| `POST /v1/feedback` | Body: `verdict` (required), `query`, `chunk_id`, `document_id`, `note`. Returns `{"id": n}` with status 201. |

### 9.4 Categories

`about`, `admissions`, `programs`, `procedures`, `finance`, `erp`, `campus`, `transport`, `canteen`, `timetables`, `people`, `student-life`, `announcements`.

### 9.5 Identifiers of live posts

Posts from the official WhatsApp groups have document ids that begin with `canteen-menu-` (one per day), `announcements-current-note-`, `student-life-update-` or `transport-update-`, followed by the date. They disappear automatically after their last valid day (the menu after one day, other posts after 7 to 14 days). Menu posts read from a photograph end with the line "Read automatically from a photo; check the photo for exact details." Show that line to the student.

## 10. For maintainers: issuing and revoking keys

Requires the admin token, which is held by the project maintainers and is never shared with chatbot developers.

Create a key:

```bash
curl -X POST https://ictkb-api.ictkb-api-worker.workers.dev/v1/admin/keys \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"owner": "student name or project", "rate_limit_per_min": 60}'
```

The response contains `id` and `api_key`; send the key to the student privately. Only a hash is stored, so a lost key cannot be recovered and must be replaced.

Revoke a key:

```bash
curl -X DELETE https://ictkb-api.ictkb-api-worker.workers.dev/v1/admin/keys/KEY_ID -H "X-Admin-Token: $ADMIN_TOKEN"
```

Revocation takes effect within one minute.
