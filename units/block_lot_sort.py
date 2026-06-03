"""Numeric sort keys for HousingUnit block_number / lot_number CharFields."""


def block_lot_sort_key(block_number, lot_number=''):
    """Sort digit strings numerically (e.g. Block 2 before Block 10)."""
    def _part(value):
        text = str(value or '').strip()
        if text.isdigit():
            return (0, int(text))
        return (1, text.lower())

    return (_part(block_number), _part(lot_number))
