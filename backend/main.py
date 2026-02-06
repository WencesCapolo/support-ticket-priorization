"""
FastAPI application for ticket prioritization scoring.

Provides REST API endpoints to get prioritized support tickets with risk scores.
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel, Field
from scorer import TicketScorer

app = FastAPI(
    title="Support Ticket Prioritization API",
    description="REST API for calculating risk-based priority scores for support tickets",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Response Models
class TicketScore(BaseModel):
    """Model for a scored ticket."""
    ticket_id: str
    client_id: str
    category: str
    status: str
    subject: Optional[str] = None
    created_at: str
    mrr: Optional[float] = None
    account_tier: Optional[str] = None
    is_recurrent: bool
    silence_days: float
    duration_days: int
    priority_score: float = Field(..., description="Calculated priority score (1-12 range)")
    sentiment_score: Optional[float] = None


class CalibrationInfo(BaseModel):
    """Model for calibration thresholds."""
    mrr_tiers: dict
    silence_thresholds: dict
    recurrence_rates: dict
    recurrence_threshold: float


# Initialize scorer
scorer = TicketScorer()


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "service": "Support Ticket Prioritization API",
        "status": "operational",
        "version": "1.0.0"
    }


from pathlib import Path

# Scenario data directory mapping
SCENARIO_DIRS = {
    "default": "data",
    "hidden_fire": "data/scenario_hidden_fire",
    "noise": "data/scenario_noise",
}


def get_scorer_for_scenario(scenario: str) -> TicketScorer:
    """Get a TicketScorer configured for the specified scenario."""
    # Use /app as base in container, or parent of current file for local dev
    base_dir = Path("/app") if Path("/app/data").exists() else Path(__file__).parent.parent
    scenario_path = SCENARIO_DIRS.get(scenario, SCENARIO_DIRS["default"])
    data_dir = base_dir / scenario_path
    return TicketScorer(data_dir=data_dir)


@app.get("/tickets/scored", response_model=List[TicketScore], tags=["Tickets"])
async def get_scored_tickets(
    status: Optional[str] = Query(
        "open", 
        description="Filter by ticket status (e.g., 'open', 'closed', or None for all)"
    ),
    limit: Optional[int] = Query(
        None, 
        description="Limit number of results (default: all tickets)",
        ge=1
    ),
    scenario: str = Query(
        "default",
        description="Data scenario: 'default', 'hidden_fire', or 'noise'"
    )
):
    """
    Get all tickets with calculated priority scores.
    
    **Score Calculation:**
    - Priority Score = (Value_Weight + Urgency_Weight) × Risk_Multiplier
    - Value Weight (1-5): Based on client MRR percentiles
    - Urgency Weight (1-3): Based on silence duration
    - Risk Multiplier (1.0x or 1.5x): Based on category recurrence rate
    
    **Scenarios:**
    - `default`: Original provided dataset
    - `hidden_fire`: 5 Enterprise silent tickets (high-value at risk)
    - `noise`: 150 Starter angry tickets (low-value noise)
    
    **Returns:**
    - List of tickets sorted by priority score (highest first)
    """
    # Get scorer for the specified scenario
    scenario_scorer = get_scorer_for_scenario(scenario)
    
    # Score all tickets
    tickets = scenario_scorer.score_tickets(status_filter=status)
    
    # Apply limit if specified
    if limit:
        tickets = tickets[:limit]
    
    return tickets


@app.get("/calibration", response_model=CalibrationInfo, tags=["Configuration"])
async def get_calibration():
    """
    Get current calibration thresholds used for scoring.
    
    These thresholds are automatically calculated from the data distribution.
    Run the /tickets/scored endpoint first to calibrate the model.
    """
    return scorer.get_calibration_info()


@app.get("/tickets/high-risk", response_model=List[TicketScore], tags=["Tickets"])
async def get_high_risk_tickets(
    min_score: float = Query(
        8.0, 
        description="Minimum priority score threshold",
        ge=0
    ),
    limit: Optional[int] = Query(
        10, 
        description="Maximum number of tickets to return",
        ge=1
    )
):
    """
    Get high-risk tickets above a certain priority score threshold.
    
    Default threshold is 8.0, which typically includes:
    - High-value clients (top 25% MRR)
    - High urgency (significant silence)
    - High-recurrence categories
    """
    # Score all open tickets
    tickets = scorer.score_tickets(status_filter='open')
    
    # Filter by minimum score
    high_risk = [t for t in tickets if t['priority_score'] >= min_score]
    
    # Apply limit
    if limit:
        high_risk = high_risk[:limit]
    
    return high_risk


@app.get("/tickets/hidden-fire", response_model=List[TicketScore], tags=["Tickets"])
async def get_hidden_fire_tickets():
    """
    Get "Hidden Fire" tickets: High-value clients silenced on critical issues.
    
    **Criteria:**
    - MRR in top 25%
    - Silenced > 5 days
    - High-recurrence category (>20% recurrence rate)
    
    These tickets represent the highest churn risk.
    """
    # Score all open tickets
    tickets = scorer.score_tickets(status_filter='open')
    
    # Ensure we have calibration
    if scorer.thresholds is None:
        return []
    
    # Filter for hidden fire pattern
    hidden_fire = [
        t for t in tickets
        if (
            t.get('mrr', 0) >= scorer.thresholds.mrr_p75 and
            t.get('silence_days', 0) > 5 and
            scorer.calculate_risk_multiplier(t['category']) > 1.0
        )
    ]
    
    return hidden_fire
