import re
from typing import Dict, List, Tuple


KEYWORD_CATEGORIES = {
    "furniture": [
        "диван", "софа", "крісло", "стілець", "стіл", "комод", "ліжко", "пуф", 
        "шафа", "полиця", "тумба", "стелаж", "банкетка", "sofa", "chair", "table", 
        "bed", "armchair", "dresser", "cabinet", "shelf", "ottoman", "desk", 
        "sideboard", "nightstand", "couch", "stool", "bench", "pouf"
    ],
    "lighting": [
        "люстра", "світильник", "лампа", "бра", "торшер", "спот", "підвіс", 
        "гірлянда", "плафон", "освітлення", "chandelier", "lamp", "pendant", 
        "sconce", "light", "spotlight", "floor lamp", "lantern", "lighting"
    ],
    "decor": [
        "декор", "ваза", "картина", "дзеркало", "свічка", "годинник", "скульптура", 
        "книги", "килим", "подушка", "плед", "штора", "посуд", "статуетка", 
        "панно", "органайзер", "decor", "vase", "mirror", "candle", "clock", 
        "sculpture", "books", "rug", "pillow", "curtain", "tableware", "carpet", 
        "cushion", "artwork", "frame"
    ],
    "plants": [
        "вазон", "квітка", "дерево", "кущ", "рослина", "зелень", "пальма", 
        "фікус", "монстера", "букет", "трава", "суккулент", "туя", "кашпо", 
        "plant", "tree", "flower", "palm", "bush", "ficus", "monstera", 
        "bouquet", "grass", "foliage", "succulent", "potted plant"
    ],
    "appliances": [
        "техніка", "телевізор", "холодильник", "витяжка", "плита", "духовка", 
        "пральна", "кавомашина", "монітор", "ноутбук", "кондиціонер", 
        "кухонна техніка", "tv", "refrigerator", "oven", "stove", "hood", 
        "washing machine", "coffee maker", "monitor", "laptop", "appliance", 
        "fridge", "microwave"
    ],
    "architecture": [
        "будинок", "фасад", "вікно", "двері", "сходи", "паркан", "колона", 
        "камін", "дах", "альтанка", "арка", "балкон", "тераса", "паркінг", 
        "building", "facade", "window", "door", "stairs", "fence", "column", 
        "fireplace", "roof", "gazebo", "arch", "balcony", "terrace"
    ],
    "textures": [
        "текстури", "матеріал", "паркет", "плитка", "мармур", "бетон", "дерево", 
        "штукатурка", "безшовна текстура", "ламінат", "мікроцемент", 
        "textures", "material", "parquet", "tile", "marble", "concrete", 
        "wood", "plaster", "seamless", "laminate"
    ],
    "vehicles": [
        "авто", "автомобіль", "машина", "велосипед", "мотоцикл", "літак", 
        "скутер", "вантажівка", "car", "vehicle", "bike", "bicycle", 
        "motorcycle", "auto", "truck", "airplane"
    ]
}


FORMAT_PATTERNS = [
    (r"\b(\.max|3ds\s*max|max)\b", "3ds Max"),
    (r"\b(\.obj|obj)\b", "OBJ"),
    (r"\b(\.fbx|fbx)\b", "FBX"),
    (r"\b(\.blend|blender)\b", "Blender"),
    (r"\b(\.3ds|3ds)\b", "3DS"),
    (r"\b(\.c4d|cinema\s*4d)\b", "Cinema 4D"),
    (r"\b(\.stl|stl)\b", "STL"),
]

ARCHIVE_PATTERNS = [
    (r"\b(\.zip|zip)\b", "ZIP"),
    (r"\b(\.rar|rar)\b", "RAR"),
    (r"\b(\.7z|7z)\b", "7Z"),
]

RENDER_PATTERNS = [
    (r"\b(v-?ray|vray)\b", "V-Ray"),
    (r"\b(corona|corona\s*renderer)\b", "Corona"),
    (r"\b(arnold)\b", "Arnold"),
    (r"\b(octane)\b", "Octane"),
    (r"\b(redshift)\b", "Redshift"),
    (r"\b(cycles)\b", "Cycles"),
    (r"\b(lumion)\b", "Lumion"),
    (r"\b(eevee)\b", "Eevee"),
]


def classify_text(text: str) -> str:
    """Detect category slug based on keyword scoring."""
    if not text:
        return "other"
        
    text_lower = text.lower()
    scores: Dict[str, int] = {slug: 0 for slug in KEYWORD_CATEGORIES}

    for slug, keywords in KEYWORD_CATEGORIES.items():
        for kw in keywords:
            # Word boundary matching where possible, or simple substring
            pattern = r"\b" + re.escape(kw) + r"\b"
            matches = len(re.findall(pattern, text_lower))
            if matches > 0:
                scores[slug] += matches * 2
            elif kw in text_lower:
                scores[slug] += 1

    best_slug = max(scores, key=scores.get)
    if scores[best_slug] > 0:
        return best_slug
    return "other"


def extract_metadata(text: str) -> Tuple[List[str], List[str], List[str], str]:
    """
    Extract file_formats, archive_types, render_engines, and a clean title.
    Returns: (file_formats, archive_types, render_engines, clean_title)
    """
    if not text:
        return [], [], [], "3D Model"

    text_lower = text.lower()

    # Formats
    file_formats = set()
    for pattern, name in FORMAT_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            file_formats.add(name)

    # Archives
    archive_types = set()
    for pattern, name in ARCHIVE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            archive_types.add(name)

    # Renders
    render_engines = set()
    for pattern, name in RENDER_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            render_engines.add(name)

    # Extract title from first line or hashtag
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    clean_title = "3D Model"
    if lines:
        first_line = lines[0]
        # Remove common telegram tags or formatting
        first_line = re.sub(r"^[#📌🔥⭐⚡✨🚀🌐]+", "", first_line).strip()
        if len(first_line) > 60:
            clean_title = first_line[:57] + "..."
        elif len(first_line) > 2:
            clean_title = first_line

    return list(file_formats), list(archive_types), list(render_engines), clean_title
