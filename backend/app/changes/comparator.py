from decimal import Decimal


def compare(
    previous: Decimal | None, current: Decimal | None
) -> tuple[Decimal | None, float | None, str]:
    if previous is None or current is None:
        return None, None, "new"
    absolute = current - previous
    if absolute == 0:
        return absolute, 0.0, "flat"
    if previous == 0:
        return absolute, None, "up" if absolute > 0 else "down"
    return absolute, float((absolute / abs(previous)) * 100), "up" if absolute > 0 else "down"
