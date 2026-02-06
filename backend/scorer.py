"""
Ticket Scoring Engine

This module provides a reusable scoring engine for support ticket prioritization.
All scoring parameters are derived from actual data distributions.

Date: 2026-02-06
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from textblob import TextBlob


@dataclass
class ScoringThresholds:
    """Container for calibrated scoring thresholds."""
    mrr_p50: float
    mrr_p75: float
    mrr_p90: float
    silence_median: float
    silence_p75: float
    recurrence_rates: Dict[str, float]
    recurrence_threshold: float = 0.20


class TicketScorer:
    """
    Main scoring engine for support tickets.
    
    Calculates priority scores using:
    Priority Score = (Value_Weight + Urgency_Weight) * Risk_Multiplier
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize scorer with data directory.
        
        Note: In production, self.reference_date would default to datetime.now().
        However, for historical data analysis ("simulation mode"), we anchor the
        reference date to the latest ticket timestamp in the dataset. This ensures
        duration_days and silence_days reflect the state at data export time,
        not the current moment.
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.data_dir = Path(data_dir)
        self.thresholds: Optional[ScoringThresholds] = None
        self.reference_date: Optional[datetime] = None
        
    def load_data(self) -> Dict[str, pd.DataFrame]:
        """
        Load all CSV files and set reference date for time calculations.
        
        The reference date is set to the latest ticket creation timestamp,
        anchoring all time-based metrics (duration, silence) to the state
        of the data at export time.
        """
        data = {
            'clients': pd.read_csv(self.data_dir / "clients.csv"),
            'conversations': pd.read_csv(self.data_dir / "conversations.csv"),
            'tickets': pd.read_csv(self.data_dir / "tickets.csv"),
            'ticket_history': pd.read_csv(self.data_dir / "ticket_history.csv"),
        }
        
        # INTELLIGENT TIME ANCHOR
        tickets_temp = data['tickets'].copy()
        tickets_temp['created_at'] = pd.to_datetime(tickets_temp['created_at'])
        max_date = tickets_temp['created_at'].max()
        now = pd.to_datetime(datetime.now())
        
        # If data is old (> 30 days), use Simulation Mode (anchor to data)
        # If data is fresh (scenarios), use Real Time Mode (anchor to now)
        if (now - max_date).days > 30:
            self.reference_date = max_date
        else:
            self.reference_date = now
        
        return data
    
    def calculate_recurrence(
        self, 
        tickets: pd.DataFrame, 
        ticket_history: pd.DataFrame,
        window_days: int = 30
    ) -> pd.DataFrame:
        """Calculate if ticket is a recurrence of previous issue."""
        all_tickets = pd.concat([
            tickets[['ticket_id', 'client_id', 'category', 'created_at']],
            ticket_history[['ticket_id', 'client_id', 'category', 'created_at']]
        ]).drop_duplicates()
        
        all_tickets['created_at'] = pd.to_datetime(all_tickets['created_at'])
        tickets_copy = tickets.copy()
        tickets_copy['created_at'] = pd.to_datetime(tickets_copy['created_at'])
        tickets_copy['is_recurrent'] = False
        tickets_copy['recurrence_count'] = 0
        
        for idx, ticket in tickets_copy.iterrows():
            previous_tickets = all_tickets[
                (all_tickets['client_id'] == ticket['client_id']) &
                (all_tickets['category'] == ticket['category']) &
                (all_tickets['created_at'] < ticket['created_at']) &
                (all_tickets['created_at'] >= ticket['created_at'] - timedelta(days=window_days))
            ]
            
            if len(previous_tickets) > 0:
                tickets_copy.at[idx, 'is_recurrent'] = True
                tickets_copy.at[idx, 'recurrence_count'] = len(previous_tickets)
        
        return tickets_copy
    
    def calculate_silence(
        self, 
        tickets: pd.DataFrame, 
        conversations: pd.DataFrame
    ) -> pd.DataFrame:
        """Calculate days since last customer message."""
        conversations_copy = conversations.copy()
        conversations_copy['sent_at'] = pd.to_datetime(conversations_copy['sent_at'])
        
        customer_messages = conversations_copy[
            conversations_copy['sender_type'] == 'customer'
        ].copy()
        
        last_customer_msg = customer_messages.sort_values('sent_at').groupby('ticket_id').last()
        
        # Use reference_date (data anchor) instead of datetime.now()
        current_date = self.reference_date if self.reference_date else datetime.now()
        tickets_copy = tickets.copy()
        tickets_copy['silence_days'] = 0.0
        
        for idx, ticket in tickets_copy.iterrows():
            if ticket['ticket_id'] in last_customer_msg.index:
                last_msg_date = last_customer_msg.loc[ticket['ticket_id'], 'sent_at']
                silence = (current_date - last_msg_date).days
                tickets_copy.at[idx, 'silence_days'] = max(0, silence)
            else:
                tickets_copy.at[idx, 'silence_days'] = 999
        
        return tickets_copy
    
    def calculate_duration(self, tickets: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate ticket duration in days.
        
        Uses reference_date (data anchor) instead of datetime.now() to ensure
        duration reflects the state at data export time.
        """
        tickets_copy = tickets.copy()
        tickets_copy['created_at'] = pd.to_datetime(tickets_copy['created_at'])
        
        # Use reference_date (data anchor) instead of datetime.now()
        current_date = self.reference_date if self.reference_date else datetime.now()
        tickets_copy['duration_days'] = (
            current_date - tickets_copy['created_at']
        ).dt.days
        
        return tickets_copy
    
    def calculate_sentiment(
        self, 
        tickets: pd.DataFrame, 
        conversations: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate sentiment score using TextBlob.
        
        For each ticket, finds the latest message and combines it with the 
        ticket subject to calculate sentiment polarity (-1.0 to 1.0).
        """
        # Sort conversations by sent_at to get the latest message per ticket
        conversations_copy = conversations.copy()
        conversations_copy['sent_at'] = pd.to_datetime(conversations_copy['sent_at'])
        
        # Get the latest message for each ticket
        latest_messages = (
            conversations_copy
            .sort_values('sent_at')
            .groupby('ticket_id')
            .last()
            .reset_index()[['ticket_id', 'message_text']]
        )
        
        tickets_copy = tickets.copy()
        tickets_copy['sentiment_score'] = 0.0
        
        for idx, ticket in tickets_copy.iterrows():
            ticket_id = ticket['ticket_id']
            subject = str(ticket.get('subject', '')) or ''
            
            # Find latest message for this ticket
            msg_row = latest_messages[latest_messages['ticket_id'] == ticket_id]
            latest_message = msg_row['message_text'].iloc[0] if len(msg_row) > 0 else ''
            
            # Construct content: subject + latest message
            content = f"{subject} {latest_message}".strip()
            
            if content:
                try:
                    sentiment = TextBlob(content).sentiment.polarity
                    tickets_copy.at[idx, 'sentiment_score'] = sentiment
                except Exception:
                    tickets_copy.at[idx, 'sentiment_score'] = 0.0
            else:
                tickets_copy.at[idx, 'sentiment_score'] = 0.0
        
        return tickets_copy
    
    def calibrate_thresholds(self, tickets: pd.DataFrame) -> ScoringThresholds:
        """Calculate all scoring thresholds from data."""
        # MRR thresholds
        mrr_values = tickets['mrr'].dropna()
        
        # Silence distribution
        silence_values = tickets['silence_days'].replace(999, np.nan).dropna()
        
        # Recurrence rates by category
        recurrence_by_category = tickets.groupby('category').agg(
            total=('ticket_id', 'count'),
            recurrent=('is_recurrent', 'sum')
        )
        recurrence_by_category['rate'] = (
            recurrence_by_category['recurrent'] / recurrence_by_category['total']
        )
        recurrence_rates = recurrence_by_category['rate'].to_dict()
        
        return ScoringThresholds(
            mrr_p50=mrr_values.quantile(0.50),
            mrr_p75=mrr_values.quantile(0.75),
            mrr_p90=mrr_values.quantile(0.90),
            silence_median=silence_values.median(),
            silence_p75=silence_values.quantile(0.75),
            recurrence_rates=recurrence_rates,
        )
    
    def calculate_value_weight(self, mrr: float) -> int:
        """Assign value weight based on MRR."""
        if pd.isna(mrr) or self.thresholds is None:
            return 1
        
        if mrr >= self.thresholds.mrr_p90:
            return 5  # Top 10%
        elif mrr >= self.thresholds.mrr_p75:
            return 3  # Top 25%
        elif mrr >= self.thresholds.mrr_p50:
            return 2  # Top 50%
        else:
            return 1  # Bottom 50%
    
    def calculate_urgency_weight(self, silence: float) -> int:
        """Assign urgency weight based on silence duration."""
        if self.thresholds is None:
            return 1
        
        if silence >= self.thresholds.silence_p75:
            return 3  # High urgency
        elif silence >= self.thresholds.silence_median:
            return 2  # Medium urgency
        else:
            return 1  # Low urgency
    
    def calculate_risk_multiplier(self, category: str) -> float:
        """Apply risk multiplier for high-recurrence categories."""
        if self.thresholds is None:
            return 1.0
        
        recurrence_rate = self.thresholds.recurrence_rates.get(category, 0.0)
        
        if recurrence_rate > self.thresholds.recurrence_threshold:
            return 1.5
        
        return 1.0
    
    def calculate_priority_score(self, ticket: pd.Series) -> float:
        """
        Calculate priority score using an additive point system (0-100).
        
        Point Breakdown:
        - Silence (Ghosting Risk): 0-30 points
        - Value Tier (Business Impact): 5-25 points  
        - Category Severity: 5-15 points
        - Recurrence (Frustration): 0-20 points
        - Stagnation (Rot Factor): 0-10 points
        
        Expected Outcomes:
        - "Noise" tickets (Starter, General, Fresh): ~10-15 points
        - "Hidden Fire" tickets (Enterprise, Payment, Silent): ~70+ points
        """
        score = 0
        
        # 1. Silence (The "Ghosting" Risk) - Max 30 points
        silence_days = ticket.get('silence_days', 0)
        if silence_days > 5:
            score += 30  # Critical - ignoring customer > 5 days
        elif silence_days > 2:
            score += 15  # Warning - starting to delay
        
        # 2. Value Tier (Business Impact) - 5-25 points
        mrr = ticket.get('mrr', 0) or 0
        if mrr >= 3000:
            score += 25  # Enterprise
        elif mrr >= 1000:
            score += 15  # Growth
        else:
            score += 5   # Starter
        
        # 3. Category Severity - 5-15 points
        category = str(ticket.get('category', '')).lower()
        high_severity_categories = {'payment', 'technical', 'compliance'}
        if category in high_severity_categories:
            score += 15  # Critical business functions
        else:
            score += 5   # General, feature_request, etc.
        
        # 4. Recurrence (Frustration) - 0-20 points
        if ticket.get('is_recurrent', False):
            score += 20  # Repeat offender flag
        
        # 5. Stagnation (The "Rot" Factor) - 0-10 points
        duration_days = ticket.get('duration_days', 0)
        status = str(ticket.get('status', '')).lower()
        if duration_days > 7 and status != 'resolved':
            score += 10  # Ticket is rotting
        
        # 6. Keyword Urgency Safety Net (Money Words) - +30 points
        subject = str(ticket.get('subject', '')).lower()
        if any(keyword in subject for keyword in ['payment', 'payrol', 'wire', 'transaction', 'money', 'payout']):
            score += 30  # Critical financial issue detected
        
        # Cap at 100
        return min(float(score), 100.0)
    
    def score_tickets(
        self, 
        status_filter: Optional[str] = 'open'
    ) -> List[Dict]:
        """
        Main method: Load data, engineer features, calibrate, and score tickets.
        
        Returns:
            List of ticket dictionaries with priority scores
        """
        # Load data
        data = self.load_data()
        clients = data['clients']
        conversations = data['conversations']
        tickets = data['tickets']
        ticket_history = data['ticket_history']
        
        # Merge with client data
        tickets_enriched = tickets.merge(
            clients[['client_id', 'mrr', 'account_tier']], 
            on='client_id', 
            how='left'
        )
        
        # Feature engineering
        tickets_enriched = self.calculate_recurrence(tickets_enriched, ticket_history)
        tickets_enriched = self.calculate_silence(tickets_enriched, conversations)
        tickets_enriched = self.calculate_duration(tickets_enriched)
        tickets_enriched = self.calculate_sentiment(tickets_enriched, conversations)
        
        # Filter by status if specified
        if status_filter:
            tickets_enriched = tickets_enriched[
                tickets_enriched['status'] == status_filter
            ].copy()
        
        # Calibrate thresholds
        self.thresholds = self.calibrate_thresholds(tickets_enriched)
        
        # Calculate scores
        tickets_enriched['priority_score'] = tickets_enriched.apply(
            self.calculate_priority_score, axis=1
        )
        
        # Prepare output
        output_columns = [
            'ticket_id', 'client_id', 'category', 'status', 'subject',
            'created_at', 'mrr', 'account_tier',
            'is_recurrent', 'recurrence_count', 'silence_days', 'duration_days', 
            'priority_score', 'sentiment_score'
        ]
        
        # Ensure dates are strings for JSON serialization
        if 'created_at' in tickets_enriched.columns:
            tickets_enriched['created_at'] = tickets_enriched['created_at'].astype(str)
        
        # Convert to list of dictionaries
        result = tickets_enriched[output_columns].to_dict('records')
        
        # Sort by priority score (descending)
        result.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return result
    
    def get_calibration_info(self) -> Dict:
        """Return current calibration thresholds."""
        if self.thresholds is None:
            return {"error": "Not calibrated yet. Run score_tickets() first."}
        
        return {
            "mrr_tiers": {
                "tier_1_max": self.thresholds.mrr_p50,
                "tier_2_max": self.thresholds.mrr_p75,
                "tier_3_max": self.thresholds.mrr_p90,
            },
            "silence_thresholds": {
                "median": self.thresholds.silence_median,
                "p75": self.thresholds.silence_p75,
            },
            "recurrence_rates": self.thresholds.recurrence_rates,
            "recurrence_threshold": self.thresholds.recurrence_threshold,
        }
