MODELS: list[tuple[str, str, str, int, str]] = [
    ("tiny",     "Tiny",     "самая лёгкая · приемлемое качество",          75 * 1024 * 1024,  "1 GB VRAM"),
    ("small",    "Small",    "сбалансированно для слабых GPU",             480 * 1024 * 1024,  "2 GB VRAM"),
    ("medium",   "Medium",   "хорошее качество русского",                 1500 * 1024 * 1024,  "5 GB VRAM"),
    ("large-v3", "Large-v3", "максимум точности · акценты, числительные", 3100 * 1024 * 1024, "10 GB VRAM"),
]

DEFAULT_MODEL = "large-v3"


def model_label(key: str) -> str:
    for k, name, *_ in MODELS:
        if k == key:
            return name
    return key
