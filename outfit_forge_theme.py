from __future__ import annotations

"""Structured theme interpretation for Outfit Forge.

The public UI deliberately exposes a theme rather than implementation buckets.
This module converts ordinary fashion language into binding garment, color, and
material constraints before any variation is sampled.
"""

import random
import re
from typing import Any


def _spec(identifier: str, name: str, category: str, aliases: str, variants: str, materials: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "name": name,
        "category": category,
        "aliases": tuple(part.strip() for part in aliases.split("|") if part.strip()),
        "variants": tuple(part.strip() for part in variants.split("|") if part.strip()),
        "materials": tuple(part.strip() for part in materials.split("|") if part.strip()),
    }


GARMENT_SPECS: tuple[dict[str, Any], ...] = (
    _spec("sundress", "sundress", "dress", "sundresses|sundress", "babydoll sundress|smocked sundress|square-neck sundress|button-front sundress|tiered sundress|halter sundress|slip sundress|pinafore sundress|prairie sundress|wrap sundress|empire-waist sundress|open-back sundress", "cotton poplin|washed linen|cotton voile|gingham|eyelet cotton|light chiffon|seersucker"),
    _spec("mini-dress", "mini dress", "dress", "minidresses|minidress|mini dresses|mini dress", "A-line mini dress|fitted mini dress|babydoll mini dress|slip mini dress|halter mini dress|long-sleeve mini dress|wrap mini dress|puff-sleeve mini dress|square-neck mini dress|cutout mini dress", "cotton poplin|ribbed jersey|silk satin|velvet|fine knit|denim|chiffon|lace"),
    _spec("dress", "dress", "dress", "dresses|dress", "fit-and-flare dress|bias-cut dress|shirt dress|wrap dress|column dress|tea dress|slip dress|babydoll dress|sweater dress|pinafore dress|one-shoulder dress|tiered dress", "cotton poplin|ribbed jersey|silk satin|velvet|fine knit|denim|chiffon|linen|lace"),
    _spec("gown", "gown", "dress", "ballgowns|ballgown|gowns|gown", "column gown|bias-cut gown|open-back gown|one-shoulder gown|corseted gown|cape-backed gown|halter gown|tiered gown|slip gown", "silk satin|velvet|chiffon|embroidered tulle|silk faille|brocade"),
    _spec("overalls", "overalls", "onepiece", "dungarees|overalls", "classic bib overalls|relaxed overalls|short overalls|skirt overalls|wide-leg overalls|cropped overalls|utility overalls|painter overalls|fitted overalls|button-side overalls", "worn denim|washed denim|cotton twill|corduroy|soft linen|canvas|lightweight poplin"),
    _spec("jumpsuit", "jumpsuit", "onepiece", "jumpsuits|jumpsuit", "wide-leg jumpsuit|wrap-front jumpsuit|halter jumpsuit|zip-front jumpsuit|tailored jumpsuit|utility jumpsuit|open-back jumpsuit|strapless jumpsuit|cutout jumpsuit", "matte jersey|linen|denim|cotton twill|silk crepe|velvet|technical nylon"),
    _spec("romper", "romper", "onepiece", "playsuits|playsuit|rompers|romper", "button-front romper|puff-sleeve romper|halter romper|wrap-front romper|utility romper|tailored romper|smocked romper|open-back romper", "cotton poplin|linen|denim|matte jersey|gingham|silk crepe"),
    _spec("bodysuit", "bodysuit", "bodywear", "catsuits|catsuit|leotards|leotard|bodysuits|bodysuit", "high-cut bodysuit|open-sided bodysuit|one-sleeve bodysuit|zip-front bodysuit|halter bodysuit|deep-back bodysuit|cutout bodysuit|long-sleeve bodysuit", "stretch jersey|velvet|lace|mesh|latex|wet-look Lycra|ribbed knit"),
    _spec("t-shirt", "T-shirt", "top", "tee shirts|tee shirt|t-shirts|t-shirt|t shirts|t shirt|tshirts|tshirt|tees|tee", "fitted T-shirt|cropped T-shirt|ringer T-shirt|boxy T-shirt|oversized T-shirt|baby T-shirt|longline T-shirt|cap-sleeve T-shirt|raw-hem T-shirt", "cotton jersey|ribbed jersey|washed cotton|slub cotton|soft modal"),
    _spec("turtleneck", "turtleneck", "top", "roll necks|roll neck|turtlenecks|turtleneck", "fitted turtleneck|ribbed turtleneck|cropped turtleneck|sleeveless turtleneck|fine-knit turtleneck|mock-layer turtleneck|longline turtleneck", "ribbed knit|fine merino|stretch jersey|velvet|cashmere knit|cotton jersey"),
    _spec("tank", "tank top", "top", "tank tops|tank top|tanks|tank", "oversized tank top|fitted tank top|cropped tank top|ribbed tank top|racerback tank top|longline tank top|contrast-trim tank top", "ribbed jersey|washed cotton|soft modal|mesh|silk knit"),
    _spec("camisole", "camisole", "top", "camisoles|camisole|camis|cami", "lace-trim camisole|bias-cut camisole|cropped camisole|longline camisole|cowl-neck camisole|strappy camisole", "silk satin|ribbed jersey|lace|velvet|cotton voile"),
    _spec("blouse", "blouse", "top", "blouses|blouse", "puff-sleeve blouse|tie-neck blouse|wrap blouse|sheer blouse|button-front blouse|cropped blouse|peasant blouse", "silk charmeuse|cotton voile|chiffon|linen|satin|lace"),
    _spec("shirt", "shirt", "top", "button-downs|button-down|button ups|button up|shirts|shirt", "fitted shirt|oversized shirt|cropped shirt|button-front shirt|camp-collar shirt|longline shirt|short-sleeve shirt", "cotton poplin|linen|silk|denim|flannel|satin"),
    _spec("corset", "corset", "bodywear", "bustiers|bustier|basques|basque|corsets|corset", "underbust corset|overbust corset|longline corset|corset top|open-cup corset|sheer-panel corset|waist corset|strapless corset", "silk satin|velvet|brocade|lace|denim|leather|mesh"),
    _spec("bra", "bra", "lingerie", "bralettes|bralette|bras|bra", "soft-cup bra|balconette bra|triangle bra|longline bralette|quarter-cup bra|plunge bra|strappy bra", "lace|silk satin|mesh|velvet|cotton jersey"),
    _spec("lingerie", "lingerie set", "lingerie", "intimates|underwear|lingerie", "matching lingerie set|bralette-and-brief set|garter lingerie set|open-cup lingerie set|longline lingerie set|sheer lingerie set", "lace|silk satin|mesh|velvet|embroidered tulle"),
    _spec("windbreaker", "windbreaker", "outerwear", "wind breakers|wind breaker|windbreakers|windbreaker", "cropped windbreaker|oversized windbreaker|color-block windbreaker|packable windbreaker|hooded windbreaker|zip-front windbreaker|longline windbreaker|sport windbreaker", "ripstop nylon|lightweight nylon|crinkled technical fabric|translucent shell fabric|matte performance fabric"),
    _spec("jacket", "jacket", "outerwear", "jackets|jacket", "cropped jacket|oversized jacket|fitted jacket|zip-front jacket|boxy jacket|longline jacket|utility jacket|bomber jacket", "denim|leather|cotton twill|velvet|technical nylon|wool"),
    _spec("cardigan", "cardigan", "outerwear", "cardigans|cardigan", "cropped cardigan|long cardigan|fitted cardigan|oversized cardigan|tie-front cardigan|buttoned cardigan|cocoon cardigan", "fine knit|cashmere knit|ribbed cotton|fuzzy mohair|chenille|velvet knit"),
    _spec("hoodie", "hoodie", "outerwear", "hoodies|hoodie|sweatshirts|sweatshirt", "cropped hoodie|oversized hoodie|zip-front hoodie|fitted hoodie|longline hoodie|sleeveless hoodie", "cotton fleece|velour|French terry|soft jersey|plush fleece"),
    _spec("coat", "coat", "outerwear", "coats|coat", "trench coat|wrap coat|cropped coat|longline coat|double-breasted coat|cocoon coat|fitted coat", "wool|cotton gabardine|velvet|faux fur|vinyl|quilted nylon"),
    _spec("blazer", "blazer", "outerwear", "blazers|blazer", "cropped blazer|oversized blazer|fitted blazer|double-breasted blazer|longline blazer|peplum blazer", "wool suiting|linen|velvet|satin|denim|leather"),
    _spec("jeans", "jeans", "bottom", "denim pants|denim trousers|jeans", "straight-leg jeans|wide-leg jeans|high-waisted jeans|low-rise jeans|cropped jeans|flared jeans|relaxed jeans|skinny jeans|patchwork jeans", "worn denim|dark denim|white denim|black denim|stretch denim"),
    _spec("trousers", "trousers", "bottom", "slacks|pants|trousers", "wide-leg trousers|pleated trousers|cigarette trousers|high-waisted trousers|cropped trousers|fluid trousers|tailored trousers", "wool suiting|linen|silk crepe|velvet|cotton twill"),
    _spec("shorts", "shorts", "bottom", "shorts|hotpants|hot pants", "soft shorts|tailored shorts|micro shorts|high-waisted shorts|running shorts|cutoff shorts|ruffled shorts|bike shorts", "cotton jersey|denim|linen|velvet|satin|technical knit"),
    _spec("mini-skirt", "mini skirt", "bottom", "miniskirts|miniskirt|mini skirts|mini skirt", "pleated mini skirt|A-line mini skirt|wrap mini skirt|micro mini skirt|five-pocket mini skirt|bubble mini skirt|fitted mini skirt", "denim|velvet|wool plaid|silk satin|cotton twill|leather"),
    _spec("skirt", "skirt", "bottom", "skirts|skirt", "bias-cut skirt|pleated skirt|wrap skirt|tiered skirt|pencil skirt|circle skirt|bubble skirt|sheer overlay skirt", "denim|velvet|wool|silk satin|linen|chiffon|cotton poplin"),
    _spec("leggings", "leggings", "bottom", "leggings|tights", "high-waisted leggings|stirrup leggings|flared leggings|ribbed leggings|cutout leggings|second-skin leggings", "stretch jersey|velvet|wet-look Lycra|ribbed knit|mesh"),
    _spec("robe", "robe", "outerwear", "kimonos|kimono|dressing gowns|dressing gown|robes|robe", "short robe|floor-length robe|open robe|kimono-style robe|wrap robe|hooded robe|feather-trimmed robe", "silk satin|velvet|lace|chiffon|linen|waffle knit"),
    _spec("suit", "suit", "suit", "tuxedos|tuxedo|suits|suit", "cropped trouser suit|oversized suit|fitted skirt suit|three-piece suit|short suit|peplum suit|deconstructed suit", "wool suiting|linen|velvet|silk faille|denim"),
    _spec("swimwear", "swimwear", "swim", "beachwear|swimwear", "two-piece swimwear|one-piece swimwear|wrap swim set|sporty swim set|retro swim set|cutout swimwear", "matte swim jersey|wet-look Lycra|ribbed swim knit|metallic swim fabric"),
    _spec("bikini", "bikini", "swim", "bikinis|bikini", "triangle bikini|high-waisted bikini|string bikini|bandeau bikini|sport bikini|ruffled bikini|wrap bikini", "matte swim jersey|wet-look Lycra|ribbed swim knit|metallic swim fabric"),
    _spec("harness", "body harness", "bodywear", "body harnesses|body harness|harnesses|harness", "geometric body harness|chest-and-hip harness|O-ring body harness|chain body harness|asymmetric body harness|minimal strap harness|wide-band harness", "leather|latex|elastic webbing|chain|velvet straps|transparent vinyl"),
    _spec("body-chain", "body chain", "jewelry", "body chains|body chain", "fine body chain|layered body chain|chandelier body chain|waist-to-shoulder body chain|crystal-fringed body chain|pearl-draped body chain|asymmetric body chain", "rhinestone chain|pearls|silver chain|gold chain|prismatic crystal|opal beads"),
    _spec("body-jewelry", "body jewelry", "jewelry", "body jewellery|body jewelry|crystal nudity", "crystal body chain|pearl body drape|rhinestone body lattice|jeweled hip frame|chandelier body fringe|chain apron|gemstone body harness", "rhinestone chain|pearls|silver chain|gold chain|prismatic crystal|opal beads"),
    _spec("armor", "armor", "armor", "armour|armor", "segmented light armor|ceremonial armor|scout armor|gladiator armor|modular armor suit|asymmetric battle armor|armored bodywear", "brushed titanium|ceramic plates|carbon fiber|chrome alloy|flexible ballistic mesh"),
)


COLORS: dict[str, str] = {
    "black": "black", "white": "white", "ivory": "ivory", "cream": "cream", "red": "red",
    "cherry red": "cherry red", "pink": "pink", "hot pink": "hot pink", "blush": "blush pink",
    "blue": "blue", "navy": "navy", "cobalt": "cobalt blue", "cyan": "cyan", "teal": "teal",
    "aqua": "aqua", "green": "green", "mint": "mint green", "olive": "olive green",
    "yellow": "yellow", "butter yellow": "butter yellow", "orange": "orange", "peach": "peach",
    "purple": "purple", "violet": "violet", "lavender": "lavender", "plum": "deep plum",
    "brown": "brown", "camel": "camel", "beige": "beige", "gray": "gray", "grey": "gray",
    "silver": "silver", "gold": "gold", "bronze": "bronze", "clear": "clear",
    "rainbow": "rainbow", "pastel": "pastel", "neon": "neon", "holographic": "holographic",
}


MATERIALS: dict[str, str] = {
    "velvet": "velvet", "satin": "satin", "silk": "silk", "charmeuse": "silk charmeuse",
    "cotton": "cotton", "denim": "denim", "linen": "linen", "lace": "lace", "mesh": "mesh",
    "chiffon": "chiffon", "organza": "organza", "tulle": "tulle", "jersey": "jersey",
    "ribbed knit": "ribbed knit", "knit": "knit", "wool": "wool", "cashmere": "cashmere",
    "mohair": "mohair", "fleece": "fleece", "flannel": "flannel", "corduroy": "corduroy",
    "leather": "leather", "latex": "latex", "vinyl": "vinyl", "pvc": "PVC", "rubber": "rubber",
    "nylon": "nylon", "ripstop": "ripstop nylon", "crochet": "crochet", "chainmail": "chainmail",
    "chain": "chain", "crystal": "crystal", "pearls": "pearls", "pearl": "pearl-strung",
    "chrome": "chrome", "metallic": "metallic fabric", "sheer": "sheer fabric", "transparent": "transparent material",
}


STYLE_ALIASES: dict[str, tuple[str, ...]] = {
    "cute": ("cute", "girly", "sweet", "adorable", "kawaii"),
    "cozy": ("cozy", "comfy", "soft", "rainy-day", "rainy day"),
    "gothic": ("gothic", "goth", "vampire", "mourning", "witchy"),
    "haunted": ("haunted", "ghostly", "spectral", "cursed", "occult"),
    "rave": ("rave", "festival", "edm", "clubwear", "club", "neon", "glowing", "uv-reactive"),
    "romantic": ("romantic", "coquette", "valentine"),
    "retro": ("retro", "vintage", "y2k", "90s", "2000s"),
    "picnic": ("picnic", "cottagecore", "garden", "pastoral"),
    "preppy": ("preppy", "college", "academia", "schoolgirl"),
    "streetwear": ("streetwear", "street style", "urban"),
    "sporty": ("sporty", "athletic", "athleisure", "tennis"),
    "punk": ("punk", "grunge", "emo", "industrial"),
    "western": ("western", "cowgirl", "rodeo", "desert"),
    "boho": ("boho", "bohemian", "burning man", "burn-night"),
    "formal": ("formal", "evening", "ceremonial", "tailored"),
    "bridal": ("bridal", "wedding", "bride"),
    "fantasy": ("fantasy", "fairy", "elf", "goddess", "mythic", "celestial"),
    "futuristic": ("futuristic", "sci-fi", "scifi", "cyber", "alien", "android"),
    "aquatic": ("aquatic", "siren", "mermaid", "jellyfish", "ocean"),
    "doll": ("doll", "porcelain", "toybox", "puppet"),
    "organic": ("organic", "living", "symbiote", "tentacle", "parasite", "fungal", "eldritch"),
}


BRIEF_STOP_WORDS = frozenset({
    "a", "an", "and", "as", "at", "by", "clothes", "clothing", "fashion", "for", "from",
    "in", "look", "looks", "of", "on", "or", "outfit", "outfits", "over", "paired", "style",
    "styles", "the", "theme", "themed", "to", "under", "wear", "wearing", "with",
})


def _brief_coverage(text: str, garments: list[dict[str, Any]], colors: list[dict[str, Any]], materials: list[dict[str, Any]], styles: list[str]) -> dict[str, Any]:
    """Report what the first-release interpreter can and cannot represent."""
    understood_terms = [
        *[str(row["alias"]) for row in garments],
        *[str(row["value"]) for row in colors],
        *[str(row["value"]) for row in materials],
        *styles,
    ]
    recognized_tokens: set[str] = set()
    for term in understood_terms:
        recognized_tokens.update(re.findall(r"[a-z0-9]+", term.casefold()))
    for style in styles:
        for alias in STYLE_ALIASES.get(style, ()):
            if re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", text, re.IGNORECASE):
                recognized_tokens.update(re.findall(r"[a-z0-9]+", alias.casefold()))
    meaningful_tokens = [token for token in re.findall(r"[a-z0-9]+", text.casefold()) if token not in BRIEF_STOP_WORDS]
    represented = [token for token in meaningful_tokens if token in recognized_tokens]
    unrepresented = list(dict.fromkeys(token for token in meaningful_tokens if token not in recognized_tokens))
    return {
        "score": round((len(represented) / len(meaningful_tokens)) * 100) if meaningful_tokens else 100,
        "understood": list(dict.fromkeys(understood_terms)),
        "unrepresented": unrepresented,
        "note": "Coverage reports interpreter vocabulary, not output quality or semantic similarity.",
    }


CATEGORY_COVERAGE: dict[str, dict[int, tuple[str, ...]]] = {
    "dress": {
        1: ("an ultra-short hem", "a plunging neckline", "high side slits", "an open back", "tiny shoulder straps"),
        2: ("a short flared hem", "a low neckline", "an open back", "slender shoulder straps", "small waist cutouts"),
        3: ("a knee-skimming hem", "a fitted lined bodice", "a square neckline", "a softly defined waist", "a breezy midi hem"),
        4: ("a midi-length skirt", "wide supportive straps", "a higher neckline", "a fully lined bodice", "a light matching layer"),
        5: ("an ankle-length skirt", "a high neckline", "long sleeves", "complete lining", "closed side seams"),
    },
    "top": {
        1: ("a cropped hem", "a deeply scooped neckline", "an open back", "large side cutouts", "a narrow halter shape"),
        2: ("a short fitted hem", "a low neckline", "cap sleeves", "an open shoulder line", "a cropped waist"),
        3: ("a waist-length hem", "a clean neckline", "short sleeves", "a fitted but practical cut", "moderate coverage"),
        4: ("a hip-length hem", "a higher neckline", "long sleeves", "a softly layered fit", "substantial coverage"),
        5: ("a longline hem", "a high closed neckline", "full-length sleeves", "complete torso coverage", "a layered underpiece"),
    },
    "outerwear": {
        1: ("worn fully open", "a cropped open front", "short detached sleeves", "large open side panels", "a barely closed front"),
        2: ("worn open", "a cropped silhouette", "pushed-up sleeves", "a light unlined shell", "an open neckline"),
        3: ("a practical zip front", "a waist-length cut", "adjustable sleeves", "balanced coverage", "a light lining"),
        4: ("a hip-length cut", "a high collar", "full sleeves", "a lined body", "a mostly closed front"),
        5: ("a longline cut", "a fully zipped front", "a protective high collar", "full-length sleeves", "complete lining"),
    },
    "bottom": {
        1: ("an ultra-short rise", "high-cut sides", "a micro hem", "large hip cutouts", "a low-rise waist"),
        2: ("a short hem", "a low-rise waist", "high side slits", "small hip cutouts", "a fitted upper line"),
        3: ("a practical mid-rise waist", "a clean fitted waist", "a knee-skimming length", "moderate coverage", "functional pockets"),
        4: ("a high waist", "a midi or cropped length", "substantial coverage", "a softly structured fit", "deep pockets"),
        5: ("a full-length leg", "a high closed waist", "complete lining", "closed side seams", "full lower-body coverage"),
    },
    "onepiece": {
        1: ("short-cut legs", "large open sides", "a deeply open back", "a low bib", "minimal shoulder straps"),
        2: ("short legs", "an open back", "slender straps", "small side cutouts", "a cropped bib"),
        3: ("a fitted bib", "a balanced leg length", "adjustable shoulder straps", "moderate coverage", "a practical waist"),
        4: ("full-length legs", "a high bib", "wide supportive straps", "substantial coverage", "a softly layered upper body"),
        5: ("full-length legs", "a high closed bib", "a long-sleeve underlayer", "complete torso coverage", "closed side seams"),
    },
    "bodywear": {
        1: ("minimal coverage", "large open body areas", "a plunging center", "high-cut lines", "a mostly open back"),
        2: ("light coverage", "open side areas", "slender straps", "a low neckline", "high-cut hips"),
        3: ("balanced coverage", "controlled cutout placement", "a fitted central panel", "moderate coverage", "a practical open-and-closed balance"),
        4: ("substantial coverage", "wide supportive panels", "a higher neckline", "a lined center", "mostly closed sides"),
        5: ("full torso coverage", "a high neckline", "full sleeves", "complete lining", "closed side panels"),
    },
}

for _category in ("lingerie", "swim", "jewelry", "armor", "suit"):
    CATEGORY_COVERAGE[_category] = CATEGORY_COVERAGE["bodywear" if _category in {"lingerie", "swim", "jewelry"} else "outerwear"]


SAFE_DETAILS: dict[str, tuple[str, ...]] = {
    "dress": ("a softly defined waist", "a gathered bust", "a tiered hem", "a bias-cut skirt", "princess seams", "a shirred back", "a wrap tie", "a fitted bodice"),
    "top": ("contrast binding", "a clean ribbed neckline", "delicate topstitching", "a raw-edge hem", "small covered buttons", "a softly draped neckline", "fine piping"),
    "outerwear": ("a two-way zipper", "adjustable cuffs", "a drawcord hem", "angled pockets", "contrast paneling", "a high collar", "a packable hood"),
    "bottom": ("a shaped waistband", "functional pockets", "contrast topstitching", "a concealed side zip", "a softly pleated front", "a raw-edge hem", "adjustable side tabs"),
    "onepiece": ("adjustable shoulder straps", "a shaped bib", "deep patch pockets", "contrast topstitching", "buttoned side tabs", "a softly defined waist", "a utility zipper"),
    "bodywear": ("adjustable straps", "clean bound edges", "a shaped center panel", "small ring hardware", "a lace-up back", "contrast piping", "a softly structured waist"),
    "lingerie": ("scalloped edging", "tiny satin bows", "adjustable straps", "delicate ruching", "a tiny hook closure", "soft lace panels"),
    "swim": ("secure adjustable ties", "a high-cut leg", "contrast piping", "shell-shaped hardware", "a wrap tie", "a softly sculpted neckline"),
    "jewelry": ("graduated crystal drops", "fine connecting chains", "a centered jewel clasp", "pearl fringe", "tiny star charms", "counterweighted drapes"),
    "armor": ("articulated joints", "a flexible underlayer", "small status lights", "etched panel lines", "quick-release clasps", "a compact utility belt"),
    "suit": ("precise lapels", "a sharply defined waist", "covered buttons", "clean pleats", "a narrow belt", "a satin-trimmed edge"),
}


STYLE_BANKS: dict[str, dict[str, tuple[str, ...]]] = {
    "cute": {"colors": ("pale pink", "powder blue", "butter yellow", "mint green", "lavender", "cream"), "details": ("tiny bows", "scalloped trim", "embroidered daisies", "small rosettes", "pearl buttons"), "accessories": ("glossy Mary Janes", "a cropped pastel cardigan", "a ribbon headband", "a tiny shoulder bag", "jelly sandals")},
    "cozy": {"colors": ("oatmeal", "warm camel", "dusty mauve", "fog gray", "cream"), "details": ("soft ribbing", "blanket stitching", "brushed cuffs", "tiny wooden toggles"), "accessories": ("a long scarf", "soft mitt cuffs", "a fuzzy shoulder bag", "a knitted headband")},
    "gothic": {"colors": ("black", "oxblood", "deep plum", "charcoal", "bone white"), "details": ("black rose embroidery", "antique silver buttons", "velvet ribbons", "thornlike trim"), "accessories": ("a velvet choker", "lace gloves", "platform Mary Janes", "antique silver jewelry")},
    "haunted": {"colors": ("ghost white", "smoky black", "bruise lavender", "faded rose", "antique silver"), "details": ("faded sigil embroidery", "torn ribbon edges", "antique lock charms", "black crystal drops"), "accessories": ("a sheer veil", "antique silver jewelry", "a tiny relic pouch", "dark ribbon cuffs")},
    "rave": {"colors": ("laser magenta", "electric cyan", "acid green", "ultraviolet", "holographic silver"), "details": ("reflective piping", "UV-reactive trim", "pixel hearts", "glowing edge lines"), "accessories": ("LED ear cuffs", "stacked kandi bracelets", "a tinted visor", "a clear mini backpack")},
    "romantic": {"colors": ("blush pink", "ivory", "champagne", "rose red", "soft lavender"), "details": ("satin bows", "tiny roses", "pearl drops", "delicate ruching"), "accessories": ("a pearl choker", "lace gloves", "a heart-shaped mini bag", "delicate ballet flats")},
    "retro": {"colors": ("tomato red", "mustard yellow", "powder blue", "cream", "avocado green"), "details": ("contrast piping", "retro floral print", "rounded buttons", "rickrack trim"), "accessories": ("cat-eye sunglasses", "a small structured handbag", "white ankle socks", "a printed headscarf")},
    "picnic": {"colors": ("strawberry red", "cream", "sky blue", "sage green", "butter yellow"), "details": ("gingham panels", "embroidered strawberries", "tiny floral trim", "scalloped edges"), "accessories": ("a woven basket bag", "canvas sneakers", "a ribbon headband", "simple sandals")},
    "preppy": {"colors": ("navy", "cream", "forest green", "burgundy", "powder blue"), "details": ("contrast tipping", "small crest embroidery", "knife pleats", "clean striped trim"), "accessories": ("penny loafers", "a structured shoulder bag", "knee socks", "a narrow headband")},
    "streetwear": {"colors": ("soft black", "stone gray", "olive green", "cobalt blue", "white"), "details": ("utility webbing", "contrast topstitching", "oversized patch pockets", "a small graphic emblem"), "accessories": ("chunky sneakers", "a crossbody pouch", "a knit beanie", "a compact shoulder bag")},
    "sporty": {"colors": ("white", "navy", "cherry red", "electric blue", "lime green"), "details": ("athletic piping", "mesh side panels", "a quarter zip", "contrast binding"), "accessories": ("clean trainers", "a sport visor", "striped crew socks", "a compact belt bag")},
    "punk": {"colors": ("black", "washed gray", "dark cherry", "acid green", "plaid red"), "details": ("exposed zippers", "safety-pin hardware", "raw edges", "contrast straps"), "accessories": ("heavy boots", "a studded cuff", "a chain belt", "a distressed shoulder bag")},
    "western": {"colors": ("tan", "rust red", "dark denim blue", "cream", "turquoise"), "details": ("western yoke stitching", "soft fringe", "pearl snaps", "tooled trim"), "accessories": ("cowboy boots", "a turquoise belt", "a small suede bag", "a neck scarf")},
    "boho": {"colors": ("sand", "terracotta", "turquoise", "cream", "sunset orange"), "details": ("coin trim", "open crochet", "tassel ties", "embroidered borders"), "accessories": ("layered necklaces", "a fringed pouch", "strappy sandals", "stacked bangles")},
    "formal": {"colors": ("midnight black", "champagne", "ink navy", "emerald", "oxblood"), "details": ("covered buttons", "precise pleats", "satin piping", "a sharply defined waist"), "accessories": ("a sculptural clutch", "long gloves", "a crystal collar", "polished heels")},
    "bridal": {"colors": ("ivory", "pearl white", "champagne", "blush pink"), "details": ("pearl embroidery", "delicate lace edging", "covered rouleau loops", "a detachable train"), "accessories": ("a short veil", "a pearl choker", "lace gloves", "a crystal hair comb")},
    "fantasy": {"colors": ("moonstone white", "forest green", "amethyst", "antique gold", "midnight blue"), "details": ("constellation beading", "leaf filigree", "tiny runes", "crystal dew drops"), "accessories": ("a delicate circlet", "ritual armlets", "a crystal collar", "a tiny spell pouch")},
    "futuristic": {"colors": ("chrome silver", "pearl white", "electric cyan", "gunmetal", "violet chrome"), "details": ("glowing seam lines", "etched circuit marks", "small status lights", "hexagonal vents"), "accessories": ("a translucent visor", "chrome arm cuffs", "a polished data collar", "articulated gloves")},
    "aquatic": {"colors": ("sea-glass green", "lagoon blue", "opal white", "coral pink", "deep ocean violet"), "details": ("water-drop crystals", "shell-shaped clasps", "finlike ruffles", "pearl fringe"), "accessories": ("shell jewelry", "a pearl waist chain", "a sheer watery wrap", "translucent gloves")},
    "doll": {"colors": ("porcelain white", "powder pink", "faded blue", "lacquer red", "aged ivory"), "details": ("tiny bow appliqués", "painted floral details", "heart-shaped buttons", "jointed ring hardware"), "accessories": ("glossy Mary Janes", "a miniature bonnet", "ribbon wrist cuffs", "lace ankle socks")},
    "organic": {"colors": ("black-violet", "abyssal blue", "fungal pink", "bioluminescent cyan", "moss green"), "details": ("pearl nodes", "bioluminescent veins", "soft fin crests", "glowing sucker rosettes"), "accessories": ("tendril armlets", "a living collar organism", "soft carapace cuffs", "a pearl-node headpiece")},
}


STYLE_MATERIALS: dict[str, tuple[str, ...]] = {
    "cute": ("cotton poplin", "cotton voile", "gingham", "eyelet cotton", "light chiffon", "ribbed jersey"),
    "cozy": ("fine knit", "cashmere knit", "ribbed cotton", "fuzzy mohair", "chenille", "cotton fleece", "velvet"),
    "gothic": ("velvet", "lace", "mesh", "silk satin", "leather", "chiffon"),
    "haunted": ("velvet", "lace", "mesh", "chiffon", "organza", "silk satin"),
    "rave": ("mesh", "vinyl", "wet-look Lycra", "technical nylon", "chainmail", "metallic fabric"),
    "romantic": ("silk satin", "lace", "chiffon", "cotton voile", "organza", "velvet"),
    "retro": ("cotton poplin", "gingham", "denim", "corduroy", "fine knit", "velvet"),
    "picnic": ("gingham", "cotton poplin", "cotton voile", "linen", "denim", "eyelet cotton"),
    "preppy": ("wool suiting", "fine knit", "cotton poplin", "wool plaid", "denim"),
    "streetwear": ("denim", "cotton jersey", "cotton fleece", "technical nylon", "leather"),
    "sporty": ("cotton jersey", "stretch jersey", "technical nylon", "mesh", "matte performance fabric"),
    "punk": ("leather", "denim", "mesh", "wool plaid", "vinyl"),
    "western": ("denim", "leather", "cotton twill", "corduroy", "linen"),
    "boho": ("linen", "crochet", "cotton voile", "chiffon", "suede"),
    "formal": ("velvet", "silk satin", "wool suiting", "silk crepe", "brocade"),
    "bridal": ("silk satin", "lace", "chiffon", "organza", "embroidered tulle"),
    "fantasy": ("velvet", "chiffon", "organza", "brocade", "leather"),
    "futuristic": ("vinyl", "technical nylon", "mesh", "chrome", "metallic fabric"),
    "aquatic": ("wet-look Lycra", "mesh", "organza", "pearl-strung", "metallic fabric"),
    "doll": ("silk satin", "lace", "cotton poplin", "organza", "velvet"),
    "organic": ("mesh", "latex", "leather", "pearl-strung", "transparent material"),
}


STYLE_GARMENTS: dict[str, tuple[str, ...]] = {
    "cute": ("sundress", "mini-dress", "dress", "romper", "tank", "camisole", "cardigan", "mini-skirt", "overalls"),
    "cozy": ("cardigan", "hoodie", "turtleneck", "coat", "robe", "leggings", "tank"),
    "gothic": ("mini-dress", "dress", "gown", "corset", "bodysuit", "skirt", "coat", "blazer"),
    "haunted": ("mini-dress", "dress", "gown", "corset", "bodysuit", "robe", "body-jewelry"),
    "rave": ("bodysuit", "bikini", "harness", "mini-skirt", "tank", "shorts", "body-jewelry", "romper"),
    "romantic": ("sundress", "mini-dress", "dress", "gown", "corset", "camisole", "skirt"),
    "retro": ("sundress", "mini-dress", "dress", "shirt", "skirt", "shorts", "overalls", "cardigan"),
    "picnic": ("sundress", "mini-dress", "dress", "blouse", "skirt", "shorts", "overalls", "cardigan"),
    "preppy": ("blazer", "turtleneck", "shirt", "mini-skirt", "skirt", "trousers", "cardigan", "suit"),
    "streetwear": ("t-shirt", "tank", "hoodie", "windbreaker", "jacket", "jeans", "shorts", "overalls"),
    "sporty": ("t-shirt", "tank", "hoodie", "windbreaker", "shorts", "leggings", "bodysuit"),
    "punk": ("t-shirt", "tank", "jacket", "mini-skirt", "jeans", "corset", "harness"),
    "western": ("shirt", "jacket", "jeans", "shorts", "skirt", "mini-dress", "corset"),
    "boho": ("sundress", "dress", "skirt", "camisole", "romper", "body-jewelry"),
    "formal": ("gown", "dress", "suit", "blazer", "trousers", "jumpsuit"),
    "bridal": ("gown", "dress", "mini-dress", "suit", "corset"),
    "fantasy": ("gown", "dress", "corset", "armor", "body-jewelry", "robe"),
    "futuristic": ("bodysuit", "jumpsuit", "armor", "harness", "mini-dress", "windbreaker"),
    "aquatic": ("swimwear", "bikini", "bodysuit", "dress", "body-jewelry"),
    "doll": ("mini-dress", "dress", "sundress", "corset", "lingerie", "cardigan"),
    "organic": ("bodysuit", "harness", "body-jewelry", "corset", "armor", "robe"),
}


DEFAULT_COLORS = ("soft black", "warm white", "cherry red", "powder blue", "butter yellow", "sage green", "dusty pink", "cream", "navy", "plum")
DEFAULT_ACCESSORIES = ("a slim shoulder bag", "simple bead jewelry", "a narrow belt", "a soft headscarf", "a canvas tote", "stacked bracelets", "clean ankle boots", "simple flats")

CATEGORY_COLORS: dict[str, tuple[str, ...]] = {
    "jewelry": ("clear crystal", "mirror silver", "pearl white", "rose gold", "black diamond", "opal rainbow", "ruby red", "sapphire blue"),
    "lingerie": ("black", "ivory", "powder pink", "wine red", "lavender", "ice blue"),
    "swim": ("coral", "aqua blue", "sunny yellow", "white", "cobalt", "watermelon pink"),
    "armor": ("gunmetal", "pearl white", "cobalt blue", "violet chrome", "black", "champagne titanium"),
    "bodywear": ("black", "white", "oxblood", "bubblegum pink", "chrome silver", "deep violet"),
}

CATEGORY_ACCESSORIES: dict[str, tuple[str, ...]] = {
    "jewelry": ("matching ear cuffs", "crystal thigh jewelry", "a narrow jeweled collar", "gem fingertip chains", "ankle chandeliers", "a small halo headpiece"),
    "lingerie": ("a lace choker", "sheer gloves", "thigh jewelry", "a satin eye mask worn up", "delicate body chains"),
    "swim": ("a sheer pareo", "shell jewelry", "a wide sun visor", "an anklet stack", "a woven mini bag"),
    "armor": ("a utility thigh rig", "a translucent visor", "armored gloves", "a compact shoulder module", "a narrow equipment belt"),
    "bodywear": ("matching wrist cuffs", "a structured collar", "thigh straps", "upper-arm bands", "ankle cuffs"),
}


def _matches(mapping: dict[str, str], text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    for alias in sorted(mapping, key=len, reverse=True):
        for match in re.finditer(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", text, re.IGNORECASE):
            span = match.span()
            if any(span[0] < right and span[1] > left for left, right in occupied):
                continue
            occupied.append(span)
            found.append({"raw": match.group(0), "value": mapping[alias], "start": span[0], "end": span[1]})
    return sorted(found, key=lambda row: row["start"])


def _garment_matches(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for spec in GARMENT_SPECS:
        for alias in sorted(spec["aliases"], key=len, reverse=True):
            for match in re.finditer(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", text, re.IGNORECASE):
                candidates.append({"spec": spec, "alias": alias, "start": match.start(), "end": match.end()})
    candidates.sort(key=lambda row: (row["start"], -(row["end"] - row["start"])))
    selected: list[dict[str, Any]] = []
    for row in candidates:
        if any(row["start"] < other["end"] and row["end"] > other["start"] for other in selected):
            continue
        if any(row["spec"]["id"] == other["spec"]["id"] for other in selected):
            continue
        selected.append(row)
    return sorted(selected, key=lambda row: row["start"])


def _clause_start(text: str, position: int, minimum: int = 0) -> int:
    start = minimum
    for match in re.finditer(r"\s+(?:and|with|plus|paired with|under|over)\s+|[,;+]", text[:position], re.IGNORECASE):
        if match.start() >= minimum:
            start = match.end()
    return start


def parse_theme(theme: str) -> dict[str, Any]:
    text = re.sub(r"\s+", " ", str(theme or "")).strip()
    folded = text.casefold()
    garments = _garment_matches(folded)
    colors = _matches(COLORS, folded)
    materials = _matches(MATERIALS, folded)
    styles = [identifier for identifier, aliases in STYLE_ALIASES.items() if any(re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", folded) for alias in aliases)]

    pieces: list[dict[str, Any]] = []
    assigned_color_spans: set[tuple[int, int]] = set()
    assigned_material_spans: set[tuple[int, int]] = set()
    for garment_index, garment in enumerate(garments):
        if garment_index:
            minimum = garments[garment_index - 1]["end"]
            start = _clause_start(folded, garment["start"], minimum)
        else:
            start = 0
        local_colors = [row for row in colors if start <= row["start"] < garment["start"]]
        local_materials = [row for row in materials if start <= row["start"] < garment["start"]]
        for row in local_colors:
            assigned_color_spans.add((row["start"], row["end"]))
        for row in local_materials:
            assigned_material_spans.add((row["start"], row["end"]))
        spec = garment["spec"]
        pieces.append({
            "id": spec["id"],
            "name": spec["name"],
            "category": spec["category"],
            "colors": list(dict.fromkeys(row["value"] for row in local_colors)),
            "materials": list(dict.fromkeys(row["value"] for row in local_materials)),
        })

    global_colors = [row["value"] for row in colors if (row["start"], row["end"]) not in assigned_color_spans]
    global_materials = [row["value"] for row in materials if (row["start"], row["end"]) not in assigned_material_spans]
    return {
        "theme": text,
        "pieces": pieces,
        "colors": list(dict.fromkeys(global_colors)),
        "materials": list(dict.fromkeys(global_materials)),
        "styles": styles,
        "brief_coverage": _brief_coverage(text, garments, colors, materials, styles),
        "hard_constraints": [
            *({"kind": "garment", "value": piece["name"], "piece": piece["id"]} for piece in pieces),
            *({"kind": "color", "value": value} for value in dict.fromkeys(global_colors)),
            *({"kind": "material", "value": value} for value in dict.fromkeys(global_materials)),
        ],
    }


def _spec_by_id(identifier: str) -> dict[str, Any]:
    return next(spec for spec in GARMENT_SPECS if spec["id"] == identifier)


def _coverage_detail(category: str, level: int, rng: random.Random) -> str:
    bank = CATEGORY_COVERAGE.get(category, CATEGORY_COVERAGE["bodywear"])
    return rng.choice(bank[level])


def _style_values(brief: dict[str, Any], field: str) -> list[str]:
    values: list[str] = []
    for style in brief.get("styles") or []:
        values.extend(STYLE_BANKS.get(style, {}).get(field, ()))
    return list(dict.fromkeys(values))


def _style_materials(brief: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    requested: list[str] = []
    for style in brief.get("styles") or []:
        requested.extend(STYLE_MATERIALS.get(style, ()))
    compatible = [value for value in dict.fromkeys(requested) if value in spec["materials"]]
    return compatible


def _piece_phrase(piece: dict[str, Any], brief: dict[str, Any], coverage: int, rng: random.Random) -> tuple[str, str]:
    spec = _spec_by_id(piece["id"])
    variants = list(spec["variants"])
    if coverage == 1:
        preferred = [value for value in variants if any(word in value for word in ("short", "mini", "cropped", "open", "cutout", "micro", "high-cut"))]
        if preferred and rng.random() < 0.65:
            variants = preferred
    elif coverage == 5:
        preferred = [value for value in variants if any(word in value for word in ("long", "full", "wide-leg", "classic", "utility", "floor", "sleeve"))]
        if preferred and rng.random() < 0.65:
            variants = preferred
    variant = rng.choice(variants)
    locked_colors = piece.get("colors") or brief.get("colors")
    colors = locked_colors or brief.get("color_options") or _style_values(brief, "colors") or list(CATEGORY_COLORS.get(spec["category"], DEFAULT_COLORS))
    locked_materials = piece.get("materials") or brief.get("materials")
    material_options = brief.get("material_options")
    if locked_materials:
        materials = locked_materials
    elif material_options:
        materials = material_options
    else:
        preferred_materials = _style_materials(brief, spec)
        materials = preferred_materials if preferred_materials and rng.random() < 0.65 else list(spec["materials"])
    color = " and ".join(locked_colors) if locked_colors and len(locked_colors) > 1 else rng.choice(colors)
    material = " and ".join(locked_materials) if locked_materials and len(locked_materials) > 1 else rng.choice(materials)
    return f"{color} {material} {variant}", _coverage_detail(spec["category"], coverage, rng)


def _join_pieces(phrases: list[tuple[dict[str, Any], str]]) -> str:
    if len(phrases) == 1:
        return phrases[0][1]
    if len(phrases) == 2:
        first, second = phrases
        first_category = first[0]["category"]
        second_category = second[0]["category"]
        if second_category == "outerwear":
            return f"{first[1]} beneath an open {second[1]}"
        if first_category == "outerwear":
            return f"{second[1]} beneath an open {first[1]}"
        if {first_category, second_category} <= {"top", "bottom", "bodywear"}:
            return f"{first[1]} paired with {second[1]}"
        if first_category == "top" and second_category == "dress":
            return f"{first[1]} layered under {second[1]}"
        if second_category == "top" and first_category == "dress":
            return f"{second[1]} layered under {first[1]}"
        return f"{first[1]} with {second[1]}"
    return ", ".join(value for _, value in phrases[:-1]) + f", and {phrases[-1][1]}"


def generate_candidate(
    brief: dict[str, Any],
    *,
    coverage: int,
    complexity: int,
    realism: int,
    rng: random.Random,
    fallback_details: list[str] | None = None,
    fallback_accessories: list[str] | None = None,
) -> tuple[str, str, bool]:
    pieces = list(brief.get("pieces") or [])
    if not pieces:
        material = (brief.get("materials") or [""])[0]
        preferred_ids = {
            identifier
            for style in brief.get("styles") or []
            for identifier in STYLE_GARMENTS.get(style, ())
        }
        if material:
            compatible = [spec for spec in GARMENT_SPECS if material in spec["materials"]]
            if not compatible:
                compatible = [spec for spec in GARMENT_SPECS if spec["category"] in {"dress", "top", "outerwear", "bottom", "onepiece", "bodywear"}]
        else:
            compatible = [spec for spec in GARMENT_SPECS if spec["category"] in {"dress", "top", "outerwear", "bottom", "onepiece"}]
        preferred = [spec for spec in compatible if spec["id"] in preferred_ids]
        if preferred:
            compatible = preferred
        spec = rng.choice(compatible)
        pieces = [{"id": spec["id"], "name": spec["name"], "category": spec["category"], "colors": [], "materials": []}]

    rendered: list[tuple[dict[str, Any], str]] = []
    coverage_details: list[str] = []
    for piece in pieces:
        phrase, detail = _piece_phrase(piece, brief, coverage, rng)
        rendered.append((piece, phrase))
        coverage_details.append(detail)
    base = _join_pieces(rendered)

    primary_category = pieces[0]["category"]
    style_details = _style_values(brief, "details")
    style_accessories = _style_values(brief, "accessories")
    details = [*SAFE_DETAILS.get(primary_category, SAFE_DETAILS["bodywear"])]
    details.extend(fallback_details or [])
    accessories = style_accessories or list(fallback_accessories or []) or list(CATEGORY_ACCESSORIES.get(primary_category, DEFAULT_ACCESSORIES))
    details = list(dict.fromkeys(details))
    accessories = list(dict.fromkeys(accessories))

    selected = [coverage_details[0]]
    if complexity >= 2:
        selected.append(rng.choice(style_details or details))
    if complexity >= 3:
        selected.append(rng.choice(accessories))
    if complexity >= 4:
        selected.append(rng.choice([value for value in details if value not in selected] or details))
    if complexity >= 5:
        selected.append(rng.choice([value for value in accessories if value not in selected] or accessories))

    experimental = realism <= 2
    if experimental:
        experimental_bank = (
            "one detached panel suspended beside the main silhouette",
            "an asymmetrical half-layer connected by visible rings",
            "a sculptural side drape",
            "a removable shoulder-to-hip panel",
            "an exaggerated one-sided volume",
            "transparent outer panels floating above the fitted core",
        )
        selected.insert(min(1, len(selected)), rng.choice(experimental_bank))

    clean_details = list(dict.fromkeys(value for value in selected if value))
    if len(clean_details) == 1:
        tail = clean_details[0]
    elif len(clean_details) == 2:
        tail = f"{clean_details[0]} and {clean_details[1]}"
    else:
        tail = ", ".join(clean_details[:-1]) + f", and {clean_details[-1]}"
    line = f"{base} with {tail}"
    clean_line = re.sub(r"\s+", " ", line).strip(" .")
    # Color, material, silhouette, and detail choices all contribute to the
    # concept. Hard-constrained themes necessarily reuse their garment nouns.
    signature = clean_line.casefold()
    return clean_line, signature, experimental


def fidelity_report(lines: list[str], brief: dict[str, Any]) -> dict[str, Any]:
    constraints: list[dict[str, Any]] = []
    for piece in brief.get("pieces") or []:
        spec = _spec_by_id(piece["id"])
        garment_terms = list(dict.fromkeys([piece["name"], *spec["aliases"], *spec["variants"]]))
        constraints.append({"kind": "garment", "label": piece["name"], "all": [], "any": garment_terms})
        for color in piece.get("colors") or []:
            constraints.append({"kind": "bound color", "label": f"{color} {piece['name']}", "all": [color], "any": garment_terms})
        for material in piece.get("materials") or []:
            constraints.append({"kind": "bound material", "label": f"{material} {piece['name']}", "all": [material], "any": garment_terms})
    for color in brief.get("colors") or []:
        constraints.append({"kind": "color", "label": color, "all": [color], "any": []})
    for material in brief.get("materials") or []:
        constraints.append({"kind": "material", "label": material, "all": [material], "any": []})

    failures: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        folded = line.casefold()
        missing = [
            row["label"]
            for row in constraints
            if not all(term.casefold() in folded for term in row["all"])
            or (row["any"] and not any(term.casefold() in folded for term in row["any"]))
        ]
        if missing:
            failures.append({"line": index + 1, "missing": missing})
    passed = len(lines) - len(failures)
    return {
        "ok": not failures,
        "score": round((passed / len(lines)) * 100) if lines else 0,
        "constraints": [{"kind": row["kind"], "label": row["label"]} for row in constraints],
        "failed_lines": failures,
        "interpreted": {
            "pieces": [piece["name"] for piece in brief.get("pieces") or []],
            "bindings": [
                " ".join([*(piece.get("colors") or []), *(piece.get("materials") or []), piece["name"]])
                for piece in brief.get("pieces") or []
                if piece.get("colors") or piece.get("materials")
            ],
            "colors": list(brief.get("colors") or []),
            "materials": list(brief.get("materials") or []),
            "styles": list(brief.get("styles") or []),
        },
        "brief_coverage": dict(brief.get("brief_coverage") or {}),
    }
