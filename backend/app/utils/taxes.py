def calculate_taxes(buy_price, sell_price, quantity, is_intraday=False):
    """
    Calculates all Indian Equity trading taxes and charges.

    Covers:
        - Brokerage (₹0 delivery / ₹20 or 0.03% intraday per leg)
        - STT (Securities Transaction Tax)
        - Exchange Transaction Charges (~0.00345%)
        - GST (18% on Brokerage + Exchange Charges)
        - SEBI Charges (₹10 per crore)
        - Stamp Duty (0.015% delivery buy / 0.003% intraday buy)

    Returns a dict with each charge and the net profit after all deductions.
    """
    turnover = (buy_price + sell_price) * quantity
    gross_profit = (sell_price - buy_price) * quantity

    # Brokerage
    if is_intraday:
        brokerage = min(20.0, turnover * 0.0003) * 2  # Both legs
    else:
        brokerage = 0.0

    # STT
    if is_intraday:
        stt = round(sell_price * quantity * 0.00025)
    else:
        stt = round(buy_price * quantity * 0.001) + round(sell_price * quantity * 0.001)

    # Exchange Transaction Charges
    exchange_charges = turnover * 0.0000345

    # GST (18% on brokerage + transaction charges)
    gst = (brokerage + exchange_charges) * 0.18

    # SEBI Charges (₹10 per crore)
    sebi_charges = turnover * 0.000001

    # Stamp Duty (buy side only)
    if is_intraday:
        stamp_duty = round(buy_price * quantity * 0.00003)
    else:
        stamp_duty = round(buy_price * quantity * 0.00015)

    total_charges = brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty
    net_profit = gross_profit - total_charges

    return {
        "gross_profit": round(gross_profit, 2),
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "exchange_charges": round(exchange_charges, 2),
        "gst": round(gst, 2),
        "sebi_charges": round(sebi_charges, 2),
        "stamp_duty": round(stamp_duty, 2),
        "total_charges": round(total_charges, 2),
        "net_profit": round(net_profit, 2),
    }
