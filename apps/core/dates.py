import calendar
from datetime import timedelta


def add_months(day, months):
    """The same day `months` later, kept inside the month: 31 Jan + 1 month = 28/29 Feb."""
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return day.replace(year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1]))


def period_end(start, months):
    """Last day of a period of `months` starting on `start`: 1 Nov + 1 month ends 30 Nov."""
    return add_months(start, months) - timedelta(days=1)
