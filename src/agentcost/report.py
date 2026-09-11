"""Report generation for cost analysis."""

from typing import List, Dict
from datetime import datetime, timedelta

from agentcost.cost import TokenUsage, CostBreakdown, calculate_cost, summarize_usage


class ReportGenerator:
    """Generate cost reports from token usage data."""

    def daily_summary(self, usages: List[TokenUsage], date: datetime = None) -> Dict:
        """Generate summary for a specific date."""
        if date is None:
            date = datetime.now()
        
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_usages = [
            u for u in usages 
            if u.timestamp and day_start <= u.timestamp < day_end
        ]
        
        return self._build_summary(day_usages, f"Daily ({date.strftime('%Y-%m-%d')})")

    def weekly_summary(self, usages: List[TokenUsage], date: datetime = None) -> Dict:
        """Generate summary for the week containing date."""
        if date is None:
            date = datetime.now()
        
        week_start = date - timedelta(days=date.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        
        week_usages = [
            u for u in usages
            if u.timestamp and week_start <= u.timestamp < week_end
        ]
        
        return self._build_summary(week_usages, f"Weekly ({week_start.strftime('%Y-%m-%d')} to {(week_end - timedelta(days=1)).strftime('%Y-%m-%d')})")

    def monthly_summary(self, usages: List[TokenUsage], date: datetime = None) -> Dict:
        """Generate summary for the month containing date."""
        if date is None:
            date = datetime.now()
        
        month_start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)
        
        month_usages = [
            u for u in usages
            if u.timestamp and month_start <= u.timestamp < month_end
        ]
        
        return self._build_summary(month_usages, f"Monthly ({month_start.strftime('%Y-%m')})")

    def projection(self, usages: List[TokenUsage]) -> Dict:
        """Project monthly cost based on recent usage."""
        if not usages:
            return {"projected_monthly": 0.0, "days_of_data": 0}
        
        # Use last 7 days for projection
        now = datetime.now()
        cutoff = now - timedelta(days=7)
        
        recent = [u for u in usages if u.timestamp and u.timestamp >= cutoff]
        if not recent:
            recent = usages[-50:]  # Last 50 entries
        
        total_cost = sum(calculate_cost(u) for u in recent)
        days = max((now - recent[0].timestamp).days, 1) if recent[0].timestamp else 1
        
        daily_avg = total_cost / days
        projected = daily_avg * 30
        
        return {
            "projected_monthly_usd": round(projected, 2),
            "daily_average_usd": round(daily_avg, 2),
            "days_of_data": days,
            "total_recent_usd": round(total_cost, 2),
        }

    def _build_summary(self, usages: List[TokenUsage], period: str) -> Dict:
        """Build a summary dict from usages."""
        breakdown = summarize_usage(usages)
        
        # By model
        by_model: Dict[str, CostBreakdown] = {}
        for u in usages:
            if u.model not in by_model:
                by_model[u.model] = CostBreakdown()
            by_model[u.model].total_input += u.input_tokens
            by_model[u.model].total_output += u.output_tokens
            by_model[u.model].total_cache_read += u.cache_read_tokens
            by_model[u.model].total_cache_write += u.cache_write_tokens
            by_model[u.model].total_cost_usd += calculate_cost(u)
            by_model[u.model].calls += 1
        
        return {
            "period": period,
            "total_calls": breakdown.calls,
            "total_tokens": breakdown.total_tokens,
            "input_tokens": breakdown.total_input,
            "output_tokens": breakdown.total_output,
            "cache_read_tokens": breakdown.total_cache_read,
            "cache_write_tokens": breakdown.total_cache_write,
            "total_cost_usd": round(breakdown.total_cost_usd, 4),
            "by_model": {
                model: {
                    "calls": b.calls,
                    "tokens": b.total_tokens,
                    "cost_usd": round(b.total_cost_usd, 4),
                }
                for model, b in by_model.items()
            },
        }
