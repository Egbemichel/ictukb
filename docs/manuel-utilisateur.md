# API de la base de connaissances d'ICT University : manuel d'utilisation

Version 1.0, 18 novembre 2026

Ce manuel explique comment connecter un chatbot, une page web ou tout autre programme à la base de connaissances d'ICT University. Il ne suppose aucune expérience préalable du système. Suivez les sections 1 à 4 pour faire une première requête réussie en une dizaine de minutes, et les sections 5 à 8 pour transformer les réponses en un vrai chatbot.

Sommaire

1. Ce qu'est la base de connaissances et à quoi elle peut répondre
2. Avant de commencer : l'adresse et une clé d'API
3. Votre première requête
4. Comprendre la réponse
5. Construire un chatbot pas à pas
6. Les autres points d'accès
7. Limites, erreurs et bonnes pratiques
8. Résolution de problèmes
9. Référence : tous les points d'accès, champs et valeurs
10. Pour les responsables : délivrer et révoquer des clés

---

## 1. Ce qu'est la base de connaissances et à quoi elle peut répondre

La base de connaissances est une base de données d'informations officielles sur ICT University, tenue à jour par l'équipe d'étudiants du projet. Vous lui envoyez une question en français ou en anglais courant. Elle renvoie les passages de documents officiels qui répondent le mieux à la question, avec le titre du document, un lien vers la source, la date de dernière vérification de l'information et un jugement indiquant si les passages contiennent vraiment la réponse.

Elle ne rédige pas de réponses. Votre programme (le chatbot) prend les passages renvoyés, avec la question de l'étudiant, et produit la réponse finale, par exemple avec un modèle de langage de votre choix. Cette conception garde les faits à un seul endroit : quand un service change un montant ou une date limite, tous les chatbots donnent la nouvelle réponse sans avoir besoin d'être modifiés.

**Informations actuellement disponibles** (au 18 novembre 2026) :

| Domaine | Exemples de ce qui est couvert |
|---|---|
| À propos de l'université | Présentation, contacts officiels, règlement académique (barème de notation, moyenne, présence), calendrier académique |
| Admissions | Comment postuler, conditions d'entrée en licence et en master, étudiants transférés et internationaux, frais de dossier |
| Programmes | Liste des programmes des deux facultés, durée, mode d'enseignement, cours et enseignants de l'emploi du temps d'automne 2026 |
| Procédures | Inscription aux cours, ajout et abandon de cours, rattrapages, relevés de notes, réclamations, report, changement de programme, stages |
| Finances | Frais de scolarité et paiement par tranches, comptes bancaires, preuve de paiement, retard de paiement, quitus |
| ERP | Connexion, réinitialisation du mot de passe, inscription, résultats, frais, demandes, assistance |
| Campus | Emplacement et lien vers la carte |
| Emplois du temps | Emploi du temps des cours de licence d'automne 2026, période d'examens |
| Personnes | Direction de l'université, enseignants par cours |
| Messages en direct | Menu de la cantine, annonces, vie étudiante et informations sur le bus, publiés par les groupes WhatsApp officiels au fur et à mesure (ils expirent automatiquement) |

**Pas encore disponible :** le barème complet des frais par programme, les dates limites de candidature, l'annuaire des bureaux, les plans des étages, les listes du personnel et des chefs de département, les programmes de doctorat, l'emploi du temps des examens (publié sous forme d'avis pendant la période d'examens) et les lignes de bus. Pour ces questions, le système répond que l'information n'est pas encore disponible, et votre chatbot doit dire à l'étudiant de s'adresser au service des admissions.

**Jamais stocké :** les données personnelles (notes, soldes de frais, numéros d'identité) et les numéros de téléphone privés. Une question comme « Quel est mon solde de frais ? » ne reçoit donc correctement aucune réponse.

## 2. Avant de commencer : l'adresse et une clé d'API

**Adresse de base :** `https://ictkb-api.ictkb-api-worker.workers.dev`

Chaque point d'accès, sauf `/v1/health`, demande une clé d'API envoyée dans l'en-tête `X-API-Key`.

**Demander une clé.** Contactez directement un responsable du projet (message privé ou en classe) en indiquant votre nom, votre classe et ce que vous construisez. Un responsable vous envoie une clé en privé. Ne demandez pas de clé et ne collez jamais de clé dans un ticket public du dépôt, car tout ce qui y est écrit est public et permanent. La clé est affichée une seule fois, donc rangez-la tout de suite. Une clé identifie votre chatbot, autorise 30 requêtes par minute et peut être désactivée par les responsables si elle est mal utilisée. Elle protège le service contre la surcharge. Ce n'est pas un secret entre vous et l'université, mais vous devez quand même la garder privée.

**Gardez la clé hors du code public.** Ne l'enregistrez jamais dans un dépôt public et ne la mettez jamais dans le JavaScript d'une page web. Rangez-la dans une variable d'environnement (voir les exemples ci-dessous) ou dans les réglages secrets de votre hébergeur.

Pour vérifier que le service fonctionne, ce qui ne demande aucune clé :

```bash
curl https://ictkb-api.ictkb-api-worker.workers.dev/v1/health
```

Un service en bonne santé répond avec `"status": "ok"`.

## 3. Votre première requête

### 3.1 Avec curl

Remplacez `VOTRE_CLE` par votre clé.

```bash
curl -X POST https://ictkb-api.ictkb-api-worker.workers.dev/v1/search \
  -H "X-API-Key: VOTRE_CLE" \
  -H "Content-Type: application/json" \
  -d '{"query": "Puis-je payer mes frais en plusieurs tranches ?"}'
```

Sous Windows PowerShell :

```powershell
curl.exe -X POST https://ictkb-api.ictkb-api-worker.workers.dev/v1/search `
  -H "X-API-Key: VOTRE_CLE" -H "Content-Type: application/json" `
  -d '{\"query\": \"Puis-je payer mes frais en plusieurs tranches ?\"}'
```

### 3.2 Avec Python

Installez la bibliothèque `requests` (`pip install requests`), puis enregistrez ceci sous `essai_recherche.py` :

```python
import os
import requests

API = "https://ictkb-api.ictkb-api-worker.workers.dev"
KEY = os.environ["KB_API_KEY"]          # à définir d'abord : voir ci-dessous

response = requests.post(
    f"{API}/v1/search",
    headers={"X-API-Key": KEY},
    json={"query": "Puis-je payer mes frais en plusieurs tranches ?", "top_k": 3},
    timeout=60,
)
response.raise_for_status()
data = response.json()

print("confiance :", data["confidence"])
for item in data["results"]:
    print(f'{item["similarity"]:.2f}  {item["document"]["title"]}')
    print("   ", item["text"][:150].replace("\n", " "))
```

Définissez la clé dans le terminal avant de lancer le programme :

```bash
export KB_API_KEY=VOTRE_CLE        # macOS et Linux
set KB_API_KEY=VOTRE_CLE           # invite de commandes Windows
$env:KB_API_KEY="VOTRE_CLE"        # Windows PowerShell
python essai_recherche.py
```

### 3.3 Avec JavaScript (Node.js 18 ou plus récent)

```javascript
const API = "https://ictkb-api.ictkb-api-worker.workers.dev";
const KEY = process.env.KB_API_KEY;

const response = await fetch(`${API}/v1/search`, {
  method: "POST",
  headers: { "X-API-Key": KEY, "Content-Type": "application/json" },
  body: JSON.stringify({ query: "Puis-je payer mes frais en plusieurs tranches ?", top_k: 3 }),
});
if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
const data = await response.json();
console.log(data.confidence, data.results.map((r) => r.document.title));
```

Enregistrez-le sous `essai_recherche.mjs` et lancez `node essai_recherche.mjs`.

## 4. Comprendre la réponse

Une recherche renvoie cette structure (raccourcie) :

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

La plupart des documents sont écrits en anglais, donc leur texte, leur titre et leurs intertitres sont en anglais, même quand la question est en français.

### 4.1 Le champ le plus important : `confidence`

| Valeur | Signification | Ce que doit faire votre chatbot |
|---|---|---|
| `high` (élevée) | Les passages renvoyés contiennent la réponse. | Répondre à partir des passages. |
| `low` (faible) | Les passages sont liés au sujet mais n'énoncent pas la réponse, ou la question sort du cadre des informations de l'université (météo, données personnelles, prédictions). | Ne pas répondre à partir d'eux. Dire que l'information n'est pas disponible et conseiller le service concerné. Vous pouvez citer les titres des documents les plus proches. |
| `none` (aucune) | Rien ne correspond. | Dire que l'information n'est pas disponible. |

La valeur de `confidence` est vérifiée, pas seulement estimée. Une correspondance très forte est acceptée tout de suite, une correspondance très faible est rejetée, et les cas intermédiaires sont jugés par un petit modèle de langage qui lit les passages et répond par oui ou non. Sur les 103 questions de test du projet, 100 % des questions qui ne doivent pas recevoir de réponse ont été correctement marquées `low`, et 82 % des questions avec réponse ont été marquées `high`. Les autres ont été marquées `low` alors qu'une réponse existait. Dans ce cas, votre chatbot dit qu'il ne sait pas, ce qui est sans danger mais peu utile. Vous pouvez alors montrer les passages les plus proches avec une phrase prudente.

### 4.2 `verification` : comment la confiance a été décidée

| Valeur | Signification |
|---|---|
| `strong-match` | Le meilleur passage était si proche de la question qu'aucune vérification n'était nécessaire (toujours `high`). |
| `weak-match` | Le meilleur passage était trop différent de la question (toujours `low`). |
| `model` | Un modèle de langage a lu les passages et les a jugés. |
| `fallback` | La vérification par le modèle n'était pas disponible, donc un seuil de similarité a été utilisé. |
| `similarity` | Vous avez désactivé la vérification avec `"verify": false`. |
| `none` | Aucun résultat. |

### 4.3 Chaque résultat

| Champ | Signification |
|---|---|
| `text` | Le passage. Il commence par le titre du document et l'intertitre, puis le contenu. Donnez ce texte à votre modèle de langage. |
| `heading_path` | La section du document, par exemple « Fees > Installments ». La plupart des intertitres sont rédigés comme des questions. |
| `similarity` | Similarité cosinus entre la question et le passage, de 0 à 1. Utile pour déboguer ; ne l'utilisez pas pour décider de répondre (utilisez `confidence`). |
| `score` | Score de classement interne. Les résultats sont triés selon lui ; ignorez sa valeur. |
| `document.id` | Identifiant stable du document. Utilisez-le pour citer, mettre en cache ou ouvrir le document entier. |
| `document.title` | Titre lisible pour les citations. |
| `document.category` | Une des 13 catégories (section 9.4). |
| `document.source_url` | La page web d'où vient l'information, ou `null`. |
| `document.attachments` | Fichiers originaux (PDF, images) avec une `description` et une `url` de téléchargement. Montrez-les à l'étudiant quand c'est pertinent. |
| `document.last_verified` | La date à laquelle une personne a vérifié l'information pour la dernière fois. Montrez-la pour les frais, les dates limites et les emplois du temps. |
| `document.freshness_tier` | La fréquence à laquelle le document doit être revérifié : `realtime` (1 jour), `daily` (7), `semester` (120), `static` (365). |
| `document.stale` | `true` quand le document a dépassé sa date de vérification. Prévenez l'étudiant qu'il peut être périmé. |

Plusieurs résultats peuvent venir du même document. Ce sont alors des passages différents de ce document, classés par pertinence.

## 5. Construire un chatbot pas à pas

Un chatbot à recherche répète quatre étapes pour chaque question : chercher, contrôler, construire la consigne, répondre.

```
question de l'étudiant
      |
      v
1. chercher     --> POST /v1/search
      |
2. contrôler    --> la confiance est "high" ?   non --> "Je n'ai pas cette information ; demandez au service des admissions"
      | oui
3. consigne     --> instructions + passages + question
      |
4. répondre     --> votre modèle de langage --> réponse avec les sources
```

### 5.1 Étape 1 : un petit client

Créez `kb.py` :

```python
import os
import time
import requests

API = os.environ.get("KB_API_URL", "https://ictkb-api.ictkb-api-worker.workers.dev")
KEY = os.environ["KB_API_KEY"]
HEADERS = {"X-API-Key": KEY}


def _post(path, payload, tries=4):
    """POST avec nouvelles tentatives pour les limites de débit (429) et les erreurs temporaires du serveur (5xx)."""
    for attempt in range(tries):
        r = requests.post(f"{API}{path}", headers=HEADERS, json=payload, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            wait = int(r.headers.get("Retry-After", 2 ** attempt))
            time.sleep(min(wait, 30))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("La base de connaissances ne répond pas. Réessayez plus tard.")


def search(query, top_k=5, **filters):
    """filters : category=..., program_level='bachelor'|'masters'|'phd', language='en'|'fr'."""
    body = {"query": query, "top_k": top_k}
    if filters:
        body["filters"] = filters
    return _post("/v1/search", body)


def feedback(verdict, query=None, document_id=None, chunk_id=None, note=None):
    """verdict : 'wrong' | 'missing' | 'outdated' | 'helpful'."""
    return _post("/v1/feedback", {"verdict": verdict, "query": query, "document_id": document_id,
                                  "chunk_id": chunk_id, "note": note})
```

### 5.2 Étape 2 : décider s'il faut répondre

```python
NOT_AVAILABLE = ("Je n'ai pas encore cette information. Veuillez demander au service des admissions "
                 "(admissions@ictuniversity.edu.cm) ou au service concerné.")


def retrieve(question):
    found = kb.search(question, top_k=5)
    if found["confidence"] != "high":
        return None, found          # rien de fiable : ne laissez pas le modèle deviner
    return found["results"], found
```

Ne sautez pas ce contrôle. Sans lui, un modèle de langage inventera souvent une réponse assurée à une question que les données ne couvrent pas, comme un solde de frais personnel ou la date d'un événement qui n'a pas été annoncé.

### 5.3 Étape 3 : construire la consigne

```python
SYSTEM = """Tu es l'assistant des étudiants d'ICT University.
Réponds uniquement à partir des SOURCES ci-dessous. Si les sources n'indiquent pas la réponse, dis-le et conseille de
demander au service concerné. N'invente jamais de montants, de dates, de noms ni de dates limites.
Réponds dans la langue de la question (français ou anglais). Fais une réponse courte et claire.
Cite les sources avec leur numéro, par exemple [1].
Si une source est marquée « peut être périmée », dis à l'étudiant de confirmer auprès du service."""


def group_by_document(results):
    """Plusieurs passages peuvent venir d'un même document ; donne un seul numéro à chaque document."""
    groups = {}
    for r in results:
        d = r["document"]
        groups.setdefault(d["id"], {"doc": d, "texts": []})["texts"].append(r["text"])
    return list(groups.values())


def build_prompt(question, results):
    blocks = []
    for i, g in enumerate(group_by_document(results), 1):
        d = g["doc"]
        flag = " (peut être périmée)" if d["stale"] else ""
        blocks.append(f'[{i}] {d["title"]}, vérifiée le {d["last_verified"]}{flag}\n' + "\n\n".join(g["texts"]))
    return "SOURCES\n\n" + "\n\n".join(blocks) + f"\n\nQUESTION\n{question}"
```

### 5.4 Étape 4 : interroger votre modèle de langage et ajouter les sources

Votre programme appelle le modèle auquel vous avez accès. La fonction ci-dessous est la seule partie que vous devez adapter :

```python
def call_model(system, user):
    """Envoie `system` et `user` à votre modèle de langage et renvoie sa réponse en texte.
    Remplacez le corps de la fonction par l'appel du service que vous utilisez."""
    raise NotImplementedError("connectez ici votre modèle de langage")


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
                sources.append(f'    Fichier : {a["description"][:80]} {a["url"]}')
    return reply + "\n\nSources :\n" + "\n".join(sources)
```

Un chatbot complet en ligne de commande :

```python
import kb

if __name__ == "__main__":
    print("Assistant d'ICT University. Tapez 'quit' pour arrêter.")
    while True:
        q = input("> ").strip()
        if q.lower() in {"quit", "exit"}:
            break
        if q:
            print(answer(q))
```

Pour tout tester avant de connecter un modèle, faites renvoyer `user` par `call_model` (cela affiche la consigne que recevrait votre modèle). Quand la consigne vous semble bonne, connectez le modèle.

### 5.5 Gérer les questions de suivi

Un étudiant peut écrire « Et pour le master ? » après avoir posé une question sur les frais. Le point d'accès de recherche n'a pas de mémoire, donc reformulez la question en une question autonome avant de chercher. Demandez-le à votre modèle :

```python
CONDENSE = ("Reformule la dernière question pour qu'elle se comprenne sans la conversation. "
            "Renvoie seulement la question reformulée, dans la même langue.")


def standalone(history, question):
    if not history:
        return question
    turns = "\n".join(f"{role}: {text}" for role, text in history[-6:])
    return call_model(CONDENSE, f"{turns}\nDernière question : {question}").strip()
```

Appelez ensuite `retrieve(standalone(history, question))`.

### 5.6 Utiliser des filtres

Les filtres restreignent la recherche. Ils sont facultatifs et rarement nécessaires.

```python
kb.search("entry requirements", category="admissions", program_level="masters")
```

Utilisez `program_level` quand l'étudiant vous a indiqué son niveau. Évitez le filtre `language` : la plupart des documents sont en anglais et une question en français reçoit une bonne réponse à partir d'eux, donc filtrer sur `fr` cacherait la plupart des résultats.

### 5.7 Signaler les mauvaises réponses

Donnez à l'étudiant un moyen de signaler une mauvaise réponse et de la renvoyer. Les responsables lisent ces signalements et corrigent les documents.

```python
kb.feedback("wrong", query=question, document_id=results[0]["document"]["id"], note="La date est périmée")
```

### 5.8 Une interface web ou mobile

N'appelez pas l'API directement depuis une page web ou une application mobile, car la clé serait visible par toute personne qui ouvre la page. Placez un petit serveur entre les deux. Un proxy Node.js minimal :

```javascript
// server.mjs : npm install express, puis KB_API_KEY=... node server.mjs
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

Votre interface appelle `/api/search` sur votre propre serveur.

## 6. Les autres points d'accès

### 6.1 Lire un document en entier

```bash
curl https://ictkb-api.ictkb-api-worker.workers.dev/v1/documents/finance-installments -H "X-API-Key: VOTRE_CLE"
```

Renvoie les métadonnées du document et tous ses passages dans l'ordre (`chunks`). Utilisez-le quand vous voulez montrer la page complète derrière une réponse.

### 6.2 Lister les documents

```bash
curl "https://ictkb-api.ictkb-api-worker.workers.dev/v1/documents?category=finance&limit=20&offset=0" -H "X-API-Key: VOTRE_CLE"
```

### 6.3 Lister les catégories avec leur nombre de documents

```bash
curl https://ictkb-api.ictkb-api-worker.workers.dev/v1/categories -H "X-API-Key: VOTRE_CLE"
```

Utile pour construire un menu du type « Choisissez un sujet ».

### 6.4 Fraîcheur des données

```bash
curl https://ictkb-api.ictkb-api-worker.workers.dev/v1/freshness -H "X-API-Key: VOTRE_CLE"
```

Renvoie, pour chaque catégorie, le nombre de documents, combien ont dépassé leur date de vérification et l'heure de la dernière modification.

### 6.5 Envoyer un retour

```bash
curl -X POST https://ictkb-api.ictkb-api-worker.workers.dev/v1/feedback \
  -H "X-API-Key: VOTRE_CLE" -H "Content-Type: application/json" \
  -d '{"verdict": "outdated", "query": "when does registration close", "document_id": "procedures-course-registration", "note": "Nouvelle date limite annoncée"}'
```

## 7. Limites, erreurs et bonnes pratiques

**Limites.** 30 requêtes par minute et par clé. Une requête au-delà de la limite reçoit le statut 429 et un en-tête `Retry-After`. Les questions font de 2 à 1 000 caractères. `top_k` vaut 20 au plus ; 3 à 5 passages suffisent pour un chatbot. Une recherche répond normalement en environ une seconde ; quand la vérification par le modèle est nécessaire, cela peut prendre quelques secondes. Les questions identiques répétées dans un délai de cinq minutes reçoivent une réponse immédiate depuis un cache.

**Erreurs.** Les erreurs renvoient un corps JSON comme `{"detail": "Invalid or revoked API key"}`.

| Statut | Signification | Que faire |
|---|---|---|
| 401 | Clé absente, fausse ou révoquée | Vérifiez l'en-tête `X-API-Key`. Demandez aux responsables si la clé a été révoquée. |
| 404 | Document ou adresse inconnu | Vérifiez l'orthographe de l'identifiant du document. |
| 422 | Requête invalide, par exemple une question de moins de 2 caractères | Corrigez le corps de la requête. |
| 429 | Trop de requêtes | Attendez `Retry-After` secondes et réessayez. |
| 500 ou 503 | Panne temporaire du service ou de l'un de ses fournisseurs | Réessayez après quelques secondes ; le client de la section 5.1 le fait automatiquement. |

**Bonnes pratiques.**

1. Vérifiez toujours `confidence` avant de répondre. Cette seule règle évite la plupart des mauvaises réponses.
2. Ne donnez à votre modèle que les passages renvoyés et dites-lui de répondre uniquement à partir d'eux.
3. Montrez les titres et les liens des documents comme sources, et montrez `last_verified` pour les frais, les dates limites, les emplois du temps, le menu de la cantine et les annonces.
4. Avertissez quand `stale` vaut true.
5. Envoyez une seule recherche par question d'étudiant ; mettez les réponses en cache dans votre application quand beaucoup d'étudiants posent la même question.
6. N'envoyez pas de données personnelles (noms, matricules, soldes) à l'API. Elle ne stocke que la question que vous envoyez dans les signalements.
7. Répondez dans la langue de la question.
8. Dites aux étudiants que l'assistant peut se tromper et que les services ont le dernier mot.

## 8. Résolution de problèmes

| Symptôme | Cause probable | Solution |
|---|---|---|
| `401 Missing X-API-Key header` | L'en-tête est absent ou mal orthographié | Envoyez exactement `X-API-Key: VOTRE_CLE`. |
| `401 Invalid or revoked API key` | Mauvaise clé, espace en trop, ou clé désactivée | Recopiez la clé sans espaces ni guillemets ; demandez à un responsable. |
| `KeyError: 'KB_API_KEY'` en Python | La variable d'environnement n'est pas définie dans ce terminal | Définissez-la dans le même terminal que celui où vous lancez le programme. |
| Chaque réponse est « Je n'ai pas cette information » | Les questions portent sur des sujets qui ne sont pas encore dans les données | Essayez un sujet connu, par exemple « Comment demander un relevé de notes ? ». Voyez la liste de la section 1. |
| Une réponse manque de détails que le service connaît | Les données ont une lacune | Envoyez un retour avec le verdict `missing` ; les responsables l'ajouteront. |
| La réponse est périmée | Le document n'a pas été revérifié | Regardez `last_verified` ; envoyez un retour avec le verdict `outdated`. |
| Première requête lente | Le service se réveille ou la vérification par le modèle s'exécute | Normal ; les questions identiques suivantes sont instantanées. Réglez un délai d'attente de 60 secondes côté client. |
| Erreurs `429` pendant les tests | Plus de 30 requêtes en une minute | Ralentissez, ou mettez les réponses en cache. |
| Une question en français renvoie du texte en anglais | La plupart des documents sont écrits en anglais | Normal. Dites à votre modèle de répondre dans la langue de l'étudiant. |

Si un problème persiste, contactez un responsable avec la question que vous avez posée, les valeurs de `confidence` et de `verification` renvoyées et l'heure. Pour un bogue qui ne contient aucune clé, vous pouvez aussi ouvrir un ticket dans le dépôt.

## 9. Référence : tous les points d'accès, champs et valeurs

### 9.1 Authentification

En-tête `X-API-Key: <votre clé>` sur chaque requête, sauf `GET /v1/health`.

### 9.2 `POST /v1/search`

Corps de la requête :

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `query` | texte, de 2 à 1 000 caractères | oui | La question de l'étudiant, en français ou en anglais. |
| `top_k` | entier, de 1 à 20 | non (5) | Nombre de passages à renvoyer. |
| `filters.category` | texte | non | Une des catégories de la section 9.4. |
| `filters.program_level` | `bachelor`, `masters` ou `phd` | non | Documents de ce niveau et documents de tous les niveaux. |
| `filters.language` | `en` ou `fr` | non | Langue du document (voir 5.6). |
| `verify` | booléen | non (true) | `false` saute la vérification par le modèle et décide de `confidence` par la seule similarité (plus rapide, moins précis). |

Réponse : `confidence`, `verification`, `results[]` comme décrit dans la section 4.

### 9.3 Autres points d'accès

| Méthode et chemin | Description |
|---|---|
| `GET /v1/health` | Sans clé. Renvoie `status`, `version`, `environment`, `documents`, `chunks`, `embedding_model`. |
| `GET /v1/documents/{id}` | Un document avec tous ses passages. 404 s'il est inconnu. |
| `GET /v1/documents?category=&limit=&offset=` | Liste de documents (`id`, `title`, `category`, `freshness_tier`, `last_verified`). `limit` jusqu'à 200. |
| `GET /v1/categories` | Les catégories avec `id`, `label`, `description`, `documents`. |
| `GET /v1/freshness` | Par catégorie : `documents`, `stale`, `last_update`. |
| `POST /v1/feedback` | Corps : `verdict` (obligatoire), `query`, `chunk_id`, `document_id`, `note`. Renvoie `{"id": n}` avec le statut 201. |

### 9.4 Catégories

`about`, `admissions`, `programs`, `procedures`, `finance`, `erp`, `campus`, `transport`, `canteen`, `timetables`, `people`, `student-life`, `announcements`.

### 9.5 Identifiants des messages en direct

Les messages des groupes WhatsApp officiels ont des identifiants de document qui commencent par `canteen-menu-` (un par jour), `announcements-current-note-`, `student-life-update-` ou `transport-update-`, suivis de la date. Ils disparaissent automatiquement après leur dernier jour de validité (le menu après un jour, les autres messages après 7 à 14 jours). Les menus lus à partir d'une photo se terminent par la ligne « Read automatically from a photo; check the photo for exact details. ». Montrez cette ligne à l'étudiant.

## 10. Pour les responsables : délivrer et révoquer des clés

Demande le jeton d'administration, que détiennent les responsables du projet et qui n'est jamais partagé avec les développeurs de chatbots.

Créer une clé :

```bash
curl -X POST https://ictkb-api.ictkb-api-worker.workers.dev/v1/admin/keys \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"owner": "nom de l'"'"'étudiant ou du projet", "rate_limit_per_min": 30}'
```

La réponse contient `id` et `api_key` ; envoyez la clé à l'étudiant en privé. Seule une empreinte est stockée, donc une clé perdue ne peut pas être retrouvée et doit être remplacée. Notez chaque clé délivrée (à qui, quand) dans un tableur privé, et ne le publiez jamais.

Révoquer une clé :

```bash
curl -X DELETE https://ictkb-api.ictkb-api-worker.workers.dev/v1/admin/keys/ID_DE_LA_CLE -H "X-Admin-Token: $ADMIN_TOKEN"
```

La révocation prend effet en moins d'une minute.
