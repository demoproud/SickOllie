from __future__ import annotations

"""Shared Wardrobe identity and assembly-attribute rules.

Wardrobe records describe reusable garments. Color, pattern, cut/fit, and wear
placement are optional choices made while assembling a Look rather than reasons
to multiply the catalog with near-identical records.
"""

import re


WARDROBE_COLOR_OPTIONS = (
    "black", "white", "cream", "gray", "brown", "tan", "red", "orange",
    "yellow", "green", "olive", "blue", "navy", "purple", "pink",
)
WARDROBE_PATTERN_OPTIONS = (
    "plaid", "tartan", "gingham", "striped", "pinstriped", "checkered",
    "floral", "polka-dot", "heart-print", "animal-print", "camouflage",
    "tie-dye", "ombré", "color-blocked",
)
WARDROBE_CUT_OPTIONS = (
    "cropped", "fitted", "oversized", "high-waisted", "low-rise", "mini",
    "micro", "midi", "maxi",
)
WARDROBE_WEAR_OPTIONS = (
    "worn underneath", "layered over", "peeking out beneath",
)

_COLOR_WORDS = (
    "black", "white", "brown", "tan", "beige", "cream", "ivory", "red",
    "burgundy", "maroon", "orange", "yellow", "mustard", "green", "olive",
    "emerald", "teal", "turquoise", "blue", "navy", "cobalt", "purple",
    "violet", "lavender", "lilac", "pink", "rose", "coral", "peach",
    "gray", "grey", "khaki", "camel", "chocolate", "plum", "wine", "aqua",
    "mint", "sage", "crimson", "scarlet", "charcoal", "nude",
)
_SHADE_WORDS = (
    "pale", "light", "dark", "deep", "bright", "pastel", "powder", "baby",
    "dusty", "warm", "cool",
)
_COLOR = "|".join(sorted((re.escape(value) for value in _COLOR_WORDS), key=len, reverse=True))
_SHADE = "|".join(re.escape(value) for value in _SHADE_WORDS)
_COLOR_RE = re.compile(rf"(?<![\w-])(?:(?:{_SHADE})\s+)?(?:{_COLOR})(?![\w-])", re.IGNORECASE)
_PATTERN_RE = re.compile(
    r"\b(?:striped?|plaid|checkered|checked|gingham|color[- ]?block(?:ed)?|colour[- ]?block(?:ed)?|"
    r"ombr[ée]|tie[- ]?dye(?:d)?|rainbow|multi[- ]?colou?red|two[- ]?tone)\b",
    re.IGNORECASE,
)
_EXPLICIT_MULTI_COLOR_RE = re.compile(
    rf"\b(?:{_COLOR})\b\s*(?:-and-|\band\b|/|&)\s*(?:\b(?:{_COLOR})\b)",
    re.IGNORECASE,
)
_RAW_COLOR_RE = re.compile(rf"(?<!\w)(?:(?:{_SHADE})\s+)?(?:{_COLOR})(?!\w)", re.IGNORECASE)
_PATTERN_ATTRIBUTE_RE = re.compile(
    r"\b(?:pin[- ]?striped?|striped?|plaid|tartan|checkered|checked|gingham|polka[- ]?dot(?:ted)?|"
    r"floral|heart[- ]?print(?:ed)?|animal[- ]?print(?:ed)?|leopard[- ]?print(?:ed)?|zebra[- ]?print(?:ed)?|"
    r"camouflage|camo|color[- ]?block(?:ed)?|colour[- ]?block(?:ed)?|ombr[ée]|tie[- ]?dye(?:d)?|"
    r"rainbow|multi[- ]?colou?red|two[- ]?tone)\b",
    re.IGNORECASE,
)
_CUT_ATTRIBUTE_RE = re.compile(
    r"\b(?:ultra[- ]?short|micro|mini|midi|maxi|cropped|crop|oversized|fitted|high[- ]?waisted|"
    r"low[- ]?rise|high[- ]?rise|little|tiny)\b",
    re.IGNORECASE,
)
_GARMENT_HEAD_RE = re.compile(
    r"\b(?:tops?|tees?|t-shirts?|shirts?|blouses?|button[- ]ups?|polos?|camisoles?|camis?|tanks?|sweaters?|hoodies?|sweatshirts?|cardigans?|jackets?|"
    r"coats?|robes?|aprons?|shorts?|skorts?|skirts?|kilts?|pants?|trousers?|jeans?|briefs?|panties|thongs?|"
    r"bloomers?|dress(?:es)?|sundress(?:es)?|nightdress(?:es)?|babydolls?|pinafores?|smocks?|coverups?|gowns?|nightgowns?|rompers?|jumpsuits?|overalls?|bodysuits?|leotards?|"
    r"teddies|catsuits?|corsets?|bustiers?|bralettes?|bras?|bikinis?|swimsuits?|chemises?|slips?|socks?|"
    r"stockings?|tights?|leggings?|thigh[- ]highs?|leg warmers?|arm warmers?|shoes?|sneakers?|boots?|heels?|stilettos?|"
    r"flats?|mary janes?|loafers?|slippers?|sandals?|flip[- ]?flops?|mules?|pumps?|gloves?|chokers?|"
    r"collars?|necklaces?|anklets?|bracelets?|earrings?|chains?|harnesses?|belts?|garters?|suspenders?|"
    r"headsets?|sarongs?)\b",
    re.IGNORECASE,
)
_PLACEMENT_FRAGMENT_RE = re.compile(
    r"(?:,?\s+)?(?:barely\s+)?(?:visible\s+)?(?:worn\s+)?underneath\b|"
    r"(?:,?\s+)?peeking\s+out\s+(?:from\s+)?(?:under|beneath)\b|"
    r"(?:,?\s+)?(?:worn|layered|draped)\s+over\s*$",
    re.IGNORECASE,
)
_COMPOUND_PARTS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\bflip[- ]?flops?\b", re.IGNORECASE), "Footwear", "Sandals"),
    (re.compile(r"\b(?:platform |heeled |feathered |patent |velvet )?mules?\b", re.IGNORECASE), "Footwear", "Heels"),
    (re.compile(r"\barm warmers?\b", re.IGNORECASE), "Accessories", "Arm Warmers"),
    (re.compile(r"\bfishnets?\b", re.IGNORECASE), "Legwear", "Tights"),
    (re.compile(r"\bsuspenders?\b", re.IGNORECASE), "Accessories", "Belts"),
    (re.compile(r"\bcat[- ]?ear headsets?\b", re.IGNORECASE), "Accessories", "Headwear"),
    (re.compile(r"\bsarongs?\b", re.IGNORECASE), "Bottoms", "Skirts"),
    (re.compile(r"\b(?:ankle chains?|toe rings?)\b", re.IGNORECASE), "Accessories", "Jewelry"),
    (re.compile(r"\b(?:painted|polished) toenails?\b", re.IGNORECASE), "Body Styling", "Skin Finish"),
    (re.compile(r"\b(?:body|belly|hip|waist) chains?\b", re.IGNORECASE), "Accessories", "Body Chains"),
    (re.compile(r"\b(?:chokers?|detachable collars?)\b", re.IGNORECASE), "Accessories", "Chokers & Collars"),
    (re.compile(r"\bgloves?\b", re.IGNORECASE), "Accessories", "Gloves"),
    (re.compile(r"\b(?:ankle[- ]high|ankle)\s+socks?\b", re.IGNORECASE), "Legwear", "Ankle Socks"),
    (re.compile(r"\bknee[- ]high\s+socks?\b", re.IGNORECASE), "Legwear", "Knee Socks"),
    (re.compile(r"\bthigh[- ]high\s+socks?\b", re.IGNORECASE), "Legwear", "Thigh-Highs"),
    (re.compile(r"\b(?:crew\s+)?socks?\b", re.IGNORECASE), "Legwear", "Crew Socks"),
    (re.compile(r"\bstockings?\b", re.IGNORECASE), "Legwear", "Stockings"),
    (re.compile(r"\b(?:tights?|leggings?)\b", re.IGNORECASE), "Legwear", "Tights"),
    (re.compile(r"\bleg warmers?\b", re.IGNORECASE), "Legwear", "Leg Warmers"),
    (re.compile(r"\bsneakers?\b", re.IGNORECASE), "Footwear", "Sneakers"),
    (re.compile(r"\bboots?\b", re.IGNORECASE), "Footwear", "Boots"),
    (re.compile(r"\b(?:heels?|stilettos?|pumps?)\b", re.IGNORECASE), "Footwear", "Heels"),
    (re.compile(r"\b(?:flats?|mary janes?|loafers?)\b", re.IGNORECASE), "Footwear", "Flats & Mary Janes"),
    (re.compile(r"\bslippers?\b", re.IGNORECASE), "Footwear", "Slippers"),
    (re.compile(r"\bsandals?\b", re.IGNORECASE), "Footwear", "Sandals"),
    (re.compile(r"\b(?:shorts?|skorts?)\b", re.IGNORECASE), "Bottoms", "Shorts"),
    (re.compile(r"\b(?:skirts?|kilts?|micro minis?|minis?)\b", re.IGNORECASE), "Bottoms", "Skirts"),
    (re.compile(r"\b(?:pants?|trousers?|jeans?)\b", re.IGNORECASE), "Bottoms", "Pants"),
    (re.compile(r"\b(?:briefs?|panties|thongs?|bloomers?)\b", re.IGNORECASE), "Bottoms", "Underwear Bottoms"),
    (re.compile(r"\b(?:dress(?:es)?|sundress(?:es)?|babydolls?|pinafores?|gowns?|nightgowns?)\b", re.IGNORECASE), "Dresses & One-Pieces", "Dresses"),
    (re.compile(r"\b(?:rompers?|jumpsuits?|overalls?)\b", re.IGNORECASE), "Dresses & One-Pieces", "Jumpsuits"),
    (re.compile(r"\b(?:bodysuits?|bikinis?|swimsuits?)\b", re.IGNORECASE), "Bodywear", "Bodysuits"),
    (re.compile(r"\bleotards?\b", re.IGNORECASE), "Bodywear", "Leotards"),
    (re.compile(r"\b(?:teddies|catsuits?)\b", re.IGNORECASE), "Bodywear", "Teddies"),
    (re.compile(r"\b(?:corsets?|bustiers?|bralettes?|bras?)\b", re.IGNORECASE), "Bodywear", "Corsets & Bustiers"),
    (re.compile(r"\b(?:chemises?|slips?)\b", re.IGNORECASE), "Bodywear", "Chemises & Slips"),
    (re.compile(r"\b(?:hoodies?|sweatshirts?)\b", re.IGNORECASE), "Layers", "Hoodies & Sweatshirts"),
    (re.compile(r"\bcardigans?\b", re.IGNORECASE), "Layers", "Cardigans"),
    (re.compile(r"\b(?:jackets?|blazers?)\b", re.IGNORECASE), "Layers", "Jackets"),
    (re.compile(r"\bcoats?\b", re.IGNORECASE), "Layers", "Coats"),
    (re.compile(r"\brobes?\b", re.IGNORECASE), "Layers", "Robes"),
    (re.compile(r"\baprons?\b", re.IGNORECASE), "Layers", "Aprons"),
    (re.compile(r"\b(?:camisoles?|camis?|tanks?)\b", re.IGNORECASE), "Tops", "Tanks & Camis"),
    (re.compile(r"\b(?:shirts?|blouses?)\b", re.IGNORECASE), "Tops", "Shirts & Blouses"),
    (re.compile(r"\bsweaters?\b", re.IGNORECASE), "Tops", "Sweaters"),
    (re.compile(r"\b(?:tops?|tees?|t-shirts?)\b", re.IGNORECASE), "Tops", "Tees"),
)
_COMPOUND_SEPARATOR_RE = re.compile(
    r"(,\s*(?:and\s+)?|\s+(?:and|with|paired with|alongside|over|under|tucked into)\s+)",
    re.IGNORECASE,
)


def neutralize_wardrobe_color(value: str, item_type: str = "piece") -> str:
    """Return a color-neutral garment identity without flattening its design."""

    original = " ".join(str(value or "").split()).strip(" ,.;")
    if not original or str(item_type or "piece").casefold() in {"finisher", "styling"}:
        return original
    preserve_color = bool(_PATTERN_RE.search(original) or _EXPLICIT_MULTI_COLOR_RE.search(original))

    # Rose gold is a metal/finish, not a removable pink modifier.
    protected = re.sub(r"\brose\s+gold\b", "__ROSE_GOLD__", original, flags=re.IGNORECASE)
    neutral = (protected if preserve_color else _COLOR_RE.sub(" ", protected)).replace("__ROSE_GOLD__", "rose gold")
    neutral = re.sub(r"^(?:a|an|the)\s+", "", neutral, flags=re.IGNORECASE)
    neutral = re.sub(r"\s+([,.;])", r"\1", neutral)
    neutral = re.sub(r"(?:\s*[-/]\s*){2,}", " ", neutral)
    neutral = re.sub(r"\s+", " ", neutral).strip(" ,.;-/")
    return neutral if re.search(r"[A-Za-z]", neutral) else original


def canonicalize_wardrobe_value(value: str, item_type: str = "piece") -> str:
    """Collapse assembly choices while retaining garment construction and material."""

    original = " ".join(str(value or "").split()).strip(" ,.;")
    clean_type = str(item_type or "piece").casefold()
    if not original or clean_type in {"finisher", "styling"}:
        return original
    text = _PLACEMENT_FRAGMENT_RE.sub(" ", original)
    text = re.sub(r"^(?:a|an|the)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:micro(?:\s+mini)?|mini)\b\s*$", "skirt", text, flags=re.IGNORECASE)
    heads = list(_GARMENT_HEAD_RE.finditer(text))
    head = heads[-1] if heads else None
    if head:
        prefix, remainder = text[:head.start()], text[head.start():]
        prefix = _PATTERN_ATTRIBUTE_RE.sub(" ", prefix)
        prefix = _CUT_ATTRIBUTE_RE.sub(" ", prefix)
        # Pattern color combinations are safe to remove here because Pattern and
        # custom Color are independent Outfit Builder controls.
        prefix = re.sub(r"\brose\s+gold\b", "__ROSE_GOLD__", prefix, flags=re.IGNORECASE)
        prefix = _RAW_COLOR_RE.sub(" ", prefix).replace("__ROSE_GOLD__", "rose gold")
        prefix = re.sub(r"(?<!\w)(?:and|&)(?!\w)", " ", prefix, flags=re.IGNORECASE)
        prefix = re.sub(r"(?<!\w)[-/]+(?!\w)", " ", prefix)
        text = prefix + remainder
    else:
        text = neutralize_wardrobe_color(text, clean_type)
    text = re.sub(r"\s+([,.;])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.;-/")
    return text if re.search(r"[A-Za-z]", text) else original


def split_wardrobe_compound(value: str) -> list[tuple[str, str, str]]:
    """Detach unmistakable independently wearable comma parts.

    Ordinary construction commas remain untouched. Returned category/subtype are
    populated only for detached pieces; the caller retains the original taxonomy
    for the first value.
    """

    original = " ".join(str(value or "").split()).strip(" ,.;")
    tokens = _COMPOUND_SEPARATOR_RE.split(original)
    if len(tokens) < 3:
        return [(original, "", "")]
    primary = [tokens[0]]
    detached: list[tuple[str, str, str]] = []
    for index in range(1, len(tokens), 2):
        delimiter = tokens[index]
        segment = tokens[index + 1] if index + 1 < len(tokens) else ""
        clean = re.sub(r"^(?:and|with)\s+", "", segment, flags=re.IGNORECASE).strip()
        if re.match(r"^(?:built[- ]in|attached|integrated|embroidered|printed|trimmed|edged)\b", clean, re.IGNORECASE):
            primary.extend((delimiter, segment))
            continue
        match = next(((pattern, category, subtype) for pattern, category, subtype in _COMPOUND_PARTS if pattern.search(clean)), None)
        if match is None:
            primary.extend((delimiter, segment))
            continue
        _, category, subtype = match
        detached.append((clean, category, subtype))
    if not detached:
        return [(original, "", "")]
    primary_text = re.sub(r"\s+", " ", "".join(primary)).strip(" ,.;")
    primary_match = next(((category, subtype) for pattern, category, subtype in _COMPOUND_PARTS if pattern.search(primary_text)), ("", ""))
    return [(primary_text, primary_match[0], primary_match[1]), *detached]


def wardrobe_color_key(value: str, item_type: str = "piece") -> str:
    neutral = canonicalize_wardrobe_value(value, item_type)
    neutral = neutral.replace("–", "-").replace("—", "-")
    neutral = re.sub(r"[-_/]+", " ", neutral.casefold())
    neutral = re.sub(r"[^a-z0-9\s]+", "", neutral)
    return re.sub(r"\s+", " ", neutral).strip()
