from __future__ import annotations

"""Deterministic, offline Outfit Forge engine and ComfyUI API.

The Forge deliberately separates generation from Creative Library browsing.
It creates editable single-line Outfit logs, audits them, and can publish the
reviewed lines into the canonical Outfit Library hierarchy.
"""

import hashlib
import random
import re
from collections import Counter, defaultdict
from typing import Any, Iterable

from .outfit_forge_anchored_catalog import (
    STRUCTURES as ANCHORED_STRUCTURES,
    base_behavior,
    plural_behavior,
)
from .outfit_forge_theme import fidelity_report, generate_candidate, parse_theme
from .solo_catalog import get_catalog

try:
    from aiohttp import web
    from server import PromptServer
except Exception:  # pragma: no cover - ComfyUI supplies these at runtime.
    web = None
    PromptServer = None


FORGE_VERSION = "2.0"
MAX_GENERATED_LINES = 500
MAX_BANK_ITEMS = 120
MAX_BANK_ITEM_LENGTH = 240
SIMILARITY_THRESHOLD = 0.92
OPENING_WORDS = 16


def _items(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = re.split(r"[\n;|]+", value)
    elif isinstance(value, (list, tuple, set)):
        raw = [str(item or "") for item in value]
    else:
        raw = []
    output: list[str] = []
    seen: set[str] = set()
    for item in raw:
        clean = re.sub(r"\s+", " ", str(item or "")).strip(" \t,;|")
        if not clean or len(clean) > MAX_BANK_ITEM_LENGTH:
            continue
        folded = clean.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        output.append(clean)
        if len(output) >= MAX_BANK_ITEMS:
            break
    return output


def _line(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_filename(value: Any) -> str:
    clean = re.sub(r"[^A-Za-z0-9._ -]+", "", _line(value)).strip(" .")
    clean = re.sub(r"\s+", " ", clean)
    clean = clean[:100] or "Outfit Forge Log"
    return clean if clean.casefold().endswith(".txt") else clean + ".txt"


PACKS: dict[str, dict[str, Any]] = {
    "everyday": {
        "label": "Everyday Fashion", "keywords": ("casual", "everyday", "street", "college", "summer", "daily"),
        "garments": "sundress|ringer tee with soft shorts|oversized tank with relaxed bottoms|fitted knit top with worn denim|button-front romper|cropped cardigan with a bias-cut skirt|easy jersey jumpsuit|boxy tee with pleated shorts|slip skirt with a ribbed tank|lightweight overalls|wrap top with wide-leg trousers|soft polo mini dress",
        "materials": "washed cotton|ribbed jersey|soft linen|worn denim|lightweight poplin|brushed knit|cotton voile|matte jersey",
        "colors": "sun-faded cream|cherry red|powder blue|soft black|butter yellow|sage green|dusty pink|warm white",
        "construction": "easy layered construction|clean everyday tailoring|softly relaxed proportions|a practical mix of fitted and loose pieces|unfussy seams and natural drape|a compact high-low silhouette",
        "motifs": "contrast binding|tiny covered buttons|a single embroidered emblem|fine piping|subtle striped trim|small patch pockets|rolled edges|delicate topstitching",
        "fasteners": "small buttons|a side tie|a short zipper|snap tabs|an adjustable drawcord|a wraparound sash",
        "accessories": "a slim shoulder bag|simple bead jewelry|a soft headscarf|a narrow belt|stacked friendship bracelets|a canvas tote",
        "effects": "lived-in softness|sun-warmed color variation|gentle movement at the hem|a slightly rumpled phone-photo realism|easy off-duty polish|light-catching texture",
    },
    "cozy": {
        "label": "Cozy + Layered", "keywords": ("cozy", "autumn", "winter", "knit", "layered", "oversized", "rainy"),
        "garments": "oversized sweater with tiny lounge shorts|long cardigan over a simple slip|chunky cropped knit with a soft midi skirt|slouchy hoodie with fitted shorts|ribbed lounge set|blanket coat over narrow layers|buttoned sleep shirt|cocoon cardigan with a tank dress|thermal top with soft drawstring pants|leg-warmer layered mini look|turtleneck sweater dress|quilted vest with relaxed separates",
        "materials": "brushed cashmere|chunky wool knit|plush fleece|ribbed cotton|washed flannel|soft chenille|quilted jersey|fuzzy mohair",
        "colors": "oatmeal|cocoa brown|dusty mauve|forest green|cream and charcoal|muted cranberry|fog gray|warm camel",
        "construction": "generous layered volume|a cocooning silhouette|soft dropped shoulders|long-over-short proportions|wrapped blanketlike construction|compact fitted layers beneath one oversized piece",
        "motifs": "cable-knit panels|blanket stitching|soft ribbing|tiny wooden toggles|brushed plaid accents|pom-pom ties|contrast cuffs|quilted channels",
        "fasteners": "horn toggles|a knitted sash|large buttons|a soft wrap tie|a half zipper|hidden snaps",
        "accessories": "a knitted bonnet|a fuzzy shoulder pouch|a long scarf|soft mitt cuffs|a fabric headband|a miniature thermos sling",
        "effects": "visible tactile softness|heavy comfortable drape|slightly rumpled warmth|a halo of fuzzy fibers|layered movement|an inviting worn-in finish",
    },
    "dresses": {
        "label": "Dresses + One-Pieces", "keywords": ("dress", "gown", "babydoll", "sundress", "romper", "one-piece"),
        "garments": "babydoll mini dress|bias-cut slip dress|tiered sundress|square-neck milkmaid dress|one-shoulder column dress|bubble-hem mini dress|button-front tea dress|halter handkerchief dress|draped jersey mini|sculpted cocktail dress|wide-leg jumpsuit|playful puff-sleeve romper",
        "materials": "silk charmeuse|crisp cotton poplin|sheer chiffon|matte crepe|glossy satin|embroidered organza|stretch velvet|fine mesh over opaque lining",
        "colors": "black cherry|ivory|candy pink|cobalt blue|pale lemon|deep plum|mint green|silver gray",
        "construction": "a sharply defined waist and released skirt|a floating high-volume hem|asymmetric draping|a fitted torso with exaggerated sleeves|a low fluid bias line|a compact sculptural bodice",
        "motifs": "tiny bows|scattered crystals|appliqué flowers|contrast ruffles|covered buttons|embroidered stars|ribbon channels|pleated fans",
        "fasteners": "a corset-laced back|a concealed zipper|a halter tie|pearl buttons|side hooks|a wrap sash",
        "accessories": "opera gloves|a jeweled mini bag|a ribbon choker|a delicate waist chain|a tiny fascinator|a short shoulder veil",
        "effects": "a weightless floating hem|liquid movement|crisp editorial volume|soft translucency between layers|a flash-lit sheen|deliberate couture imbalance",
    },
    "formal": {
        "label": "Formal + Tailored", "keywords": ("formal", "tailored", "suit", "bridal", "ceremonial", "evening"),
        "garments": "deconstructed tuxedo set|floor-length evening gown|cropped blazer with a column skirt|waistcoat worn as a fitted top with trousers|ceremonial cape dress|sculpted peplum suit|backless tailored jumpsuit|asymmetric dinner dress|longline vest with a sheer underlayer|bridal mini with detachable train|double-breasted coat dress|silk blouse with sharply pleated trousers",
        "materials": "wool barathea|silk faille|heavy satin|fine suiting|velvet|crystal-beaded tulle|brocade|polished crepe",
        "colors": "midnight black|champagne|oxblood|pearl white|ink navy|antique gold|smoky lilac|emerald",
        "construction": "precise architectural tailoring|a long uninterrupted vertical line|controlled asymmetric drape|formal structure interrupted by one exposed plane|a fitted core with removable ceremonial volume|sharp shoulders and a narrow waist",
        "motifs": "satin lapels|hand-set crystals|embroidered heraldic marks|pearl piping|knife pleats|covered rouleau loops|tonal beading|metallic soutache",
        "fasteners": "jewel buttons|a concealed hook placket|a long back zipper|a wrapped cummerbund|a shoulder clasp|a line of tiny rouleau loops",
        "accessories": "a sculptural clutch|long gloves|a narrow formal tie|a crystal collar|a miniature veil|a polished waist ornament",
        "effects": "high-flash polish|controlled train movement|deep velvet light absorption|knife-sharp edges|a restrained metallic glint|formal stillness broken by one moving panel",
    },
    "lingerie": {
        "label": "Lingerie + Boudoir", "keywords": ("lingerie", "boudoir", "lace", "garter", "corset", "intimate"),
        "garments": "open-cup lingerie set|longline bralette with split tap shorts|sheer slip with detachable garters|underbust corset with high-cut briefs|soft-cup balconette with a suspender belt|lace teddy with open sides|ribbon-laced bodysuit|quarter-cup bra with a tiny bustle brief|sheer robe over minimal lingerie|pearl-strung body teddy|structured basque with floating stockings|bias-cut nightdress with a deeply open back",
        "materials": "French lace|silk satin|transparent mesh|glossy stretch satin|embroidered tulle|soft velvet elastic|sheer chiffon|pearl-strung cord",
        "colors": "powder pink|black|ivory|wine red|lavender|ice blue|peach nude|mint",
        "construction": "delicate tensioned panels|open negative-space construction|soft cups against sharper strap geometry|a corseted center with floating outer pieces|high-cut lines and suspended details|barely connected front and back elements",
        "motifs": "tiny satin bows|scalloped lace|pearl drops|heart sliders|crystal rosettes|eyelash fringe|ribbon flowers|contrast picot edging",
        "fasteners": "garter clips|ribbon lacing|tiny hook-and-eye tabs|pearl buttons|heart-shaped rings|sliding strap hardware",
        "accessories": "a lace choker|sheer gloves|a tiny feather fan|thigh jewelry|a satin eye mask worn up|delicate body chains",
        "effects": "soft translucency|glossy highlight along the seams|floating lace edges|a barely-there layered illusion|subtle tension between straps|a powdery vintage finish",
    },
    "rave": {
        "label": "Rave + Festival", "keywords": ("rave", "festival", "club", "edm", "neon", "cyber", "glow"),
        "garments": "reflective micro set|open rave harness with detachable panels|mesh catsuit broken by large cutouts|LED-edged bikini layers|holographic chaps over a tiny bodysuit|fiber-optic fringe dress|transparent vinyl shrug with a micro skirt|UV-reactive wrap set|chainmail halter with floating hip pieces|iridescent asymmetric bodysuit|kandi-strung body harness|glossy cutout romper",
        "materials": "holographic vinyl|UV-reactive mesh|reflective tape|transparent PVC|iridescent foil knit|fiber-optic strands|liquid-shine Lycra|aluminum chainmail",
        "colors": "laser magenta|electric cyan|acid green|ultraviolet|holographic silver|neon orange|candy rainbow|black with prismatic light",
        "construction": "high-mobility cutout construction|modular clip-on pieces|a glowing open lattice|asymmetric straps crossing large negative spaces|tiny panels suspended from reflective lines|dance-responsive fringe architecture",
        "motifs": "pixel hearts|glowing stars|kandi beads|reflective flames|holographic butterflies|tiny alien charms|laser-cut spirals|UV flowers",
        "fasteners": "carabiner clips|glowing buckles|clear snaps|O-rings|magnetic tabs|adjustable bungee cords",
        "accessories": "LED ear cuffs|a clear mini backpack|stacked kandi cuffs|tinted visor glasses|fiber-optic hair clips|platform ankle bands",
        "effects": "UV fluorescence|chasing LED light|oil-slick color shift|reflective flash flare|sparkling motion trails|glowing translucent edges",
    },
    "harness": {
        "label": "Harness + Fetish", "keywords": ("harness", "fetish", "bondage", "straps", "latex", "bodywear"),
        "garments": "open geometric body harness|cage bra with a matching hip frame|latex strap dress|suspender harness with detached cuffs|body-chain corset|buckled chaps with a minimal center piece|wide collar linked to a waist cage|asymmetric torso sling|O-ring connected strap bodysuit|open-sided vinyl basque|thigh-to-shoulder tension harness|minimal three-point body frame",
        "materials": "polished leather|glossy latex|rubberized elastic|black chrome chain|transparent vinyl|satin-backed straps|mirror-finish hardware|soft suede webbing",
        "colors": "black|oxblood|white|bubblegum pink|chrome silver|deep violet|electric blue|clear smoke",
        "construction": "load-bearing strap geometry|open cage construction|a few wide bands opposed by many fine lines|symmetrical restraint architecture|one diagonal tension path|modular rings joining detached body zones",
        "motifs": "heart-shaped rings|spike-free studs|chain tassels|crystal rivets|contrast stitching|small lock charms|rounded buckles|metallic edge piping",
        "fasteners": "roller buckles|locking O-rings|snap hooks|magnetic cuffs|lace-up tabs|sliding harness keepers",
        "accessories": "matching wrist cuffs|a structured collar|thigh straps|a tiny chain pouch|upper-arm bands|ankle cuffs",
        "effects": "hard glossy reflections|precise strap tension|a wet-look finish|suspended negative space|flash-bright metal highlights|sharp graphic shadows",
    },
    "swim": {
        "label": "Swim + Beach", "keywords": ("swim", "beach", "pool", "bikini", "resort", "aquatic"),
        "garments": "asymmetric bikini with a wrap skirt|deep-cut one-piece swimsuit|string bikini beneath an open crochet layer|scarf-tied bandeau set|sporty zip-front swim suit|cutout monokini|retro high-waist bikini|micro triangle set with a sheer pareo|ruffled swim dress|metallic resort bodysuit|sarong-built halter set|open-weave beach tunic over minimal swimwear",
        "materials": "matte swim jersey|wet-look Lycra|open crochet|sheer gauze|metallic swim knit|ribbed stretch fabric|quick-dry mesh|silky scarf fabric",
        "colors": "coral|aqua blue|sunny yellow|white|tropical green|cobalt|watermelon pink|sea-glass gradient",
        "construction": "secure swim-ready ties|a high-leg sculpted line|wrapped scarf construction|sporty paneling with exposed sides|a minimal suit beneath one floating layer|adjustable resort draping",
        "motifs": "shell rings|tropical flowers|contrast piping|tiny nautical knots|pearl beads|wave-shaped cutouts|sunburst hardware|sea-glass charms",
        "fasteners": "scarf ties|shell clasps|waterproof zippers|sliding rings|back hooks|braided cords",
        "accessories": "a sheer pareo|shell jewelry|a wide sun visor|an anklet stack|a woven mini bag|a translucent beach scarf",
        "effects": "wet reflective sheen|sunlit translucency|salt-softened texture|wind-lifted layers|water-drop sparkle|a vivid resort color shift",
    },
    "fantasy": {
        "label": "Fantasy + Mythic", "keywords": ("fantasy", "fairy", "elf", "witch", "goddess", "myth", "celestial", "druid"),
        "garments": "ritual wrap dress|petal-built fairy bodice with a split skirt|moon-priestess body drape|forest ranger corset with layered panels|sorceress gown broken into floating veils|elven tunic with sculpted hip guards|oracle robe with an open geometric understructure|dragon-scale mini armor dress|star-chain celestial set|mushroom-cap mantle with a fitted body layer|enchanted bridal gown|asymmetric faun festival regalia",
        "materials": "moonlit silk|leaf-veined organza|soft leather|iridescent scale mesh|velvet|crystal-thread tulle|woven vine fiber|aged metallic brocade",
        "colors": "moonstone white|forest green|amethyst|midnight blue|antique gold|mushroom pink|ember red|opal rainbow",
        "construction": "ritual layered construction|floating magical panels|organic asymmetry|a fitted understructure beneath weightless veils|armorlike accents around a fluid core|branching lines that echo natural growth",
        "motifs": "crescent moons|tiny runes|pressed flowers|constellation beading|leaf filigree|crystal dew drops|moth-wing embroidery|dragon-scale edging",
        "fasteners": "enchanted clasps|ribbon lacing|leaf-shaped hooks|crystal toggles|braided vine ties|moon-ring connectors",
        "accessories": "a delicate circlet|ritual armlets|a tiny spell pouch|a crystal collar|pointed shoulder jewelry|a veil of fine chains",
        "effects": "faint bioluminescence|weightless floating edges|slow color-changing embroidery|starlike sparkle|soft magical mist caught in the layers|living botanical movement",
    },
    "armor": {
        "label": "Armor + Sci-Fi", "keywords": ("armor", "armour", "sci-fi", "scifi", "mecha", "space", "cybernetic", "battle"),
        "garments": "segmented light armor suit|cropped armored jacket with articulated hip plates|sleek pilot bodysuit|ceremonial breastplate over a flexible underlayer|asymmetric battle dress|modular exosuit harness|open-sided spacewear set|scout armor with a short utility cape|techwear jumpsuit with floating hard panels|gladiator-inspired plated bodywear|android shell dress|high-collar command suit",
        "materials": "brushed titanium|carbon fiber|flexible ballistic mesh|translucent polymer|ceramic armor plates|chrome alloy|rubberized technical knit|holographic smart fabric",
        "colors": "gunmetal|white and cyan|black with warning red|champagne titanium|cobalt blue|olive and orange|violet chrome|pearl gray",
        "construction": "articulated modular plating|a flexible body layer beneath floating armor|asymmetric protection zones|interlocking hard and soft panels|a compact exoskeletal frame|battle-ready mobility cuts",
        "motifs": "status lights|unit markings|warning stripes|etched circuit lines|small heraldic emblems|holographic rank bars|hexagonal vents|glowing seams",
        "fasteners": "magnetic locks|quick-release buckles|servo clasps|vacuum seals|rotating hardpoints|flush technical zippers",
        "accessories": "a utility thigh rig|a translucent visor|a compact shoulder module|armored gloves|a data collar|a narrow equipment belt",
        "effects": "projected edge light|subtle powered movement|mirror-bright highlights|transparent interface glow|battle-worn surface variation|clean high-tech luminescence",
    },
    "organic": {
        "label": "Organic + Living", "keywords": ("organic", "living", "symbiote", "tentacle", "parasite", "fungal", "botanical", "eldritch"),
        "garments": "living halter organism with a coiled hip frame|breathing membrane dress|root-grown body lattice|symbiotic second-skin suit|petal-creature bodice with trailing tendrils|fungal mantle linked to a mycelial underlayer|tentacle-built chest and thigh harness|soft carapace corset with living side panels|jelly membrane wrap|colonial creature swarm garment|vine-grown open bodysuit|bio-organic robe that clings at isolated points",
        "materials": "oil-slick membrane|velvet-soft tendrils|translucent bio-gel|pearlescent chitin|root fiber|breathing mesh|jellylike skin|iridescent fungal tissue",
        "colors": "black-violet|abyssal blue|fungal pink|bioluminescent cyan|moss green|pearl white|bruise lavender|coral red",
        "construction": "self-supporting living anatomy|branching organic growth|sucker-held open construction|a breathing membrane suspended between tendrils|colonial units forming a larger silhouette|soft plates grown around flexible joints",
        "motifs": "glowing sucker rosettes|pearl nodes|fine cilia|tiny gill frills|seedpod beads|eye-like gems|soft fin crests|bioluminescent veins",
        "fasteners": "suction disks|coiling tendrils|root hooks|living mouth clasps|soft gripping cilia|self-tightening loops",
        "accessories": "a living collar organism|tendril armlets|a pearl-node headpiece|soft carapace cuffs|a trailing spinal creature|glowing ankle colonies",
        "effects": "slow breathing ripples|responsive bioluminescence|wet iridescent sheen|self-adjusting tension|gentle coordinated movement|a pulse of light traveling between anchors",
    },
    "jewelry": {
        "label": "Jewelry + Near-Nothing", "keywords": ("jewelry", "jewellery", "crystal", "chain", "adornment", "ornament", "barely"),
        "garments": "crystal body-chain constellation|pearl curtain body drape|chandelier hip frame|gem-strung chest and waist lattice|metallic fringe suspended from a collar|constellation of floating brooches|rhinestone garter architecture|chainmail micro drape|ornamental shoulder-to-thigh cascade|five-point jewel suspension piece|crystal apron held by hair-fine chains|halo-ring body mobile",
        "materials": "rhinestone chain|freshwater pearls|mirror-polished silver|prismatic crystal|rose-gold wire|black diamond beads|opal cabochons|fine champagne chain",
        "colors": "clear crystal|pearl white|rose gold|mirror silver|black diamond|opal rainbow|ruby|sapphire blue",
        "construction": "counterweighted jewelry suspension|nearly invisible connecting lines|chandelier-like graduated tiers|open constellation geometry|isolated ornaments linked across bare space|a few structural rings carrying many delicate falls",
        "motifs": "star charms|water-drop gems|tiny hearts|crescent pendants|crystal flowers|miniature halos|butterfly jewels|graduated pearl drops",
        "fasteners": "jewel clasps|magnetic studs|fine lobster clasps|sliding chain loops|pearl toggles|tiny ornamental hooks",
        "accessories": "matching ear cuffs|crystal thigh jewelry|a halo headpiece|gem fingertip chains|ankle chandeliers|a narrow jeweled collar",
        "effects": "dense flash sparkle|floating-jewel illusion|rainbow refraction|delicate counterweighted movement|mirror-bright glints|a rain of tiny highlights",
    },
    "avantgarde": {
        "label": "Avant-Garde Couture", "keywords": ("avant", "couture", "surreal", "editorial", "runway", "sculptural", "conceptual"),
        "garments": "asymmetric sculptural dress|deconstructed suit transformed into body architecture|inflated tube garment|floating-panel corset look|kinetic mobile dress|one-sided cocoon coat|rigid hip sculpture with a minimal torso piece|folded-paper jumpsuit|transparent pane dress|spiral ribbon body construction|oversized collar carrying a tiny lower silhouette|modular garment assembled from detached geometric pieces",
        "materials": "bonded neoprene|clear acrylic|crushed metallic foil|architectural felt|molded silicone|stiffened organza|inflatable vinyl|laser-cut leather",
        "colors": "optic white|absolute black|safety orange|chrome|ultraviolet|monochrome blush|cobalt|acid yellow",
        "construction": "impossible-looking counterbalance|deliberately displaced garment architecture|extreme asymmetric volume|detached pieces held in visual tension|a rigid frame interrupted by fluid material|transformable modular construction",
        "motifs": "oversized eyelets|cutaway circles|repeated fins|graphic seam maps|floating disks|architectural pleats|inflated knots|mirrored tabs",
        "fasteners": "exposed industrial hinges|magnetic standoffs|oversized zippers|structural lacing|clear locking rods|modular snap rails",
        "accessories": "a sculptural face frame|one monumental cuff|an architectural mini bag|a single exaggerated glove|a rigid neck halo|geometric shoe covers",
        "effects": "gallery-object stillness|kinetic balancing movement|hard flash reflections|shadow-casting volume|transparent floating planes|a dramatic transformation between angles",
    },
    "anchored": {
        "label": "Anchored Experimental Bodywear", "keywords": ("anchor", "anchored", "suction", "threaded", "docking", "suspended", "eldritch"),
        "garments": "living body harness|suspended chest and hip framework|minimal anchored body drape|open lattice bodypiece|tendril-built halter and thigh wraps|floating membrane garment|jewelry-suspended body curtain|organic chest frame with asymmetrical garters",
        "materials": "oil-slick living ribbons|translucent membrane|glossy tendrils|pearlescent bioelastic cords|soft chitin lace|iridescent mesh|velvet-black appendages|jellylike straps",
        "colors": "black-violet|abyssal blue|opal white|deep teal|bruise lavender|phosphor cyan|oil-slick rainbow|smoky rose",
        "construction": "isolated anchors carrying open spans|self-tensioning living geometry|suction-supported negative space|threaded suspension between body jewelry|coiling appendages replacing conventional seams|a few gripping points holding large floating forms",
        "motifs": "glowing sucker rosettes|pearl nodes|crystal drops|gill-like frills|tiny orbiting rings|soft fin crests|bioluminescent veins|living clasp creatures",
        "fasteners": "suction seals|threaded jewelry anchors|coiling tendrils|magnetic docking points|soft mouth clasps|rootlike hooks",
        "accessories": "living garters|a tendril collar|pearl-node cuffs|a membrane veil|organic thigh jewelry|a trailing spinal cascade",
        "effects": "self-correcting tension|slow bioluminescent pulses|responsive living movement|wet iridescent sheen|weightless suspension|gentle contraction around every anchor",
    },
}


# Explicit garment words in a brief are stronger than a broad structure pack.
# This prevents a request for sundresses from wandering into cocktail dresses,
# rompers, or jumpsuits merely because they share the Dresses pack.
GARMENT_FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "id": "sundress", "label": "Sundresses", "pattern": r"\bsun[ -]?dresses?\b",
        "garments": "babydoll sundress|fit-and-flare sundress|tiered sundress|smocked sundress|wrap sundress|button-front sundress|pinafore sundress|halter sundress|square-neck sundress|prairie sundress|slip sundress|empire-waist sundress|ruffle-hem sundress|tie-strap sundress|midi sundress|mini sundress",
        "garments_by_coverage": {
            1: "mini sundress|slip sundress|tie-strap sundress|halter sundress|babydoll sundress|ruffle-hem mini sundress",
            2: "babydoll sundress|halter sundress|slip sundress|tie-strap sundress|smocked mini sundress|wrap mini sundress",
            3: "babydoll sundress|fit-and-flare sundress|tiered sundress|smocked sundress|wrap sundress|button-front sundress|pinafore sundress|halter sundress|square-neck sundress|prairie sundress|slip sundress|empire-waist sundress|ruffle-hem sundress|tie-strap sundress|midi sundress|mini sundress",
            4: "midi sundress|prairie sundress|button-front sundress|pinafore sundress|tiered sundress|fit-and-flare sundress|empire-waist sundress",
            5: "maxi sundress|long prairie sundress|ankle-length button-front sundress|layered pinafore sundress|long tiered sundress|long-sleeve empire-waist sundress",
        },
        "materials": "soft cotton poplin|eyelet cotton|light floral chiffon|washed linen|seersucker|cotton voile|lightweight gingham|broderie anglaise|soft jersey|daisy-print cotton",
        "construction": "a gathered empire waist|a smocked bodice|a softly fitted waist|a loose flared skirt|a tiered breezy skirt|a ruched bust|a button-front bodice|a wrap-tied waist|a softly pleated skirt|a fitted princess-seam bodice|a shirred back panel|a gently dropped waist",
        "motifs": "tiny bow straps|embroidered daisies|scalloped eyelet trim|a strawberry print|delicate floral embroidery|lace-edged straps|small covered buttons|a gingham check|tiny rosette details|contrast piping|a ribbon-trimmed neckline|scattered pastel flowers",
        "fasteners": "ribbon shoulder ties|small front buttons|a concealed side zipper|a back bow tie|a wraparound sash|a short button placket|adjustable shoulder ties|a delicate halter tie",
        "accessories": "cream ballet flats|glossy Mary Janes|simple canvas sneakers|a cropped cream cardigan|a lightweight denim jacket|white ankle socks and flats|a ribbon headband|jelly sandals|a delicate beaded anklet|a small woven shoulder bag|a fitted baby tee underneath|bare legs and simple sandals",
        "effects": "a breezy summer drape|a softly fluttering hem|lightweight movement|a crisp sunlit finish|gentle volume through the skirt|soft lived-in texture",
        "coverage": {
            1: "an ultra-short flared hem|a deeply open back|tiny tie straps|high side slits|a plunging tie-front bodice",
            2: "a short airy skirt|an open back|slender ribbon straps|a low square neckline|small side-waist cutouts",
            3: "a knee-skimming hem|a fitted lined bodice|a square neckline|wide shoulder straps|a breezy midi skirt",
            4: "a calf-length skirt|a higher neckline|wide shoulder straps|a light matching cardigan|a softly lined bodice",
            5: "an ankle-length skirt|a high neckline|long puff sleeves|a fully lined bodice|a buttoned lightweight cardigan",
        },
    },
    {"id": "babydoll", "label": "Babydoll Dresses", "pattern": r"\bbabydoll(?: dresses?| minis?)?\b", "garments": "babydoll mini dress|empire-waist babydoll dress|puff-sleeve babydoll dress|sheer-overlay babydoll dress|square-neck babydoll dress|ruffled babydoll dress|satin babydoll dress|eyelet babydoll sundress|velvet babydoll mini|bow-strap babydoll dress"},
    {"id": "gown", "label": "Gowns", "pattern": r"\b(?:gowns?|ballgowns?)\b", "garments": "bias-cut evening gown|column gown|open-back satin gown|tiered chiffon gown|sculpted ballgown|one-shoulder gown|halter-neck gown|corseted formal gown|cape-backed gown|slip gown|draped jersey gown|embroidered tulle gown"},
    {"id": "dress", "label": "Dresses", "pattern": r"\b(?:dresses?|minidresses?|mini dresses?)\b", "garments": "babydoll mini dress|bias-cut slip dress|tiered day dress|square-neck dress|one-shoulder column dress|bubble-hem mini dress|button-front tea dress|halter handkerchief dress|draped jersey mini dress|wrap dress|pinafore dress|shirt dress|sweater dress|fit-and-flare dress"},
    {"id": "romper", "label": "Rompers", "pattern": r"\brompers?\b", "garments": "button-front romper|puff-sleeve romper|halter romper|wrap-front romper|open-back romper|utility romper|ruffled playsuit|tailored short romper|smocked cotton romper|cutout festival romper"},
    {"id": "jumpsuit", "label": "Jumpsuits", "pattern": r"\bjumpsuits?\b", "garments": "wide-leg jumpsuit|fitted catsuit-style jumpsuit|halter jumpsuit|wrap-front jumpsuit|open-back jumpsuit|utility jumpsuit|tailored evening jumpsuit|strapless column jumpsuit|cutout jersey jumpsuit|zip-front technical jumpsuit"},
    {"id": "lingerie", "label": "Lingerie", "pattern": r"\b(?:lingerie|intimates?|underwear)\b", "garments": "longline bralette and matching briefs|soft-cup lingerie set|sheer slip with detachable garters|underbust corset with high-cut briefs|balconette bra with a suspender belt|lace teddy|ribbon-laced bodysuit|quarter-cup bra with a tiny bustle brief|sheer robe over a minimal lingerie set|structured basque with floating stockings"},
    {"id": "corset", "label": "Corsets", "pattern": r"\b(?:corsets?|bustiers?|basques?)\b", "garments": "underbust corset|overbust corset|longline bustier|open-cup basque|ribbon-laced corset top|sheer-panel corset|waist-cinching satin corset|structured corset bodysuit|cropped corset top|pearl-strung corset frame"},
    {"id": "bodysuit", "label": "Bodysuits", "pattern": r"\b(?:bodysuits?|catsuits?|leotards?|teddies)\b", "garments": "high-cut bodysuit|open-sided bodysuit|sheer mesh bodysuit|asymmetrical one-sleeve bodysuit|cutout catsuit|deep-back leotard|lace teddy|zip-front bodysuit|strapless sculpted bodysuit|ribbon-laced body teddy"},
    {"id": "harness", "label": "Harness Bodywear", "pattern": r"\b(?:harnesses?|bondage wear|strap bodywear)\b", "garments": "open geometric body harness|cage bra with a matching hip frame|suspender harness with detached cuffs|body-chain corset|wide collar linked to a waist cage|asymmetric torso sling|O-ring connected strap bodysuit|open-sided vinyl basque|minimal three-point body frame|thigh-to-shoulder tension harness"},
    {"id": "swim", "label": "Swimwear", "pattern": r"\b(?:swimwear|swimsuits?|bikinis?|monokinis?|beachwear)\b", "garments": "asymmetric bikini|deep-cut one-piece swimsuit|string bikini with an open crochet layer|scarf-tied bandeau set|sporty zip-front swimsuit|cutout monokini|retro high-waist bikini|micro triangle bikini with a sheer pareo|ruffled swim dress|metallic resort bodysuit"},
    {"id": "robe", "label": "Robes", "pattern": r"\b(?:robes?|kimonos?|dressing gowns?)\b", "garments": "short satin robe|floor-length silk robe|open chiffon robe|waffle-knit bathrobe|velvet dressing gown|kimono-style robe|sheer lace robe|hooded jersey robe|feather-trimmed boudoir robe|lightweight linen robe"},
    {"id": "suit", "label": "Suits + Tailoring", "pattern": r"\b(?:suits?|tuxedos?|tailoring|tailored separates)\b", "garments": "deconstructed tuxedo set|cropped blazer with a column skirt|waistcoat worn with wide-leg trousers|sculpted peplum suit|backless tailored jumpsuit|longline vest with a sheer underlayer|double-breasted coat dress|silk blouse with sharply pleated trousers|short suit with an oversized blazer|fitted vest and cigarette trousers"},
    {"id": "skirt", "label": "Skirt Outfits", "pattern": r"\bskirts?\b", "garments": "bias-cut midi skirt with a fitted tank|pleated mini skirt with a cropped cardigan|wrap skirt with a soft camisole|tiered maxi skirt with a tiny halter|bubble mini skirt with a fitted tee|denim mini skirt with a ribbed tank|sheer overlay skirt with a bodysuit|pencil skirt with a cropped blazer|ruffled micro skirt with a bralette|circle skirt with a tucked blouse"},
    {"id": "tank", "label": "Tank Outfits", "pattern": r"\b(?:tank tops?|tanks|camisoles?|camis)\b", "garments": "oversized tank with soft shorts|fitted ribbed tank with worn denim|contrast-trim tank with a pleated mini|longline camisole with lounge shorts|cropped tank with wide-leg trousers|soft jersey tank dress|racerback tank with a wrap skirt|lace-trim camisole with a cardigan|boxy tank with fitted bike shorts|thermal camisole with drawstring pants"},
    {"id": "armor", "label": "Armor", "pattern": r"\b(?:armor|armour|breastplates?|battlewear)\b", "garments": "segmented light armor suit|cropped armored jacket with articulated hip plates|sleek pilot bodysuit|ceremonial breastplate over a flexible underlayer|asymmetric battle dress|modular exosuit harness|open-sided spacewear set|scout armor with a short utility cape|gladiator-inspired plated bodywear|high-collar command suit"},
    {"id": "body-jewelry", "label": "Body Jewelry", "pattern": r"\b(?:body jewelry|body jewellery|jewel(?:ry|lery) outfits?|crystal nudity)\b", "garments": "crystal body-chain constellation|pearl curtain body drape|rhinestone chest and hip harness|chandelier fringe body piece|jeweled garter lattice|silver chain apron|gemstone collar-to-waist cascade|crystal shoulder-and-thigh drape|waist-chain skirt with matching pasties|floating jewel body harness"},
    {"id": "organic", "label": "Living Bodywear", "pattern": r"\b(?:tentacles?|symbiotes?|living bodywear|organic bodywear|parasites?)\b", "garments": "living halter organism with a coiled hip frame|breathing membrane dress|root-grown body lattice|symbiotic second-skin suit|petal-creature bodice with trailing tendrils|fungal mantle linked to a mycelial underlayer|tentacle-built chest and thigh harness|soft carapace corset with living side panels|jelly membrane wrap|vine-grown open bodysuit"},
)


STYLE_OVERLAYS: tuple[dict[str, Any], ...] = (
    {
        "id": "cute", "pattern": r"\b(?:cute|girly|sweet|adorable|kawaii)\b",
        "colors": "soft white|pale pink|powder blue|butter yellow|mint green|lavender|peach|cream|strawberry red|sky blue",
        "materials": "soft cotton|eyelet cotton|light chiffon|satin|gingham|seersucker|fine jersey|embroidered voile",
        "motifs": "tiny bows|embroidered daisies|scalloped lace trim|small rosettes|a strawberry print|delicate ruffles|pearl buttons|ribbon edging|tiny floral embroidery|heart-shaped buttons",
        "accessories": "cream ballet flats|glossy Mary Janes|white ankle socks|frilled knee socks|a cropped pastel cardigan|a ribbon headband|simple canvas sneakers|jelly sandals|a tiny shoulder bag|a delicate beaded anklet",
    },
    {
        "id": "gothic", "pattern": r"\b(?:goth|gothic|mourning|vampire|witchy)\b",
        "colors": "black|oxblood|deep plum|charcoal|midnight blue|bone white|dark cherry|smoky violet",
        "materials": "black lace|crushed velvet|matte satin|sheer mesh|dark brocade|washed leather|smoky chiffon",
        "motifs": "cross-shaped hardware|black rose embroidery|scalloped lace|antique silver buttons|thornlike trim|velvet ribbons|tiny moon charms|spiderweb beading",
        "accessories": "a velvet choker|lace gloves|platform Mary Janes|a miniature veil|silver chain jewelry|a tiny structured bag",
    },
    {
        "id": "neon", "pattern": r"\b(?:neon|rave|festival|edm|uv|glowing|cyber)\b",
        "colors": "laser magenta|electric cyan|acid green|ultraviolet|holographic silver|neon orange|candy rainbow|black with prismatic color",
        "materials": "holographic vinyl|UV-reactive mesh|reflective tape|transparent PVC|iridescent foil knit|fiber-optic strands|liquid-shine Lycra",
        "motifs": "pixel hearts|glowing stars|kandi beads|reflective flames|holographic butterflies|tiny alien charms|UV flowers",
        "accessories": "LED ear cuffs|a clear mini backpack|stacked kandi cuffs|tinted visor glasses|fiber-optic hair clips|platform ankle bands",
    },
    {
        "id": "romantic", "pattern": r"\b(?:romantic|bridal|valentine|coquette)\b",
        "colors": "blush pink|ivory|champagne|rose red|powder blue|soft lavender|pearl white",
        "materials": "silk charmeuse|fine lace|embroidered tulle|soft satin|sheer organza|cotton eyelet",
        "motifs": "satin bows|pearl drops|tiny roses|scalloped lace|heart-shaped buttons|ribbon flowers|delicate ruching",
        "accessories": "a pearl choker|a ribbon headband|a tiny veil|lace gloves|a heart-shaped mini bag|delicate ballet flats",
    },
    {
        "id": "aquatic", "pattern": r"\b(?:aquatic|siren|mermaid|jellyfish|ocean|underwater)\b",
        "colors": "sea-glass green|lagoon blue|opal white|coral pink|deep ocean violet|pearlescent aqua",
        "materials": "wet-look Lycra|iridescent organza|translucent mesh|pearl-strung cord|jellylike vinyl|scale-textured knit",
        "motifs": "pearl drops|shell-shaped clasps|wave embroidery|water-drop crystals|finlike ruffles|jellyfish fringe",
        "accessories": "shell jewelry|a pearl waist chain|translucent gloves|a fin-shaped shoulder piece|a sheer watery wrap",
    },
    {
        "id": "doll", "pattern": r"\b(?:doll|dollhouse|porcelain|toybox|puppet)\b",
        "colors": "porcelain white|powder pink|faded blue|lacquer red|soft black|lavender|aged ivory",
        "materials": "glossy satin|fine lace|crisp cotton|sheer organza|velvet ribbon|translucent vinyl",
        "motifs": "tiny bow appliqués|painted floral details|heart-shaped buttons|jointed ring hardware|delicate ruffles|crystal teardrops|toy-like buckles",
        "accessories": "glossy Mary Janes|a miniature bonnet|ribbon wrist cuffs|a tiny structured bag|lace ankle socks|a doll-sized collar",
    },
    {
        "id": "haunted", "pattern": r"\b(?:haunted|ghostly|spectral|cursed|eldritch|occult)\b",
        "colors": "smoky black|ghost white|bruise lavender|faded rose|deep violet|cold blue|antique silver",
        "materials": "distressed lace|smoky chiffon|cracked satin|oil-sheen mesh|aged velvet|translucent organza",
        "motifs": "faded sigils|torn ribbon edges|antique lock charms|ghostly embroidery|black crystal drops|fine chain fringe",
        "accessories": "a sheer veil|antique silver jewelry|a narrow ritual collar|lace gloves|a tiny relic pouch|dark ribbon cuffs",
    },
    {
        "id": "futuristic", "pattern": r"\b(?:alien|futuristic|sci[ -]?fi|space|android|robotic|cybernetic|chrome)\b",
        "colors": "chrome silver|pearl white|electric cyan|violet chrome|gunmetal|holographic blue|black with warning red",
        "materials": "brushed titanium|translucent polymer|holographic smart fabric|mirror vinyl|flexible technical mesh|liquid chrome",
        "motifs": "glowing seam lines|etched circuit marks|small status lights|holographic emblems|hexagonal vents|biomechanical curves",
        "accessories": "a translucent visor|a polished data collar|articulated gloves|a compact shoulder module|chrome arm cuffs|a narrow utility belt",
    },
)


GENERIC_COVERAGE_DETAILS = {
    1: _items("minimal coverage|a deeply open back|large open side areas|minimal narrow straps|large geometric cutouts|a plunging neckline"),
    2: _items("light coverage|an open back|slender straps|a low neckline|small side cutouts|high-cut lines"),
    3: _items("balanced coverage|selective open areas|a fitted central layer|moderate coverage|controlled cutout placement|a practical open-and-closed balance"),
    4: _items("substantial coverage|a higher neckline|wide supportive straps|a light outer layer|a softly lined body|mostly closed side seams"),
    5: _items("full-body coverage|a high closed neckline|full-length sleeves|complete lining|closed side seams|a buttoned outer layer"),
}


EXPERIMENTAL_DETAILS = _items(
    "one-shoulder paneling with a detached sleeve|a sculptural fan-pleated side panel|asymmetrical cutouts linked by visible rings|a floating hip frame over a fitted center|a detachable rear cascade|split front and back panels joined only at the shoulders|an open riblike side structure|a single diagonal strap path from shoulder to thigh|transparent outer panels floating above an opaque center|graduated fringe replacing the lower panel|a crescent-shaped shoulder piece|a narrow collar supporting long vertical drapes|a deconstructed corset frame|modular clip-on hip and shoulder pieces|an exaggerated bubble hem on one side|three detached panels suspended at different heights|a chain-linked open side|a high-low skirt with an unusually long rear panel|a fitted center beneath an oversized sculptural collar|a spiral wrap crossing the torso once|a constellation of small panels joined by fine straps|an asymmetrical half-jacket construction|a compact bodice with dramatic side panniers|a liquid-looking drape frozen at one hip|a cocoonlike outer shell peeling away at the shoulders"
)


def _blueprint(identifier: str, packs: str, template: str) -> dict[str, Any]:
    return {"id": identifier, "packs": set(packs.split()), "template": template}


# Conceptually distinct structural blueprints.  Pack vocabularies provide the
# theme language; blueprints ensure the log explores different outfit logic.
BLUEPRINTS = [
    _blueprint("single-focus", "all everyday cozy dresses lingerie rave swim fantasy organic avantgarde", "A {coverage} {garment} becomes the single focal piece, realized in {color} {material} with {construction}; {motif} and {effect} keep the {theme} direction visually explicit."),
    _blueprint("two-piece-opposition", "all everyday cozy lingerie rave harness swim armor", "Two deliberately opposed pieces define this {theme} look: a close {garment} element against a looser secondary layer, both in {color} {material}, joined through {fastener} and finished with {motif}."),
    _blueprint("long-over-short", "all everyday cozy formal rave fantasy armor", "Long-over-short proportions reinterpret {theme} through a trailing {material} outer piece above a compact {garment}; {color} surfaces, {motif}, and {accessory} create a {complexity} silhouette."),
    _blueprint("short-over-long", "all everyday dresses formal avantgarde", "Short-over-long layering gives the {theme} wardrobe an unusual rhythm, placing a cropped structured layer above an elongated {garment} in {color} {material}, secured by {fastener} and sharpened with {motif}."),
    _blueprint("detached-sleeves", "all everyday dresses lingerie rave fantasy avantgarde", "Detached sleeves orbit a {coverage} {garment} rather than matching it conventionally; the {color} {material} pieces use {construction}, {fastener}, and a concentrated line of {motif} for a clearly {theme} result."),
    _blueprint("one-shoulder", "all dresses formal lingerie rave swim fantasy armor avantgarde", "One shoulder carries nearly the entire {theme} composition, with a diagonal {color} {material} path descending into a {garment}, one exposed side, {motif}, and {effect}."),
    _blueprint("split-center", "all dresses formal lingerie rave harness fantasy organic avantgarde", "A center split divides the {garment} into two independently moving {color} {material} halves; {fastener} holds the upper structure while details of {motif} mark the open line in this {theme} design."),
    _blueprint("wrap", "all everyday cozy dresses formal lingerie swim fantasy", "Wrapped construction shapes a {garment} from overlapping {color} {material}, leaving one controlled opening and one long tie; {motif}, {accessory}, and {effect} translate it into {theme}."),
    _blueprint("modular", "all rave armor avantgarde fantasy harness organic", "Modular {theme} clothing assembles a {garment} from removable {color} {material} sections, each attached by {fastener}; alternating open and dense zones carry {motif} and {effect}."),
    _blueprint("convertible", "all everyday dresses formal rave swim fantasy armor avantgarde", "Designed to transform, this {garment} shifts between a compact and expanded {theme} silhouette through {fastener}, detachable {material} panels, {color} contrast, and movable {motif}."),
    _blueprint("cape-core", "all formal rave fantasy armor organic avantgarde", "A cape becomes the structural core instead of an accessory, descending from a {color} {material} collar into a {coverage} {garment}; details of {motif} weight the edges as the {theme} piece shows {effect}."),
    _blueprint("apron", "all everyday lingerie rave harness jewelry avantgarde", "Apron logic is reduced to one small {color} {material} front panel suspended over a {garment}, with the back intentionally open, {fastener} fully visible, and {motif} expressing {theme}."),
    _blueprint("side-panels", "all dresses lingerie rave swim fantasy armor avantgarde", "Only the outer sides receive fabric: twin {color} {material} panels frame a central {garment}, joined by {construction}, edged in {motif}, and animated by {effect} for a side-weighted {theme} silhouette."),
    _blueprint("back-only", "all formal lingerie rave harness fantasy armor organic jewelry avantgarde", "From the front this {theme} look is almost absent; from behind, {color} {material} builds a complete {garment} architecture with {motif}, {fastener}, and {accessory} arranged down the spine."),
    _blueprint("front-only", "all formal lingerie rave harness jewelry avantgarde", "A front-only {garment} in {color} {material} hangs from barely visible supports, leaving the sides and back structurally empty; the visual clasp is built from {motif} while {effect} completes the {theme} illusion."),
    _blueprint("hip-dominant", "all rave harness swim fantasy armor organic jewelry avantgarde", "The hips dominate this {theme} construction through an enlarged {color} {material} frame, while the upper {garment} remains deliberately minimal; {fastener}, {motif}, and {effect} balance the width."),
    _blueprint("shoulder-dominant", "all formal rave fantasy armor organic jewelry avantgarde", "Exaggerated shoulders carry the visual mass of a {theme} {garment}, spreading {color} {material} outward before narrowing sharply at the waist; {motif}, {accessory}, and {effect} emphasize the upper silhouette."),
    _blueprint("collar-led", "all formal lingerie rave harness fantasy armor organic jewelry avantgarde", "Everything descends from a monumental collar: {color} {material} branches into a {garment}, a fall of {motif} occupies the center, and {fastener} keeps the {theme} structure under {complexity} tension."),
    _blueprint("waist-led", "all everyday dresses formal lingerie rave harness swim fantasy avantgarde", "A sculpted waist piece organizes the entire {theme} outfit, sending {color} {material} upward into a {garment} and downward into split panels; {fastener} is hidden among {motif} as the edges show {effect}."),
    _blueprint("cuff-led", "all lingerie rave harness fantasy organic jewelry avantgarde", "Oversized wrist and thigh cuffs act as four foundations for a sparse {theme} {garment}; {color} {material} spans the gaps, details of {motif} hang at unequal depths, and {effect} makes the tension visible."),
    _blueprint("glove-extension", "all formal rave fantasy armor organic jewelry avantgarde", "Glovelike {color} {material} extensions climb from individual fingers and converge into a {garment}, turning hand movement into the fastening system; {motif} and {effect} make the {theme} structure responsive."),
    _blueprint("foot-up", "all rave harness fantasy armor organic jewelry avantgarde", "Beginning at sculptural ankle loops, {color} {material} travels upward in interrupted lines before reappearing as a {garment}; {fastener} bridges the visual jumps and accents of {motif} punctuate the {theme} route."),
    _blueprint("head-supported", "all formal rave fantasy organic jewelry avantgarde", "A {color} {material} headpiece supports long descending lines that become a {coverage} {garment}, with {motif} used as counterweights and {accessory} reinforcing the improbable {theme} silhouette."),
    _blueprint("single-line", "all lingerie rave harness fantasy organic jewelry avantgarde", "One uninterrupted length of {color} {material} draws the complete {theme} outfit from shoulder to torso, hip, and ankle, becoming a {garment} without doubling back; accents of {motif} mark each change of direction."),
    _blueprint("spiral", "all dresses lingerie rave harness fantasy organic jewelry avantgarde", "A loose spiral of {color} {material} wraps into a {garment} that appears ready to slip away, yet {fastener} catches its lowest turn; sparse {motif} and {effect} preserve the {theme} motion."),
    _blueprint("ladder", "all lingerie rave harness armor organic jewelry avantgarde", "An open ladder of {color} {material} climbs one side of the body with every other rung missing, converting the gaps into a {garment}; {fastener}, {motif}, and {effect} give the {theme} piece deliberate tension."),
    _blueprint("rib-cage", "all rave harness fantasy armor organic jewelry avantgarde", "Several riblike arcs of {color} {material} hover from chest to hip as a {coverage} {garment}, open at the center and rooted by {fastener}; details of {motif} occupy only the lowest arc in this {theme} frame."),
    _blueprint("orbital", "all rave fantasy armor organic jewelry avantgarde", "Orbital rings of {color} {material} circle the body at different distances, intersecting to suggest a {garment}; {motif}, {accessory}, and {effect} turn the moving geometry into {theme} bodywear."),
    _blueprint("constellation", "all lingerie rave fantasy organic jewelry avantgarde", "A constellation of isolated {color} {material} pieces replaces conventional panels, with almost invisible leads forming a {garment}; every point carries different {motif} and shifts through {effect} in the {theme} arrangement."),
    _blueprint("chandelier", "all formal lingerie rave fantasy organic jewelry avantgarde", "Chandelier construction turns a narrow {color} {material} canopy into descending tiers around a {garment}; graduated {motif}, {fastener}, and {effect} create a sparkling {theme} body drape."),
    _blueprint("mobile", "all rave fantasy armor organic jewelry avantgarde", "Built like a kinetic mobile, this {theme} {garment} suspends {color} {material} shapes and {motif} from branching balance bars; {fastener} anchors the primary line while every element shows {effect}."),
    _blueprint("panes", "all rave armor organic jewelry avantgarde", "Transparent-looking panes of {color} {material} float around a {garment} without meeting edge to edge, attached through {fastener}; clusters of {motif} gather along selected bevels as the {theme} planes show {effect}."),
    _blueprint("armor-deconstructed", "all rave fantasy armor avantgarde", "Armor is deconstructed into separated {color} {material} plates around a flexible {garment}, with bare space replacing missing protection; {fastener}, {motif}, and {effect} make the {theme} logic intentional."),
    _blueprint("exoskeleton", "all rave fantasy armor organic avantgarde", "An exoskeletal outline follows shoulders, outer ribs, hips, and one leg while leaving the interior {garment} visible; {color} {material}, {fastener}, and a dorsal line of {motif} establish the {theme} frame."),
    _blueprint("cocoon", "all cozy formal fantasy organic avantgarde", "Cocoon fragments of {color} {material} peel away from a compact {garment}, as though the {theme} outfit is hatching; newly exposed edges carry {motif}, {fastener}, and {effect}."),
    _blueprint("dissolving", "all formal rave fantasy organic jewelry avantgarde", "The {theme} construction begins as dense {color} {material} at one shoulder, thins across the {garment}, and ends as isolated {motif} beyond the opposite hip, producing {effect}."),
    _blueprint("gradient-density", "all everyday formal rave fantasy armor organic jewelry avantgarde", "Density changes from opaque to nearly absent across this {garment}: layered {color} {material} gradually gives way to lines, then {motif}, with {fastener} controlling the {theme} transition."),
    _blueprint("mismatched-halves", "all everyday dresses formal lingerie rave swim fantasy armor avantgarde", "Two intentionally nonmatching halves form one {theme} {garment}, one rendered in broad {color} {material} planes and the other in fine open lines; shared {motif} and {fastener} make the mismatch coherent."),
    _blueprint("five-panels", "all dresses formal rave fantasy armor avantgarde", "Exactly five detached panels reconstruct a {garment} without conventional seams, each using a different scale of {color} {material}; {fastener} and repeated {motif} bind the {theme} composition."),
    _blueprint("three-zones", "all everyday cozy formal lingerie rave harness fantasy armor organic avantgarde", "Three independent zones—upper, waist, and lower—interpret {theme} without directly touching, each built from {color} {material}; {motif} and {fastener} create visual continuity around the {garment}."),
    _blueprint("negative-space-cross", "all lingerie rave harness swim fantasy organic jewelry avantgarde", "A cross-shaped field of negative space interrupts the {garment}, forcing {color} {material} toward the outer body; {fastener} guards each inner corner while details of {motif} make the {theme} opening graphic."),
    _blueprint("diagonal", "all everyday dresses formal lingerie rave harness swim fantasy armor avantgarde", "A severe diagonal slices through this {theme} {garment}, placing dense {color} {material} above the line and a sparse counterstructure below; {motif}, {accessory}, and {effect} reinforce the angle."),
    _blueprint("vertical-trio", "all formal lingerie rave harness fantasy armor organic jewelry avantgarde", "Three separate vertical falls of {color} {material} descend through the {garment} with open channels between them; {fastener} redirects each fall and accents of {motif} weight their unequal {theme} lengths."),
    _blueprint("horizontal-bands", "all everyday lingerie rave harness swim armor avantgarde", "Horizontal {color} {material} bands rebuild a {garment} at deliberately irregular intervals, skipping the waist before returning at the hips; {motif} and {fastener} articulate the {theme} spacing."),
    _blueprint("fan", "all dresses formal rave fantasy armor organic jewelry avantgarde", "Fan geometry opens from one side of a {garment}, spreading {color} {material} rays around a central {fastener}; accents of {motif} tip the outer edge and {effect} gives the {theme} fan responsive movement."),
    _blueprint("crescent", "all formal lingerie rave fantasy armor organic jewelry avantgarde", "Crescents of {color} {material} replace ordinary garment panels at shoulder, torso, and hips; a {garment} emerges from their shared {fastener}, with {motif} and {effect} completing the lunar {theme} arrangement."),
    _blueprint("teardrops", "all dresses lingerie rave swim fantasy organic jewelry avantgarde", "Hollow teardrops frame the torso and hips instead of covering them, each built from {color} {material} and linked into a {garment} by {fastener}; clusters of {motif} collect at the rounded ends for {theme}."),
    _blueprint("square-circle", "all rave harness fantasy armor jewelry avantgarde", "A square over one shoulder and a circle at the opposite hip define the {theme} {garment}, joined diagonally through {color} {material}; {fastener}, {motif}, and {effect} soften the collision of shapes."),
    _blueprint("hourglass-void", "all formal lingerie rave harness fantasy organic jewelry avantgarde", "Opposing curves suggest an hourglass without touching across the waist, using {color} {material} to frame a {garment}; a fall of {motif} replaces the missing center while {fastener} preserves the {theme} void."),
    _blueprint("pleated", "all everyday dresses formal fantasy armor avantgarde", "Pleats become the main architecture of a {theme} {garment}, changing from knife-sharp {color} {material} folds to loose released volume; {motif}, {fastener}, and {effect} articulate the transformation."),
    _blueprint("ruffle-map", "all everyday dresses lingerie rave swim fantasy avantgarde", "Ruffles follow an unexpected map across this {garment}, clustering at one shoulder, disappearing at the waist, and returning around one thigh; {color} {material}, {motif}, and {effect} hold the {theme} route."),
    _blueprint("pockets", "all everyday cozy armor avantgarde", "Storage becomes ornament in a {theme} {garment} covered with differently scaled pockets, some functional and some floating; {color} {material}, {fastener}, and {motif} prevent the utility from becoming uniform."),
    _blueprint("belt-creature", "all harness fantasy organic avantgarde", "One beltlike form circles the body at several heights to become a {garment}, using {color} {material}, repeated {fastener}, and a spine of {motif}; {effect} makes the {theme} coil feel continuous."),
    _blueprint("swarm", "all rave fantasy organic jewelry avantgarde", "Hundreds of tiny {color} {material} units gather into a sparse swarm garment, densest at one hip and nearly absent over the abdomen; scouts carry {motif} outward as the {theme} colony shows {effect}."),
    _blueprint("bloom-trio", "all dresses lingerie rave fantasy organic jewelry avantgarde", "Three oversized blooms replace conventional garment zones at shoulder, waist, and thigh, linked only by {color} {material} stems; {motif}, {fastener}, and {effect} make the isolated forms read as one {theme} {garment}."),
    _blueprint("pod-line", "all rave fantasy armor organic avantgarde", "Hollow pods descend from collar to hip along a {garment}, each tethered differently in {color} {material}; details of {motif} spill from selected openings while {fastener} controls the {theme} line."),
    _blueprint("fringe-only", "all formal lingerie rave harness swim fantasy jewelry avantgarde", "Instead of solid fabric, graduated fringe supplies nearly the entire {garment}; {color} {material} hangs from {fastener}, strands of {motif} weight selected falls, and {effect} gives the {theme} silhouette constant motion."),
    _blueprint("ribbon-knot", "all everyday dresses lingerie rave fantasy organic jewelry avantgarde", "Self-tying ribbon logic shapes a {garment} from long {color} {material} bands, with knots replacing seams and {motif} gathered at each crossing; {effect} keeps the {theme} construction freshly tensioned."),
    _blueprint("inflated", "all rave fantasy organic avantgarde", "Inflated {color} {material} tubes outline a {garment} without filling it, expanding around {fastener} and shrinking between zones; bubblelike {motif} and {effect} exaggerate the {theme} volume."),
    _blueprint("liquid", "all rave fantasy armor organic jewelry avantgarde", "Liquid-looking {color} {material} pours around the body before reforming into a {garment}, breaking into droplets near {fastener}; {motif}, {accessory}, and {effect} freeze the {theme} flow in place."),
    _blueprint("transparent-over-opaque", "all everyday cozy dresses formal lingerie rave swim fantasy armor avantgarde", "A transparent {color} {material} shell floats above a smaller opaque {garment}, touching only at {fastener}; suspended {motif} and {effect} make the double-layered {theme} silhouette readable from every angle."),
    _blueprint("opaque-over-transparent", "all everyday dresses formal lingerie rave swim fantasy armor avantgarde", "Small opaque {color} {material} pieces sit over a continuous sheer {garment}, reversing ordinary layering; {fastener}, {motif}, and {effect} define the {theme} coverage map."),
    _blueprint("train", "all dresses formal lingerie rave fantasy avantgarde", "A compact {garment} releases one disproportionately long {color} {material} train from an unexpected point, anchored by {fastener}; details of {motif} thin toward the end as {effect} dramatizes the {theme} movement."),
    _blueprint("bustle", "all dresses formal lingerie rave fantasy avantgarde", "A concentrated back bustle of {color} {material} projects behind an otherwise narrow {garment}; {fastener} carries the weight, nested details of {motif} fill the volume, and {effect} keeps the {theme} front visually spare."),
    _blueprint("panniers", "all dresses formal fantasy armor avantgarde", "Airy side panniers expand a {theme} {garment} beyond the hips without forming a central skirt, using {color} {material} ribs, {fastener}, floating {motif}, and {effect}."),
    _blueprint("bolero", "all everyday dresses formal lingerie rave fantasy armor", "Bolero proportions reduce the upper layer to a {color} {material} shoulder shell above a {garment}, leaving the center open; {fastener}, {motif}, and {accessory} give the cropped {theme} piece purpose."),
    _blueprint("vest", "all everyday cozy formal rave armor", "A long vest becomes the dominant {theme} line over a contrasting {garment}, cut from {color} {material} with interrupted sides, visible {fastener}, and a sparse vertical row of {motif}."),
    _blueprint("jacket-half", "all everyday cozy formal rave armor avantgarde", "Half of a jacket remains fully tailored while the other dissolves into straps around a {garment}; shared {color} {material}, {fastener}, and {motif} keep the {theme} asymmetry intentional."),
    _blueprint("corset-skeleton", "all dresses formal lingerie rave harness fantasy armor organic avantgarde", "Corset logic appears only as widely spaced bones around a {garment}, never joined by solid textile; {color} {material}, {fastener}, and {motif} create an open {theme} framework with {effect}."),
    _blueprint("bandeau-segments", "all lingerie rave harness swim armor avantgarde", "A bandeau is broken into floating {color} {material} segments separated by bare intervals, with hidden lines leading into a {garment}; an off-center cluster of {motif} acts as the visual clasp above {fastener} for the {theme} illusion."),
    _blueprint("high-low", "all everyday dresses formal rave swim fantasy avantgarde", "Extreme high-low cutting gives this {theme} {garment} a compact front and expansive {color} {material} rear, connected through {fastener}; {motif} and {effect} exaggerate the difference in length."),
    _blueprint("column-cutouts", "all dresses formal lingerie rave fantasy armor avantgarde", "A long column {garment} is interrupted by differently shaped cutouts instead of seams, each bordered in {color} {material}; {fastener}, {motif}, and {effect} turn the openings into the {theme} ornament system."),
    _blueprint("bubble", "all everyday dresses rave fantasy avantgarde", "Bubble volume gathers around the hem and one sleeve of a {theme} {garment}, using {color} {material}, internal {fastener}, floating {motif}, and {effect} to keep the shape buoyant."),
    _blueprint("tiered", "all everyday dresses formal lingerie rave fantasy", "Uneven tiers descend around a {garment}, alternating dense {color} {material} with open intervals; details of {motif} change scale at each tier and {fastener} remains visible in the {theme} construction."),
    _blueprint("panel-mosaic", "all everyday formal rave fantasy armor avantgarde", "A mosaic of nonmatching {color} {material} panels reconstructs a {garment} from small geometric decisions; exposed {fastener}, recurring {motif}, and {effect} unify the {theme} patchwork."),
    _blueprint("scarf-built", "all everyday dresses lingerie rave swim fantasy", "Several scarves in {color} {material} are knotted into a {garment} without cutting the cloth, using {fastener} only at the load points; {motif}, {accessory}, and {effect} push the result toward {theme}."),
    _blueprint("chain-linked", "all lingerie rave harness fantasy armor organic jewelry avantgarde", "Detached sections of a {garment} are linked by exposed chains rather than seams, alternating {color} {material} with open space; {motif}, {fastener}, and {effect} make the {theme} links ornamental."),
    _blueprint("laced-map", "all dresses formal lingerie rave harness fantasy armor avantgarde", "Lacing travels across this {theme} {garment} in changing directions—vertical, radial, then diagonal—pulling {color} {material} around open gaps; accents of {motif} cap each point held by {fastener}."),
    _blueprint("ring-map", "all lingerie rave harness fantasy armor organic jewelry avantgarde", "A map of differently scaled rings organizes {color} {material} into a {garment}, with straps entering and leaving each ring at unexpected angles; {motif} and {effect} establish the {theme} rhythm."),
    _blueprint("utility", "all everyday rave armor avantgarde", "Utility architecture becomes a {theme} {garment} through modular {color} {material} pockets, a fastening system using {fastener}, a deliberately exposed support structure, {motif}, and {accessory}."),
    _blueprint("ceremonial-rays", "all formal fantasy armor organic jewelry avantgarde", "Ceremonial symmetry sends rays of {color} {material} from a central {garment}, with {motif} occupying every formal intersection; {fastener}, {accessory}, and {effect} complete the {theme} regalia."),
    _blueprint("ritual-asymmetry", "all formal fantasy armor organic jewelry avantgarde", "Deliberately unbalanced ritual wear places dense {color} {material} over one shoulder and three fine cords over the opposite hip; {fastener}, {motif}, and {effect} resolve the {theme} {garment}."),
    _blueprint("grand-system", "all rave fantasy armor organic jewelry avantgarde", "A grand convertible system combines collar, open torso structure, articulated hips, one leg extension, and rear cascade into a {garment}; {color} {material}, {fastener}, shifting {motif}, and {effect} all serve {theme}."),
]


COVERAGE = {
    1: "barely-there", 2: "high-exposure", 3: "selectively revealing",
    4: "moderate-coverage", 5: "fully covered",
}
COMPLEXITY = {
    1: "pared-back", 2: "cleanly detailed", 3: "layered",
    4: "ornate", 5: "maximalist",
}
REALISM = {
    1: "impossible dream-logic", 2: "surreal editorial", 3: "fashion-plausible",
    4: "physically wearable", 5: "production-ready",
}


def _clamp_level(value: Any, default: int = 3) -> int:
    try:
        return max(1, min(5, int(value)))
    except (TypeError, ValueError):
        return default


def _resolve_packs(theme: str, requested: Any) -> list[str]:
    selected = [item for item in _items(requested) if item in PACKS and item != "auto"]
    if selected:
        return selected[:6]
    folded = theme.casefold()
    matches = [key for key, row in PACKS.items() if any(word in folded for word in row.get("keywords") or ())]
    if matches:
        if "avantgarde" not in matches and re.search(r"\b(?:avant[ -]?garde|experimental|surreal|sculptural|impossible|bizarre)\b", folded):
            matches.append("avantgarde")
        return matches[:4]
    if re.search(r"\b(?:avant[ -]?garde|experimental|surreal|sculptural|impossible|bizarre)\b", folded):
        return ["avantgarde"]
    return ["everyday"]


def _merged_bank(packs: list[str], field: str, supplied: Any) -> list[str]:
    explicit = _items(supplied)
    if explicit:
        return explicit
    merged: list[str] = []
    for key in packs:
        merged.extend(_items(PACKS[key].get(field) or ""))
    return _items(merged)


def _detect_garment_family(theme: str) -> dict[str, Any] | None:
    return next((family for family in GARMENT_FAMILIES if re.search(str(family["pattern"]), theme, re.IGNORECASE)), None)


def _detect_style_overlays(theme: str) -> list[dict[str, Any]]:
    return [overlay for overlay in STYLE_OVERLAYS if re.search(str(overlay["pattern"]), theme, re.IGNORECASE)]


def _profiled_bank(
    packs: list[str],
    field: str,
    supplied: Any,
    family: dict[str, Any] | None,
    overlays: list[dict[str, Any]],
) -> list[str]:
    explicit = _items(supplied)
    if explicit:
        return explicit
    family_items = _items((family or {}).get(field) or "")
    overlay_items: list[str] = []
    for overlay in overlays:
        overlay_items.extend(_items(overlay.get(field) or ""))
    base_items = _merged_bank(packs, field, None)
    if field == "garments" and family_items:
        return family_items
    if field in {"colors", "motifs", "accessories"} and overlay_items:
        return _items([*family_items, *overlay_items])
    if family_items:
        return _items([*family_items, *overlay_items])
    if overlay_items:
        return _items([*overlay_items, *base_items])
    return base_items


def _coverage_details(family: dict[str, Any] | None, level: int) -> list[str]:
    family_coverage = (family or {}).get("coverage")
    if isinstance(family_coverage, dict):
        values = _items(family_coverage.get(level) or "")
        if values:
            return values
    return list(GENERIC_COVERAGE_DETAILS[level])


def _joined_details(values: list[str]) -> str:
    clean = [_line(value).strip(" ,.;") for value in values if _line(value).strip(" ,.;")]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return ", ".join(clean[:-1]) + f", and {clean[-1]}"


def _experimental_rate(packs: list[str], realism: int) -> float:
    if realism == 1:
        return 1.0
    if realism == 2:
        return 0.68
    # The default and higher levels promise readable, directly promptable
    # clothing. Theme-specific garments can remain fantastical without an
    # unrelated experimental construction being bolted onto the line.
    return 0.0


def _concise_outfit_line(
    banks: dict[str, list[str]],
    coverage_details: list[str],
    complexity: int,
    experimental: bool,
    rng: random.Random,
) -> tuple[str, str]:
    garment = _pick(banks["garments"], rng, "outfit")
    material = _pick(banks["materials"], rng, "textile")
    color = _pick(banks["colors"], rng, "theme-led color")
    coverage_detail = _pick(coverage_details, rng, "balanced coverage")
    construction = _pick(banks["construction"], rng, "clean construction")
    motif = _pick(banks["motifs"], rng, "subtle trim")
    fastener = _pick(banks["fasteners"], rng, "a simple closure")
    accessory = _pick(banks["accessories"], rng, "one coordinated accessory")
    effect = _pick(banks["effects"], rng, "natural movement")
    experimental_detail = _pick(EXPERIMENTAL_DETAILS, rng, "asymmetrical paneling") if experimental else ""

    base_variants = (
        f"{color} {material} {garment}",
        f"{color} {garment} in {material}",
        f"{material} {garment} in {color}",
        f"{color} {garment} cut from {material}",
    )
    base = base_variants[rng.randrange(len(base_variants))]

    target_count = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}[complexity]
    primary = [coverage_detail]
    candidates = [construction, motif, fastener, accessory]
    rng.shuffle(candidates)
    if experimental_detail:
        primary.append(experimental_detail)
    for value in candidates:
        if len(primary) >= target_count:
            break
        if value.casefold() not in {item.casefold() for item in primary}:
            primary.append(value)
    if complexity == 5 and len(primary) < target_count:
        primary.append(effect)
    # At the balanced default, accessories should appear often enough for the
    # line to describe a complete usable look, not merely garment engineering.
    if complexity >= 3 and accessory.casefold() not in {item.casefold() for item in primary}:
        if len(primary) >= target_count:
            primary[-1] = accessory
        else:
            primary.append(accessory)

    connector = "featuring" if " with " in garment.casefold() else "with"
    line = f"{base} {connector} {_joined_details(primary)}"
    signature = "|".join(item.casefold() for item in (garment, coverage_detail, construction, motif, experimental_detail))
    return _line(_repair_articles(line)).rstrip("."), signature


def _pick(values: list[str], rng: random.Random, fallback: str) -> str:
    return rng.choice(values) if values else fallback


def _seed_value(value: Any, theme: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        digest = hashlib.sha256(theme.encode("utf-8")).hexdigest()
        return int(digest[:12], 16)


def _phrase_is_plural(value: str) -> bool:
    clean = _line(value).casefold()
    if not clean or re.match(r"^(?:a|an|one|single|each|every)\b", clean):
        return False
    final = re.findall(r"[a-z]+", clean)
    if not final:
        return False
    word = final[-1]
    return word.endswith("s") and not word.endswith(("ss", "us", "is"))


def _repair_articles(text: str) -> str:
    repaired = re.sub(r"\b([Aa]) (?=(?:[aeiou]|honest\b|hour\b|heir\b))", lambda match: "An " if match.group(1) == "A" else "an ", text, flags=re.IGNORECASE)
    repaired = re.sub(r"\b([Aa])n (?=(?:one\b|uni|user\b|use\b|util|euro|uv\b))", lambda match: "A " if match.group(1) == "A" else "a ", repaired, flags=re.IGNORECASE)
    repaired = re.sub(r"\b([Aa]) (?=(?:LED|LCD|RGB|X-ray)\b)", lambda match: "An " if match.group(1) == "A" else "an ", repaired)
    repaired = re.sub(r"\b(a|an) ([a-z-]+) (?:a|an) ", r"\1 \2 ", repaired, flags=re.IGNORECASE)
    return repaired


def _agree_direct_subject(template: str, field: str, phrase: str, verbs: dict[str, str]) -> str:
    if not _phrase_is_plural(phrase):
        return template
    for singular, plural in verbs.items():
        template = template.replace(f"{{{field}}} {singular}", f"{{{field}}} {plural}")
    return template


def _format_blueprint(blueprint: dict[str, Any], context: dict[str, str]) -> str:
    template = str(blueprint["template"])
    template = _agree_direct_subject(template, "fastener", context["fastener"], {
        "holds": "hold", "catches": "catch", "bridges": "bridge", "anchors": "anchor",
        "controls": "control", "carries": "carry", "guards": "guard", "keeps": "keep",
        "preserves": "preserve", "redirects": "redirect", "remains": "remain", "is": "are",
    })
    template = _agree_direct_subject(template, "effect", context["effect"], {
        "completes": "complete", "dramatizes": "dramatize", "gives": "give",
        "keeps": "keep", "makes": "make",
    })
    return _line(_repair_articles(template.format(**context)))


OPENING_REFRAMES = (
    "Beginning with {color} {material} and {motif}, {body}",
    "Treating {fastener} as visible design language, {body}",
    "Centered on {motif} rather than conventional trim, {body}",
    "Using {material} to redirect the silhouette, {body}",
    "Against a {color} foundation, {body}",
    "Reversing the expected balance of the outfit, {body}",
    "Led by {effect} and an unusual proportion shift, {body}",
    "With {accessory} acting as a counterpoint, {body}",
    "Built outward from {fastener}, {body}",
    "Keeping {motif} concentrated in one zone, {body}",
    "Through a deliberate collision of {material} and {color}, {body}",
    "Shaped first by {construction}, {body}",
    "Moving the visual weight away from center, {body}",
    "Allowing {effect} to change the outline, {body}",
    "Reducing the fastening system to {fastener}, {body}",
    "Framing the theme through {motif}, {body}",
    "Starting at the least conventional garment zone, {body}",
    "Balancing {color} against the texture of {material}, {body}",
    "Instead of repeating familiar layer order, {body}",
    "Carrying {motif} across otherwise unrelated pieces, {body}",
)


def _unique_opening(candidate: str, context: dict[str, str], seen: set[str], rng: random.Random) -> str:
    def opening(value: str) -> str:
        return " ".join(re.findall(r"[a-z]+", value.casefold())[:7])

    if opening(candidate) not in seen:
        return candidate
    body = candidate[:1].lower() + candidate[1:]
    order = list(OPENING_REFRAMES)
    rng.shuffle(order)
    for template in order:
        reframed = _line(template.format(body=body, **context))
        if opening(reframed) not in seen:
            return reframed
    return _line(f"Under a {context['color']} {context['material']} variation keyed to {context['motif']}, {body}")


def _anchored_context_profile(banks: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "materials": banks["materials"] or _items(PACKS["anchored"]["materials"]),
        "colors": banks["colors"] or _items(PACKS["anchored"]["colors"]),
        "anchors": banks["fasteners"] or _items(PACKS["anchored"]["fasteners"]),
        "ornaments": banks["motifs"] or _items(PACKS["anchored"]["motifs"]),
        "behaviors": banks["effects"] or _items(PACKS["anchored"]["effects"]),
    }


_ANCHORED_PLURAL = {
    1, 3, 5, 9, 12, 13, 14, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 35,
    44, 45, 47, 50, 51, 52, 53, 54, 55, 57, 59, 63, 71, 72, 74, 75, 82, 87, 94,
}
_ANCHORED_BASE = {65, 80, 92, 95}


def _anchored_line(profile: dict[str, Any], structure_index: int, rng: random.Random) -> str:
    structure = ANCHORED_STRUCTURES[structure_index % len(ANCHORED_STRUCTURES)]
    material = _pick(profile["materials"], rng, "living ribbon")
    material_2 = _pick([item for item in profile["materials"] if item != material], rng, material)
    color = _pick(profile["colors"], rng, "iridescent black")
    color_2 = _pick([item for item in profile["colors"] if item != color], rng, color)
    anchor = _pick(profile["anchors"], rng, "a self-tightening anchor")
    anchor_2 = _pick([item for item in profile["anchors"] if item != anchor], rng, anchor)
    ornament = _pick(profile["ornaments"], rng, "pearl nodes")
    ornament_2 = _pick([item for item in profile["ornaments"] if item != ornament], rng, ornament)
    behavior = _pick(profile["behaviors"], rng, "holds itself under responsive tension")
    behavior_2 = _pick([item for item in profile["behaviors"] if item != behavior], rng, behavior)
    if structure_index in _ANCHORED_PLURAL:
        behavior, behavior_2 = plural_behavior(behavior), plural_behavior(behavior_2)
    elif structure_index in _ANCHORED_BASE:
        behavior, behavior_2 = base_behavior(behavior), base_behavior(behavior_2)
    return _line(structure.format(
        c=color, c2=color_2, m=material, m2=material_2, a=anchor, a2=anchor_2,
        o=ornament, o2=ornament_2, b=behavior, b2=behavior_2,
    ))


def normalized_words(value: str) -> set[str]:
    return set(re.findall(r"[a-z]+", value.casefold()))


def audit_outfits(lines: Iterable[Any], *, required: Any = None, avoided: Any = None) -> dict[str, Any]:
    raw_lines = [str(value or "") for value in lines]
    clean_lines = [_line(value) for value in raw_lines]
    required_terms = _items(required)
    avoided_terms = _items(avoided)
    issues: list[dict[str, Any]] = []
    line_issues: dict[int, list[str]] = defaultdict(list)

    for index, value in enumerate(clean_lines):
        if not value:
            line_issues[index].append("Blank line")
        if "\n" in raw_lines[index] or "\r" in raw_lines[index]:
            line_issues[index].append("Entry is not single-line")
        if re.match(r"^\s*(?:\d+[.)]|[-*#])\s", value):
            line_issues[index].append("Numbered or bulleted opening")
        for term in required_terms:
            if term.casefold() not in value.casefold():
                line_issues[index].append(f"Missing required term: {term}")
        for term in avoided_terms:
            if term.casefold() in value.casefold():
                line_issues[index].append(f"Contains avoided term: {term}")

    exact: dict[str, list[int]] = defaultdict(list)
    openings: dict[str, list[int]] = defaultdict(list)
    for index, value in enumerate(clean_lines):
        exact[value.casefold()].append(index)
        opening = " ".join(re.findall(r"[a-z]+", value.casefold())[:OPENING_WORDS])
        if opening:
            openings[opening].append(index)
    for indexes in exact.values():
        if len(indexes) > 1:
            for index in indexes:
                line_issues[index].append("Exact duplicate")
    for indexes in openings.values():
        if len(indexes) > 1:
            for index in indexes:
                line_issues[index].append(f"Repeated {OPENING_WORDS}-word opening")

    closest = {"score": 0.0, "left": -1, "right": -1}
    word_sets = [normalized_words(value) for value in clean_lines]
    for left in range(len(clean_lines)):
        if not word_sets[left]:
            continue
        for right in range(left + 1, len(clean_lines)):
            union = word_sets[left] | word_sets[right]
            score = len(word_sets[left] & word_sets[right]) / len(union) if union else 0.0
            if score > closest["score"]:
                closest = {"score": round(score, 3), "left": left, "right": right}
            if score >= SIMILARITY_THRESHOLD:
                line_issues[left].append(f"Very similar to line {right + 1} ({score:.0%})")
                line_issues[right].append(f"Very similar to line {left + 1} ({score:.0%})")

    first_words = Counter((re.findall(r"[a-z]+", value.casefold()) or [""])[0] for value in clean_lines if value)
    dominant_openers = [{"word": word, "count": count} for word, count in first_words.most_common() if word and count > max(4, len(clean_lines) // 10)]
    for index, messages in sorted(line_issues.items()):
        issues.append({"line": index + 1, "issues": list(dict.fromkeys(messages))})

    exact_duplicate_count = sum(max(0, len(indexes) - 1) for indexes in exact.values())
    repeated_opening_count = sum(max(0, len(indexes) - 1) for indexes in openings.values())
    # Color/material-led noun phrases are normal for outfit logs. Dominant
    # first words remain visible as a diagnostic, but only actual line issues
    # reduce the quality score.
    penalty = exact_duplicate_count * 12 + repeated_opening_count * 2 + len(issues) * 0.65
    score = max(0, min(100, round(100 - penalty)))
    return {
        "ok": not issues,
        "score": score,
        "line_count": len(clean_lines),
        "unique_count": len({value.casefold() for value in clean_lines if value}),
        "blank_count": sum(1 for value in clean_lines if not value),
        "exact_duplicate_count": exact_duplicate_count,
        "repeated_opening_count": repeated_opening_count,
        "dominant_openers": dominant_openers,
        "closest_pair": {"score": closest["score"], "left": closest["left"] + 1, "right": closest["right"] + 1},
        "issues": issues,
    }


def _apply_fidelity(audit: dict[str, Any], lines: list[str], brief: dict[str, Any]) -> dict[str, Any]:
    fidelity = fidelity_report(lines, brief)
    audit["fidelity"] = fidelity
    if fidelity["ok"]:
        return audit
    existing = {int(row["line"]): row for row in audit["issues"]}
    for failure in fidelity["failed_lines"]:
        row = existing.setdefault(int(failure["line"]), {"line": int(failure["line"]), "issues": []})
        row["issues"].append("Missing theme constraint: " + ", ".join(failure["missing"]))
    audit["issues"] = [existing[key] for key in sorted(existing)]
    audit["ok"] = False
    audit["score"] = min(int(audit["score"]), int(fidelity["score"]))
    return audit


def generate_outfits(payload: dict[str, Any]) -> dict[str, Any]:
    theme = _line(payload.get("theme"))
    if not theme:
        raise ValueError("Describe an outfit theme before generating")
    try:
        count = max(1, min(MAX_GENERATED_LINES, int(payload.get("count") or 100)))
    except (TypeError, ValueError):
        count = 100
    seed = _seed_value(payload.get("seed"), theme)
    rng = random.Random(seed)
    packs = _resolve_packs(theme, payload.get("packs"))
    coverage = _clamp_level(payload.get("coverage"), 3)
    complexity = _clamp_level(payload.get("complexity"), 3)
    realism = _clamp_level(payload.get("realism"), 3)
    required = _items(payload.get("required"))
    avoided = _items(payload.get("avoided"))
    if any(term.casefold() in theme.casefold() for term in avoided):
        raise ValueError("The theme itself contains an avoided term")

    family = _detect_garment_family(theme)
    overlays = _detect_style_overlays(theme)
    brief = parse_theme(theme)
    brief["color_options"] = _items(payload.get("colors"))
    brief["material_options"] = _items(payload.get("materials"))
    banks = {
        field: _profiled_bank(packs, field, payload.get(field), family, overlays)
        for field in ("garments", "materials", "colors", "construction", "motifs", "fasteners", "accessories", "effects")
    }
    if family and not _items(payload.get("garments")):
        family_coverage_garments = family.get("garments_by_coverage")
        if isinstance(family_coverage_garments, dict):
            scoped_garments = _items(family_coverage_garments.get(coverage) or "")
            if scoped_garments:
                banks["garments"] = scoped_garments
    if not banks["garments"] or not banks["materials"]:
        raise ValueError("The selected structure packs do not provide enough garment and material vocabulary")

    coverage_bank = _coverage_details(family, coverage)
    experimental_rate = _experimental_rate(packs, realism)
    anchored_profile = _anchored_context_profile(banks)
    use_anchored = "anchored" in packs
    # Explicit legacy garment banks and the historical anchored preset API stay
    # usable for saved drafts. The normal theme-only workflow always uses the
    # structured brief path.
    use_structured = not use_anchored and not _items(payload.get("garments"))
    anchored_order = list(range(len(ANCHORED_STRUCTURES)))
    rng.shuffle(anchored_order)

    lines: list[str] = []
    concepts: set[str] = set()
    seen_values: set[str] = set()
    line_word_sets: list[set[str]] = []
    seen_openings: set[str] = set()
    experimental_count = 0
    attempts = 0
    max_attempts = max(400, count * 100)
    while len(lines) < count and attempts < max_attempts:
        output_index = len(lines)
        attempts += 1
        anchored_turn = use_anchored and (len(packs) == 1 or output_index % max(2, len(packs)) == 0)
        candidate_experimental = anchored_turn
        if anchored_turn:
            structure_index = anchored_order[(output_index + attempts - 1) % len(anchored_order)]
            candidate = _anchored_line(anchored_profile, structure_index, rng).rstrip(".")
            concept = f"anchored:{structure_index}:{_pick(banks['garments'], rng, 'bodywear')}"
        elif use_structured:
            has_explicit_pieces = bool(brief.get("pieces"))
            candidate, concept, candidate_experimental = generate_candidate(
                brief,
                coverage=coverage,
                complexity=complexity,
                realism=realism,
                rng=rng,
                fallback_details=[] if has_explicit_pieces else [*banks["construction"], *banks["motifs"], *banks["fasteners"]],
                fallback_accessories=[] if has_explicit_pieces else banks["accessories"],
            )
        else:
            experimental = rng.random() < experimental_rate
            candidate_experimental = experimental
            candidate, concept = _concise_outfit_line(banks, coverage_bank, complexity, experimental, rng)

        if required:
            missing = [term for term in required if term.casefold() not in candidate.casefold()]
            if missing:
                candidate = candidate.rstrip(" ,.;") + ", " + _joined_details(missing)
        if any(term.casefold() in candidate.casefold() for term in avoided):
            continue
        candidate = _line(_repair_articles(candidate)).rstrip(".")
        folded_candidate = candidate.casefold()
        if folded_candidate in seen_values:
            continue
        opening = " ".join(re.findall(r"[a-z]+", candidate.casefold())[:OPENING_WORDS])
        if opening and opening in seen_openings:
            continue
        candidate_words = normalized_words(candidate)
        if any(
            len(candidate_words & existing_words) / len(candidate_words | existing_words) >= SIMILARITY_THRESHOLD
            for existing_words in line_word_sets
            if candidate_words | existing_words
        ):
            continue
        if concept in concepts:
            continue
        lines.append(candidate)
        concepts.add(concept)
        seen_values.add(folded_candidate)
        line_word_sets.append(candidate_words)
        if opening:
            seen_openings.add(opening)
        experimental_count += int(candidate_experimental)

    if len(lines) < count:
        raise ValueError(f"Forge could create only {len(lines)} clean entries under the current restrictions; loosen avoided terms or add more vocabulary")

    audit = _apply_fidelity(audit_outfits(lines, required=required, avoided=avoided), lines, brief)
    fidelity = audit["fidelity"]
    return {
        "ok": True,
        "forge_version": FORGE_VERSION,
        "theme": theme,
        "filename": _safe_filename(payload.get("filename") or theme),
        "seed": seed,
        "packs": packs,
        "pack_labels": [PACKS[key]["label"] for key in packs],
        "garment_family": {"id": family["id"], "label": family["label"]} if family else None,
        "style_overlays": [overlay["id"] for overlay in overlays],
        "brief": brief,
        "fidelity": fidelity,
        "experimental_count": experimental_count,
        "lines": lines,
        "audit": audit,
        "banks": banks,
    }


def _collection_by_name(rows: list[dict[str, Any]], name: str, parent_id: str = "") -> dict[str, Any] | None:
    folded = _line(name).casefold()
    clean_parent = str(parent_id or "")
    return next((row for row in rows if _line(row.get("name")).casefold() == folded and str(row.get("parent_id") or "") == clean_parent), None)


def export_to_outfit_library(lines: Iterable[Any], *, category: str, subcategory: str = "") -> dict[str, Any]:
    values = _items(list(lines))
    if not values:
        raise ValueError("The Forge has no Outfit lines to export")
    category_name = _line(category)
    subcategory_name = _line(subcategory)
    if not category_name:
        raise ValueError("Choose an Outfit Library category")
    catalog = get_catalog()
    collections = catalog.component_collections("outfit")
    parent = _collection_by_name(collections, category_name)
    category_created = parent is None
    if parent is None:
        parent = catalog.create_component_collection("outfit", category_name)
        collections.append(parent)
    parent_id = str(parent.get("collection_id") or "")
    target = parent
    subcategory_created = False
    if subcategory_name:
        target = _collection_by_name(collections, subcategory_name, parent_id)
        subcategory_created = target is None
        if target is None:
            target = catalog.create_component_collection("outfit", subcategory_name, parent_id)
    target_id = str(target.get("collection_id") or "")

    before = {str(row.get("value") or "").casefold() for row in catalog.recipe_components("outfit")}
    component_ids: list[str] = []
    created = matched = 0
    for value in values:
        existed = value.casefold() in before
        component = catalog.upsert_recipe_component("outfit", value, manual=True)
        component_id = str(component.get("component_id") or "")
        if component_id:
            component_ids.append(component_id)
        if existed:
            matched += 1
        else:
            created += 1
            before.add(value.casefold())
    membership = catalog.add_components_to_collections(component_ids, [target_id]) if target_id else {"memberships_added": 0}

    # Rebuild managed Prompt Core logs only after the complete atomic publish.
    from . import solo_recipe_catalog as recipe_catalog
    log_sync = recipe_catalog._safe_sync_recipe_component_logs()
    return {
        "ok": True,
        "log_sync": log_sync,
        "line_count": len(values),
        "created": created,
        "matched": matched,
        "memberships_added": int(membership.get("memberships_added") or 0),
        "category": {"name": category_name, "collection_id": parent_id, "created": category_created},
        "subcategory": {"name": subcategory_name, "collection_id": target_id if subcategory_name else "", "created": subcategory_created} if subcategory_name else None,
    }


def forge_config() -> dict[str, Any]:
    collections = get_catalog().component_collections("outfit")
    return {
        "ok": True,
        "forge_version": FORGE_VERSION,
        "max_lines": MAX_GENERATED_LINES,
        "collections": collections,
    }


if PromptServer is not None and web is not None:

    @PromptServer.instance.routes.get("/sickollie/outfit-forge/config")
    async def outfit_forge_config(_request):
        return web.json_response(forge_config())

    @PromptServer.instance.routes.post("/sickollie/outfit-forge/generate")
    async def outfit_forge_generate(request):
        try:
            result = generate_outfits(await request.json())
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response(result)

    @PromptServer.instance.routes.post("/sickollie/outfit-forge/audit")
    async def outfit_forge_audit(request):
        payload = await request.json()
        lines = payload.get("lines")
        if not isinstance(lines, list):
            return web.json_response({"ok": False, "error": "Outfit lines must be a list"}, status=400)
        audit = audit_outfits(lines, required=payload.get("required"), avoided=payload.get("avoided"))
        theme = _line(payload.get("theme"))
        if theme:
            audit = _apply_fidelity(audit, [_line(line) for line in lines], parse_theme(theme))
        return web.json_response({"ok": True, "audit": audit})

    @PromptServer.instance.routes.post("/sickollie/outfit-forge/export-library")
    async def outfit_forge_export_library(request):
        payload = await request.json()
        lines = payload.get("lines")
        if not isinstance(lines, list):
            return web.json_response({"ok": False, "error": "Outfit lines must be a list"}, status=400)
        try:
            result = export_to_outfit_library(
                lines,
                category=str(payload.get("category") or ""),
                subcategory=str(payload.get("subcategory") or ""),
            )
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response(result)
