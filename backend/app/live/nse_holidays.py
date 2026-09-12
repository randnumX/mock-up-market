"""
NSE equity segment trading holidays - full-day market closures (Diwali
Laxmi Pujan/Muhurat Trading is a special evening session outside normal
hours on an otherwise-closed day, so it's listed here as a holiday too).

Sourced from NSE's own published circulars and cross-checked against two
independent broker-published calendars for 2026 (Upstox, Groww) to catch
transcription errors; 2025 additionally verified against an official NSE
circular (nsearchives.nseindia.com/content/circulars/CMTR65587.pdf).

This list needs a manual update once a year (NSE publishes each year's
calendar around December of the prior year) - `is_market_open()` degrades
gracefully to weekday+hours-only checking for any year not listed here,
rather than silently misbehaving once this goes stale.
"""

NSE_HOLIDAYS_2025 = {
    "2025-02-26",  # Mahashivratri
    "2025-03-14",  # Holi
    "2025-03-31",  # Id-Ul-Fitr
    "2025-04-10",  # Shri Mahavir Jayanti
    "2025-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
    "2025-04-18",  # Good Friday
    "2025-05-01",  # Maharashtra Day
    "2025-08-15",  # Independence Day
    "2025-08-27",  # Ganesh Chaturthi
    "2025-10-02",  # Mahatma Gandhi Jayanti / Dussehra
    "2025-10-21",  # Diwali Laxmi Pujan (Muhurat Trading)
    "2025-10-22",  # Diwali - Balipratipada
    "2025-11-05",  # Guru Nanak Jayanti
    "2025-12-25",  # Christmas
}

NSE_HOLIDAYS_2026 = {
    "2026-01-15",  # Special trading holiday (Maharashtra municipal corporation elections)
    "2026-01-26",  # Republic Day
    "2026-03-03",  # Holi
    "2026-03-26",  # Shri Ram Navami
    "2026-03-31",  # Shri Mahavir Jayanti
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-05-28",  # Bakri Id
    "2026-06-26",  # Muharram
    "2026-09-14",  # Ganesh Chaturthi
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-20",  # Dussehra
    "2026-11-10",  # Diwali - Balipratipada
    "2026-11-24",  # Prakash Gurpurb Sri Guru Nanak Dev
    "2026-12-25",  # Christmas
}

NSE_HOLIDAYS = NSE_HOLIDAYS_2025 | NSE_HOLIDAYS_2026
