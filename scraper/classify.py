"""Assign a spirit type to a product from its name.

Neither the NC price list nor Wake's inventory search carries a category,
so this uses keywords in the name first, then a list of well-known brands
whose names don't say what they are. Anything unmatched becomes "Other";
the scraper writes those names to data/unclassified.txt so the lists below
can be tuned.
"""
import re

TYPES = ["Whiskey", "Vodka", "Gin", "Rum", "Tequila", "Brandy", "Liqueur", "Cocktails", "Other"]

# Checked in order; first match wins. Canned cocktails come first (4/6/8-packs,
# RTD brands), then liqueurs so "Bourbon Cream" lands in Liqueur, then strong
# whiskey words, then the other spirits, then weak whiskey markers last.
# 10/12-packs are usually 50 ml minis, so only 4/6/8-packs count as cocktails.
KEYWORDS = [
    ("Cocktails", r"\brtd\b|\b[468]\s*pk\b|\bvariety\b|\bseltzer\b|\btallboy\b|\bsingle can\b|\b19\.2\s*oz\b|\bhigh noon\b|\bsurfside\b|\bbuzzballz\b|\bcutwater\b|\bon the rocks\b|\bsun cruiser\b|^-196\b|\bloud lemon\b|\bspritz\b|\bsuper lyte\b|\bxxi martinis\b|\bnutrl\b|\bnütrl\b|\bcanned cocktail|\bready to drink\b|\blong island iced tea\b|\bmargarita\b|\bwhite russian\b|\bpina colada\b|\bmudslide\b|\bmartini\b|\bold fashioned\b|\bchi chi's\b|\bskinnygirl\b"),
    ("Liqueur", r"\bliqueur|\bliq\.|\btequila rose\b|\bcream\b|\bschnapps\b|triple sec|\bamaretto\b|\bcordial\b|\bcreme de\b|\bcrème\b|\bsambuca\b|\banisette\b|\bouzo\b|\bvermouth\b|\bbitters\b|\bamaro\b|\baperitivo?\b|\blimoncello\b|\brock\s*&\s*rye\b|\bcoffee\b|\bcafe\b|\bcaffe\b|\babsinthe\b|\bcuracao\b|\bnocino\b|\bnog\b|\bmalort\b|\bsalted caramel\b|\bpeanut butter\b|\bcreme\b|\bespresso\b|\bcold brew\b|\brompope\b"),
    ("Whiskey", r"\bwhiske?y\b|\bwhky\b|\bwsk\b|\bbourbon\b|\bscotch\b|\bsingle malt\b"),
    ("Tequila", r"\bteq\b|\bagave\b|\btequila\b|\bmezcal\b|\bsotol\b|\breposado\b|\banejo\b|\bañejo\b|\bblanco\b|\bplata\b|\braicilla\b"),
    ("Gin", r"\bgin\b|\bgenever\b"),
    ("Vodka", r"\bvodka\b|\bvodca\b"),
    ("Rum", r"\brum\b|\brhum\b|\bcachaca\b|\bcachaça\b|\brum\s*cream\b"),
    ("Brandy", r"\bbrandy\b|\bcognac\b|\barmagnac\b|\bcalvados\b|\bpisco\b|\bgrappa\b|\bv\.?s\.?o\.?p\b|\bx\.?o\b|\bapple\s*jack\b|\bapplejack\b"),
    ("Whiskey", r"\bwhiske?y\b|\bbourbon\b|\brye\b|\bscotch\b|\bsingle malt\b|\bmalt\b|\btennessee\b|\bsour mash\b|\bblended\b|\bmoonshine\b|\bshine\b|\bcorn\b|\bsingle barrel\b|\bbottled in bond\b|\bbib\b|\bbtb\b|\bs\.m\.|\bfull proof\b|\bbarrel proof\b|\bcask strength\b|\bsmall batch\b|\bwheated\b|\bstraight\b|\bpot still\b|\bwsk\b|\bcanadian\b"),
]

BRANDS = {
    "Whiskey": [
        "maker's mark", "makers mark", "jack daniel", "jim beam", "crown royal", "jameson", "buffalo trace",
        "wild turkey", "woodford", "bulleit", "evan williams", "elijah craig", "four roses", "knob creek",
        "basil hayden", "old forester", "eagle rare", "weller", "blanton", "pappy", "van winkle", "macallan",
        "glenlivet", "glenfiddich", "glenmorangie", "johnnie walker", "dewar", "lagavulin", "laphroaig",
        "talisker", "oban", "balvenie", "ardbeg", "hibiki", "toki", "nikka", "yamazaki", "hakushu",
        "whistlepig", "whistle pig", "angel's envy", "angels envy", "larceny", "heaven hill", "1792",
        "old grand-dad", "old grand dad", "seagram's 7", "seagrams 7", "canadian club", "black velvet",
        "pendleton", "skrewball", "e.h. taylor", "eh taylor", "stagg", "michter", "high west", "redemption",
        "old overholt", "rittenhouse", "sazerac", "george dickel", "uncle nearest", "jefferson's", "jeffersons",
        "booker's", "bookers", "baker's", "bakers", "old crow", "ancient age", "benchmark", "fighting cock",
        "old fitzgerald", "very old barton", "kentucky gentleman", "early times", "ezra brooks", "rebel",
        "wild turkey", "russell's reserve", "russells reserve", "bushmills", "tullamore", "redbreast",
        "powers", "teeling", "chivas", "monkey shoulder", "famous grouse", "j&b", "cutty sark", "clan macgregor",
        "lord calvert", "kessler", "fireball cinnamon whisky", "proper no", "proper twelve", "tincup",
        "sweet tea", "ole smoky", "midnight moon", "junior johnson", "southern star", "old forester",
        "penelope", "hardin's creek", "yellowstone", "rare character", "little book", "compass box",
        "glendronach", "bruichladdich", "bowmore", "aberfeldy", "remus", "king of kentucky", "parker's heritage",
        "blood oath", "orphan barrel", "templeton", "sagamore", "barrell", "rabbit hole", "old ezra", "fiddler",
        "frank august", "2xo", "joseph magnus", "pinhook", "chicken cock", "green river", "blade & bow",
        "old soul", "old hillside", "calumet", "doc holliday", "traveller", "holladay", "boann", "blue note",
        "old cassidy", "commanders club", "jimmy red", "jd mclaren", "glen ", "highland park", "springbank",
        "kilchoman", "bunnahabhain", "caol ila", "dalmore", "dalwhinnie", "deanston", "tomatin", "aberlour",
        "craigellachie", "jura", "old pulteney", "auchentoshan", "benriach", "knappogue", "slane", "writers' tears",
        "green spot", "yellow spot", "midleton", "kilbeggan", "connemara", "stranahan", "westland", "balcones",
        "garrison brothers", "smooth ambler", "willett", "noah's mill", "rowan's creek", "old rip", "w.l. weller",
        "elmer t", "rock hill farms", "hancock", "old charter", "colonel", "jack daniels", "gentleman jack",
        "heaven's door", "bardstown", "new riff", "wilderness trail", "peerless", "starlight", "bib & tucker",
        "belle meade", "nelson", "uncle nearest", "jefferson", "kentucky owl", "bomberger", "old elk",
        "troy & sons", "muddy river", "tim smith", "jb rader", "two trees", "holman", "defiant",
        "blue run", "brother's bond", "cooper's craft", "coopers craft", "eagle rare", "e.h.", "sweetens cove",
        "widow jane", "hudson", "ironroot", "high n' wicked", "o.k.i", "oki", "russell's", "wyoming whiskey",
        "j.w. dant", "jw dant", "j.t.s. brown", "henry mckenna", "old bardstown", "very old barton", "mellow corn",
        "pikesville", "ri1", "ri 1", "lot 40", "pike creek", "j.p. wiser", "jp wiser", "forty creek", "seagram's vo",
        "windsor", "canadian mist", "black bush", "proper no. twelve", "fistful of bourbon", "buchanan",
        "grand old parr", "j. walker", "jw black", "dewars",
        "ballantine", "black & white", "bowman's virginia", "isaac bowman", "caribou crossing", "classic 12",
        "crawford's", "dickel", "duggan's dew", "georgia moon", "grant's", "highland mist", "hochstadter",
        "i.w. harper", "iw harper", "inver house", "j & b", "johnny drum", "lismore", "lock stock & barrel",
        "old parr", "old smuggler", "old taylor", "paddy", "rich & rare", "roe & co", "scoresby", "singleton",
        "ten high", "travelers club", "wiser's", "bernheim", "amador", "bird dog",
    ],
    "Vodka": [
        "tito", "smirnoff", "absolut", "ketel one", "grey goose", "svedka", "deep eddy", "pinnacle",
        "burnett", "belvedere", "stolichnaya", "stoli", "ciroc", "new amsterdam", "skyy", "three olives",
        "western son", "kirov", "taaka", "aristocrat", "platinum 7x", "sobieski", "chopin", "luksusowa",
        "reyka", "chateau", "crystal palace", "highclere", "vladimir", "finlandia", "van gogh", "pearl",
        "effen", "crystal head", "barton vodka", "wodka", "dixie", "hangar 1", "cathead",
        "crown russe", "nikolai", "popov", "relska", "skol", "rain cucumber", "rain mango", "rain vodka",
        "fleischmann's royal", "gilbey's 80", "seagram's extra smooth",
    ],
    "Gin": [
        "tanqueray", "hendrick", "beefeater", "bombay", "gordon's", "gordons", "aviation", "the botanist",
        "monkey 47", "roku", "sipsmith", "plymouth", "seagram's extra dry", "seagrams extra dry",
        "broker's", "fleischmann's dry", "gilbey's london dry", "gray whale", "violet fog", "seagram's lime",
    ],
    "Rum": [
        "bacardi", "captain morgan", "malibu", "sailor jerry", "kraken", "mount gay", "appleton",
        "diplomatico", "gosling", "myers", "cruzan", "don q", "capt. morgan", "capt morgan", "mt. gay",
        "bacoo", "rumhaven", "kirk and sweeney", "ronrico", "pusser", "montego bay", "wray & nephew", "brugal",
        "barbarossa", "bumbu", "papa's pilar", "pilar", "ten to one", "probitas", "smith & cross", "plantation", "flor de cana", "el dorado",
        "ron zacapa", "havana club", "rumchata", "blue chair bay", "admiral nelson", "parrot bay", "castillo",
    ],
    "Tequila": [
        "patron", "patrón", "casamigos", "don julio", "espolon", "espolòn", "jose cuervo", "1800", "hornitos",
        "sauza", "herradura", "clase azul", "teremana", "lunazul", "olmeca", "milagro", "cazadores",
        "el jimador", "camarena", "corralejo", "avion", "casa noble", "21 seeds", "corzo", "818",
        "lalo", "dos hombres", "del maguey", "montelobos", "400 conejos", "margaritaville", "el toro",
        "juarez", "montezuma", "two fingers", "don ramon", "mi cosecha", "d'ego", "maestro dobel", "dobel",
        "lobos 1707", "gran coramino", "codigo 1530", "cantera negra", "ilegal", "blue shark", "jose  cuervo",
        "cuervo", "tres generaciones", "gran centenario", "hussong", "kirkland tequila", "la gritona",
    ],
    "Brandy": [
        "hennessy", "courvoisier", "remy martin", "rémy martin", "martell", "e&j", "e & j", "christian brothers",
        "paul masson", "korbel", "presidente", "laird", "st-remy", "st remy", "d'usse", "dusse", "pierre ferrand",
        "meukow", "ansac", "remy v", "torres", "camus", "hine", "salignac", "raynal",
    ],
    "Liqueur": [
        "kahlua", "kahlúa", "baileys", "bailey's", "cointreau", "aperol", "campari", "disaronno", "frangelico", "chambord",
        "grand marnier", "st-germain", "st germain", "southern comfort", "jagermeister", "jägermeister",
        "rumple minze", "dr. mcgillicuddy", "dr mcgillicuddy", "hpnotiq", "fireball", "tuaca", "galliano",
        "drambuie", "chartreuse", "benedictine", "midori", "pama", "licor 43", "goldschlager", "rumpleminze",
        "99 brand", "mr. boston", "mr boston", "dekuyper", "de kuyper", "bols", "hiram walker", "kinky",
        "x-rated", "tia maria", "mozart", "carolans", "rumchata", "screwball peanut butter", "pucker",
        "jeremiah weed", "fernet", "averna", "montenegro", "cynar", "lillet", "pimm", "st. elder", "luxardo",
        "irish mist", "agavero", "patron citronge", "watershed", "ole smoky salted caramel", "99 ", "twenty grand",
        "barenjager", "bärenjäger", "b & b", "domaine de canton", "giffard", "kamora", "kapali", "shanky's",
        "melone", "sarti", "arrow ", "faccia brutto", "sunshine punch", "travis hasse", "bitter tooth",
        "mohawk butterscotch", "e m walton", "twisted shotz",
    ],
}

_kw = [(t, re.compile(p, re.I)) for t, p in KEYWORDS]
_brands = sorted(((b, t) for t, bs in BRANDS.items() for b in bs), key=lambda x: -len(x[0]))


def classify(name: str) -> str:
    n = name.lower().replace("’", "'")
    for t, rx in _kw:
        if rx.search(n):
            return t
    for b, t in _brands:
        if b in n:
            return t
    return "Other"
