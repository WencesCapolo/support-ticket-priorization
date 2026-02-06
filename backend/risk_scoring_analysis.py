"""
Weighted Risk Scoring Model for Support Ticket Prioritization

This script analyzes customer support ticket data and generates a data-driven
prioritization model. All parameters (MRR tiers, recurrence rates, silence thresholds)
are derived from actual data distributions.

Date: 2026-02-06
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Dict

# ============================================================================
# CONSTANTS
# ============================================================================

DATA_DIR = Path(__file__).parent.parent / "data"
RECURRENCE_WINDOW_DAYS = 30
RECURRENCE_THRESHOLD = 0.20  # 20% recurrence rate triggers risk multiplier


# ============================================================================
# DATA LOADING
# ============================================================================

def load_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all CSV files and perform basic validation."""
    print("=" * 80)
    print("LOADING DATA")
    print("=" * 80)
    
    clients = pd.read_csv(DATA_DIR / "clients.csv")
    conversations = pd.read_csv(DATA_DIR / "conversations.csv")
    tickets = pd.read_csv(DATA_DIR / "tickets.csv")
    ticket_history = pd.read_csv(DATA_DIR / "ticket_history.csv")
    
    print(f"✓ Loaded {len(clients)} clients")
    print(f"✓ Loaded {len(conversations)} conversations")
    print(f"✓ Loaded {len(tickets)} tickets")
    print(f"✓ Loaded {len(ticket_history)} historical ticket records")
    print()
    
    return clients, conversations, tickets, ticket_history


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

def engineer_recurrence_feature(
    tickets: pd.DataFrame, 
    ticket_history: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate recurrence: Did the same client have a ticket in the same 
    category within the previous 30 days?
    """
    # Combine current tickets with historical data
    all_tickets = pd.concat([
        tickets[['ticket_id', 'client_id', 'category', 'created_at']],
        ticket_history[['ticket_id', 'client_id', 'category', 'created_at']]
    ]).drop_duplicates()
    
    # Convert dates
    all_tickets['created_at'] = pd.to_datetime(all_tickets['created_at'])
    tickets_copy = tickets.copy()
    tickets_copy['created_at'] = pd.to_datetime(tickets_copy['created_at'])
    
    # For each ticket, check if there was a previous ticket in same category
    tickets_copy['is_recurrent'] = False
    
    for idx, ticket in tickets_copy.iterrows():
        # Find previous tickets from same client in same category
        previous_tickets = all_tickets[
            (all_tickets['client_id'] == ticket['client_id']) &
            (all_tickets['category'] == ticket['category']) &
            (all_tickets['created_at'] < ticket['created_at']) &
            (all_tickets['created_at'] >= ticket['created_at'] - timedelta(days=RECURRENCE_WINDOW_DAYS))
        ]
        
        if len(previous_tickets) > 0:
            tickets_copy.at[idx, 'is_recurrent'] = True
    
    return tickets_copy


def engineer_silence_feature(
    tickets: pd.DataFrame, 
    conversations: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate silence: Days since last customer message (ignoring agent replies).
    """
    conversations_copy = conversations.copy()
    conversations_copy['sent_at'] = pd.to_datetime(conversations_copy['sent_at'])
    
    # Filter only customer messages
    customer_messages = conversations_copy[
        conversations_copy['sender_type'] == 'customer'
    ].copy()
    
    # Get last customer message for each ticket
    last_customer_msg = customer_messages.sort_values('sent_at').groupby('ticket_id').last()
    
    # Calculate days since last message
    current_date = datetime.now()
    tickets_copy = tickets.copy()
    tickets_copy['silence_days'] = 0.0
    
    for idx, ticket in tickets_copy.iterrows():
        if ticket['ticket_id'] in last_customer_msg.index:
            last_msg_date = last_customer_msg.loc[ticket['ticket_id'], 'sent_at']
            silence = (current_date - last_msg_date).days
            tickets_copy.at[idx, 'silence_days'] = max(0, silence)
        else:
            # No customer messages - set high silence value
            tickets_copy.at[idx, 'silence_days'] = 999
    
    return tickets_copy


def engineer_duration_feature(tickets: pd.DataFrame) -> pd.DataFrame:
    """Calculate ticket duration: Days since ticket was created."""
    tickets_copy = tickets.copy()
    tickets_copy['created_at'] = pd.to_datetime(tickets_copy['created_at'])
    
    current_date = datetime.now()
    tickets_copy['duration_days'] = (
        current_date - tickets_copy['created_at']
    ).dt.days
    
    return tickets_copy


def engineer_all_features(
    tickets: pd.DataFrame,
    ticket_history: pd.DataFrame,
    conversations: pd.DataFrame,
    clients: pd.DataFrame
) -> pd.DataFrame:
    """Apply all feature engineering steps."""
    print("=" * 80)
    print("FEATURE ENGINEERING")
    print("=" * 80)
    
    # Merge with client data to get MRR
    tickets_enriched = tickets.merge(
        clients[['client_id', 'mrr', 'account_tier']], 
        on='client_id', 
        how='left'
    )
    
    # Apply feature engineering
    print("✓ Calculating recurrence features...")
    tickets_enriched = engineer_recurrence_feature(tickets_enriched, ticket_history)
    
    print("✓ Calculating silence features...")
    tickets_enriched = engineer_silence_feature(tickets_enriched, conversations)
    
    print("✓ Calculating duration features...")
    tickets_enriched = engineer_duration_feature(tickets_enriched)
    
    # Filter to open tickets only
    open_tickets = tickets_enriched[tickets_enriched['status'] == 'open'].copy()
    
    print(f"✓ Feature engineering complete: {len(open_tickets)} open tickets")
    print()
    
    return open_tickets


# ============================================================================
# STATISTICAL CALIBRATION
# ============================================================================

def calculate_mrr_thresholds(tickets: pd.DataFrame) -> Dict[str, float]:
    """Calculate MRR percentiles to define value tiers."""
    mrr_values = tickets['mrr'].dropna()
    
    thresholds = {
        'p50': mrr_values.quantile(0.50),
        'p75': mrr_values.quantile(0.75),
        'p90': mrr_values.quantile(0.90),
        'mean': mrr_values.mean(),
        'median': mrr_values.median(),
    }
    
    return thresholds


def calculate_recurrence_probabilities(tickets: pd.DataFrame) -> pd.DataFrame:
    """Calculate recurrence rate for each ticket category."""
    recurrence_by_category = tickets.groupby('category').agg(
        total_tickets=('ticket_id', 'count'),
        recurrent_tickets=('is_recurrent', 'sum')
    ).reset_index()
    
    recurrence_by_category['recurrence_rate'] = (
        recurrence_by_category['recurrent_tickets'] / 
        recurrence_by_category['total_tickets']
    )
    
    return recurrence_by_category.sort_values('recurrence_rate', ascending=False)


def calculate_silence_distribution(tickets: pd.DataFrame) -> Dict[str, float]:
    """Calculate silence duration distribution for open tickets."""
    silence_values = tickets['silence_days'].replace(999, np.nan).dropna()
    
    distribution = {
        'median': silence_values.median(),
        'p75': silence_values.quantile(0.75),
        'p90': silence_values.quantile(0.90),
        'mean': silence_values.mean(),
    }
    
    return distribution


def print_calibration_table(
    mrr_thresholds: Dict[str, float],
    recurrence_probs: pd.DataFrame,
    silence_dist: Dict[str, float]
) -> None:
    """Print comprehensive calibration table with statistical justifications."""
    print("=" * 80)
    print("CALIBRATION TABLE: DATA-DRIVEN PARAMETERS")
    print("=" * 80)
    print()
    
    # MRR Tiers
    print("📊 VALUE TIERS (Based on MRR Distribution)")
    print("-" * 80)
    print(f"  Tier 1 (Low):      MRR < ${mrr_thresholds['p50']:.2f}      → Weight: 1 point")
    print(f"  Tier 2 (Medium):   MRR ${mrr_thresholds['p50']:.2f} - ${mrr_thresholds['p75']:.2f}  → Weight: 2 points")
    print(f"  Tier 3 (High):     MRR ${mrr_thresholds['p75']:.2f} - ${mrr_thresholds['p90']:.2f} → Weight: 3 points")
    print(f"  Tier 4 (Critical): MRR > ${mrr_thresholds['p90']:.2f}     → Weight: 5 points")
    print()
    print(f"  📝 JUSTIFICATION: Weights are based on percentile distribution.")
    print(f"     - 50% of clients have MRR below ${mrr_thresholds['p50']:.2f} (baseline)")
    print(f"     - Top 10% of clients (>${mrr_thresholds['p90']:.2f}) get 5x weight due to revenue impact")
    print()
    
    # Recurrence Probabilities
    print("📊 RECURRENCE RISK (By Category)")
    print("-" * 80)
    for _, row in recurrence_probs.iterrows():
        multiplier = "1.5x 🔥" if row['recurrence_rate'] > RECURRENCE_THRESHOLD else "1.0x"
        print(f"  {row['category']:<20} {row['recurrence_rate']*100:>5.1f}%  ({row['total_tickets']:>3} tickets)  → {multiplier}")
    
    print()
    highest_recurrence = recurrence_probs.iloc[0]
    print(f"  📝 JUSTIFICATION: '{highest_recurrence['category']}' category has the highest")
    print(f"     recurrence rate of {highest_recurrence['recurrence_rate']*100:.1f}%, meaning customers with these issues")
    print(f"     are more likely to experience repeat problems. Categories with >20%")
    print(f"     recurrence get a 1.5x risk multiplier to prioritize proactive resolution.")
    print()
    
    # Silence Distribution
    print("📊 URGENCY THRESHOLDS (Based on Silence Duration)")
    print("-" * 80)
    print(f"  Low Urgency:     Silence < {silence_dist['median']:.1f} days       → Weight: 1 point")
    print(f"  Medium Urgency:  Silence {silence_dist['median']:.1f} - {silence_dist['p75']:.1f} days  → Weight: 2 points")
    print(f"  High Urgency:    Silence > {silence_dist['p75']:.1f} days       → Weight: 3 points")
    print()
    print(f"  📝 JUSTIFICATION: Median silence time is {silence_dist['median']:.1f} days.")
    print(f"     Tickets silent longer than {silence_dist['p75']:.1f} days (75th percentile)")
    print(f"     are at risk of customer frustration and should be prioritized.")
    print()
    
    print("=" * 80)
    print()


# ============================================================================
# SCORING LOGIC
# ============================================================================

def calculate_value_weight(mrr: float, thresholds: Dict[str, float]) -> int:
    """Assign value weight based on MRR quartiles."""
    if pd.isna(mrr):
        return 1
    elif mrr >= thresholds['p90']:
        return 5  # Top 10% - Critical
    elif mrr >= thresholds['p75']:
        return 3  # Top 25% - High
    elif mrr >= thresholds['p50']:
        return 2  # Top 50% - Medium
    else:
        return 1  # Bottom 50% - Low


def calculate_urgency_weight(silence: float, distribution: Dict[str, float]) -> int:
    """Assign urgency weight based on silence duration."""
    if silence >= distribution['p75']:
        return 3  # High urgency
    elif silence >= distribution['median']:
        return 2  # Medium urgency
    else:
        return 1  # Low urgency


def calculate_risk_multiplier(
    category: str, 
    recurrence_probs: pd.DataFrame
) -> float:
    """Apply risk multiplier for high-recurrence categories."""
    category_row = recurrence_probs[recurrence_probs['category'] == category]
    
    if len(category_row) > 0:
        recurrence_rate = category_row.iloc[0]['recurrence_rate']
        if recurrence_rate > RECURRENCE_THRESHOLD:
            return 1.5
    
    return 1.0


def calculate_priority_scores(
    tickets: pd.DataFrame,
    mrr_thresholds: Dict[str, float],
    silence_dist: Dict[str, float],
    recurrence_probs: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate priority score for each ticket:
    Priority Score = (Value_Weight + Urgency_Weight) * Risk_Multiplier
    """
    tickets_copy = tickets.copy()
    
    tickets_copy['value_weight'] = tickets_copy['mrr'].apply(
        lambda x: calculate_value_weight(x, mrr_thresholds)
    )
    
    tickets_copy['urgency_weight'] = tickets_copy['silence_days'].apply(
        lambda x: calculate_urgency_weight(x, silence_dist)
    )
    
    tickets_copy['risk_multiplier'] = tickets_copy['category'].apply(
        lambda x: calculate_risk_multiplier(x, recurrence_probs)
    )
    
    tickets_copy['priority_score'] = (
        (tickets_copy['value_weight'] + tickets_copy['urgency_weight']) * 
        tickets_copy['risk_multiplier']
    )
    
    return tickets_copy


# ============================================================================
# REPORTING
# ============================================================================

def print_top_risk_tickets(tickets: pd.DataFrame, top_n: int = 10) -> None:
    """Print top N high-risk tickets with detailed breakdown."""
    print("=" * 80)
    print(f"TOP {top_n} HIGH-RISK TICKETS (Ranked by Priority Score)")
    print("=" * 80)
    print()
    
    top_tickets = tickets.nlargest(top_n, 'priority_score')
    
    for i, (_, ticket) in enumerate(top_tickets.iterrows(), 1):
        print(f"#{i} | Ticket ID: {ticket['ticket_id']} | Score: {ticket['priority_score']:.1f}")
        print(f"    Client ID: {ticket['client_id']} | MRR: ${ticket['mrr']:.2f}")
        print(f"    Category: {ticket['category']} | Status: {ticket['status']}")
        print(f"    📍 Contributing Factors:")
        print(f"       • Value Weight: {ticket['value_weight']} (MRR-based)")
        print(f"       • Urgency Weight: {ticket['urgency_weight']} (Silence: {ticket['silence_days']:.0f} days)")
        print(f"       • Risk Multiplier: {ticket['risk_multiplier']}x (Recurrence: {ticket['is_recurrent']})")
        print(f"       • Duration: {ticket['duration_days']} days open")
        print()
    
    print("=" * 80)
    print()


def identify_hidden_fire_pattern(
    tickets: pd.DataFrame,
    mrr_thresholds: Dict[str, float],
    silence_dist: Dict[str, float]
) -> pd.DataFrame:
    """
    Identify "Hidden Fire" tickets:
    - High MRR (top 25%)
    - Silenced > 5 days
    - Critical category (high recurrence rate)
    """
    hidden_fire = tickets[
        (tickets['mrr'] >= mrr_thresholds['p75']) &  # High value
        (tickets['silence_days'] > 5) &  # Silenced
        (tickets['risk_multiplier'] > 1.0)  # Critical category
    ].copy()
    
    return hidden_fire.sort_values('priority_score', ascending=False)


def print_hidden_fire_tickets(hidden_fire: pd.DataFrame) -> None:
    """Print tickets matching the 'Hidden Fire' pattern."""
    print("=" * 80)
    print("🔥 HIDDEN FIRE PATTERN: High-Value Silenced Critical Tickets")
    print("=" * 80)
    print()
    
    if len(hidden_fire) == 0:
        print("✓ No 'Hidden Fire' tickets found - Good news!")
        print()
        print("=" * 80)
        print()
        return
    
    print(f"⚠️  ALERT: {len(hidden_fire)} tickets match the 'Hidden Fire' pattern")
    print("   These high-value clients have been silent on critical issues.")
    print()
    
    for i, (_, ticket) in enumerate(hidden_fire.iterrows(), 1):
        print(f"#{i} | Ticket ID: {ticket['ticket_id']} | Score: {ticket['priority_score']:.1f}")
        print(f"    Client ID: {ticket['client_id']} | MRR: ${ticket['mrr']:.2f} (Top 25%)")
        print(f"    Category: {ticket['category']} (High Recurrence)")
        print(f"    ⏰ Silenced for {ticket['silence_days']:.0f} days")
        print(f"    ⚠️  Risk: Customer may be churning silently!")
        print()
    
    print("=" * 80)
    print()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Execute the complete risk scoring analysis pipeline."""
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  WEIGHTED RISK SCORING MODEL FOR SUPPORT TICKET PRIORITIZATION".center(78) + "║")
    print("║" + "  Data-Driven Parameter Calibration".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    # Step 1: Load Data
    clients, conversations, tickets, ticket_history = load_data()
    
    # Step 2: Feature Engineering
    tickets_enriched = engineer_all_features(
        tickets, ticket_history, conversations, clients
    )
    
    # Step 3: Statistical Calibration
    print("=" * 80)
    print("STATISTICAL CALIBRATION")
    print("=" * 80)
    print("✓ Calculating MRR thresholds...")
    mrr_thresholds = calculate_mrr_thresholds(tickets_enriched)
    
    print("✓ Calculating recurrence probabilities...")
    recurrence_probs = calculate_recurrence_probabilities(tickets_enriched)
    
    print("✓ Calculating silence distribution...")
    silence_dist = calculate_silence_distribution(tickets_enriched)
    print()
    
    # Step 4: Print Calibration Table
    print_calibration_table(mrr_thresholds, recurrence_probs, silence_dist)
    
    # Step 5: Calculate Priority Scores
    print("=" * 80)
    print("CALCULATING PRIORITY SCORES")
    print("=" * 80)
    tickets_scored = calculate_priority_scores(
        tickets_enriched, mrr_thresholds, silence_dist, recurrence_probs
    )
    print(f"✓ Calculated scores for {len(tickets_scored)} open tickets")
    print()
    
    # Step 6: Generate Reports
    print_top_risk_tickets(tickets_scored, top_n=10)
    
    # Step 7: Identify Hidden Fire Pattern
    hidden_fire = identify_hidden_fire_pattern(
        tickets_scored, mrr_thresholds, silence_dist
    )
    print_hidden_fire_tickets(hidden_fire)
    
    # Step 8: Summary Statistics
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"  Total Open Tickets Analyzed: {len(tickets_scored)}")
    print(f"  Recurrent Tickets: {tickets_scored['is_recurrent'].sum()} ({tickets_scored['is_recurrent'].mean()*100:.1f}%)")
    print(f"  Average Priority Score: {tickets_scored['priority_score'].mean():.2f}")
    print(f"  High-Risk Tickets (Score > 8): {len(tickets_scored[tickets_scored['priority_score'] > 8])}")
    print(f"  Hidden Fire Tickets: {len(hidden_fire)}")
    print()
    print("=" * 80)
    print()
    print("✅ Analysis Complete!")
    print()


if __name__ == "__main__":
    main()
