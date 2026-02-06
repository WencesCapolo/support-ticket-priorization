# Architecture Overview

A detailed breakdown of the system architecture, decision-making logic, and component responsibilities for the Support Ticket Prioritization Engine.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interface                               │
│                    (Next.js Dashboard @ :3000)                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  • Ticket Priority List (sorted by score)                       │ │
│  │  • Sentiment vs Priority Comparison View                        │ │
│  │  • Score Breakdown Tooltips                                     │ │
│  │  • Scenario Selector (default / hidden_fire / noise)            │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP (REST API)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API Layer                                    │
│                    (FastAPI @ :8000)                                 │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  /tickets/scored     → Prioritized ticket list                  │ │
│  │  /tickets/high-risk  → Critical tickets only                    │ │
│  │  /calibration        → Scoring thresholds                       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Scoring Engine                                  │
│                    (scorer.py)                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  TicketScorer Class                                             │ │
│  │  ├── load_data()        → CSV ingestion                         │ │
│  │  ├── calibrate()        → Threshold calculation                 │ │
│  │  ├── calculate_score()  → Multi-signal aggregation              │ │
│  │  └── score_tickets()    → Batch processing                      │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Data Layer                                     │
│                    (/data/*.csv)                                     │
│  ┌───────────────┬───────────────┬────────────────┬───────────────┐ │
│  │  tickets.csv  │  clients.csv  │ conversations  │ ticket_history│ │
│  │  (201 rows)   │  (50 rows)    │ (1145 rows)    │ (301 rows)    │ │
│  └───────────────┴───────────────┴────────────────┴───────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Scoring Engine Design

### Core Problem

**Sentiment ≠ Actionability**

| Example | Sentiment | Business Reality |
|---------|-----------|------------------|
| "We're frustrated with the new regulation changes" | Negative (-0.6) | NOT URGENT — Industry problem, not our issue |
| "Hi, just following up on the delayed payout" | Neutral (0.1) | URGENT — Their money is stuck |

### Solution: Multi-Signal Scoring (0-100)

The scoring engine aggregates 5 weighted signals:

```python
priority_score = (
    silence_points +      # +30 max (agent ghosting)
    keyword_points +      # +30 max (business-critical language)
    tier_points +         # +25 max (revenue protection)
    recurrence_points +   # +20 max (frustration signal)
    stagnation_points     # +10 max (aging tickets)
)
```

---

## Signal Definitions

### 1. Silence Risk (0-30 pts)

**Question:** How long since an agent responded?

| Silence Duration | Points | Rationale |
|------------------|--------|-----------|
| < 2 days | 0 | Normal SLA |
| 2-5 days | 15 | Warning zone |
| > 5 days | 30 | Critical ghosting |

```python
def calculate_silence_points(silence_days: float) -> int:
    if silence_days > 5:
        return 30
    elif silence_days > 2:
        return 15
    return 0
```

### 2. Keyword Urgency (0-30 pts)

**Question:** Does the subject/content indicate business-critical impact?

| Keywords | Points |
|----------|--------|
| "payroll", "payment", "wire", "salary" | 30 |
| "blocked", "failure", "urgent", "asap" | 30 |
| "issue", "problem", "help" | 10 |
| (no matches) | 0 |

### 3. Account Tier (0-25 pts)

**Question:** What's the revenue risk if this client churns?

| MRR Range | Tier | Points |
|-----------|------|--------|
| $3,000+ | Enterprise | 25 |
| $500-2,999 | Growth | 15 |
| < $500 | Starter | 0 |

### 4. Recurrence (0-20 pts)

**Question:** Has this client raised the same issue category before (within 30 days)?

| Recurrence | Points | Rationale |
|------------|--------|-----------|
| Same category repeated | 20 | Frustration compounding |
| First occurrence | 0 | Normal ticket |

### 5. Stagnation (0-10 pts)

**Question:** How long has the ticket been open without resolution?

| Duration | Points |
|----------|--------|
| > 14 days | 10 |
| 7-14 days | 5 |
| < 7 days | 0 |

---

## Time Anchoring (Simulation Mode)

### The Problem

The dataset is **45 days old**. Naive time calculations would:
- Mark all tickets as "stagnant" (14+ days open)
- Show 45+ days of "silence" for every ticket

### The Solution

**Dynamic Time Anchor:** Use the dataset's most recent timestamp as "now."

```python
class TicketScorer:
    def __init__(self, data_dir):
        self.reference_date = None  # Set during calibration
    
    def calibrate(self, df):
        # Use the most recent created_at as our "present moment"
        self.reference_date = df['created_at'].max()
    
    def calculate_silence(self, last_reply_date):
        # Calculate relative to data timeline, not wall clock
        return (self.reference_date - last_reply_date).days
```

This allows accurate scoring on historical data without modification.

---

## Data Relationships

```
┌─────────────┐       ┌─────────────┐
│   clients   │       │   tickets   │
├─────────────┤       ├─────────────┤
│ client_id   │◄──────│ client_id   │
│ company     │       │ ticket_id   │
│ mrr         │       │ category    │
│ tier        │       │ status      │
│ created_at  │       │ created_at  │
└─────────────┘       └──────┬──────┘
                             │
                             │ 1:many
                             ▼
                      ┌─────────────────┐
                      │  conversations  │
                      ├─────────────────┤
                      │ ticket_id       │
                      │ sender_type     │
                      │ message         │
                      │ created_at      │
                      └─────────────────┘
                      
                      ┌─────────────────┐
                      │ ticket_history  │
                      ├─────────────────┤
                      │ client_id       │
                      │ category        │
                      │ created_at      │
                      │ resolved_at     │
                      └─────────────────┘
```

---

## Design Principles

1. **Actionability over Sentiment**  
   Prioritize signals that indicate blocked workflows, not just emotional tone.

2. **Revenue Protection**  
   Enterprise clients represent higher churn cost—weight accordingly.

3. **Recency Matters**  
   Recent issues weighted more heavily than historical patterns.

4. **Transparency**  
   Every score is explainable—CS team can see WHY a ticket is flagged.

5. **Simulation-Ready**  
   Time anchoring allows accurate demos on historical data.

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI routes, scenario handling |
| `backend/scorer.py` | TicketScorer class, scoring logic |
| `frontend/src/app/page.tsx` | Main dashboard component |
| `docker-compose.yml` | Container orchestration |
| `data/*.csv` | Source data files |

---

## Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Frontend | Next.js | 16.x |
| Frontend | React | 19.x |
| Frontend | Tailwind CSS | 4.x |
| Backend | Python | 3.11 |
| Backend | FastAPI | 0.128 |
| Backend | Pandas | 3.0 |
| Backend | TextBlob | 0.19 |
| Infra | Docker/Podman | - |
