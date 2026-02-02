import re


def convert_to_seconds(duration_str: str) -> int:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    total = 0.0
    for match in re.finditer(r"(?P<val>\d+(\.\d+)?)(?P<unit>[smhdw]?)", duration_str, re.I):
        val = float(match.group("val"))
        unit = match.group("unit").lower() or "s"
        total += val * units.get(unit, 1)
    return int(total)
