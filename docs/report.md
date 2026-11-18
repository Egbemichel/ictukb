# Design and Implementation of a Retrieval Knowledge Base for ICT University Chatbots

Course: CSC 4121 Artificial Intelligence, Fall 2026
Institution: ICT University, Yaoundé, Cameroon
Project type: Group project, shared knowledge base
Authors: [student names and matricule numbers]
Supervisor: [course instructor]
Date: 18 November 2026
Repository: https://github.com/Egbemichel/ictukb

---

## Abstract

Students and staff of ICT University must find answers to practical questions (fees, registration, timetables, procedures) scattered across a website, notices, policy documents and an administrative system. Chatbots can help, but a chatbot is only as reliable as the data it reads from. This report describes the design, construction and evaluation of a shared knowledge base from which individual student chatbots retrieve official information.

The system stores curated documents, website pages and short-lived announcements as passages in a PostgreSQL database with vector search. Retrieval combines semantic similarity and keyword matching, and a verification step decides whether the retrieved passages actually answer the question. A public interface, deployed on free infrastructure, lets any chatbot query the data with an access key. Information is classified by how often it changes, every document records its source and the person who verified it, and conflicts between sources are resolved in favour of the most recent official document. Private information is excluded by design.

At the time of writing the database holds 80 documents divided into 679 passages. A set of 103 test questions was used to measure quality. For the 98 answerable questions, 63 (64.3%) had a corresponding document in the database. For these, the correct document appeared among the five best results for 88.9% of questions and for all 19 questions on the highest-priority topics, and the mean reciprocal rank was 86.6%. All five questions that the database should not answer were correctly refused. The report concludes that the architecture is sound and inexpensive to operate, and that the main remaining task is collecting the missing information from the university's offices.

Keywords: knowledge base, information retrieval, vector search, hybrid retrieval, retrieval-augmented generation, university information systems, data quality.

---

## Table of contents

1. Introduction
2. Literature review
3. Methodology
4. System design
5. Implementation
6. Results and discussion
7. Conclusion and recommendations

References

Appendix A: Document metadata schema
Appendix B: Interface summary
Appendix C: Test question format
Appendix D: Repository layout

---

## Chapter 1. Introduction

### 1.1 Background

A university generates a large volume of practical information. Applicants need to know how to apply and what documents to provide. Enrolled students need the dates of registration, the amounts and instalments of tuition, the procedure to request a transcript or to resit an examination, the timetable of their classes and the location of an office. The sources of this information are varied: pages of the university website, signed notices, policy documents, forms, messages in official messaging groups and the screens of the university's administrative system. No single place answers a question such as "Until when can I register for courses and what happens after that date?", and the answer may be spread across a communiqué and a notice from the finance office.

Conversational assistants, commonly called chatbots, are a natural interface for such questions. A chatbot that answers from general knowledge, however, will state plausible but wrong facts about a particular institution. The established remedy is to separate the knowledge from the conversation: the assistant first retrieves relevant passages from a trusted store and then composes its reply from them. This pattern is known as retrieval-augmented generation (Lewis et al., 2020). Its quality depends first on the store, since a response cannot be more accurate than the passages it is built from.

For the course CSC 4121 (Artificial Intelligence) each student develops an individual chatbot for the university. The class decided that all chatbots would read from one shared knowledge base rather than each student collecting data separately. This report documents that knowledge base.

### 1.2 Problem statement

Three problems motivated the project.

1. **Fragmentation.** Official information is spread over several media and formats, some of them images or scanned documents that cannot be searched.
2. **Change.** Some facts change each semester (fees, dates, timetables) and others each day (the canteen menu, announcements). A static document collection becomes wrong without maintenance.
3. **Trust.** A student who receives a wrong deadline or amount from a chatbot may suffer a financial penalty. The system must therefore know which facts are verified, where they come from, how recent they are, and when it does not know the answer.

### 1.3 Objectives

The general objective was to design, build, deploy and evaluate a shared, open and maintainable knowledge base about ICT University from which student chatbots can retrieve accurate, current and attributable information.

The specific objectives were:

1. to define the information the knowledge base must contain and to collect it from official sources;
2. to design a data model that records the source, date, owner and verification status of every document;
3. to implement a pipeline that converts documents, web pages, spreadsheets and messages into searchable passages;
4. to implement retrieval that answers questions in English and French and that recognises questions it cannot answer;
5. to provide a public interface with access control, and to deploy it at no cost;
6. to keep the data current through scheduled and near real-time updates;
7. to measure retrieval quality against a fixed set of test questions.

### 1.4 Research questions

RQ1. Can a hybrid retrieval design return the correct official document among the first five results for most questions on a small institutional corpus?

RQ2. Can the system reliably distinguish questions that the corpus answers from questions that it does not?

RQ3. Can the system be built, deployed and kept up to date using only free services?

### 1.5 Scope and delimitations

The knowledge base covers thirteen categories of information: the university, admissions, programs, academic procedures, finance, the administrative system (ERP), the campus, transport, the canteen, timetables, people, student life and announcements. The undergraduate English-language timetable of the Fall 2026 semester is included; other timetables are not. The system stores no personal data. It does not generate answers: composing the reply is the task of each chatbot. The report does not evaluate any chatbot, only the knowledge base from which chatbots read.

### 1.6 Significance

The project provides the class with a single reliable source of institutional facts, reduces duplicated effort, and shows a complete method, from collection to deployment, that other departments could reuse. The decision to record provenance and freshness for every fact makes errors traceable and correctable.

### 1.7 Definitions of terms

Passage (chunk): a short piece of a document, a few sentences or a table section, stored and retrieved as a unit.
Embedding: a list of numbers (here 1,024) representing the meaning of a text, such that texts with similar meaning have similar vectors.
Retrieval: finding the passages most relevant to a question.
Freshness tier: the maximum time allowed between two verifications of a document.
Verified document: a document whose content a named person has checked against an official source.

### 1.8 Organisation of the report

Chapter 2 reviews the literature on retrieval and on knowledge quality. Chapter 3 presents the methodology. Chapter 4 describes the design of the system and Chapter 5 its implementation. Chapter 6 reports and discusses the results. Chapter 7 concludes and makes recommendations.

---

## Chapter 2. Literature review

### 2.1 Question answering over institutional knowledge

Answering questions from a bounded, authoritative collection of documents differs from open-domain question answering. The collection is small, its authority is known and its errors are costly. Typical university assistants therefore rely on retrieval from the institution's own material rather than on general knowledge. The central design questions are how to represent documents, how to retrieve, and how to keep the content correct over time.

### 2.2 Lexical and dense retrieval

Classical retrieval ranks documents by the words they share with the query. The probabilistic ranking function BM25 weights each word by its rarity and by the length of the document and has remained a strong baseline for decades (Robertson and Zaragoza, 2009; Manning, Raghavan and Schütze, 2008). Its weakness is vocabulary mismatch: a question that says "pay in instalments" does not match a passage that says "tuition may be settled in parts".

Dense retrieval addresses this limitation by mapping questions and passages to vectors with a trained encoder and ranking by vector similarity (Karpukhin et al., 2020). Sentence-level encoders trained on pairs of related sentences produce embeddings suited to comparison by cosine similarity (Reimers and Gurevych, 2019). Multilingual encoders map several languages to the same space, so that a French question can retrieve an English passage. This property is valuable at a bilingual university.

Dense retrieval has its own weakness: it may retrieve passages that are topically close but do not contain the specific fact asked for, and it handles rare identifiers (course codes, names) less well than lexical methods. Combining both signals is a common remedy.

### 2.3 Approximate nearest-neighbour search and hybrid fusion

Comparing a query with every stored vector does not scale, so vector databases use approximate nearest-neighbour indexes. The hierarchical navigable small world graph (Malkov and Yashunin, 2020) offers high recall at low latency and is available in the pgvector extension for PostgreSQL (Kane, 2021). Keeping vectors in the same relational database as the metadata allows filtering by category, level or validity date in a single query.

Two ranked lists, one lexical and one dense, can be merged by reciprocal rank fusion, which scores each item by the sum of the reciprocals of its ranks in the lists (Cormack, Clarke and Büttcher, 2009). The method needs no tuning of score scales and was shown to outperform several more elaborate fusion techniques.

### 2.4 Retrieval-augmented generation and its failure modes

In retrieval-augmented generation the retrieved passages are supplied to a language model together with the question (Lewis et al., 2020). Two failure modes are relevant here. First, if the retrieval returns passages that do not contain the answer, the model may still produce a confident reply. Second, if the passages are outdated or contradictory, the reply inherits the error. Both failures are properties of the knowledge store and its retrieval interface, which is why this project invests in verification of retrieved passages and in provenance of documents rather than in the generation step.

### 2.5 Chunking

Documents are divided into passages before indexing. Passages that are too long dilute the meaning captured by an embedding and waste the model's context; passages that are too short lose context. Splitting along the structure of the document (headings, paragraphs, table rows) and prefixing each passage with its title and heading keeps it understandable when retrieved alone. Tables require special treatment: splitting by rows and repeating the header row keeps each piece interpretable.

### 2.6 Knowledge freshness and provenance

Information quality depends on currency and attribution. Documents about fees and timetables lose validity each semester, while an announcement loses it in days. Assigning each document an expected lifetime, recording the date of the last verification and exposing both to the consumer allows a system to warn when information may be out of date. Recording the source and the verifier allows an error to be traced and corrected, and a stated rule for resolving conflicts (here, the most recent signed official document) makes the outcome predictable.

### 2.7 Evaluation of retrieval

Retrieval is commonly evaluated with a fixed set of questions with known relevant documents. The measure hit at k records whether a relevant document appears among the first k results. The mean reciprocal rank averages the reciprocal of the rank of the first relevant result (Voorhees, 1999). For a system that must also decline to answer, the share of unanswerable questions that are correctly refused is an additional measure. Because a test set can be prepared before the content exists, the proportion of questions for which a relevant document is present must be reported separately, otherwise missing content is confused with retrieval errors.

### 2.8 The knowledge base in an agent architecture

In the vocabulary of the course, a chatbot is an agent whose percepts are the student's messages and whose actions are replies. A goal-based agent that must give correct answers requires a knowledge component that is accurate, current and queryable (Russell and Norvig, 2021). The knowledge base described in this report is that component, kept outside the agent so that it can be shared and updated independently.

### 2.9 Positioning of the project

The literature provides the retrieval techniques; the contribution of this project is their integration for a specific institution under real constraints: a small, bilingual, partly scanned corpus, facts with different rates of change, no budget, and a requirement that the result be open to a whole class. The following chapters describe how these constraints shaped the method.

---

## Chapter 3. Methodology

### 3.1 Research design

The project followed an iterative design-and-build approach. Each iteration consisted of collecting a batch of sources, converting them to documents, indexing them, measuring retrieval quality against the fixed question set, and correcting the data or the system according to the failures observed. The question set was written before the content existed so that progress could be measured objectively. Quantitative results from each iteration are given in Chapter 6.

### 3.2 Requirements elicitation

The requirements came from the course brief and from the questions students ask. The stakeholders were the students building chatbots, the students and staff asking questions, and the administration. The following requirements were identified.

Functional requirements:
- store information of thirteen categories, including documents, images and tabular data;
- answer questions in English and French;
- return the source and the date of verification with every result;
- recognise questions that cannot be answered;
- accept near real-time updates for fast-changing information;
- provide access to any chatbot through a documented interface with access keys.

Non-functional requirements:
- open source, with protection against unauthorised changes;
- no sensitive data;
- operation at no financial cost;
- maintainability by a changing team of students.

### 3.3 Sources and collection procedure

Information was collected from the following sources, in decreasing order of authority.

| Source | Content | Method |
|---|---|---|
| Signed notices, policies and letters | Academic regulations, registration dates, fee control, bank accounts | Files supplied by the team; scanned pages read and transcribed |
| Administrative system (ERP) user manual | Procedures, grading scale, fees, resits, transcripts, complaints | Read from the official manual inside the system; no personal data used |
| University website | Programs, admission requirements, faculties, calendar, news | Public interface of the website, read daily |
| Timetable (PDF) | Lectures of the Fall 2026 semester | Table extraction, then generation of per-day tables and per-program lists |
| Messages of official groups | Canteen menu, announcements, student-life updates | Messages of administrators of four official groups, received automatically |
| Spreadsheets | Directories, canteen, transport | Templates prepared; to be filled by the offices |

Seven collection rules governed the work: every item records its source, date and collector; original files are kept and not retyped; files are named by category, topic and date; verbal information is confirmed in writing; a conflict between sources is resolved in favour of the most recent signed official document and recorded in the document; only official contact details are stored; and no secret or personal data enters the repository. One unofficial compiled report was supplied during the project; because it did not originate from the university, it was excluded from verification.

To organise the collection, a catalogue of 85 documents was defined in advance. For each document the catalogue lists the questions it must answer, the files to obtain, the responsible office and a priority (P0 for the core service, P1 for completeness, P2 for coverage). From the catalogue the project generated a stub for each document, spreadsheet templates and a checklist of about 80 files to obtain.

### 3.4 Verification and governance

Each document has a status: draft, verified or deprecated. Only verified documents are visible in production. A document may be verified only when it contains no unresolved placeholder, names a person who checked it, and has an assigned owner. A validation program enforces these rules and also rejects e-mail addresses outside the official domains and malformed metadata.

Freshness tiers define the maximum age of the last verification: one day for real-time information, seven days for daily information, 120 days for semester information and 365 days for static information. Documents beyond their limit are reported as stale, and an issue is opened for the owner.

### 3.5 Privacy and ethics

The knowledge base is intended to be open, so the following measures were applied.

- No personal data is stored. Questions about an individual's grades or balance are deliberately unanswerable.
- Official bank account numbers, although published to students by the university, are kept in a private folder that is excluded from the public repository and indexed only from the maintainer's machine.
- The website is read through its public interface and its stated crawl delay of 20 seconds is respected.
- The messages of the official groups are read only with the number of a group member, only messages from group administrators are used, and phone numbers, mentions and unofficial e-mail addresses are removed before anything is stored. Group administrators are to be informed that the number is a member.
- Access to the interface requires a key that can be revoked.

### 3.6 Data model

Each curated document is a Markdown file with structured metadata (Appendix A): identifier, title, category, level, language, source type and address, attachments, validity dates, freshness tier, status, date of last verification, verifier, owner, collector and a note on conflicts. The body is organised under headings phrased as the questions a student would ask. Binary files (PDF, images) are stored in a media service and never in the repository; their extracted text, reviewed in the repository, is indexed together with a human-written description.

### 3.7 Processing pipeline

For each document the pipeline (1) validates the metadata against a schema, (2) divides the body into passages along headings and paragraphs, each prefixed with the document title and heading, (3) converts each passage to an embedding, and (4) writes the document and its passages to the database. A hash of the content allows unchanged documents to be skipped. Documents that disappear from their source are removed. The embedding model is recorded in the database so that vectors of different models are never mixed.

### 3.8 Retrieval and answer verification

Retrieval proceeds in three stages. The question is converted to an embedding. Two candidate lists of 40 passages are produced: the nearest passages by cosine similarity, and the passages matching the informative words of the question by full-text search. The lists are merged by reciprocal rank fusion with the constant 60, and the best results are returned with their document metadata. Filters by category, level and language apply to both lists, and documents past their validity date are never returned.

The system then decides whether the results answer the question. If the best similarity is at least 0.70, the answer is accepted without further checking; if it is below 0.45, it is rejected; between these values a small language model reads the first three passages and answers yes or no to the question "do the passages contain the answer?". The interface returns the outcome as a confidence value (high, low or none). The thresholds were derived from the observed distribution of similarities of answerable and unanswerable test questions (section 6.3).

### 3.9 Evaluation design

A set of 103 test questions was written before the content was collected. It contains 98 answerable questions, of which 6 are French or misspelled variants and 4 require two documents, and 5 questions that the database must not answer (for example a private telephone number, a personal balance, a prediction). Each answerable question lists the documents that answer it. The measures are:

- coverage: the share of answerable questions whose expected document exists in the database;
- hit at 5: for covered questions, the share for which an expected document (all of them for two-document questions) appears among the first five results;
- mean reciprocal rank (MRR);
- the share of retrieved answerable questions that receive high confidence;
- no-answer correctness: the share of unanswerable questions marked low or none.

Hit at 5 and MRR are computed only on covered questions, so that missing content is not counted as a retrieval error. Targets were 85% overall hit at 5 and 95% on the highest-priority (P0) questions.

### 3.10 Tools and environment

The pipeline is written in Python. The database is PostgreSQL with the pgvector extension, hosted by Neon. Embeddings and the verification model are provided by Cloudflare Workers AI. Files are stored in Cloudinary. The public interface runs on Cloudflare Workers. Automation uses GitHub Actions. The messaging connector is a Node.js program hosted on a free web service. All services were used within their free allowances.

---

## Chapter 4. System design

### 4.1 Architecture

```
                                     chatbots of the students
                                                |
                                      HTTPS, access key
                                                v
                              +--------------------------------+
                              | Cloudflare Worker (public API) |
                              | search, documents, feedback    |
                              | embeddings, answer verification|
                              +----+---------------------+-----+
                                   |                     ^
                              reads/writes          admin posts
                                   v                     |
 +---------------------+    +--------------+     +-------------------+
 | Python pipeline     |--->| Neon         |     | WhatsApp listener |
 | validate, chunk,    |    | PostgreSQL + |     | official groups   |
 | embed, index        |    | pgvector     |     +-------------------+
 +----------+----------+    +--------------+
            ^
   content files (Git), website, spreadsheets, uploaded files
```

The design separates three concerns: curation (files in a Git repository and the sources that feed them), storage and retrieval (the database and the public interface) and consumption (the chatbots).

### 4.2 Storage design

The database has two main tables. A document row holds the metadata of Appendix A and an origin (curated files, website, spreadsheet, short-lived post or private file) so that each ingestion path removes only the documents it created. A passage row holds the text, the heading path, the source (body, attachment or sheet), the embedding and a full-text vector generated from the text. Supporting tables hold access keys (stored as hashes), feedback reports, ingestion runs, a record of the embedding model and the state of the messaging connector.

### 4.3 Index design

Embeddings are indexed with a hierarchical navigable small world graph using cosine distance. The full-text vectors are indexed with an inverted index and use a language-neutral configuration because the corpus is bilingual. A composite index on category, status and freshness tier supports filtering.

### 4.4 Interface design

The interface is a small set of HTTP endpoints (Appendix B). The principal endpoint accepts a question, an optional number of results and optional filters, and returns the passages with confidence, verification method and, for each passage, the document identifier, title, category, source address, attachments, date of last verification, freshness tier and a stale flag. Further endpoints list categories, report freshness, return a full document, accept feedback reports and report health. An administrative group of endpoints, protected by a separate token, creates and revokes access keys, publishes and deletes short-lived posts, and stores the connector state. There is no endpoint that edits curated content: changes to curated documents happen only through the repository and the pipeline.

Access keys are random, shown once and stored only as hashes. Each key has a per-minute request limit. Cross-origin requests are allowed, but the documentation advises that keys be kept on a server.

### 4.5 Ingestion design

Four connectors feed the same tables:

1. curated files, validated and indexed after review;
2. the website, read daily through its public content interface, with a change record for each page;
3. spreadsheets, shared as read-only, rendered into self-contained text rows and grouped into one document per group (for example per program and semester);
4. short-lived posts, created from messages, which carry a validity period and are deleted automatically when it ends.

An intake command registers collected files: it uploads the original, extracts its text, and attaches it to the matching document, creating a draft when none exists.

### 4.6 Live information

The canteen menu, bus information and announcements are published by administrators in messaging groups. A connector linked to a member number receives those messages, keeps only messages written by group administrators, removes personal data, reads text from menu photographs with a vision model, and publishes each message as a post. Several menu messages of one day are merged into one menu; a deleted or edited message updates the post. The session of the connector is stored in the database so that the program can run on a host without a disk and restart without relinking.

### 4.7 Deployment

The public interface runs as a Cloudflare Worker, which is free, always available and reads the database over HTTP. The connector runs as a free web service that is contacted every five minutes by a scheduled task of the Worker so that it does not sleep. The pipeline runs from a maintainer's machine and from scheduled GitHub Actions jobs: a live job every 15 minutes, a daily job for the website and sheets, and a deployment job on every change of the main branch. These jobs are switched on by a repository variable after the required secrets are set.

### 4.8 Security

The repository is public, so secrets never enter it; a scanner checks every change. Administrative operations require a token held by the maintainers. The main branch is protected by review rules and required checks. The connector's WhatsApp session is a credential and is kept in the database, not in the repository.

### 4.9 Design decisions and trade-offs

Git as the source of truth. Curated content lives in Markdown files so that changes are reviewed, attributed and reversible. The cost is that every change goes through a pull request, which is acceptable for slowly changing facts.

Separate paths for volatile data. Committing a menu to Git daily would be impractical, so volatile data enters the database directly and expires by itself.

A JavaScript interface next to the Python code. The free Cloudflare platform cannot run the Python database driver, so the public interface was written for the Worker runtime. The Python pipeline remains the reference for indexing and for the evaluation, and both share the same database.

A private overlay for sensitive but useful data. Some facts are valuable to chatbots but unsuitable for a public repository. A separate, ignored folder is indexed from one machine under its own origin so that the public automation never deletes it.

Verification by threshold and model. A similarity threshold alone could not separate answerable from unanswerable questions (section 6.3), so a small model checks the ambiguous cases. Very strong and very weak matches skip the model, which limits cost and delay.

---

## Chapter 5. Implementation

### 5.1 Repository and modules

The repository (Appendix D) contains the curated content, the schema and catalogue, the Python package, the Worker, the messaging connector, the test questions, the workflow definitions and the documentation. The Python package of about 3,000 lines includes modules for configuration, database access, content validation, chunking, embedding providers, indexing, search, evaluation, the website and spreadsheet connectors, file intake, document parsers, freshness reporting, access keys and a command-line interface. The Worker is about 500 lines, the connector about 600 lines and the automated tests about 480 lines of Python plus 15 tests in JavaScript.

### 5.2 Content validation

Metadata is validated with a JSON Schema. Further rules check that the file name equals the identifier, that the folder matches the category, that referenced documents exist, that dates are consistent, that e-mail addresses belong to the official domains, that verified documents contain no placeholder and name their verifier, and that attachment text files exist. Phone numbers produce a warning for reviewers. The validation runs on every change.

### 5.3 Chunking

Markdown is split at headings, and each section into paragraphs packed up to about 380 tokens. Each passage begins with the document title and the heading path. Tables are split by rows and the header is repeated in each piece. The resulting passages in the database average about 110 tokens, reflecting that most documents are organised as short question-and-answer sections.

### 5.4 Embeddings

The first implementation used a hosted multilingual embedding service with 1,024 dimensions. After the evaluation had been repeated several times, the free key reached its monthly limit of 1,000 calls and the public interface stopped answering new questions. The embedding model was therefore replaced by a free multilingual model of the same dimension provided by the deployment platform. The Worker computes both query and document embeddings, and the Python pipeline requests document embeddings from the Worker, so that every vector in the database comes from one model. The 679 passages were re-embedded in one command, and thresholds were recalibrated (section 6.3). The recorded model name prevents accidental mixing.

### 5.5 Indexer and search

The indexer computes a hash of the title and passages; unchanged documents are skipped and only their metadata is refreshed, while changed documents have their passages replaced. After each run, documents of the same origin that no longer exist at the source are deleted, with a safeguard that refuses to delete everything when a source returns nothing. Search is a single SQL statement that computes the two candidate lists, fuses them and returns the best passages with their document metadata, using positional parameters so that the Python and JavaScript implementations share the same query.

### 5.6 Connectors and file processing

The website connector reads pages and recent news through the site's structured content interface, converts HTML to Markdown, removes repeated blocks and classifies each page into a category by rules on its address. The spreadsheet connector converts rows to self-contained text lines and groups them. The intake command extracts text from PDF, Word, Excel, CSV and image files. Three problems required special handling:

- scanned documents have no text layer; their pages were read as images and transcribed into the document body, with the scan retained as an attachment;
- one PDF stored text as one word per line, which is repaired by joining the lines;
- the timetable PDF was extracted by table position rather than as plain text, which recovered 85 sessions with course, lecturer, hall, time and audience, from which per-day tables, a list of lecturers per course and the courses of each program and year were generated.

### 5.7 The Worker

The Worker implements the endpoints of Appendix B. It hashes keys with SHA-256, caches key lookups for a minute, limits request rates per key in memory, calls the database over HTTP, computes embeddings, and runs the answer check. Identical questions are cached for five minutes. Administrative endpoints publish and delete posts, create and revoke keys, compute embeddings for the pipeline and store the connector state. Error messages never include connection strings.

### 5.8 The messaging connector

The connector uses an unofficial library for the linked-device protocol. It routes each group to a post type by the group's name, uses only messages written by administrators, redacts personal data, reads photographs with a vision model, merges daily menus, handles edits and deletions, and keeps its session and bookkeeping in the database. It exposes a health address, stops when another instance takes over the session, and flushes its state on shutdown. The use of an unofficial client carries a risk that the number is blocked or that a protocol change interrupts the service; this risk is accepted and documented.

### 5.9 Automation and testing

Workflows validate every change (style checks, schema validation, a scan for secrets, and the test suites, including database tests against a temporary pgvector instance), evaluate retrieval, ingest data on a schedule, report stale documents and deploy. There are 38 automated tests: 23 for the Python code (8 of which require a database), 4 for the Worker and 11 for the connector. They cover validation rules, chunking, the keyword query, connectors, intake, indexing, pruning, search filters, key authentication and rate limiting, posts and their expiry, redaction, routing, menu merging, edits, deletions and the session store.

### 5.10 Problems encountered and their resolution

| Problem | Cause | Resolution |
|---|---|---|
| Scanned documents unsearchable | No text layer | Pages read as images and transcribed; scan attached |
| Timetable text garbled | Table layout lost in plain extraction | Extraction by table position and regeneration as tables |
| Conflicting values (attendance 75% and 80%, three registration dates) | Different documents and dates | Most recent signed official document used; conflict recorded |
| Unanswerable questions returned relevant-looking passages | Similarity of unrelated topics overlaps with that of answers | Answer verification step |
| Public interface stopped answering | Monthly call limit of the embedding service reached | Free embedding model on the platform; re-embedding |
| Secrets rejected in production | Quotes and carriage returns copied from a local file | Cleaning when setting secrets; documented |
| Private data in a public repository | Bank accounts in a document | Private overlay with its own origin; fixed a defect that tagged it as public content |
| Free server could not run the interface | Native database driver unsupported | Interface rewritten for the Worker runtime |
| Connector lost its session on restart | No disk on the free host | Session stored in the database |
| Idle database connections closed during long evaluations | Pooler timeout | Short-lived connections and retries |

---

## Chapter 6. Results and discussion

### 6.1 The corpus

On 18 November 2026 the database contained 80 documents and 679 passages. The 80 documents comprised 46 curated and verified documents, one private document and 33 pages of the university website. By category: programs 34, ERP 10, admissions 9, procedures 8, about 6, finance 6, timetables 2, announcements 2, people 2 and campus 1. Seventy-nine documents are in English and one in French. Six documents carry attachments. Of the 85 documents of the catalogue, 46 (54%) were complete: 21 of 22 at priority P0, 23 of 48 at P1 and 2 of 15 at P2. The only incomplete P0 document is the office directory, which was deferred by the administration. The canteen menu, bus and student-life information are supplied by live posts rather than documents, and these categories were empty at the time of the evaluation because no administrator message had yet been received.

### 6.2 Retrieval quality over the iterations

Table 6.1 shows the evaluation after each major batch of data. The test questions were unchanged throughout.

Table 6.1. Retrieval quality by iteration

| Stage | Covered questions | Hit at 5 (covered) | P0 hit at 5 |
|---|---|---|---|
| Website pages only | 5 of 98 (5.1%) | 60.0% | not covered |
| Plus official notices and the ERP manual | 38 of 98 (38.8%) | 94.7% | 100.0% (11 of 19 covered) |
| Plus timetable, regulations policy and further notices | 46 of 98 (46.9%) | 91.3% | 92.9% (14 of 19) |
| Plus admissions, programs, contacts and fee documents | 63 of 98 (64.3%) | 92.1% | 94.7% (19 of 19) |
| After change of embedding model and verification | 63 of 98 (64.3%) | 88.9% | 100.0% (19 of 19) |

Coverage rose from 5% to 64% as official documents were added. Retrieval accuracy on covered questions stayed between 89% and 95%, above the target of 85%. The final system reached the target of 95% on the P0 questions (19 of 19), which the previous embedding model missed by one question.

### 6.3 Answering and declining

Table 6.2 gives the final results measured against the deployed interface.

Table 6.2. Final results on the deployed interface

| Measure | Value | Target |
|---|---|---|
| Questions in the test set | 103 | |
| Answerable questions with an indexed document (coverage) | 63 of 98 (64.3%) | |
| Hit at 5 on covered questions | 88.9% | 85% |
| Hit at 5 on covered P0 questions | 100.0% (19 of 19) | 95% |
| Mean reciprocal rank | 86.6% | |
| Retrieved and answered with high confidence | 82.1% | |
| No-answer correctness | 100.0% (5 of 5) | |

Before the verification step, the confidence of a result was decided by a similarity threshold, and no unanswerable question was refused (0 of 5). The similarities of the unanswerable questions ranged from 0.47 to 0.63, while those of correctly retrieved answerable questions ranged from 0.50 to 0.75 with a median of 0.69, so no single threshold separated them. A test with keyword overlap between question and passages also failed, because answerable questions often use different words from the passage. Rerankers and language-model judges were then compared on the same questions. One reranker refused four of five unanswerable questions but lost French questions; a second refused all five at the cost of a trial-key limit of about ten calls per minute, which cannot serve a public interface. A small language model judge refused all five unanswerable questions and accepted 74% of the answerable ones. It was adopted for the ambiguous middle range, with accept-without-check above 0.70 and reject-without-check below 0.45. All five unanswerable questions are now marked low confidence, including the one about a private telephone number, whose nearest passage is the official contact page.

A part of the 18% of answerable questions that did not receive high confidence is correct behaviour: for the questions about application deadlines and the per-program fee schedule, the database states that the information is not yet available and refers the student to the Admissions office, so a refusal is the intended outcome.

### 6.4 Failure analysis

Seven questions failed. Three require two documents and returned only one (a transcript and clearance question, a resit and fee question, and a Masters requirements and fee question); the second document of each pair exists in the database, so the weakness is that a question needing two documents is better served by two retrieval rounds, which a chatbot can perform. One question about the credits of a course returned program pages with high confidence although no document states course credits; this is the only observed case of an answer wrongly accepted, and it shows the limit of a verification step that reads only the first three passages. Two questions are vague (a staff member's office hours; whether a class was rescheduled this week) and produced low confidence, appropriately. One question asking for the lecturers of a department returned course lists of the program but not the list of lecturers among the first five results. None of the failures concerns a high-priority topic.

### 6.5 Performance and cost

From the maintainers' network a search normally answered in 0.7 to 1.5 seconds. One measurement with a model check took 9 seconds, and repeated identical questions are answered from a cache in under one second. The whole system operates within the free allowances of its providers. The daily allowance of the platform's model service is estimated to permit on the order of a thousand model checks per day, and the checks are skipped for very strong and very weak matches; when the allowance is exhausted the interface falls back to the similarity threshold of 0.64, which refused all five unanswerable test questions while keeping about 80% of correct answers at high confidence.

### 6.6 Operational results

The interface, database, scheduled jobs and connector were deployed. The deployment job completed successfully on each change after the secrets were configured, including a re-indexing step. The live job and the daily job (including a crawl of the website from the automation runner) completed successfully. The connector reconnected from the stored session on a host with no local files, found the four configured groups and reported itself connected. At the time of writing no group message had yet been received after deployment, so the end-to-end publication of a live post was tested with simulated messages against the real interface and database but not with a real administrator message.

### 6.7 Discussion

RQ1. A hybrid design returned the correct document among the first five results for 88.9% of covered questions and for all high-priority ones, above the targets. The result holds for a corpus of 80 documents; larger corpora may require re-tuning.

RQ2. Similarity alone could not distinguish answerable from unanswerable questions, and the added verification step, which uses a model only for ambiguous cases, did so on the whole test set. The number of unanswerable test questions is small (five), so the figure of 100% should be read as evidence that the approach works rather than as a precise rate.

RQ3. All components run within free allowances. The cost of this freedom is dependence on quotas, demonstrated by the interruption caused by the embedding service limit, and on hosts that may sleep or restart. The design mitigates both: the model is replaceable, the state is in the database, and the interface falls back to simpler behaviour when a service is unavailable.

The experience also shows that data quality dominates technical quality. Coverage, not retrieval accuracy, is the main limit: 35% of answerable test questions cannot be answered because the corresponding document has not yet been obtained. The source hierarchy and conflict recording proved necessary: three official documents gave three registration dates, and two gave different attendance requirements.

### 6.8 Limitations and threats to validity

1. The test set was written by the project team and may not represent the questions students actually ask. The five unanswerable questions are too few for a precise estimate.
2. The expected documents of the test questions were assigned by the team, and some questions have more than one acceptable document; the evaluation accepts any of the listed documents.
3. Coverage is incomplete. The office directory, deadlines, the per-program fee schedule, PhD programs and bus information are missing, and several figures (the tuition amount and the instalment percentages) were supplied by the team and await confirmation in an official notice.
4. The verification step uses a small language model whose behaviour may change if the provider updates it.
5. The connector depends on an unofficial client, and its operation on a free host is not guaranteed.
6. Latency was measured from one location and with few samples.

---

## Chapter 7. Conclusion and recommendations

### 7.1 Summary

The project delivered a working, documented and deployed knowledge base for ICT University. It converts official documents, website pages, spreadsheets and administrators' messages into searchable passages, retrieves them with a hybrid method, decides whether they answer a question, and serves them through a keyed public interface at no cost. Provenance, verification status and freshness are recorded for every document. Evaluated on 103 questions, it found the correct document among the first five results for 88.9% of questions that the data covers, including all the highest-priority ones, and it declined every question that it should not answer.

### 7.2 Contributions

1. A catalogue-driven method to specify, collect and track the information of a university, with a generated collection checklist.
2. A document model that records the source, the verifier, the validity and the freshness of each fact, with an explicit rule for conflicts.
3. A retrieval interface that combines semantic and keyword search and returns a verified indication of whether the result answers the question.
4. A deployment on free services, together with automation for validation, scheduled ingestion, evaluation and release.
5. A reusable evaluation set and a coverage-aware evaluation method.
6. Documentation for contributors and for chatbot developers (a user manual).

### 7.3 Limitations

The limitations of section 6.8 apply. In addition, the knowledge base serves factual questions; it does not hold the personal data that many students would like a chatbot to use, and it does not support transactions.

### 7.4 Recommendations

For the project team:

1. Obtain the missing P0 and P1 documents in the following order: the fee schedule and instalment plan from the finance office; the application deadlines and the application guide from the admissions office; the directories of offices, rooms and staff from the administration; the curriculum, course descriptions, graduation rules and thesis rules from the registrar and the heads of department.
2. Confirm in writing the tuition and instalment figures that were supplied verbally.
3. Collect the first real messages of the official groups and verify that menus and announcements appear correctly.
4. Replace the examination timetable placeholder with the official notice when it is published.

For the administration:

5. Designate an owner for each category and require that notices be published as files, so that they can be indexed.
6. Publish a single current academic calendar and fee schedule, and retire older versions, to avoid conflicting dates.
7. Inform the administrators of the official groups that a member number reads their messages.

For chatbot developers:

8. Answer only when the interface reports high confidence, show the source and the date of verification, and warn when a document is stale.
9. Keep the access key on a server, and send feedback reports for wrong or missing answers.

For the maintainers:

10. Rotate the database password that was displayed during development, review the access keys periodically, and keep the daily and live jobs enabled.
11. Re-run the evaluation after every batch of new documents and extend the test set with questions that students actually ask.

### 7.5 Future work

- Add a second retrieval round for questions that need two documents.
- Extend the test set, in particular the unanswerable questions, and measure the stability of the verification model over time.
- Fill the spreadsheets for directories, bus routes and clubs, and automate their synchronisation.
- Add a simple text-based navigation of the building, which the team is preparing.
- Add the timetables of the other sections and of the Masters programs.
- Evaluate end-to-end chatbots built on the interface, with students as users.
- Investigate a retrieval method that handles French questions about English documents better, since a French question about transcripts retrieved a document about complaints during testing.

---

## References

Cormack, G. V., Clarke, C. L. A. and Büttcher, S. (2009) 'Reciprocal rank fusion outperforms Condorcet and individual rank learning methods', Proceedings of the 32nd International ACM SIGIR Conference on Research and Development in Information Retrieval, pp. 758-759.

Kane, A. (2021) pgvector: open-source vector similarity search for Postgres. Available at: https://github.com/pgvector/pgvector (Accessed: 18 November 2026).

Karpukhin, V., Oguz, B., Min, S., Lewis, P., Wu, L., Edunov, S., Chen, D. and Yih, W. (2020) 'Dense passage retrieval for open-domain question answering', Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing, pp. 6769-6781.

Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S. and Kiela, D. (2020) 'Retrieval-augmented generation for knowledge-intensive NLP tasks', Advances in Neural Information Processing Systems, 33, pp. 9459-9474.

Malkov, Y. A. and Yashunin, D. A. (2020) 'Efficient and robust approximate nearest neighbor search using hierarchical navigable small world graphs', IEEE Transactions on Pattern Analysis and Machine Intelligence, 42(4), pp. 824-836.

Manning, C. D., Raghavan, P. and Schütze, H. (2008) Introduction to Information Retrieval. Cambridge: Cambridge University Press.

Reimers, N. and Gurevych, I. (2019) 'Sentence-BERT: sentence embeddings using Siamese BERT-networks', Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing, pp. 3982-3992.

Robertson, S. and Zaragoza, H. (2009) 'The probabilistic relevance framework: BM25 and beyond', Foundations and Trends in Information Retrieval, 3(4), pp. 333-389.

Russell, S. and Norvig, P. (2021) Artificial Intelligence: A Modern Approach. 4th edn. Harlow: Pearson.

Voorhees, E. M. (1999) 'The TREC-8 question answering track report', Proceedings of the Eighth Text REtrieval Conference (TREC-8), pp. 77-82.

---

## Appendix A. Document metadata schema

| Field | Type | Meaning |
|---|---|---|
| id | text | Stable identifier, equal to the file name |
| title | text | Human-readable title |
| category | one of 13 | about, admissions, programs, procedures, finance, erp, campus, transport, canteen, timetables, people, student-life, announcements |
| program_level | list | all, bachelor, masters, phd |
| language | en or fr | Language of the document |
| source_type | enumeration | official_doc, website, interview, sheet, image, observation |
| source_url | address or null | Origin of the information |
| attachments | list | Stored file identifier, kind, description, extracted text file |
| academic_year, semester | text | Period concerned |
| valid_from, valid_until | dates | Validity; documents past valid_until are not returned |
| freshness_tier | enumeration | realtime, daily, semester, static |
| status | enumeration | draft, verified, deprecated |
| last_verified, verified_by | date, handle | When and by whom the content was checked |
| owner, collected_by, collected_on | text, date | Responsibility and collection record |
| confirmed_in_writing | boolean | Whether verbal information was confirmed in writing |
| conflict_note | text | Description of a disagreement between sources |
| tags, related | lists | Keywords and related documents |

## Appendix B. Interface summary

| Method and path | Purpose | Access |
|---|---|---|
| GET /v1/health | Service status | none |
| POST /v1/search | Retrieve passages for a question | key |
| GET /v1/documents/{id} | A document with all passages | key |
| GET /v1/documents | List of documents | key |
| GET /v1/categories | Categories with document counts | key |
| GET /v1/freshness | Staleness by category | key |
| POST /v1/feedback | Report a wrong, missing or outdated answer | key |
| POST /v1/admin/keys, DELETE /v1/admin/keys/{id} | Create and revoke access keys | admin token |
| POST /v1/admin/notes, DELETE /v1/admin/notes/{id} | Publish and delete short-lived posts | admin token |
| POST /v1/admin/transcribe | Read text from an image | admin token |
| POST /v1/admin/embed | Compute embeddings for the pipeline | admin token |
| POST /v1/admin/wa-state/get, /set | Store the connector state | admin token |

The complete description for chatbot developers is in the user manual (docs/user-manual.md).

## Appendix C. Test question format

Each question has an identifier, text, category, type (factual, procedural, list, multi-hop, variant or no-answer), language, priority (P0, P1 or P2), the list of documents that answer it, and a field in which the category owner records the correct answer. A result matches an expected document when the identifier is equal to it or begins with it followed by a hyphen, which allows grouped documents (for example one timetable document per program) to match.

## Appendix D. Repository layout

| Folder | Content |
|---|---|
| content/ | Curated documents (Markdown with metadata) and extracted attachment texts |
| content-private/ | Documents indexed from one machine only; not published |
| schema/ | Metadata schema, categories, catalogue of planned documents |
| sources/ | Configuration of the website and spreadsheet connectors |
| src/ictkb/ | Python package: pipeline, command-line tool, reference interface |
| cloudflare-worker/ | Public interface for the Worker runtime |
| whatsapp-listener/ | Messaging connector |
| eval/ | Test questions and evaluation program |
| db/migrations/ | Database migrations |
| docker/, render.yaml | Container definitions and host blueprint |
| docs/ | Architecture, interface reference, collection guide, runbook, deployment, user manual, this report |
| .github/ | Workflows, issue and review templates |
| tests/ | Automated tests |
