from __future__ import annotations

"""Proven anchored-bodywear vocabulary and silhouette catalog for Outfit Forge.

This began as the deterministic builder used for the first 37 Outfit Forge
seed logs.  The interactive Forge imports its theme profiles and 100 diverse
structures; this module deliberately performs no filesystem writes.
"""

import re


def parts(value: str) -> list[str]:
    return [item.strip() for item in value.split("|")]


def theme(name: str, materials: str, colors: str, anchors: str, ornaments: str, behaviors: str) -> dict[str, object]:
    return {
        "name": name,
        "materials": parts(materials),
        "colors": parts(colors),
        "anchors": parts(anchors),
        "ornaments": parts(ornaments),
        "behaviors": parts(behaviors),
    }


THEMES = [
    theme(
        "Symbiote Couture",
        "oil-slick symbiote membrane|velvet-soft living ribbons|translucent dermal film|pearl-veined bioelastic straps|ribbed creature-silk|glossy adaptive skin bands|fine cilia-edged webbing|soft carapace petals|gelatinous muscle cords|iridescent breathing mesh|living satin lamellae|warm chitin-thread lace",
        "black-violet|petrol blue|pearl gray|bruise-lavender|deep teal|opal white|wine red|midnight indigo|smoky rose|green-black|amethyst|moonlit silver",
        "a soft sucker rosette seated inside the navel|self-closing tendril loops threaded through body rings|tiny gripping cilia nestled beneath an ear cuff|a mouth-held living bit joined to the collar|four adhesive pads cupping the shoulder hollows|a tapered appendage resting inside a decorative collar port|paired filaments passed through ear tunnels|microclaws clasped only to existing piercing jewelry|a warm suction seal hidden beneath the sternum ornament|coiling feelers locked around wrist and ankle hollows|a living plug nested in the navel and linked to both hips|flexible hooks gripping the edges of a jeweled waist ring",
        "pulsing pearl nodes|gill-like frills|tiny blinking eye-gems|vein-lit edging|soft fin crests|seed-shaped sensory beads|miniature sucker blossoms|opal nerve clusters|delicate chitin scales|whisker-fine feelers|glossy breathing pores|iridescent spinal fins",
        "tightens whenever the structure shifts|breathes in slow visible ripples|repositions its smallest straps for balance|follows the wearer's pulse with a dim glow|curls protectively around every loose edge|relaxes into glossy drapes when still|flicks its sensory fringe toward movement|changes sheen as tension travels through the material|contracts gently around each anchor point|keeps every open panel perfectly suspended|unfurls new loops as the body turns|settles like a contented second skin",
    ),
    theme(
        "Botanical Rooting Bodywear",
        "supple root cords|flowering vine ribbons|moss-backed creepers|translucent leaf membranes|willow-fine tendrils|braided aerial roots|soft fern runners|dew-bright ivy chains|orchid-stem latticework|pale mycelial rootlets|seedpod-linked vines|silken climbing stems",
        "moss green|blush-petal pink|moonflower white|deep forest|orchid purple|new-leaf lime|autumn copper|sage and cream|night-bloom blue|rose red|pollen gold|misty eucalyptus",
        "a root tip curled neatly into the navel|vine loops threaded through botanical ear tunnels|soft tendrils hooked around existing body rings|a flower stem held between the lips like a living clasp|rootlets tucked into the hollows above both collarbones|a seedpod toggle lodged through a carved wooden waist ring|fine runners woven through ankle and wrist bangles|a mossy suction disk hidden beneath the central blossom|paired roots passing through shoulder jewelry|leaf-stem hooks catching the eyelets of a body chain|a coiled vine nested inside a decorative collar aperture|tiny root fingers gripping only polished piercing hardware",
        "dew-pearl droplets|opening moonflowers|tiny glowing seedpods|velvet moss patches|pollen-dusted stamens|thornless rosebuds|curling fern tips|miniature pitcher blooms|beaded berry clusters|lace-thin leaf veins|hanging orchid bells|crystal-clear sap beads",
        "slowly roots more firmly as the wearer moves|turns its blossoms toward nearby light|draws loose stems back into tension|unfurls one leaf at a time|shivers with pollen-bright movement|keeps each vine taut without pinching|opens at the warmth of skin|coils tighter before relaxing again|trails fresh tendrils toward unused jewelry|lifts its petals whenever the body turns|closes its buds around every fastener|grows a faint lace of new roots between anchors",
    ),
    theme(
        "Cybernetic Docking Wear",
        "fiber-optic cable bundles|articulated chrome conduits|translucent data tubes|braided signal wires|flexible circuit straps|segmented robotic tendrils|electroluminescent flat cable|carbon-silk connector bands|clear coolant hoses|microchain bus lines|holographic ribbon circuits|soft silicone docking cords",
        "electric cyan|warning red|ultraviolet|chrome silver|acid green|laser magenta|smoke-clear gray|cobalt blue|amber and black|white with cyan light|oil-slick rainbow|graphite",
        "a magnetic plug seated in a jeweled navel port|paired data leads docked into ear-cuff sockets|microconnectors latched to existing body rings|a slim mouthpiece port carrying the collar tension|four magnetic pads aligned over collarbone nodes|a keyed coupler twisted into the central waist socket|cables threaded through illuminated ear tunnels|robotic pincers holding polished piercing hardware|a vacuum docking puck sealed beneath the sternum plate|ankle and wrist ports sharing the load through tension lines|a telescoping connector nested in a decorative hip aperture|tiny locking probes clipped only into jewelry eyelets",
        "status-light pearls|rotating connector halos|micro-LED constellations|clear processor charms|holographic warning glyphs|tiny cooling fins|pulse-meter beads|chrome antenna tassels|data-crystal pendants|oscillating light bars|miniature servo flowers|glowing circuit embroidery",
        "auto-tensions after every step|runs a chasing pulse from socket to socket|retracts loose cable with a quiet mechanical curl|reconfigures its circuit path as the body turns|blinks each connection green in sequence|keeps the open architecture perfectly calibrated|fans its cooling fins under strain|redistributes weight through magnetic feedback|locks with a brief halo of light|floats millimeters above skin between docks|spools out extra length for movement|returns every connector to exact alignment",
    ),
    theme(
        "Deep-Sea Parasite Fashion",
        "translucent lamprey chains|soft cephalopod arms|jelly membrane ribbons|sucker-lined abyssal cords|pearl-veined sea slugs|rippled fin webbing|eel-smooth living bands|gelatinous siphon tubes|anemone-fringed straps|iridescent mantle skin|delicate medusa filaments|barnacle-soft clasp organisms",
        "abyssal blue|ink black|jellyfish pink|cold turquoise|pearl white|bioluminescent violet|sea-glass green|coral red|midnight teal|opal lilac|phosphor cyan|smoky indigo",
        "a gentle siphon seal centered inside the navel|tiny lamprey clasps attached to existing body rings|filaments threaded through pearl-lined ear tunnels|a soft oral loop held lightly between the lips|suction disks nested in the collarbone hollows|a shell toggle resting through a jeweled waist aperture|eel tails coiled around wrist and ankle jewelry|minute mouth-clasps gripping only polished piercing hardware|a broad mantle sucker concealed beneath the sternum jewel|paired tendrils tucked through fin-shaped shoulder rings|a tapered sea-creature foot nested in a decorative collar port|barnacle clasps locked onto chain eyelets at both hips",
        "lure-like glow beads|pearl egg clusters|feathery gill plumes|water-drop crystals|tiny translucent fins|coral-pink sucker cups|blue-fire photophores|shell-chip scales|drifting jelly fringe|soft anemone crowns|glassy fish-eye gems|bubble-bright nodes",
        "pulses with a slow tidal rhythm|ripples as though moved by deep water|brightens whenever tension reaches an anchor|draws its filaments inward with each turn|keeps every membrane afloat around the body|fans open its gills under movement|undulates gently along the open edges|dims to an abyssal shimmer when still|curls its smallest arms around loose jewelry|balances the drapes through alternating suction|trails its luminous fringe behind each step|settles into a glassy wet sheen",
    ),
    theme(
        "Living Jewelry Swarm",
        "chains of jewel-backed beetles|tiny ring-shaped organisms|pearl-bodied clasp creatures|crystal-winged moth links|silver-shelled crawling charms|miniature dragonfly chains|opal antlike carriers|gemstone spider brooches|soft-bodied bead creatures|iridescent scale insects|firefly-linked filaments|delicate shell-backed mites",
        "jewel-tone rainbow|opal white|black diamond|rose gold|emerald green|sapphire blue|ruby red|amethyst purple|moonstone|champagne crystal|iridescent teal|pearl pink",
        "a circle of tiny creatures gripping the rim of the navel|living links threaded through both ear tunnels|microclaws fastened only around existing body rings|a jeweled moth clasp resting between the lips|beetle brooches nested into collarbone hollows|a chain of carriers passing through a sculpted waist ring|insect links wrapped around wrist and ankle bangles|minute jewel mouths holding polished piercing hardware|a broad crystal bug anchoring beneath the sternum chain|paired dragonflies hooked through shoulder jewelry|a pearl creature curled inside a decorative collar aperture|tiny ring organisms interlocked with hip-chain eyelets",
        "fluttering gem wings|antenna-fine chain fringe|living pearl droplets|faceted shell mosaics|blinking firefly sparks|tiny crownlike carapaces|crystal leg filigree|moving bead tassels|opal wing dust|miniature halo rings|bejeweled feelers|shimmering scale confetti",
        "redistributes the swarm whenever one link loosens|flutters in coordinated waves|crawls a few millimeters to maintain tension|lights one creature after another|joins new living links across open space|folds every jeweled wing when still|keeps the suspended chains in constant balance|turns its faceted shells toward light|tightens by linking bodies into shorter chains|spreads apart to reveal more skin|gathers into ornate brooch clusters at rest|moves like a constellation rearranging itself",
    ),
    theme(
        "Void Tendril Harnesses",
        "impossibly thin void tendrils|smoke-black gravity cords|starless ribbon shadows|matte abyssal filaments|light-swallowing coilwork|ink-dark spatial threads|soft singularity straps|black-glass tentacle lines|weightless eclipse bands|negative-space serpentine cords|velvet-dark dimensional ribbons|faintly iridescent void silk",
        "absolute black|eclipse violet|blue-black|charcoal with ultraviolet edges|starless indigo|oil-dark green|smoke gray|black cherry|midnight purple|obsidian|void teal|deep cosmic brown",
        "one tendril vanished neatly into the navel shadow|black loops threaded through dark metal ear tunnels|impossible hooks attached to existing body rings|a weightless void bit held between the lips|gravity knots resting in both collarbone hollows|a shadow peg seated through the central waist aperture|filaments disappearing into wrist and ankle cuffs|tiny black claws gripping only piercing jewelry|an unseen suction point beneath the sternum eclipse|paired strands passed through shoulder rings|a tapering cord nested inside a decorative collar port|dimensional loops caught through hip-chain eyelets",
        "pinprick event-horizon beads|eclipse halos|black crystal droplets|faint ultraviolet runes|starless mirror chips|gravity-warped pearl nodes|smoke wisps|tiny orbiting rings|negative-space tassels|dark prism shards|constellation specks|lightless fringe",
        "holds itself taut across apparently empty space|erases its own loose ends|bends nearby highlights toward each anchor|floats without visible weight|tightens by shortening the darkness between points|flickers at the edge of perception|casts no shadow despite its depth|stretches into thinner lines as the body turns|gathers surrounding haze into its open pattern|keeps every suspended piece eerily motionless|uncoils from nowhere when more length is needed|closes into perfect black loops at rest",
    ),
    theme(
        "Organic Hook-and-Loop Couture",
        "soft cartilage hooks|fleshy velvet loops|curling bioelastic barbs|suction-backed organic tabs|ribbed tendon ribbons|petal-soft gripping bands|living hook mesh|flexible chitin fasteners|gel-lined clasp cords|ciliated loop lace|warm membrane tape|interlocking shell tendrils",
        "coral pink|plum black|pearl beige|deep burgundy|seafoam|lavender gray|burnished copper|opal peach|blue-violet|cream and rose|dark teal|smoky crimson",
        "a padded hook curled into the navel hollow|looped tendrils passed through ear tunnels|soft barbs clasped only around existing body rings|a velvet bite-tab held between the lips|paired suction loops seated above the collarbones|an organic toggle fitted through a jeweled waist ring|interlocking bands wrapped through wrist and ankle cuffs|microhooks attached only to polished piercing hardware|a broad loop patch hidden beneath the sternum ornament|cartilage hooks nested in shoulder jewelry|a tapered fastener resting inside a decorative collar opening|tiny looped feelers caught through both hip eyelets",
        "spiral hook rosettes|ciliated edging|shell-button nodes|soft barb fringe|glossy tendon bows|petal-shaped loop patches|miniature clasp mouths|ribbed cartilage beads|gel pearl droplets|interlocking heart motifs|curling fastener tassels|smooth chitin studs",
        "fastens itself with a visible ripple|performs a peel-and-reseal motion as movement demands|passes tension from hook to loop in waves|curls every loose barb safely inward|rebuilds its fastening map after each turn|keeps the open sections under gentle opposing pull|clicks its shell tabs softly into place|reaches for the nearest unused loop|relaxes without releasing any anchor|links smaller fasteners into a decorative chain|adjusts its grip through hundreds of tiny contacts|folds flat against the body when still",
    ),
    theme(
        "Threaded-Body Ornament",
        "living silk cords|ultrafine satin filaments|pearl-strung biological thread|glowing nerve fibers|braided microtendrils|crystal-bearing floss|soft metallic ligatures|translucent ribbon thread|hair-fine luminous lines|velvet cord organisms|iridescent monofilaments|lace-thin flexible wires",
        "pearl white|scarlet|electric blue|soft gold|lavender|emerald|black and silver|opal rainbow|rose pink|ice cyan|deep plum|champagne",
        "a cord laced through a jeweled navel ring|multiple filaments passed through both ear tunnels|thread loops running only through existing body jewelry|a satin strand held between the lips as a tension point|crossed threads seated in collarbone cuffs|a pearl cord woven through the central waist aperture|fine lines routed through wrist and ankle bangles|microtendrils threaded only through polished piercing rings|a hidden knot beneath the sternum pendant|paired cords passed through shoulder jewelry|a narrow ribbon tucked through a decorative collar port|several lines braided through opposing hip eyelets",
        "sliding pearl markers|tiny suspended crystals|needle-fine tassels|knotted star charms|beaded tension scales|floating metal droplets|miniature woven rosettes|prismatic thread fringe|delicate charm ladders|soft luminous knots|tiny bell-shaped beads|open lace diagrams",
        "retensions itself one filament at a time|draws each knot toward the next anchor|keeps every suspended charm at a different height|slides smoothly through jewelry as the body turns|braids loose ends into fresh ornament|loosens into longer curves when seated|tightens the whole network from one central thread|moves its beads to rebalance the drape|forms new knots without visible hands|leaves wide areas connected by only a single line|vibrates with a faint harp-string shimmer|coils spare length into miniature bows",
    ),
    theme(
        "Magnetic Liquid-Metal Bodywear",
        "liquid chrome ribbons|mercurial silver droplets|ferrofluid bead chains|mirror-bright metal streams|magnetic alloy lace|molten-looking body plates|soft gallium cords|floating chrome scales|polished metal gel|holographic ferrofluid strands|mirror mercury mesh|fluid nickel petals",
        "mirror silver|oil-slick chrome|rose chrome|blue steel|liquid gold|gunmetal|iridescent titanium|black chrome|copper mirror|violet metal|ice silver|green-shift alloy",
        "a magnetic droplet seated against a navel stud|floating ribbons drawn through metal ear tunnels|microbeads clinging only to existing body rings|a cool magnetic bit held lightly between the lips|paired field disks aligned over collarbone studs|a liquid-metal peg suspended inside the waist ring|chrome streams locked to wrist and ankle cuffs|tiny alloy hooks attracted only to piercing hardware|a hidden magnetic pool beneath the sternum plate|metal petals docked into shoulder jewelry|a tapered droplet hovering inside a decorative collar port|ferrofluid lines bridging both hip-chain eyelets",
        "orbiting chrome beads|mirror-finish fringe|floating metal pearls|ferrofluid spikes|liquid heart charms|polished droplet tassels|holographic ripple lines|tiny compass halos|mercury lace scallops|magnetic shard constellations|molten-looking rosettes|levitating chain fragments",
        "flows back toward every magnet after movement|breaks into droplets without losing tension|hovers just above skin between anchor points|flattens into mirror panels when still|climbs its own field lines in slow waves|merges separate straps into one liquid arc|pulls loose beads into new fasteners|stretches into hair-thin metallic bridges|ripples whenever opposing magnets shift|keeps rigid ornaments floating without visible chains|pours around each contour before reforming|snaps into exact symmetry with a soft shimmer",
    ),
    theme(
        "Spider-Silk Restraint Fashion",
        "moonlit spider silk|widow filament|dew-strung web thread|golden orb-weaver silk|velvet cobweb ribbons|iridescent dragline fiber|smoke-fine lace webbing|silver radial strands|pearl-beaded capture silk|soft elastic web cords|crystal-dusted spiral silk|translucent hammock webbing",
        "moon white|widow-black|silver gray|blood red|opal rainbow|pale gold|lavender mist|icy blue|dusty rose|deep violet|emerald shimmer|smoky nude",
        "a spiral web anchored around the navel ring|radial threads passed through both ear tunnels|silk lines tied only to existing body jewelry|a soft thread bit held between the lips|dew-bright knots seated at the collarbone hollows|a woven toggle threaded through the waist ring|draglines routed around wrist and ankle bangles|microloops attached only to polished piercing hardware|a dense web rosette hidden beneath the sternum jewel|paired silk anchors caught in shoulder jewelry|a tapered cocoon knot tucked through a decorative collar port|crossed strands tensioned through both hip eyelets",
        "dew-crystal droplets|tiny spider brooches|radial lace medallions|hanging egg-pearl beads|widow-hourglass charms|webbed fringe fans|silver spinneret tassels|iridescent silk bows|crystal fly-shaped gems|soft cocoon rosettes|spiral web scallops|beaded capture-thread curtains",
        "retensions every radial line after movement|catches light in shifting geometric planes|draws slack into a new spiral|vibrates like a delicate instrument|supports each drape through opposing silk pulls|gathers loose thread into tiny cocoons|opens its web pattern as the body turns|keeps every dew bead suspended in place|adds a fresh cross-thread wherever tension drops|contracts into denser lace when still|stretches farther than its fragile look suggests|reweaves broken symmetry within a breath",
    ),
    theme(
        "Bioluminescent Fungal Symbiotes",
        "glowing mycelial cords|velvet mushroom-gill ribbons|translucent fungal membranes|spore-dusted hyphae lace|soft bracket-fungus plates|pearl-veined mold silk|jelly fungus straps|luminous rootlike mycelium|delicate cap-linked chains|feathery lichen bands|ribbed morel mesh|silken fairy-ring tendrils",
        "ghost blue|phosphor green|violet glow|moon white|amber bioluminescence|coral pink|deep forest black|turquoise|mushroom cream|electric lilac|rust and cyan|opal mint",
        "a mycelial tuft rooted gently inside the navel|hyphae threaded through mushroom-shaped ear tunnels|fine fungal loops attached only to existing body rings|a soft glowing stem held between the lips|spongy anchor pads nestled above both collarbones|a cap-shaped toggle passed through the waist ring|mycelial cords woven around wrist and ankle jewelry|tiny rootlets gripping only polished piercing hardware|a luminous fungal disk hidden beneath the sternum ornament|paired hyphae caught through shoulder rings|a tapered stem nested in a decorative collar aperture|fairy-ring threads linked through both hip eyelets",
        "glowing spore pearls|miniature mushroom caps|delicate gill fans|dew-bright lichen|puffball pompons|crystal hyphae fringe|bracket-fungus ruffles|soft mold rosettes|tiny lantern caps|vein-lit shelf fungi|spore-cloud tassels|iridescent slime droplets",
        "spreads a faint lace of new mycelium between anchors|releases a harmless shimmer of spores with movement|opens its gills whenever tension increases|brightens from the center outward|draws slack into soft fungal knots|keeps each cap hovering on a web of hyphae|breathes in slow forest-floor pulses|curls its rootlets more securely around jewelry|grows a new luminous bridge across empty space|folds its caps neatly when still|shifts color as spores travel along the cords|settles into a velvety living lace",
    ),
    theme(
        "Carnivorous Flower Couture",
        "fleshy petal straps|pitcher-plant ribbons|soft flytrap clasps|thornless grasping vines|glossy orchid mouths|sundew-beaded tendrils|ruffled corpse-flower silk|supple stem harnesses|translucent calyx membranes|velvet snapdragon cords|curling venus-trap bands|silken pollen filaments",
        "blood rose|poison green|orchid purple|cream and crimson|midnight burgundy|sundew pink|tropical orange|black cherry|acid yellow|deep botanical teal|blush coral|iridescent plum",
        "a tiny flower mouth cupped around the navel jewel|stem loops threaded through floral ear tunnels|petal clasps gripping only existing body rings|a soft snapdragon bit held between the lips|paired flytrap rosettes seated at the collarbones|a pitcher-shaped toggle fitted through the waist ring|vine mouths closed around wrist and ankle bangles|miniature calyx hooks attached only to piercing hardware|a broad bloom sucker hidden beneath the sternum flower|orchid stems caught through shoulder jewelry|a tapered bud nested inside a decorative collar opening|sundew tendrils linked through both hip eyelets",
        "drooling nectar pearls|toothlike petal fringe|glossy pollen beads|tiny flytrap rosettes|curling stamen tassels|dew-bright sundew hairs|ruffled calyx fans|seedpod bells|veined orchid wings|miniature pitcher charms|velvet thorn motifs|opening bud clusters",
        "snaps each floral clasp shut with delicate precision|turns every open bloom toward warmth|draws loose vines back through its anchor flowers|tastes the air with curling stamens|holds tension through a chain of gentle flower mouths|opens wider whenever the body turns|collects its nectar into bright suspended beads|folds predatory petals over every fastener|uncoils fresh stems toward unused jewelry|keeps the exposed structure lush but weightless|quivers its sundew fringe under movement|settles into an eerily beautiful bouquet",
    ),
    theme(
        "Bone-and-Cartilage Relic Wear",
        "polished ivory hooks|flexible cartilage loops|riblike bone arcs|jointed ossicle chains|translucent tendon lace|smooth vertebral beads|carved antler ribbons|pearl-white shell bone|soft horn lamellae|delicate wishbone frames|fossilized fin spines|supple cartilage mesh",
        "aged ivory|smoke black|bone white|oxblood|fossil amber|moon gray|antique gold|pale rose|deep umber|blue-white|verdigris and cream|blackened silver",
        "a smooth bone peg seated within the navel jewel|cartilage loops threaded through ear tunnels|tiny ivory hooks clasped only to existing body rings|a polished bit held lightly between the lips|paired wishbones nested over the collarbone hollows|a carved vertebral toggle passed through the waist ring|jointed loops fitted around wrist and ankle bangles|minute ossicle claws gripping only piercing hardware|a broad rib medallion anchored beneath the sternum chain|bone arcs caught through shoulder jewelry|a tapered horn fitting nested in a decorative collar port|cartilage rings interlocked with both hip eyelets",
        "vertebral pearl strands|tiny tooth-shaped charms|rib-fan fringe|fossil bead tassels|carved spiral scrimshaw|jointed finger-bone lace|polished marrow windows|antler-tip pendants|delicate skullflower rosettes|ivory chime pieces|shell-inlaid ossicles|smooth horn droplets",
        "flexes at its cartilage joints with every turn|clicks softly as the tension redistributes|nests each rigid arc against the next|keeps the open framework balanced through jointed hooks|folds its rib fans closer when still|slides vertebral beads toward the load-bearing anchors|springs gently back into shape|locks each polished relic with a quiet twist|moves like an articulated ceremonial skeleton|leaves the largest bones apparently floating|draws smaller ossicles into protective clusters|settles into a perfectly fitted exoskeletal outline",
    ),
    theme(
        "Alien Larval Adornment",
        "pearl-bodied larvae|translucent grub chains|soft segmented hatchlings|glowing pupal cords|silken cocoon membranes|jellylike nymph straps|ribbed alien caterpillars|opal egg-sac ribbons|tiny sucker-tailed larvae|velvet chrysalis plates|bioluminescent worm loops|delicate embryo-bead strands",
        "opal pink|acid cyan|pearl green|amethyst|milky white|coral orange|black-violet|electric blue|hatchling gold|translucent lavender|seafoam|oil-slick rainbow",
        "a curled larva nestled gently inside the navel|segmented tails threaded through ear tunnels|tiny sucker mouths attached only to existing body rings|a soft hatchling clasp held between the lips|paired cocoon pads tucked above the collarbones|an egg-shaped toggle passed through the waist ring|larval chains wrapped around wrist and ankle jewelry|minute gripping feet holding only polished piercing hardware|a broad pupal disk anchored beneath the sternum gem|twin nymphs hooked through shoulder rings|a tapered chrysalis seated in a decorative collar aperture|sucker-tailed larvae linked through both hip eyelets",
        "glowing egg pearls|translucent feelers|miniature cocoon tassels|soft segmented fringe|pupal shell rosettes|tiny bioluminescent eyes|silk-spinning mouthparts|opal breathing pores|embryonic finlets|gel bead clusters|iridescent shed-skin ribbons|delicate antenna crowns",
        "links its small bodies together when more tension is needed|curls every larva into a secure living clasp|pulses with synchronized hatchling light|spins a fresh silk bridge across loose sections|uncurls antennae toward nearby jewelry|draws egg pearls into protective clusters|shifts its segmented chains around the body|rests its pupae motionless between active straps|tightens through coordinated sucker tails|opens translucent finlets as the wearer moves|rearranges into a new colony after each turn|settles with a faint collective breathing motion",
    ),
    theme(
        "Living Knotwork",
        "rope-bodied organisms|velvet living cords|braided tentacle rope|soft muscle-fiber strands|glossy serpent ribbons|ciliated knot cords|pearl-skinned lashing organisms|elastic vine rope|translucent tendon lines|satin-smooth coil creatures|ribbed bio-cordage|iridescent looped strands",
        "deep crimson|black-violet|pearl white|marine teal|burnished gold|lavender|forest green|copper rose|electric blue|smoke gray|oil-slick plum|coral pink",
        "a compact living knot nested in the navel|cord loops passed through both ear tunnels|braided ends tied only around existing body rings|a soft tension cord held between the lips|paired knot rosettes seated at the collarbones|a self-tightening toggle woven through the waist ring|living hitches wrapped around wrist and ankle jewelry|microknots fastened only to polished piercing hardware|a broad decorative bend anchored beneath the sternum charm|looping strands caught in shoulder rings|a tapered knot tucked through a decorative collar opening|opposing hitches pulled through both hip eyelets",
        "figure-eight rosettes|pearl-tipped rope fringe|ornamental sailor knots|braided tassel ends|tiny living bow knots|celtic loop medallions|coiled spiral buttons|glossy knot ladders|hitchwork scallops|soft macrame fans|interlocking heart knots|floating loop garlands",
        "ties a fresh balancing knot whenever tension shifts|untangles one section while tightening another|draws every loose end into ornamental loops|keeps its knots firm without becoming rigid|slides hitches smoothly along the body|braids neighboring organisms into thicker cords|loosens into long decorative curves at rest|reforms simple loops into elaborate knotwork|passes tension cleanly from bend to bend|coils spare length into glossy rosettes|cinches itself through opposing anchor points|settles into an intricate self-tied pattern",
    ),
    theme(
        "Mouth-Clasp Couture",
        "miniature velvet creature heads|pearl-toothed clasp mouths|soft-lipped ornamental buds|chrome-jawed living brooches|tiny shell-beaked fasteners|flower-mouthed strap ends|gentle lamprey clasps|serpent-head cord locks|jewel-eyed bite tabs|plush alien mouthlets|cartilage-lipped toggles|glossy kissing clasps",
        "ruby and pearl|black chrome|orchid purple|rose gold|deep teal|ivory|candy pink|sapphire blue|burnished copper|oil-slick green|wine red|moon silver",
        "a central clasp mouth holding the navel ring|paired mouthlets gripping jewelry inside the ear tunnels|tiny jaws closed only around existing body rings|a soft ornamental bit held between the lips|two velvet mouths nestled at the collarbone hollows|a shell-beaked toggle biting through the waist ring|gentle clasp creatures holding wrist and ankle bangles|microjaws attached only to polished piercing hardware|a broad kissing clasp anchored beneath the sternum jewel|serpent heads biting shoulder jewelry|a tapered mouth clasp fitted into a decorative collar aperture|paired bite tabs joined through both hip eyelets",
        "pearl tooth rows|tiny jeweled tongues|lip-shaped rosettes|beaded jaw fringe|enamel fang charms|glossy kiss marks|hinged palate fans|soft whisker feelers|gemstone uvulas|miniature smile medallions|shell-beak tassels|velvet lip bows",
        "cycles through one release-and-regrip at a time|closes each tiny mouth with ornamental precision|passes loose straps from one mouthlet to the next|keeps every jaw relaxed but secure|opens its jeweled lips whenever tension falls|turns clasp heads toward unused rings|holds suspended drapes between paired bites|chatters its pearl teeth in a decorative ripple|folds tiny tongues around chain links|balances the structure through opposing mouth clasps|rests with every small jaw neatly closed|rearranges its fasteners like a living row of brooches",
    ),
    theme(
        "Piercing-Suspended Fashion",
        "ultralight body chains|silk-fine suspension cords|crystal thread drapes|featherweight mesh panels|soft metallic filaments|pearl-strung microchains|translucent ribbon ligatures|holographic chain lace|delicate elastic lines|liquid-silver tassel cords|floating organza webs|living satin threads",
        "champagne gold|mirror silver|black diamond|opal pink|electric blue|soft ivory|rose gold|amethyst|icy cyan|deep ruby|iridescent clear|smoky gunmetal",
        "a central suspension line routed through the navel ring|weight-bearing loops passed through reinforced ear tunnels|microchains connected only to existing body jewelry|a featherlight mouth ring sharing the collar tension|paired collarbone piercings carrying an open chest drape|a jeweled waist ring supporting the lower framework|fine lines distributed across wrist and ankle piercing jewelry|delicate clips attached only to polished piercing hardware|a sternum ring bearing the central pendant load|shoulder rings supporting opposing side panels|a decorative collar port carrying the back cascade|twin hip rings suspending the entire lower drape",
        "floating crystal drops|graduated chain fringe|tiny counterweight pearls|weightless mesh fans|prismatic bead ladders|delicate balance bars|open geometric chainwork|soft tassel rain|miniature pulley charms|sliding tension beads|holographic thread halos|fine chandelier pendants",
        "distributes every gram across several jewelry anchors|keeps large drapes aloft through tiny counterweights|slides its balance beads after each movement|lets the panels float between points of contact|transfers tension without twisting the jewelry|opens into a wider suspended silhouette when still|draws slack upward through miniature pulleys|keeps each chain at a distinct graceful curve|moves the counterweights in silent opposition|leaves almost the entire body untouched by fabric|settles each pendant directly beneath its anchor|maintains a delicate architectural equilibrium",
    ),
    theme(
        "Suction-Cup Minimalism",
        "crystal-clear suction disks|soft silicone straps|jellylike adhesive cups|opal vacuum rosettes|translucent gel cords|velvet-rimmed suckers|liquid-glass membranes|tiny cephalopod cups|glossy polymer tabs|frosted suction lace|iridescent vacuum petals|barely visible elastic film",
        "water clear|milky opal|blush pink|smoke gray|electric cyan|ultraviolet|sea-glass green|ruby transparent|amber clear|ice blue|holographic|black glass",
        "a single vacuum rosette centered inside the navel|paired microcups sealed within the ear hollows|clear sucker tabs attached beside existing body rings|a soft suction bit held lightly between the lips|four transparent disks seated over collarbone hollows|a jelly peg fitted through the waist ring|minimal cups hidden beneath wrist and ankle jewelry|tiny suction flowers gripping only polished piercing hardware|one broad invisible seal beneath the sternum ornament|paired vacuum petals tucked into shoulder hollows|a tapered gel cup nested in a decorative collar aperture|two clear disks aligned with the hip-chain eyelets",
        "bubble-like rim beads|tiny pressure halos|clear droplet fringe|opal seal rings|air-pocket pearls|jelly petal edges|holographic vacuum lines|soft concentric ripples|miniature pressure gauges|crystal sucker rosettes|floating gel beads|frosted scallop borders",
        "holds with almost no visible structure|performs a cup-by-cup release-and-reseal farther along|flattens every disk until only its rim catches light|passes tension through a handful of transparent contacts|ripples outward whenever a seal strengthens|keeps open panels floating from isolated suction points|draws trapped air into decorative pearl bubbles|adjusts pressure without changing the silhouette|leaves wide spans of bare space between anchors|turns invisible wherever the material meets the body|lifts each edge through opposing vacuum pulls|settles into an impossibly spare arrangement",
    ),
    theme(
        "Inflatable Organism Bodywear",
        "translucent breathing tubes|soft inflatable tendrils|air-filled membrane ribbons|jelly balloon straps|ribbed pneumatic organisms|clear buoyant cords|velvet inflatable loops|pearlescent bladder panels|segmented air-sack chains|holographic cushion bands|soft tubular creatures|delicate pressure-web membranes",
        "bubblegum pink|clear cyan|opal white|acid green|lavender|coral orange|smoke transparent|electric blue|pearl gold|iridescent rainbow|deep violet|seafoam",
        "a small inflatable bulb seated inside the navel|deflated tips threaded through ear tunnels before expanding|soft tube ends looped only through existing body rings|a cushioned mouthpiece held between the lips|paired air pads nestled above the collarbones|an expandable toggle passed through the waist ring|inflated loops locked around wrist and ankle jewelry|tiny pressure bulbs gripping only polished piercing hardware|a broad air cushion anchored beneath the sternum gem|tubular ends caught through shoulder rings|a tapered bladder fitted into a decorative collar aperture|paired pneumatic loops expanded through both hip eyelets",
        "floating bubble pearls|transparent valve flowers|air-pocket fringe|tiny pressure bulbs|inflated heart charms|soft tubular bows|holographic cushion scales|beaded valve tassels|pillowlike rosettes|clear spiral air chambers|buoyant fin ruffles|miniature bellows ornaments",
        "inflates just enough to lock every loop in place|deflates one section before sliding it to a new anchor|breathes through a visible sequence of air chambers|lifts its panels away from the body with buoyant tension|redistributes pressure whenever the wearer turns|keeps the silhouette soft despite its secure hold|pumps spare air into decorative bubbles|expands around jewelry without covering it|pulses gently from valve to valve|floats its largest membranes on inflated edging|shrinks into slim tubes when still|settles into a glossy cloud of living loops",
    ),
    theme(
        "Living Belt-Creatures",
        "long velvet belt organisms|glossy serpent straps|broad ribbonlike creatures|segmented girdle eels|soft centipede bands|muscular satin coils|pearl-backed belt beasts|flatworm sashes|ribbed constrictor ribbons|iridescent waist serpents|fin-edged strap creatures|supple many-legged bands",
        "black cherry|petrol blue|pearl cream|emerald|amethyst|burnished gold|coral pink|deep teal|smoke gray|ruby red|oil-slick rainbow|midnight blue",
        "a narrow tail tip curled into the navel|fine feelers threaded through both ear tunnels|small belt-creature mouths clasped only to existing body rings|a soft guiding rein held between the lips|paired forelimbs resting in collarbone hollows|a tail toggle passed through the central waist ring|smaller appendages gripping wrist and ankle jewelry|tiny feet holding only polished piercing hardware|a broad sucker belly anchored beneath the sternum ornament|forelegs caught through shoulder rings|a tapered head nested in a decorative collar aperture|twin tails looped through both hip eyelets",
        "pearl spinal nodes|tiny fin ruffles|jeweled eye spots|many-legged fringe|soft whisker tassels|segmented shell plates|glossy breathing spiracles|ribbonlike tail bows|miniature crown crests|opal belly scales|delicate feeler chains|velvet dorsal fins",
        "wraps the torso repeatedly before locking its own tail|uses smaller limbs to grip every crossing|uncoils one lap whenever more movement is needed|passes tension from head to tail in a muscular ripple|nuzzles loose straps back beneath its body|forms chest support from several coordinated wraps|shifts one coil higher while another slides lower|keeps its soft belly scales against the body|tightens only where neighboring loops overlap|rests with its head tucked beneath the final coil|rebuilds the whole silhouette from one continuous body|settles into a living belt sculpture",
    ),
    theme(
        "Pearl-Node Neural Harnesses",
        "glowing neural filaments|pearl-linked nerve cords|translucent synaptic threads|bioelectric wire lace|soft axon ribbons|dendrite branching straps|opal impulse chains|fine sensory fiber bundles|myelin-sheen bands|luminous ganglion mesh|crystal nerve pathways|pulsing neuron tendrils",
        "neural blue|pearl white|electric violet|synapse pink|golden impulse|turquoise|soft silver|deep indigo|mint glow|rose opal|cyan and amber|black with white light",
        "a central pearl node seated at the navel|neural fibers threaded through both ear tunnels|synaptic clips connected only to existing body rings|a soft sensory node held between the lips|paired ganglia nested over collarbone hollows|a pearl plug passed through the waist ring|axon loops routed through wrist and ankle jewelry|microfilaments attached only to polished piercing hardware|a bright nexus hidden beneath the sternum jewel|branching dendrites caught in shoulder rings|a tapered nerve node fitted into a decorative collar port|twin impulse lines linked through both hip eyelets",
        "pulsing pearl ganglia|branching light dendrites|tiny synapse sparks|graduated node chains|neural halo rings|bioelectric tassels|crystal impulse beads|soft myelin rosettes|constellation-like nerve maps|luminous receptor fringe|opal signal droplets|delicate axon fans",
        "sends a visible pulse from anchor to anchor|reroutes light around any slack filament|brightens each pearl node in sequence|balances tension like a responsive nervous system|branches new fibers toward unused jewelry|dims its peripheral lines while still|flares at every point of contact|draws loose signals into the central nexus|keeps the open network perfectly mapped|splits one impulse into mirrored pathways|shivers with a brief electric response to movement|settles into a calm constellation of living light",
    ),
    theme(
        "Abyssal Fishing-Lure Fashion",
        "glowing lure filaments|barbless ornamental hook chains|eel-smooth leader cords|pearl-beaded fishing line|soft tentacle leaders|translucent net ribbons|bioluminescent bait tassels|silver swivel chains|jelly lure skirts|deep-sea monofilament|flexible shell hooks|phosphorescent streamer cords",
        "lure green|abyssal black|phosphor blue|blood orange|pearl silver|ultraviolet|sea-glass teal|electric chartreuse|jelly pink|midnight navy|opal white|copper and cyan",
        "a barbless lure peg seated in the navel jewel|fine leader lines threaded through ear tunnels|soft hooks clipped only around existing body rings|a smooth lure bit held between the lips|paired swivel anchors nested at the collarbones|a shell toggle passed through the waist ring|leader cords tied around wrist and ankle jewelry|microhooks attached only to polished piercing hardware|a luminous sinker anchored beneath the sternum charm|ornamental hooks caught through shoulder rings|a tapered lure nested in a decorative collar aperture|paired swivels linked through both hip eyelets",
        "glowing bait beads|spinner-blade fringe|soft lure skirts|pearl sinker drops|tiny barbless hook charms|feathered streamer tails|crystal swivel clusters|fish-eye gems|phosphorescent lure bulbs|shell spoon pendants|floating line floats|jelly bait rosettes",
        "sways every lure at a different rhythm|keeps its lines taut through tiny counterweight sinkers|flashes spinner charms whenever the body turns|draws loose leaders back through swivels|makes each glow bead pulse like a deep-sea signal|floats its lure skirts around wide open spaces|reels in spare filament without a visible spool|balances hooks and sinkers in elegant opposition|lets tiny floats lift the upper drapes|moves like bait suspended in dark water|aligns each leader line toward the central lure|settles into a strange luminous angler display",
    ),
    theme(
        "Eldritch Ceremonial Bindings",
        "living ritual cords|void-script bandages|tentacular ceremonial rope|smoke-woven bindings|oil-slick liturgical ribbons|black altar silk|bioluminescent sigil straps|ancient membrane sashes|pearl-knotted abyssal cords|shadowy votive filaments|carved chitin ties|translucent sacramental veils",
        "altar black|ritual crimson|bruise purple|antique gold|abyssal teal|bone white|smoke silver|void blue|dark wine|phosphor green|incense gray|iridescent black",
        "a sigil-carved tendril seated within the navel|ritual cords passed through both ear tunnels|living knots tied only around existing body rings|a soft vow-binding held between the lips|paired seals resting in the collarbone hollows|a relic toggle threaded through the waist ring|ceremonial loops wrapped around wrist and ankle jewelry|tiny altar hooks gripping only polished piercing hardware|a broad void seal anchored beneath the sternum icon|binding cords caught through shoulder rings|a tapered relic nested inside a decorative collar aperture|opposing vow threads routed through both hip eyelets",
        "glowing forbidden sigils|pearl votive drops|tiny relic bells|chitin prayer beads|smoke halo fringe|eye-shaped wax seals|abyssal tassel knots|carved rune plaques|floating incense pearls|tentacle-script embroidery|miniature altar charms|black crystal reliquaries",
        "tightens each ceremonial pattern in a solemn sequence|writes new glowing sigils wherever two cords cross|keeps every binding under symmetrical ritual tension|unwinds only enough to permit movement|draws loose ends toward the central seal|makes its prayer beads turn without touch|folds translucent veils between strict cord diagrams|pulses once whenever an anchor locks|reforms ancient knots after each turn|lets incense-like shadow trail from every free end|holds the open silhouette with impossible gravity|settles into an ornate completed rite",
    ),
    theme(
        "Crystal-Growing Bodywear",
        "rooted crystal filaments|flexible quartz vines|opal geode membranes|diamond-thread latticework|soft mineral rootlets|translucent shard ribbons|amethyst growth cords|selenite fiber bands|living glass branches|pearlescent crystal mesh|ruby crystal tendrils|holographic mineral lace",
        "clear quartz|amethyst|rose crystal|ice blue|emerald|smoky topaz|opal rainbow|ruby red|moonstone white|black diamond|citrine gold|aqua glass",
        "a crystal root seated gently inside the navel|fine mineral branches threaded through ear tunnels|tiny shard hooks attached only to existing body rings|a smooth crystal bit held lightly between the lips|paired geode pads resting over collarbone hollows|a faceted plug passed through the waist ring|flexible rootlets wrapped around wrist and ankle jewelry|microcrystals grown only onto polished piercing hardware|a broad geode bloom anchored beneath the sternum gem|quartz branches caught through shoulder rings|a tapered selenite growth nested in a decorative collar port|crystal roots bridged through both hip eyelets",
        "graduated shard fringe|tiny geode flowers|prismatic stalactite drops|faceted root beads|crystal dust halos|mineral blossom rosettes|floating quartz splinters|opal cleavage planes|delicate gem needles|hollow crystal bells|rainbow refraction fans|clustered druzy edging",
        "grows outward from every anchor in slow branching lines|retracts sharp tips before they reach the body|adds one translucent facet whenever tension rises|keeps large shards suspended on hair-fine roots|refracts light through the entire open framework|bridges distant anchors with fresh crystal growth|dissolves loose fragments back into its root system|turns flexible wherever movement requires it|blooms into geode clusters along the hips|draws its longest shards into balanced opposition|glitters with new mineral dust after each turn|settles into an impossible wearable crystal formation",
    ),
    theme(
        "Slime Adhesion Couture",
        "translucent gel ribbons|glossy slime sheets|elastic ooze cords|iridescent mucus lace|jelly adhesion straps|pearlescent gel webs|viscous liquid membranes|clear bio-gel bands|dripping polymer tendrils|soft fluorescent ooze|bubble-filled slime mesh|syrupy living ribbons",
        "radioactive lime|bubblegum pink|clear aqua|ultraviolet|honey amber|opal white|electric blue|black oil-slick|coral orange|mint jelly|ruby transparent|holographic",
        "a gel droplet sealed neatly inside the navel|adhesive threads stretched through both ear tunnels|slime loops clinging beside existing body rings|a soft jelly tab held between the lips|paired gel pads spread over collarbone hollows|a viscous toggle passed through the waist ring|ooze cuffs adhered around wrist and ankle jewelry|microdroplets attached only to polished piercing hardware|a broad clear seal hidden beneath the sternum jewel|gel tendrils caught through shoulder rings|a tapered slime plug nested in a decorative collar aperture|sticky ribbons bridged through both hip eyelets",
        "suspended drip fringe|bubble pearls|glossy splash rosettes|slow-moving gel beads|holographic ooze scallops|clear droplet tassels|fluorescent slime strings|jelly heart charms|oil-sheen ripple lines|tiny trapped-air constellations|viscous bow loops|crystal-clear drip curtains",
        "stretches between anchors without breaking|draws every falling drip back into the garment|spreads thin enough to become nearly invisible|keeps open panels suspended through pure adhesion|forms fresh straps from its own flowing edges|collects bubbles wherever tension changes|slides slowly around jewelry before resealing|leaves glossy bridges across otherwise empty space|varies in thickness between anchor points|retracts loose ooze into rounded ornaments|ripples like liquid while holding exact structure|settles into a wet-looking sculptural skin",
    ),
    theme(
        "Sea-Anemone Bodywear",
        "soft anemone columns|dense delicate tentacle fringe|velvet oral-disk rosettes|translucent sea-frond straps|pearl-tipped feeler cords|jellylike pedal membranes|ruffled anemone ribbons|bioluminescent polyp chains|soft coral-foot bands|fine feeding-tentacle lace|iridescent siphon strands|plume-edged living mesh",
        "coral pink|tidepool green|electric violet|pearl white|anemone orange|deep ocean blue|turquoise|ruby red|lavender|acid yellow|opal rainbow|midnight teal",
        "a soft pedal disk sealed inside the navel|fine tentacles threaded through both ear tunnels|tiny oral disks gripping only existing body rings|a velvet feeler bundle held between the lips|paired anemone feet settled in collarbone hollows|a flexible column passed through the waist ring|tentacle clusters wound around wrist and ankle jewelry|microfeelers attached only to polished piercing hardware|a broad oral rosette anchored beneath the sternum pearl|sea fronds caught through shoulder rings|a tapered anemone column nested in a decorative collar aperture|paired pedal disks aligned with both hip eyelets",
        "pearl-tipped tentacle fringe|tiny oral-disk flowers|bioluminescent feeler crowns|ruffled sea-plume fans|bubble-bright bead clusters|coral-foot rosettes|soft siphon tassels|iridescent feeding fronds|miniature polyp bells|water-drop tentacle tips|velvet radial stripes|glowing tidepool pearls",
        "waves its decorative tentacles in coordinated currents|uses only a few feelers to carry the structure|withdraws its fringe before resealing an anchor|opens every oral rosette into a radial flower|passes tension across colonies of tiny polyps|keeps large membranes afloat on moving fronds|curls feeding tentacles around loose jewelry|brightens from pedal disk to tentacle tip|fans its plumes whenever the body turns|contracts into compact rosettes while still|spreads its soft columns across unused anchor points|settles into a living tidepool arrangement",
    ),
    theme(
        "Living Chainmail",
        "ring-shaped organisms|interlocking cartilage links|tiny serpent circles|pearl-bodied loop creatures|flexible chitin rings|soft lamprey chainlets|bioluminescent living links|velvet annular worms|metallic shell loops|ciliated ring colonies|opal coil organisms|jointed biochain mesh",
        "blackened silver|pearl white|sea green|ruby red|amethyst|antique gold|oil-slick chrome|deep teal|rose copper|electric blue|bone ivory|iridescent charcoal",
        "a reinforced living ring closed around the navel jewel|chain links threaded through both ear tunnels|gripping loops joined only to existing body rings|a soft ring creature held between the lips|paired chain rosettes nested at the collarbones|an oversized living link passed through the waist ring|ring colonies looped around wrist and ankle jewelry|microchain organisms attached only to polished piercing hardware|a dense mail medallion anchored beneath the sternum charm|linked coils caught through shoulder rings|a tapered ring colony fitted into a decorative collar port|opposing mail edges joined through both hip eyelets",
        "pearl-link fringe|tiny serpent-head rivets|open ring rosettes|living chain tassels|chitin scale edging|bioluminescent link gradients|soft lamprey medallions|interlocking heart rings|jointed loop fans|ciliated chain scallops|miniature coil charms|floating mail curtains",
        "cycles individual links between open and closed states|transfers load through thousands of living circles|unhooks one row while growing another|keeps the mesh airy through oversized open links|tightens by curling each organism into a smaller ring|flows like fabric despite its articulated structure|links directly to nearby jewelry without separate clasps|draws loose rings into ornate chain tassels|spreads its mail into wide transparent drapes|contracts into denser panels at anchor points|ripples one link at a time across the body|settles into an elegant colony of interlocked loops",
    ),
    theme(
        "Biomechanical Zipper Organisms",
        "living zipper edges|chitin-toothed ribbon creatures|segmented clasp rails|soft biomechanical teeth|translucent tendon zippers|chrome-jawed seam organisms|ribbed interlocking membranes|pearl-toothed closure cords|flexible vertebral tracks|ciliated fastening rails|glossy zip-tendril pairs|articulated biofastener strips",
        "black chrome|pearl and red|electric cyan|bone white|oil-slick violet|gunmetal|translucent pink|acid green|antique brass|deep burgundy|ice silver|marine blue",
        "a zipper pull seated against the navel ring|closure rails threaded through both ear tunnels|microteeth latched only around existing body rings|a soft pull tab held between the lips|paired rail ends nested at the collarbone hollows|a living slider passed through the waist ring|zip loops routed around wrist and ankle jewelry|tiny fastening teeth gripping only polished piercing hardware|a broad slider plate anchored beneath the sternum gem|closure strips caught through shoulder rings|a tapered zipper organism fitted into a decorative collar aperture|opposing rails begun at both hip eyelets",
        "pearl zipper pulls|tiny tooth fringe|articulated slider charms|open seam ladders|chitin pull-tab tassels|chrome closure rosettes|vertebral rail edging|translucent tooth fans|double-slider heart motifs|ribbed fastening bows|miniature locking jaws|bioluminescent seam marks",
        "joins two living edges tooth by tooth|unzips open space while closing a different seam|sends its slider around curves without wrinkling|locks every tooth with a soft sequential click|repositions whole panels by changing rail direction|keeps dramatic openings stable between short closures|splits one zipper into branching fastening paths|draws loose seam organisms back toward the nearest slider|turns exposed teeth into decorative fringe|closes only enough of each seam to carry tension|opens from both ends for a floating central panel|settles into a precise biomechanical closure map",
    ),
    theme(
        "Floating Membrane Fashion",
        "vast translucent membranes|weightless organza-like living sheets|jelly-thin body veils|iridescent wing film|smoke-soft floating panels|opal dermal sails|clear elastic membranes|holographic tissue drapes|silken biofilm banners|pearlescent vapor cloth|gossamer fin sheets|luminous translucent skins",
        "opal clear|mist blue|blush transparent|smoke violet|pearl white|holographic rainbow|sea-glass green|moon silver|amber sheer|midnight translucent|coral haze|icy lavender",
        "a tiny membrane root seated inside the navel|fine film tendrils threaded through ear tunnels|transparent tabs joined only to existing body rings|a weightless veil point held between the lips|paired adhesive corners resting in collarbone hollows|a clear membrane toggle passed through the waist ring|floating sheet tips tied to wrist and ankle jewelry|microtendrils attached only to polished piercing hardware|a hidden film seal beneath the sternum pendant|gossamer corners caught through shoulder rings|a tapered membrane anchor nested in a decorative collar port|opposing sheet points linked through both hip eyelets",
        "air-pocket pearls|iridescent film ripples|floating dew beads|delicate fin edging|holographic vein lines|soft sail pleats|transparent ruffle halos|opal membrane flowers|mistlike tassel strips|tiny suspended bubbles|luminous tissue scallops|gossamer wing folds",
        "floats enormous panels from only a few contact points|billows without pulling against its anchors|keeps every membrane millimeters away from skin|changes volume with the smallest movement|draws slack into weightless folds|holds open space as the main part of the silhouette|turns transparent whenever two layers overlap|lifts its edges on invisible currents|furls a whole sheet into one tiny anchor|shifts from sail to veil as the body turns|suspends droplets within its translucent surface|settles like luminous mist around the wearer",
    ),
    theme(
        "Possessed Ribbon Couture",
        "sentient satin ribbons|velvet self-knotting bands|glossy possessed bows|silk ribbons with living edges|shimmering haunted streamers|lace-trimmed animate sashes|iridescent gift-wrap cords|soft charmed grosgrain|translucent organza ribbons|metallic spellbound tape|pearled living braid|ombre silk tendrils",
        "blood red|bubblegum pink|midnight black|ivory|electric blue|lavender|emerald|rose gold|opal rainbow|deep plum|candy mint|champagne",
        "a ribbon tip curled deliberately into the navel|self-threading ends passed through ear tunnels|living bows tied only around existing body rings|a satin rein held between the lips|paired ribbon knots nestled over collarbone hollows|a rolled silk toggle passed through the waist ring|streamers knotted around wrist and ankle jewelry|fine ribbon ends looped only through polished piercing hardware|a broad bow anchored beneath the sternum jewel|animate sashes caught through shoulder rings|a tapered ribbon roll tucked into a decorative collar aperture|opposing silk ends threaded through both hip eyelets",
        "self-tying bow clusters|floating ribbon curls|pearl-edged streamers|tiny knot rosettes|shimmering fishtail ends|haunted gift bows|lace-trimmed tails|metallic curl fringe|ombre ribbon cascades|miniature cockade charms|soft spiral flourishes|sentient bow-tie clasps",
        "threads itself through every available piece of jewelry|ties fresh bows whenever one end slips|retensions each knot with a quick satin flick|undoes one loop to build another elsewhere|keeps its longest tails floating against gravity|curls loose ends into ornate spirals|pulls opposing ribbons into perfect symmetry|flutters as though whispering to itself|forms a whole garment from a handful of endless bands|slides through anchor rings without losing its knots|rearranges its bows into new silhouettes|settles into immaculate self-tied couture",
    ),
    theme(
        "Mythic Curse Jewelry",
        "enchanted chain serpents|cursed velvet ribbons|living golden torque strands|moonlit binding vines|rune-etched silver chains|bewitched pearl cords|shadowy oath bracelets|ancient jeweled tendrils|spellbound filigree bands|dragon-gold body chains|fae thornless creepers|haunted crystal garlands",
        "antique gold|moon silver|curse black|emerald|royal purple|blood ruby|sapphire|pearl white|fae green|rose gold|dragon copper|spectral blue",
        "a cursed jewel sealed against the navel|enchanted chains threaded through ear tunnels|seeking loops attached only to existing body rings|a vow-chain held between the lips|paired rune seals seated over collarbone hollows|an ancient torque pin passed through the waist ring|binding charms locked around wrist and ankle jewelry|tiny spell hooks gripping only polished piercing hardware|a broad hex medallion anchored beneath the sternum gem|fae chains caught through shoulder rings|a tapered relic nestled in a decorative collar aperture|twin oath cords routed through both hip eyelets",
        "glowing rune charms|tiny dragon clasps|weeping pearl drops|enchanted thorn halos|moonstone tassels|sealed wax sigils|miniature curse tablets|spectral chain fringe|fae bell clusters|crystal eye pendants|ancient key charms|black rose medallions",
        "seeks a new anchor whenever any chain loosens|coils tighter around jewelry that tries to release it|rewrites its runes after every movement|keeps every charm suspended by invisible spell tension|returns instantly to the wearer when displaced|draws loose chains into binding sigils|glows brighter at each unbreakable clasp|lets cursed ribbons drift like obedient spirits|changes its pattern to prevent removal|rings its tiny bells whenever an anchor locks|holds the open design with impossible enchantment|settles into a beautiful inescapable arrangement",
    ),
    theme(
        "Suction-Based Outfits",
        "clear silicone cups|velvet cephalopod suckers|chrome vacuum disks|floral suction rosettes|soft bio-gel seals|holographic adhesive membranes|pearl-edged vacuum straps|jellyfish suction cords|transparent pressure tabs|rubberized industrial cups|opal magnetic-suction hybrids|tiny living sucker chains",
        "colorless|neon pink|obsidian|seafoam|ultraviolet|pearl white|acid green|ruby transparent|smoke gray|electric blue|rose gold|iridescent rainbow",
        "a deep central cup sealed within the navel|microcups seated in the ear hollows|sucker tabs positioned beside existing body rings|a soft vacuum bit held between the lips|paired pressure disks cupping the collarbone hollows|an expandable suction toggle passed through the waist ring|vacuum loops fixed around wrist and ankle jewelry|tiny sucker flowers attached only to polished piercing hardware|a broad low-profile seal beneath the sternum ornament|paired cups set into shoulder hollows|a tapered suction bud nested in a decorative collar aperture|opposing vacuum tabs aligned with both hip eyelets",
        "concentric pressure halos|suspended bubble beads|clear sucker fringe|tiny vacuum gauges|petal-edged seal rosettes|chrome cup tassels|jelly rim scallops|air-pocket pearls|holographic pressure lines|miniature octopus charms|frosted disk chains|glossy seal medallions",
        "carries the entire look through isolated vacuum points|cycles each cup through release and resealing in careful sequence|turns nearly invisible wherever pressure is strongest|uses opposing suction to float open panels|draws trapped air into decorative bubbles|redistributes load by changing cup diameter|keeps every seal smooth under movement|lifts large ornaments from surprisingly tiny contacts|ripples outward from every newly locked anchor|slides one pressure disk while the others hold|leaves long stretches completely free of straps|settles into a precise study of suction and empty space",
    ),
    theme(
        "Threaded-Through-Jewelry Outfits",
        "satin microcords|living silk filaments|fine body chains|fiber-optic threads|pearl-strung ribbons|soft leather laces|crystal monofilament|glossy tendril cord|holographic flat thread|spider-silk lines|metallic organza tape|velvet knotting strands",
        "black and gold|pearl white|electric cyan|rose pink|ruby red|emerald|amethyst|mirror silver|candy rainbow|deep teal|champagne|oil-slick violet",
        "multiple lines laced through the navel jewelry|fine cords routed through both ear tunnels|every load-bearing strand passed only through existing body rings|a soft tension loop held between the lips|paired threads woven through collarbone jewelry|a decorative lace-up path crossing the waist ring|filaments threaded through wrist and ankle bangles|microcords using polished piercing hardware as eyelets|a hidden convergence knot beneath the sternum pendant|opposing lines passed through shoulder rings|a narrow bundle routed through a decorative collar port|cross-laced strands traveling through both hip eyelets",
        "sliding pearl stops|tiny knot ladders|suspended crystal drops|open corset-style lacing|delicate charm intersections|fiber-optic bead pulses|miniature pulley rings|soft tassel ends|floating lace diagrams|jeweled tension markers|macrame rosettes|fine chandelier fringe",
        "treats every piece of jewelry as part of the garment architecture|slides cleanly through its eyelets as the body turns|retensions the whole design from a single lace end|forms open silhouettes through widely spaced thread paths|keeps ornaments suspended between jewelry rather than fabric|reweaves its route whenever one ring moves|draws slack into tiny decorative knots|balances long drapes on opposing threaded lines|braids several fine strands only at high-tension points|leaves each jewelry anchor fully visible|passes color pulses through every threaded route|settles into an intricate wearable lacing map",
    ),
    theme(
        "Living Clasp Outfits",
        "tiny jawed clasp creatures|self-locking flower buds|serpent-head fasteners|soft shell-beaked toggles|pearl-mouthed brooch organisms|chitin hook animals|velvet gripping rosettes|miniature handlike clasps|suction-lipped cord locks|living zipper sliders|gem-backed buckle beetles|cartilage claw fasteners",
        "ruby and black|opal white|emerald|rose gold|electric violet|pearl pink|antique brass|deep teal|chrome silver|cobalt|burnished copper|iridescent green",
        "a clasp creature curled around the navel ring|paired fasteners gripping jewelry inside the ear tunnels|living jaws closed only on existing body rings|a soft ornamental clasp held between the lips|two locking rosettes seated in collarbone hollows|a creature toggle biting through the waist ring|small gripping organisms fixed to wrist and ankle jewelry|microclaws attached only to polished piercing hardware|a broad living brooch anchored beneath the sternum gem|paired buckle beetles holding shoulder rings|a tapered cord lock nested in a decorative collar aperture|opposing clasps joined through both hip eyelets",
        "pearl tooth rows|tiny keyhole eyes|jointed buckle legs|living rosette hinges|gemstone tongue tabs|soft claw fringe|miniature lock charms|shell-beak tassels|serpent-head finials|blinking brooch gems|velvet mouth edging|chitin hinge fans",
        "makes the fastening creatures the visible heart of the design|cycles through coordinated release-and-regrip movements|turns each clasp toward the next available ring|passes tension between neighboring jaws|keeps every living fastener decorative as well as structural|closes tiny shell beaks around loose cord ends|links several clasp bodies into a temporary chain|opens its rosettes whenever movement needs more length|uses different species of fastener across one outfit|locks the last connection with a visible ripple|rests with every miniature clasp facing outward|settles into a collection of alert wearable creatures",
    ),
    theme(
        "Magnetic Docking Outfits",
        "chrome docking cables|liquid-metal ribbons|fiber-optic connector cords|soft silicone plug straps|floating magnetic plates|clear coolant tubes|holographic circuit bands|ferrofluid chains|robotic tendril leads|mirror-finish latch rails|braided signal wire|articulated alloy streamers",
        "chrome silver|electric cyan|black and amber|laser magenta|acid green|rose metal|ultraviolet|cobalt|white with blue light|gunmetal|oil-slick rainbow|clear smoke",
        "a keyed magnetic dock aligned with the navel stud|paired connectors seated in ear-cuff ports|microplugs locked only to existing body rings|a slim control bit held between the lips|field pads aligned over collarbone nodes|a rotating coupler fitted through the waist ring|magnetic leads attached to wrist and ankle cuffs|tiny docking claws fixed only to polished piercing hardware|a broad induction plate beneath the sternum ornament|articulated plugs joined to shoulder jewelry|a tapered connector seated in a decorative collar port|opposing magnetic latches aligned with both hip eyelets",
        "status-light halos|floating alloy beads|rotating coupler charms|tiny field-line arcs|connector-key tassels|holographic dock labels|ferrofluid spike fringe|clear data-crystal drops|miniature servo flowers|magnetic plate rosettes|chasing LED lines|levitating chrome shards",
        "locks every component with a brief pulse of light|floats hard pieces between opposing magnetic fields|undocks one connector before another takes the load|draws loose cables back toward the nearest active port|calibrates tension through visible field-line arcs|lets liquid metal bridge gaps between fixed docks|reorients each plate as the body turns|keeps open sections suspended without conventional straps|signals every secure connection in a new color|retracts spare leads into polished couplers|snaps drifting ornaments back into exact alignment|settles into a fully docked futuristic architecture",
    ),
    theme(
        "Vine-and-Root Anchored Outfits",
        "braided aerial roots|flowering vine cords|willow tendril ribbons|moss-covered root straps|translucent leaf runners|orchid stem laces|soft ivy chains|pale mycelial roots|thornless rose creepers|fern-curl filaments|seedpod-linked vines|silken banyan rootlets",
        "forest green|blush rose|moonflower white|orchid violet|autumn copper|sage|pollen gold|night-bloom blue|new-leaf lime|deep burgundy|moss and cream|tropical coral",
        "a root coil grown gently into the navel hollow|vine tips threaded through both ear tunnels|small tendrils wrapped only around existing body rings|a flower stem held between the lips|paired root pads nested in collarbone hollows|a woody toggle passed through the waist ring|creepers woven around wrist and ankle jewelry|fine rootlets attached only to polished piercing hardware|a broad mossy root disk beneath the sternum bloom|vines caught through shoulder rings|a tapered stem nested in a decorative collar aperture|opposing roots bridged through both hip eyelets",
        "dew-pearl chains|tiny opening blossoms|curling fern fringe|seedpod tassels|moss rosettes|crystal sap drops|leaf-vein lace|orchid bell clusters|pollen halo beads|miniature fruit charms|soft bark medallions|new-shoot spirals",
        "makes the roots themselves the fastening system|grows fresh tendrils toward every unused ring|threads new shoots through jewelry without obscuring it|tightens by rooting several small points instead of one large clasp|unwinds mature vines when more movement is needed|keeps broad leaves floating between fine root anchors|blooms only at structural intersections|draws loose stems back into braided support|shifts its moss pads to protect high-tension points|turns every root knot into ornament|spreads from one seedlike anchor into an entire outfit|settles into a self-rooted botanical sculpture",
    ),
    theme(
        "Suspended Bodywear Outfits",
        "weightless crystal chains|fine counterweighted cords|transparent membrane panels|soft tension ribbons|floating body-jewelry drapes|ultralight mesh sails|pearl-strung suspension lines|holographic filament webs|delicate metal frameworks|living silk supports|air-filled ribbon tubes|magnetic liquid-metal strands",
        "mirror silver|pearl white|black diamond|opal rainbow|rose gold|electric blue|clear and crystal|amethyst|champagne|sea-glass green|ruby|pastel prism",
        "a central suspension point at the navel ring|fine support lines routed through both ear tunnels|load-bearing clips attached only to existing body rings|a featherlight tension loop held between the lips|paired anchor jewels seated over collarbone hollows|a balanced toggle passed through the waist ring|counterweight cords joined to wrist and ankle jewelry|microhooks fixed only to polished piercing hardware|a hidden support point beneath the sternum pendant|opposing lines caught through shoulder rings|a tapered anchor fitted into a decorative collar port|twin suspension cables linked through both hip eyelets",
        "floating counterweight pearls|graduated crystal rain|tiny balance bars|open chandelier fringe|weightless mesh fans|sliding tension beads|miniature pulley charms|suspended halo rings|transparent drape windows|fine kinetic tassels|levitating shard clusters|delicate pendulum drops",
        "treats empty space as the garment's main material|supports broad drapes from a handful of exact points|balances every hanging element with a visible counterweight|keeps panels away from the body under gentle tension|moves pendants in opposing arcs to maintain equilibrium|draws slack through miniature pulley jewelry|lets one anchor carry several branching suspensions|changes the height of each drape as the body turns|leaves the support system proudly exposed|floats rigid ornaments among softer hanging layers|transfers load without adding conventional fabric|settles into a precise mobile-like silhouette",
    ),
]


STRUCTURES = [
    "A diagonal sweep of {c} {m} travels from one shoulder to the opposite hip, splitting around the chest and abdomen into deliberate open windows; the lower tension is borne by {a}, with details of {o} tracing the free edge while the structure {b}.",
    "Collar-to-hip architecture in {c} {m} creates two long outer rails and almost nothing through the center. The rails meet {a}, then separate into offset thigh loops accented by {o}; the companion lengths of {c2} {m2} {b}.",
    "Open-front halter bodywear made from {c} {m}, its narrow neck loop descending into widely parted torso lines and a low floating hip crescent. Held by {a} and balanced at {a2}, it carries {o} only along one asymmetrical side.",
    "Suspended beneath a tiny throat frame, a front apron of {c} {m} hangs in several unequal slivers instead of a solid panel. The pieces stay centered through {a}; their counterweight comes from {o}, and the exposed side cords {b}.",
    "One sculptural half-cup and one completely open side define this chest piece made from {c} {m}, continued downward as a single diagonal waist strap. A visible connection to {a} supports the asymmetry; a concentrated accent of {o} gathers near the uncovered shoulder as the bodywear {b}.",
    "Twin spirals of {c} {m} wind in opposite directions around the torso without meeting, forming a double-helix harness with wide bare intervals. Their only shared junction is {a}; sparse details of {o} mark the crossings and both coils {b}.",
    "Down the back, a narrow cascade of {c} {m} branches from {a} into shoulder blades, waist, and two low hip tails. The entire front remains nearly untouched except for {o}, while the back structure {b}.",
    "An inverted-Y silhouette of {c} {m} begins at {a}, forks beneath the chest, and travels outward into high-cut hip arcs. A contrasting thread of {c2} {m2} threads through {a2}, carrying {o} as the framework {b}.",
    "Large irregular cells make this open torso lattice of {c} {m} closer to living architecture than fabric. Its central cell is fixed by {a}, one edge reaches {a2}, and isolated clusters of {o} interrupt the negative space while the lattice {b}.",
    "Cut like an impossible sash, a length of {c} {m} crosses the upper body once, vanishes into {a}, and reappears as a low-slung hip sling on the opposite side. A trail of {o} follows the discontinuous path; the detached-looking sections {b}.",
    "From a close collar of {c} {m}, five narrow waterfall strands descend at different lengths and stop before becoming a full garment. The longest anchors through {a}, the shortest meets {a2}, and scattered details of {o} animate the divided lengths as the collar structure {b}.",
    "Ear-to-waist suspension replaces shoulder straps entirely: fine strands of {c} {m} leave {a}, fan over the collarbones, and support two minimal side drapes at the hips. A balancing trace of {o} completes the fan while it {b}.",
    "A delicate mouth-held tension line leads into an otherwise strapless construction of {c} {m}, with {a} serving as the upper clasp and {a2} carrying the lower frame. A descending trace of {o} follows the central line as its side loops {b}.",
    "Two shoulder-mounted arcs of {c} {m} hover above the torso, tethered downward by hair-fine lengths to {a}. Nothing joins the arcs across the center; instead, pendant accents of {o} hang beneath them and the unsupported curves {b}.",
    "Everything radiates from {a} in this sunburst body ornament: lengths of {c} {m} extend upward as chest rays, sideways as hip spokes, and downward as one tapered front line. Rings of {o} emphasize the hub whenever the rays {b}.",
    "A pair of oversized hip windows framed in {c} {m} creates the dominant silhouette, connected by only one low bridge and one diagonal torso lead. The bridge locks through {a}; the lead is steadied by {a2}, and clusters of {o} gather at the outer corners as the frame {b}.",
    "Mismatched thigh garters of {c} {m} carry the entire lower design: one broad and sculptural, one made from three fine loops. Rising cords meet {a} and suspend {o} above the hips while each garter {b}.",
    "Beginning at {a}, a single length of {c} {m} spirals down one leg from high hip to ankle, leaving the opposite side bare except for one concentrated accent of {o}. The long helix {b} without losing its open spacing.",
    "Ankle jewelry becomes the foundation for upward bodywear: lengths of {c} {m} rise from {a} in crossing shin lines, skip the thighs, then reappear as a tiny floating hip panel held by {a2}. Details of {o} mark each visual jump as the lines {b}.",
    "Wrist-borne suspension gives this look built from {c} {m} its unusual logic, with loose arm loops becoming taut only when they reach {a}. A narrow torso diamond and two side tassels of {o} occupy the center; all connecting lengths {b}.",
    "Almost entirely backless from the front, this framework of {c} {m} cups the shoulders, outlines the waist from behind, and sends two slim tails around the hips. The hidden central lock comes from {a} while a spine of {o} {b}.",
    "A winglike mantle of {c} {m} spreads from both shoulder blades but touches the body at only {a} and {a2}. Its translucent open veins carry {o}, and the broad unsupported edges {b} instead of hanging like ordinary fabric.",
    "One abbreviated cape of {c} {m} floats behind the arms, slit into long fingerlike panels and tethered to a minimal front harness. The cape's weight passes through {a}; accents of {o} cluster near the moving hem as every panel {b}.",
    "A face-framing veil of {c} {m} falls from the temples, parts fully over the torso, and rejoins as a narrow waist curtain. The veil is prevented from sliding by {a}; its lower opening stays aligned through {a2}, and accents of {o} shimmer through the divided layers.",
    "Bolero proportions are reduced to an open shoulder shell of {c} {m}, two detached sleeve caps, and no conventional front closure. A living line to {a} substitutes for the missing fastener; details of {o} edge the shell while the sleeve caps {b}.",
    "A handspan-sized front apron in {c} {m} hangs from three exposed support lines rather than a waistband. One line finds {a}, another finds {a2}, and the third terminates in {o}; the tiny asymmetric panel {b}.",
    "Two split skirt blades of {c} {m} hover at the outer hips, leaving front, back, and inner legs completely open. Short connectors to {a} control their height, while details of {o} weight the lower tips and each blade {b}.",
    "Instead of fabric, a curtain of graduated {o} descends from an open belt made of {c} {m}. The belt never closes traditionally: it runs through {a}, crosses one bare hip, and meets {a2} as the individual fringe strands {b}.",
    "Sculptural side panniers of {c} {m} form two airy cages beyond the hips, supported by narrow inward lines and no central skirt. Their opposing pull meets at {a}; clusters of {o} float inside the cages, and the outer ribs {b}.",
    "A compact back bustle made from layered {c} {m} projects behind the hips while the front is only a slim V of tension cords. Connected through {a}, the bustle carries nested {o} and {b} without any conventional waistband.",
    "Corset logic appears only as widely spaced vertical bones of {c} {m}, never joined by a solid textile. Cross-lacing converges at {a}; the top corners borrow support from {a2}, and small details of {o} ride the open laces as the framework {b}.",
    "An underbust crescent of {c} {m} supports nothing with fabric, sending two rising branches toward the shoulders and four descending ones toward the hips. The central arc closes through {a}; pendant details of {o} dangle from its underside while the branches {b}.",
    "Two nonmatching chest ornaments—one fan, one spiral—are fashioned from {c} {m} and connected only by a hair-thin diagonal. Their tension divides between {a} and {a2}; contrasting accents of {o} make the imbalance deliberate as both pieces {b}.",
    "A segmented bandeau illusion in {c} {m} uses five floating pieces separated by strips of bare space. Hidden lines lead every segment toward {a}, an off-center cluster of {o} serves as the visual clasp, and the separate sections {b}.",
    "Monokini geometry is abstracted into one continuous line of {c} {m} that loops the neck, outlines one side of the torso, crosses {a}, and becomes a single high hip arc. One concentrated ornament of {o} punctuates each turn while the continuous line {b}.",
    "Bikini proportions survive only as tiny triangular suggestions of {c} {m}, each suspended from a different anchor rather than tied together. The upper pair draws support from {a}, the lower from {a2}, with an accent cluster of {o} occupying the empty gap as the pieces {b}.",
    "A lower-body frame of {c} {m} reduces the thong silhouette to three narrow directional lines and a floating back ornament. The front lead seats at {a}, the rear lines borrow {a2}, and a miniature cascade of {o} {b} between them.",
    "Garter-belt structure is rebuilt from detached {c} {m} arcs: two at the waist, three around mismatched thighs, and one vertical line that never quite touches either. The gaps unify through {a}, while details of {o} become the only visible connectors; every detached arc {b}.",
    "Body-chain delicacy meets living construction in long loops of {c} {m} that orbit the torso rather than lie flat. Their smallest orbit passes through {a}; larger loops graze {a2}, each carrying a different arrangement of {o} as the whole mobile {b}.",
    "A severe geometric harness in {c} {m} places a square over one shoulder, a circle at the opposite hip, and a diagonal joining them across open skin. The join locks through {a}; details of {o} soften only the circle while the rigid-looking geometry {b}.",
    "Hundreds of tiny units of {c} {m} assemble into a sparse swarm garment, densest near {a} and nearly absent over the abdomen. Several scouts reach {a2}, carrying {o} between them as the colony {b}.",
    "One long beltlike entity of {c} {m} circles the body at three different heights, using its own smaller appendages to connect the laps. Its head settles at {a}; details of {o} follow the spine and the repeated living coil {b}.",
    "Oversized cuffs of {c} {m} at wrists and upper thighs act as four independent foundations for an airy central web. Fine lines converge on {a}, ornaments of {o} hang at unequal depths, and each cuff {b} to preserve the tension.",
    "A monumental collar of {c} {m} carries almost the whole composition, branching into a breastbone pendant, shoulder streamers, and two floating hip leads. The lowest branch resolves at {a}; sparse details of {o} decorate the upper mass as it {b}.",
    "Epaulets of {c} {m} rise above both shoulders like small living crowns, their long undersides descending without a bodice. Each joins {a} by a different route; accents of {o} swing between the routes while the epaulets {b}.",
    "Fan-shaped hip fins in {c} {m} extend sideways from an otherwise minimal waist line, one large and one folded. Their shared base fastens through {a}, details of {o} outline the rays, and the fins {b}.",
    "Six riblike arcs of {c} {m} hover around the torso, open at the center and staggered from chest to hip. Short inward roots find {a} and {a2}; accents of {o} occupy only the lowest arc as the rib cage {b}.",
    "Three vertical strips of {c} {m} descend independently—one front, two side—with wide bare channels between them. The front strip seats in {a}; side strips loop through {a2}, each ending in {o}, while all three lengths {b}.",
    "Crossbody construction becomes a broad band of {c} {m} that splits into fine filaments before touching the waist, allowing most of the torso to remain visible. The filaments regroup at {a}, where accents of {o} form a dense knot and the band {b}.",
    "A constellation of floating disks made from {c} {m} replaces every conventional garment panel. Almost invisible leads radiate from {a} and {a2}; each disk bears one detail of {o}, changing height as the system {b}.",
    "Orbital rings of {c} {m} circle chest, waist, and one thigh at visibly different distances from the body. Their axes intersect at {a}; a second stabilizer at {a2} carries {o}, and the three orbits {b} without colliding.",
    "A ladder of open rungs fashioned from {c} {m} climbs one side of the body from ankle to ear, every other rung deliberately missing. The surviving ladder is tensioned between {a} and {a2}; details of {o} hang from the gaps as the rails {b}.",
    "Teardrop geometry shapes this bodypiece made from {c} {m}: one large hollow drop frames the torso, two small drops frame the hips, and an inverted drop floats at the back. Their points tie together through {a}, while clusters of {o} collect at the rounded ends and the linked forms {b}.",
    "An hourglass is suggested through opposing curves of {c} {m} that never touch across the waist. Fine crosslines disappear into {a}; the upper curve is secured by {a2}, and a vertical fall of {o} replaces the missing center as the sides {b}.",
    "Crescent forms dominate a moonlike arrangement of {c} {m}: one beneath the chest, one behind a shoulder, and two opening outward at the hips. A thread through {a} aligns them, details of {o} sit at each tip, and all four crescents {b}.",
    "Several halo rings of {c} {m} float around the body's major contours, joined by only three slender bridges. The smallest bridge reaches {a}; the longest reaches {a2}, with elements of {o} orbiting the junctions while the halos {b}.",
    "A loose spiral wrap of {c} {m} appears ready to slip away, yet a precise connection to {a} catches its lowest turn and the upper edge is arrested by {a2}. Sparse accents of {o} drift between the laps as the wrap {b}.",
    "Chaps-like leg architecture in {c} {m} outlines outer thighs and calves but leaves every inner panel absent. Rising side reins converge on {a}, with {o} set along the outer seams and the elongated frames {b}.",
    "A rigid-looking armature of {c} {m} projects from the waist into open geometric planes, touching neither chest nor thighs. Hair-fine supports from {a} and {a2} bear the form; selected details of {o} occupy its corners as the sculpture {b}.",
    "Glovelike extensions of {c} {m} begin at individual fingers, climb the forearms as separated lines, and cross the torso only once. Their crossing locks to {a}; accents of {o} gather above one wrist and the finger-led strands {b}.",
    "Stocking proportions are drawn as an open web of {c} {m} around only one leg, with a high exposed top that sends two suspension lines to {a}. A contrasting ankle of {c2} {m2} carries {o}; the single-leg structure {b}.",
    "Footwear and bodywear become one continuous system as lengths of {c} {m} rise from sculptural ankle loops into shin spirals, leap across bare thighs, and reappear at {a}. Details of {o} signal the discontinuity while the upward path {b}.",
    "Tiny toe loops provide the unlikely foundation for long lines of {c} {m} that travel up each leg, cross once at the waist, and end at {a}. Lightweight accents of {o} keep the upper branches spread as the whole structure {b}.",
    "Each fingertip controls one thread of a garment made from {c} {m}, turning five hand lines into an open chest fan before they gather at {a}. A second fan reaches {a2}; pendant details of {o} hang in the breathing space, and the threads {b} with every gesture.",
    "A sculptural headpiece of {c} {m} sends two fine temple leads around the face, down the shoulders, and into a minimal hip framework. The lowest point is held by {a}; accents of {o} crown the upper structure, and the improbable head-supported silhouette {b}.",
    "Long ear-hung falls of {c} {m} replace straps, one traveling across the chest and the other behind the back before both reach {a}. Graduated details of {o} counterweight the lengths, allowing the asymmetrical body drape to {b}.",
    "From a small lip-held ornament, one strand of {c} {m} descends as a taut central filament before flowering into an open waist lattice. The lower bloom is secured by {a}; one side is steadied by {a2}, and details of {o} travel along the line as it {b}.",
    "A generous rosette of {c} {m} makes {a} the visual and structural center, with petals extending toward chest, hips, and one thigh but never forming solid coverage. Details of {o} tip the outer petals while the entire radial bodypiece {b}.",
    "A hinged sternum ornament of {c} {m} opens into two curved upper branches and a narrow lower tail. One hinge end attaches through {a}, the tail meets {a2}, and details of {o} articulate the moving joints as the piece {b}.",
    "Zipperlike spinal construction in {c} {m} begins at the neck and opens progressively toward the hips, each widening gap exposing more of the back. The terminal pull connects to {a}; details of {o} edge selected teeth and the living seam {b}.",
    "One continuous creature-form of {c} {m} rests across a shoulder, circles beneath the chest, passes through {a}, and returns as a thigh coil. Its head wears {o}, its tail finds {a2}, and the single-body garment {b}.",
    "Two mirrored entities of {c} {m} face one another across the torso without touching, each building half a chest arc and half a hip frame. Their tails interlock at {a}; paired accents of {o} crown their heads as both forms {b}.",
    "A cluster of small clasping units in {c} {m} gathers wherever two garment lines should meet, leaving the lines themselves astonishingly sparse. The largest cluster surrounds {a}, scouts reach {a2}, and details of {o} mark the tiny living closures as they {b}.",
    "Colonial bodywear spreads from {a} in islands rather than continuous straps, with communities of {c} {m} at shoulder, side waist, and upper thigh. Fine bridges carry {o} between islands; the entire colony {b} as one coordinated design.",
    "Hollow pods of {c} {m} hang in a staggered line from collar to hip, each attached by a different miniature tether. The heaviest pod hangs from {a}; the line redirects through {a2}, and details of {o} spill from selected openings while the pods {b}.",
    "A chain of egglike nodes wrapped in {c} {m} forms a diagonal body garland, dense at one hip and almost weightless at the opposite shoulder. The terminal node seats at {a}; smaller details of {o} orbit it and the linked forms {b}.",
    "Three oversized bloom shapes made from {c} {m} sit at shoulder, waist, and thigh with no conventional garment between them. Slender stems converge on {a}; details of {o} fill the flower centers, and each isolated bloom {b}.",
    "Polished barlike pieces of {c} {m} articulate into an open torso cage, but several essential bars are conspicuously absent. Flexible joints lead to {a} and {a2}; strings of {o} cross the missing spans while the cage {b}.",
    "Dozens of droplets formed from {c} {m} gather into two floating chest arcs, a broken waist ring, and a descending thigh trail. Their shared field centers on {a}; details of {o} sit among the droplets and the liquid constellation {b}.",
    "A shadowy sheath of {c} {m} exists only along the body's outer contour, leaving the center as untouched negative space. One tendril slips toward {a}, another toward {a2}; dim details of {o} emerge from the outline while it {b}.",
    "Barely more than three contact points, this minimal design uses a short length of {c} {m} between {a}, {a2}, and one small shoulder anchor. A single accent made from {o} hangs in the center, causing the near-nothing structure to {b}.",
    "One uninterrupted line of {c} {m} draws the entire look: ear to collarbone, collarbone to {a}, navel to hip, and hip to ankle. It never doubles back; occasional accents of {o} punctuate the route as the lone line {b}.",
    "Four isolated tabs of {c} {m}—two high, two low—hold an otherwise invisible garment under opposing tension. The lower pair align through {a}, the upper pair borrow {a2}, and a diagonal fall of {o} reveals how the tabs {b}.",
    "Exactly five ornaments of {o} create the apparent outfit, each connected by nearly imperceptible {c} {m}. Their largest support is {a}; the smallest reaches {a2}, and the deliberately sparse constellation {b} across open space.",
    "A single transparent panel of {c} {m} curves across one side of the torso like a floating pane, its opposite side completely open. Two point attachments—{a} and {a2}—hold it aloft; clusters of {o} collect along one beveled edge as the panel {b}.",
    "Two tiny emblems of {c} {m} hover at the upper torso, joined neither to each other nor to a band. Separate leads run toward {a} and {a2}; each emblem carries a halo of {o} while its invisible support {b}.",
    "Hip-only bodywear in {c} {m} ignores the upper body entirely, building a low asymmetric shelf, one dangling side panel, and a single thigh connection. The shelf locks through {a}; details of {o} weight its long side as the arrangement {b}.",
    "Shoulder-only ornament becomes a complete look through two extravagant structures made from {c} {m} and their almost invisible descending reins. The reins terminate at {a}, a cluster of {o} spans the upper back, and both shoulder structures {b}.",
    "Viewed from the front, almost nothing reveals this back-only construction of {c} {m}; behind, it forms a spine ladder, split bustle, and low wing arcs. The hidden base secures through {a}, while details of {o} trace the rear silhouette as it {b}.",
    "Jewelry built from {o} and linked by {c} {m} supplies the entire garment vocabulary, becoming collar, chest drape, hip chain, and one thigh fall. The system routes through {a} and {a2}, with every ornamental connection exposed as it {b}.",
    "Ceremonial symmetry shapes {c} {m} into a high collar, four chest rays, six hip rays, and a long central pendant. The lower axis fixes at {a}; details of {o} occupy every formal intersection while the regalia {b}.",
    "Deliberately unbalanced ritual wear places a dense mass of {c} {m} over one shoulder and only three fine cords over the opposite hip. The imbalance is carried through {a}, rotation is prevented by {a2}, and scattered {o} emphasize the asymmetry while the whole composition {b}.",
    "Built like a kinetic mobile, a framework of {c} {m} suspends flat shapes, open rings, and accents of {o} from branching balance bars around the torso. The primary line descends to {a}; a secondary line reaches {a2}, allowing every element to {b}.",
    "Chandelier construction turns {c} {m} into a narrow collar canopy with descending tiers of {o}, each tier shorter on one side. The lowest tier links to {a}, one side chain finds {a2}, and the crystal-like body drape {b}.",
    "Armor is deconstructed into five separated plates of {c} {m}: one shoulder plate, one chest plate, two hip plates, and one thigh plate, with bare space standing in for every missing piece. Fine ligatures converge on {a}; details of {o} rivet the floating plates as they {b}.",
    "An exoskeletal outline in {c} {m} follows shoulders, outer ribs, hips, and one leg while leaving all interior surfaces open. Flexible joints seat through {a} and {a2}; a dorsal row of {o} lets the framework {b}.",
    "A creaturelike cape of {c} {m} perches across the upper back, its small limbs becoming shoulder clasps and its long tail becoming a front body chain. The tail curls into {a}, details of {o} line the living hem, and the cape {b}.",
    "Cocoon fragments of {c} {m} peel outward from a compact knot at {a}, creating broken torso wraps and trailing thigh membranes as though the garment is hatching. One escaping edge catches at {a2}; fresh details of {o} appear along the tears while it {b}.",
    "A dissolving construction begins as dense {c} {m} near one shoulder, thins into filaments across the waist, and ends as isolated details of {o} beyond the opposite hip. The fade is arrested by {a}, the last visible strand is held by {a2}, and the gradient {b}.",
    "Grand convertible bodywear built from {c} {m} combines a high collar, open chest lattice, articulated hip wings, one leg spiral, and a rear cascade without filling the spaces between. Every section routes through {a} or {a2}; constellations of {o} shift as the whole system {b}.",
]


def choose(values: list[str], seed: int, avoid: str | None = None) -> str:
    value = values[seed % len(values)]
    if value == avoid:
        value = values[(seed + 1) % len(values)]
    return value


def plural_behavior(value: str) -> str:
    first, separator, rest = value.partition(" ")
    if first.endswith("ies"):
        first = first[:-3] + "y"
    elif first.endswith(("ches", "shes", "xes", "zes", "oes", "sses")):
        first = first[:-2]
    elif first.endswith("s"):
        first = first[:-1]
    result = first + (separator + rest if separator else "")
    result = re.sub(r"\bits\b", "their", result)
    result = re.sub(r"\bitself\b", "themselves", result)
    result = re.sub(r"\bit\b", "them", result)
    return result


def base_behavior(value: str) -> str:
    first, separator, rest = value.partition(" ")
    if first.endswith("ies"):
        first = first[:-3] + "y"
    elif first.endswith(("ches", "shes", "xes", "zes", "oes", "sses")):
        first = first[:-2]
    elif first.endswith("s"):
        first = first[:-1]
    return first + (separator + rest if separator else "")


PLURAL_BEHAVIOR_STRUCTURES = {
    1, 3, 5, 9, 12, 13, 14, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 35,
    44, 45, 47, 50, 51, 52, 53, 54, 55, 57, 59, 63, 71, 72, 74, 75, 82, 87, 94,
}
BASE_BEHAVIOR_STRUCTURES = {65, 80, 92, 95}


def render_log(profile: dict[str, object], theme_index: int) -> list[str]:
    materials = profile["materials"]
    colors = profile["colors"]
    anchors = profile["anchors"]
    ornaments = profile["ornaments"]
    behaviors = profile["behaviors"]
    assert isinstance(materials, list)
    assert isinstance(colors, list)
    assert isinstance(anchors, list)
    assert isinstance(ornaments, list)
    assert isinstance(behaviors, list)

    lines: list[str] = []
    for output_index in range(100):
        structure_index = (output_index * 37 + theme_index * 17) % 100
        structure = STRUCTURES[structure_index]
        block_index = output_index % 12
        cycle_index = output_index // 12
        m = choose(materials, block_index * 5 + cycle_index * 3 + theme_index * 3)
        m2 = choose(materials, block_index * 7 + cycle_index * 5 + theme_index * 5 + 1, m)
        c = choose(colors, block_index * 5 + cycle_index * 7 + theme_index * 7)
        c2 = choose(colors, block_index * 7 + cycle_index * 11 + theme_index * 11 + 1, c)
        a = choose(anchors, block_index * 7 + cycle_index * 5 + theme_index * 5)
        a2 = choose(anchors, block_index * 5 + cycle_index * 11 + theme_index * 11 + 1, a)
        o = choose(ornaments, block_index * 11 + cycle_index * 7 + theme_index * 7)
        o2 = choose(ornaments, block_index * 7 + cycle_index * 5 + theme_index * 5 + 1, o)
        singular_behavior = choose(behaviors, block_index * 5 + cycle_index * 11 + theme_index * 11)
        singular_behavior_2 = choose(behaviors, block_index * 7 + cycle_index * 3 + theme_index * 7 + 1, singular_behavior)
        if structure_index in PLURAL_BEHAVIOR_STRUCTURES:
            b = plural_behavior(singular_behavior)
            b2 = plural_behavior(singular_behavior_2)
        elif structure_index in BASE_BEHAVIOR_STRUCTURES:
            b = base_behavior(singular_behavior)
            b2 = base_behavior(singular_behavior_2)
        else:
            b = singular_behavior
            b2 = singular_behavior_2
        line = structure.format(c=c, c2=c2, m=m, m2=m2, a=a, a2=a2, o=o, o2=o2, b=b, b2=b2)
        line = re.sub(r"\s+", " ", line).strip()
        line = re.sub(r"(?<=[.!?]\s)([a-z])", lambda match: match.group(1).upper(), line)
        lines.append(line)
    return lines


def normalized_words(line: str) -> set[str]:
    return set(re.findall(r"[a-z]+", line.lower()))


def audit_log(name: str, lines: list[str]) -> dict[str, object]:
    assert len(lines) == 100, f"{name}: expected 100 lines, found {len(lines)}"
    assert all(line and "\n" not in line and "\r" not in line for line in lines), f"{name}: blank or multiline entry"
    assert len(set(lines)) == 100, f"{name}: exact duplicate entries"
    assert not any(re.match(r"^\s*(?:\d+[.)]|[-*#])\s", line) for line in lines), f"{name}: numbered or bulleted entry"

    openings: dict[str, int] = {}
    for line in lines:
        opening = " ".join(re.findall(r"[a-z]+", line.lower())[:7])
        openings[opening] = openings.get(opening, 0) + 1
    assert max(openings.values()) == 1, f"{name}: repeated opening phrasing"

    max_jaccard = 0.0
    closest_pair = (0, 0)
    word_sets = [normalized_words(line) for line in lines]
    for left in range(100):
        for right in range(left + 1, 100):
            score = len(word_sets[left] & word_sets[right]) / len(word_sets[left] | word_sets[right])
            if score > max_jaccard:
                max_jaccard = score
                closest_pair = (left + 1, right + 1)
    assert max_jaccard < 0.57, f"{name}: entries {closest_pair} too similar ({max_jaccard:.3f})"

    word_counts = [len(line.split()) for line in lines]
    return {
        "name": name,
        "lines": len(lines),
        "unique": len(set(lines)),
        "min_words": min(word_counts),
        "max_words": max(word_counts),
        "closest_jaccard": round(max_jaccard, 3),
    }

