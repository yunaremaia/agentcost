"""SQLite parser for Hermes agent state database."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List

from agentcost.cost import TokenUsage


class HermesSQLiteParser:
    """Parse Hermes state.db SQLite database for token usage."""
    
    def __init__(self, db_path: Path = None):
        """Initialize with path to state.db."""
        if db_path is None:
            db_path = Path.home() / ".hermes" / "state.db"
        self.db_path = db_path
    
    def parse(self) -> List[TokenUsage]:
        """Parse all session_model_usage entries from the database."""
        usages = []
        
        if not self.db_path.exists():
            return usages
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT session_id, model, input_tokens, output_tokens, 
                           cache_read_tokens, cache_write_tokens, 
                           estimated_cost_usd, actual_cost_usd,
                           first_seen, last_seen
                    FROM session_model_usage
                    ORDER BY last_seen DESC
                """)
                
                for row in cursor.fetchall():
                    # Convert Unix timestamps to datetime
                    first_seen = datetime.fromtimestamp(row["first_seen"]) if row["first_seen"] else None
                    last_seen = datetime.fromtimestamp(row["last_seen"]) if row["last_seen"] else None
                    
                    usage = TokenUsage(
                        model=row["model"],
                        input_tokens=row["input_tokens"] or 0,
                        output_tokens=row["output_tokens"] or 0,
                        cache_read_tokens=row["cache_read_tokens"] or 0,
                        cache_write_tokens=row["cache_write_tokens"] or 0,
                        timestamp=last_seen or first_seen,
                        agent_id="hermes-agent",
                        session_id=row["session_id"],
                    )
                    usages.append(usage)
        except (sqlite3.Error, OSError):
            pass
        
        return usages
    
    def get_date_range(self) -> tuple:
        """Get the date range of available data."""
        if not self.db_path.exists():
            return None, None
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MIN(first_seen), MAX(last_seen) FROM session_model_usage")
                row = cursor.fetchone()
                
                if row and row[0] and row[1]:
                    return datetime.fromtimestamp(row[0]), datetime.fromtimestamp(row[1])
        except (sqlite3.Error, OSError):
            pass
        
        return None, None
