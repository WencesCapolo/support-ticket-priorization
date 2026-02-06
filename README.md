# Support Ticket Prioritization: Beyond Sentiment

A **Multi-Factor Prioritization Engine** that identifies high-risk support tickets before they become churn events—by weighing behavioral signals.

> 📐 For a detailed breakdown of the scoring logic and decision-making architecture, see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## 📋 The Problem

Standard sentiment analysis fails in real-world customer support:

| Pattern | Sentiment Says | Reality |
|---------|----------------|---------|
| **"Hidden Fire"** 🔥 | Neutral/Positive | Enterprise client silently waiting on a blocked payroll. **High churn risk.** |
| **"Noise"** 📢 | Angry/Negative | Starter-tier user frustrated about UI fonts. **Low business impact.** |

**Polite customers churn silently. Angry users often have trivial issues.**

Sentiment alone captures emotion—not urgency, not value, not risk.

---

## 💡 The Solution: Ontop Priority Score

An **Additive Scoring System (0-100)** that combines multiple behavioral and contextual signals:

| Points | Signal | Description |
|--------|--------|-------------|
| **+30** | 🔕 **Silence Risk** | Agent hasn't replied in >5 days. Critical ghosting indicator. |
| **+30** | ⚠️ **Keyword Urgency** | Subject contains "payroll", "wire", "failure", "blocked". Business-critical language. |
| **+25** | 🏢 **Enterprise Tier** | High MRR clients ($3k+) get priority bumps. Revenue protection. |
| **+20** | 🔄 **Recurrence** | Same client, same issue category. Frustration compounding signal. |
| **+10** | ⏰ **Stagnation** | Ticket open >7 days without resolution. |

**Score Interpretation:**
- **70-100:** 🔴 Critical — Immediate attention required
- **40-69:** 🟡 Medium — Schedule within 24h
- **0-39:** 🟢 Low — Standard queue priority

---

## 🚀 Quick Start

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & Docker Compose (or Podman)
- Git

### Installation & Running

1. **Clone the repository:**
```bash
git clone https://github.com/WencesCapolo/support-ticket-prioritization.git
cd support-ticket-prioritization
```

2. **Run with Docker Compose:**
```bash
docker-compose up --build
```

That's it! The system will initialize the database, calculate historical scores, and launch the dashboard.

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Dashboard** | [http://localhost:3000](http://localhost:3000) | Interactive prioritization UI |
| **API** | [http://localhost:8000](http://localhost:8000) | FastAPI REST endpoints |
| **API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger/OpenAPI documentation |

---

## 🧪 Demo Scenarios

### Scenario A: "The Hidden Fire" 🔥

Look for ticket **#f6bdbf55** or similar "Payment delayed" examples.

```
Subject: "Payment delayed for contractor"
Sentiment: Neutral (0.0)
Priority:  Critical (100.0) ← Our system catches this
```

**Why it matters:** TextBlob sees a calm, professional message. Our engine sees:
- Enterprise client ($8,500 MRR) → +25 pts
- "Payment" keyword → +30 pts  
- 6 days of agent silence → +30 pts
- Recurring issue → +20 pts

**This ticket would be buried by sentiment-only systems.**

---

### Scenario B: "The Noise" 📢

Look for tickets mentioning "UGLY FONT" or similar UI complaints.

```
Subject: "THIS FONT IS UGLY!!!"
Sentiment: Angry (-0.8)
Priority:  Low (15.0) ← Correctly deprioritized
```

**Why it matters:** Sentiment analysis screams "urgent!" Our engine sees:
- Starter tier ($50 MRR) → +0 pts
- No critical keywords → +0 pts
- Agent replied same day → +0 pts
- First-time issue → +0 pts
- Category: UI/Cosmetic → Low recurrence rate

**Angry doesn't mean urgent.**

---

## 🏗️ Technical Highlights

### 1. Simulation Mode (Time Travel) ⏳

The provided dataset is **45 days old**. Running naive time calculations would mark every ticket as "stagnant."

**Solution: Dynamic Time Anchor**

```python
# Instead of datetime.now()
reference_date = df['created_at'].max()  # Anchors to dataset's timeline
silence_days = (reference_date - last_agent_reply).days
```

This allows the scoring engine to evaluate tickets *as if the system were running at the time of the data*—essential for accurate historical analysis and demo purposes.

---

### 2. Comparison Dashboard 📊

The frontend includes a **Sentiment vs. Priority toggle** that displays:
- Side-by-side ticket rankings
- Score breakdown tooltips
- Visual indicators for "Hidden Fire" and "Noise" patterns

This directly demonstrates the value proposition to stakeholders.

---

### 3. Containerized Architecture 🐳

```
┌─────────────────────────────────────────────────────┐
│                  docker-compose.yml                 │
├─────────────────────┬───────────────────────────────┤
│     Frontend        │          Backend              │
│  ┌───────────────┐  │  ┌─────────────────────────┐  │
│  │  Next.js 16   │  │  │    FastAPI + Uvicorn    │  │
│  │  React 19     │◄─┼──┤    Python 3.11          │  │
│  │  Tailwind CSS │  │  │    Pandas + TextBlob    │  │
│  └───────────────┘  │  └─────────────────────────┘  │
│     Port 3000       │        Port 8000              │
└─────────────────────┴───────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    │  /data      │
                    │  CSV Files  │
                    └─────────────┘
```

**Key decisions:**
- **Volume mounts** for hot-reload during development
- **Named volumes** for `node_modules` and `.next` (avoids permission conflicts)
- **SELinux-compatible** (`:Z` flags for Fedora/RHEL)

---

## 📡 API Reference

### Get Scored Tickets

```bash
GET /tickets/scored?status=open&scenario=default
```

**Parameters:**
- `status`: Filter by ticket status (`open`, `closed`, or omit for all)
- `scenario`: Data scenario (`default`, `hidden_fire`, `noise`)
- `limit`: Maximum results to return

**Response:**
```json
[
  {
    "ticket_id": "f6bdbf55",
    "client_id": "ENT-001",
    "category": "Payments",
    "priority_score": 100.0,
    "sentiment_score": 0.0,
    "silence_days": 6.2,
    "mrr": 8500.0,
    "is_recurrent": true
  }
]
```

### Get High-Risk Tickets

```bash
GET /tickets/high-risk?min_score=70&limit=10
```

Returns tickets above the specified priority threshold.

### Get Calibration Info

```bash
GET /calibration
```

Returns the calculated thresholds (MRR percentiles, recurrence rates, etc.)

---

## 📁 Project Structure

```
support-ticket-priorization/
├── backend/
│   ├── main.py           # FastAPI application
│   ├── scorer.py         # Priority scoring engine
│   ├── requirements.txt  # Python dependencies
│   └── Dockerfile
├── frontend/
│   ├── src/app/          # Next.js pages
│   ├── package.json
│   └── Dockerfile
├── data/
│   ├── tickets.csv
│   ├── clients.csv
│   ├── conversations.csv
│   └── ticket_history.csv
├── docker-compose.yml
└── README.md
```

---

## 🎯 Key Takeaways

1. **Sentiment is one signal, not the signal.** Behavioral patterns (silence, recurrence) are stronger churn predictors.

2. **High-value clients need priority escalation.** A $50 complaint and an $8,500 complaint are not equal business risks.

3. **Time-based signals decay.** Implementing proper time anchoring prevents false positives in historical data.

4. **The best prioritization is explainable.** Each score component is visible and auditable.

---
