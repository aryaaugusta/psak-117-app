def format_idr(val):
    """
    Mengubah float/int menjadi format string Rupiah yang rapi
    """
    if isinstance(val, (int, float)):
        return f"Rp {val:,.2f}"
    return val