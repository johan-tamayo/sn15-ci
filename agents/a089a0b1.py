"""A shopping agent for the ORO store worlds, forked from CHIDORI v11 (public 2026-11-12 03:19 UTC), the race-21 and
race-22 winner. CHIDORI's design and code are kept where they are unchanged; our own logic is added on top of it.
Every model call goes to a Claude model.
"""
import json
import random
import re
import time
from typing import Any

from src.agent.proxy_client import ProxyClient

LIGHT = "anthropic/claude-haiku-5.5"
HEAVY = "anthropic/claude-sonnet-5.5"
SPARE = "anthropic/claude-haiku-4.5"

TURN_CAP = 42
CALL_CAP = 60
SOFT = 0.055
HARD = 0.078
HEAVY_ROOM = 0.02
BRIEF_DEADLINE = 120
OUTAGE_PAUSE = 10
OUTAGE_CUTOFF = 150
WAITS = (4, 10, 20, 35)
WAIT_BUDGET = 45

EPISODE_LEN = 300
MARGIN = 20
CALL_FLOOR = 6
INTERVIEW_DEADLINE = 165
LATE_Q_DEADLINE = 190
WIND_DOWN = 200
HUNT_DEADLINE = 200
HUNT_GRACE = 25
QUESTION_DEADLINE = 210
LAST_TURN = 255
EMPTY_CART_ROOM = 12

STORE_GAP = 0.25
OPENING_GAP = 0.5
ROW_CLIP = 450
TEXT_CLIP = 3000
OBS_CAP = 15000
HISTORY_CAP = 150000
PAGE_ATTR_CLIP = 700
PAGE_REST_CLIP = 300
TITLE_LIMIT = 200
KEY_TABLE_SIZE = 18
CRASH_RETRIES = 3

OPEN_MIN_STEPS = 20
OPEN_MIN_ITEMS = 2
LATER_STEPS_PER_ITEM = 2
ROWS_PER_ITEM = 6
WIDEN_SHARE = 5
OPENING_ROWS = 5

SHORTER_RESERVE = 8
WIDEN_PER_ITEM = 6
AUTO_PAGES = 6
HUNT_CAP = 24
HUNT_RESERVE = 10
HUNT_ROUNDS = 2
HUNT_IDLE = 4
HUNT_YIELD = 5
HUNT_WHOLE = 49
HUNT_VALUE_LEN = 30
HUNT_SHARE = 0.6
FIT_WORDS = 4
FIT_OPENS = 4
FIT_PAGES = 2
CHEAPER_SHOWN = 4
CHEAPER_OPENED = 3
VALUE_ROOM = 12
VALUE_RESERVE = 8
LIMIT_CHANCE = 0.05
WALK_RESERVE = 10
WALK_PER_LINE = 4
FLOOR_PAGES = 4
FLOOR_PROBES = 5
FLOOR_START = 8
FLOOR_KEEP = 5

ASK_TURNS = 2
LIST_ONE = 12
LIST_MANY = 8
RAMP_ONE = (1, 1, 3)
RAMP_MANY = (3, 3)
MIX_LABELS = 3
LOOKALIKES = 2
QUIET_LEN = 4
GUARD_KEYS = 3
GUARD_SHARE = 0.0
GUARD_GAP = 0.34

GATE_ROUNDS = 3
TRAIL_ROOM = 15
EARLY_ROUNDS = 6
DIRECTOR_CAP = 8000
CHAIN_SEARCHES = 6
EARLY_OPENS = 12
LOW_EFFORT_CLOCK = 90
CLOSEST_CLOCK = 215
BIG_STEP_LINE = 60
BIG_OPENS = 2
BIG_SPARE = 20
PINNED_SERIES = 2
SERIES_PAGES = 6
VS_SWEEPS = 2
VS_PAGES = 2
SWEEP_MIN = 7
SWEEP_MAX = 48
SWEEP_KEEP = 6
LAST_PAGE_ROOM = 6
END_READS = 2
END_ROOM = 14
DEAR_SHARE = 2.0 / 3.0
DEAR_ROOM = 12
SOLD_PEERS = 2
LABEL_SHARE = 0.4
HUNT_CHOICES = 3
SETS_SHOWN = 2
LINK_SEARCHES = 3
LINK_ROWS = 3
LINK_FAMILIES = 12
REC_MIN = 3
NOTE_MIN = 5
FIELD_SHARE = 0.15
PAIR_SHARE = 0.7
BLOCK_NAME = 60
BLOCK_VALUE = 40
TAG_LIMIT = 20000

V1_MSG = re.compile(r"(?:^|_)(?:text|texts|body|message|messages|note|notes|content|contents|question|questions|msg|say)(?:_|$)", re.I)
V2_NOTMSG = re.compile(r"(?:^|_)(?:id|ids|type|format|code|lang|language|kind)$", re.I)
V3_OPENX = re.compile(r"\b(?:not|no|other than|unlike|at most|at least|under|over|below|above|less|more|between|within|up to|or|same|listing)\b", re.I)
V4_WHOLE = re.compile(r"(?:no|none|false|0|n)", re.I)
V4_PART = re.compile(r"out[ _-]?of[ _-]?stock|sold[ _-]?out|unavailable|not[ _-]?available", re.I)
V5_HOWASK = re.compile(r"\b(?:one|each|single|first|once|several|many|much|all|lot|too|list|separate\w*|split|short\w*|time|turn|question|questions|ask\w*)\b", re.I)
V6_MAX = re.compile(r"(?:^|_)(?:cap|max|maximum|ceiling|under|up_to|upto)(?:_|$)", re.I)
V7_NONPRICE = re.compile(r"result|row|page|count|size|num|item|step", re.I)
V8_PRICE = re.compile(r"price|cost|budget|spend|money|amount", re.I)
V9_LOW = re.compile(r"(?:^|_)(?:min|minimum|low|lowest|least|from|start|offset|floor)(?:_|$)", re.I)
V10_SHELF = re.compile(r"section|department|categor|label|shelf|aisle|(?:^group|(?<!age)_group)(?:_name|_label)?$", re.I)
V11_LISTMODE = re.compile(r"field|filter|facet|brows|categor|list|structured", re.I)
V12_AMOUNT = r"\d[\d.,]*\s*[A-Za-z\"']{1,12}"
V12 = re.compile(V12_AMOUNT)
V13_FLOOR = re.compile(r"\b(?:at least|no less than|no fewer than|min|minimum)\b\s+(" + V12_AMOUNT + r")\s*$", re.I)
V14_QUERY = re.compile(r"(?:^|_)(?:q|query|search|text|phrase|keyword|keywords|term|terms|word|words)(?:_|$)|query|phrase|keyword", re.I)
V15_NONPROP = re.compile(r"\b(?:option|options|variant|variants|model|models|sku|id|ids|code|codes|asin|upc|ean|barcode|barcodes|warrant\w*|video|url|link|links|image|images|photo|photos|condition)\b")
V16_KINDS = re.compile(r"\b(?:type|types|style|styles|kind|kinds|shape|shapes)\b")
V16_CATCH = re.compile(r"\b(?:feature|features|function|functions|highlight|highlights|spec|specs|specification|specifications|description|descriptions|extra|extras|includ\w*|accessor\w*|misc\w*)\b")
V17_FIT = re.compile(r"\b[A-Z][A-Za-z]{0,5}[ -]?(?:\d{3,6}|\d{1,5}[xX]{1,3})\b")
V18_PART = r"[A-Za-z]{1,5}\d{0,3}-?\d{3,7}"
V19_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_ ./&'()\-]{0,38}")
V20_BULLET = re.compile(r"^\s*(?:[-*•·]|\d{1,3}[.)])\s+")
V21_PAIRKEY = re.compile(r"^k$|name|key|label|attr|prop|field|spec|title", re.I)
V22_ID = re.compile(r"(?i:(?:^|[ _-])(?:id|idx|sku|pid|ref|asin|ident\w*)(?=$|[ _-]))|^[iI][dD][A-Z0-9]|Ident|(?i:(?<![a-z])(?!(?:paid|valid|grid|solid|rigid|fluid|liquid|hybrid|rapid|void|acid|humid|android|said|laid)$)[a-z]*id$)")
V23_FAIL = re.compile(r"error|fail|(?<!de)fault|trouble(?!shoot)|denied|refus|invalid", re.I)
V24_PLACEHOLDER = re.compile(r"(?:none|null|n/a|unknown)")
V25_PAIRS = (": ", " = ", "=", " -> ", " - ")
V26_FIELDS = (" | ", "\n", " || ", " ; ", "; ", "\t", " // ", " · ", " • ", "|", ";", ", ")

PICKS3 = re.compile(r"cheapest|most|least")
UNIT_VALUE = re.compile(r"\d[\d.]*\s*[A-Za-z]{2,4}")
MONEY_WORDS = re.compile(r"price|cost|fee|amount|charge", re.I)

_YEAR_WORD = re.compile(r"[A-Z][a-z]* (?:19|20)\d\d")
_GAPS = re.compile(r"[ -]+")


def find_codes(text):
    out = []
    for m in V17_FIT.finditer(text or ""):
        c = m.group(0)
        if _YEAR_WORD.fullmatch(c):
            continue
        out.append(_GAPS.sub(" ", c).strip().lower())
    return out


def code_covers(part, device):
    p = re.sub(r"[ -]", "", part or "").lower()
    d = re.sub(r"[ -]", "", device or "").lower()
    m = re.search(r"(\d)(x+)$", p)
    if m:
        head = p[:m.start(2)]
        return d.startswith(head) and len(d) == len(p)
    return p == d


_OWN_CODE = re.compile(r"[\[(]\s*(?:part\s*)?(" + V18_PART + r")\s*[\])]", re.I)
_MODEL_CODE = re.compile(r"\bmodel\s*(?:no\.|no|number|#)?\s*[:.]?\s*(?!(?:no|number)\b)([A-Z][A-Z]{0,5}[ -]?(?:\d{3,6}|\d{1,5}X{1,3}))\b", re.I)
_ALSO_SOLD = re.compile(r"(?:also sold as|also known as|sold also as)([^.;]*)", re.I)
_WORKS = re.compile(r"(?<!not )(?<!never )\b(?:works with|compatible with|fits)\s*:?\s+([^.;]*)", re.I)
_EXCEPT_CUT = re.compile(r"\b(?:except|excluding|but not)\b", re.I)
_PART_ALSO = re.compile(r"part\s+" + V18_PART + r"\s+also\s*$", re.I)
_ALSO_FITS = re.compile(r"\bpart\s+(" + V18_PART + r")\s+also fits:?([^.;]*)", re.I)
_POINTER = re.compile(r"\b(?:more|details|see|read)\s+(?:on|at|under|about)?\s*(?:the\s+)?part\s+(" + V18_PART + r")", re.I)
_OWN_SERIES = re.compile(r"\b([A-Za-z]{1,5}\d{1,3})-\d{2,7}\b")
_SERIES_EXCL = re.compile(r"\b(?:except|excluding|but not|not for|not compatible with|does not fit|does not take)\b[^.;]*", re.I)
_NAMED_SERIES = re.compile(r"\b[A-Za-z]{1,5}\d{1,3}\b")


def fit_marks(text):
    text = text or ""
    m = _OWN_CODE.search(text)
    own = m.group(1).upper() if m else ""
    models = []
    for m in _MODEL_CODE.finditer(text):
        models.extend(find_codes(m.group(1)))
    for m in _ALSO_SOLD.finditer(text):
        models.extend(find_codes(m.group(1)))
    works = []
    barred = []
    for m in _WORKS.finditer(text):
        before = text[max(0, m.start() - 40):m.start()]
        if _PART_ALSO.search(before):
            continue
        span = m.group(1)
        c = _EXCEPT_CUT.search(span)
        if c:
            works.extend(find_codes(span[:c.start()]))
            barred.extend(find_codes(span[c.end():]))
        else:
            works.extend(find_codes(span))
    notes = []
    for m in _ALSO_FITS.finditer(text):
        notes.append((m.group(1).upper(), find_codes(m.group(2))))
    m = _POINTER.search(text)
    pointer = m.group(1).upper() if m else ""
    own_series = sorted({m.group(1).upper() for m in _OWN_SERIES.finditer(text)})
    rest = _OWN_SERIES.sub(" ", text)
    rest = _SERIES_EXCL.sub(" ", rest)
    named = sorted({m.group(0).upper() for m in _NAMED_SERIES.finditer(rest)})
    return {"own": own, "models": models, "works": works, "barred": barred, "notes": notes,
            "pointer": pointer, "series": own_series, "named": named}


MODEL_CLIENT = ProxyClient(timeout=50, max_retries=1, retry_delay=1)
ENV_CLIENT = ProxyClient(timeout=95, max_retries=3, retry_delay=1)
SHORT_CLIENTS = {}


GUIDE = """You are Cairn, a careful purchaser serving one single shopper inside a web shop. Your sole means of acting is a call to one of the store's tools. Grading is all-or-nothing: a score of one requires a finish that is exactly correct; anything else scores zero. A correct purchase must hold all requested items, every one in the quantity asked, every one satisfying each requirement still in force when checkout happens, and it must cost no more than the budget. The single alternative correct finish: when the shop truly holds nothing that satisfies everything, you must instead close the episode through the decline tool, performed in the manner the request specifies.

HOW THE STORE OPERATES
- Each call to a tool spends one step, the supply of steps is finite, and reasoning is free. Every store has its own tool names, parameter names and result layouts, so you must study the schema and the description of every tool and pass parameter names and permitted values exactly as given. Never guess a parameter name or a value.
- A search can be restricted: it may filter by category, a keyword mode may read just the opening words of a query, pages may hold only a handful of rows, and reaching the next page may need a token or an offset. Set the total the store reports against the number of rows you have seen; if the answer hinges on seeing every row, fetch further pages, passing back unchanged whatever token or offset came with the result. Keep keyword queries brief and lead with the value: the wanted value, then the product noun. A store's search may match attribute values and seller names in addition to titles, and may demand that every query word be present, so a handful of required values together with the noun can return almost the entire fitting set. A search by a part number or a model code can come back empty; a single attempt shows whether this store's search finds codes at all. When a filtered search returns zero rows, the usual cause is a wrong filter value or a wrong filter parameter: try again with the label copied letter for letter as the rows of a result show it, or switch to another filter parameter.
- Rows in search results are summaries only. Shops divide a listing's record across views differently: one view may expose the attribute block (attributes and properties are one thing here), another just the offer and a description, and either kind may appear in the side-by-side compare view. Once Cairn has learned which tool exposes attributes, the ledger says so. Each property requirement is judged on those attributes, so you must inspect the attributes of every listing you might purchase. A single call that displays several listings at once saves steps, provided it displays what is required. Never reopen a listing whose state has not changed since you read it.
- Asking the shopper is the job of Cairn's interviewer: never send the shopper a message yourself. The shopper's replies appear in your conversation, and the ledger records them.
- A request may also demand intermediate steps: obtaining an approval, sending a message, verifying or reading something beforehand. Each appears in the ledger. Those that fall due right ahead of the order or of a no-purchase ending are carried out by Cairn itself, at the moment you call the checkout or the decline tool. Hence never hold off waiting for them, and never decline on their account. The remaining steps you perform yourself with the shop's tools; questions about products are the exception and go via the interviewer.

WHAT COUNTS AS FITTING
- The category label of the listing settles the kind of product: only a label matching the requested item in its entirety qualifies; an adjacent label never does.
- A property requirement is satisfied when the attribute the listing has for that property gives the value. How the key is written is irrelevant: spacing, underscore separators, prefixes or camel-cased joins. When the attribute is a list split by commas or slashes, a single matching element suffices. Matching works word by word; differences of letter case, of singular versus plural form, and ordinary synonyms are tolerated. Containment counts: a value that includes all words of the required value meets it despite extra words (a colour with a shade word in front satisfies the plain colour; a fit word surrounded by an intensifier and a noun satisfies the plain fit word). A value made of other words fails: an abbreviation or a code does not equal the word it abbreviates, and two colour names sharing one word but differing in the other are different values (navy blue is not sky blue). Numbers: convert units first, then compare; a limit is inclusive of its boundary; a value given as a range must sit entirely within the limit.
- An attribute keyed by the requirement's property (that exact name or an ordinary synonym of it) is decisive: should it state another value, the listing fails, regardless of the title or of any other key. The exception: when a key prefixes the property name with the item's name (on a bag listing, a key meaning the bag's shape), its value counts even if the plain property key states otherwise. A key about another property, even a closely related one, settles nothing for this requirement (the colour of a handle tells nothing about the colour of the body). After listings are opened, Cairn appends [evidence] lines naming, for each requirement, the attribute keys whose name matches it.
- When a listing lacks any attribute for the property, the value sought still counts when it appears under some other attribute (such as a styles list or a features list that contains it), or in its description or title. It does not count when the figure is a different kind of quantity (weight is no substitute for capacity), or when a bare number appears with no text saying what it measures.
- When the requirement's value is written into the label of the category (a season or a target audience inside the label), the category satisfies it. Conversely a listing filed under the label that was asked for counts as a product of the requested kind, even when its description or title mentions something different; such a listing is judged solely on its requirements, its price and its stock.
- A requirement may refer to another listing rather than give its value, as in "match the X of the listing that <shop> sells with <property>" or "stay within N units of the X shown on another listing's page ...". Resolve such a requirement first: locate the referenced listing (searching on its words, brand, shop or category) and open its whole page using the single-item tool or the compare tool; a row from a search does not suffice. If the opened page sends you onward to one more listing that holds the property, that listing too is located and opened by the same method, and so on: the final page in the chain supplies the value. If the requirement wants whatever goes with the referenced value (its partner or its counterpart), and that page says what its own value is paired with, then that paired value becomes the requirement. An order is valid only if every page along the chain was opened. If the requirement accepts anything other than the value of the referenced listing, it removes only listings sharing exactly that value, and that rule by itself must never cause a decline.
- If a listing you intend to buy now points to a further page with more detail about itself, check that page before the purchase.
- If one requested item has to suit another, as an accessory suits a device, pick both jointly, based on the listings' own wording: a compatibility list, or a series or model code that appears on both pages. If no accessory meeting its own requirements is compatible with the chosen device, change to a different device that satisfies its own requirements and that one of those accessories does fit. Never decline while that device switch has not been tried.
- Exclusions must be honoured, and so must closed lists. Wishes (softly worded preferences, phrases meaning ideally or nice to have) serve only to break ties.
- Sold-out listings must never be bought. The total (each line's price times its quantity, added across all lines) must not go over the budget; landing exactly on it is allowed.

CHOOSING
- If the request wants the cheapest choice (the smallest price or the lowest total), the order must contain the listing with the lowest price out of ALL fitting listings. Establish the complete fitting set by paging through it (rows frequently arrive unsorted by price, and Cairn fetches further pages of short result lists on its own), examine the candidates from the cheapest upward, and pick the earliest one that fits fully. If a search tool accepts a maximum price, use it: list that category with the cap set below what its present best pick costs, so that only the cheaper ones still need checking.
- If the request wants the greatest or smallest amount of a measure, compare every fitting listing on the measure and take the extreme one; a listing silent on the measure is never the winner.
- Otherwise any listing satisfying everything is correct; do not burn steps looking for a better one.
- Put each item in the cart the moment an opened listing satisfies all of that item's requirements (for a price-ranked or measure-ranked pick, only after the fitting set has been compared), and then go on to the next item. A store frequently sells out a line shortly after it enters the cart, and carting early keeps steps in hand for a replacement.
- When several distinct items are requested, each needs its own cart line, every line at that item's requested quantity.

CHANGES DURING THE WORK
- Both the shopper and the store may alter the task: a fresh budget, an added or a removed requirement, a new price, a listing gone out of stock. Such changes show up within tool results, frequently on a checkout attempt in the form of a refusal. Any note is valid whichever tool's result carries it. The ledger shows the requirements currently in force. A refusal does not end the episode: apply all changes, correct the cart and try the checkout again.
- Prices and stock may also shift without any note. When you call the checkout, Cairn re-checks the cart lines and views the cart itself, so do not spend a turn on either one.

FINISHING
- Make the cart contain only the chosen lines, removing everything else, and then send the checkout as a call by itself, never batched with other calls in one turn.
- A no-purchase ending is allowed only once a genuine search has found that no listing satisfies everything. Being low on steps proves no such thing; in that situation check out with the best cart you hold. The ending follows the request's own wording; when a remark has to accompany it, keep it brief and name no listing.
- Each reply must include one or more tool calls. Keep text brief: the known facts, then the next action."""


BRIEF_PROMPT = """You set up a buying job that an agent will carry out. You receive the shopper's text and the list of store tools. Reply with exactly ONE JSON object, compact and unindented, with no text around it, holding the keys below.
"items": a list with one entry for each distinct product to be bought. Each entry is an object with four fields: "name" (what sort of product it is, worded as the request words it); "shelf" (if some tool exposes the store's category labels, the matching label, copied exactly; else a category that the request gives the product, as when a product is wanted "in" a named department, which then gives that department's name; else an empty text); "quantity" (the count of units to buy of that single listing, an integer, 1 when no number is stated; pairs and sets that come as one listing are quantity 1); "musts" (a list of the product's firm requirements, each written as property: constraint, stating the precise value, bound, excluded value or permitted set of values).
Name the property inside a must with the very word the request used for it: wording that the product is intended for some kind of occasion gives the property occasion with that kind as its value; a measure placed before a part of the product (a twelve-inch blade) gives that part's length, with number and unit. Never trade the property for a neighbouring one.
A reference requirement (its value has to come from a different listing) is written as ONE must that carries the other listing's full description, for example "colour: different from the colour of the tote bag that ShopName sells with a zip pocket". All the words describing the other listing (its shop, its product kind and any trailing clause of "with" plus property and value pairs) remain within that single must; none of them ever becomes a must of this product, and whatever words the request uses to relate the wanted value to the referenced value are copied as they stand: never reduce them to "same as".
Price, budget, stock and quantity never go into musts. Narrative around the purchase (the intended user, the place the product goes, earlier trouble, the occasion that prompted the purchase) counts as context and never as a must, except where it explicitly gives some property's value or bound. Words forming part of the product's own name, such as a season or a target group mentioned alongside the product, remain in "name" and are never turned into musts.
The exception that does create a must: when the request treats a purpose or event as a property belonging to the product, it IS a requirement on that very property, the one the request turns the purpose into (for example occasion: business), except where the category label used by the store names it already. This covers something said to be for a kind of wear, something said to be made for a kind of event, a product followed by a separate clause stating it is for an event, and a plain statement that the occasion must equal a given value. In contrast these remain context: one specific person's own event (wearing it at someone's own wedding), the recipient or place the purchase is meant for (a present for a co-worker), and its intended sit, feel or appearance when used.
When one phrase names products linked by "and" (a single "I want" clause with a single quantity, frequently the title of a single department of the store), that is ONE item. Split into separate items only if every product receives a separate quantity or separate requirements.
"budget": the shopper's ceiling for the whole spend, as a number in whatever unit the request uses; null if absent.
"budget_unit": the unit, written out (for example cents); null if absent.
"budget_scope": "total" if the cap applies to the full order, "each" if it applies per item, null if there is no cap.
"in_stock_only": true by default; false just when the request plainly allows unavailable listings.
"pick": "cheapest" for a request wanting the minimum price or the least total cost; "most" or "least" for a request wanting the maximum or minimum of some measure; "any" otherwise. Saying money is short does not make a pick rule.
"pick_measure": when the pick is one of the two extremes, the quantity being pushed to its extreme; otherwise an empty text.
"messages": the number of shopper messages the request permits the agent, an integer; null if unstated.
"steps": the request's allowance of steps, which it may phrase as moves or as calls to tools; an integer, else null.
"lookups": exact copies of those musts whose value has to be fetched first from a listing the request refers to; an empty list if none.
"rules": every instruction contained in the request on working method or on the way to finish, each no longer than 12 words.
"wishes": nice-to-haves, preferences the shopper voices without requiring them.
"ask_first": whatever the request explicitly wants confirmed with the shopper prior to choosing; empty if none.
"process": duties the request imposes on top of locating and purchasing the correct items (securing approval from the shopper; informing the shopper of, or displaying to them, some matter; confirming a point with the shopper; reading a thing before acting; employing a specific tool). Each entry is an object of three fields: "step" (the duty, no longer than 15 words), "when" (exactly one of "choose" = before any product is chosen, "order" = just before checking out, "end" = just before finishing with no purchase) and "messages" (the number of shopper messages the duty consumes, 0 if none). An empty list if the request imposes no such duty. Not duties: item requirements, budget, stock, the message and step limits, and what to do if nothing fits.
"quiet_decline": true if the request forbids suggesting or naming alternatives in case nothing fits; false if it wants alternatives; null if silent.
"fits": one entry for every requested item that, by the request, has to work together with some OTHER item of the request, or fit it, or suit it (that is, suit whichever listing the agent picks for that other item), as an object of two item numbers: "item" (the dependent item) and "with" (that other item). An empty list if none.
"roles": an object that maps each of nine jobs to the precise tool name, or to null where no tool performs it: "search"; "open" (displays the properties or attributes of a single listing; given two tools that each display a single listing, pick the one that, by its own description, offers specifications, properties or attributes); "offer" (displays one listing's live offer, for instance price and stock, and only if a tool other than the open one does that); "compare" (displays several listings completely); "ask" (messages the shopper); "cart" (modifies the cart); "cart_view" (displays the cart); "buy" (performs the checkout); "refuse" (finishes with no purchase).
"search_words": an object of three fields: "tool" (the tool taking free-text words to search listings; if one tool browses a category while a different one accepts words, choose the word-taking one), "field" (the parameter of that tool which receives the words) and "args" (constant arguments needed to switch it to word search, as a mode tool needs its mode value here; else an empty object).
"buy_args": constant arguments needed for the buy tool to perform the checkout (a mode tool needs its mode value here); else an empty object.
"refuse_args": constant arguments needed for the refuse tool to finish with no purchase; else an empty object."""

PLAN_PROMPT = """You pick which questions an agent will put to the person it shops for. Each shopper keeps a small number of firm, unwritten preferences, and every such preference is about a single property of a single requested product. Asking reveals a preference solely if the question names precisely that property. Where the shopper holds no opinion the answer is a "don't mind"; where the property never crosses the shopper's mind the answer is puzzled. Hence each property put in a message spends a share of that message.
You receive the request text; the items, each with the requirements the request already fixes; and a numbered table of attribute keys found on opened listings in every item's category, giving per key the count of those listings that have it plus sample values. Beware: the unwritten preference can concern a property none of the listed keys covers.
Choose in three tiers, in this order:
0. Anything the request wants checked with the shopper (shown under ASK FIRST, if present), each one named after the property involved.
1. Hinted properties. A request's story frequently hints at some unwritten preference while leaving its value unsaid: a sentence about a matter the shopper is unable to judge or hands over to the agent; about a person whose taste is decisive; about how the product looks or the surroundings it belongs to; about the intended wearer or user; about its contents. Per such sentence give the single property hinted at, together with its item, following the story's own order. Whenever a key listed for the same item matches the hint, use that key: a hint about the wearer maps to the gender or audience key; a hint about the product's looks maps to whichever colour, finish or pattern key is carried by the largest share of that item's listings. A hinted property absent from every listing of this item ranks below that item's three most widely carried keys, hence never above fourth.
2. Then the listed keys in rank order. Prefer both whatever properties shoppers for that sort of product decide on earliest (commonly the type or style, the form or fit, the dimensions, size or capacity, the material, the pattern or colour: whichever ones that sort of product is chosen by) and keys present on a majority of that item's listings. Once at least five listings have been read, steer clear of keys found on merely one listing or two.
Skip, per item: any property the request has settled for that item, that is, one a requirement already names (not settled, and still askable: a key with values that merely echo a required value, such as a pattern key whose values show the decoration the request demands); a further name for an already chosen property; a key in which each value bundles several purchase options together; identifiers; model names; warranty and any other logistics. Do not skip pack sizes, per-pack quantities and counts: they count as ordinary properties. A key carrying the mark [not the stated ...] is a different property from the requirement it mentions, however many words the two names share.
Rank every item separately: its hinted properties before its listed keys.
The "label" holds the plain name of the property. From a listed key it takes every word of the key in plain spelling: a key whose words run together with a capital at each join, or are joined by underscores, is written as separate lower-case words, and it is never cut down to its last word (the label for a lid's colour is "lid colour", never just "colour"; for a rim's finish it is "rim finish", never only "finish"). Just the name: no sample values, no bracketed text, and never a second property.
Pick at most COUNT properties per item, strongest first. The answer is ONE JSON object only, with a single key "ask" whose value is a list of picks, each an object with "item" (which item, by number), "label" (text) and "hint" (no more than eight words taken from the story that led to the pick, or an empty text). Within each item the picks follow rank order."""

REPLY_PROMPT = """An agent has put some questions to a shopper. Every answer has to be read. Reply with ONE JSON object only, nothing besides it, with five keys:
"needs": a list of objects with three fields: "item" (the item's number), "need" (written as property: constraint) and "points" (true if the value has to be taken from a different listing, false otherwise);
"drop": a list of objects with "item" and "property", the latter naming a requirement now abandoned by the shopper;
"free": a list of objects with "item" and "property";
"crowded": a list of question numbers where the answer objects that the message covered too many subjects, or wants the subjects asked singly; not answers that merely say the question was not understood or ask for plainer wording;
"budget": a revised overall ceiling as a number, else null.
"needs" covers each firm preference any answer expresses, with its precise value or bound and its unit (for example length: at least 40 cm; shape: oval; material: not plastic). Name the need after the property that the answer itself mentions, even when that differs from the property the question was about; several answers on one property give one need. Copy the value word for word from the answer, including the nouns and the units (a minimum number of shelves keeps the noun: at least 4 shelves, not only the number). Restrict the value to what a listing might state: it starts at the value wanted (or at the bound word preceding it), ends where the value ends, and omits the answer's surrounding framing: strip a leading word of matching, a lead-in saying the matter is settled and a tail saying nothing else will do, leaving the bare value, and strip a leading "equal to" before a bound, leaving the bound with its unit.
An answer may supply the value by reference to some other listing, giving a value that is like, unlike or close to the value on a product from some shop, which product is identified by a handful of its properties. That makes ONE single need for the property named by the answer, flagged with "points" true. Its value is the exact text of the answer, starting at the comparison word and running through to where that description ends, together with anything said about a listing which that page might name. It must never be shortened or reworded. Properties that describe the other product never count as this item's needs.
"free": per question, the property the shopper declared indifference to.
Folksy or indirect phrasing that still names a value does state that value. Phrasing that refuses to negotiate a value (it is not to be traded away, surrendered or altered) states the value as wanted; write a need as "not" a value only if the answer turns that very value down."""


NOTE_PROMPT = """During an agent's work the store displayed the notice below; its author may be the store itself or the shopper. Reply with one JSON object, nothing besides it, holding these keys in this order: "kind": "change" if the notice alters the job at hand (a budget, requirements, some price, availability, or refusing the order), "error" if it merely says some call was badly formed or turned down, "other" in all remaining cases; "budget": the new limit on total spend, as a figure in whatever unit the request used, or null; "add": new requirements, each an object with "item" (an item number) and "need" (written as property: constraint); "drop": requirements no longer wanted, each an object with "item" (an item number) and "need" (the wording of the withdrawn requirement); "gone": a list of the ids of listings the notice calls unavailable; "sold_out": true if the notice says a picked listing has vanished, sold out, or is no longer obtainable, even when no id is named; "price_moved": true if it reports some price moving; "summary": one brief sentence. A requirement swapped for another must appear twice, as a drop for the old wording plus an add for the new. Report each change the notice contains, all of them, not merely the first."""

CHECK_PROMPT = """You are the final gate ahead of checkout. From the records below, decide if this cart is precisely right.
The requirement list in force (the ledger under its heading below) already includes every later change made by the shopper and overrides what the request text says; a requirement carrying the marker DROPPED is void, and stays void even where the request's text goes on stating it.
Reading rules. For a requirement R on property P with value V: R holds when the listing's field for P states V; within that, the key K may be spelled any way, a single list member suffices, capitalisation, singular or plural forms and simple synonyms are all fine, a value that includes V's words counts (a shade word followed by the wanted colour satisfies that colour), units get converted, a limit includes its own boundary, and a range has to fall wholly inside. A field whose key names P itself decides: if it states something other than V, the listing fails; except that a value filed under a key prefixing P with the item's own kind (on a backpack, a key for the backpack's colour) still counts though the bare key for P disagrees. A key for another property, however related, decides nothing (a strap's colour says nothing about the main body's colour). Where no field for P exists at all, V stated under some other field, or in the title or description, is enough, except a figure of a different sort (a weight figure is no capacity) and a lone figure whose surrounding text never says what it measures. When R is a bound expressed with a unit (a measured limit), the only attribute that can settle it is one whose name has some word in common with P: if the figure sits under an attribute for some other dimension, or solely in the title, R stays unknown, and the listing is to be judged as failing R. An attribute whose name is P in plural form and whose value is a list enumerates the variants the seller offers; such a list does not give this particular listing's value whenever the title names some other member of it. If R is stated by the category label as such, being in that category satisfies R. The category label has to match the whole requested item, not just part of it. A requirement to differ from another listing's value is taken as met, except where the records reveal that very value.
Cart rules: every requested item must get a dedicated cart line carrying the quantity asked; the cart may hold nothing beyond those lines; no line may be shown as unavailable through stock-out; and each line's price multiplied by its quantity, added up, must give a total no higher than the budget.
When there are several records of one listing, the newest governs.
When other listings are provided (the pick rules cheapest, most and least), weigh them too: should one plainly satisfy all requirements while outdoing the cart's choice under that rule, then this cart is wrong.
Reply with one JSON object only, nothing besides it, with the keys "ok" (boolean), "problems" (a list of short, concrete faults) and "better" (ids of listings to put in place of some cart line, strongest first). "ok" is to be false solely for a fault the records plainly show, or when some requirement is addressed by no record."""

READ_RULES = """For a requirement R on property P with value V: a field of the listing settles P whenever its key K names P (K spelled any way; one list member suffices; synonyms are fine and units may be converted; a value that includes V's words is fine, as a shade word followed by the wanted colour satisfies that colour; a limit includes its own boundary); a value filed under a key prefixing P with the item's own kind (on a backpack, a key for the backpack's colour) still counts though the bare key for P disagrees; a key for another property, however related, decides nothing (a strap's colour says nothing about the main body's colour); with no field naming P, V stated under some other field, or in the title or description, is enough, but a lone figure that never says what it measures is worth nothing; when R is a bound expressed with a unit (a measured limit), the only attribute that can settle it is one whose name has some word in common with P, and a figure under an attribute for some other dimension, or solely in the title, leaves R unknown, so the listing fails R; an attribute whose name is P in plural form and whose value is a list enumerates the variants the seller offers, and such a list does not give this particular listing's value whenever the title names some other member of it; if the category label states R, that category meets R; the category label has to match the item; a requirement to differ from another listing's value is taken as met, except where the records reveal that very value; a listing that is out of stock, or that goes over the budget, is not a fit; the binding requirement list overrides the request text, and any requirement flagged DROPPED is void."""

AUDIT_PROMPT = ("The agent means to stop without buying, believing nothing fits. Check the records shown below against the requirements, using these reading rules: " +
                READ_RULES +
                "\nROW records come only from a search row: nobody has read their page (the fields), hence on any property the row itself does not show, such a record may be judged neither a pass nor a fail. "
                "Reply with one JSON object only: \"fits\" (an object whose keys are item numbers and whose values list the ids that seem to satisfy all requirements, lowest price first, 4 at most), "
                "\"open\" (ids of ROW listings whose kind was requested and that are within budget, whose page might prove a fit, likeliest first, 6 at most) and \"reason\" (one sentence).")

UNMIX_PROMPT = """Someone turned a shopping request into firm requirements for one product. Some requirements get their value from a different listing the request refers to, and words picking out that listing (the kind it is, the shop it comes from, the properties a "with" phrase after it names) are at times mistaken for requirements on the purchased product. Going by the request's own phrasing, say which entries of the second list, the one headed OTHER REQUIREMENTS placed after this text, do nothing but describe the referenced listing; the requirements that point to that listing are context, not candidates. Reply with one JSON object only: {"describe_other": [each such requirement, copied word for word]}, with an empty list when all are genuine requirements for the purchase."""

CHAIN_PROMPT = """The agent is near checkout. Some requirements draw their value off a second listing rather than stating it, and one listing's page may refer the reader onward to yet another listing for that same property. An order only counts once the agent has fully opened each listing along every such chain. Trace the chain of every requirement starting at its own description, link after link, through what the pages themselves say, using the records placed after the text. OPENED = that page was opened by the agent; ROW = page unread, the listing known just from a search row or through its fields.
A record counts as a link only if it fits the link's entire description: shop or brand, product kind AND each property value its description lists (a description of a multipack holding some count excludes a listing from that shop with the same count of another unit and no multipack). If no record fits all of it, the link is unlocated, even when that shop carries further listings of the same kind. For an unlocated link, "find" is a short query: the shop's name plus the described values, with property names and the product kind left out (describing one shop's kettle listing by a lid material of glass and the colour red gives a three-word query: the shop's name, glass, red): the store's word search requires every query word to appear in a listing, while listings often lack the property's name or the word for the product kind. Give the links of every chain in sequence and end that list at the earliest link that is unlocated or lacks an OPENED page, because what that page says is not yet known.
Reply with one JSON object only, holding "chains", one entry per requirement, each with: "need" (that requirement, copied word for word); "links" (an ordered list, each link with "id" (the identifier of the record that is this link (the record's own identifier, not any code its title happens to print), else an empty text), "about" (the way this link is described, by the requirement or by the preceding page), "values" (the values that description attributes to this listing, in a handful of words, with no property names and without the shop's name) and "find" (only where the link is not yet located: search words formed from the shop's name plus the described values, with property names and the product kind left out)); "done" (true if the final link is OPENED, its page itself states the property's value, and its own wording does not point the reader onward to yet another listing about that property (a page that hands the value over to some other listing does not qualify as the final link, even if its attribute block shows a value); true as well when the requirement wants some value that differs from that one or is unlike it, because the value on that page is the yardstick; otherwise false); "value" (the property's value as the final page states it; but when the requirement itself, or the original request phrasing behind it, wants a separate value that partners the page's value (a partner or counterpart value rather than the page's own) and the page also says what its own value is paired with, that partner; phrasing that wants whatever value the pointed page states, or wants to match it, means that very value, even if a verb about going together is used; else an empty text)."""

GATE_PROMPT = """The agent will shortly STAGE. The request wants the listed steps performed en route. Using the RECORD (the numbered lines recording the agent's actions), decide for each step owed ahead of this STAGE whether it has been completed for the cart in its current state. A step is complete only if some RECORD line records its performance; for a step concerning the cart or the order, that same line must also come later than the latest cart change, and the reply recorded on that same line must grant it. Questions about a product's properties never perform a step. For a step still missing, name the single store call to perform it now, picking a tool from the TOOLS list and supplying its arguments. Shopper messages use the messaging tool and consist of one brief sentence or question on that step alone, plainly worded, mentioning no product property or value beyond what the step needs. Give no call if all owed steps are complete, or if the remaining messages or steps cannot achieve the missing one. Reply with one JSON object only: "steps" (a list of entries with "step" (that step), "done" (boolean) and "lines" (the numbers of the RECORD lines that prove it)), "call" (an object with "tool" (a name) and "args" (an object), or null), "hold" (a change that some reply asks for before the agent goes on, else an empty text) and "needs" (a list of objects, each with "item" (an item number) and "need" (property: constraint), one per firm requirement a reply of that kind states)."""

SWAP_PROMPT = ("A listing in the agent's cart sold out a moment ago. Pick substitutes for it out of the remaining records shown, using these reading rules: " +
               READ_RULES +
               "\nReply with one JSON object only: \"fits\" (a list of entries, each with \"id\" (a listing id) and \"price\" (its price in number form, the way the record states it), "
               "covering every listing that seems to satisfy all requirements of the lost line's item, 6 at most) and \"reason\" (one sentence).")

SHAPE_PROMPT = """Some store tool produced the output shown after this text. Label its parts using the exact keys found in that result and in the tool's parameters. Reply with one JSON object only: "rows" (the key where the array of listings sits), "count" (the key where the total number of matches sits, explicitly not the number displayed, or null), "next" (the key where the value that requests the subsequent page sits, or null), "next_arg" (which tool parameter accepts that value, or null), "price" (within a row, the key of the listing's price, or null), "stock" (within a row, the key telling whether it can be purchased right now, or null)."""


_BOOLW = re.compile(r"true|false")
_EMPTYW = re.compile(r"none|null")
_MONEY = re.compile(r"[$€£]?\s?((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)")
_LEAD0 = re.compile(r"0\d")
_SPACE = re.compile(r"\s")
_DIGIT = re.compile(r"\d")


def failure_only(o):
    if not isinstance(o, dict) or not (1 <= len(o) <= 3):
        return False
    for k, v in o.items():
        if V23_FAIL.search(str(k)) and v:
            return True
    if len(o) == 1:
        v = next(iter(o.values()))
        if isinstance(v, str) and 1 <= len(v) <= 40 and not _SPACE.search(v):
            return True
    return False


def plain(t):
    s = str(t).strip()
    lo = s.lower()
    if _BOOLW.fullmatch(lo):
        return lo == "true"
    if not s or _EMPTYW.fullmatch(lo):
        return None
    m = _MONEY.fullmatch(s)
    if m and not _LEAD0.match(m.group(1)):
        num = m.group(1).replace(",", "")
        if "." in num:
            return float(num)
        return int(num)
    return s


def block_value(t):
    v = plain(t)
    s = str(t).strip()
    if isinstance(v, bool):
        return s
    if v is None and s:
        return s
    return v


def pair(text, mark):
    i = text.find(mark)
    if i >= 0:
        name, value = text[:i], text[i + len(mark):]
    else:
        bare = mark.strip()
        if bare and text.endswith(bare):
            name, value = text[:len(text) - len(bare)], ""
        else:
            return None
    name = V20_BULLET.sub("", name, count=1).strip()
    if not V19_FIELD.fullmatch(name) or len(name.split()) > 5:
        return None
    return name, value.strip()


def split_fields(text, sep, mark):
    parts = [p for p in text.split(sep) if p.strip()]
    if not parts or not pair(parts[0].strip(), mark):
        return [], 0
    fields = []
    named = 0
    heading = None
    for raw in parts:
        st = raw.strip()
        if sep == "\n" and heading is not None and (V20_BULLET.match(raw) or raw[:1] in " \t"):
            v = fields[heading][1]
            fields[heading][1] = (v + "\n" + st) if v else st
            continue
        heading = None
        if sep == "\n" and st.endswith(":") and V19_FIELD.fullmatch(st[:-1].strip()):
            fields.append([st[:-1].strip(), ""])
            heading = len(fields) - 1
            named += 1
            continue
        pr = pair(st, mark)
        if pr:
            fields.append([pr[0], pr[1]])
            named += 1
            continue
        if fields:
            fields[-1][1] = fields[-1][1] + sep + st
    return [(a, b) for a, b in fields], named


_LOOSE = re.compile(r"['\"]?([A-Za-z][A-Za-z0-9_ ./\-]{0,38})['\"]?\s*[:=]\s*['\"]?([^,'\"}\]]*)")
_BLOCK_CUT = re.compile(r";\s+|;$|\s\|\s|\n")
_NOPARSE = object()


def block_of(text):
    s = str(text).strip()
    if len(s) < 5:
        return None
    if s[0] in "{[" and s[-1] in "}]":
        try:
            v = json.loads(s)
        except Exception:
            v = _NOPARSE
        if v is not _NOPARSE:
            return v if isinstance(v, dict) else None
        found = {}
        for m in _LOOSE.finditer(s):
            found[m.group(1).strip()] = plain(m.group(2))
        return found if len(found) >= 2 else None
    if "=" in s:
        parts = [p for p in _BLOCK_CUT.split(s) if p.strip()]
        block = {}
        last = None
        for p in parts:
            i = p.find("=")
            name = p[:i].strip() if i >= 0 else ""
            if i >= 0 and 1 <= len(name) <= BLOCK_NAME and name not in block:
                block[name] = block_value(p[i + 1:])
                last = name
            elif last is not None:
                block[last] = str(block[last]) + "; " + p.strip()
            else:
                return None
        if len(block) >= 2:
            return block
        if len(block) == 1:
            k = next(iter(block))
            if ":" not in k and len(k) <= 30 and len(s) <= 90:
                return block
        return None
    lines = [ln for ln in s.split("\n") if ln.strip()]
    if len(lines) >= 2 and all(V20_BULLET.match(ln) for ln in lines):
        out = {}
        for ln in lines:
            pr = pair(ln.strip(), ": ")
            if not pr:
                out = None
                break
            out[pr[0]] = plain(pr[1])
        if out:
            return out
    for sep in (", ", "; "):
        if sep in s and ": " in s:
            prs = [pair(p.strip(), ": ") for p in s.split(sep)]
            if len(prs) >= 2 and all(prs) and all("." not in a for a, b in prs) and all(len(b) <= BLOCK_VALUE for a, b in prs):
                return {a: plain(b) for a, b in prs}
    return None


def record_text(text):
    best = None
    for sep in V26_FIELDS:
        if sep not in text:
            continue
        pieces = len([p for p in text.split(sep) if p.strip()])
        share = PAIR_SHARE if sep == ", " else FIELD_SHARE
        kept = None
        for mark in V25_PAIRS:
            fields, named = split_fields(text, sep, mark)
            if named < REC_MIN or named < share * pieces:
                continue
            if len({f[0] for f in fields}) * 2 <= len(fields):
                continue
            if kept is None or len(fields) > len(kept):
                kept = fields
        if kept is not None:
            best = kept
            break
    if best is None:
        return None
    out = {}
    for name, value in best:
        if name in out:
            continue
        b = block_of(value)
        if b is not None:
            out[name] = b
        elif V22_ID.search(name):
            out[name] = value.strip()
        else:
            out[name] = plain(value)
    return out


_RULE_LINE = re.compile(r"[\s|:+=\-]*")
_NUM_HEAD = re.compile(r"[\d.,$]+")


def table_text(text):
    lines = []
    for ln in text.split("\n"):
        if not ln.strip() or _RULE_LINE.fullmatch(ln):
            continue
        lines.append(ln.strip().strip("|").strip())
    if len(lines) < 2:
        return None
    for sep in ("|", "\t", ";", ","):
        rows = [[c.strip() for c in ln.split(sep)] for ln in lines]
        head = rows[0]
        if len(head) < 3 or any(len(r) != len(head) for r in rows) or not all(V19_FIELD.fullmatch(c) for c in head):
            continue
        if any(_NUM_HEAD.fullmatch(c) for c in head):
            continue
        return [{head[i]: plain(r[i]) for i in range(len(head))} for r in rows[1:]]
    return None


_TAG = re.compile(r"<[A-Za-z/][^<>]{0,40}>")
_INLINE_TAG = re.compile(r"</?(?:b|i|em|strong|span|a|u|small)\b[^<>]{0,40}>", re.I)
_CELL_TAG = re.compile(r"</t[dh]>\s*<t[dh](?:\s[^<>]{0,40})?>", re.I)
_TAG_RUN = re.compile(r"\s*(?:<[^<>]{1,40}>\s*)+")
_BLANK_CUT = re.compile(r"\n\s*\n")
_COL_GAP = re.compile(r" {2,}|\t")


def records_text(text):
    s = text.strip()
    if len(s) < 12:
        return None
    if s[0] in "{[":
        try:
            return restore(json.loads(s), 0, False, True)
        except ValueError:
            pass
    for cut in (_BLANK_CUT.split(s), s.split("\n")):
        if len(cut) >= 2:
            good = [r for r in (record_text(p) for p in cut) if r]
            if len(good) >= 2 and len(good) * 5 >= len(cut) * 4 and len({next(iter(r)) for r in good}) == 1:
                return good
    one = record_text(s)
    if "\n" in s and one is None:
        found = table_text(s)
    else:
        found = one
    if found is None and len(s) <= TAG_LIMIT and _TAG.search(s):
        h = _INLINE_TAG.sub("", s)
        h = _CELL_TAG.sub(": ", h)
        h = _TAG_RUN.sub("\n", h).strip()
        if h != s and len(h) >= 12:
            return records_text(h)
    if found is None and "\n" in s:
        g = "\n".join(_COL_GAP.sub(": ", ln.strip(), count=1) for ln in s.split("\n") if ln.strip())
        if g != s:
            return record_text(g)
    return found


_NV_PART = re.compile(r"[^=:]{1,40}=[^=]{0,200}")


def block_text(t):
    if len(t) < 5 or "=" not in t or not ("; " in t or " | " in t or "\n" in t):
        return t
    parts = [p for p in _BLOCK_CUT.split(t.strip()) if p.strip()]
    if len(parts) < 2 or not all(_NV_PART.fullmatch(p.strip()) for p in parts):
        return t
    b = block_of(t)
    return t if b is None else b


def attr_list(lst, allowed):
    if len(lst) < 2:
        return None
    f = lst[0]
    if isinstance(f, dict):
        keys = list(f.keys())
        if len(keys) != 2 or not V21_PAIRKEY.search(str(keys[0])):
            return None
        out = {}
        for e in lst:
            if not isinstance(e, dict) or set(e.keys()) != set(keys):
                return None
            n, v = e[keys[0]], e[keys[1]]
            if not isinstance(n, str) or not (1 <= len(n) <= BLOCK_NAME) or isinstance(v, (dict, list)):
                return None
            out[n.strip()] = v
        return out
    if isinstance(f, list):
        out = {}
        for e in lst:
            if not isinstance(e, list) or len(e) != 2 or not isinstance(e[0], str) or not (1 <= len(e[0]) <= BLOCK_NAME) or isinstance(e[1], (dict, list)):
                return None
            out[e[0].strip()] = e[1]
        return out
    if allowed and all(isinstance(e, str) for e in lst):
        out = {}
        for e in lst:
            s = e.strip()
            pr = pair(s, ": ") or pair(s, "=")
            if not pr or len(pr[1]) > BLOCK_VALUE or len(pr[0].split()) > 3:
                return None
            out[pr[0]] = plain(pr[1])
        return out
    return None


def holds_id(o):
    return isinstance(o, dict) and any(V22_ID.search(str(k)) for k in o)


def id_like(v, named):
    if not isinstance(v, str):
        return False
    s = v.strip()
    if not (3 <= len(s) <= 64) or _SPACE.search(s):
        return False
    return bool(named) or bool(_DIGIT.search(s))


def column_rows(o):
    for hk, hv in o.items():
        if isinstance(hv, list) and len(hv) >= 2 and all(isinstance(x, str) and V19_FIELD.fullmatch(x) for x in hv):
            for rk, rv in o.items():
                if rk == hk:
                    continue
                if isinstance(rv, list) and rv and all(isinstance(r, list) and len(r) == len(hv) for r in rv):
                    out = {}
                    for k, v in o.items():
                        if k == hk:
                            continue
                        out[k] = [dict(zip(hv, r)) for r in rv] if k == rk else v
                    return out
    return o


def id_texts(o):
    if not any(isinstance(v, str) and " " in v for v in o.values()):
        return o
    return {k: (str(v) if isinstance(v, int) and not isinstance(v, bool) and V22_ID.search(str(k)) and abs(v) >= 100 else v) for k, v in o.items()}


def keyed_rows(o):
    vals = list(o.values())
    if len(vals) < 2 or not all(isinstance(v, dict) and len(v) >= 3 for v in vals):
        return None
    if not all(_DIGIT.search(str(k)) and " " not in str(k) for k in o):
        return None
    shared = set(vals[0])
    for v in vals[1:]:
        shared &= set(v)
    if len(shared) < 3:
        return None
    out = []
    for k, v in o.items():
        if holds_id(v):
            out.append(v)
        else:
            r = {"id": str(k)}
            r.update(v)
            out.append(r)
    return out


def flat(v):
    if not any(isinstance(x, dict) for x in v.values()):
        return v
    out = {}
    for k, x in v.items():
        if isinstance(x, dict):
            for ik, iv in x.items():
                if isinstance(iv, (dict, list)):
                    continue
                out[str(k) + " " + str(ik)] = iv
        else:
            out[k] = x
    return out


def restore(v, depth=0, inrec=False, page=True):
    if depth > 7:
        return v
    if isinstance(v, str):
        r = records_text(v)
        return v if r is None else r
    if isinstance(v, list):
        a = attr_list(v, inrec and page)
        if a is not None:
            return a
        return [field_rule(e, depth, False, page) for e in v]
    if isinstance(v, dict):
        o = id_texts(column_rows(v))
        carded = len(o) >= 3 or holds_id(o)
        o2 = {}
        for k, x in o.items():
            kr = keyed_rows(x) if isinstance(x, dict) else None
            o2[k] = kr if kr is not None else x
        o = o2
        listing = holds_id(o) or any(id_like(x, False) for x in o.values())
        out = {}
        for k, x in o.items():
            if not isinstance(x, str) or len(o) <= 2:
                out[k] = field_rule(x, depth, carded, page)
            else:
                out[k] = block_text(x) if listing else x
        if depth <= 3:
            for k, x in list(out.items()):
                if isinstance(x, dict) and x and len(out) >= 3 and not holds_id(x):
                    inner = list(x.values())
                    f0 = inner[0]
                    if any(isinstance(i, dict) for i in inner) and not any(isinstance(i, list) for i in inner):
                        if isinstance(f0, (str, int, float)) or (isinstance(f0, dict) and f0):
                            out[k] = flat(x)
        if len(out) == 1 and v:
            only = next(iter(out.values()))
            first = next(iter(v.values()))
            if isinstance(only, dict) and len(only) >= 3 and isinstance(first, str):
                return only
        return out
    return v


def field_rule(x, depth, inrec, page):
    r = restore(x, depth + 1, inrec, page)
    if isinstance(x, str) and isinstance(r, dict) and len(r) < 5 and not holds_id(r) and not any(id_like(y, False) for y in r.values()):
        return x
    return r


FIRST_SPELLING = {}
_COMMA_CUT = re.compile(r"(?<!\d),|,(?!\d)")


def join_vals(held, new):
    have = {p.strip().lower() for p in _COMMA_CUT.split(held)}
    extras = []
    for p in _COMMA_CUT.split(new):
        q = p.strip().lower()
        if q and q not in have:
            have.add(q)
            extras.append(p.strip())
    if not extras:
        return held
    j = (held + ", " if held.strip() else held) + ", ".join(extras)
    FIRST_SPELLING[j] = FIRST_SPELLING.get(held, held)
    return j


def fold(v, depth=0):
    if depth > 5:
        return v
    if isinstance(v, list):
        return [fold(e, depth + 1) for e in v]
    if not isinstance(v, dict):
        return v
    out = {}
    seen = {}
    for k, x in v.items():
        n = words(k)
        fx = fold(x, depth + 1)
        if n in seen:
            kk = seen[n]
            if out[kk] == fx:
                continue
            if isinstance(out[kk], str) and isinstance(fx, str) and not V22_ID.search(n):
                out[kk] = join_vals(out[kk], fx)
                continue
            out[k] = fx
        else:
            seen[n] = k
            out[k] = fx
    if len(out) < 2 and len(v) >= 2:
        return {k: fold(x, depth + 1) for k, x in v.items()}
    return out


def dump(v):
    try:
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(v)


def clip(v, n, depth=0):
    if depth > 7:
        return "..."
    if isinstance(v, str):
        return v[:n] + "..." if len(v) > n else v
    if isinstance(v, dict):
        return {k: clip(x, n, depth + 1) for k, x in v.items()}
    if isinstance(v, list):
        return [clip(x, n, depth + 1) for x in v]
    return v


_FENCE = re.compile(r"```[A-Za-z]*\s*(.*?)\s*```", re.S)


def obj_of(t):
    if not isinstance(t, str):
        return None
    s = t.strip()
    m = _FENCE.fullmatch(s)
    if m:
        s = m.group(1)
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except (ValueError, RecursionError):
        pass
    a, b = s.find("{"), s.rfind("}")
    if 0 <= a < b:
        try:
            v = json.loads(s[a:b + 1])
            return v if isinstance(v, dict) else None
        except (ValueError, RecursionError):
            return None
    return None


_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SEPRUN = re.compile(r"[\s_.\-]+")
_PLURAL_ES = re.compile(r"(?:ch|sh|ss|x|z)es$")
_STOPW = re.compile(r"and|for|the|with")
_OUR = re.compile(r"our$")
_GLUE = re.compile(r"(\d)\s+([a-z]{1,3})(?![a-z0-9])")
_ALNUM = re.compile(r"[a-z0-9]+")
_TIER1 = re.compile(r"[a-z0-9]{3,}")
_TIER2 = re.compile(r"\d+[a-z]|\d*[a-z][a-z0-9]+")
_DIGITS = re.compile(r"\d+")


def words(s):
    s = _CAMEL.sub(" ", str(s))
    return _SEPRUN.sub(" ", s).strip().lower()


def under(s):
    return words(s).replace(" ", "_")


def stems(s):
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words(s).split()}


def roots(s):
    out = set()
    for w in words(s).split():
        if _PLURAL_ES.search(w):
            w = w[:-2]
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        if len(w) >= 3 and not _STOPW.fullmatch(w):
            out.add(w)
    return out


def spelled(s):
    out = set()
    for w in words(s).split():
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(_OUR.sub("or", w))
    return out


def names(a, b):
    if not a or not b:
        return False
    return a == b or a <= b or (len(b) >= 2 and b <= a)


def glued(s):
    return _GLUE.sub(r"\1\2", str(s).lower())


def text_words(s):
    lo = str(s).lower()
    return set(_ALNUM.findall(lo)) | set(_ALNUM.findall(glued(lo)))


def value_tokens(v):
    g = glued(v)
    t1 = _TIER1.findall(g)
    if t1:
        return t1
    t2 = [r for r in _ALNUM.findall(g) if _TIER2.fullmatch(r)]
    if t2:
        return t2
    return _DIGITS.findall(g)


def kinds(sc):
    t = sc.get("type") if isinstance(sc, dict) else None
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [x for x in t if isinstance(x, str)]
    return []


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def kind_fit(k, v):
    if k == "string":
        return isinstance(v, str)
    if k == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if k == "number":
        return is_num(v)
    if k == "boolean":
        return isinstance(v, bool)
    if k == "array":
        return isinstance(v, list)
    if k == "object":
        return isinstance(v, dict)
    if k == "null":
        return False
    return True


_SIGNED = re.compile(r"\s*-?\d+(?:\.\d+)?\s*")
_BOOLTXT = re.compile(r"\s*(?:true|false)\s*", re.I)


def shape(v, sc, path, faults):
    if not isinstance(sc, dict):
        return v
    ks = kinds(sc)
    if ks and not any(kind_fit(k, v) for k in ks):
        for k in ks:
            if k == "integer" and isinstance(v, float):
                try:
                    if v == int(v):
                        v = int(v)
                        break
                except (OverflowError, ValueError):
                    pass
            if (k == "integer" or k == "number") and isinstance(v, str) and _SIGNED.fullmatch(v):
                f = float(v.strip())
                v = int(f) if (k == "integer" or f == int(f)) else f
                break
            if k == "string" and is_num(v):
                v = str(v)
                break
            if k == "boolean" and isinstance(v, str) and _BOOLTXT.fullmatch(v):
                v = v.strip().lower() == "true"
                break
            if k == "array" and not isinstance(v, list) and v is not None:
                v = [v]
                break
        if not any(kind_fit(k, v) for k in ks):
            faults.append(path + " should be " + "/".join(ks))
            return v
    en = sc.get("enum")
    if isinstance(en, list) and v not in en:
        if isinstance(v, str):
            for o in en:
                if isinstance(o, str) and o.lower() == v.strip().lower():
                    v = o
                    break
        if v not in en:
            faults.append(path + " must be one of " + dump(en))
    ml = sc.get("maxLength")
    if isinstance(v, str) and isinstance(ml, int) and not isinstance(ml, bool) and len(v) > ml:
        cut = v[:ml]
        if not v[ml].isspace() and cut and not cut[-1].isspace() and " " in cut.strip():
            cut = cut[:cut.rfind(" ")].rstrip()
        v = cut
    mn = sc.get("minLength")
    if isinstance(v, str) and isinstance(mn, int) and not isinstance(mn, bool) and len(v) < mn:
        faults.append(path + " is too short")
    if is_num(v):
        lo, hi = sc.get("minimum"), sc.get("maximum")
        if is_num(lo) and v < lo:
            faults.append(path + " is below the minimum " + str(lo))
        if is_num(hi) and v > hi:
            faults.append(path + " exceeds the maximum " + str(hi))
    if isinstance(v, list):
        mx, mi = sc.get("maxItems"), sc.get("minItems")
        if isinstance(mx, int) and not isinstance(mx, bool) and len(v) > mx:
            faults.append(path + " allows at most " + str(mx) + " entries")
        if isinstance(mi, int) and not isinstance(mi, bool) and len(v) < mi:
            faults.append(path + " needs at least " + str(mi) + " entries")
        it = sc.get("items")
        if isinstance(it, dict):
            v = [shape(e, it, path + "[" + str(i) + "]", faults) for i, e in enumerate(v)]
    if isinstance(v, dict):
        props = sc.get("properties") if isinstance(sc.get("properties"), dict) else {}
        if sc.get("additionalProperties") is False:
            for k in v:
                if k not in props:
                    faults.append(path + "." + str(k) + " is not allowed by the schema")
        req = sc.get("required")
        if isinstance(req, list):
            for r in req:
                if isinstance(r, str) and r not in v:
                    faults.append(path + "." + r + " is required")
        v = {k: (shape(x, props[k], path + "." + str(k), faults) if k in props else x) for k, x in v.items()}
    return v


def shape_args(args, sc):
    faults = []
    out = shape(args, sc, "args", faults)
    return out, faults


def listify(v):
    if isinstance(v, list):
        return v
    if (isinstance(v, str) and v) or (isinstance(v, dict) and v):
        return [v]
    return []


_COUNT = re.compile(r"\s*(\d+)(?:\.0*)?\s*")


def count_of(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        try:
            return int(v) if v == int(v) else None
        except (OverflowError, ValueError):
            return None
    if isinstance(v, str):
        m = _COUNT.fullmatch(v)
        return int(m.group(1)) if m else None
    return None


def learn_id(rows):
    if not rows:
        return None
    best = None
    bs = None
    for k in rows[0].keys():
        named = bool(V22_ID.search(str(k)))
        vals = [r.get(k) for r in rows]
        if not all(id_like(x, named) for x in vals):
            continue
        if len(rows) >= 2 and len({x.strip() for x in vals}) < len(vals):
            continue
        score = (named, sum(len(x.strip()) for x in vals) / len(vals))
        if bs is None or score > bs:
            best, bs = k, score
    return best


def row_present(i, v, depth=0, inlist=False):
    if depth > 5:
        return False
    if isinstance(v, dict):
        if inlist and any(isinstance(x, str) and x.strip() == i for x in v.values()):
            return True
        return any(row_present(i, x, depth + 1, False) for x in v.values())
    if isinstance(v, list):
        return any(row_present(i, x, depth + 1, True) for x in v)
    return False


def model_client(room):
    if room >= 50:
        return MODEL_CLIENT
    t = max(5, int(room // 5) * 5)
    c = SHORT_CLIENTS.get(t)
    if c is None:
        c = ProxyClient(timeout=t, max_retries=1, retry_delay=1)
        SHORT_CLIENTS[t] = c
    return c


def attr_block(rec):
    if not isinstance(rec, dict):
        return None
    best = None
    bn = 0
    for v in rec.values():
        if isinstance(v, dict) and len(v) >= 2:
            sc = {k: x for k, x in v.items() if isinstance(x, (str, int, float)) and not isinstance(x, bool)}
            if len(sc) >= 2 and len(sc) > bn:
                best, bn = sc, len(sc)
    return best


def soft(fb):
    def deco(f):
        def w(self, *a, **k):
            try:
                return f(self, *a, **k)
            except Exception as e:
                self.trace.append({"kind": "soft_crash", "where": f.__name__, "error": (type(e).__name__ + ": " + str(e))[:300]})
                return fb() if callable(fb) else fb
        w.__name__ = f.__name__
        return w
    return deco


class Trace(list):
    def __init__(self, t0):
        super().__init__()
        self.t0 = t0

    def append(self, e):
        if isinstance(e, dict) and "t" not in e:
            e["t"] = round(time.monotonic() - self.t0, 1)
        super().append(e)


def filler(sc):
    if not isinstance(sc, dict):
        return False, None
    en = sc.get("enum")
    if isinstance(en, list) and en:
        return True, en[0]
    if "const" in sc:
        return True, sc["const"]
    if "default" in sc:
        return True, sc["default"]
    ks = kinds(sc)
    if "integer" in ks or "number" in ks:
        m = sc.get("minimum")
        return True, (m if is_num(m) else 1)
    if "boolean" in ks:
        return True, False
    if "string" in ks:
        ml = sc.get("maxLength")
        return True, "question"[:ml if isinstance(ml, int) and ml else 8]
    return False, None


def strings(v, depth=0):
    if isinstance(v, str):
        return [v]
    out = []
    if isinstance(v, dict):
        for x in v.values():
            out.extend(strings(x, depth + 1))
    elif isinstance(v, list):
        for x in v:
            out.extend(strings(x, depth + 1))
    return out


def says(v, text):
    return any(s == text for s in strings(v))


def rdump(v, n, limit):
    t = dump(clip(v, n))
    if len(t) <= limit or not isinstance(v, dict):
        return t[:limit]
    keys = list(v.keys())
    blocks = [k for k in keys if isinstance(v[k], dict) and len(v[k]) >= 2]
    if not blocks:
        return t[:limit]
    bk = blocks[0]
    bl = len(dump(clip(v[bk], n)))
    for k in blocks[1:]:
        ln = len(dump(clip(v[k], n)))
        if ln > bl:
            bk, bl = k, ln
    after = keys[keys.index(bk) + 1:]
    if not any(isinstance(v[k], str) and v[k].strip() for k in after):
        return t[:limit]
    ents = list(v[bk].items())
    for kept in range(len(ents) - 1, -1, -1):
        nb = dict(ents[:kept])
        nb["..."] = str(len(ents) - kept) + " more entries cut"
        rec = {k: (nb if k == bk else x) for k, x in v.items()}
        d = dump(clip(rec, n))
        if len(d) <= limit:
            return d
    return t[:limit]


_VOWELY = re.compile(r"[aeiouy]")


def kin(a, b):
    if not a or not b or not a.isalpha() or not b.isalpha() or a == b:
        return a == b
    k = 0
    while k < len(a) and k < len(b) and a[k] == b[k]:
        k += 1
    if k < 4:
        return False
    for tail in (a[k:], b[k:]):
        if tail and not (2 <= len(tail) <= 4 and _VOWELY.search(tail)):
            return False
    return True


_SPLIT_PARTS = re.compile(r"[,/;|]")


def fold_words(s):
    out = []
    for w in _ALNUM.findall(str(s).lower()):
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def split_run(want, text):
    ww = fold_words(want)
    if len(ww) < 2:
        return False
    run = False
    spread = False
    for part in _SPLIT_PARTS.split(str(text)):
        pw = fold_words(part)
        n = len(ww)
        if any(pw[i:i + n] == ww for i in range(len(pw) - n + 1)):
            run = True
        it = iter(pw)
        if all(w in it for w in ww):
            spread = True
    return spread and not run


_MONEY_TXT = re.compile(r"\s*[^\d\s]{0,3}\s?(\d[\d,]*(?:\.\d+)?)\s*[A-Za-z]{0,6}\.?\s*")


def money(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        for x in v.values():
            if is_num(x):
                return float(x)
        return None
    if not isinstance(v, str):
        return None
    m = _MONEY_TXT.fullmatch(v)
    return float(m.group(1).replace(",", "")) if m else None


def gnum(x):
    try:
        return "%g" % x
    except (TypeError, ValueError):
        return str(x)


class Item:
    def __init__(self, name, shelf, quantity, musts):
        self.name = name
        self.shelf = shelf
        self.quantity = quantity
        self.musts = musts
        self.told = []
        self.dropped = []
        self.free = []


_POINTER_WORDS = re.compile(r"\b(?:listing|page|shown|other than|unlike|same as)\b", re.I)
_PLAIN_BUDGET = re.compile(r"\s*\d+(?:\.\d+)?\s*")
_STAGES = re.compile(r"choose|order|end")
_SENT_BREAK = re.compile(r"(?<=[.!?;])\s+|\n+")
_FIGURE = re.compile(r"\d+(?:\.\d+)?")
_WORDRUN = re.compile(r"[a-z0-9]+")
_FINISH409 = re.compile(r"finish|quarantin|finaliz")
_RESYNC409 = re.compile(r"expected (\d+)")
_REUSE409 = re.compile(r"reuse|different action")
_HARD_FAIL = re.compile(r"400|401|402|403|404|422")
_RETRY_STATUS = re.compile(r"402|408|425|429")


class E1:
    def __init__(self, problem_data):
        env = problem_data["environment"]
        self.binding = dict(env["binding"])
        pv = env["policy_view"]
        self.pv = pv
        q = pv.get("query")
        self.request = q if isinstance(q, str) else ("" if q is None else str(q))
        self.tools = []
        self.schemas = {}
        self.descs = {}
        for t in pv.get("tools") or []:
            if isinstance(t, dict) and isinstance(t.get("function"), dict) and isinstance(t["function"].get("name"), str):
                fn = t["function"]
                sc = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {"type": "object", "properties": {}}
                self.schemas[fn["name"]] = sc
                self.descs[fn["name"]] = fn.get("description") or ""
                self.tools.append(t)
        self.names = list(self.schemas.keys())
        ms = pv.get("max_steps")
        b = count_of(ms)
        if b is None and isinstance(ms, float):
            try:
                b = int(ms)
            except (OverflowError, ValueError):
                b = None
        if not b or b <= 0:
            b = 30
        self.budget_steps = b
        self.t0 = time.monotonic()
        self.step = 0
        self.finished = bool(pv.get("finished"))
        self.store_broke = False
        self.no_credit = False
        self.waited = 0
        self.misses = 0
        self.spend = 0.0
        self.calls = 0
        self.turns = 0
        self.trace = Trace(self.t0)
        self.gap = STORE_GAP
        self.store_secs = 0.0
        self.store_n = 0
        self.last_store = 0.0
        self.convo = []
        self.brief = {}
        self.roles = {}
        self.items = []
        self.budget = None
        self.msg_limit = 0
        self.msg_used = 0
        self.duties = []
        self.msg_reserve = 0
        self.gate_msgs = 0
        self.gate_passes = set()
        self.done_log = []
        self.done_steps = []
        self.asked = False
        self.qlog = []
        self.heard = set()
        self.changes = []
        self.version = 0
        self.queued = []
        self.lookups = []
        self.rows = {}
        self.full = {}
        self.order = []
        self.opened = set()
        self.views = {}
        self.facts = {}
        self.bare = {}
        self.factless = set()
        self.id_key = None
        self.row_keys = set()
        self.tool_keys = {}
        self.view_keys = {}
        self.shapes = {}
        self.price_key = None
        self.stock_key = None
        self.read_cache = {}
        self.pages_read = 0
        self.paged = []
        self.remembered = {}
        self.page_arg = {}
        self.page_queries = {}
        self.searched = []
        self.value_rows = set()
        self.cmp_good = 0
        self.cmp_bad = 0
        self.code_tries = []
        self.codes_dead = False
        self.cart_touched = False
        self.cart_changed_at = -1
        self.cart_seen_at = -1
        self.cart_view = None
        self.cart_lines = {}
        self.cart_said = ""
        self.id_args = {}
        self.built = []
        self.dropped_ids = set()
        self.checkouts = 0
        self.refused_at = -1
        self.refusals = 0
        self.recent = []
        self.sold_holds = 0
        self.line_holds = 0
        self.fit_holds = 0
        self.checked = set()
        self.verdicts = {}
        self.audited = False
        self.leads = []
        self.lead_items = {}
        self.decline_blocks = 0
        self.pushed = False
        self.late_held = False
        self.confirmed = None
        self.completed = False
        self.offer_seen = {}
        self.gone = {}
        self.unavail = set()
        self.sold_lines = set()
        self.note_sold = False
        self.note_named = False
        self.refs = []
        self.ref_values = {}
        self.chain_rounds = 0
        self.chain_holds = 0
        self.chain_room = None
        self.decline_chain_done = False
        self.link_tried = set()
        self.link_searches = 0
        self.link_seen = {}
        self.fit_pairs = []
        self.fit_cache = None
        self.fit_partfits = {}
        self.owners_seen = {}
        self.adopted = {}
        self.plan_order = []
        self.lanes = {}
        self.hinted = {}
        self.lane_found = {}
        self.lane_spent = {}
        self.lane_used = {}
        self.lane_misses = {}
        self.late_asked = False
        self.one_product = set()
        self.list_asks = 0
        self.apart = {}
        self.follow_ups = []
        self.listing = False
        self.reply_reads = 0
        self.capped = set()
        self.terms_seen = 0
        self.cheaper_marks = set()
        self.wider_held = False
        self.hunts = 0
        self.hunt_mark = ""
        self.hunt_tried = {}
        self.hunt_stems = {}
        self.hunt_nonoun = set()
        self.fit_hunted = False
        self.absorbs = 0
        self.cat_cache = None
        self.title_cache = None
        self.cheaper_holds = 0
        self.dear_paged = set()
        self.cheaper_named = set()
        self.check_better = {}
        self.swap_agreed = False
        self.weak_holds = 0
        self.proofs = {}
        self.tools_reopened = False
        self.item_origins = {}
        self.swept = False
        self.series_swept = set()
        self.set_holds = 0
        self.link_pages = {}
        self.trail_notes = []
        self.ever_carted = {}
        self.effort_ok = True
        self.last_sent = {}
        self.carted_ids = set()
        self.units_known = False
        self.owner_cache = {}

    def left(self):
        return self.budget_steps - self.step

    def clock(self):
        return time.monotonic() - self.t0

    def room(self):
        return EPISODE_LEN - MARGIN - self.clock()

    def rushed(self):
        pace = self.store_secs / self.store_n if self.store_n else 1.0
        return self.room() <= 2 * max(pace, 1.0)

    def free_msgs(self):
        return self.msg_limit - self.msg_used - max(0, self.msg_reserve - self.gate_msgs)

    def cart_mark(self):
        return dump(sorted([[k, v] for k, v in self.cart_lines.items()]))

    def gate_due(self, stage):
        if not any(d["stage"] == stage for d in self.duties):
            return False
        return (stage, self.cart_mark() + "#" + str(self.version)) not in self.gate_passes

    def reserve(self):
        if any(d["stage"] == "order" and d["messages"] > 0 for d in self.duties) and self.msg_used < self.msg_limit and self.gate_due("order"):
            return 2
        return 1

    def judges(self, limit=SOFT):
        if self.spend <= limit and self.spend + HEAVY_ROOM <= HARD:
            return [HEAVY, LIGHT]
        if self.spend <= HARD:
            return [LIGHT]
        return []

    def pick(self):
        p = self.brief.get("pick") if isinstance(self.brief, dict) else None
        if isinstance(p, str) and PICKS3.fullmatch(p):
            return p
        return "any"

    def page_tools(self):
        out = []
        p = self.roles.get("offer") or self.roles.get("open")
        if p:
            out.append(p)
        c = self.roles.get("compare")
        if c and c not in out:
            out.append(c)
        return out

    def facts_tool(self):
        for t, v in self.facts.items():
            if v is True and self.single_target(t):
                return t
        o = self.roles.get("open")
        if o and self.facts.get(o) is not False and self.single_target(o):
            return o
        return None

    def cmp_facts(self):
        c = self.roles.get("compare")
        return self.facts.get(c) if c else None

    def cmp_bare(self):
        cf = self.cmp_facts()
        if cf is False:
            return True
        if cf is None:
            ft = self.facts_tool()
            return (ft is not None and self.facts.get(ft) is True) or bool(self.roles.get("offer"))
        return False

    def row_ids(self, tool, args):
        r = self.roles
        if tool not in (r.get("open"), r.get("offer"), r.get("compare"), r.get("cart")) or not tool or not self.rows:
            return args
        tk = self.title_key()
        if not tk:
            return args
        props = (self.schemas.get(tool) or {}).get("properties") or {}

        def fix(k, v):
            if not isinstance(v, str):
                return v
            s = v.strip()
            if s in self.rows or not (3 <= len(s) <= 30) or not _DIGIT.search(s):
                return v
            if isinstance(props.get(k), dict) and "enum" in props[k]:
                return v
            pat = re.compile(r"(?<![a-z0-9])" + re.escape(s.lower()) + r"(?![a-z0-9])")
            hits = [i for i, row in self.rows.items() if isinstance(row.get(tk), str) and pat.search(row[tk].lower())]
            if len(hits) == 1:
                self.trace.append({"kind": "row_id", "value": s, "id": hits[0]})
                return hits[0]
            return v

        out = {}
        for k, v in args.items():
            out[k] = [fix(k, e) for e in v] if isinstance(v, list) else fix(k, v)
        return out

    def think(self, messages, models, cap, tools=None):
        for model in models:
            if self.calls >= CALL_CAP:
                return None
            if self.room() < CALL_FLOOR:
                self.trace.append({"kind": "late_call_skipped", "model": model})
                return None
            self.calls += 1
            tries = 0
            status = None
            while True:
                msg, status = self.one_call(model, messages, cap, tools)
                if msg is not None:
                    return msg
                retryable = status is None or (isinstance(status, int) and (status >= 500 or bool(_RETRY_STATUS.fullmatch(str(status)))))
                limit = 1 if (status is None or status == 408) else len(WAITS)
                if not retryable or tries >= limit:
                    break
                wait = WAITS[tries]
                if self.waited + wait > WAIT_BUDGET or self.room() - 1.2 * wait < CALL_FLOOR:
                    break
                time.sleep(wait * random.uniform(0.8, 1.2))
                self.waited += wait
                tries += 1
            if status == 402:
                self.no_credit = True
                return None
        return None

    def one_call(self, model, messages, cap, tools):
        msgs = messages
        if model.startswith("anthropic/") and len(messages) >= 2:
            msgs = [dict(m) for m in messages]
            for i in sorted({0, len(msgs) - 1}):
                c = msgs[i].get("content")
                if isinstance(c, str) and c:
                    msgs[i]["content"] = [{"type": "text", "text": c, "cache_control": {"type": "ephemeral"}}]
        body = {"model": model, "messages": msgs, "max_tokens": cap, "temperature": 0}
        effort = bool(tools) and self.effort_ok and self.clock() >= LOW_EFFORT_CLOCK
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if effort:
            body["reasoning"] = {"effort": "low"}
        res = model_client(self.room()).post_verbose("/inference/chat/completions", body)
        data = res.data
        ok = isinstance(data, dict) and bool(data.get("choices"))
        if effort and not ok:
            st = (res.error or {}).get("status")
            if isinstance(data, dict) and isinstance(data.get("error"), dict):
                st = count_of(data["error"].get("code"))
            if st == 400 or st == 422:
                self.effort_ok = False
                self.trace.append({"kind": "effort_refused", "model": model, "status": st})
                return self.one_call(model, messages, cap, tools)
        if ok:
            usage = data.get("usage")
            cost = usage.get("cost") if isinstance(usage, dict) else None
            if is_num(cost):
                self.spend += cost
            ch = data["choices"][0] if isinstance(data["choices"], list) else {}
            if not isinstance(ch, dict):
                ch = {}
            msg = ch.get("message") if isinstance(ch.get("message"), dict) else {}
            if tools and not msg.get("tool_calls") and ch.get("finish_reason") == "length":
                self.trace.append({"kind": "model_fail", "model": model, "status": 0, "body": "the reply stopped at the token cap without a tool call"})
                return None, 0
            if msg.get("content") or msg.get("tool_calls"):
                return msg, 200
            self.trace.append({"kind": "empty_reply", "model": model})
            return None, 0
        err = res.error or {}
        status = err.get("status")
        body_text = err.get("body")
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            status = count_of(data["error"].get("code"))
            body_text = data["error"].get("message")
        self.trace.append({"kind": "model_fail", "model": model, "status": status, "body": str(body_text)[:200]})
        return None, status

    def json_ask(self, prompt, models, cap=1800):
        for m in models:
            msg = self.think([{"role": "user", "content": prompt}], [m], cap)
            o = obj_of(msg.get("content")) if msg else None
            if o is not None:
                return o
            if self.store_broke or self.no_credit or self.calls >= CALL_CAP:
                return None
        return None

    def env(self, tool, args):
        envl = dict(self.binding)
        envl["step"] = self.step + 1
        envl["action"] = {"name": tool, "args": args}
        self.last_sent[tool] = args
        since = time.monotonic() - self.last_store
        if since < self.gap:
            time.sleep(self.gap - since)
        self.last_store = time.monotonic()
        for _ in range(4):
            t = time.monotonic()
            res = ENV_CLIENT.post_verbose("/environment/call", envl)
            self.store_secs += time.monotonic() - t
            self.store_n += 1
            data = res.data
            if isinstance(data, dict):
                st = data.get("step")
                if isinstance(st, int) and not isinstance(st, bool):
                    self.step = st
                else:
                    self.step += 1
                if data.get("finished"):
                    self.finished = True
                if tool != self.roles.get("ask"):
                    data["observation"] = self.unspell(tool, data.get("observation"))
                obs = data.get("observation")
                self.note_read(tool, args, obs)
                ft = self.facts_tool()
                if tool == ft and isinstance(obs, dict) and not failure_only(obs):
                    ident = self.listing_id(obs, False, 0)
                    if ident and not attr_block(obs):
                        self.factless.add((tool, ident))
                if tool in self.page_tools() and not (isinstance(obs, dict) and obs.get("error")) and not failure_only(obs):
                    dumped = None
                    for v in args.values():
                        if isinstance(v, str):
                            self.opened.add(v.strip())
                            self.views.setdefault(v.strip(), set()).add(tool)
                        elif isinstance(v, list):
                            if dumped is None:
                                dumped = dump(obs)
                            for e in v:
                                if isinstance(e, str) and e.strip() in dumped:
                                    self.opened.add(e.strip())
                                    self.views.setdefault(e.strip(), set()).add(tool)
                return data
            err = res.error or {}
            status = err.get("status")
            body = str(err.get("body") or "")
            self.trace.append({"kind": "env_fail", "tool": tool, "status": status, "body": body[:200]})
            if status == 409:
                low = body.lower()
                if _FINISH409.search(low):
                    self.finished = True
                    return None
                m = _RESYNC409.search(body)
                if m:
                    n = int(m.group(1))
                    self.step = n - 1
                    envl["step"] = n
                    continue
                if _REUSE409.search(low):
                    self.step += 1
                    envl["step"] = self.step + 1
                    continue
                return None
            if isinstance(status, int) and _HARD_FAIL.fullmatch(str(status)):
                if status == 402:
                    self.store_broke = True
                return None
        return None

    def unspell(self, tool, obs):
        r = self.roles
        views = {r.get("open"), r.get("offer"), r.get("compare")} - {None}
        page = tool != r.get("search") or tool in views
        res = fold(restore(obs, 0, False, page))
        if tool not in views:
            return res
        for i, row in self.rows.items():
            if i not in self.opened:
                self.row_keys.update(row.keys())
        if not self.row_keys:
            return res

        def gather(rec):
            if not isinstance(rec, dict) or attr_block(rec) or not self.listing_id(rec, True, 1):
                return rec
            extras = {k: v for k, v in rec.items() if k not in self.row_keys and (isinstance(v, str) or is_num(v))}
            if len(extras) < REC_MIN:
                return rec
            out = {k: v for k, v in rec.items() if k not in extras}
            out["attributes"] = extras
            return out

        if isinstance(res, dict) and self.listing_id(res, False, 0):
            return gather(res)
        if isinstance(res, dict):
            return {k: ([gather(e) for e in v] if isinstance(v, list) else v) for k, v in res.items()}
        return res

    def shared_shelf(self, b):
        seen = set()
        for e in listify(b.get("items")):
            if isinstance(e, dict):
                s = words(e.get("shelf") or "")
                if s:
                    if s in seen:
                        return True
                    seen.add(s)
        return False

    def complete(self, b):
        return bool(b) and bool(b.get("items")) and isinstance(b.get("roles"), dict) and bool(b["roles"].get("buy"))

    def read_brief(self):
        lines = []
        for t in self.tools:
            fn = t["function"]
            p = fn.get("parameters")
            lines.append("- " + fn["name"] + ": " + str(fn.get("description") or "") + " | parameters: " + dump(p if p is not None else {}))
        prompt = BRIEF_PROMPT + "\nTOOLS:\n" + "\n".join(lines) + "\n\nREQUEST:\n" + self.request
        if self.pv.get("opening") is not None:
            prompt += "\n\nSTORE'S OPENING NOTE (shown before any call):\n" + dump(clip(self.pv["opening"], 1500))
        b = self.json_ask(prompt, [LIGHT], 4000) or {}
        if not self.no_credit:
            if not b.get("items") or not isinstance(b.get("roles"), dict) or not b["roles"].get("buy"):
                b2 = self.json_ask(prompt, [HEAVY, LIGHT], 2500)
                if b2:
                    b = b2
            elif self.shared_shelf(b):
                b2 = self.json_ask(prompt, [HEAVY], 2500)
                if self.complete(b2):
                    b = b2
        while not b and not self.no_credit and self.calls < CALL_CAP and self.clock() < BRIEF_DEADLINE:
            time.sleep(OUTAGE_PAUSE)
            b = self.json_ask(prompt, [LIGHT, HEAVY], 2500) or {}
        if b:
            self.waited = 0
        self.brief = b
        roles = b.get("roles") if isinstance(b.get("roles"), dict) else {}
        self.roles = {k: v for k, v in roles.items() if isinstance(v, str) and v in self.schemas}
        if not isinstance(b.get("buy_args"), dict):
            b["buy_args"] = {}
        if not isinstance(b.get("refuse_args"), dict):
            b["refuse_args"] = {}
        buy, ref = self.roles.get("buy"), self.roles.get("refuse")
        if buy and buy == ref:
            ba, ra = b["buy_args"], b["refuse_args"]
            if not (ba and ra and ba != ra):
                p = ("The store tool " + buy + " can either complete the purchase or close the episode with no purchase, "
                     "depending on the arguments it is given. Its parameter schema:\n" + dump(self.schemas.get(buy) or {}) +
                     "\nReply with one JSON object only, nothing else, holding two fields: \"buy_args\", the constant arguments "
                     "that make this tool complete the purchase, and \"refuse_args\", the constant arguments that make it close "
                     "the episode without buying. Include in each only the arguments that select the mode.")
                ans = self.json_ask(p, [LIGHT, HEAVY], 1500)
                if ans and isinstance(ans.get("buy_args"), dict) and isinstance(ans.get("refuse_args"), dict) and ans["buy_args"] != ans["refuse_args"]:
                    b["buy_args"], b["refuse_args"] = ans["buy_args"], ans["refuse_args"]
        raw = b.get("items")
        if isinstance(raw, (dict, str)):
            raw = [raw]
        if not isinstance(raw, list):
            raw = []
        items = []
        for e in raw:
            if not isinstance(e, dict):
                continue
            q = count_of(e.get("quantity"))
            q = q if q and q > 0 else 1
            mv = e.get("musts")
            mv = mv if isinstance(mv, list) else [mv]
            musts = [str(m) for m in mv if m]
            nm = e.get("name")
            nm = str(nm) if nm is not None and str(nm).strip() else "the product"
            sh = e.get("shelf")
            sh = str(sh) if sh is not None else ""
            items.append(Item(nm, sh, q, musts))
        merged = []
        renum = {}
        for idx, it in enumerate(items):
            tgt = None
            if it.shelf.strip():
                for j, m in enumerate(merged):
                    if m.quantity == it.quantity and words(m.shelf) == words(it.shelf) and not self.conflict(m, it):
                        tgt = j
                        break
            if tgt is None:
                merged.append(it)
                renum[idx + 1] = len(merged)
            else:
                m = merged[tgt]
                for r in it.musts:
                    if r not in m.musts:
                        m.musts.append(r)
                renum[idx + 1] = tgt + 1
                self.trace.append({"kind": "merged_items", "into": m.name, "from": it.name})
        if not merged:
            merged = [Item("the requested product", "", 1, [])]
        self.items = merged
        self.scope()
        for f in listify(b.get("fits")):
            if not isinstance(f, dict):
                continue
            a = renum.get(count_of(f.get("item")))
            w = renum.get(count_of(f.get("with")))
            if a and w and a != w and a <= len(merged) and w <= len(merged) and (a, w) not in self.fit_pairs:
                self.fit_pairs.append((a, w))
        for lk in listify(b.get("lookups")):
            t = str(lk).strip()
            self.lookups.append(t)
            if not any(t in it.musts for it in merged):
                p = words(t.split(":", 1)[0])
                for it in merged:
                    hit = next((m for m in it.musts if words(m.split(":", 1)[0]) == p), None)
                    if hit:
                        t = hit
                        break
            n = next((i + 1 for i, it in enumerate(merged) if t in it.musts), 1)
            if t and (n, t) not in self.refs:
                self.refs.append((n, t))
        self.unmix()
        bu = b.get("budget")
        if isinstance(bu, str) and _PLAIN_BUDGET.fullmatch(bu):
            bu = float(bu)
        self.budget = bu if is_num(bu) and bu > 0 else None
        mc = count_of(b.get("messages"))
        if mc is not None and mc >= 0:
            self.msg_limit = mc
        elif self.roles.get("ask"):
            self.msg_limit = 3
        sc = count_of(b.get("steps"))
        if sc is not None and 10 <= sc < self.budget_steps:
            self.budget_steps = sc
        for d in listify(b.get("process")):
            if not isinstance(d, dict) or not str(d.get("step") or "").strip():
                continue
            st = str(d.get("when") or "").strip().lower()
            if not _STAGES.fullmatch(st):
                st = "order"
            mm = count_of(d.get("messages"))
            mm = max(0, mm) if mm is not None else 0
            self.duties.append({"text": str(d["step"]).strip(), "stage": st, "messages": mm})
        if self.roles.get("ask"):
            c = [d["messages"] for d in self.duties if d["stage"] != "choose" and d["messages"] > 0]
            self.msg_reserve = min(max(c), self.msg_limit) if c else 0

    def scope(self):
        pointed = {str(x).strip() for x in listify(self.brief.get("lookups"))}
        sents = [s for s in _SENT_BREAK.split(self.request) if s.strip()]
        sroots = []
        for s in sents:
            lst = []
            for w in words(s).split(" "):
                lst.extend(roots(w))
            sroots.append(lst)
        nr = [roots(it.name) for it in self.items]

        def named(si):
            rl = sroots[si]
            rs = set(rl)
            out = []
            for i, r in enumerate(nr):
                if not r or not r <= rs:
                    continue
                wider = any(j != i and nr[j] > r and nr[j] <= rs for j in range(len(nr)))
                if wider and all(rl.count(x) == 1 for x in r):
                    continue
                out.append(i)
            return out

        cands = sorted({m for it in self.items for m in it.musts if ":" in m and m not in pointed})
        for c in cands:
            holders = [i for i, it in enumerate(self.items) if c in it.musts]
            if len(holders) < 2:
                continue
            prop, val = c.split(":", 1)
            pr = roots(prop)
            if not pr:
                continue
            figs = set(_FIGURE.findall(val))
            keep = set()
            for si in range(len(sents)):
                if not (pr <= set(sroots[si]) and figs <= set(_FIGURE.findall(sents[si]))):
                    continue
                nh = [i for i in named(si) if i in holders]
                if not nh:
                    keep = set()
                    break
                keep |= set(nh)
            if not keep:
                continue
            for i in holders:
                if i not in keep and any(nr[i] & nr[k] for k in keep):
                    self.items[i].musts.remove(c)
                    self.trace.append({"kind": "scoped", "must": c, "left": i + 1, "kept": sorted(k + 1 for k in keep)})

    def conflict(self, a, b):
        for x in a.musts:
            for y in b.musts:
                px, _, vx = x.partition(":")
                py, _, vy = y.partition(":")
                if words(px) == words(py) and words(vx) != words(vy):
                    return True
        return False

    def unmix(self):
        for n, it in enumerate(self.items, 1):
            ptrs = [t for (i, t) in self.refs if i == n and t in it.musts]
            rest = [m for m in it.musts if m not in ptrs]
            if not ptrs or not rest:
                continue
            p = (UNMIX_PROMPT + "\n\nREQUEST:\n" + self.request + "\n\nPRODUCT: " + it.name +
                 "\nTHESE REQUIREMENTS REFER TO A DIFFERENT LISTING:\n" + "\n".join(ptrs) +
                 "\nOTHER REQUIREMENTS:\n" + "\n".join(rest))
            ans = self.json_ask(p, [HEAVY, LIGHT], 1500) or {}
            lst = [x.strip() for x in listify(ans.get("describe_other")) if isinstance(x, str)]
            moved = [m for m in rest if m in lst]
            if not moved:
                continue
            first = ptrs[0]
            new = first + " (that listing: " + "; ".join(moved) + ")"
            it.musts = [(new if m == first else m) for m in it.musts if m not in moved]
            self.refs = [(i, new if (i == n and t == first) else t) for (i, t) in self.refs]
            self.trace.append({"kind": "unmixed", "item": n, "moved": moved})

    def live_of(self, it):
        return [r for r in it.musts + it.told if r not in it.dropped]

    def described(self, n, req):
        if any(req == t for _, t in self.refs) or req in self.lookups:
            return False
        if ":" not in req:
            return False
        prop, val = req.split(":", 1)
        if not prop.strip():
            return False
        if len(_WORDRUN.findall(val.lower())) < 4:
            return False
        if _POINTER_WORDS.search(val):
            return False
        vst = stems(val)
        for j, o in enumerate(self.items, 1):
            if j != n and vst & {s for s in stems(o.name) if len(s) >= 4}:
                return False
        ck = self.cat_key()
        blocks = []
        for i in self.order:
            rec = self.full.get(i)
            if rec is None:
                continue
            if ck is not None and not self.owns(n, str(rec.get(ck) if rec.get(ck) is not None else "")):
                continue
            ab = attr_block(rec)
            if ab:
                blocks.append(ab)
        if len(blocks) < 3:
            return False
        pst = stems(prop)
        for ab in blocks:
            for k in ab:
                if stems(k) & pst:
                    return False
        return True

    def ledger(self):
        lines = []
        many = len(self.items) > 1
        for n, it in enumerate(self.items, 1):
            head = ("item %d: %s" % (n, it.name)) if many else ("item: " + it.name)
            if it.shelf:
                head += " (store label: " + it.shelf + ")"
            head += ", quantity " + str(it.quantity)
            dec = []
            desc = []
            live = self.live_of(it)
            for r in live:
                txt = r
                if r in self.ref_values:
                    txt += " (value read on the referenced page: " + str(self.ref_values[r]) + ")"
                (desc if self.described(n, r) else dec).append(txt)
            head += "; requirements: " + ("; ".join(dec) if dec else "nothing besides the product type itself")
            if desc:
                head += "; from the shopper's own phrasing, recorded by no attribute of any listing, so they settle nothing: " + "; ".join(desc)
            dl = []
            for d in it.dropped:
                if d and d not in dl and d not in live:
                    dl.append(d)
            if dl:
                head += ("; DROPPED, withdrawn by the shopper after the request was written (required no more, and that holds also "
                         "where the request's text still states them): " + "; ".join(dl))
            lines.append(head)
        ll = self.label_line()
        if ll:
            lines.append(ll)
        if self.budget is not None:
            unit = self.brief.get("budget_unit")
            scope = "for each item" if self.brief.get("budget_scope") == "each" else "in total"
            s = "budget: at most " + str(self.budget) + " " + (str(unit) if unit else "") + " " + scope
            lines.append(s.replace("  ", " ", 1))
        pk = self.pick()
        if pk == "cheapest":
            lines.append("pick: the lowest-priced matching listing (lowest price)")
        elif pk == "most" or pk == "least":
            lines.append("pick: the " + pk + " " + str(self.brief.get("pick_measure") or "") + " among the matching listings")
        else:
            lines.append("pick: any listing meeting every requirement")
        if self.brief.get("in_stock_only") is not False:
            lines.append("in stock only")
        for w in listify(self.brief.get("wishes")):
            lines.append("wish (only breaks ties): " + str(w))
        for r in listify(self.brief.get("rules")):
            lines.append("rule the request gives: " + str(r))
        if self.brief.get("quiet_decline") is True:
            lines.append("if nothing fits, the episode ends without naming or proposing any listing")
        for d in self.duties:
            if d["stage"] == "choose":
                tm = "before choosing"
            elif d["stage"] == "order":
                tm = "at the purchase; Cairn carries it out when you order"
            else:
                tm = "at a decline; Cairn carries it out at that moment"
            lines.append("step the request requires (" + tm + "): " + d["text"])
        ft = self.facts_tool()
        if ft and (self.facts.get(ft) is True or self.roles.get("offer")):
            s = "listing attributes: " + ft + " shows them"
            pts = set(self.page_tools())
            if self.roles.get("offer"):
                pts.add(self.roles["offer"])
            none = sorted(t for t in pts if self.facts.get(t) is False)
            if none:
                s += "; " + ", ".join(none) + " show none"
            others = sorted(t for t in self.page_tools() if t != ft)
            if others:
                s += "; " + " or ".join(others) + " display a listing's page, the page meant whenever a chain is followed or a page is checked"
            lines.append(s)
        return "\n".join("- " + x for x in lines)

    def status(self):
        s, m, lft = self.step, self.budget_steps, self.left()
        res = self.reserve()
        out = "[Cairn] step %d of %d used, %d left." % (s, m, lft)
        if lft <= res + 1:
            out += (" FINAL STEPS: order now if every item already has a carted line; decline only when searching has "
                    "proved that some item lacks any matching listing, and a shortage of steps proves no such thing.")
        elif lft <= 6 or (lft <= len(self.items) + 5 and not self.checkouts):
            out += " Few steps remain: make the cart hold exactly the picked lines and order at once."
        elif not self.checkouts and lft <= 12:
            out += " Steps are getting scarce: decide the picks, put them in the cart and order within a few more steps."
        elif not self.checkouts and not self.cart_touched and s >= m // 2:
            out += (" Half the step budget is spent with nothing in the cart: put the matching listing of every item in it "
                    "now, because the store may yet sell a listing out.")
        if self.clock() >= WIND_DOWN and lft > res + 1:
            out += (" TIME IS ALMOST OVER: make the cart hold the picked lines and order within two more turns, since an "
                    "episode cut off by the clock scores zero.")
        livep = set(self.live())
        pend = [t for (i, t) in self.refs if (i, t) in livep and t not in self.ref_values]
        if pend and not self.checkouts:
            out += ("\n[Settle these first: visit the listing each one points at, and also every listing to which that "
                    "listing's page refers onward (only those its page directs you on to), since the final page holds the value] " +
                    " | ".join(pend[:3]))
        if self.leads:
            out += "\n[review candidates] " + ", ".join(self.leads)
        if self.fit_pairs and not self.checkouts:
            fp = self.fit_plan()
            if fp:
                out += "\n" + fp
        if self.fit_pairs:
            sets = self.read_sets()
            cur = set(self.cart_ids())
            if sets and not any(set(s["ids"]) == cur for s in sets):
                out += ("\n[complete sets made only of listings already read]: each line of these sets states every one of its own "
                        "requirements in its attribute block or its title, and the line chosen for each bound item matches the device "
                        "through a code. " + self.set_text(sets) + ". Make the cart consist of one of the listed sets, unless some "
                        "record contradicts a requirement.")
        if self.changes:
            out += "\n[changes so far] " + " | ".join(self.changes[-4:])
        out += "\n[ledger]\n" + self.ledger()
        return out


_THREE_DIGITS = re.compile(r"\d{3}")
_SLASH_SP = re.compile(r" / ")
_LETTERS3 = re.compile(r"[a-z]{3,}")
_ALNUM3 = re.compile(r"[a-z0-9]{3,}")
_E2_CMP = re.compile(r"\b(?:not|no|other than|unlike|under|less|below|up to|at most|more|above|over|at least|between|within|or)\b", re.I)
_E2_PRICED = re.compile(r"price|money|cost|amount|spend|budget", re.I)
_E2_CAPW = re.compile(r"max|most|under|below|limit|cap|upto|up_to", re.I)
_PRICE_TXT = re.compile(r"\s*[^\d\s]{0,3} ?(\d[\d,]*(?:\.\d+)?)\s*[A-Za-z]{0,6}\.?\s*")

SKIP_OPEN = "[Cairn] This call was not executed and spent no step."
HOLD_OPEN = "[Cairn] This call was not executed yet and spent no step."
BARE_HOLD = "[Cairn] This call was not executed yet."


class E2:
    def listing_id(self, o, inrows, depth):
        if not isinstance(o, dict) or len(o) < 3:
            return None
        if self.id_key is not None:
            v = o.get(self.id_key)
            if id_like(v, True):
                return v.strip()
        if not (inrows or depth == 0 or any(isinstance(v, dict) for v in o.values())):
            return None
        k = learn_id([o])
        if k is None:
            return None
        v = o[k].strip()
        if "id" in str(k).lower() or v in self.rows:
            return v
        return None

    def is_row_list(self, lst):
        cand = [e for e in lst if isinstance(e, dict) and len(e) >= 3]
        if not cand or len(cand) * 2 < len(lst):
            return False
        if self.id_key is not None and all(id_like(e.get(self.id_key), True) for e in cand):
            return True
        k = learn_id(cand)
        if k is None:
            return False
        self.id_key = k
        return True

    def absorb(self, obs):
        self.absorbs += 1
        self.walk_obs(obs, False, 0)

    def walk_obs(self, v, inrows, depth):
        if depth > 6:
            return
        if isinstance(v, dict):
            i = self.listing_id(v, inrows, depth)
            if i:
                if i not in self.rows:
                    self.order.append(i)
                    self.rows[i] = {}
                row = self.rows[i]
                flip = None
                for k, x in v.items():
                    if row.get(k) is True and x is False:
                        flip = "off"
                        break
                if flip is None:
                    for k, x in v.items():
                        if row.get(k) is False and x is True:
                            flip = "on"
                            break
                if flip == "off":
                    self.unavail.add(i)
                elif flip == "on":
                    self.unavail.discard(i)
                row.update(v)
                if attr_block(v):
                    self.full[i] = dict(row)
                elif i in self.full:
                    self.full[i].update(v)
                return
            for x in v.values():
                self.walk_obs(x, False, depth + 1)
        elif isinstance(v, list):
            rl = self.is_row_list(v)
            for x in v:
                self.walk_obs(x, rl, depth + 1)

    def enum_labels(self):
        out = set()

        def walk(sc, d):
            if d > 6 or not isinstance(sc, dict):
                return
            en = sc.get("enum")
            if isinstance(en, list):
                for o in en:
                    if isinstance(o, str):
                        out.add(o.strip().lower())
            for x in sc.values():
                if isinstance(x, dict):
                    walk(x, d + 1)

        for sc in self.schemas.values():
            walk(sc, 0)
        return out

    def cat_key(self):
        ck = (len(self.rows), self.absorbs)
        if self.cat_cache is not None and self.cat_cache[0] == ck:
            return self.cat_cache[1]
        best = None
        if self.rows:
            vals = {}
            cnt = {}
            for row in self.rows.values():
                for k, v in row.items():
                    if isinstance(v, str) and 1 <= len(v) <= 40 and not _THREE_DIGITS.search(v):
                        vals.setdefault(k, set()).add(v)
                        cnt[k] = cnt.get(k, 0) + 1
            total = max(1, len(self.rows))
            labels = self.enum_labels()
            bs = None
            for k, d in vals.items():
                if cnt[k] * 5 < total * 4 or len(d) > 40:
                    continue
                share = sum(1 for x in d if x.strip().lower() in labels) / len(d)
                score = (share, -len(d), cnt[k], sum(len(x) for x in d) / len(d))
                if bs is None or score > bs:
                    best, bs = k, score
        self.cat_cache = (ck, best)
        return best

    def label_of(self, i, full=False):
        ck = self.cat_key()
        if ck is None:
            return ""
        rec = (self.full.get(i) if full else None) or self.rows.get(i) or {}
        v = rec.get(ck)
        return "" if v is None else str(v)

    def label_matches(self, label):
        lw = words(label)
        ls = {s for s in stems(label) if len(s) >= 4}
        for it in self.items:
            if lw == words(it.shelf) or lw == words(it.name):
                return True
            if ls & {s for s in (stems(it.shelf) | stems(it.name)) if len(s) >= 4}:
                return True
        return self.owner(label) > 0

    def key_table(self):
        ck = self.cat_key()
        groups = {}
        for i in self.order:
            rec = self.full.get(i)
            if rec is None:
                continue
            ab = attr_block(rec) or {}
            cv = rec.get(ck) if ck is not None else None
            lab = str(cv) if cv is not None and str(cv) != "" else "listings"
            g = groups.setdefault(lab, {"n": 0, "keys": {}})
            g["n"] += 1
            seen = set()
            for k, v in ab.items():
                wf = words(k)
                if not wf or wf in seen:
                    continue
                seen.add(wf)
                slot = g["keys"].setdefault(wf, {"count": 0, "shown": {}, "meas": {}, "distinct": []})
                slot["count"] += 1
                sv = str(v).strip().lower()
                slot["shown"][i] = sv
                mv = FIRST_SPELLING.get(v, v) if isinstance(v, str) else v
                slot["meas"][i] = str(mv).strip().lower()
                if sv not in slot["distinct"]:
                    slot["distinct"].append(sv)
        matched = [lab for lab in groups if self.label_matches(lab)]
        keep = matched if matched else list(groups)
        keep.sort(key=lambda lab: -groups[lab]["n"])
        rows = []
        for lab in keep:
            g = groups[lab]
            ks = sorted(g["keys"].items(), key=lambda kv: (-kv[1]["count"], len(kv[0])))
            kept = []
            for wf, slot in ks:
                mv = list(slot["meas"].values())
                if not mv:
                    continue
                mean = sum(len(x) for x in mv) / len(mv)
                if mean > 40 or sum(1 for x in mv if _SLASH_SP.search(x)) * 2 >= len(mv):
                    continue
                if len(mv) >= 4 and len(set(mv)) == len(mv) and mean > 12:
                    sets = [set(_LETTERS3.findall(x)) for x in mv]
                    sharing = 0
                    for j, sj in enumerate(sets):
                        others = set()
                        for jj, sk in enumerate(sets):
                            if jj != j:
                                others |= sk
                        if sj & others:
                            sharing += 1
                    if sharing * 2 < len(mv):
                        continue
                twin = None
                for kk in kept:
                    if self.twins(kk, (wf, slot)):
                        twin = kk
                        break
                if twin is not None:
                    ts = twin[1]
                    for lid, sv in slot["shown"].items():
                        if lid not in ts["meas"]:
                            ts["shown"][lid] = sv
                            ts["meas"][lid] = slot["meas"][lid]
                    for sv in slot["distinct"]:
                        if sv not in ts["distinct"]:
                            ts["distinct"].append(sv)
                    ts["count"] = len(ts["meas"])
                    continue
                kept.append((wf, slot))
            kept.sort(key=lambda kv: -kv[1]["count"])
            for wf, slot in kept[:KEY_TABLE_SIZE]:
                rows.append((lab, wf, slot["count"], [x[:40] for x in slot["distinct"][:4]]))
        return rows

    def twins(self, a, b):
        wa, sa = a
        wb, sb = b
        A, B = set(wa.split()), set(wb.split())
        if not A or not B or not (A & B):
            return False

        def agree(x, y):
            if x == y:
                return True
            xw, yw = _WORDRUN.findall(x), _WORDRUN.findall(y)
            if len(xw) <= len(yw):
                sh, lg = xw, yw
            else:
                sh, lg = yw, xw
            return bool(sh) and all(w in lg for w in sh) and len(lg) <= 2 * len(sh) + 2

        shared = [lid for lid in sa["meas"] if lid in sb["meas"] and sa["meas"][lid].strip() and sb["meas"][lid].strip()]
        ag = sum(1 for lid in shared if agree(sa["meas"][lid], sb["meas"][lid]))
        if not (A <= B or B <= A):
            return len(shared) >= 2 and ag == len(shared)
        if shared:
            return ag * 2 > len(shared)
        return bool({x for x in sa["distinct"] if x} & {x for x in sb["distinct"] if x})

    def not_stated(self, label, key, shown):
        o = self.owner(label)
        if not o:
            return ""
        sw = set(_ALNUM3.findall(" ".join(shown).lower()))
        for r in self.live_of(self.items[o - 1]):
            prop, _, val = r.partition(":")
            if _E2_CMP.search(val):
                continue
            vw = _ALNUM3.findall(val.lower())
            if prop.strip() and words(prop) != key and (stems(prop) & stems(key)) and vw and not all(w in sw for w in vw):
                return " [not the stated " + prop.strip() + ": another property]"
        return ""

    def item_groups(self):
        ck = self.cat_key()
        groups = {}
        for i in self.order:
            row = self.rows.get(i) or {}
            cv = row.get(ck) if ck is not None else None
            lab = "" if cv is None else str(cv)
            groups.setdefault(lab, []).append(i)
        matched = [lab for lab in groups if self.label_matches(lab)]
        pool = matched or list(groups)
        pool.sort(key=lambda lab: -len(groups[lab]))
        return [groups[lab] for lab in pool[:max(1, len(self.items))]]

    def single_target(self, tool):
        sc = self.schemas.get(tool)
        if not isinstance(sc, dict):
            return None
        props = sc.get("properties") if isinstance(sc.get("properties"), dict) else {}
        req = [r for r in (sc.get("required") or []) if isinstance(r, str)] if isinstance(sc.get("required"), list) else []
        texts = [k for k, p in props.items() if isinstance(p, dict) and "string" in kinds(p) and "enum" not in p]
        tgt = next((r for r in req if r in texts), None)
        if tgt is None and len(texts) == 1:
            tgt = texts[0]
        if tgt is None or any(r != tgt for r in req):
            return None
        return tgt

    def price(self, i):
        if not self.price_key:
            return None
        v = (self.rows.get(i) or {}).get(self.price_key)
        if isinstance(v, dict):
            for x in v.values():
                if is_num(x):
                    return float(x)
            return None
        if isinstance(v, str):
            m = _PRICE_TXT.fullmatch(v)
            return float(m.group(1).replace(",", "")) if m else None
        if is_num(v):
            return float(v)
        return None

    def sold_out(self, i):
        return i in self.unavail or i in self.gone

    def buyable(self, i):
        if self.sold_out(i):
            return False
        if not self.stock_key:
            return True
        v = (self.rows.get(i) or {}).get(self.stock_key)
        if isinstance(v, str):
            s = v.strip()
            return not (V4_WHOLE.fullmatch(s) or V4_PART.search(s))
        if v is False:
            return False
        if is_num(v) and v <= 0:
            return False
        return True

    def records_of(self, obs):
        out = []
        if isinstance(obs, dict):
            i = self.listing_id(obs, False, 0)
            if i:
                return [(i, obs)]
            for v in obs.values():
                if isinstance(v, list):
                    for e in v:
                        j = self.listing_id(e, True, 1) if isinstance(e, dict) else None
                        if j:
                            out.append((j, e))
                elif isinstance(v, dict):
                    j = self.listing_id(v, False, 1)
                    if j:
                        out.append((j, v))
                    else:
                        for x in v.values():
                            if isinstance(x, list):
                                for e in x:
                                    jj = self.listing_id(e, True, 2) if isinstance(e, dict) else None
                                    if jj:
                                        out.append((jj, e))
        elif isinstance(obs, list):
            for e in obs:
                j = self.listing_id(e, True, 1) if isinstance(e, dict) else None
                if j:
                    out.append((j, e))
        return out

    def note_view(self, tool, obs):
        for i, rec in self.records_of(obs):
            ks = set(rec.keys())
            self.tool_keys.setdefault(tool, set()).update(ks)
            vk = self.view_keys.get(i)
            if vk and vk[0] == self.version:
                vk[1].update(ks)
            else:
                self.view_keys[i] = (self.version, set(ks))

    def shown_already(self, tool, i):
        tk = self.tool_keys.get(tool)
        vk = self.view_keys.get(i)
        return bool(tk) and vk is not None and vk[0] == self.version and tk <= vk[1] and i not in self.gone

    def read_shape(self, tool, obs):
        if tool in self.shapes:
            return self.shapes[tool]
        if not isinstance(obs, dict):
            return None
        cands = [k for k, v in obs.items() if isinstance(v, list) and len(v) >= 2 and all(isinstance(e, dict) for e in v)]
        if not cands:
            return None
        self.shapes[tool] = None
        sample = {k: (v[:3] if k in cands else v) for k, v in obs.items()}
        p = (SHAPE_PROMPT + "\n\nTOOL: " + tool + " | " + dump(self.schemas.get(tool) or {}) +
             "\n\nRESULT (only its first rows are shown):\n" + dump(clip(sample, 120))[:4000])
        ans = self.json_ask(p, [LIGHT, HEAVY], 2500) or {}
        rk = ans.get("rows")
        if not isinstance(rk, str) or rk not in cands:
            return None
        props = (self.schemas.get(tool) or {}).get("properties") or {}
        first = obs[rk][0]

        def ok(v, where):
            return v if isinstance(v, str) and v in where else None

        sh = {"rows": rk, "count": ok(ans.get("count"), obs), "next": ok(ans.get("next"), obs),
              "next_arg": ok(ans.get("next_arg"), props), "price": ok(ans.get("price"), first), "stock": ok(ans.get("stock"), first)}
        if sh["count"] is not None:
            c = obs.get(sh["count"])
            if isinstance(c, bool) or not isinstance(c, int):
                sh["count"] = None
        self.shapes[tool] = sh
        if self.price_key is None and sh["price"]:
            self.price_key = sh["price"]
        if self.stock_key is None and sh["stock"]:
            self.stock_key = sh["stock"]
        self.trace.append({"kind": "shape", "tool": tool, "shape": sh})
        return sh

    def paging(self, tool, obs):
        sh = self.read_shape(tool, obs)
        if not sh or not sh.get("count") or not sh.get("next") or not sh.get("next_arg") or not isinstance(obs, dict):
            return None
        rows = obs.get(sh["rows"])
        if not isinstance(rows, list) or not rows:
            return None
        c = obs.get(sh["count"])
        if isinstance(c, bool) or not isinstance(c, int):
            return None
        nx = obs.get(sh["next"])
        if nx is not None and (isinstance(nx, bool) or not isinstance(nx, (str, int))):
            return None
        return (c, len(rows), sh["next_arg"], nx)

    def price_sorted(self, obs):
        ps = [self.price(i) for i, _ in self.records_of(obs)]
        if len(ps) < 3 or any(p is None for p in ps):
            return False
        return all(ps[k] <= ps[k + 1] for k in range(len(ps) - 1))

    def auto_page(self, tool, args, obs):
        self.paged = []
        if not PICKS3.fullmatch(self.pick()):
            return ""
        pl = self.paging(tool, obs)
        if not pl:
            return ""
        total, shown, arg, nx = pl
        sent = args.get(arg)
        if isinstance(sent, bool):
            later = sent
        elif isinstance(sent, int):
            later = sent != 0 and sent != 1
        elif sent is None or sent == "" or sent == [] or sent == {}:
            later = False
        else:
            later = True
        if nx is None or later or total <= shown:
            return ""
        if self.pick() == "cheapest" and self.price_sorted(obs):
            return ""
        need = -(-(total - shown) // shown)
        if need > 2 and self.pages_read + 2 <= AUTO_PAGES and self.left() - self.reserve() - 2 >= 12:
            need = 2
        if need > 2 or self.pages_read + need > AUTO_PAGES or self.left() - self.reserve() - need < 12:
            return ("\n[Cairn] This search matched %d listings but displayed only %d, and not sorted by price; the pick weighs "
                    "every listing that fits. Search again with tighter words, namely the value the requirement names, or request "
                    "the next page by sending %s set to %s." % (total, shown, arg, dump(nx)))
        lines = []
        cur = nx
        read = 0
        for _ in range(need):
            a = dict(args)
            a[arg] = cur
            a, faults = shape_args(a, self.schemas.get(tool) or {})
            if faults:
                break
            r = self.env(tool, a)
            if r is None or self.finished:
                break
            self.pages_read += 1
            o = r.get("observation")
            self.observe(tool, o)
            self.paged.append(o)
            txt = self.show(o)
            self.read_cache[tool + dump(a)] = (self.version, self.step, txt)
            lines.append(str(arg) + "=" + dump(cur) + ": " + txt)
            read += 1
            pl2 = self.paging(tool, o)
            if not pl2 or pl2[3] is None:
                cur = None
                break
            cur = pl2[3]
        self.trace.append({"kind": "auto_pages", "pages": read})
        if not read:
            return ""
        out = "\n[Cairn fetched the following pages of this search by itself, one step per page]\n" + "\n".join(lines)
        if cur is not None:
            out += ("\n[Cairn] The search matched %d listings and Cairn has now read %d rows. Make the search tighter with the "
                    "value the requirement names, or keep requesting pages, so the remaining listings come into view." % (total, shown * (read + 1)))
        return out

    def cap_ignored(self, tool, args, obs):
        props = (self.schemas.get(tool) or {}).get("properties") or {}
        rank = self.ceiling_args(tool)
        caps = []
        for k, v in args.items():
            if k not in props or not is_num(v):
                continue
            p = props[k] if isinstance(props[k], dict) else {}
            priced = bool(_E2_PRICED.search(str(k) + " " + str(p.get("description") or "")))
            if (_E2_CAPW.search(str(k)) and priced) or (len(rank) == 1 and rank[0] == k):
                caps.append((v, k))
        if not caps or not self.price_key:
            return ""
        cap, name = min(caps, key=lambda x: x[0])
        over = [i for i, _ in self.records_of(obs) if (self.price(i) or 0) > cap]
        if not over:
            return ""
        others = []
        for k, v in args.items():
            p = props.get(k)
            if isinstance(v, str) and isinstance(p, dict) and isinstance(p.get("enum"), list):
                alt = [o for o in p["enum"] if o != v]
                if alt:
                    others.append(str(k) + "=" + dump(alt[0]))
        hint = ""
        if others:
            hint = (" Browse the category instead: set " + ", ".join(others) + " while keeping the same " + str(name) +
                    ", so that only the cheaper listings show.")
        return "\n[Cairn] This search did not honour %s at %s: %d of its rows are priced above it.%s" % (name, gnum(cap), len(over), hint)

    def cheapest_here(self, obs):
        if self.pick() != "cheapest" or not self.price_key:
            return ""
        ids = []
        for o in [obs] + list(self.paged):
            for i, _ in self.records_of(o):
                if i not in ids:
                    ids.append(i)
        ok = [(self.price(i), i) for i in ids if self.buyable(i) and self.price(i) is not None]
        if len(ok) < 2:
            return ""
        ok.sort()
        return "\n[Cairn] Buyable rows of this result from the lowest price up: " + ", ".join(i + " (" + gnum(p) + ")" for p, i in ok[:6])

    def wider_hold(self):
        if self.wider_held or self.pick() != "cheapest" or self.left() < 14 + 2 * len(self.items):
            return ""
        self.wider_held = True
        priced = [i + " at " + gnum(self.price(i)) for i in self.cart_ids() if self.price(i) is not None]
        return (HOLD_OPEN + " %d steps remain and the pick is cheapest. A search may match only part of a listing's text, so "
                "searching by a requirement's value surfaces only part of the listings that fit, and rows arrive unordered by "
                "price. Ahead of any checkout, for each item run a few extra searches under different product names: the "
                "product's bare one-word name, its synonyms, and words lifted from titles of fitting listings already seen. "
                "Consider only rows that can be bought and cost less than that item's current cart line%s. Then check the "
                "attribute records of the lowest-priced of those rows, replace the cart line with any one that fits, and then "
                "check out." % (self.left(), (" (" + "; ".join(priced) + ")") if priced else ""))

    def fact_note(self, tool, has):
        if has:
            self.facts[tool] = True
        elif self.facts.get(tool) is not True:
            self.bare[tool] = self.bare.get(tool, 0) + 1
            if self.bare[tool] >= 2:
                self.facts[tool] = False

    def lists_things(self, tool):
        t = self.single_target(tool)
        if t and (V10_SHELF.search(under(t)) or V14_QUERY.search(under(t))):
            return True
        return tool in self.shapes


_SNAKE = re.compile(r"[\s_.\-]+")
_RUN4 = re.compile(r"[a-z]{4,}")
_NAMEWORD = re.compile(r"[a-z][a-z'\-]{2,}")


def snake(k):
    return _SNAKE.sub("_", str(k).strip()).lower()


class E3:
    def fill_facts(self, ids, reserve):
        ft = self.facts_tool()
        tgt = self.single_target(ft) if ft else None
        if (not ft or not tgt) and self.cmp_facts() is not True:
            return []
        wanted = [i for i in ids if i in self.rows and i not in self.full and not self.sold_out(i)]
        texts = []
        unread = []
        cmp = self.roles.get("compare")
        ct = self.cmp_target()
        while cmp and ct and self.cmp_facts() is True and len(wanted) >= 2 and self.left() > reserve and not self.finished and not self.rushed():
            room = self.cmp_room()
            batch = wanted[:room]
            wanted = wanted[room:]
            a, f = shape_args({ct: batch}, self.schemas.get(cmp) or {})
            if f:
                wanted = batch + wanted
                break
            r = self.env(cmp, a)
            if r is None:
                wanted = batch + wanted
                break
            o = r.get("observation")
            self.observe(cmp, o)
            self.note_view(cmp, o)
            recs = self.records_of(o)
            for i, rec in recs:
                texts.append(i + ": " + self.bshow(rec, 1500))
            if recs:
                self.cmp_good = max(self.cmp_good, len(recs))
                unread += [i for i in batch if i not in self.full]
                continue
            self.cmp_bad = min(self.cmp_bad or 999, len(batch))
            wanted = batch + wanted
            if self.cmp_room() >= len(batch):
                break
        if not ft or not tgt:
            if texts:
                self.trace.append({"kind": "fill_facts", "texts": len(texts)})
            return texts
        for i in unread + [w for w in wanted if w not in unread]:
            if self.left() <= reserve or self.finished or self.facts.get(ft) is False or self.rushed():
                break
            if (ft, i) in self.factless:
                continue
            a, f = shape_args({tgt: i}, self.schemas.get(ft) or {})
            if f:
                break
            r = self.env(ft, a)
            if r is None:
                break
            o = r.get("observation")
            self.observe(ft, o)
            self.note_view(ft, o)
            if isinstance(o, dict) and self.listing_id(o, False, 0):
                self.fact_note(ft, bool(attr_block(o)))
            texts.append(i + ": " + self.bshow(o, 1500))
        if texts:
            self.trace.append({"kind": "fill_facts", "texts": len(texts)})
        return texts

    def show_links(self, ids, reserve):
        tpl = self.value_template()
        if not tpl or (len(self.items) < 2 and len(ids) < 2):
            return
        tool, fixed, field = tpl
        for i in ids:
            fi = self.fit_index()
            code = (fi.get(i) or {}).get("pointer")
            if not code or code in self.link_tried:
                continue
            if any(m.get("own") == code for m in fi.values()):
                continue
            if self.left() <= reserve or self.finished or self.rushed():
                return
            self.link_tried.add(code)
            a = dict(fixed)
            a[field] = code
            a, f = shape_args(a, self.schemas.get(tool) or {})
            if f:
                return
            r = self.env(tool, a)
            if r is None:
                return
            self.observe(tool, r.get("observation"))
            self.trace.append({"kind": "show_links", "code": code})
            fi = self.fit_index()
            self.fill_facts([j for j, m in fi.items() if m.get("own") == code], max(reserve, self.reserve() + 6))

    def ceiling_args(self, tool):
        props = (self.schemas.get(tool) or {}).get("properties") or {}
        cands = [k for k, p in props.items() if isinstance(p, dict) and ("integer" in kinds(p) or "number" in kinds(p))
                 and not V7_NONPRICE.search(str(k)) and not V9_LOW.search(snake(k))]
        ev = self.ceiling_evidence(tool)
        proved = [k for k in cands if any(v == "holds" and a == k for (a, m), v in ev.items())]
        maxn = [k for k in cands if V6_MAX.search(snake(k))]
        money = [k for k in cands if V8_PRICE.search(snake(k))]
        both = [k for k in maxn if k in money]
        for g in (proved, both, money, maxn):
            if g:
                return g
        return []

    def ceiling_evidence(self, tool):
        ck = self.cat_key()
        pools = {}
        for i in self.rows:
            p = self.price(i)
            if p is not None:
                pools.setdefault(self.label_of(i) if ck else "", []).append(p)
        props = (self.schemas.get(tool) or {}).get("properties") or {}
        ev = {}
        for t, args, res in list(self.remembered.values()):
            if t != tool:
                continue
            recs = self.records_of(res)
            if not recs or any(self.price(i) is None for i, _ in recs):
                continue
            mode = tuple(sorted((k, dump(v)) for k, v in args.items() if isinstance(props.get(k), dict) and isinstance(props[k].get("enum"), list)))
            pool = []
            if ck:
                for lab in {self.label_of(i) for i, _ in recs}:
                    pool += pools.get(lab, [])
            dear = max(self.price(i) for i, _ in recs)
            for k, v in args.items():
                if k not in props or not is_num(v):
                    continue
                key = (k, mode)
                if dear > v:
                    ev[key] = "fails"
                    continue
                if ev.get(key) == "fails":
                    continue
                if pool and (sum(1 for p in pool if p <= v) / len(pool)) ** len(recs) < LIMIT_CHANCE:
                    ev[key] = "holds"
        return ev

    def has_words(self, tool, s, shelf):
        props = (self.schemas.get(tool) or {}).get("properties") or {}
        for k, v in s.items():
            if k == shelf or (isinstance(props.get(k), dict) and isinstance(props[k].get("enum"), list)):
                continue
            if isinstance(v, str) and v.strip() and V14_QUERY.search(under(k)):
                return True
        return False

    def capped_template(self):
        for tool in self.names:
            sc = self.schemas.get(tool) or {}
            props = sc.get("properties") if isinstance(sc.get("properties"), dict) else {}
            ceil = self.ceiling_args(tool)
            shelf = [k for k, p in props.items() if isinstance(p, dict) and "string" in kinds(p) and "enum" not in p and V10_SHELF.search(under(k))]
            if len(ceil) != 1 or len(shelf) != 1:
                continue
            c = ceil[0]
            ev = self.ceiling_evidence(tool)
            learned = [(dict(m), v) for (a, m), v in ev.items() if a == c]
            req = sc.get("required") if isinstance(sc.get("required"), list) else []
            opts = [k for k, p in props.items() if isinstance(p, dict) and isinstance(p.get("enum"), list) and len(p["enum"]) >= 2]
            single = len(opts) == 1 and opts[0] in req
            fixed = {}
            for k in opts:
                en = props[k]["enum"]
                val, have = None, False
                for m, v in learned:
                    if v == "holds" and k in m:
                        val, have = json.loads(m[k]), True
                        break
                if not have:
                    for s in reversed(self.searched):
                        if s.get(shelf[0]) not in (None, "") and k in s and not self.has_words(tool, s, shelf[0]):
                            val, have = s[k], True
                            break
                if not have:
                    lm = [o for o in en if isinstance(o, str) and V11_LISTMODE.search(o)]
                    if len(lm) == 1:
                        val, have = lm[0], True
                if not have and single:
                    worded = {dump(s[k]) for s in self.searched if k in s and self.has_words(tool, s, shelf[0])}
                    if worded:
                        never = [o for o in en if dump(o) not in worded]
                        if len(never) == 1:
                            val, have = never[0], True
                if single:
                    spoiled = {m[k] for m, v in learned if v == "fails" and k in m}
                    if spoiled and (not have or dump(val) in spoiled):
                        rest = [o for o in en if dump(o) not in spoiled]
                        if len(rest) == 1:
                            val, have = rest[0], True
                        else:
                            have = False
                if not have:
                    return None
                fixed[k] = val
            return (tool, fixed, shelf[0], c)
        return None

    @soft("")
    def list_below(self, lines):
        tpl = self.capped_template()
        ck = self.cat_key()
        if not tpl or not ck:
            return ""
        tool, fixed, shelf, carg = tpl
        sc = self.schemas.get(tool) or {}
        out = []
        for line in lines:
            p = self.price(line)
            lab = (self.rows.get(line) or {}).get(ck)
            mark = (line, p, self.terms_seen)
            if p is None or p < 2 or not lab or mark in self.capped:
                continue
            self.capped.add(mark)
            txt = self.floor_walk(tool, fixed, shelf, carg, sc, lab, p, line)
            if txt:
                out.append(txt)
        return "\n".join(out)

    def floor_walk(self, tool, fixed, shelf, carg, sc, lab, p, line):
        def capped_call(cap, extra=None):
            a = dict(fixed)
            a[shelf] = lab
            a[carg] = cap
            if extra:
                a.update(extra)
            a, f = shape_args(a, sc)
            if f:
                return None
            r = self.env(tool, a)
            if r is None:
                return None
            o = r.get("observation")
            self.observe(tool, o)
            return o

        def room(need):
            return self.left() - self.reserve() >= need and not self.finished and not self.rushed()

        if self.sold_out(line):
            top = int(p)
        else:
            top = int(p) - 1 if p == int(p) else int(p)
        if top < 1 or not room(FLOOR_START):
            return ""
        lo, lo_n = 0, 0
        hi = hi_n = None
        best = None
        cap = top
        tried = set()
        for _ in range(FLOOR_PROBES):
            if cap < 1 or cap in tried or not room(FLOOR_KEEP):
                break
            tried.add(cap)
            o = capped_call(cap)
            if o is None:
                break
            recs = self.records_of(o)
            pl = self.paging(tool, o)
            cnt = pl[0] if pl else len(recs)
            per = max(pl[1] if pl else len(recs), 1)
            self.trace.append({"kind": "floor_walk", "line": line, "price": p, "ceiling": cap, "count": cnt})
            if any((self.price(i) or 0) > cap for i, _ in recs):
                return ""
            fit = per * FLOOR_PAGES
            if recs and cnt <= fit + fit // 2:
                if best is None or abs(cnt - fit) < abs(best[3] - fit):
                    best = (cap, o, pl, cnt, per)
                if cnt > fit - per:
                    break
                lo, lo_n = cap, cnt
                if hi is None:
                    break
            elif not recs:
                if hi is None:
                    return ""
                lo, lo_n = cap, 0
            else:
                hi, hi_n = cap, cnt
            want = fit
            below = sorted(self.price(i) for i in self.order if self.price(i) is not None and lo < self.price(i) < hi
                           and str(self.label_of(i)).strip().lower() == str(lab).strip().lower())
            nxt = None
            if below and hi_n > lo_n:
                k = int(len(below) * (want - lo_n) / (hi_n - lo_n))
                nxt = int(below[min(max(k, 0), len(below) - 1)])
            if nxt is None or not lo < nxt < hi:
                nxt = (lo + hi) // 2
            cap = nxt
        if not best:
            return ""
        cap, o, pl, cnt, per = best
        texts = [self.show(o)]
        cur = pl[3] if pl else None
        for _ in range(min(-(-cnt // per), FLOOR_PAGES) - 1):
            if cur is None or not room(FLOOR_KEEP):
                break
            o2 = capped_call(cap, {pl[2]: cur})
            if o2 is None:
                break
            texts.append(self.show(o2))
            pl2 = self.paging(tool, o2)
            cur = pl2[3] if pl2 else None
        return ("[Cairn listed the %d lowest-priced listings of %s at or under %s by itself, one step per call; a cheaper one that "
                "meets every requirement replaces the carted line]\n" % (cnt, lab, gnum(cap))) + "\n".join(texts)

    def cheaper_pool(self, line, p, lab):
        cart = set(self.cart_ids())
        key = lab.strip().lower()
        pool = [i for i in self.order if i not in cart and i not in self.full and self.buyable(i)
                and self.label_of(i).strip().lower() == key and self.price(i) is not None and self.price(i) < p]
        pool.sort(key=lambda i: self.price(i))
        return pool

    def cheaper_rows(self):
        if self.pick() != "cheapest":
            return []
        ck = self.cat_key()
        mark = self.cart_mark() + "#" + str(self.version)
        if not ck or mark in self.cheaper_marks:
            return []
        self.cheaper_marks.add(mark)
        lines = self.cart_ids()
        self.list_below(lines)
        room = self.cmp_room() if self.cmp_facts() is True else 0
        picks = []
        for line in lines:
            p = self.price(line)
            lab = self.label_of(line)
            if p is None or not lab:
                continue
            pool = self.cheaper_pool(line, p, lab)
            vr = next((i for i in pool if i in self.value_rows), None)
            if vr:
                pool = [vr] + [i for i in pool if i != vr]
            n = 0
            for i in pool:
                if n >= (room or 2):
                    break
                if i not in picks:
                    picks.append(i)
                    n += 1
        cap = room * len(lines) if room else min(6, max(1, 3 * len(lines)))
        return self.fill_facts(picks[:cap], self.reserve() + 6)

    @soft("")
    def below_cart(self):
        if not self.cat_key():
            return ""
        ents = []
        for line in self.cart_ids():
            p = self.price(line)
            lab = self.label_of(line)
            if p is None or not lab:
                continue
            for i in self.cheaper_pool(line, p, lab)[:CHEAPER_SHOWN]:
                ents.append(i + " at " + gnum(self.price(i)))
        if not ents:
            return ""
        return "These rows have not been read yet and cost less than a line of the cart: " + ", ".join(ents) + "."

    def title_key(self):
        stamp = (len(self.rows), self.absorbs)
        if self.title_cache is not None and self.title_cache[0] == stamp:
            return self.title_cache[1]
        ck = self.cat_key()
        stats = {}
        for row in self.rows.values():
            for k, v in row.items():
                if k == ck or not isinstance(v, str) or len(v) > TITLE_LIMIT:
                    continue
                s = stats.setdefault(k, [0, 0, 0, set()])
                s[0] += len(v.split())
                s[1] += 1
                s[2] += len(v)
                s[3].add(v)
        total = len(self.rows)
        kept = [k for k, s in stats.items() if s[1] * 5 >= total * 4 and s[0] >= 2 * s[1] and len(s[3]) * 2 >= s[1]]
        best = None
        if kept:
            most = max(len(stats[k][3]) for k in kept)
            kept = [k for k in kept if len(stats[k][3]) * 10 >= most * 9]
            best = min(kept, key=lambda k: (stats[k][2] / stats[k][1], str(k)))
        self.title_cache = (stamp, best)
        return best

    def hunt_words(self, n):
        it = self.items[n - 1]
        ck = self.cat_key()
        tk = self.title_key()
        labels = []
        nms = []
        if ck:
            for i in self.order:
                lab = self.label_of(i)
                if self.owns(n, lab):
                    labels.append(lab)
                    if tk and isinstance((self.rows.get(i) or {}).get(tk), str):
                        nms.append(self.rows[i][tk])
            for i in self.order:
                if i in self.full and self.owns(n, self.label_of(i, True)):
                    ab = attr_block(self.full[i]) or {}
                    nms.append(" ".join(v for v in ab.values() if isinstance(v, str) and len(v) <= HUNT_VALUE_LEN))
        other = set()
        for j, o in enumerate(self.items, 1):
            if j != n:
                other |= set(_RUN4.findall((o.shelf + " " + o.name).lower()))
        if labels:
            cnt = {}
            for lab in labels:
                cnt[lab.lower()] = cnt.get(lab.lower(), 0) + 1
            home = max(cnt, key=lambda x: cnt[x])
        else:
            home = (it.shelf or it.name).lower()
        cands = [w for w in _RUN4.findall(home) if w not in other]
        noun = max(cands, key=len) if cands else ""
        if n in self.hunt_nonoun:
            noun = ""
        if not nms:
            return noun, []
        counts = {}
        for nm in nms:
            for w in set(_NAMEWORD.findall(nm.lower())):
                counts[w] = counts.get(w, 0) + 1
        own = roots(it.shelf) | roots(it.name)
        ceiling = max(2, int(HUNT_SHARE * len(nms)))
        ws = [w for w, c in counts.items() if 2 <= c <= ceiling and w != noun and roots(w) and not (roots(w) & own)]
        ws.sort(key=lambda w: (-counts[w], w))
        return noun, ws

    def item_rows(self, n):
        if not self.cat_key():
            return len(self.rows)
        return sum(1 for i in self.order if self.owns(n, self.label_of(i)))

    @soft("")
    def cheaper_hunt(self):
        mark = dump([self.live_of(it) for it in self.items]) + "|" + str(self.budget) + "|" + dump(sorted(self.gone))
        if self.pick() != "cheapest" or self.hunts >= HUNT_ROUNDS or mark == self.hunt_mark:
            return ""
        tpl = self.value_template()
        if not tpl or not self.price_key or self.clock() > HUNT_DEADLINE:
            return ""
        room = min(HUNT_CAP, self.left() - self.reserve() - HUNT_RESERVE - 2 * len(self.items))
        if room < 3:
            return ""
        self.hunts += 1
        self.hunt_mark = mark
        share = max(3, room // len(self.items))
        spent = 0
        new = 0
        for n in range(1, len(self.items) + 1):
            if spent >= room or self.finished:
                break
            s, g = self.item_hunt(n, tpl, min(share, room - spent))
            spent += s
            new += g
        self.trace.append({"kind": "cheaper_hunt", "steps": spent, "new_rows": new, "cart": self.cart_mark()})
        if spent:
            self.wider_held = True
            return ("Cairn itself ran %d extra searches chasing a lower price, each costing one step, and they brought up %d new rows." % (spent, new))
        return ""

    def item_hunt(self, n, tpl, room):
        tool, fixed, field = tpl
        sc = self.schemas.get(tool) or {}
        tried = self.hunt_tried.setdefault(n, set())
        noun, _ = self.hunt_words(n)
        vals = [v for v, _f in self.value_words(n)]
        st = {"spent": 0, "gain": 0, "idle": 0, "refused": False}

        def run(q):
            tried.add(q.lower())
            a = dict(fixed)
            a[field] = q
            a, f = shape_args(a, sc)
            if f:
                st["refused"] = True
                return False, False
            if st["spent"] >= room or self.finished:
                return False, False
            holds = bool(vals) and all(v.lower() in q.lower() for v in vals)
            found = False
            visited = set()
            while not self.finished and self.clock() <= HUNT_DEADLINE + HUNT_GRACE:
                mk = self.call_mark(tool, a)
                if mk in visited:
                    break
                visited.add(mk)
                if mk in self.remembered:
                    o = self.remembered[mk][2]
                    got = HUNT_YIELD
                else:
                    if st["spent"] >= room:
                        break
                    before = self.item_rows(n)
                    r = self.env(tool, a)
                    if r is None:
                        break
                    st["spent"] += 1
                    o = r.get("observation")
                    self.observe(tool, o)
                    got = self.item_rows(n) - before
                    st["gain"] += got
                    st["idle"] = 0 if got else st["idle"] + 1
                recs = self.records_of(o)
                if recs:
                    found = True
                if holds:
                    self.value_rows.update(i for i, _ in recs)
                pl = self.paging(tool, o)
                if not pl or pl[3] is None or (got < HUNT_YIELD and pl[0] > HUNT_WHOLE):
                    break
                a2 = dict(a)
                a2[pl[2]] = pl[3]
                a, f = shape_args(a2, sc)
                if f:
                    break
            return True, found

        key = (n, tuple(vals))
        if key not in self.hunt_stems:
            tries = []
            if vals:
                tries += [" ".join(vals + [noun]), " ".join(vals)]
            if len(vals) >= 2:
                tries.append(" ".join(vals[:-1] + [noun]))
            if noun:
                tries.append(noun)
            uniq = []
            for t in tries:
                t = t.strip()
                if t not in uniq:
                    uniq.append(t)
            stem = None
            for t in uniq:
                issued, found = run(t)
                if not issued:
                    return st["spent"], st["gain"]
                if found:
                    stem = t
                    break
                if noun and t == noun:
                    self.hunt_nonoun.add(n)
                    noun = ""
            self.hunt_stems[key] = stem or ""
        stem = self.hunt_stems[key]
        while st["spent"] < room and st["idle"] < HUNT_IDLE and not st["refused"] and not self.finished and self.clock() <= HUNT_DEADLINE + HUNT_GRACE:
            _, ws = self.hunt_words(n)
            sw = set(stem.lower().split())
            ws = [w for w in ws if (w + " " + stem).strip().lower() not in tried and w not in sw]
            if not ws:
                break
            run((ws[0] + " " + stem).strip())
        return st["spent"], st["gain"]

    @soft(list)
    def fit_hunt(self):
        tpl = self.value_template()
        if self.fit_hunted or self.clock() > HUNT_DEADLINE or not tpl:
            return []
        res = self.reserve() + len(self.items) + 1
        spare = self.left() - res
        if spare < 3:
            return []
        self.fit_hunted = True
        nitems = len(self.items)
        covered = [self.label_of(i) for i in self.cart_ids() if self.held(i) > 0]
        hunt = [n for n in range(1, nitems + 1) if not any(self.owns(n, lab) for lab in covered)] or list(range(1, nitems + 1))
        wanted = {n: [t for v, _ in self.value_words(n) for t in value_tokens(v)] for n in hunt}
        tool, fixed, field = tpl
        walked = self.page_walk(tool, wanted, min(FIT_PAGES, spare // 2))
        sroom = min(HUNT_CAP, self.left() - self.reserve() - HUNT_RESERVE)
        searches = 0
        sc = self.schemas.get(tool) or {}
        if sroom >= 3:
            share = max(2, sroom // len(hunt))
            for n in hunt:
                vals = [v for v, _ in self.value_words(n)]
                noun, ws = self.hunt_words(n)
                qs = []
                for s in self.series_for(n)[:LINK_SEARCHES]:
                    qs.append(s + " " + (vals[0] if vals else "") + " " + noun)
                for v in vals:
                    qs.append(v + " " + noun)
                if noun:
                    qs += vals
                for w in ws[:FIT_WORDS]:
                    qs.append(w + " " + noun)
                if noun:
                    qs.append(noun)
                uniq = []
                for q in qs:
                    q = q.strip()
                    if q and q not in uniq:
                        uniq.append(q)
                used = 0
                for q in uniq:
                    if searches >= sroom or used >= share or self.finished or self.clock() > HUNT_DEADLINE + HUNT_GRACE:
                        break
                    a = dict(fixed)
                    a[field] = q
                    a, f = shape_args(a, sc)
                    if f:
                        continue
                    r = self.env(tool, a)
                    if r is None:
                        return []
                    searches += 1
                    used += 1
                    self.observe(tool, r.get("observation"))
        texts = []
        ck = self.cat_key()
        for n in hunt:
            picks = [i for i in self.order if i not in self.full and self.buyable(i) and (not ck or self.owns(n, self.label_of(i)))]
            if is_num(self.budget):
                picks = [i for i in picks if (self.price(i) or 0) <= self.budget]
            toks = set(wanted[n])
            picks.sort(key=lambda i: (-len(toks & text_words(dump(self.rows.get(i) or {}))), self.price(i) is None, self.price(i) or 0))
            picks = picks[:FIT_OPENS]
            for k in range(0, len(picks), 4):
                if self.clock() > HUNT_DEADLINE + HUNT_GRACE:
                    break
                texts += self.fill_facts(picks[k:k + 4], res)
        self.trace.append({"kind": "fit_hunt", "pages": walked, "searches": searches, "opened": len(texts)})
        return texts

    def page_walk(self, tool, wanted, room):
        spent = 0
        share = max(1, room // max(1, len(wanted)))
        sc = self.schemas.get(tool) or {}
        for limit in (share, room):
            for n, toks in wanted.items():
                stop = min(room, spent + limit)
                tset = set(toks)
                for t, args, res in list(self.remembered.values()):
                    if t != tool:
                        continue
                    txt = " ".join(v.lower() for v in args.values() if isinstance(v, str))
                    if not (text_words(txt) & tset):
                        continue
                    owners = {self.owner(self.label_of(i)) for i, _ in self.records_of(res)}
                    if owners and 0 not in owners and n not in owners:
                        continue
                    o = res
                    a = dict(args)
                    visited = set()
                    while spent < stop and not self.finished:
                        pl = self.paging(tool, o)
                        if not pl or pl[3] is None:
                            break
                        a2 = dict(a)
                        a2[pl[2]] = pl[3]
                        a2, f = shape_args(a2, sc)
                        if f:
                            break
                        m2 = self.call_mark(tool, a2)
                        if m2 in visited:
                            break
                        visited.add(m2)
                        a = a2
                        if m2 in self.remembered:
                            o = self.remembered[m2][2]
                            continue
                        r = self.env(tool, a2)
                        if r is None:
                            return spent
                        spent += 1
                        o = r.get("observation")
                        self.observe(tool, o)
        return spent


_WS = re.compile(r"\s+")


class E4:
    def call_mark(self, tool, args):
        props = (self.schemas.get(tool) or {}).get("properties") or {}
        kept = {}
        for k in sorted(args, key=str):
            v = args[k]
            p = props.get(k) if isinstance(props.get(k), dict) else {}
            if isinstance(v, int) and not isinstance(v, bool):
                if ("minimum" in p and v == p["minimum"]) or ("default" in p and v == p["default"]):
                    continue
                if v == 1 and self.page_arg.get(tool) == k and "minimum" not in p and "default" not in p:
                    continue
            if isinstance(v, str):
                v = _WS.sub(" ", v.lower()).strip()
            kept[k] = v
        return tool + dump(kept)

    def note_read(self, tool, args, obs):
        r = self.roles
        page = r.get("offer") or r.get("open")
        if tool in (page, r.get("compare"), r.get("ask"), r.get("cart"), r.get("cart_view"), r.get("buy"), r.get("refuse")):
            return
        self.new_query(tool, args)
        if isinstance(obs, (dict, list)) and not failure_only(obs):
            self.remembered[self.call_mark(tool, args)] = (tool, dict(args), obs)

    def new_query(self, tool, args):
        kind = dump({k: v for k, v in args.items() if not (isinstance(v, int) and not isinstance(v, bool))})
        mem = self.page_queries.setdefault(tool, set())
        if kind in mem:
            return False
        mem.add(kind)
        return True

    def low_of(self, tool, k):
        p = ((self.schemas.get(tool) or {}).get("properties") or {}).get(k)
        mn = p.get("minimum") if isinstance(p, dict) else None
        return mn if isinstance(mn, int) and not isinstance(mn, bool) else 1

    @soft("")
    def late_page(self, tool, args, obs):
        if tool in self.page_arg or not isinstance(obs, dict):
            return ""
        props = (self.schemas.get(tool) or {}).get("properties") or {}
        cands = [k for k, v in args.items() if isinstance(v, int) and not isinstance(v, bool) and k in props and v > self.low_of(tool, k)]
        if len(cands) != 1 or self.left() <= self.reserve() + 4:
            return ""
        sh = self.read_shape(tool, obs)
        if not sh or not sh.get("count") or not sh.get("next") or obs.get(sh["next"]) is not None:
            return ""
        rows = obs.get(sh["rows"])
        c = obs.get(sh["count"])
        if not isinstance(rows, list) or isinstance(c, bool) or not isinstance(c, int) or c <= len(rows):
            return ""
        k = cands[0]
        lo = self.low_of(tool, k)
        a = dict(args)
        a[k] = lo
        a, f = shape_args(a, self.schemas.get(tool) or {})
        if f:
            return ""
        r = self.env(tool, a)
        if r is None:
            return ""
        o = r.get("observation")
        self.observe(tool, o)
        rows2 = o.get(sh["rows"]) if isinstance(o, dict) else None
        old = {i for i, _ in self.records_of(obs)}
        new = {i for i, _ in self.records_of(o)}
        if not isinstance(rows2, list) or len(rows2) < len(rows) or (new & old):
            return ""
        self.page_arg[tool] = k
        return ("\n[Cairn] " + str(k) + " is this search's page number, and the call just made displayed the final page. "
                "Page " + str(lo) + " of that same search:\n" + self.show(o))

    @soft(False)
    def names_code(self, args):
        said = set()
        for v in args.values():
            if isinstance(v, str):
                said.update(find_codes(v))
        if not said:
            return False
        known = set()
        for m in self.fit_index().values():
            known.update(m["models"])
            known.update(m["works"])
        return bool(said & known)

    def first_look(self, tool, args, fresh):
        k = self.page_arg.get(tool)
        if not k or not fresh:
            return args
        v = args.get(k)
        if isinstance(v, int) and not isinstance(v, bool):
            lo = self.low_of(tool, k)
            if v != lo:
                a = dict(args)
                a[k] = lo
                return a
        return args

    @soft("")
    def shorter(self, tool, args, obs):
        tpl = self.value_template()
        if not tpl or tpl[0] != tool:
            return ""
        if self.left() <= self.reserve() + SHORTER_RESERVE or self.finished or not isinstance(obs, dict):
            return ""
        field = tpl[2]
        q = args.get(field)
        if not isinstance(q, str) or len(q.split()) < 3 or self.records_of(obs):
            return ""
        for v in obs.values():
            if isinstance(v, (list, str)) and v:
                return ""
            if is_num(v) and v > 0:
                return ""
        short = " ".join([w for w in q.split() if not find_codes(w)][:2])
        if not short:
            return ""
        a = {k: v for k, v in args.items() if not (isinstance(v, int) and not isinstance(v, bool))}
        a[field] = short
        a, f = shape_args(a, self.schemas.get(tool) or {})
        if f:
            return ""
        r = self.env(tool, a)
        if r is None:
            return ""
        o = r.get("observation")
        self.observe(tool, o)
        return ("\n[Cairn] No listing carries every one of those words; the identical search with only '" + short +
                "' gives:\n" + self.show(o))

    @soft("")
    def opening(self):
        tpl = self.value_template()
        if not tpl or self.budget_steps < OPEN_MIN_STEPS or len(self.items) < OPEN_MIN_ITEMS:
            return ""
        tool, fixed, field = tpl
        sc = self.schemas.get(tool) or {}
        self.gap = OPENING_GAP
        stop = self.budget_steps - self.reserve() - self.free_msgs() - LATER_STEPS_PER_ITEM * len(self.items) - HUNT_RESERVE // 2
        lines = []
        reft = {t for _, t in self.refs}
        for n, it in enumerate(self.items, 1):
            vals = []
            for m in it.musts:
                if ":" not in m or m in reft:
                    continue
                v = m.split(":", 1)[1].strip()
                if v and len(v.split()) <= 3 and not V3_OPENX.search(v):
                    vals.append(v)
            nw = it.name.split()
            noun = it.name if len(nw) <= 3 else " ".join(nw[-2:])
            tries = []
            if vals:
                tries.append(" ".join(vals[:2] + [noun]))
            if noun not in tries:
                tries.append(noun)
            for t in tries:
                a = dict(fixed)
                a[field] = t
                a, f = shape_args(a, sc)
                if f or self.finished or self.step >= stop:
                    break
                r = self.env(tool, a)
                if r is None:
                    return "\n".join(lines)
                o = r.get("observation")
                self.observe(tool, o)
                if self.records_of(o):
                    self.searched = (self.searched + [dict(a)])[-8:]
                    lines.append(t + ": " + self.show(o))
                    pl = self.paging(tool, o)
                    if pl and pl[3] is not None and self.item_rows(n) < ROWS_PER_ITEM and not self.finished and self.step < stop:
                        a2 = dict(a)
                        a2[pl[2]] = pl[3]
                        a2, f2 = shape_args(a2, sc)
                        if not f2:
                            r2 = self.env(tool, a2)
                            if r2 is not None:
                                o2 = r2.get("observation")
                                self.observe(tool, o2)
                                lines.append("next page: " + self.show(o2))
                    if self.item_rows(n) >= ROWS_PER_ITEM:
                        break
                elif failure_only(o):
                    lines.append(t + ": the store rejected the call: " + self.show(o))
                else:
                    lines.append(t + ": no rows")
        if self.rows and self.roles.get("ask") and self.free_msgs() > 0:
            found = [n for n in range(1, len(self.items) + 1) if self.item_rows(n) > 0]
            start = self.step
            while self.step - start < self.budget_steps // WIDEN_SHARE and self.step < stop and not self.finished:
                if all(self.item_records(n) >= ROWS_PER_ITEM for n in found):
                    break
                before = len(self.full)
                self.widen_compare()
                if len(self.full) <= before:
                    break
        self.gap = STORE_GAP
        for i in list(self.full):
            lines.append("read in full: " + self.page_text(i))
        ev = self.evidence_ids(list(self.full))
        if ev:
            lines.append(ev)
        return "\n".join(lines)

    def page_text(self, i):
        rec = self.full.get(i) or self.rows.get(i) or {}
        ab = attr_block(rec) or {}
        rest = {k: v for k, v in rec.items() if not isinstance(v, (dict, list))}
        return i + ": attributes " + dump(clip(ab, 120))[:PAGE_ATTR_CLIP] + " | " + dump(clip(rest, 200))[:PAGE_REST_CLIP]

    def observe(self, tool, obs):
        self.absorb(obs)
        lines = self.loose(obs)
        if not lines:
            return ""
        m = self.read_note(lines)
        if m:
            self.queued.append("(seen on " + str(tool) + ") " + m)
        return m

    def widen_compare(self):
        cmp = self.roles.get("compare")
        sc = self.schemas.get(cmp) if cmp else None
        props = sc.get("properties") if isinstance(sc, dict) and isinstance(sc.get("properties"), dict) else {}
        tgt = next((k for k, p in props.items() if isinstance(p, dict) and "array" in kinds(p)), None)
        req = sc.get("required") if isinstance(sc, dict) and isinstance(sc.get("required"), list) else []
        if not cmp or not tgt or any(x != tgt for x in req) or self.cmp_bare():
            return self.widen_single()
        if self.left() <= 12:
            return
        mx = props[tgt].get("maxItems")
        cap = min(mx if isinstance(mx, int) and not isinstance(mx, bool) else 4, self.cmp_room())
        groups = sorted(self.item_groups(), key=lambda g: sum(1 for i in g if i in self.full))
        lanes = [[i for i in g if i not in self.full] for g in groups]
        picks = []
        for rk in range(cap):
            for ln in lanes:
                if rk < len(ln):
                    picks.append(ln[rk])
        picks = picks[:cap]
        if len(picks) < 2:
            self.fill_facts(picks, 12)
            return
        a, f = shape_args({tgt: picks}, sc)
        if f:
            return
        before = len(self.full)
        r = self.env(cmp, a)
        if r is not None:
            o = r.get("observation")
            self.observe(cmp, o)
            self.note_view(cmp, o)
            recs = self.records_of(o)
            if recs:
                self.facts[cmp] = self.facts.get(cmp) is True or any(attr_block(x) for _, x in recs)
                self.cmp_good = max(self.cmp_good, len(recs))
            else:
                self.cmp_bad = min(self.cmp_bad or 999, len(picks))
            if recs and self.facts.get(cmp) is False:
                return self.widen_single()
        if len(self.full) <= before and len(picks) > 2 and self.left() > 12:
            a2, f2 = shape_args({tgt: picks[:2]}, sc)
            if not f2:
                r2 = self.env(cmp, a2)
                if r2 is not None:
                    o2 = r2.get("observation")
                    self.observe(cmp, o2)
                    self.cmp_good = max(self.cmp_good, len(self.records_of(o2)))

    def widen_single(self):
        ft = self.facts_tool()
        tgt = self.single_target(ft) if ft else None
        if not ft or not tgt:
            return
        wanted = set()
        for _, r in self.live():
            val = r.split(":", 1)[1] if ":" in r else r
            wanted |= set(_ALNUM3.findall(val.lower()))
        size = WIDEN_PER_ITEM if len(self.items) <= 2 else 4
        lanes = []
        heads = []
        for g in self.item_groups():
            opened = sum(1 for i in g if i in self.full)
            pool = [i for i in g if i not in self.full and self.buyable(i)]
            if self.pick() == "cheapest":
                pool.sort(key=lambda i: (self.price(i) is None, self.price(i) or 0))
            pool.sort(key=lambda i: -len(wanted & set(_ALNUM3.findall(dump(self.rows.get(i) or {}).lower()))))
            k = size - opened
            lanes.append(pool[:k] if k > 0 else [])
            heads.append(max(0, 4 - opened))
        first = []
        more = []
        for rk in range(4):
            for ln, hd in zip(lanes, heads):
                if rk < hd and rk < len(ln):
                    first.append(ln[rk])
        for rk in range(size):
            for ln, hd in zip(lanes, heads):
                if rk >= hd and rk < len(ln):
                    more.append(ln[rk])
        cut = max(5, 2 * len(lanes) + 2)
        got = self.fill_facts(first[:min(cut, 8)], 22)
        rest = (first[cut:] + more)[:max(0, 10 - len(got))]
        self.fill_facts(rest, 30)

    def ready_to_ask(self):
        if self.asked or not self.roles.get("ask") or self.free_msgs() <= 0:
            return False
        if self.left() <= 8 or self.clock() > INTERVIEW_DEADLINE:
            return False
        if self.turns < ASK_TURNS and any(self.item_records(n) == 0 for n in range(1, len(self.items) + 1)):
            return False
        if len(self.full) >= 3 * len(self.items) + 1:
            return True
        return self.step >= max(8, self.budget_steps // 4)


_VALUE_X = re.compile(r"\b(?:not|no|other than|unlike|alongside|listing|page|shown|at most|at least|under|over|below|above|less|more|between|within|up to|or)\b", re.I)
_LETTER = re.compile(r"[a-zA-Z]")


class E5:
    def msg_args(self, text):
        tool = self.roles.get("ask")
        sc = self.schemas.get(tool) if tool else None
        if not isinstance(sc, dict):
            sc = {}
        props = sc.get("properties") if isinstance(sc.get("properties"), dict) else {}
        req = sc.get("required") if isinstance(sc.get("required"), list) else []
        texts = [k for k, p in props.items() if isinstance(p, dict) and "string" in kinds(p) and "enum" not in p and "const" not in p]
        pool = [x for x in req if x in texts] or texts
        args = {}
        if pool:
            def key(k):
                ml = props[k].get("maxLength")
                return (not V2_NOTMSG.search(under(k)), bool(V1_MSG.search(under(k))), ml if isinstance(ml, int) and not isinstance(ml, bool) else 1000000)
            best = pool[0]
            bk = key(best)
            for k in pool[1:]:
                kk = key(k)
                if kk > bk:
                    best, bk = k, kk
            args[best] = text
        else:
            for k, p in props.items():
                if not isinstance(p, dict):
                    continue
                if "array" in kinds(p):
                    args[k] = [text]
                    break
                ip = p.get("properties")
                if isinstance(ip, dict):
                    sk = next((x for x, q in ip.items() if isinstance(q, dict) and "string" in kinds(q)), None)
                    if sk:
                        args[k] = {sk: text}
                        break
        if not args:
            return None
        for x in req:
            if x not in args:
                ok, v = filler(props.get(x) if isinstance(props.get(x), dict) else {})
                if not ok:
                    return None
                args[x] = v
        a, f = shape_args(args, sc)
        return None if f else a

    def reset_counters(self, follow=True):
        for n in range(1, len(self.items) + 1):
            self.lane_found[n] = 0
            self.lane_spent[n] = 0
            self.lane_used[n] = set()
        if follow:
            self.follow_ups = []

    def ref_line(self, line):
        many = len(self.items) > 1
        return any(line == ((("item %d: " % i) + t) if many else t) for i, t in self.refs)

    def interview(self):
        self.asked = True
        if self.free_msgs() <= 0:
            return ""
        self.widen_compare()
        cnt = max(self.msg_limit - self.msg_used, self.list_cap())
        self.plan(cnt)
        self.reset_counters()
        sent = []
        told = []
        groups = self.ask_groups(self.free_msgs()) if self.listing else []
        while self.free_msgs() > 0 and not self.finished and self.left() > 6 and self.clock() < QUESTION_DEADLINE:
            got = []
            while groups and self.listing and not got:
                got = self.group_ask(groups.pop(0), told)
            if not got:
                got = self.ask_next(told)
            if not got:
                break
            sent += got
        found = [n for n in range(1, len(self.items) + 1) if self.lane_found.get(n, 0) > 0]
        early = self.early_trail()
        vs = self.value_search(found) if found else ""
        if told:
            self.version += 1
        lines = ["[Cairn's interviewer questioned the shopper as shown, one step per question]"]
        for _n, q, a in sent:
            lines.append("Q: " + q)
            lines.append("A: " + a)
        lines.append("Firm requirements the answers added: " + ("; ".join(told) if told else "none") +
                     ". These must be applied to every pick, with a fresh search on the new values wherever one is needed.")
        refl = [t for t in told if self.ref_line(t)]
        if refl:
            lines.append("These needs get their value from a different listing: " + " | ".join(refl) +
                         ". Locate that listing, read its whole page, and then open every further listing to which that page "
                         "directs onward (only those it points onward to); the final page along this chain supplies the value; "
                         "an order is valid only once every one of them has been opened.")
        if early:
            lines.append(early)
        if vs:
            lines.append(vs)
        if self.queued:
            lines.append("[notes seen in the meantime] " + " | ".join(self.queued))
            self.queued = []
        return "\n".join(lines)

    def late_question(self):
        if self.late_asked or not self.roles.get("ask") or self.msg_used >= self.msg_limit:
            return ""
        if any(d["stage"] == "order" and d["messages"] >= 1 for d in self.duties):
            return ""
        if self.left() < 8 or self.clock() > LATE_Q_DEADLINE or not self.judges():
            return ""
        self.late_asked = True
        if not self.lanes:
            self.plan(self.list_cap() if self.listing else 1)
            self.reset_counters(False)
        old = self.budget
        told = []
        got = self.ask_next(told, 6)
        if not got:
            self.trace.append({"kind": "late_question", "sent": False})
            return ""
        if self.budget != old:
            told.append("budget now " + str(self.budget))
        if not told:
            return ""
        self.version += 1
        n, q, a = got[0]
        lines = ["[Cairn put a further question to the shopper ahead of the checkout, at a cost of one step]", "Q: " + q, "A: " + a,
                 "New firm requirements: " + "; ".join(told) + ". The checkout did not happen. Test every cart line against these "
                 "requirements (re-searching on those new values where necessary), repair the cart, and after that check out."]
        refl = [t for t in told if self.ref_line(t)]
        if refl:
            lines.append("These needs get their value from a different listing: " + " | ".join(refl) +
                         ". Locate that listing, read its whole page, and then open every further listing to which that page "
                         "directs onward (only those it points onward to); the final page along this chain supplies the value.")
        vs = self.value_search([n]) if n else ""
        if vs:
            lines.append(vs)
        return "\n".join(lines)

    def shelf_like(self, v):
        w = words(v)
        refs = []
        for it in self.items:
            refs += [it.shelf, it.name]
        ck = self.cat_key()
        if ck:
            refs += list({str(r.get(ck)) for r in self.rows.values() if r.get(ck) is not None})
        vs = {x for x in stems(v) if len(x) >= 4}
        for r in refs:
            if not r:
                continue
            if words(r) == w or vs & {x for x in stems(r) if len(x) >= 4}:
                return True
        return False

    def search_template(self):
        tool = self.roles.get("search")
        if not tool:
            return None
        sc = self.schemas.get(tool) or {}
        props = sc.get("properties") if isinstance(sc.get("properties"), dict) else {}
        req = sc.get("required") if isinstance(sc.get("required"), list) else []
        texts = [k for k, p in props.items() if isinstance(p, dict) and "string" in kinds(p) and "enum" not in p]
        named = [k for k in texts if V14_QUERY.search(under(k))]
        ck = self.cat_key()
        labels = {str(r.get(ck)).strip().lower() for r in self.rows.values() if r.get(ck) is not None} if ck else set()
        for s in reversed(self.searched):
            cands = [k for k in (named or texts) if isinstance(s.get(k), str) and _LETTER.search(s[k])]
            if not named:
                ok = []
                for k in cands:
                    vals = [x.get(k) for x in self.searched if isinstance(x.get(k), str)]
                    if len(set(vals)) >= 2 and any(len(v.split()) >= 2 for v in vals) and not any(v.strip().lower() in labels for v in vals):
                        ok.append(k)
                cands = ok
            if not cands:
                continue
            field = cands[0]
            kept = {k: v for k, v in s.items() if k != field and isinstance(props.get(k), dict) and ("enum" in props[k] or k in req)}
            for k in list(kept):
                if isinstance(kept[k], str) and k not in req and self.shelf_like(kept[k]):
                    del kept[k]
            for k in list(kept):
                if "enum" in props[k]:
                    cnt = {}
                    for x in self.searched:
                        if isinstance(x.get(field), str) and _LETTER.search(x[field]) and k in x:
                            d = dump(x[k])
                            cnt[d] = cnt.get(d, 0) + 1
                    if cnt:
                        kept[k] = json.loads(max(cnt, key=cnt.get))
            return (tool, kept, field)
        return None

    def value_words(self, n):
        it = self.items[n - 1]
        reft = {t for _, t in self.refs}
        out = []
        for r in self.live_of(it):
            if r in reft or ":" not in r:
                continue
            v = r.split(":", 1)[1].strip()
            told = r in it.told
            m = V13_FLOOR.search(v)
            if m:
                if told:
                    out.append((m.group(1).strip(), True))
                continue
            if not v or _VALUE_X.search(v):
                continue
            out.append((v, told))
        return out

    def value_template(self):
        t = self.search_template()
        if t:
            return t
        tool = self.roles.get("search")
        if not tool:
            return None
        sw = self.brief.get("search_words") if isinstance(self.brief.get("search_words"), dict) else None
        if sw:
            wt = sw.get("tool") if isinstance(sw.get("tool"), str) and sw.get("tool") in self.schemas else tool
            wprops = (self.schemas.get(wt) or {}).get("properties") or {}
            fld = sw.get("field")
            if isinstance(fld, str) and isinstance(wprops.get(fld), dict) and "string" in kinds(wprops[fld]) and "enum" not in wprops[fld]:
                a = dict(sw.get("args")) if isinstance(sw.get("args"), dict) else {}
                a[fld] = "x"
                a2, f = shape_args(a, self.schemas.get(wt) or {})
                if not f:
                    a2.pop(fld, None)
                    return (wt, a2, fld)
        sc = self.schemas.get(tool) or {}
        props = sc.get("properties") if isinstance(sc.get("properties"), dict) else {}
        req = sc.get("required") if isinstance(sc.get("required"), list) else []
        wf = [k for k, p in props.items() if isinstance(p, dict) and "string" in kinds(p) and "enum" not in p and V14_QUERY.search(under(k))]
        last = self.searched[-1] if self.searched else None
        sets = [k for k, p in props.items() if isinstance(p, dict) and isinstance(p.get("enum"), list) and len(p["enum"]) >= 2]
        modes = {}
        for k in sets:
            en = props[k]["enum"]
            qm = [o for o in en if isinstance(o, str) and V14_QUERY.search(o)]
            if len(qm) == 1:
                modes[k] = qm[0]
            elif k in req and len(en) == 2 and last is not None and k in last:
                diff = [o for o in en if o != last.get(k)]
                if len(diff) == 1:
                    modes[k] = diff[0]
        if len(wf) != 1 or len(modes) > 1 or (sets and not modes):
            return None
        base = {k: last[k] for k in req if last and k in last and k != wf[0]}
        base.update(modes)
        return (tool, base, wf[0])

    def value_search(self, items):
        tpl = self.value_template()
        if not tpl or self.left() < self.reserve() + VALUE_ROOM:
            return ""
        allow = min(VALUE_RESERVE, self.left() - self.reserve() - VALUE_RESERVE)
        tool, base, field = tpl
        sc = self.schemas.get(tool) or {}
        ck = self.cat_key()
        lines = []
        for n in items:
            ph = self.value_words(n)
            if not [v for v, t in ph if t] or allow <= 2:
                continue
            idx = [k for k, (v, t) in enumerate(ph) if t and (len(v.split()) == 1 or V12.fullmatch(v.strip()))]
            ordered = [ph[k] for k in idx] + [ph[k] for k in range(len(ph)) if k not in idx]
            reqp = [k for k, (v, t) in enumerate(ordered) if not t]
            drop = reqp[-1] if reqp else 0
            vals = [v for v, t in ordered]
            if len(vals) >= 2:
                tries = [vals, [v for k, v in enumerate(vals) if k != drop]]
            elif idx:
                tries = [[vals[0], self.items[n - 1].name], [vals[0]]]
            else:
                tries = [[vals[0]]]
            for ws in tries[:2]:
                a = dict(base)
                a[field] = " ".join(ws)
                a, f = shape_args(a, sc)
                if f or self.finished:
                    break
                r = self.env(tool, a)
                allow -= 1
                if r is None:
                    break
                o = r.get("observation")
                self.observe(tool, o)
                found = [i for i, _ in self.records_of(o)]
                kept = [i for i in found if self.buyable(i) and (not ck or self.owns(n, self.label_of(i)))]
                if is_num(self.budget):
                    pr = [self.price(i) for i in found]
                    if not (pr and all(p is not None and p > 10 * self.budget for p in pr)):
                        kept = [i for i in kept if self.price(i) is None or self.price(i) <= self.budget]
                hl = self.home_label(n)
                if ck and hl:
                    kept = [i for i in kept if words(self.label_of(i)) == hl] + [i for i in kept if words(self.label_of(i)) != hl]
                lines.append(dump(a.get(field)) + ": " + (", ".join(kept[:6]) if kept else "no row of the item's kind came back"))
                if kept:
                    unread = [i for i in kept if i not in self.full][:max(0, min(3, allow))]
                    texts = self.fill_facts(unread, self.reserve() + 8)
                    allow -= len(texts)
                    if texts:
                        lines.append(("opened: " + " | ".join(texts))[:2400])
                    break
        if not lines:
            return ""
        self.trace.append({"kind": "value_search", "lines": len(lines)})
        return ("[Cairn searched all the requirement values of each such item at once and read the leading rows of the right kind]\n" +
                "\n".join(lines))

    def home_label(self, n):
        ck = self.cat_key()
        if not ck:
            return ""
        it = self.items[n - 1]
        target = words(it.shelf) or words(it.name)
        for pool in (list(self.full.values()), [self.rows[i] for i in self.order]):
            cnt = {}
            for rec in pool:
                v = rec.get(ck)
                lab = "" if v is None else str(v)
                if lab and self.owns(n, lab):
                    w = words(lab)
                    cnt[w] = cnt.get(w, 0) + 1
            if target in cnt:
                return target
            if cnt:
                return max(cnt, key=cnt.get)
        return ""

    def ask_groups(self, free):
        order = [n for n in self.plan_order if self.lanes.get(n)] + [n for n in range(1, len(self.items) + 1) if n not in self.plan_order and self.lanes.get(n)]
        if free <= 0 or len(order) <= free:
            return []
        groups = []
        rest = order[:]
        for g in range(free, 0, -1):
            size = -(-len(rest) // g)
            groups.append(rest[:size])
            rest = rest[size:]
        return [g for g in groups if g]

    def remaining(self, n):
        used = self.lane_used.get(n, set())
        return [lab for lab in self.lanes.get(n, []) if words(lab) not in used and not self.told_about(n, lab)]

    def crowded_of(self, reading):
        return any(x == 1 and not isinstance(x, bool) for x in listify(reading.get("crowded")))

    def group_ask(self, group, told, floor=6):
        gs = len(group)
        cap = self.list_cap()
        now = self.list_now()
        share = max(1, now // gs) if now < cap else max(MIX_LABELS, cap // gs)
        parts = []
        for n in group:
            rem = self.remaining(n)
            if rem:
                parts.append((n, rem[:share]))
        if not parts:
            return []
        if len(parts) == 1:
            n, labs = parts[0]
            labs2, text = self.fit_ask(n, labs, False)
            if not labs2:
                return []
            sent = self.send([(n, labs2[0], text)], floor)
            if sent:
                self.finish_ask(n, labs2, False, sent, told)
            return sent
        ok = None
        while parts and ok is None:
            for c in range(share, 0, -1):
                cut = [(n, labs[:c]) for n, labs in parts]
                text = self.group_text(cut)
                a = self.msg_args(text)
                if a is not None and says(a, text):
                    ok = (cut, text)
                    break
            if ok is None:
                parts = parts[:-1]
        if ok is None:
            return []
        cut, text = ok
        sent = self.send([(cut[0][0], cut[0][1][0], text)], floor)
        if not sent:
            return []
        for n, _ in cut:
            self.lane_spent[n] = self.lane_spent.get(n, 0) + 1
        self.list_asks += 1
        before = {m: len(self.items[m - 1].told) for m in range(1, len(self.items) + 1)}
        reading = self.read_answers([(0, text, sent[0][2])], [LIGHT, HEAVY])
        reading.pop("free", None)
        self.fold_reading(reading, told)
        crowded = self.crowded_of(reading)
        answered = []
        for n, labs in cut:
            new = self.items[n - 1].told[before[n]:]
            if new:
                answered.append(n)
                self.lane_found[n] = self.lane_found.get(n, 0) + 1
                self.settle(n, labs, False, new, False)
        if crowded and not answered:
            self.listing = False
            self.trace.append({"kind": "lists_off", "via": "group"})
            return sent
        if not answered:
            self.lane_used.setdefault(cut[0][0], set()).add(words(cut[0][1][0]))
        self.trace.append({"kind": "group_ask", "items": [n for n, _ in cut], "answered": answered})
        return sent

    def finish_ask(self, n, labels, shown, sent, told):
        self.lane_spent[n] = self.lane_spent.get(n, 0) + 1
        self.list_asks += 1
        before = {m: len(self.items[m - 1].told) for m in range(1, len(self.items) + 1)}
        reading = self.read_answers([(n, sent[0][1], sent[0][2])], [LIGHT, HEAVY])
        if len(labels) > 1:
            reading.pop("free", None)
        self.fold_reading(reading, told)
        new = []
        for m in range(1, len(self.items) + 1):
            nn = self.items[m - 1].told[before[m]:]
            if nn:
                new += nn
                self.lane_found[m] = self.lane_found.get(m, 0) + 1
        self.settle(n, labels, shown, new, self.crowded_of(reading))

    def list_cap(self):
        return LIST_ONE if len(self.items) == 1 else LIST_MANY

    def list_now(self):
        ramp = RAMP_ONE if len(self.items) == 1 else RAMP_MANY
        k = self.list_asks
        v = ramp[k] if k < len(ramp) else self.list_cap()
        return min(v, self.list_cap())

    def next_ask(self):
        def key(n):
            pk = self.plan_order.index(n) if n in self.plan_order else len(self.plan_order) + n
            return (self.lane_found.get(n, 0) > 0, self.lane_spent.get(n, 0), pk)

        for n in sorted(range(1, len(self.items) + 1), key=key):
            rem = self.remaining(n)
            if rem:
                return n, (rem[:self.list_now()] if self.listing else rem[:1])
        return None

    def told_about(self, n, label):
        lab = spelled(label)
        for r in self.items[n - 1].told:
            if names(lab, spelled(r.split(":", 1)[0])):
                return True
        return False

    def lookalikes(self, n, label):
        keyroots = {}
        order = []
        for i in self.item_listings(n):
            if i not in self.full:
                continue
            for k, v in (attr_block(self.full[i]) or {}).items():
                w = words(k)
                if w not in keyroots:
                    keyroots[w] = set()
                    order.append(w)
                keyroots[w] |= roots(str(v))
        wc = {}
        for w in keyroots:
            for x in set(w.split()):
                wc[x] = wc.get(x, 0) + 1
        lw = words(label)
        plainw = {x for x in lw.split() if wc.get(x, 0) <= 2}
        own = keyroots.get(lw, set())
        scored = []
        for idx, w in enumerate(order):
            if not w or w == lw:
                continue
            shared = plainw & set(w.split())
            common = own & keyroots[w]
            if shared or common:
                scored.append((-(3 * len(shared) + min(3, len(common))), idx, w))
        scored.sort()
        return [w for _, _, w in scored[:LOOKALIKES]]

    def q_text(self, n, labels, shown=False):
        name = self.asked_name(n)
        if len(labels) >= 2:
            return "What " + ", ".join(labels[:-1]) + " or " + labels[-1] + " would you like for the " + name + "?"
        lab = labels[0]
        la = self.apart.get(lab, {}).get(n)
        if la:
            s = "Apart from the " + la[0] + (" and the " + la[1] if len(la) > 1 else "")
            return s + ", which " + lab + " would you like for the " + name + "?"
        if shown:
            ex = self.examples(n, lab)
            return "What " + lab + " would you like for the " + name + ", for example " + ex[0] + " or " + ex[1] + "?"
        return self.plain_q(n, lab)

    def group_text(self, parts):
        clauses = []
        for n, labs in parts:
            piece = (", ".join(labs[:-1]) + " or " + labs[-1]) if len(labs) >= 2 else labs[0]
            clauses.append("what " + piece + " for the " + self.asked_name(n))
        t = ", and ".join(clauses)
        t = "W" + t[1:]
        i = t.find(" for the ")
        t = t[:i] + " would you like" + t[i:]
        return t + "?"

    def fit_ask(self, n, labels, shown):
        for c in range(len(labels), 0, -1):
            text = self.q_text(n, labels[:c], shown)
            a = self.msg_args(text)
            if a is not None and says(a, text):
                return labels[:c], text
        return [], ""

    def ask_next(self, told, floor=6):
        pick = None
        for _ in range(LIST_ONE):
            self.follow_ups = [f for f in self.follow_ups if not self.told_about(f[0], f[1][0])]
            if self.follow_ups:
                n, labels, shown = self.follow_ups.pop(0)
            else:
                na = self.next_ask()
                if not na:
                    return []
                n, labels = na
                shown = False
            if not labels:
                return []
            labs, text = self.fit_ask(n, labels, shown)
            if not labs and shown:
                shown = False
                labs, text = self.fit_ask(n, labels, False)
            if labs:
                pick = (n, labs, text, shown)
                break
            self.lane_used.setdefault(n, set()).add(words(labels[0]))
            self.trace.append({"kind": "question_too_long", "item": n, "label": labels[0]})
        if not pick:
            return []
        n, labs, text, shown = pick
        sent = self.send([(n, labs[0], text)], floor)
        if not sent:
            return []
        self.finish_ask(n, labs, shown, sent, told)
        return sent


_E6V1 = re.compile(r"\s*[\d.,/x \-]+[a-z]{0,6}\s*")
_E6V2 = re.compile(r"[A-Za-z0-9][ _]models?(?![A-Za-z0-9])")
_E6V3 = re.compile(r"\s(?:and|or)\s|/|,|;|\(")
_PLAIN_S = re.compile(r"(?<=[a-z]{3})s$")
_E6V5_AND = re.compile(r"\band\b", re.I)
_E6V5_CUT = re.compile(r"\s*(?:,|\band\b)\s*", re.I)
_E6V5_PLURAL = re.compile(r"[A-Za-z]{2}[a-rtv-zA-RTV-Z]s$")
_E6V7 = re.compile(r"\b(?:and|for|like|me|or|please|tell|the|what|which|would|you)\b", re.I)
_ALNUMI = re.compile(r"[A-Za-z0-9]+")
_TRAIL_QP = re.compile(r"[?.]+$")


def plainf(s):
    return " ".join(_OUR.sub("or", _PLAIN_S.sub("", w)) for w in words(s).split())


class E6:
    def catch(self, k):
        w = words(k)
        return not V16_KINDS.search(w) and bool(V16_CATCH.search(w))

    def clamp(self, v):
        n = count_of(v)
        if not n:
            n = 1
        return min(max(n, 1), len(self.items))

    def settle(self, n, labels, shown, new, crowded):
        used = self.lane_used.setdefault(n, set())
        if len(labels) == 1:
            lab = labels[0]
            used.add(words(lab))
            if crowded and self.listing:
                self.listing = False
                self.trace.append({"kind": "lists_off", "via": "single"})
            if new or not crowded:
                return
            if n not in self.one_product and self.name_parts(n):
                self.one_product.add(n)
                self.follow_ups.insert(0, (n, [lab], shown))
                self.trace.append({"kind": "one_product", "item": n})
                return
            if not self.apart:
                la = self.lookalikes(n, lab)
                if la:
                    self.apart.setdefault(lab, {})[n] = la
                    self.follow_ups.insert(0, (n, [lab], False))
                    self.trace.append({"kind": "set_apart", "item": n, "label": lab, "keys": la})
            return
        if crowded and not new:
            self.listing = False
            self.follow_ups.insert(0, (n, [labels[0]], False))
            self.trace.append({"kind": "lists_off", "via": "list"})
            return
        hit = self.hit_pos(labels, new) if new else None
        if hit is not None:
            ahead = labels[hit + 1:]
            for x in labels[:hit + 1]:
                used.add(words(x))
            self.lane_misses[n] = 0
        else:
            ahead = list(reversed(labels[1:]))
            used.add(words(labels[0]))
            self.lane_misses[n] = self.lane_misses.get(n, 0) + 1
        rest = [x for x in self.lanes.get(n, []) if x not in labels]
        m = self.lane_misses[n]
        if m and m % 2 == 0:
            mid = (len(ahead) - 1) / 2.0
            ahead = [x for _, x in sorted(enumerate(ahead), key=lambda p: (abs(p[0] - mid), p[0]))]
            self.lanes[n] = rest + ahead
        else:
            self.lanes[n] = ahead + rest
        self.trace.append({"kind": "list_settled", "item": n, "hit": hit})

    def hit_pos(self, labels, needs):
        pooled = {}
        for lab, key, cnt, ex in self.key_table():
            s = pooled.setdefault(key, set())
            for x in ex:
                s |= roots(x)
        pos = []
        for nd in needs:
            if ":" in nd:
                prop, val = nd.split(":", 1)
            else:
                prop, val = nd, ""
            ps = spelled(prop)
            scores = [len(spelled(x) & ps) for x in labels]
            if not labels or max(scores) == 0:
                vr = roots(val)
                scores = [len(pooled.get(words(x), set()) & vr) for x in labels]
            if scores and max(scores) > 0:
                pos.append(scores.index(max(scores)))
        return min(pos) if pos else None

    def ranked_keys(self, n, table):
        it = self.items[n - 1]
        settled = [stems(m.split(":", 1)[0]) for m in it.musts]
        rows = [r for r in table if self.owner(r[0]) == n]
        if len(self.items) == 1 and not rows:
            rows = list(table)
        measured = {}
        for r in table:
            ex = r[3]
            measured[r[1]] = sum(1 for x in ex if _E6V1.fullmatch(x)) * 2 > len(ex)
        rows = sorted(rows, key=lambda r: (-r[2], measured.get(r[1], False), -len(r[3])))
        keys = [r[1] for r in rows if not any(names(s, stems(r[1])) for s in settled)]
        prop = [k for k in keys if not V15_NONPROP.search(k) or _E6V2.search(k)]
        dem = [k for k in keys if k not in prop]
        return [k for k in prop if not self.catch(k)] + [k for k in prop if self.catch(k)] + dem

    def adopt(self):
        if len(self.items) < 2 or not self.cat_key():
            return
        self.part_shelves()
        labels = []
        for i in self.full:
            lab = self.label_of(i, True)
            if lab and lab not in labels:
                labels.append(lab)
        strays = [lab for lab in labels if self.owner(lab) == 0]
        orphans = [n for n in range(1, len(self.items) + 1) if not any(self.owner(lab, False) == n or words(lab) == words(self.items[n - 1].shelf) for lab in labels)]
        if strays and len(orphans) == 1:
            for lab in strays:
                self.adopted[lab] = orphans[0]
            self.trace.append({"kind": "adopted", "item": orphans[0], "labels": strays})

    def owner(self, label, adopt=True):
        if not label:
            return 0
        if adopt and label in self.adopted:
            return self.adopted[label]
        key = (label, len(self.items))
        if key in self.owner_cache:
            return self.owner_cache[key]
        lw = words(label)
        lr = roots(label)
        best, bs = 0, 0
        for n, it in enumerate(self.items, 1):
            if lw == words(it.shelf):
                s = 3
            elif lw == words(it.name):
                s = 2
            else:
                ir = roots(it.shelf) | roots(it.name)
                s = len(lr & ir) / max(1, len(lr | ir))
            if s > bs:
                best, bs = n, s
        res = best if bs > 0 else 0
        self.owner_cache[key] = res
        return res

    def owns(self, n, label):
        if not label or not (1 <= n <= len(self.items)):
            return False
        return self.owner(label) == n or words(label) == words(self.items[n - 1].shelf)

    def item_records(self, n):
        if not self.cat_key():
            return 0
        return sum(1 for i, rec in self.full.items() if self.owns(n, self.label_of(i, True)) and attr_block(rec))

    def plan(self, count):
        self.adopt()
        table = self.key_table()
        parts = [PLAN_PROMPT.replace("COUNT", str(max(1, count))), "REQUEST:\n" + self.request]
        parts.append("ITEMS:\n" + "\n".join("item %d: %s - what the request already settles for it: %s" % (n, it.name, "; ".join(it.musts) if it.musts else "nothing")
                                         for n, it in enumerate(self.items, 1)))
        af = [str(x).strip() for x in listify(self.brief.get("ask_first")) if str(x).strip()]
        if af:
            parts.append("ASK FIRST (the request wants the shopper asked about these):\n" + "\n".join(af))
        if table:
            kl = []
            prev = None
            for k, (lab, key, cnt, ex) in enumerate(table, 1):
                if lab != prev:
                    kl.append("category " + repr(lab) + ":")
                    prev = lab
                line = "  %d. %s (on %d): %s" % (k, key, cnt, " | ".join(ex))
                line += self.not_stated(lab, key, ex)
                if self.catch(key):
                    line += " [lumps several features together: ask last]"
                kl.append(line)
            parts.append("ATTRIBUTE KEYS SEEN:\n" + "\n".join(kl))
        else:
            parts.append("ATTRIBUTE KEYS SEEN:\n(no listing has been read in full yet)")
        ans = self.json_ask("\n\n".join(parts), [HEAVY, LIGHT], 3500) or {}
        lanes = {n: [] for n in range(1, len(self.items) + 1)}
        hinted = {n: set() for n in lanes}
        picks = ans.get("ask")
        if isinstance(picks, dict):
            picks = [picks]
        if not isinstance(picks, list):
            picks = []
        for pk in picks:
            if not isinstance(pk, dict):
                continue
            n = self.clamp(pk.get("item"))
            lab = _E6V3.split(str(pk.get("label") or ""), 1)[0].strip()
            lab = _TRAIL_QP.sub("", lab).strip()
            if not lab or len(lab.split()) > 5:
                continue
            if not any(words(x) == words(lab) for x in lanes[n]):
                lanes[n].append(lab)
            if str(pk.get("hint") or "").strip():
                hinted[n].add(words(lab))
                if n not in self.plan_order:
                    self.plan_order.append(n)
        for n in lanes:
            keys = self.ranked_keys(n, table)
            rc = max(1, self.item_records(n))
            own = {}
            for lab, key, cnt, ex in table:
                if self.owner(lab) == n:
                    own[key] = max(own.get(key, 0), cnt / rc)

            def store(x):
                pf = plainf(x)
                for k in own:
                    if plainf(k) == pf:
                        return k
                return x

            def share(x):
                w = words(x)
                if w in own:
                    return own[w]
                ls = stems(x)
                c = [v for k, v in own.items() if names(stems(k), ls) or names(ls, stems(k))]
                return max(c) if c else 0

            hint = {words(store(h)) for h in hinted[n]}
            lane = []
            for x in lanes[n]:
                s = store(x)
                if not any(words(y) == words(s) for y in lane):
                    lane.append(s)
            guard = [k for k in keys if not self.catch(k) and own.get(k, 0) >= GUARD_SHARE][:GUARD_KEYS]
            for g in guard:
                if words(g) in [words(x) for x in lane[:3]]:
                    continue
                gs = own.get(g, 0)
                weak = None
                for x in lane[:3]:
                    if words(x) not in hint and share(x) + GUARD_GAP <= gs:
                        weak = x
                        break
                if weak is None and len(lane) >= 3:
                    continue
                new = [x for x in lane if words(x) != words(g)]
                if weak is not None:
                    wi = new.index(weak)
                    if len(self.items) > 1:
                        new[wi] = g
                        if len(new) >= 3:
                            new.insert(3, weak)
                        else:
                            new.append(weak)
                    else:
                        new.insert(wi, g)
                else:
                    new.append(g)
                top = [words(x) for x in new[:3]]
                if any(words(x) in hint and words(x) not in top for x in lane[:3]):
                    continue
                lane = new
            for k in keys:
                if not any(words(x) == words(k) for x in lane):
                    lane.append(k)
            lane = [x for x in lane if not self.catch(x)] + [x for x in lane if self.catch(x)]
            self.lanes[n] = lane
            self.hinted[n] = hint
        self.trace.append({"kind": "plan", "lanes": {str(k): v[:12] for k, v in self.lanes.items()}})

    def name_parts(self, n):
        nm = self.items[n - 1].name
        if not _E6V5_AND.search(nm):
            return []
        parts = [p.strip() for p in _E6V5_CUT.split(nm) if p.strip()]
        if len(parts) >= 2 and all(_E6V5_PLURAL.search(p) for p in parts):
            return parts
        return []

    def asked_name(self, n):
        it = self.items[n - 1]
        parts = self.name_parts(n)
        if not parts:
            return it.name
        if n not in self.one_product:
            return _E6V5_AND.sub("or", it.name)
        ck = self.cat_key()
        rr = []
        for i in self.order:
            row = self.rows.get(i) or {}
            if ck and not self.owns(n, self.label_of(i)):
                continue
            s = set()
            for k, v in row.items():
                if isinstance(v, str) and k != ck:
                    s |= roots(v)
            rr.append(s)
        best, bs = parts[0], -1
        for p in parts:
            head = roots(p.split()[-1])
            sc = sum(1 for s in rr if head & s)
            if sc > bs:
                best, bs = p, sc
        return best

    def plain_q(self, n, label):
        return "What " + label + " would you like for the " + self.asked_name(n) + "?"

    def examples(self, n, label):
        must = " ".join(self.items[n - 1].musts).lower()
        for lab, key, cnt, ex in self.key_table():
            if key == words(label):
                return [x for x in ex if x and len(x) <= 30 and x not in must][:2]
        return []

    def send(self, triples, floor=6):
        out = []
        tool = self.roles.get("ask")
        for n, label, text in triples:
            if self.finished or self.left() <= floor or self.msg_used >= self.msg_limit:
                break
            a = self.msg_args(text)
            if a is None:
                break
            r = self.env(tool, a)
            if r is None:
                break
            self.msg_used += 1
            obs = r.get("observation")
            ans = self.spoken(obs)
            out.append((n, text, ans))
            self.done_log.append("step %d: sent the shopper the message %r -> reply %r (cart then: %s)" % (self.step, text, ans[:300], self.cart_mark()))
            self.done_steps.append(self.step)
            self.trace.append({"kind": "message", "item": n, "text": text[:300], "reply": ans[:300]})
            if isinstance(obs, dict) and "error" in obs:
                break
        return out

    def fold_reading(self, reading, told):
        many = len(self.items) > 1
        for e in listify(reading.get("needs")):
            if not isinstance(e, dict) or not str(e.get("need") or "").strip():
                continue
            n = self.clamp(e.get("item"))
            nd = str(e["need"]).strip()
            it = self.items[n - 1]
            if nd not in it.told:
                it.told.append(nd)
                told.append((("item %d: " % n) + nd) if many else nd)
            if e.get("points") is True and (n, nd) not in self.refs:
                self.refs.append((n, nd))
        for e in listify(reading.get("drop")):
            if not isinstance(e, dict) or not str(e.get("property") or "").strip():
                continue
            n = self.clamp(e.get("item"))
            it = self.items[n - 1]
            p = words(str(e["property"]).split(":", 1)[0])
            for r in it.musts + it.told:
                if r not in it.dropped and words(r.split(":", 1)[0]) == p:
                    it.dropped.append(r)
                    told.append("dropped " + r)
        for e in listify(reading.get("free")):
            if isinstance(e, dict) and e.get("property"):
                self.items[self.clamp(e.get("item")) - 1].free.append(str(e["property"]))
        b = reading.get("budget")
        if is_num(b) and b > 0:
            self.budget = b

    def read_answers(self, sent, models=None):
        if models is None:
            models = [HEAVY, LIGHT]
        if self.quiet(sent):
            self.trace.append({"kind": "quiet_reply"})
            return {}
        self.reply_reads += 1
        lines = [REPLY_PROMPT, "", "ITEMS:"]
        lines += ["item %d: %s" % (n, it.name) for n, it in enumerate(self.items, 1)]
        lines += ["", "QUESTIONS AND ANSWERS:"]
        for k, (n, q, a) in enumerate(sent, 1):
            tag = ("(about item %d)" % n) if n else "(about several items)"
            lines.append("%d. %s Q: %s" % (k, tag, q))
            lines.append("A: " + a)
        return self.json_ask("\n".join(lines), models, 2500) or {}

    @soft(False)
    def quiet(self, sent):
        if self.reply_reads == 0:
            return False
        known = set()
        for it in self.items:
            known |= spelled(it.name) | spelled(it.shelf)
            for r in it.musts + it.told:
                known |= spelled(" ".join(_ALNUMI.findall(r.split(":", 1)[0])))
        for lab, key, cnt, ex in self.key_table():
            known |= spelled(key) | spelled(lab)
        for rec in self.full.values():
            for v in (attr_block(rec) or {}).values():
                known |= spelled(" ".join(w for w in _ALNUMI.findall(str(v)) if len(w) >= QUIET_LEN))
        for n, q, a in sent:
            qw = spelled(" ".join(_ALNUMI.findall(_E6V7.sub(" ", q))))
            aw = spelled(" ".join(_ALNUMI.findall(a)))
            if _DIGIT.search(a) or (aw & known) or (aw & qw) or V5_HOWASK.search(a):
                return False
        return True


_E7V1 = re.compile(r"\b(?:qty|quantity|count|unit|units)\b")
_E7V2 = re.compile(r"\b(?:not|no|least|most|under|over|min|max|minimum|maximum|unlike|different)\b")
_E7V3 = re.compile(r"remov|delet|drop|clear|take", re.I)
_VALSPLIT = re.compile(r"[,/;|]")


class E7:
    def tool_lines(self, skip=()):
        out = []
        for t in self.tools:
            fn = t["function"]
            if fn["name"] in skip:
                continue
            p = fn.get("parameters")
            out.append("- " + fn["name"] + ": " + str(fn.get("description") or "") + " | parameters: " + dump(p if p is not None else {}))
        return out

    def gate(self, stage):
        due = [d for d in self.duties if d["stage"] == stage]
        if not due or self.finished or not self.gate_due(stage):
            return True, ""
        said = []
        nudged = False
        phrase = "place the order" if stage == "order" else "end without buying anything"
        tl = self.tool_lines([x for x in (self.roles.get("buy"), self.roles.get("refuse")) if x])
        lead = "[Cairn carried out the request's own steps before continuing]\n"
        for _rnd in range(GATE_ROUNDS):
            rec = "\n".join("%d. %s" % (k, ln) for k, ln in enumerate(self.done_log, 1)) or "(nothing recorded yet)"
            blocks = [GATE_PROMPT.replace("STAGE", phrase), "REQUEST:\n" + self.request,
                      "STEPS DUE NOW:\n" + "\n".join("- " + d["text"] for d in due), "LEDGER:\n" + self.ledger(),
                      "CART: " + self.cart_text(), "RECORD (the shopper messages and step-taking calls made so far):\n" + rec]
            if self.changes:
                blocks.append("STORE NOTES SEEN:\n" + "\n".join(self.changes[-4:]))
            blocks.append("Messages left: %d   Steps left: %d (the %s itself uses one step)" % (
                max(0, self.msg_limit - self.msg_used), self.left(), "order" if stage == "order" else "ending"))
            blocks.append("TOOLS:\n" + "\n".join(tl))
            ans = self.json_ask("\n\n".join(blocks), [HEAVY, LIGHT] if nudged else [LIGHT, HEAVY], 3500)
            if ans is None:
                break
            if said:
                new = []
                self.fold_reading({"needs": ans.get("needs")}, new)
                hold = str(ans.get("hold") or "").strip()
                if new or hold:
                    self.version += 1
                    t = lead + "\n".join(said) + "\n"
                    t += ("The shopper's answer alters the task: " + "; ".join(new + ([hold] if hold else [])) +
                          ". Repair the cart accordingly and check out once more.")
                    return False, t
            call = ans.get("call") if isinstance(ans.get("call"), dict) else None
            if call is None:
                talk = stage == "order" and any(d["messages"] >= 1 for d in due)
                proof = {k for k, st in enumerate(self.done_steps, 1) if (not talk) or st > self.cart_changed_at}
                unproven = []
                for s in listify(ans.get("steps")):
                    if not isinstance(s, dict):
                        continue
                    ls = s.get("lines")
                    ls = ls if isinstance(ls, list) else [ls]
                    cited = [count_of(x) for x in ls if not isinstance(x, bool)]
                    if s.get("done") is not True or not any(c in proof for c in cited if c is not None):
                        unproven.append(str(s.get("step") or ""))
                if unproven and not said and not nudged and self.roles.get("ask") and self.msg_used < self.msg_limit and self.left() >= 2:
                    nudged = True
                    self.done_log.append("(Cairn: none of the record lines written after the cart's latest change at step %d proves: %s; messages left %d, steps left %d; name the call that performs it now)" % (
                        self.cart_changed_at, "; ".join(unproven)[:200], self.msg_limit - self.msg_used, self.left()))
                    self.done_steps.append(-1)
                    continue
                self.gate_passes.add((stage, self.cart_mark() + "#" + str(self.version)))
                break
            tool = call.get("tool")
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            if not isinstance(tool, str) or tool not in self.schemas or tool == self.roles.get("buy") or tool == self.roles.get("refuse"):
                break
            if self.left() < 2:
                break
            if tool == self.roles.get("ask") and self.msg_used >= self.msg_limit:
                break
            a, f = shape_args(args, self.schemas.get(tool) or {})
            if f:
                break
            if tool == self.roles.get("ask"):
                ss = strings(a)
                if not ss:
                    break
                text = max(ss, key=len)
                sent = self.send([(1, "", text)], 1)
                if not sent:
                    break
                self.gate_msgs += 1
                said.append("Q: " + text + "\nA: " + sent[0][2])
                continue
            r = self.env(tool, a)
            if r is None:
                break
            o = r.get("observation")
            self.absorb(o)
            shown = self.show(o)
            self.done_log.append("step %d: %s %s -> %s (cart: %s)" % (self.step, tool, dump(a), shown[:300], self.cart_mark()))
            self.done_steps.append(self.step)
            said.append(tool + " " + dump(a) + " -> " + shown[:400])
        if said:
            return True, lead + "\n".join(said)
        return True, ""

    def spoken(self, obs):
        if isinstance(obs, str):
            return obs
        out = []

        def walk(v, d):
            if d > 4:
                return
            if isinstance(v, str):
                if len(v.split()) >= 2:
                    out.append(v)
            elif isinstance(v, dict):
                for x in v.values():
                    walk(x, d + 1)
            elif isinstance(v, list):
                for x in v:
                    walk(x, d + 1)

        walk(obs, 0)
        if out:
            return " ".join(out)[:800]
        return dump(obs)[:400]

    def loose(self, obs):
        if not isinstance(obs, dict) or self.listing_id(obs, False, 0):
            return []
        out = []
        for v in obs.values():
            if isinstance(v, str):
                if len(v.split()) >= 5:
                    out.append(v)
            elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
                out += [x for x in v if len(x.split()) >= 5]
            elif isinstance(v, dict) and not self.listing_id(v, False, 1):
                out += [x for x in v.values() if isinstance(x, str) and len(x.split()) >= 6]
        return [ln for ln in out if ln not in self.heard]

    def read_note(self, lines):
        for ln in lines:
            self.heard.add(ln)
        p = NOTE_PROMPT + "\n\nITEMS AND REQUIREMENTS NOW:\n" + self.ledger() + "\n\nTHE NOTICE:\n" + "\n".join(lines)
        ans = self.json_ask(p, [LIGHT, SPARE], 2500) or {}
        gone = [str(g) for g in listify(ans.get("gone")) if isinstance(g, str) or (isinstance(g, int) and not isinstance(g, bool))]
        known = [g for g in gone if g in self.rows]
        for g in known:
            self.unavail.add(g)
        sold_flag = ans.get("sold_out") is True
        self.note_sold = bool(gone) or sold_flag
        self.note_named = bool(known)
        if self.note_sold and len(lines) == 1:
            self.sold_lines.add(lines[0])
        kind = ans.get("kind")
        if kind is not None and kind != "change":
            return ""
        rec = []
        b = self.budget_guard(ans.get("budget"))
        budget_moved = False
        if is_num(b) and b > 0 and b != self.budget:
            self.budget = b
            rec.append("budget now " + gnum(b))
            budget_moved = True
        dropped_any = False
        for e in listify(ans.get("drop")):
            if not isinstance(e, dict) or not str(e.get("need") or "").strip():
                continue
            it = self.items[self.clamp(e.get("item")) - 1]
            nd = str(e["need"]).strip()
            live = self.live_of(it)
            m = nd if nd in live else next((r for r in live if words(r.split(":", 1)[0]) == words(nd.split(":", 1)[0])), None)
            it.dropped.append(m if m is not None else nd)
            rec.append("dropped " + nd)
            dropped_any = True
        for e in listify(ans.get("add")):
            if not isinstance(e, dict) or not str(e.get("need") or "").strip():
                continue
            it = self.items[self.clamp(e.get("item")) - 1]
            nd = str(e["need"]).strip()
            while nd in it.dropped:
                it.dropped.remove(nd)
            if nd not in it.musts and nd not in it.told:
                it.told.append(nd)
            rec.append("added " + nd)
        if gone:
            rec.append("unavailable: " + ", ".join(gone))
        if ans.get("price_moved") is True:
            rec.append("a price moved")
        if self.pick() == "cheapest" and (dropped_any or gone or sold_flag or budget_moved):
            self.wider_held = False
            self.cheaper_marks = set()
        summ = str(ans.get("summary") or "").strip()
        if rec or summ:
            self.version += 1
            self.recent = []
            self.changes.append(summ or "; ".join(rec))
        out = summ
        if rec:
            out += " (" + "; ".join(rec) + ")"
        return out.strip()

    def live(self):
        out = []
        for n, it in enumerate(self.items, 1):
            for r in self.live_of(it):
                out.append((n, r))
        return out

    def evidence(self, obs):
        ids = []

        def walk(v, d, inrows):
            if d > 6:
                return
            if isinstance(v, dict):
                i = self.listing_id(v, inrows, d)
                if i and attr_block(v):
                    if i not in ids:
                        ids.append(i)
                    return
                for x in v.values():
                    walk(x, d + 1, False)
            elif isinstance(v, list):
                for x in v:
                    walk(x, d + 1, True)

        walk(obs, 0, False)
        return self.evidence_ids(ids)

    def evidence_ids(self, ids):
        live = self.live()
        if not ids or not live:
            return ""
        many = len(self.items) > 1
        lines = []
        for i in ids[:12]:
            ab = attr_block(self.full.get(i)) or {}
            parts = []
            for n, r in live[:8]:
                prop = r.split(":", 1)[0].strip()
                ps = stems(prop)
                hits = []
                for k, v in ab.items():
                    if names(ps, stems(k)):
                        h = str(k) + "=" + str(v)[:80]
                        bo = self.bare_off(r, v)
                        if bo is not None:
                            u = self.measured(r)
                            h += " (a bare figure: taken in the unit the requirement uses (" + u + ", that requirement's unit), it amounts to " + gnum(bo) + " " + u + ")"
                        hits.append(h)
                hits = hits[:3]
                if hits:
                    parts.append(("item %d: " % n if many else "") + prop + " -> " + ", ".join(hits))
            if parts:
                lines.append(i + ": " + "; ".join(parts))
        if not lines:
            return ""
        return ("[evidence: the keys listed carry a requirement's property inside their name; a key about another property "
                "(another component or aspect) settles nothing either way; a differently named key might still hold that same property] " +
                " | ".join(lines))

    def fresh(self):
        return self.cart_view is not None and self.cart_seen_at >= self.cart_changed_at

    def cart_text(self):
        if self.fresh():
            return dump(clip(self.cart_view, 300))[:3000]
        return "(from Cairn's cart record, listing: units) " + dump(self.cart_lines)

    def held(self, i, default=1):
        if self.fresh():
            stack = [self.cart_view]
            while stack:
                v = stack.pop()
                if isinstance(v, dict):
                    if any(isinstance(x, str) and x.strip() == i for x in v.values()):
                        cs = [count_of(x) for k, x in v.items() if not isinstance(x, str) and count_of(x) is not None and _E7V1.search(words(k))]
                        if len(cs) == 1:
                            return cs[0]
                    for x in v.values():
                        if isinstance(x, (dict, list)):
                            stack.append(x)
                elif isinstance(v, list):
                    stack.extend(v)
        return self.cart_lines.get(i, default)

    def cart_ids(self):
        if self.fresh():
            t = dump(self.cart_view)
            return [i for i in self.order if i in t]
        return list(self.cart_lines.keys())

    def rec_text(self, i):
        r = self.full.get(i) or self.rows.get(i)
        if r is None:
            return "(no record seen)"
        return dump(clip(r, 400))[:3000]

    def others(self, skip, limit=30):
        ids = list(reversed(self.order))
        if self.pick() == "cheapest":
            ids.sort(key=lambda i: (i not in self.full, self.price(i) is None, self.price(i) or 0))
        out = []
        for i in ids:
            if i in skip or self.sold_out(i):
                continue
            out.append(dump(clip(self.full.get(i) or self.rows.get(i), 160))[:900])
            if len(out) >= limit:
                break
        return out

    def fit_index(self):
        key = (len(self.order), len(self.full), sum(len(v) for v in self.views.values()))
        if self.fit_cache is not None and self.fit_cache[0] == key:
            return self.fit_cache[1]
        marks = {}
        partfits = {}
        for i in self.order:
            rec = self.full.get(i) or self.rows.get(i) or {}
            strs = [v for v in rec.values() if isinstance(v, str)]
            ents = []
            for v in rec.values():
                if isinstance(v, dict):
                    ents += [str(k) + " " + x for k, x in v.items() if isinstance(x, str)]
            m = fit_marks(" ".join(strs) + " " + ". ".join(ents))
            marks[i] = m
            for code, codes in m["notes"]:
                partfits.setdefault(code, set()).update(codes)
        self.fit_partfits = partfits
        self.fit_cache = (key, marks)
        return marks

    def fit_set(self, i):
        m = self.fit_index().get(i)
        if not m:
            return set()
        s = set(m["works"])
        if m["own"]:
            s |= self.fit_partfits.get(m["own"], set())
        return s

    def item_listings(self, n):
        if not self.cat_key():
            return []
        return [i for i in self.order if self.owns(n, self.label_of(i))]

    def system(self, part, main):
        fi = self.fit_index()
        for carrier, namer in ((part, main), (main, part)):
            ls = self.item_listings(carrier)
            tagged = [i for i in ls if fi[i]["series"]]
            if len(tagged) < LINK_ROWS or len(tagged) * 2 < len(ls):
                continue
            fam = set()
            for i in tagged:
                fam |= set(fi[i]["series"])
            if len(fam) > LINK_FAMILIES:
                continue
            if any(set(fi[j]["named"]) & fam for j in self.item_listings(namer)):
                return (carrier, namer, fam)
        return None

    def link_holds(self, carried, naming, fam):
        fi = self.fit_index()
        a = set((fi.get(carried) or {}).get("series", [])) & fam
        b = set((fi.get(naming) or {}).get("named", [])) & fam
        if a and b:
            return bool(a & b)
        return None

    def link_faults(self, part, main, device, plines):
        sysm = self.system(part, main)
        if not sysm:
            return []
        carrier, namer, fam = sysm
        fi = self.fit_index()
        out = []
        for line in plines:
            carried, naming = (line, device) if carrier == part else (device, line)
            if self.link_holds(carried, naming, fam) is not False:
                continue
            want = set(fi[naming]["named"]) & fam
            good = [i for i in self.item_listings(carrier) if set(fi[i]["series"]) & want and not self.sold_out(i) and i != carried][:4]
            t = "%s (series %s) against %s, which takes series %s" % (carried, ", ".join(sorted(set(fi[carried]["series"]) & fam)), naming, ", ".join(sorted(want)))
            if good:
                t += "; seen listings carrying that series: " + ", ".join(good)
            else:
                t += ("; search for that series together with the item's own words, or take a different listing of the " +
                      self.items[main - 1].name + ", one with a series carried by the wanted lines")
            out.append(t)
        return out

    def series_for(self, n):
        fi = self.fit_index()
        held = []
        cnt = {}
        cart = set(self.cart_ids())
        for part, main in self.fit_pairs:
            if n != part and n != main:
                continue
            sysm = self.system(part, main)
            if not sysm:
                continue
            fam = sysm[2]
            for i in self.item_listings(part) + self.item_listings(main):
                for f in sorted((set(fi[i]["series"]) | set(fi[i]["named"])) & fam):
                    cnt[f] = cnt.get(f, 0) + 1
                    if i in cart and f not in held:
                        held.append(f)
        rest = sorted([f for f in cnt if f not in held], key=lambda f: (-cnt[f], f))
        return (held + rest)[:LINK_SEARCHES]

    def covers(self, i, dcodes):
        fs = self.fit_set(i)
        bar = (self.fit_index().get(i) or {}).get("barred", [])
        return any(code_covers(c, d) for c in fs for d in dcodes) and not any(code_covers(b, d) for b in bar for d in dcodes)

    def fit_faults(self):
        if not self.fit_pairs:
            return []
        fi = self.fit_index()
        cart = self.cart_ids()
        out = []
        for part, main in self.fit_pairs:
            dev = [i for i in cart if self.owns(main, self.label_of(i))]
            pls = [i for i in cart if self.owns(part, self.label_of(i))]
            if len(dev) != 1 or not pls:
                continue
            lf = self.link_faults(part, main, dev[0], pls)
            if lf:
                out += lf
                continue
            dcodes = (fi.get(dev[0]) or {}).get("models") or []
            if not dcodes:
                continue
            for line in pls:
                fs = self.fit_set(line)
                if not fs or self.covers(line, dcodes):
                    continue
                good = [i for i in self.item_listings(part) if self.covers(i, dcodes) and not self.sold_out(i) and i not in cart][:4]
                t = "%s (%s) is meant for %s, against %s (%s)" % (line, self.items[part - 1].name, ", ".join(sorted(fs)[:4]), dev[0], ", ".join(sorted(dcodes)))
                if good:
                    t += "; compatible parts of the same sort: " + ", ".join(good)
                else:
                    t += ("; none of the seen parts of this sort suits the device. Hunt for a part that suits it, or change the device: " +
                          self.fit_plan(True))
                out.append(t)
        return out

    def fit_plan(self, short=False):
        if not self.fit_pairs:
            return ""
        fi = self.fit_index()
        lines = []
        for main in sorted({m for p, m in self.fit_pairs}):
            parts = [p for p, m in self.fit_pairs if m == main]
            tally = {}
            order = []
            for p in parts:
                for i in self.item_listings(p):
                    if self.sold_out(i):
                        continue
                    for c in sorted(self.fit_set(i)):
                        if c not in tally:
                            tally[c] = {}
                            order.append(c)
                        tally[c][p] = tally[c].get(p, 0) + 1
                sysm = self.system(p, main)
                if sysm and sysm[0] == p:
                    for i in self.item_listings(p):
                        if self.sold_out(i):
                            continue
                        for f in sorted(set(fi[i]["series"]) & sysm[2]):
                            if f not in tally:
                                tally[f] = {}
                                order.append(f)
                            tally[f][p] = tally[f].get(p, 0) + 1
            ranked = sorted(order, key=lambda c: (-len(tally[c]), -sum(tally[c].values())))[:6]
            if ranked:
                segs = []
                for c in ranked:
                    devs = [i for i in self.item_listings(main) if c in fi[i]["named"] or any(code_covers(c, d) for d in fi[i]["models"])][:2]
                    cnts = ", ".join("%d %s" % (tally[c][p], self.items[p - 1].name) for p in parts if p in tally[c])
                    segs.append(c + ": " + cnts + ((" (devices seen: " + ", ".join(devs) + ")") if devs else " (no device has turned up yet)"))
                lines.append("codes the parts name for the " + self.items[main - 1].name + " candidates -> " + "; ".join(segs))
            if self.pick() == "cheapest":
                cs = self.cheapest_sets(main, parts)
                if cs:
                    lines.append(cs)
        if not lines:
            return ""
        if short:
            return " | ".join(lines)
        return ("[fit plan: a part suits a device if the part's wording mentions the device's model number or an alternative trade "
                "name of it, or if the device's wording mentions the series that the part's code belongs to; try a single query "
                "combining one code (or one series) with the item's own terms, and should that return nothing, browse the category "
                "the device belongs to and read the codes off its rows]\n" + "\n".join(lines))

    @soft("")
    def cheapest_sets(self, main, parts):
        fi = self.fit_index()
        shelves = {}
        for p in parts:
            sh = [i for i in self.item_listings(p) if self.price(i) is not None and self.buyable(i)]
            sh.sort(key=lambda i: (self.price(i), i))
            shelves[p] = (self.system(p, main), sh)
        sets = []
        for d in self.item_listings(main):
            m = fi[d]
            if (not m["models"] and not m["named"]) or self.price(d) is None or not self.buyable(d):
                continue
            total = self.price(d) * self.items[main - 1].quantity
            ids = [d]
            ok = True
            for p in parts:
                sysm, sh = shelves[p]
                pick = None
                for i in sh:
                    if (m["models"] and self.covers(i, m["models"])) or (sysm and sysm[0] == p and self.link_holds(i, d, sysm[2]) is True):
                        pick = i
                        break
                if pick is None:
                    ok = False
                    break
                ids.append(pick)
                total += self.price(pick) * self.items[p - 1].quantity
            if ok:
                sets.append((total, ids))
        if not sets:
            return ""
        sets.sort(key=lambda s: s[0])
        return ("cheapest complete sets observed (requirements still unverified): " +
                "; ".join("+".join(ids) + " = " + gnum(t) for t, ids in sets[:SETS_SHOWN]))

    def all_labels(self):
        ck = self.cat_key()
        if not ck:
            return []
        return sorted({str(r.get(ck)).strip() for r in self.rows.values() if r.get(ck) is not None and str(r.get(ck)).strip()})

    def missing_items(self):
        if not self.cat_key():
            return []
        lines = [i for i in self.cart_ids() if self.held(i) > 0]
        if len(lines) >= len(self.items):
            return []
        labs = [self.label_of(i) for i in lines]
        seen = {self.label_of(i) for i in self.order}
        return [n for n in range(1, len(self.items) + 1) if any(self.owns(n, x) for x in seen) and not any(self.owns(n, x) for x in labs)]

    def states_all(self, i, n):
        ab = attr_block(self.full.get(i)) or {}
        for r in self.live_of(self.items[n - 1]):
            prop, _, val = r.partition(":")
            nv = words(val)
            vw = set(_VALSPLIT.sub(" ", nv).split())
            if not vw or _E7V2.search(nv):
                return False
            ok = False
            for k, v in ab.items():
                if names(spelled(prop), spelled(k)) and vw <= set(_VALSPLIT.sub(" ", words(v)).split()):
                    ok = True
                    break
            if not ok:
                return False
        return True

    def fill_short(self):
        bound = {x for pr in self.fit_pairs for x in pr}
        picks = []
        for n in self.missing_items():
            it = self.items[n - 1]
            cands = [i for i in self.item_listings(n) if i in self.full and i not in self.cart_lines and self.buyable(i)
                     and self.price(i) is not None and self.states_all(i, n)]
            cands.sort(key=lambda i: self.price(i))
            pick = cands[0] if cands and n not in bound else None
            if pick and is_num(self.budget):
                each = self.brief.get("budget_scope") == "each"
                cost = self.price(pick) * (1 if each else it.quantity)
                if not each:
                    cost += sum((self.price(i) or 0) * self.held(i) for i in self.cart_ids())
                if cost > self.budget + 1e-9:
                    pick = None
            if not pick:
                return False
            picks.append((pick, it.quantity))
        if not picks:
            return True
        wanted = {i: self.cart_lines[i] for i in self.cart_ids() if i in self.cart_lines}
        for i, q in picks:
            wanted[i] = q
        calls = self.cart_calls(wanted, [])
        if not calls or len(calls) > self.left() - 1:
            return False
        tool = self.roles.get("cart")
        for a in calls:
            a2, f = shape_args(a, self.schemas.get(tool) or {})
            if f:
                return False
            r = self.env(tool, a2)
            if r is None:
                return False
            self.note_cart(tool, a2)
        self.trace.append({"kind": "short_cart_filled", "picks": picks})
        return True

    def part_shelves(self):
        if not self.cat_key():
            return
        labels = self.all_labels()
        moved = False
        for n, it in enumerate(self.items, 1):
            nr = roots(it.name)
            if not nr or not it.shelf:
                continue
            if not any(j != n and words(o.shelf) == words(it.shelf) for j, o in enumerate(self.items, 1)):
                continue
            if any(j != n and roots(o.name) == nr for j, o in enumerate(self.items, 1)):
                continue
            own = [x for x in labels if roots(x) == nr and words(x) != words(it.shelf)]
            if len(own) == 1 and not any(words(o.shelf) == words(own[0]) for o in self.items):
                self.trace.append({"kind": "shelf_parted", "item": n, "shelf": own[0]})
                it.shelf = own[0]
                moved = True
        if moved:
            self.owner_cache = {}
            self.fit_cache = None

    def fuller_label(self, n, label):
        it = self.items[n - 1]
        nr = roots(it.name)
        if len(nr) < 2 or nr <= roots(label) or not self.cat_key():
            return None
        if it.shelf and roots(label) == roots(it.shelf):
            return None
        return next((x for x in self.all_labels() if nr <= roots(x)), None)

    def named_label(self, n, label):
        it = self.items[n - 1]
        if not it.shelf or not self.cat_key() or words(label) == words(it.shelf):
            return None
        for i in self.order:
            x = self.label_of(i)
            if words(x) == words(it.shelf):
                return x
        return None

    def line_faults(self):
        self.adopt()
        lines = [i for i in self.cart_ids() if self.held(i) > 0]
        if not lines or not self.cat_key():
            return []
        nit = len(self.items)
        owners = {i: [n for n in range(1, nit + 1) if self.owns(n, self.label_of(i))] for i in lines}
        seen = {self.label_of(i) for i in self.order}
        known = [n for n in range(1, nit + 1) if any(self.owns(n, x) for x in seen)]
        out = []
        for n in known:
            it = self.items[n - 1]
            mine = [i for i in lines if n in owners[i]]
            if not mine:
                out.append(("other", "item %d (%s) lacks a cart line" % (n, it.name)))
                continue
            if len([i for i in mine if owners[i] == [n]]) > 1:
                out.append(("other", "item %d (%s) has %d cart lines (%s); keep one" % (n, it.name, len(mine), ", ".join(mine))))
            for i in mine:
                h = self.held(i)
                if owners[i] == [n] and h != it.quantity:
                    out.append(("units", "%s is held at %d %s; item %d (%s) wants %d" % (i, h, "unit" if h == 1 else "units", n, it.name, it.quantity)))
                lab = self.label_of(i)
                alt = self.fuller_label(n, lab) or self.named_label(n, lab)
                if alt:
                    out.append(("other", "%s comes from the label %r while the store also has the label %r, which names item %d (%s) completely; source this line from %r instead" % (i, lab, alt, n, it.name, alt)))
        if len(known) == nit:
            for i in lines:
                if not owners[i]:
                    out.append(("other", "%s (%s) is a kind nobody requested; remove it" % (i, self.label_of(i) or "unknown kind")))
        for i in lines:
            if self.sold_out(i):
                out.append(("other", "%s is sold out" % i))
        if is_num(self.budget) and all(self.price(i) is not None for i in lines):
            if self.brief.get("budget_scope") == "each":
                for i in lines:
                    p = self.price(i)
                    if self.budget < p <= 10 * self.budget:
                        out.append(("other", "%s costs %s, over the per-item limit of %s" % (i, gnum(p), gnum(self.budget))))
            else:
                tot = sum(self.price(i) * self.held(i) for i in lines)
                if tot > self.budget + 1e-9 and tot <= 10 * self.budget:
                    out.append(("other", "the cart totals %s, over the budget of %s" % (gnum(tot), gnum(self.budget))))
        return out

    def count_fixes(self):
        if not self.cat_key():
            return []
        cart = self.cart_ids()
        fixes = []
        for i in cart:
            h = self.held(i, 0)
            own = [n for n in range(1, len(self.items) + 1) if self.owns(n, self.label_of(i))]
            if h <= 0 or len(own) != 1:
                continue
            n = own[0]
            nl = [j for j in cart if self.cart_lines.get(j, 1) > 0 and self.owns(n, self.label_of(j))]
            if len(nl) != 1 or h == self.items[n - 1].quantity or self.sold_out(i):
                continue
            fixes.append((i, h, self.items[n - 1].quantity))
        tool = self.roles.get("cart")
        sc = self.schemas.get(tool) if tool else None
        if not fixes or not isinstance(sc, dict):
            return []
        props = sc.get("properties") if isinstance(sc.get("properties"), dict) else {}
        req = sc.get("required") if isinstance(sc.get("required"), list) else []
        texts = [k for k, p in props.items() if isinstance(p, dict) and "string" in kinds(p) and "enum" not in p]
        learned = [k for (t, k) in self.id_args if t == tool and k in texts]
        idp = learned[0] if learned else (next((x for x in req if x in texts), None) or (texts[0] if len(texts) == 1 else None))
        cnt = next((k for k, p in props.items() if isinstance(p, dict) and "integer" in kinds(p)), None)
        mode = next((k for k, p in props.items() if isinstance(p, dict) and isinstance(p.get("enum"), list) and len(p["enum"]) >= 2), None)
        if not idp or not cnt:
            return []
        calls = []
        for i, h, w in fixes:
            if self.sets_counts():
                calls.append({idp: i, cnt: w})
            elif mode:
                en = props[mode]["enum"]
                rem = next((o for o in en if _E7V3.search(str(o))), en[1])
                add = next((o for o in en if o != rem), en[0])
                calls.append({idp: i, mode: rem, cnt: h})
                calls.append({idp: i, mode: add, cnt: w})
            else:
                return []
        if len(calls) + 3 > self.left():
            return []
        done = []
        for a in calls:
            a2, f = shape_args(a, sc)
            if f:
                break
            r = self.env(tool, a2)
            if r is None:
                break
            self.note_cart(tool, a2)
            o = r.get("observation")
            self.cart_said = dump(o)
            self.observe(tool, o)
            done.append(dump(a2) + " -> " + self.show(o)[:300])
            if self.finished:
                break
        self.trace.append({"kind": "count_fixes", "done": len(done)})
        return done

    def cart_check(self, planned=None, limit=SOFT):
        ids = list(planned) if planned else self.cart_ids()
        key = "|".join(sorted(ids)) + "#" + str(self.version)
        js = self.judges(limit)
        if key in self.checked or not js or not ids:
            return ""
        self.checked.add(key)
        parts = [CHECK_PROMPT, "REQUEST:\n" + self.request, "REQUIREMENTS NOW BINDING:\n" + self.ledger()]
        if planned:
            parts.append("CART (planned only: judge it as though these listings sat in the cart, each at its asked quantity): " +
                         "; ".join("item %d: quantity %d" % (n, it.quantity) for n, it in enumerate(self.items, 1)) + "\n" + ", ".join(ids))
        else:
            parts.append("CART:\n" + self.cart_text())
        recs = []
        for i in ids:
            so = "SOLD OUT (the store reports this listing cannot be purchased any more) " if self.sold_out(i) else ""
            recs.append(i + ": " + so + self.rec_text(i))
        parts.append("RECORDS OF THE CARTED LISTINGS:\n" + "\n".join(recs))
        if PICKS3.fullmatch(self.pick()):
            parts.append("OTHER LISTINGS SEEN (newest first):\n" + "\n".join(self.others(set(ids), 15)))
        prompt = "\n\n".join(parts)
        ans = None
        if len(js) == 2 and not planned and not self.audited and not PICKS3.fullmatch(self.pick()):
            ans = self.json_ask(prompt, [LIGHT], 3000)
            if ans is not None:
                js = [HEAVY] if (ans.get("ok") is False and HEAVY in self.judges(limit)) else []
        if js and not self.no_credit:
            a2 = self.json_ask(prompt, js, 3000)
            if a2 is not None:
                ans = a2
        self.trace.append({"kind": "cart_check", "ids": ids, "ok": None if ans is None else ans.get("ok")})
        self.verdicts[key] = ans is not None and ans.get("ok") is not False
        if ans is None or ans.get("ok") is not False:
            return ""
        self.leads = [x for x in self.leads if x not in ids]
        probs = [str(p) for p in listify(ans.get("problems"))][:5]
        better = [str(b) for b in listify(ans.get("better")) if str(b) in self.rows and not self.sold_out(str(b))][:4]
        t = "A careful review finds the cart still wrong: " + ("; ".join(probs) if probs else "see the requirements in the ledger") + "."
        if better:
            t += " Candidates that seem preferable: " + ", ".join(better) + "."
        t += " Repair the cart, or else demonstrate that the reviewer erred by reading the records afresh, and then check out."
        return t


_LINK_STOP1 = re.compile(r"the|and|with|from|that|comes|listing|page|its|for|of")
_LINK_STOP2 = re.compile(r"the|and|with|from|that|comes|listing|page|its|for")
_ANYRUN = re.compile(r"[a-z0-9]+")
_FIRST_DIGITS = re.compile(r"\d+")

APOLOGY = "I am sorry, but no product in this shop satisfies all of your requirements, so I am not making a purchase."


def leaves(v):
    if isinstance(v, dict):
        out = []
        for x in v.values():
            out += leaves(x)
        return out
    if isinstance(v, list):
        out = []
        for x in v:
            out += leaves(x)
        return out
    return [v]


def token_in(word, text):
    return re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", text) is not None


class E8:
    def page_read(self, i):
        if i not in self.opened:
            return False
        off = self.roles.get("offer")
        if off and self.single_target(off):
            return off in self.views.get(i, set())
        return True

    def pending_refs(self):
        livep = set(self.live())
        return [(n, t) for (n, t) in self.refs if (n, t) in livep and t not in self.ref_values]

    def trail(self, limit=None):
        pend = self.pending_refs()
        tool = self.roles.get("offer") or self.roles.get("open")
        tgt = self.single_target(tool) if tool else None
        seen = []
        lost = []
        while pend and self.chain_rounds < min(6 if self.left() > 15 else 4, self.chain_room if self.chain_room is not None else 6)\
                and self.spend < HARD and (limit is None or self.clock() <= limit):
            self.chain_rounds += 1
            recs = []
            nopen = 0
            for i in reversed(self.order):
                r = self.full.get(i) or self.rows.get(i)
                if self.page_read(i) and r is not None and nopen < 45:
                    recs.append("OPENED " + dump(clip(r, 300))[:1400])
                    nopen += 1
            for i in reversed(self.order):
                if len(recs) >= 60:
                    break
                r = self.full.get(i) or self.rows.get(i)
                if not self.page_read(i) or r is None:
                    if i in self.full:
                        recs.append("ROW " + dump(clip(self.full[i], 120))[:700])
                    elif i in self.rows:
                        recs.append("ROW " + dump(clip(self.rows[i], 80))[:300])
            p = (CHAIN_PROMPT + "\n\nREQUIREMENTS WHOSE VALUE SITS ON ANOTHER LISTING:\n" + "\n".join(t for _, t in pend) +
                 "\n\nRECORDS (newest first):\n" + "\n".join(recs))
            ans = self.json_ask(p, [LIGHT], 4500)
            if ans is None and not (self.store_broke or self.no_credit or self.calls >= CALL_CAP) and self.spend + HEAVY_ROOM <= HARD:
                ans = self.json_ask(p, [HEAVY], 4500)
            ans = ans or {}
            reach = []
            lost = []
            gaps = []
            chains = ans.get("chains")
            if isinstance(chains, dict):
                chains = [chains]
            if not isinstance(chains, list):
                chains = []
            for ch in chains:
                if not isinstance(ch, dict):
                    continue
                need = str(ch.get("need") or "").strip()
                match = next((pt for pt in pend if pt[1].strip() == need), None)
                if match is None and len(pend) == 1:
                    match = pend[0]
                if match is None:
                    continue
                lk = ch.get("links")
                links = [x for x in (lk if isinstance(lk, list) else listify(lk)) if isinstance(x, dict)]
                lids = [str(x.get("id") or "").strip() for x in links]
                val = str(ch.get("value") or "").strip()
                allread = bool(links) and all(x and self.page_read(x) for x in lids)
                if ch.get("done") is True and allread and val:
                    self.ref_values[match[1]] = val
                    self.version += 1
                    continue
                if allread and not str(links[-1].get("find") or "").strip():
                    self.ref_values[match[1]] = val or ("whatever the listing " + lids[-1] + " shows")
                    self.version += 1
                    continue
                unread = [x for x in lids if x in self.rows and not self.page_read(x)]
                if unread:
                    for x in unread:
                        if x not in reach:
                            reach.append(x)
                    continue
                lkd = next((x for x, i in zip(links, lids) if i not in self.rows), None) or {}
                desc = str(lkd.get("about") or "").strip() or "the listing the requirement leads to"
                fw = str(lkd.get("find") or "").strip()
                lost.append(match[1] + " -> find " + desc + ((" (search: " + fw + ")") if fw else ""))
                gaps.append((desc, fw))
            pend = [pt for pt in pend if pt[1] not in self.ref_values]
            if not reach and gaps and tool and tgt and self.left() > 12 and self.link_searches < LINK_SEARCHES:
                reach, known = self.link_finder(gaps[0][0], gaps[0][1])
                if known:
                    seen.append(known + ": a page, already open, of the shop the chain names; it shows the values listed in the "
                                "description. Take the value off that page.")
                    lost = lost[1:]
            if not reach or not tool or not tgt or self.left() < len(reach) + 4 or self.finished:
                break
            for x in reach[:max(0, min(3, 6 - len(seen)))]:
                a, f = shape_args({tgt: x}, self.schemas.get(tool) or {})
                if f or self.rushed():
                    break
                r = self.env(tool, a)
                if r is None or self.finished:
                    break
                o = r.get("observation")
                self.observe(tool, o)
                seen.append(x + ": " + self.show(o)[:1500])
        txt = ""
        if seen:
            txt += "[Cairn opened these pages, which the requirements lead to]\n" + "\n".join(seen)
        if self.ref_values:
            txt += ("\n" if txt else "") + "[values taken from those pages] " + "; ".join(k + " -> " + str(v) for k, v in self.ref_values.items())
        hold = False
        if lost and self.chain_holds < (3 if self.left() > 15 else 2) and self.left() > 5:
            self.chain_holds += 1
            hold = True
            txt += (("\n" if txt else "") + "The purchase is only valid once you have read completely every page that a requirement "
                    "leads to (a result row will not do), including each page that leads on to yet another listing. Not yet located "
                    "or read: " + " | ".join(lost[:3]) + ". Search using the shop's name plus the values in the description (another "
                    "product of that kind sold by the same shop is the wrong one), open whichever row from that shop has a page showing "
                    "those values, use the value printed on that page, and then order.")
        return txt, hold

    def trail_pre(self):
        return self.left() >= TRAIL_ROOM and self.clock() <= HUNT_DEADLINE and bool(self.pending_refs())

    def early_trail(self):
        if not self.trail_pre():
            return ""
        sr, sh = self.chain_rounds, self.chain_holds
        self.chain_rounds = 0
        self.chain_room = EARLY_ROUNDS
        try:
            txt, _ = self.trail(HUNT_DEADLINE)
        finally:
            self.chain_rounds, self.chain_holds = sr, sh
            self.chain_room = None
        return txt

    def decline_trail(self):
        if self.decline_chain_done or not self.trail_pre():
            return ""
        self.decline_chain_done = True
        txt, _ = self.trail(HUNT_DEADLINE)
        if not txt:
            return ""
        return txt + "\nRun searches for those values at once and purchase whatever matches; decline only if nothing matches."

    def no_name_keys(self):
        return {self.id_key, self.cat_key(), self.title_key()} - {None}

    def name_cands(self, row):
        bad = self.no_name_keys()
        return [v.strip() for k, v in row.items() if k not in bad and isinstance(v, str) and 2 < len(v.strip()) <= 40
                and not V24_PLACEHOLDER.fullmatch(v.strip().casefold())]

    def shop_rows(self, desc, ids):
        d = desc.lower()
        return [i for i in ids if i not in self.opened and any(token_in(c.lower(), d) for c in self.name_cands(self.rows.get(i) or {}))]

    def opened_shops(self, desc):
        d = desc.lower()
        return [i for i in self.opened if i in self.rows and any(token_in(c.lower(), d) for c in self.name_cands(self.rows[i]))]

    def link_finder(self, desc, sw):
        bad = self.no_name_keys()
        shops = set(self.shop_rows(desc, self.order)) | set(self.opened_shops(desc))
        namew = set()
        for i in shops:
            for k, v in (self.rows.get(i) or {}).items():
                if k not in bad and isinstance(v, str) and len(v.strip()) <= 40 and not V24_PLACEHOLDER.fullmatch(v.strip().casefold()):
                    namew |= set(_ALNUM3.findall(v.lower()))
        src = sw or desc
        valw = [w for w in _ANYRUN.findall(src.lower()) if (len(w) >= 3 or w.isdigit()) and w not in namew and not _LINK_STOP1.fullmatch(w)]
        for i in self.opened_shops(desc):
            lv = " ".join(str(x) for x in leaves(self.full.get(i) or self.rows.get(i) or {})).lower()
            if valw and all(token_in(w, lv) for w in valw):
                return [], i
        tpl = self.value_template()
        memo = _WS.sub(" ", sw.lower()).strip()
        cands = None
        if memo in self.link_seen:
            cands = self.shop_rows(desc, self.link_seen[memo])
        elif tpl and sw.strip():
            tool, fixed, field = tpl
            qs = [sw.strip()]
            two = " ".join(sw.split()[:2])
            if two != qs[0]:
                qs.append(two)
            for q in qs:
                a = dict(fixed)
                a[field] = q
                a, f = shape_args(a, self.schemas.get(tool) or {})
                if f:
                    break
                self.link_searches += 1
                r = self.env(tool, a)
                if r is None:
                    break
                o = r.get("observation")
                self.observe(tool, o)
                ids = [i for i, _ in self.records_of(o)]
                self.link_seen[memo] = ids
                cands = self.shop_rows(desc, ids)
                if ids:
                    break
        kindw = {w for w in _ALNUM3.findall(src.lower()) if w not in namew and not _LINK_STOP2.fullmatch(w)}

        def of_kind(i):
            return not kindw or bool(set(_ALNUM3.findall(dump(self.rows.get(i) or {}).lower())) & kindw)

        res = [i for i in (cands or []) if of_kind(i)][:2]
        if not res:
            res = [i for i in self.shop_rows(desc, list(reversed(self.order))) if of_kind(i)][:2]
        return res, None

    def reread(self):
        tool = self.roles.get("offer") or self.roles.get("open")
        tgt = self.single_target(tool) if tool else None
        if not tool or not tgt:
            return ""
        cut = max(self.step - 2, self.refused_at)
        stale = [i for i in self.cart_ids() if i not in self.gone and self.offer_seen.get(i, -99) < cut]
        if not stale or self.left() < len(stale) + 5:
            return ""
        lines = []
        for i in stale:
            a, f = shape_args({tgt: i}, self.schemas.get(tool) or {})
            if f or self.rushed():
                break
            before = dict(self.rows.get(i) or {})
            r = self.env(tool, a)
            if r is None or self.finished:
                break
            self.offer_seen[i] = self.step
            o = r.get("observation")
            self.observe(tool, o)
            after = self.rows.get(i) or {}
            ch = [k for k in before if k in after and after[k] != before[k] and not isinstance(after[k], (dict, list))]
            if ch:
                lines.append(i + " changed (" + ", ".join(str(k) for k in ch[:4]) + "): " + dump(clip(o, 300))[:900])
        if lines:
            self.version += 1
        return "\n".join(lines)

    def swap_hint(self):
        lost = [i for i in self.cart_ids() if i not in self.gone and self.sold_out(i)]
        if not lost:
            return ""
        for i in lost:
            self.gone[i] = self.step
        self.leads = [x for x in self.leads if x not in lost]
        self.version += 1
        reps = self.replacements(lost)
        t = ("[Cairn] " + ", ".join(lost) + " sold out from now on (the store shows they cannot be purchased any more); they are "
             "gone for good and must not be opened again. ")
        if reps and self.left() <= 6:
            t += ("Steps are scarce: within this very turn put " + reps[0] + " in the cart in the quantity asked and remove the line "
                  "that sold out (that is two calls), and then order. Other already-read listings that seem to match: " +
                  (", ".join(reps[1:]) or "none") + ".")
        elif reps and self.pick() == "cheapest":
            p0 = self.price(reps[0])
            t += ("Already-read listings that seem to match that item, lowest price first: " + ", ".join(reps) + ". The request "
                  "wants the lowest price, so unless you have already seen every matching listing, make one search capped below " +
                  reps[0] + "'s price" + ((" (" + gnum(p0) + ")") if p0 is not None else "") + " (through the search's price ceiling "
                  "argument, if the search has one) ahead of replacing the line that sold out with the lowest-priced matching listing.")
        elif reps:
            t += ("Already-read listings that seem to match that item: " + ", ".join(reps) + ". Within this turn remove the line that "
                  "sold out and put " + reps[0] + " in the cart in the quantity asked, and order after that.")
        else:
            t += "Remove that line and put in the best other matching listing, searching when none of those already read matches."
        return t

    def sold_search(self):
        lines = [i for i in self.cart_ids() if i not in self.gone]
        if any(self.sold_out(i) for i in lines):
            return ""
        if len(lines) == 1:
            self.unavail.add(lines[0])
            return ""
        if len(lines) >= 2:
            return self.reread()
        return ""

    def replacements(self, lost):
        js = self.judges()
        if not js:
            return []
        recs = []
        for i in reversed(self.order):
            if i in lost or i in self.gone or self.sold_out(i):
                continue
            recs.append(dump(clip(self.full.get(i) or self.rows.get(i), 200))[:1200])
            if len(recs) >= 25:
                break
        if not recs:
            return []
        p = (SWAP_PROMPT + "\n\nREQUEST:\n" + self.request + "\n\nREQUIREMENTS NOW LIVE:\n" + self.ledger() +
             "\n\nTHE LINE THAT SOLD OUT:\n" + "\n".join(i + ": " + self.rec_text(i) for i in lost) +
             "\n\nCURRENT CART:\n" + self.cart_text() + "\n\nREMAINING RECORDS SEEN (latest first):\n" + "\n".join(recs))
        ans = self.json_ask(p, list(reversed(js)), 3500) or {}
        cart = set(self.cart_ids())
        kept = []
        fits = ans.get("fits")
        for e in (fits if isinstance(fits, list) else ([fits] if fits is not None else [])):
            i = str(e.get("id")) if isinstance(e, dict) else str(e)
            pr = e.get("price") if isinstance(e, dict) else None
            pr = pr if is_num(pr) else float("inf")
            if i in self.rows and i not in lost and i not in self.gone and i not in cart and i not in [k for k, _ in kept]:
                kept.append((i, pr))
        if self.pick() == "cheapest":
            kept.sort(key=lambda x: x[1])
        return [i for i, _ in kept[:4]]

    def audit(self):
        if self.audited or not self.judges():
            return ""
        self.audited = True
        ans = self.audit_call()
        fits = self.audit_fits(ans)
        if not fits:
            opens = [str(x) for x in listify((ans or {}).get("open"))]
            opens = [x for x in opens if x in self.rows and x not in self.opened and not self.sold_out(x)]
            if opens and self.audit_open(opens):
                ans = self.audit_call()
                fits = self.audit_fits(ans)
        if not fits:
            return ""
        self.lead_items = fits
        self.leads = [i for k in fits for i in fits[k]]
        reason = str((ans or {}).get("reason") or "").strip()
        t = "The review believes the following listings could match: " + "; ".join("item " + k + ": " + ", ".join(v) for k, v in fits.items())
        if reason:
            t += " (" + reason + ")"
        return t + ". Open these listings and purchase what really matches; decline only when every one of them fails."

    def audit_call(self):
        js = self.judges()
        ids = list(reversed(self.order))
        ids.sort(key=lambda i: i not in self.full)
        recs = []
        for i in ids:
            if self.sold_out(i):
                continue
            if i in self.full:
                recs.append("OPENED " + dump(clip(self.full[i], 200))[:1200])
            else:
                recs.append("ROW " + dump(clip(self.rows[i], 120))[:500])
            if len(recs) >= 30:
                break
        if not recs:
            return None
        p = (AUDIT_PROMPT + "\n\nREQUEST:\n" + self.request + "\n\nREQUIREMENTS NOW LIVE:\n" + self.ledger() +
             "\n\nRECORDS SEEN (latest first):\n" + "\n".join(recs))
        ans = self.json_ask(p, [LIGHT], 4000) if js else None
        if HEAVY in js and not self.no_credit and not self.audit_fits(ans):
            a2 = self.json_ask(p, [HEAVY], 4000)
            if a2 is not None:
                ans = a2
        return ans

    def audit_fits(self, ans):
        f = (ans or {}).get("fits")
        if not isinstance(f, dict):
            return {}
        out = {}
        for k, v in f.items():
            ids = [str(x) for x in (v if isinstance(v, list) else [v]) if x is not None and str(x) in self.rows and not self.sold_out(str(x))][:4]
            if ids:
                out[str(k)] = ids
        return out

    def audit_open(self, ids):
        cmp = self.roles.get("compare")
        ct = self.cmp_target()
        before = len(self.full)
        if cmp and ct and self.cmp_facts() is not False:
            plan = [(cmp, {ct: ids[:self.cmp_room()]})]
        else:
            ft = self.facts_tool()
            tgt = self.single_target(ft) if ft else None
            if not ft or not tgt:
                return False
            plan = [(ft, {tgt: i}) for i in ids[:2]]
        cs = self.cart_calls({"#%d" % k: 1 for k in range(len(self.items))}, [])
        steps = len(cs) if cs is not None else len(self.items)
        if self.left() < len(plan) + max(5, self.reserve() + steps):
            return False
        for tool, a in plan:
            a2, f = shape_args(a, self.schemas.get(tool) or {})
            if f:
                return False
            r = self.env(tool, a2)
            if r is None or self.finished:
                break
            self.observe(tool, r.get("observation"))
        return len(self.full) > before

    def cart_props(self):
        tool = self.roles.get("cart")
        sc = self.schemas.get(tool) if tool else None
        if not isinstance(sc, dict):
            return None, {}, []
        props = sc.get("properties") if isinstance(sc.get("properties"), dict) else {}
        req = sc.get("required") if isinstance(sc.get("required"), list) else []
        return sc, props, req

    def cart_calls(self, wanted, drops):
        sc, props, req = self.cart_props()
        if sc is None:
            return None
        tool = self.roles.get("cart")
        for k, p in props.items():
            if isinstance(p, dict) and "array" in kinds(p) and isinstance(p.get("items"), dict) and isinstance(p["items"].get("properties"), dict):
                ip = p["items"]["properties"]
                idk = next((x for x, q in ip.items() if isinstance(q, dict) and "string" in kinds(q) and "enum" not in q), None)
                ck = next((x for x, q in ip.items() if isinstance(q, dict) and "integer" in kinds(q)), None)
                if not idk:
                    return None
                return [{k: [dict([(idk, i)] + ([(ck, u)] if ck else [])) for i, u in wanted.items()]}]
        texts = [k for k, p in props.items() if isinstance(p, dict) and "string" in kinds(p) and "enum" not in p]
        learned = [k for (t, k) in self.id_args if t == tool and k in texts]
        tgt = learned[0] if learned else (next((x for x in req if x in texts), None) or (texts[0] if len(texts) == 1 else None))
        cnt = next((k for k, p in props.items() if isinstance(p, dict) and "integer" in kinds(p)), None)
        mode = next((k for k, p in props.items() if isinstance(p, dict) and isinstance(p.get("enum"), list) and len(p["enum"]) >= 2), None)
        if not tgt:
            return None
        sets = self.sets_counts()
        calls = []
        for i in drops:
            h = self.cart_lines.get(i, 1)
            mn = props[cnt].get("minimum") if cnt else None
            if mode:
                c = {tgt: i, mode: props[mode]["enum"][1]}
                if cnt:
                    c[cnt] = h
                calls.append(c)
            elif cnt and sets:
                calls.append({tgt: i, cnt: 0})
            elif cnt and isinstance(mn, int) and not isinstance(mn, bool) and mn <= -h:
                calls.append({tgt: i, cnt: -h})
            else:
                return None
        cart = set(self.cart_ids())
        for i, u in wanted.items():
            h = self.cart_lines.get(i, 0) if i in cart else 0
            if h == u:
                continue
            if h and not sets:
                return None
            c = {tgt: i}
            if mode:
                c[mode] = props[mode]["enum"][0]
            if cnt:
                c[cnt] = u
            calls.append(c)
        return calls

    def sets_counts(self):
        sc, props, req = self.cart_props()
        if any(isinstance(p, dict) and isinstance(p.get("enum"), list) and len(p["enum"]) >= 2 for p in props.values()):
            return False
        return any(isinstance(p, dict) and "integer" in kinds(p) and is_num(p.get("minimum")) and p.get("minimum") == 0 for p in props.values())

    def whole_removal(self, args):
        sc, props, req = self.cart_props()
        cnt = next((k for k, p in props.items() if isinstance(p, dict) and "integer" in kinds(p)), None)
        rem = any(isinstance(props.get(k), dict) and isinstance(props[k].get("enum"), list) and v in props[k]["enum"][1:] for k, v in args.items())
        line = next((v for v in args.values() if isinstance(v, str) and v in self.cart_lines), None)
        if cnt and rem and line and cnt not in args:
            h = self.cart_lines[line]
            mx = props[cnt].get("maximum")
            args = dict(args)
            args[cnt] = min(h, mx) if is_num(mx) else h
        return args

    def note_cart(self, tool, args):
        self.cart_touched = True
        self.cart_changed_at = self.step
        props = (self.schemas.get(tool) or {}).get("properties") or {}
        rem = any(isinstance(props.get(k), dict) and isinstance(props[k].get("enum"), list) and len(props[k]["enum"]) >= 2
                  and v in props[k]["enum"][1:] for k, v in args.items())
        loose = next((count_of(v) for v in args.values() if is_num(v) and count_of(v) is not None), None)
        lines = []
        whole = False
        for k, v in args.items():
            if isinstance(v, list):
                p = props.get(k) if isinstance(props.get(k), dict) else {}
                it = p.get("items") if isinstance(p.get("items"), dict) else {}
                if not v and ("object" in kinds(it) or isinstance(it.get("properties"), dict)):
                    whole = True
                for e in v:
                    if isinstance(e, dict):
                        whole = True
                        i = next((x for x in e.values() if isinstance(x, str) and x in self.rows), None)
                        c = next((count_of(x) for x in e.values() if is_num(x) and count_of(x) is not None), None)
                        if i:
                            lines.append((i, c if c is not None else 1))
                    elif isinstance(e, str) and e in self.rows:
                        lines.append((e, loose))
            elif isinstance(v, str) and v in self.rows:
                lines.append((v, loose))
        if whole:
            self.cart_lines = {i: c for i, c in lines if c is not None and c > 0}
            for i, c in self.cart_lines.items():
                self.ever_carted[i] = c
                self.carted_ids.add(i)
            return
        has_int = any(isinstance(p, dict) and "integer" in kinds(p) for p in props.values())
        sets = self.sets_counts()
        for i, c in lines:
            h = self.cart_lines.get(i, 0)
            if rem:
                if has_int:
                    h -= c if c else 1
                else:
                    h = h - c if c is not None else 0
            elif sets:
                h = c if c is not None else 1
            else:
                h += c if c is not None else 1
            if h > 0:
                self.cart_lines[i] = h
                self.ever_carted[i] = h
                self.carted_ids.add(i)
            else:
                self.cart_lines.pop(i, None)

    def complete_cart(self):
        if self.completed or not self.confirmed or self.sold_out(self.confirmed) or not self.roles.get("cart") or not self.roles.get("buy"):
            return ""
        self.completed = True
        ck = self.cat_key()

        def kind(i):
            if ck:
                v = (self.rows.get(i) or {}).get(ck)
                return ("" if v is None else str(v)).strip().lower()
            return i

        planned = {}
        pk = set()
        for key, ids in self.lead_items.items():
            m = _FIRST_DIGITS.search(str(key))
            n = int(m.group(0)) if m else (1 if len(self.items) == 1 else None)
            pick = next((i for i in ids if not self.sold_out(i)), None)
            if pick and n and 1 <= n <= len(self.items) and kind(pick) not in pk:
                planned[pick] = self.items[n - 1].quantity
                pk.add(kind(pick))
        if self.confirmed not in planned:
            return ""
        keep = {}
        drops = []
        for i in self.cart_ids():
            if i in planned:
                continue
            if not self.sold_out(i) and kind(i) not in pk:
                keep[i] = self.cart_lines.get(i, 1)
            else:
                drops.append(i)
        if len(planned) + len({kind(i) for i in keep}) < len(self.items):
            return ""
        lines = dict(keep)
        lines.update(planned)
        calls = self.cart_calls(lines, drops)
        if not calls or self.left() < len(calls) + 1:
            return ""
        ids = list(lines)
        self.fill_facts(ids, len(calls) + 3)
        self.show_links(ids, len(calls) + 3)
        self.cart_check(ids, HARD)
        if self.verdicts.get("|".join(sorted(ids)) + "#" + str(self.version)) is not True:
            return ""
        tool = self.roles["cart"]
        sc = self.schemas.get(tool) or {}
        sent = []
        for a in calls:
            a2, f = shape_args(a, sc)
            if f:
                return ""
            r = self.env(tool, a2)
            if r is None or self.finished:
                return ""
            self.note_cart(tool, a2)
            self.observe(tool, r.get("observation"))
            sent.append(dump(a2))
        buy = self.roles["buy"]
        oa, f = shape_args(dict(self.brief.get("buy_args") or {}), self.schemas.get(buy) or {})
        if f:
            return ""
        kept = []
        gate_txt = ""
        for att in range(2):
            if att == 1:
                self.reread()
                self.cart_check(ids, HARD)
                if self.verdicts.get("|".join(sorted(ids)) + "#" + str(self.version)) is not True or self.left() < 1 or self.finished or any(self.sold_out(i) for i in ids):
                    break
            go, gt = self.gate("order")
            if gt:
                gate_txt = gt
            if not go:
                break
            r = self.env(buy, oa)
            if r is None:
                break
            self.checkouts += 1
            if not self.finished:
                self.refused_at = self.step
            o = r.get("observation")
            self.observe(buy, o)
            kept.append(self.show(o))
            if self.finished:
                break
        if not kept and not gate_txt:
            return ""
        t = ("[Cairn] The decline was not sent because Cairn acted in its place: an independent check passed " + self.confirmed +
             ", so Cairn changed the cart (" + "; ".join(sent) + ") and placed the order.")
        if gate_txt:
            t += "\n" + gate_txt
        if kept:
            t += "\n" + " [then] ".join(kept)
        return t

    def is_order(self, tool, args):
        b = self.roles.get("buy")
        if not b or tool != b:
            return False
        fa = self.brief.get("buy_args") if isinstance(self.brief.get("buy_args"), dict) else {}
        return all(args.get(k) == v for k, v in fa.items())

    def is_decline(self, tool, args):
        b = self.roles.get("refuse")
        if not b or tool != b:
            return False
        fa = self.brief.get("refuse_args") if isinstance(self.brief.get("refuse_args"), dict) else {}
        return all(args.get(k) == v for k, v in fa.items())

    def offered(self):
        r = self.roles
        ends = [x for x in (r.get("buy"), r.get("refuse")) if x]
        lft = self.left()
        res = self.reserve()
        allow = None
        if ends:
            if lft <= res:
                allow = set(ends)
            elif lft <= res + 3:
                allow = set(ends) | {r.get("cart"), r.get("cart_view")}
            elif lft <= len(self.items) + 5 and not self.checkouts:
                allow = set(ends) | {r.get("cart"), r.get("cart_view"), r.get("offer")}
        ask = r.get("ask")
        hide = bool(ask) and self.msg_args("x" * 200) is not None
        base = [t for t in self.tools if not (hide and t["function"]["name"] == ask)]
        if allow is None:
            return base
        out = [t for t in base if t["function"]["name"] in allow]
        return out or base

    def quiet_fill(self, args):
        tool = self.roles.get("refuse")
        sc = self.schemas.get(tool) if tool else None
        if not isinstance(sc, dict):
            return args
        props = sc.get("properties") if isinstance(sc.get("properties"), dict) else {}
        req = sc.get("required") if isinstance(sc.get("required"), list) else []
        args = dict(args)
        for k, p in props.items():
            if not isinstance(p, dict) or "string" not in kinds(p) or "enum" in p:
                continue
            if k not in args and k not in req:
                continue
            v = args.get(k)
            txt = v if isinstance(v, str) else ""
            if not txt or any(i in txt for i in self.rows) or self.brief.get("quiet_decline") is not False:
                ml = p.get("maxLength")
                args[k] = APOLOGY[:ml if isinstance(ml, int) and not isinstance(ml, bool) else 200]
        return args

    def map_titles(self, tool, args):
        r = self.roles
        if tool not in (r.get("cart"), r.get("open"), r.get("offer"), r.get("compare")) or not self.id_key:
            return args, ""
        props = (self.schemas.get(tool) or {}).get("properties") or {}
        free = [k for k, p in props.items() if isinstance(p, dict) and ("string" in kinds(p) or "array" in kinds(p)) and "enum" not in p]
        if len(free) != 1:
            return args, ""
        k = free[0]
        if (tool != r.get("cart") and (tool, k) not in self.id_args) or k not in args:
            return args, ""

        def mp(v):
            if not isinstance(v, str):
                return v, ""
            s = v.strip()
            if s in self.rows:
                return s, ""
            if id_like(s, True) or len(s) < 8:
                return v, ""
            lo = s.lower()
            hits = [i for i, row in self.rows.items() if any(isinstance(x, str) and kk != self.id_key and x.lower().startswith(lo) for kk, x in row.items())]
            if len(hits) == 1:
                return hits[0], ""
            if hits:
                return v, "more than one listing holds the text %r (%s); give a single listing id" % (s, ", ".join(hits[:6]))
            return v, "%r is no listing id; give the id as the result rows show it, in their %s field" % (s, self.id_key)

        v = args[k]
        if isinstance(v, list):
            out = []
            for e in v:
                m, prob = mp(e)
                if prob:
                    return args, prob
                out.append(m)
            a = dict(args)
            a[k] = out
            return a, ""
        m, prob = mp(v)
        if prob:
            return args, prob
        a = dict(args)
        a[k] = m
        return a, ""

    def show(self, obs):
        t = dump(clip(obs, ROW_CLIP if self.records_of(obs) else TEXT_CLIP))
        if len(t) > OBS_CAP:
            t = t[:OBS_CAP] + " ...[cut]"
        return t

    def cmp_target(self):
        c = self.roles.get("compare")
        sc = self.schemas.get(c) if c else None
        if not isinstance(sc, dict):
            return None
        props = sc.get("properties") if isinstance(sc.get("properties"), dict) else {}
        t = next((k for k, p in props.items() if isinstance(p, dict) and "array" in kinds(p)), None)
        req = sc.get("required") if isinstance(sc.get("required"), list) else []
        if not t or any(x != t for x in req):
            return None
        return t

    def cmp_room(self):
        t = self.cmp_target()
        learned = max(2, min(self.cmp_bad - 1, max(self.cmp_good + 1, 2))) if self.cmp_bad else None
        if t:
            mx = self.schemas[self.roles["compare"]]["properties"][t].get("maxItems")
            if isinstance(mx, int) and not isinstance(mx, bool):
                return min(mx, learned) if learned else mx
        if learned:
            return learned
        return max(4, self.cmp_good)

    def join_opens(self, calls):
        op = self.roles.get("open")
        cmp = self.roles.get("compare")
        ot = self.single_target(op) if op else None
        ct = self.cmp_target()
        if not op or not ot or not cmp or not ct or op == cmp or self.cmp_facts() is False:
            return [(c, False) for c in calls]
        room = self.cmp_room()
        picks = []
        for k, c in enumerate(calls):
            fn = c.get("function") or {}
            raw = fn.get("arguments")
            if fn.get("name") != op or not isinstance(raw, str):
                continue
            a = obj_of(raw)
            if not isinstance(a, dict) or list(a.keys()) != [ot]:
                continue
            v = a[ot]
            if isinstance(v, str) and v.strip() in self.rows and v.strip() not in self.gone:
                picks.append((k, v.strip()))
        picks = picks[:room]
        if len(picks) < 2:
            return [(c, False) for c in calls]
        pk = {k for k, _ in picks}
        first = picks[0][0]
        out = []
        for k, c in enumerate(calls):
            if k == first:
                out.append(({"id": c.get("id"), "type": "function", "function": {"name": cmp, "arguments": dump({ct: [v for _, v in picks]})}}, False))
            else:
                out.append((c, k in pk))
        return out


_QUOTED_ID = re.compile(r"(?<=\")([A-Za-z0-9][A-Za-z0-9_\-:.]{5,40})(?=\")")


class E9:
    def run(self):
        if self.finished:
            return
        self.read_brief()
        self.trace.append({"kind": "brief", "brief": self.brief})
        op = self.pv.get("opening")
        shown_op = None
        if op is not None:
            shown_op = restore(op)
            self.absorb(shown_op)
        txt = self.opening() if not self.finished else ""
        self.gap = STORE_GAP
        msg = "SHOPPER'S REQUEST:\n" + self.request
        if op is not None:
            msg += "\n\nTHE STORE'S STARTING DISPLAY:\n" + self.show(shown_op)
        if txt:
            msg += ("\n\nCairn has already searched for every item, and part of each item's listings were read in full, one step "
                    "per read:\n" + txt + "\nJudge these listings by the requirements, and search more only where something is "
                    "still lacking.\n\n" + self.status())
        else:
            msg += ("\n\nBegin with a search for each item requested, sought within the category it belongs to, and read several "
                    "listings completely, so that the interviewer can tell which properties such listings show.\n\n" + self.status())
        self.convo = [{"role": "system", "content": GUIDE}, {"role": "user", "content": msg}]
        self.work_loop(TURN_CAP, HARD)
        if not self.finished:
            t = self.finish(True)
            if t and not self.finished and not self.store_broke and not self.no_credit and self.left() > 1:
                self.convo.append({"role": "user", "content": "[Cairn] Cairn attempted to finish, and " + t +
                                   "\nFollow the store's answer and then finish.\n" + self.status()})
                self.work_loop(self.turns + 10, HARD + 0.01)
        for _ in range(2):
            if self.finished:
                break
            t = self.finish()
            if not t or self.finished or self.store_broke or self.no_credit or self.left() <= 1:
                break
            self.convo.append({"role": "user", "content": "[Cairn] Cairn attempted to finish, and " + t +
                               "\nFollow the store's answer and then finish.\n" + self.status()})
            self.work_loop(self.turns + 6, HARD + HEAVY_ROOM)
        self.trace.append({"kind": "end", "finished": self.finished, "steps": self.step, "spend": round(self.spend, 5), "model_calls": self.calls})

    def work_loop(self, cap, spend_cap):
        for _ in range(CRASH_RETRIES):
            try:
                self.turn_loop(cap, spend_cap)
                return
            except Exception as e:
                self.trace.append({"kind": "crash", "error": (type(e).__name__ + ": " + str(e))[:400]})
                self.answer_open()

    def answer_open(self):
        idx = None
        for k in range(len(self.convo) - 1, -1, -1):
            if self.convo[k].get("tool_calls"):
                idx = k
                break
        if idx is None:
            return
        answered = {m.get("tool_call_id") for m in self.convo[idx + 1:] if m.get("role") == "tool"}
        for c in self.convo[idx]["tool_calls"]:
            if c.get("id") not in answered:
                self.convo.append({"role": "tool", "tool_call_id": c.get("id"),
                                   "content": "[Cairn] This call possibly did not execute, because something failed along the way. Inspect the present state before repeating it."})
        self.convo.append({"role": "user", "content": self.status()})

    def turn_loop(self, cap, spend_cap):
        idle = 0
        r = self.roles
        while (not self.finished and not self.store_broke and self.left() >= 1 and self.turns < cap and self.spend < spend_cap
               and (self.clock() < LAST_TURN or (not self.cart_ids() and self.room() > EMPTY_CART_ROOM))):
            if self.ready_to_ask():
                s = self.interview()
                if s:
                    self.convo.append({"role": "user", "content": s + "\n" + self.status()})
                continue
            self.trim()
            self.turns += 1
            msg = self.think(self.convo, [LIGHT, SPARE], DIRECTOR_CAP, self.offered())
            if msg is None:
                self.misses += 1
                if self.no_credit or self.calls >= CALL_CAP:
                    break
                if self.misses > 2:
                    if self.clock() >= OUTAGE_CUTOFF:
                        break
                    time.sleep(OUTAGE_PAUSE)
                continue
            calls = []
            tcs = msg.get("tool_calls")
            for k, tc in enumerate(tcs if isinstance(tcs, list) else []):
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                raw = fn.get("arguments")
                if isinstance(raw, dict):
                    a = raw
                elif isinstance(raw, str) and raw.strip():
                    a = obj_of(raw) or {}
                else:
                    a = {}
                nm = fn.get("name")
                calls.append({"id": tc.get("id") or ("k%d_%d" % (self.turns, k)), "type": "function",
                              "function": {"name": "" if nm is None else str(nm), "arguments": dump(a)}})
            c = msg.get("content")
            text = c if isinstance(c, str) else (dump(c) if c is not None else "")
            if not calls:
                idle += 1
                self.convo.append({"role": "assistant", "content": text or "(no call)"})
                ro = self.reopen()
                if ro:
                    idle = 0
                self.convo.append({"role": "user", "content": "[Cairn] Use one of the tools, so that the work goes on." + ((" " + ro) if ro else "") + "\n" + self.status()})
                if idle >= 3:
                    break
                continue
            idle = 0
            nms = [cc["function"]["name"] for cc in calls]
            commit = [x for x in (r.get("cart"), r.get("buy"), r.get("refuse")) if x]
            if (not self.asked and r.get("ask") and self.free_msgs() > 0 and self.left() > 8 and self.clock() <= INTERVIEW_DEADLINE
                    and any(nm in commit for nm in nms)):
                self.convo.append({"role": "assistant", "content": text or None, "tool_calls": calls})
                for cc in calls:
                    self.convo.append({"role": "tool", "tool_call_id": cc["id"], "content": SKIP_OPEN + " The shopper is questioned first."})
                s = self.interview()
                self.convo.append({"role": "user", "content": (s or "[Cairn] The interviewer had no question to put.") + "\n" + self.status()})
                continue
            self.convo.append({"role": "assistant", "content": text or None, "tool_calls": calls})
            self.trace.append({"kind": "turn", "text": text[:300], "calls": [cc["function"] for cc in calls]})
            replies = self.dispatch(calls)
            for k, cc in enumerate(calls):
                rep = replies[k]
                if k == len(calls) - 1:
                    rep = rep + "\n" + self.status()
                self.convo.append({"role": "tool", "tool_call_id": cc["id"], "content": rep})

    def trim(self):
        total = sum(len(dump(m.get("content"))) for m in self.convo)
        if total <= HISTORY_CAP:
            return
        tm = [m for m in self.convo if m.get("role") == "tool"]
        for m in tm[:max(1, len(tm) // 2)]:
            c = m.get("content")
            if isinstance(c, str) and len(c) > 600:
                ids = []
                for x in _QUOTED_ID.findall(c):
                    if x in self.rows and x not in ids:
                        ids.append(x)
                m["content"] = c[:400] + "... (an older result was shortened; listing ids it held: " + ", ".join(ids[:20]) + ")"

    def cart_footer(self):
        return "\nCart now: " + self.cart_text()

    def dispatch(self, calls):
        joined = self.join_opens(calls)
        n_calls = len(joined)
        replies = []
        r = self.roles
        for cc, isj in joined:
            allowed = sorted({t["function"]["name"] for t in self.offered()})
            if isj:
                replies.append("[Cairn] This listing is in the comparison result given earlier in this turn, because Cairn read them jointly in a single step.")
                continue
            if self.finished:
                replies.append("[Cairn] This call was not executed, because the episode has ended.")
                continue
            tool = cc["function"]["name"]
            raw = cc["function"]["arguments"]
            if tool and tool == r.get("ask") and self.msg_args("x" * 200) is not None:
                replies.append(SKIP_OPEN + " Cairn's interviewer sends all shopper messages.")
                continue
            if tool not in self.schemas:
                replies.append(SKIP_OPEN + " unknown tool; the tools are: " + ", ".join(allowed))
                continue
            if tool not in allowed:
                replies.append(SKIP_OPEN + " Too few steps remain for this tool; use one of these instead: " + ", ".join(allowed))
                continue
            if isinstance(raw, dict):
                args = raw
            elif isinstance(raw, str) and raw.strip():
                args = obj_of(raw)
                if args is None:
                    replies.append(SKIP_OPEN + " The argument text did not form exactly one JSON object.")
                    continue
            else:
                args = {}
            args, faults = shape_args(args, self.schemas.get(tool) or {})
            if faults:
                replies.append(SKIP_OPEN + " " + "; ".join(faults[:6]))
                continue
            args, prob = self.map_titles(tool, args)
            if prob:
                replies.append(SKIP_OPEN + " " + prob + ".")
                continue
            if tool == r.get("cart"):
                args = self.whole_removal(args)
            tail = []
            ct = self.cmp_target()
            if tool == r.get("compare") and ct and isinstance(args.get(ct), list) and self.cmp_bad and len(args[ct]) > self.cmp_room():
                room = self.cmp_room()
                rest = args[ct][room:]
                args = dict(args)
                args[ct] = args[ct][:room]
                tail.append("[Cairn] Only the first %d went out, as this store's comparison takes no more than %d; not yet sent: %s" % (
                    room, room, ", ".join(str(x) for x in rest)))
            st = self.single_target(tool)
            if st and tool in (r.get("open"), r.get("offer")) and isinstance(args.get(st), str) and args[st].strip() in self.gone:
                g = args[st].strip()
                replies.append(SKIP_OPEN + " This listing's sell-out was recorded at step %d and it will not return. Put a different "
                               "listing that fits in place of its cart line." % self.gone[g])
                continue
            if tool == r.get("cart") and any(not isinstance(v, str) and count_of(v) is not None and count_of(v) < 0 for v in args.values()):
                view = dump(self.cart_view) if self.fresh() else ""
                bad = next((v for v in args.values() if isinstance(v, str) and v in self.rows and v not in self.cart_lines
                            and v not in view and v not in self.cart_said), None)
                if bad:
                    replies.append(SKIP_OPEN + " " + bad + " is not held, so no units can come off it." + self.cart_footer())
                    continue
            is_ord = self.is_order(tool, args)
            is_dec = self.is_decline(tool, args)
            fin = is_ord or is_dec
            if fin and n_calls > 1:
                replies.append(SKIP_OPEN + " A finishing call must go alone, once the results of the other calls have been read.")
                continue
            if not fin and self.left() <= self.reserve() and (r.get("buy") or r.get("refuse")):
                replies.append(SKIP_OPEN + " The last few steps are reserved for the order" +
                               (" (with the shopper approving the basket first)" if self.reserve() == 2 else "") + " or for a decline.")
                continue
            plain_roles = {v for k, v in r.items() if k != "search"}
            search_like = tool not in plain_roles
            fresh = False
            if search_like:
                fresh = self.new_query(tool, args)
                if fresh:
                    a2 = self.first_look(tool, args, True)
                    if a2 != args:
                        tail.append("[Cairn] This being a new search, Cairn sent it for page one (you had sent %s)." % dump(args))
                        args = a2
            args = self.row_ids(tool, args)
            if tool == r.get("search") and self.codes_dead and self.names_code(args):
                replies.append(SKIP_OPEN + " Code searches in this store returned nothing. Search with words and attribute values "
                               "instead, browse the category listing, and take the codes from the rows shown.")
                continue
            mark = tool + dump(args)
            if not fin and tool != r.get("cart") and mark in self.recent:
                replies.append(SKIP_OPEN + " This exact call was just made, with no change since; the earlier result stands.")
                continue
            reader = tool in (r.get("search"), r.get("open"), r.get("offer"), r.get("compare"))
            if reader and mark in self.read_cache and self.read_cache[mark][0] == self.version:
                _v, s, ctxt = self.read_cache[mark]
                replies.append(SKIP_OPEN + " The identical call at step %d gave the result below, with no change since then.\n%s" % (s, ctxt[:3000]))
                continue
            if reader and tool != r.get("compare") and st and isinstance(args.get(st), str):
                tv = args[st].strip()
                if (tv in self.rows and self.shown_already(tool, tv)) or (tool, tv) in self.factless:
                    replies.append(SKIP_OPEN + " This view has nothing new to show for that listing. Its record: " + self.rec_text(tv))
                    continue
            if tool == r.get("compare") and ct and isinstance(args.get(ct), list) and args[ct]:
                lst = args[ct]
                drop = [x for x in lst if isinstance(x, str) and self.shown_already(tool, x)]
                if drop and len(drop) == len(lst):
                    replies.append((SKIP_OPEN + " This view has nothing new to show for these listings.\n" +
                                    "\n".join(str(x) + ": " + self.rec_text(x) for x in lst))[:4000])
                    continue
                if drop:
                    tail.append("[Cairn] Left out as already shown in full with no change since: " + ", ".join(drop))
                    args = dict(args)
                    args[ct] = [x for x in lst if x not in drop]
                    mark = tool + dump(args)
            ttxt = ""
            if is_ord and self.left() > 2:
                hunt_txt = self.cheaper_hunt()
                w = self.wider_hold()
                if w:
                    replies.append(w + self.cart_footer())
                    continue
                changed = self.reread()
                if self.note_sold:
                    self.sold_search()
                if self.cart_touched and not self.fresh() and r.get("cart_view") and self.left() > 5 and not self.rushed():
                    cv = r["cart_view"]
                    a, f = shape_args({}, self.schemas.get(cv) or {})
                    if not f:
                        res = self.env(cv, a)
                        if res is not None:
                            o = res.get("observation")
                            self.cart_view = o
                            self.cart_seen_at = self.step
                            m = self.observe(cv, o)
                            if m:
                                self.queued = []
                                replies.append(HOLD_OPEN + " Viewing the cart revealed a change: " + m + self.cart_footer() +
                                               "\nApply it, repair the cart where necessary, then order.")
                                continue
                sh = self.swap_hint()
                gl = [i for i in self.cart_ids() if i in self.gone] if self.sold_holds < 2 else []
                if sh or gl:
                    if not sh:
                        self.sold_holds += 1
                    replies.append(HOLD_OPEN + " " + (sh or ("The carted lines " + ", ".join(gl) + " are sold out; replace that carted line first.")) + self.cart_footer())
                    continue
                ttxt, thold = self.trail()
                if thold:
                    replies.append(HOLD_OPEN + " " + ttxt + self.cart_footer())
                    continue
                if self.fit_holds < 2 and self.left() > self.reserve() + 3:
                    ff = self.fit_faults()
                    if ff:
                        self.fit_holds += 1
                        self.trace.append({"kind": "fit_hold", "faults": ff[:4]})
                        replies.append(HOLD_OPEN + " A carted part is incompatible with the carted device: " + "; ".join(ff[:3]) +
                                       ". Replace the part, or else the device, and then order." + self.cart_footer())
                        continue
                if self.line_holds < 2 and self.left() > self.reserve() + 2:
                    lf = self.line_faults()
                    if lf and all(k == "units" for k, _ in lf):
                        fixes = self.count_fixes()
                        if fixes:
                            lf = self.line_faults()
                            if not lf:
                                self.line_holds += 1
                                replies.append(HOLD_OPEN + " Cairn adjusted the unit counts itself: " + "; ".join(fixes) +
                                               ". If the store rejected any of those fixes, correct those lines; then order." + self.cart_footer())
                                continue
                    if lf:
                        self.line_holds += 1
                        self.trace.append({"kind": "line_hold", "faults": [t for _, t in lf[:6]]})
                        replies.append(HOLD_OPEN + " The cart and the request do not match yet: " + "; ".join(t for _, t in lf[:6]) +
                                       ". Correct those lines with the means the cart tool offers for adding and removing units, and then order." + self.cart_footer())
                        continue
                ids = self.cart_ids()
                facts = self.fill_facts(ids, self.reserve() + (1 if len(ids) >= 2 else 3))
                self.show_links(ids, self.reserve() + 1)
                facts += self.cheaper_rows()
                verdict = self.cart_check()
                if verdict:
                    t = BARE_HOLD
                    if ttxt:
                        t += " " + ttxt
                    if hunt_txt:
                        t += "\n" + hunt_txt + " " + self.below_cart() + "\n"
                    if facts:
                        t += "\n[Cairn fetched the attribute records of the listings below for this review, at one step apiece]\n" + "\n".join(facts)
                    replies.append(t + "\n" + verdict + self.cart_footer())
                    continue
                if changed and self.spend > SOFT:
                    replies.append(HOLD_OPEN + " Cairn has just fetched the cart's listings again: " + changed +
                                   "\nOrder again once all lines are still in stock and priced within budget; otherwise swap that line before ordering.")
                    continue
            if is_dec and self.left() > 5:
                dt = self.decline_trail()
                if dt:
                    replies.append(HOLD_OPEN + " " + dt)
                    continue
                self.fit_hunt()
                at = self.audit()
                if at:
                    replies.append(HOLD_OPEN + " " + at)
                    continue
                if self.leads and self.left() > 4 and self.decline_blocks == 0:
                    self.decline_blocks = 1
                    self.trace.append({"kind": "lead_hold", "leads": self.leads})
                    replies.append(HOLD_OPEN + " The review named listings that seem to fit: " + ", ".join(self.leads) + ". Open them "
                                   "where necessary, cart whichever fits best while obeying the pick rule, then order. Decline only if all of "
                                   "them plainly fail some requirement, and in that case state in your own reply text (not a shopper "
                                   "message) which one fails and send the decline once more.")
                    continue
                if self.leads and self.left() > 4 and self.decline_blocks == 1:
                    self.decline_blocks = 2
                    first = self.leads[0]
                    self.cart_check([first], HARD)
                    if self.verdicts.get(first + "#" + str(self.version)) is True and first in self.leads:
                        self.confirmed = first
                        self.trace.append({"kind": "confirmed", "id": first})
                        replies.append(HOLD_OPEN + " A second, separate check of " + first + "'s records finds that it satisfies all "
                                       "requirements. Cart it in the quantity asked and order; decline only when its record plainly breaks a requirement.")
                        continue
            if is_dec and self.left() <= 5 and not self.late_held:
                built = [i for i in self.built if not self.sold_out(i)]
                cart = set(self.cart_ids())
                missing = [i for i in built if i not in cart or (not self.fresh() and i in self.dropped_ids)]
                if len(built) >= len(self.items) and len(missing) + 1 <= self.left():
                    self.late_held = True
                    self.trace.append({"kind": "late_decline_hold", "missing": missing})
                    t = (HOLD_OPEN + " A decline scores zero whenever a fitting listing exists, and running low on steps is no evidence "
                         "about whether one exists. ")
                    if missing:
                        t += "Cart these lines again in the quantities asked: " + ", ".join(missing) + ", and order. "
                    else:
                        t += "Order the cart unchanged. "
                    t += ("Decline only if the searching proved that, for one of the requested items, no listing satisfies its "
                          "requirements, and in that case send the decline once more.")
                    replies.append(t)
                    continue
            if is_dec and not self.leads and not self.pushed and self.left() > self.budget_steps // 3:
                self.pushed = True
                replies.append(HOLD_OPEN + (" %d steps remain. Try untried kinds of search before giving up: list every requested "
                                            "item's category and page onward through that listing using the page token, or offset value, "
                                            "returned by the store; try one-word queries of values and alternative names of the property; "
                                            "open any listing that could fit. Decline only after all that." % self.left()))
                continue
            if is_dec:
                if self.confirmed:
                    ctx = self.complete_cart()
                    if ctx:
                        replies.append(ctx + (" [episode finished]" if self.finished else ""))
                        continue
                args = self.quiet_fill(args)
            if is_ord:
                lq = self.late_question()
                if lq:
                    replies.append(BARE_HOLD + " " + lq + self.cart_footer())
                    continue
            if fin and self.left() >= 2:
                go, gt = self.gate("order" if is_ord else "end")
                if not go:
                    replies.append(BARE_HOLD + " " + gt + self.cart_footer())
                    continue
                if gt:
                    tail.insert(0, "[Cairn] " + gt)
            res = self.env(tool, args)
            if res is None:
                replies.append("[Cairn] The call broke down through a network or server problem; you may retry it.")
                continue
            obs = res.get("observation")
            if tool == r.get("compare") and ct and isinstance(args.get(ct), list) and len(args[ct]) > 1:
                d = dump(obs)
                if not any(isinstance(x, str) and x in d for x in args[ct]):
                    self.cmp_bad = min(self.cmp_bad or 999, len(args[ct]))
                    tail.append("[Cairn] The comparison came back empty for %d listings. Send no more than %d per call." % (len(args[ct]), self.cmp_room()))
                else:
                    self.cmp_good = max(self.cmp_good, len(args[ct]))
            self.recent = (self.recent + [mark])[-3:]
            for k, v in args.items():
                vals = v if isinstance(v, list) and v else [v]
                if all(isinstance(x, str) and x in self.rows for x in vals):
                    self.id_args[(tool, k)] = True
            self.absorb(obs)
            if tool == r.get("compare"):
                recs = self.records_of(obs)
                if recs:
                    self.facts[tool] = self.facts.get(tool) is True or any(attr_block(x) for _, x in recs)
            if reader and tool != r.get("search"):
                self.note_view(tool, obs)
            notes = ""
            if search_like and not fin:
                notes += self.auto_page(tool, args, obs)
                if fresh:
                    notes += self.late_page(tool, args, obs)
                notes += self.shorter(tool, args, obs)
            if st and tool not in (r.get("cart"), r.get("buy"), r.get("refuse"), r.get("ask")) and isinstance(obs, dict):
                lid = self.listing_id(obs, False, 0)
                if lid:
                    self.fact_note(tool, bool(attr_block(obs)))
                    if tool == self.roles.get("open") and self.facts.get(tool) is False:
                        for t in self.names:
                            if t == tool or not self.single_target(t) or self.facts.get(t) is False:
                                continue
                            if t in (r.get("cart"), r.get("buy"), r.get("refuse"), r.get("ask"), r.get("search")) or self.lists_things(t):
                                continue
                            self.roles["open"] = t
                            break
                    if self.facts.get(tool) is False and tool != self.roles.get("open") and not self.roles.get("offer"):
                        self.roles["offer"] = tool
                    if tool == self.roles.get("offer") or (tool == self.roles.get("open") and not self.roles.get("offer")):
                        self.offer_seen[lid] = self.step
            if tool == r.get("cart"):
                self.note_cart(tool, args)
                self.cart_said = dump(obs)
                self.recent = []
                cnts = [count_of(v) for v in args.values() if not isinstance(v, (str, bool)) and count_of(v) is not None]
                if cnts:
                    for v in args.values():
                        if isinstance(v, str) and v in self.rows:
                            if cnts[0] <= 0 and not row_present(v, obs):
                                self.dropped_ids.add(v)
                            elif cnts[0] > 0:
                                self.dropped_ids.discard(v)
                cur = [i for i in self.cart_ids() if not self.sold_out(i) and i not in self.dropped_ids]
                if len(cur) >= len(self.built):
                    self.built = cur
            if tool == r.get("search") and self.names_code(args):
                self.code_tries.append(bool(self.records_of(obs)))
                if len(self.code_tries) >= 2 and not any(self.code_tries):
                    self.codes_dead = True
            if tool == r.get("search") and self.records_of(obs):
                self.searched = (self.searched + [dict(args)])[-8:]
            if tool == r.get("cart_view"):
                self.cart_view = obs
                self.cart_seen_at = self.step
            if is_ord:
                self.checkouts += 1
                if not self.finished:
                    self.refused_at = self.step
            txt = self.show(obs) + notes + (("\n" + "\n".join(tail)) if tail else "")
            if search_like and not fin:
                txt += self.cheapest_here(obs) + self.cap_ignored(tool, args, obs)
            cacheable = txt
            ev = self.evidence(obs)
            if ev:
                txt += "\n" + ev
            if tool == r.get("cart"):
                c0 = [count_of(v) for v in args.values() if not isinstance(v, (str, bool)) and count_of(v) is not None]
                if c0 and c0[0] == 0 and any(isinstance(v, str) and v in self.rows and row_present(v, obs) for v in args.values()):
                    txt += ("\n[Cairn] A zero count did not remove the line, since this tool adds the number given to the line; "
                            "removing units takes a negative number.")
            self.note_sold = False
            lines = self.loose(obs)
            loose_sold = False
            named = False
            if lines:
                m = self.read_note(lines)
                loose_sold = self.note_sold
                named = self.note_named
                if m:
                    txt += "\n[note read] " + m + " Carry this change into the picks before ordering."
            refused = is_ord and not self.finished
            again = refused and any(ln in self.spoken(obs) for ln in self.sold_lines)
            loosen = loose_sold and (refused or (not named and not is_ord))
            if (loosen or again) and self.cart_ids() and not self.finished:
                ss = self.sold_search()
                if ss:
                    txt += "\n[Cairn fetched the cart lines again following the rejection]\n" + ss
            self.note_sold = False
            sh = self.swap_hint()
            if sh:
                txt += "\n" + sh
            if tool == r.get("cart") and self.fit_pairs and not self.finished:
                ff = self.fit_faults()
                if ff:
                    txt += "\n[Cairn] These lines are not yet compatible with each other: " + "; ".join(ff)
            if self.queued:
                txt += "\n[seen during Cairn's own calls] " + " | ".join(self.queued)
                self.queued = []
            if reader:
                self.read_cache[mark] = (self.version, self.step, cacheable)
            if self.finished:
                txt += " [episode finished]"
            replies.append(txt)
        return replies

    def can_decline(self):
        t = self.roles.get("refuse")
        if not t:
            return False
        a = self.quiet_fill(dict(self.brief.get("refuse_args") or {}))
        _, f = shape_args(a, self.schemas.get(t) or {})
        return not f

    def finish(self, again=False):
        if self.finished or self.store_broke or self.left() <= 0:
            return ""
        holding = bool(self.cart_ids())
        whole = True
        if holding and len(self.items) >= 2:
            ok = self.fill_short()
            whole = ok or not self.can_decline()
        ids = self.cart_ids()
        if whole and len(ids) >= 2:
            self.fill_facts(ids, self.reserve())
            if self.left() >= 3 and self.room() > 5:
                self.show_links(ids, self.reserve())
        if not whole:
            self.trace.append({"kind": "short_cart_decline"})
        if self.finished or self.left() <= 0:
            return ""
        buy = self.roles.get("buy")
        if whole and buy and (holding or (self.cart_touched and not self.fresh() and self.left() >= 2)):
            oa, f = shape_args(dict(self.brief.get("buy_args") or {}), self.schemas.get(buy) or {})
            if not f:
                if self.left() >= 2:
                    self.gate("order")
                if self.finished or self.left() <= 0:
                    return ""
                res = self.env(buy, oa)
                self.trace.append({"kind": "forced_order", "answered": res is not None})
                if self.finished or self.left() <= 0:
                    return ""
                if again and res is not None:
                    self.checkouts += 1
                    self.refused_at = self.step
                    o = res.get("observation")
                    self.observe(buy, o)
                    return "the order was rejected: " + self.show(o)
        ref = self.roles.get("refuse")
        if ref:
            da, f = shape_args(self.quiet_fill(dict(self.brief.get("refuse_args") or {})), self.schemas.get(ref) or {})
            if not f:
                if self.left() >= 2:
                    self.gate("end")
                if self.finished or self.left() <= 0:
                    return ""
                res = self.env(ref, da)
                self.trace.append({"kind": "forced_decline", "answered": res is not None})
                if res is not None and not self.finished:
                    o = res.get("observation")
                    self.observe(ref, o)
                    return "the decline was rejected: " + self.show(o)
        return ""


_MISSING = object()


class G3A:
    def rec_label(self, rec):
        ck = self.cat_key()
        if ck is None or not isinstance(rec, dict):
            return ""
        v = rec.get(ck)
        return "" if v is None else str(v)

    def held_owners(self):
        return {self.owner(self.label_of(i)) for i in self.cart_ids()}

    def asked_later(self, sent):
        if isinstance(sent, bool):
            return sent
        if isinstance(sent, int):
            return sent != 0 and sent != 1
        if sent is None or sent == "" or sent == [] or sent == {}:
            return False
        return True

    def req_words(self):
        out = {}
        for n, r in self.live():
            v = r.split(":", 1)[1] if ":" in r else r
            out.setdefault(n, set()).update(_ALNUM3.findall(words(v)))
        return out

    def item_groups(self):
        ck = self.cat_key()
        groups = {}
        for i in self.order:
            row = self.rows.get(i) or {}
            cv = row.get(ck) if ck is not None else None
            lab = "" if cv is None else str(cv)
            groups.setdefault(lab, []).append(i)
        matched = [lab for lab in groups if self.label_matches(lab)]
        fits = {}
        best = {}
        for lab in matched:
            o = self.owner(lab)
            f = self.label_fit(lab, o) if o else 0
            fits[lab] = (o, f)
            if o:
                best[o] = max(best.get(o, 0), f)
        pool = [lab for lab in matched if not fits[lab][0] or best[fits[lab][0]] < 0.5 or fits[lab][1] >= LABEL_SHARE * best[fits[lab][0]]]
        pool = pool or list(groups)
        pool.sort(key=lambda lab: -len(groups[lab]))
        return [groups[lab] for lab in pool[:max(1, len(self.items))]]

    def page_param(self, tool, val):
        if isinstance(val, bool) or not isinstance(val, (str, int)):
            return None
        sc = self.schemas.get(tool) or {}
        props = sc.get("properties") if isinstance(sc.get("properties"), dict) else {}
        req = sc.get("required") if isinstance(sc.get("required"), list) else []
        sent = self.last_sent.get(tool) or {}
        cands = []
        for k, p in props.items():
            if not isinstance(p, dict) or k in req or "enum" in p:
                continue
            ks = kinds(p)
            if ks and not any(kind_fit(x, val) for x in ks):
                continue
            sv = sent.get(k) if isinstance(sent, dict) else None
            if isinstance(sv, str) and sv.strip():
                continue
            if V14_QUERY.search(under(k)):
                continue
            ml = p.get("maxLength")
            if isinstance(val, str) and isinstance(ml, int) and not isinstance(ml, bool) and len(val) > ml:
                continue
            if isinstance(val, int):
                mn, mx = p.get("minimum"), p.get("maximum")
                if (is_num(mn) and val < mn) or (is_num(mx) and val > mx):
                    continue
            cands.append(k)
        if isinstance(val, int):
            ints = [k for k in cands if "integer" in kinds(props[k])]
            if ints:
                cands = ints
        return cands[0] if len(cands) == 1 else None

    def read_shape(self, tool, obs):
        if tool in self.shapes:
            return self.shapes[tool]
        if not isinstance(obs, dict):
            return None
        cands = [k for k, v in obs.items() if isinstance(v, list) and len(v) >= 2 and all(isinstance(e, dict) for e in v)]
        if not cands:
            return None
        self.shapes[tool] = None
        sample = {k: (v[:3] if k in cands else v) for k, v in obs.items()}
        p = (SHAPE_PROMPT + "\n\nTOOL: " + tool + " | " + dump(self.schemas.get(tool) or {}) +
             "\n\nRESULT (only its first rows are shown):\n" + dump(clip(sample, 120))[:4000])
        ans = self.json_ask(p, [LIGHT, HEAVY], 2500) or {}
        rk = ans.get("rows")
        if not isinstance(rk, str) or rk not in cands:
            return None
        props = (self.schemas.get(tool) or {}).get("properties") or {}
        first = obs[rk][0]

        def ok(v, where):
            return v if isinstance(v, str) and v in where else None

        sh = {"rows": rk, "count": ok(ans.get("count"), obs), "next": ok(ans.get("next"), obs),
              "next_arg": ok(ans.get("next_arg"), props), "price": ok(ans.get("price"), first), "stock": ok(ans.get("stock"), first)}
        if sh["count"] is not None:
            c = obs.get(sh["count"])
            if isinstance(c, bool) or not isinstance(c, int):
                sh["count"] = None
        if not sh["next_arg"] and sh["next"] and obs.get(sh["next"]) is not None:
            sh["next_arg"] = self.page_param(tool, obs.get(sh["next"]))
        self.shapes[tool] = sh
        if self.price_key is None:
            if sh["price"]:
                self.price_key = sh["price"]
            else:
                mk = self.money_key(obs, sh)
                if mk:
                    self.price_key = mk
        if self.stock_key is None and sh["stock"]:
            self.stock_key = sh["stock"]
        self.trace.append({"kind": "shape", "tool": tool, "shape": sh})
        return sh

    def auto_page(self, tool, args, obs):
        self.paged = []
        if not PICKS3.fullmatch(self.pick()):
            return self.next_big_page(tool, args, obs)
        pl = self.paging(tool, obs)
        if not pl:
            return ""
        total, shown, arg, nx = pl
        if nx is None or self.asked_later(args.get(arg)) or total <= shown:
            return ""
        if self.pick() == "cheapest" and self.price_sorted(obs):
            return ""
        need = -(-(total - shown) // shown)
        if need > 2 and self.pages_read + 2 <= AUTO_PAGES and self.left() - self.reserve() - 2 >= 12:
            need = 2
        room = LAST_PAGE_ROOM if need == 1 else 12
        if need > 2 or self.pages_read + need > AUTO_PAGES or self.left() - self.reserve() - need < room:
            return ("\n[Cairn] This search matched %d listings but displayed only %d, and not sorted by price; the pick weighs "
                    "every listing that fits. Search again with tighter words, namely the value the requirement names, or request "
                    "the next page by sending %s set to %s." % (total, shown, arg, dump(nx)))
        lines = []
        cur = nx
        read = 0
        for _ in range(need):
            a = dict(args)
            a[arg] = cur
            a, faults = shape_args(a, self.schemas.get(tool) or {})
            if faults:
                break
            r = self.env(tool, a)
            if r is None or self.finished:
                break
            self.pages_read += 1
            o = r.get("observation")
            self.observe(tool, o)
            self.paged.append(o)
            txt = self.show(o)
            self.read_cache[tool + dump(a)] = (self.version, self.step, txt)
            lines.append(str(arg) + "=" + dump(cur) + ": " + txt)
            read += 1
            pl2 = self.paging(tool, o)
            if not pl2 or pl2[3] is None:
                cur = None
                break
            cur = pl2[3]
        self.trace.append({"kind": "auto_pages", "pages": read})
        if not read:
            return ""
        out = "\n[Cairn fetched the following pages of this search by itself, one step per page]\n" + "\n".join(lines)
        if cur is not None:
            out += ("\n[Cairn] The search matched %d listings and Cairn has now read %d rows. Make the search tighter with the "
                    "value the requirement names, or keep requesting pages, so the remaining listings come into view." % (total, shown * (read + 1)))
        return out

    def next_big_page(self, tool, args, obs):
        if self.budget_steps < BIG_STEP_LINE or self.left() - self.reserve() < BIG_SPARE:
            return ""
        pl = self.paging(tool, obs)
        if not pl:
            return ""
        total, shown, arg, nx = pl
        if nx is None or self.asked_later(args.get(arg)) or total <= shown or not self.cat_key():
            return ""
        rowo = {self.owner(self.rec_label(rec)) for _, rec in self.records_of(obs)} - {0}
        if not rowo or rowo <= self.held_owners():
            return ""
        a = dict(args)
        a[arg] = nx
        a, f = shape_args(a, self.schemas.get(tool) or {})
        if f:
            return ""
        r = self.env(tool, a)
        if r is None or self.finished:
            return ""
        self.pages_read += 1
        o = r.get("observation")
        self.observe(tool, o)
        self.paged.append(o)
        txt = self.show(o)
        self.read_cache[tool + dump(a)] = (self.version, self.step, txt)
        self.trace.append({"kind": "next_big_page", "tool": tool})
        return "\n[Cairn fetched this search's following page on its own, at a cost of one step]\n" + str(arg) + "=" + dump(nx) + ": " + txt

    def big_opens(self, tool, args, obs):
        if self.budget_steps < BIG_STEP_LINE or self.left() - self.reserve() < BIG_SPARE or not self.cat_key():
            return ""
        held = self.held_owners()
        rw = self.req_words()
        pool = []
        seen = set()
        for o in [obs] + list(self.paged):
            for i, rec in self.records_of(o):
                ow = self.owner(self.rec_label(rec))
                if not ow or ow in held or i in self.full or not self.buyable(i) or self.sold_out(i) or i in seen:
                    continue
                seen.add(i)
                hits = len(rw.get(ow, set()) & set(_ALNUM3.findall(words(dump(self.rows.get(i) or rec)))))
                pr = (self.price(i) or 0) if self.pick() == "cheapest" else 0
                pool.append((-hits, pr, i))
        pool.sort()
        picks = [i for _, _, i in pool[:BIG_OPENS]]
        if not picks:
            return ""
        texts = self.fill_facts(picks, self.reserve() + BIG_SPARE)
        if not texts:
            return ""
        self.trace.append({"kind": "big_opens", "ids": picks})
        return "\n[The attribute records below were fetched by Cairn on its own, at a cost of one step per listing]\n" + "\n".join(texts)

    @soft("")
    def end_reads(self, tool, args, obs):
        if self.budget_steps >= BIG_STEP_LINE or self.pick() != "cheapest" or not self.paged or not self.price_key:
            return ""
        pl = self.paging(tool, self.paged[-1])
        if pl and pl[3] is not None:
            return ""
        if self.left() - self.reserve() < END_ROOM or not self.cat_key():
            return ""
        held = self.held_owners()
        pool = []
        seen = set()
        for o in [obs] + list(self.paged):
            for i, rec in self.records_of(o):
                ow = self.owner(self.rec_label(rec))
                if not ow or ow in held or i in self.full or self.price(i) is None or not self.buyable(i) or self.sold_out(i) or i in seen:
                    continue
                seen.add(i)
                pool.append((self.price(i), i))
        pool.sort()
        picks = [i for _, i in pool[:END_READS]]
        if not picks:
            return ""
        texts = self.fill_facts(picks, self.reserve() + END_ROOM - END_READS - 1)
        if not texts:
            return ""
        self.trace.append({"kind": "end_reads", "ids": picks})
        ev = self.evidence_ids([i for i in picks if i in self.full])
        out = ("\n[Cairn on its own fetched the attribute records of the lowest-priced rows of this search, at one step per row, "
               "since a cheapest pick is in force and the search has now been read through its final page]\n" + "\n".join(texts))
        if ev:
            out += "\n" + ev
        return out

    def series_sweep(self):
        st = self.roles.get("search")
        if self.budget_steps < BIG_STEP_LINE or not self.fit_pairs or not st or not self.cat_key() or self.left() - self.reserve() < BIG_SPARE:
            return ""
        fi = self.fit_index()
        sc = self.schemas.get(st) or {}
        lines = []
        for part, main in self.fit_pairs:
            sysm = self.system(part, main)
            if not sysm or sysm[0] != part:
                continue
            fam = sysm[2]
            proven = [i for i in self.item_listings(part) if i in self.full and self.buyable(i) and not self.sold_out(i) and self.proves(i, part)]
            want = set()
            for i in proven:
                want |= set(fi[i]["series"]) & fam
            key = (main, frozenset(want))
            if not proven or len(proven) > PINNED_SERIES or not want or key in self.series_swept:
                continue

            def names_it():
                f2 = self.fit_index()
                return any(set(f2[j]["named"]) & want and self.buyable(j) and not self.sold_out(j) for j in self.item_listings(main))

            if names_it():
                continue
            self.series_swept.add(key)
            dw = set(_ALNUM3.findall(words(self.items[main - 1].name)))
            for r in self.live_of(self.items[main - 1]):
                dw |= set(_ALNUM3.findall(words(r.split(":", 1)[1] if ":" in r else "")))
            spent = 0
            for t, a0, res in list(self.remembered.values()):
                if t != st:
                    continue
                if main not in {self.owner(self.rec_label(rec)) for _, rec in self.records_of(res)}:
                    continue
                if not (dw & text_words(" ".join(v for v in a0.values() if isinstance(v, str)).lower())):
                    continue
                cur, ca = res, dict(a0)
                walked = {self.call_mark(st, a0)}
                while spent < SERIES_PAGES and self.left() - self.reserve() >= BIG_SPARE and not self.finished and not names_it():
                    pl = self.paging(st, cur)
                    if not pl or pl[3] is None:
                        break
                    a2 = dict(ca)
                    a2[pl[2]] = pl[3]
                    a2, f = shape_args(a2, sc)
                    if f:
                        break
                    mk = self.call_mark(st, a2)
                    if mk in walked:
                        break
                    walked.add(mk)
                    if mk in self.remembered:
                        cur, ca = self.remembered[mk][2], a2
                        continue
                    r = self.env(st, a2)
                    spent += 1
                    if r is None:
                        break
                    o = r.get("observation")
                    self.observe(st, o)
                    self.pages_read += 1
                    lines.append(str(pl[2]) + "=" + dump(pl[3]) + " of " + dump(a0) + ": " + self.show(o))
                    cur, ca = o, a2
                if names_it() or spent >= SERIES_PAGES:
                    break
            f2 = self.fit_index()
            hits = [j for j in self.item_listings(main) if set(f2[j]["named"]) & want and self.buyable(j) and not self.sold_out(j) and j not in self.full][:BIG_OPENS]
            texts = self.fill_facts(hits, self.reserve() + BIG_SPARE // 2) if hits else []
            self.trace.append({"kind": "series_sweep", "main": main, "series": sorted(want), "pages": spent, "hits": hits})
            if lines or texts:
                lines.append("[" + self.items[main - 1].name + ": its rows mentioning the series " + ", ".join(sorted(want)) +
                             ", the series carried by the sole opened listings of the " + self.items[part - 1].name +
                             " proving each requirement]: " + (", ".join(hits) if hits else "none found"))
                lines += texts
        if not lines:
            return ""
        return ("\n[Cairn on its own went through further pages of searches for the item the parts are meant to fit, one step per page]\n" +
                "\n".join(lines))

    def cap_repeat(self, tool, args):
        ca = self.ceiling_args(tool)
        if len(ca) != 1 or ca[0] not in args:
            return ""
        c = ca[0]
        props = (self.schemas.get(tool) or {}).get("properties") or {}
        mode = tuple(sorted((k, dump(v)) for k, v in args.items() if isinstance(props.get(k), dict) and isinstance(props[k].get("enum"), list)
                            and isinstance(v, (str, int, float))))
        if self.ceiling_evidence(tool).get((c, mode)) != "fails":
            return ""
        others = {k: v for k, v in args.items() if k != c}
        for t, a0, res in reversed(list(self.remembered.values())):
            if t != tool or a0.get(c, _MISSING) == args[c]:
                continue
            if {k: v for k, v in a0.items() if k != c} != others or not self.records_of(res):
                continue
            self.trace.append({"kind": "cap_repeat", "tool": tool})
            return (SKIP_OPEN + " This mode of the search ignores " + str(c) + ", as its rows went over it; so the identical search with " +
                    str(c) + " at " + dump(a0.get(c)) + " has already given precisely these rows:\n" + self.show(res)[:3000])
        return ""

    @soft("")
    def dear_page(self, lines):
        st = self.roles.get("search")
        if self.budget_steps >= BIG_STEP_LINE or self.pick() != "cheapest" or self.left() - self.reserve() < DEAR_ROOM or not self.cat_key() or not st:
            return ""
        sc = self.schemas.get(st) or {}
        for line in lines:
            p = self.price(line)
            lab = self.label_of(line)
            ow = self.owner(lab)
            if p is None or not ow or ow in self.dear_paged:
                continue
            for t, a0, res in reversed(list(self.remembered.values())):
                if t != st or line not in [i for i, _ in self.records_of(res)]:
                    continue
                pl = self.paging(st, res)
                if not pl or pl[3] is None:
                    continue
                a2 = dict(a0)
                a2[pl[2]] = pl[3]
                a2, f = shape_args(a2, sc)
                if f or self.call_mark(st, a2) in self.remembered:
                    continue
                pr = [self.price(i) for i, _ in self.records_of(res) if self.buyable(i) and self.price(i) is not None]
                if len(pr) < 4 or sum(1 for x in pr if x < p) < DEAR_SHARE * len(pr):
                    continue
                self.dear_paged.add(ow)
                r = self.env(st, a2)
                if r is None or self.finished:
                    return ""
                o = r.get("observation")
                self.observe(st, o)
                self.pages_read += 1
                below = sorted((self.price(i), i) for i, rec in self.records_of(o) if i not in self.full and self.buyable(i)
                               and self.price(i) is not None and self.price(i) < p and self.rec_label(rec) == lab)[:2]
                ids = [i for _, i in below]
                texts = self.fill_facts(ids, self.reserve() + DEAR_ROOM - 4) if ids else []
                self.trace.append({"kind": "dear_page", "line": line, "read": ids})
                ev = self.evidence_ids([i for i in ids if i in self.full])
                out = ("\n[Cairn] " + line + " is pricier than the majority of rows in the search that displayed it, so with a cheapest "
                       "pick Cairn fetched the following page of that search (" + str(pl[2]) + "=" + dump(pl[3]) + ", one step): " + self.show(o))
                if texts:
                    out += ("\nand Cairn also read the attribute records of that page's lowest-priced rows that cost less than the cart "
                            "line (a single step apiece):\n" + "\n".join(texts))
                if ev:
                    out += "\n" + ev
                return out
        return ""


_ORW = re.compile(r"\bor\b", re.I)
_CHOICE_CUT = re.compile(r"\s*,\s*|\s+or\s+", re.I)
_UNIT_PARTS = re.compile(r"([\d.]+)\s*([A-Za-z]+)")
_BARE_NUM = re.compile(r"[A-Za-z]+\s+(\d{3,})")


class G3B:
    def bshow(self, v, limit):
        t = self.show(v)
        if len(t) <= limit:
            return t
        return rdump(v, ROW_CLIP if self.records_of(v) else TEXT_CLIP, limit)

    def hunt_sets(self, n):
        txt = " ".join(v.lower() for s in self.searched for v in s.values() if isinstance(v, str))
        plainv = [v for v, _ in self.value_words(n) if not find_codes(v)]
        reft = {t for _, t in self.refs}
        choices = []
        for i, r in self.live():
            if choices or i != n or ":" not in r or r in reft:
                continue
            v = r.split(":", 1)[1].strip()
            if not _ORW.search(v) or V3_OPENX.search(_ORW.sub(" ", v)):
                continue
            parts = [p.strip(" .") for p in _CHOICE_CUT.split(v)]
            parts = [p for p in parts if p]
            if len(parts) < 2:
                continue
            ch = [p for p in parts if not find_codes(p) and len(p) <= HUNT_VALUE_LEN][:HUNT_CHOICES]
            if ch:
                choices = ch
        raws = [plainv + [c] for c in choices] if choices else [list(plainv)]
        out = []
        for s in raws:
            res = []
            changed = []
            for v in s:
                t = v.strip()
                m = _UNIT_PARTS.fullmatch(t) if UNIT_VALUE.fullmatch(t) else None
                if m:
                    other = (m.group(1) + m.group(2)) if " " in t else (m.group(1) + " " + m.group(2))
                    res.append(other)
                    changed.append((v, other))
                else:
                    res.append(v)
            s2 = res if changed and any(v.lower() in txt and o.lower() not in txt for v, o in changed) else s
            if s2 not in out:
                out.append(s2)
        first = out[0]
        bare = []
        for v in first:
            t = v.strip()
            m = _BARE_NUM.fullmatch(t)
            bare.append(m.group(1) if m else t)
        if bare != first and bare not in out:
            out.append(bare)
        return out

    def item_hunt(self, n, tpl, room):
        tool, fixed, field = tpl
        sc = self.schemas.get(tool) or {}
        tried = self.hunt_tried.setdefault(n, set())
        noun, _ = self.hunt_words(n)
        sets = self.hunt_sets(n)
        st = {"spent": 0, "gain": 0, "idle": 0, "refused": False}

        def run(q):
            tried.add(q.lower())
            a = dict(fixed)
            a[field] = q
            a, f = shape_args(a, sc)
            if f:
                st["refused"] = True
                return False, False
            if st["spent"] >= room or self.finished:
                return False, False
            ql = q.lower()
            holds = any(s and all(v.lower() in ql for v in s) for s in sets)
            found = False
            visited = set()
            while not self.finished and self.clock() <= HUNT_DEADLINE + HUNT_GRACE:
                mk = self.call_mark(tool, a)
                if mk in visited:
                    break
                visited.add(mk)
                if mk in self.remembered:
                    o = self.remembered[mk][2]
                    got = HUNT_YIELD
                else:
                    if st["spent"] >= room:
                        break
                    before = self.item_rows(n)
                    r = self.env(tool, a)
                    if r is None:
                        break
                    st["spent"] += 1
                    o = r.get("observation")
                    self.observe(tool, o)
                    got = self.item_rows(n) - before
                    st["gain"] += got
                    st["idle"] = 0 if got else st["idle"] + 1
                recs = self.records_of(o)
                if recs:
                    found = True
                if holds:
                    self.value_rows.update(i for i, _ in recs)
                pl = self.paging(tool, o)
                if not pl or pl[3] is None or (got < HUNT_YIELD and pl[0] > HUNT_WHOLE):
                    break
                a2 = dict(a)
                a2[pl[2]] = pl[3]
                a, f = shape_args(a2, sc)
                if f:
                    break
            return True, found

        key = (n, tuple(tuple(s) for s in sets))
        if key not in self.hunt_stems:
            stem = ""
            for s in sets:
                if not s:
                    continue
                tries = []
                cand = [" ".join(s + [noun]).strip(), " ".join(s)]
                if len(s) >= 2:
                    cand.append(" ".join(s[:-1] + [noun]).strip())
                for t in cand:
                    if t not in tries:
                        tries.append(t)
                for t in tries:
                    issued, found = run(t)
                    if not issued:
                        return st["spent"], st["gain"]
                    if found:
                        if not stem:
                            stem = t
                        break
            if not stem and noun:
                issued, found = run(noun)
                if not issued:
                    return st["spent"], st["gain"]
                if found:
                    stem = noun
                else:
                    self.hunt_nonoun.add(n)
            self.hunt_stems[key] = stem
        stem = self.hunt_stems[key]
        while st["spent"] < room and st["idle"] < HUNT_IDLE and not st["refused"] and not self.finished and self.clock() <= HUNT_DEADLINE + HUNT_GRACE:
            _, ws = self.hunt_words(n)
            sw = set(stem.lower().split())
            ws = [w for w in ws if (w + " " + stem).strip().lower() not in tried and w not in sw]
            if not ws:
                break
            run((ws[0] + " " + stem).strip())
        return st["spent"], st["gain"]

    @soft("")
    def opening(self):
        tpl = self.value_template()
        if not tpl or self.budget_steps < OPEN_MIN_STEPS or len(self.items) < OPEN_MIN_ITEMS:
            return ""
        tool, fixed, field = tpl
        sc = self.schemas.get(tool) or {}
        self.gap = OPENING_GAP
        stop = self.budget_steps - self.reserve() - self.free_msgs() - LATER_STEPS_PER_ITEM * len(self.items) - HUNT_RESERVE // 2
        lines = []
        vsearch = []
        reft = {t for _, t in self.refs}
        for n, it in enumerate(self.items, 1):
            vals = []
            for m in it.musts:
                if ":" not in m or m in reft:
                    continue
                v = m.split(":", 1)[1].strip()
                if v and len(v.split()) <= 3 and not V3_OPENX.search(v):
                    vals.append(v)
            nw = it.name.split()
            noun = it.name if len(nw) <= 3 else " ".join(nw[-2:])
            tries = []
            if vals:
                tries.append(" ".join(vals[:2] + [noun]))
            if noun not in tries:
                tries.append(noun)
            singles = [vals[0] + " " + noun, vals[1] + " " + noun] if len(vals) >= 2 else []
            while tries:
                t = tries.pop(0)
                a = dict(fixed)
                a[field] = t
                a, f = shape_args(a, sc)
                if f or self.finished or self.step >= stop:
                    break
                r = self.env(tool, a)
                if r is None:
                    return "\n".join(lines)
                o = r.get("observation")
                self.observe(tool, o)
                recs = self.records_of(o)
                if recs:
                    self.searched = (self.searched + [dict(a)])[-8:]
                    lines.append(t + ": " + self.show(o))
                    if vals and t != noun:
                        org = self.item_origins.setdefault(n, [])
                        for i, _ in recs:
                            if i not in org:
                                org.append(i)
                        vsearch.append((n, dict(a), o))
                    pl = self.paging(tool, o)
                    if pl and pl[3] is not None and self.item_rows(n) < ROWS_PER_ITEM and not self.finished and self.step < stop:
                        a2 = dict(a)
                        a2[pl[2]] = pl[3]
                        a2, f2 = shape_args(a2, sc)
                        if not f2:
                            r2 = self.env(tool, a2)
                            if r2 is not None:
                                o2 = r2.get("observation")
                                self.observe(tool, o2)
                                lines.append("next page: " + self.show(o2))
                    tries = [x for x in tries if x not in singles]
                    if self.item_rows(n) >= ROWS_PER_ITEM:
                        break
                else:
                    fo = failure_only(o)
                    lines.append(t + (": the store rejected the call: " + self.show(o) if fo else ": no rows"))
                    if singles and t not in singles and t != noun and not fo:
                        tries = [x for x in singles if x not in tries] + tries
        lines += self.value_pages(tool, vsearch, stop)
        if self.rows and self.roles.get("ask") and self.free_msgs() > 0:
            found = [n for n in range(1, len(self.items) + 1) if self.item_rows(n) > 0]
            start = self.step
            while self.step - start < self.budget_steps // WIDEN_SHARE and self.step < stop and not self.finished:
                if all(self.item_records(n) >= ROWS_PER_ITEM for n in found):
                    break
                before = len(self.full)
                self.widen_compare()
                if len(self.full) <= before:
                    break
        self.gap = STORE_GAP
        sw = self.series_sweep()
        for i in list(self.full):
            lines.append("read in full: " + self.page_text(i))
        if sw:
            lines.append(sw.strip("\n"))
        ev = self.evidence_ids(list(self.full))
        if ev:
            lines.append(ev)
        return "\n".join(lines)

    def value_pages(self, tool, vs, stop):
        big = self.budget_steps >= BIG_STEP_LINE
        if (self.pick() != "cheapest" and not big) or self.swept:
            return []
        ck = self.cat_key()
        q = []
        for n, a, o in vs:
            pl = self.paging(tool, o)
            if not pl or pl[3] is None or not (SWEEP_MIN <= pl[0] <= SWEEP_MAX):
                continue
            if self.pick() == "cheapest" and self.price_sorted(o):
                continue
            recs = self.records_of(o)
            own = sum(1 for _, rec in recs if ck and self.owner(self.rec_label(rec)) == n)
            if not own * 2 > len(recs):
                continue
            q.append((pl[0], n, a, pl))
        if not q:
            return []
        self.swept = True
        q.sort(key=lambda x: -x[0])
        k = max(VS_SWEEPS, len(self.items)) if big else VS_SWEEPS
        lines = []
        for _, n, a, pl in q[:k]:
            lines += self.vs_sweep(tool, n, a, pl, stop)
        return lines

    def vs_sweep(self, tool, n, args, pl, stop):
        lines = []
        read = 0
        a = dict(args)
        sc = self.schemas.get(tool) or {}
        org = self.item_origins.setdefault(n, [])
        guard = 0
        while pl and pl[3] is not None and read < VS_PAGES and stop - self.step >= SWEEP_KEEP and not self.finished and guard < 100:
            guard += 1
            a2 = dict(a)
            a2[pl[2]] = pl[3]
            a2, f = shape_args(a2, sc)
            if f:
                break
            mk = self.call_mark(tool, a2)
            if mk in self.remembered:
                o = self.remembered[mk][2]
            else:
                r = self.env(tool, a2)
                if r is None:
                    break
                o = r.get("observation")
                self.observe(tool, o)
                self.pages_read += 1
                read += 1
                lines.append("next page: " + self.show(o))
            for i, _ in self.records_of(o):
                if i not in org:
                    org.append(i)
            a = a2
            pl = self.paging(tool, o)
        if lines:
            self.trace.append({"kind": "value_pages", "item": n, "pages": read})
        return lines

    def widen_single(self):
        ft = self.facts_tool()
        tgt = self.single_target(ft) if ft else None
        if not ft or not tgt:
            return
        per = {}
        for n, r in self.live():
            val = r.split(":", 1)[1] if ":" in r else r
            per.setdefault(n, set()).update(_ALNUM3.findall(val.lower()))
        allw = set()
        for v in per.values():
            allw |= v
        size = WIDEN_PER_ITEM if len(self.items) <= 2 else 4
        ck = self.cat_key()
        lanes = []
        heads = []
        for g in self.item_groups():
            opened = sum(1 for i in g if i in self.full)
            pool = [i for i in g if i not in self.full and self.buyable(i)]
            glab = self.label_of(g[0]) if g and ck else ""
            owners = [n for n in range(1, len(self.items) + 1) if glab and self.owns(n, glab)]
            wanted = set()
            found = set()
            for n in owners:
                wanted |= per.get(n, set())
                found |= set(self.item_origins.get(n, []))
            if not owners:
                wanted = allw

            def key(i, wanted=wanted, found=found):
                hits = len(wanted & set(_ALNUM3.findall(words(dump(self.rows.get(i) or {})))))
                k = (i not in found, -hits)
                if self.pick() == "cheapest":
                    k += (self.price(i) is None, self.price(i) or 0)
                return k

            pool.sort(key=key)
            k = size - opened
            lanes.append(pool[:k] if k > 0 else [])
            heads.append(max(0, 4 - opened))
        first = []
        more = []
        for rk in range(4):
            for ln, hd in zip(lanes, heads):
                if rk < hd and rk < len(ln):
                    first.append(ln[rk])
        for rk in range(size):
            for ln, hd in zip(lanes, heads):
                if rk >= hd and rk < len(ln):
                    more.append(ln[rk])
        cut = max(5, 2 * len(lanes) + 2)
        got = self.fill_facts(first[:min(cut, 8)], 22)
        rest = (first[cut:] + more)[:max(0, 10 - len(got))]
        self.fill_facts(rest, 30)



class G4A:
    def label_text(self, n):
        ck = self.cat_key()
        if not ck or not (1 <= n <= len(self.items)):
            return None
        cands = sorted({str(r.get(ck)).strip() for r in self.rows.values() if r.get(ck) is not None and str(r.get(ck)).strip()})
        it = self.items[n - 1]
        targets = [roots(it.name)]
        if it.shelf.strip():
            targets.append(roots(it.shelf))
        for c in cands:
            if roots(c) in targets and self.owner(c) == n:
                return c
        return None

    def label_line(self):
        if len(self.items) < 2 or not self.cat_key():
            return ""
        lt = {}
        for n in range(1, len(self.items) + 1):
            t = self.label_text(n)
            if t:
                lt[n] = t
        paired = set()
        for a in lt:
            for b in lt:
                if a != b and roots(lt[a]) < roots(lt[b]):
                    paired.add(a)
                    paired.add(b)
        if len(paired) < 2:
            return ""
        ps = sorted(paired)
        if all(self.items[n - 1].shelf and words(self.items[n - 1].shelf) == words(lt[n]) for n in ps):
            return ""
        ents = "; ".join("item %d (%s) under '%s'" % (n, self.items[n - 1].name, lt[n]) for n in ps)
        return ("store labels: " + ents + ". Any listing counts toward one item only, the item whose category label that listing "
                "carries, and what its title says does not change this; find each of these items by listing that item's own label.")

    def label_fit(self, label, n):
        if not label or not (1 <= n <= len(self.items)):
            return 0
        it = self.items[n - 1]
        lw = words(label)
        if lw == words(it.shelf) or self.adopted.get(label) == n:
            return 3
        if lw == words(it.name):
            return 2
        ir = roots(it.shelf) | roots(it.name)
        lr = roots(label)
        return len(lr & ir) / max(1, len(lr | ir))

    def budget_guard(self, v):
        b = self.budget
        if not is_num(v) or v <= 0 or not is_num(b) or b <= 0:
            return v
        if b / 30.0 <= v <= b * 30:
            return v
        for c in (v * 100.0, v / 100.0):
            if b / 3.0 <= c <= b * 3:
                r = round(c, 6)
                self.trace.append({"kind": "budget_unit", "read": v, "kept": r})
                return int(r) if r == int(r) else r
        return v

    def fit_faults(self):
        if not self.fit_pairs:
            return []
        fi = self.fit_index()
        cart = self.cart_ids()
        out = []
        for part, main in self.fit_pairs:
            dev = [i for i in cart if self.owns(main, self.label_of(i))]
            pls = [i for i in cart if self.owns(part, self.label_of(i))]
            if len(dev) != 1 or not pls:
                continue
            dcodes = (fi.get(dev[0]) or {}).get("models") or []
            lf = []
            for line in pls:
                if dcodes and self.covers(line, dcodes):
                    continue
                lf += self.link_faults(part, main, dev[0], [line])
            if lf:
                out += lf
                continue
            if not dcodes:
                continue
            for line in pls:
                fs = self.fit_set(line)
                if not fs or self.covers(line, dcodes):
                    continue
                good = [i for i in self.item_listings(part) if self.covers(i, dcodes) and not self.sold_out(i) and i not in cart][:4]
                t = "%s (%s) is meant for %s, against %s (%s)" % (line, self.items[part - 1].name, ", ".join(sorted(fs)[:4]), dev[0], ", ".join(sorted(dcodes)))
                if good:
                    t += "; compatible parts of the same sort: " + ", ".join(good)
                else:
                    t += ("; none of the seen parts of this sort suits the device. Hunt for a part that suits it, or change the device: " +
                          self.fit_plan(True))
                out.append(t)
        return out


_PROOF_TOK = re.compile(r"[a-z0-9+#]+")
_LIST_SEP = re.compile(r"[,/;|]")
_AMOUNT_M = re.compile(r"(?<![a-z0-9])\d[\d.,]*\s*[a-z\"']{1,12}")
_AMOUNT_HEAD = re.compile(r"^[\d.,\s]+")
_DECIMAL = re.compile(r"\d\.\d")
_LOWER_ONLY = re.compile(r"[a-z]+")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_NUMLET = re.compile(r"(\d+(?:\.\d+)?)\s*([a-z]*)")
_HAS_LETTER = re.compile(r"[a-z]")
_LRUN = re.compile(r"[a-z]+")
_VISIBLE = re.compile(r"[a-z0-9]+")
_ABBR_CUT = re.compile(r"\s*,\s*|\s+or\s+")
_CHOICE_SPLIT = re.compile(r"\s+or\s+")
_OR_WORD = re.compile(r"\bor\b")
PLACEHOLDER_LEAD = "whatever the listing"


def proof_tokens(text):
    return _PROOF_TOK.findall(words(text))


def list_pieces(text):
    out = []
    for part in _LIST_SEP.split(str(text)):
        t = proof_tokens(part)
        if t:
            out.append(t)
    return out


class G4B:
    def owners_of(self, i):
        lab = self.label_of(i)
        return [n for n in range(1, len(self.items) + 1) if self.owns(n, lab)]

    def judged(self, n):
        return [r for r in self.live_of(self.items[n - 1]) if not self.described(n, r)]

    def measured(self, req):
        if ":" not in req:
            return None
        val = req.split(":", 1)[1]
        raw = val.lower()
        for m in _AMOUNT_M.finditer(raw):
            unit = _AMOUNT_HEAD.sub("", m.group(0))
            if V3_OPENX.fullmatch(unit):
                continue
            if not (_DECIMAL.search(raw) or V3_OPENX.search(words(val))):
                return None
            return unit if _LOWER_ONLY.fullmatch(unit) else ""
        return None

    def bare_off(self, req, val):
        u = self.measured(req)
        if not u:
            return None
        t = str(val).strip().lower().replace(",", "")
        if not _NUM.fullmatch(t):
            return None
        num = float(t)
        m = _NUM.search(req.split(":", 1)[1].replace(",", ""))
        tgt = float(m.group(0)) if m else 0
        if num <= 0 or tgt <= 0:
            return None
        if num >= 10 * tgt or 10 * num <= tgt:
            return num
        return None

    def misread(self, block, req):
        pr = roots(req.split(":", 1)[0])
        cands = [v for k, v in block.items() if roots(k) & pr and _DIGIT.search(str(v))]
        return bool(cands) and all(self.bare_off(req, v) is not None for v in cands)

    def gives_qty(self, block, prop, unit):
        pr = roots(prop)
        for k, v in block.items():
            if not (roots(k) & pr):
                continue
            s = str(v).lower()
            if not _DIGIT.search(s):
                continue
            if not unit or not _HAS_LETTER.search(s) or re.search(r"\d[\s-]*" + re.escape(unit), s):
                return True
        return False

    def split_wording(self, req, texts):
        if not texts:
            return False
        val = req.split(":", 1)[1] if ":" in req else ""
        if _LIST_SEP.search(val) or V3_OPENX.search(words(val)) or self.measured(req) is not None:
            return False
        return split_run(val, " | ".join(texts))

    def lists_codes(self, i, codes):
        m = self.fit_index().get(i) or {}
        acc = list(m.get("works", [])) + list(m.get("models", []))
        bar = m.get("barred", [])
        return all(any(code_covers(a, c) for a in acc) and not any(code_covers(b, c) for b in bar) for c in codes)

    def title_of(self, i):
        rec = self.full.get(i) or {}
        tk = self.title_key() or "title"
        for v in (rec.get(tk), rec.get("title"), (self.rows.get(i) or {}).get("title")):
            if isinstance(v, str):
                return v
        return ""

    def states_word(self, i, req, strict=False):
        rec = self.full.get(i) or {}
        block = attr_block(rec) or {}
        prop, _, val = req.partition(":")
        toks = value_tokens(val)
        if not toks:
            return True
        ps = spelled(prop)
        keyed = [v for k, v in block.items() if names(ps, spelled(k))]
        if keyed:
            if self.split_wording(req, [str(v) for v in keyed]):
                return False
            if not strict:
                return True
            kt = [glued(dump(v)) for v in keyed]
            return any(t in x for t in toks for x in kt) or any(kin(t, w) for t in toks for x in kt for w in _LRUN.findall(x))
        codes = find_codes(val)
        if codes and self.lists_codes(i, codes):
            return True
        page = glued(" ".join([dump(v) for v in block.values()] + [self.title_of(i)]))
        if any(t in page for t in toks) or any(kin(t, w) for t in toks for w in _LRUN.findall(page)):
            return True
        vis = set(_VISIBLE.findall(page))
        for piece in _ABBR_CUT.split(val.lower()):
            lr = _LRUN.findall(piece)
            for a in range(len(lr)):
                for b in range(a + 3, len(lr) + 1):
                    if "".join(w[0] for w in lr[a:b]) in vis:
                        return True
        return False

    def proves(self, i, n, reqs=None):
        rec = self.full.get(i)
        block = attr_block(rec) if rec else None
        if not block:
            return False
        t = rec.get("title") if isinstance(rec.get("title"), str) else (self.rows.get(i) or {}).get("title")
        ttoks = set(proof_tokens(t)) if isinstance(t, str) else set()
        if reqs is None:
            reqs = self.judged(n) if 1 <= n <= len(self.items) else []
        if not reqs:
            return False
        inw = set()
        if 1 <= n <= len(self.items):
            inw = spelled(self.items[n - 1].name)
            inw.add("of")
        lines = []
        for r in reqs:
            prop, _, val = r.partition(":")
            vt = set(proof_tokens(val))
            if not vt or V3_OPENX.search(words(val)):
                return False
            ps = spelled(prop)
            match = [k for k in block if names(ps, spelled(k))]
            fuller = [k for k in match if spelled(k) > ps and spelled(k) <= (ps | inw)]
            if fuller:
                mx = max(len(spelled(k)) for k in fuller)
                fuller = [k for k in fuller if len(spelled(k)) == mx]
            deciding = fuller or [k for k in match if spelled(k) == ps]
            disagree = []
            if fuller:
                disagree = [k for k in match if spelled(k) == ps and not any(vt <= set(pc) for pc in list_pieces(block[k]))]
            sat = False
            for k in (deciding or match):
                v = block[k]
                pcs = list_pieces(v)
                cov = [pc for pc in pcs if vt <= set(pc)]
                if self.split_wording(r, [str(v)]):
                    cov = []
                plural = words(k) != words(prop) and spelled(k) == ps
                if cov and plural and len(pcs) > 1 and any(set(pc) <= ttoks for pc in pcs if pc not in cov) and not any(set(pc) <= ttoks for pc in cov):
                    cov = []
                if deciding and not cov:
                    return False
                if cov:
                    sat = True
                    if len(lines) < len(reqs):
                        ln = str(k) + ": " + clip(str(v), 160)
                        if disagree:
                            d = disagree[0]
                            ln += (" (this key extends the property's name with the requested item's name, and for that reason it wins "
                                   "over the plain key " + str(d) + ", which gives " + clip(str(block[d]), 60) + ")")
                        lines.append(ln)
            if not sat:
                return False
        self.proofs[i] = lines
        return True

    def literal(self, i, req):
        u = self.measured(req)
        if u is None:
            return None
        prop, _, val = req.partition(":")
        fl = V13_FLOOR.search(val.strip())
        if not fl and V3_OPENX.search(words(val)):
            return None
        m = _NUM.search((fl.group(1) if fl else val.strip()).replace(",", ""))
        if not m:
            return None
        want = float(m.group(0))
        block = attr_block(self.full.get(i)) or {}
        ps = spelled(prop)
        kept = []
        for k, v in block.items():
            if not names(ps, spelled(k)):
                continue
            mm = _NUMLET.search(str(v).lower().replace(",", ""))
            if not mm:
                continue
            let = mm.group(2)
            if not u or not let or let.rstrip("s") == u.rstrip("s"):
                kept.append(float(mm.group(1)))
        if not kept:
            return None
        if fl:
            return any(x >= want - 1e-9 for x in kept)
        return any(abs(x - want) <= 1e-9 for x in kept)

    def resolved(self, n):
        ptrs = {t for (i, t) in self.refs if i == n}
        out = []
        for r in self.judged(n):
            if r in ptrs:
                v = str(self.ref_values.get(r) or "")
                if not v or v.startswith(PLACEHOLDER_LEAD) or V3_OPENX.search(words(v)):
                    return None
                out.append(r.split(":", 1)[0].strip() + ": " + v)
            else:
                out.append(r)
        return out

    def pointer_items(self):
        livet = {t for _, t in self.live()}
        return {i for (i, t) in self.refs if t in livet}

    def meets_words(self, i, n, literal=False):
        if i not in self.full or not self.buyable(i) or self.sold_out(i) or self.price(i) is None:
            return False
        reqs = self.resolved(n)
        if not reqs:
            return False
        if any(self.described(n, r) for r in self.live_of(self.items[n - 1])):
            return False
        block = attr_block(self.full[i]) or {}
        for r in reqs:
            prop, _, val = r.partition(":")
            ms = self.measured(r) is not None
            if literal and ms:
                if self.literal(i, r) is not True:
                    return False
                continue
            if ms or V3_OPENX.search(_OR_WORD.sub(" ", words(val))):
                return False
            if any(names(spelled(prop), spelled(k)) for k in block):
                choices = [c.strip() for c in _CHOICE_SPLIT.split(val.strip()) if c.strip()] or [val.strip()]
                if not any(self.proves(i, n, [prop.strip() + ": " + c]) for c in choices):
                    return False
            elif not self.states_word(i, r, True):
                return False
        return True

    def code_link(self, piece, dev):
        fi = self.fit_index()
        dm = (fi.get(dev) or {}).get("models") or []
        if not dm:
            return False
        bar = (fi.get(piece) or {}).get("barred", [])
        return any(code_covers(c, d) for c in self.fit_set(piece) for d in dm) and not any(code_covers(b, d) for b in bar for d in dm)

    def keeps_links(self, n, cand, cart):
        for part, main in self.fit_pairs:
            if n != part and n != main:
                continue
            partner = main if n == part else part
            pl = self.item_listings(partner)
            plines = [c for c in cart if c in pl]
            if not plines:
                return False
            sysm = self.system(part, main)
            for line in plines:
                dev, piece = (line, cand) if n == part else (cand, line)
                if sysm:
                    carried, naming = (piece, dev) if sysm[0] == part else (dev, piece)
                    if self.link_holds(carried, naming, sysm[2]) is not True:
                        return False
                elif not self.code_link(piece, dev):
                    return False
        return True

    def cost_factor(self, n):
        return 1 if self.brief.get("budget_scope") == "each" else self.items[n - 1].quantity

    @soft(list)
    def read_sets(self, literal=False):
        if not self.fit_pairs:
            return []
        mains = {m for p, m in self.fit_pairs}
        if len(mains) != 1:
            return []
        main = list(mains)[0]
        parts = sorted({p for p, m in self.fit_pairs})
        q = {}
        for n in range(1, len(self.items) + 1):
            q[n] = [i for i in self.item_listings(n) if self.meets_words(i, n, literal)]
            if not q[n]:
                return []
        rem = {}
        rtot = 0.0
        for n in range(1, len(self.items) + 1):
            if n == main or n in parts:
                continue
            best = min(q[n], key=lambda i: self.price(i))
            rem[best] = self.items[n - 1].quantity
            rtot += self.price(best) * self.cost_factor(n)
        sets = []
        for d in q[main]:
            lines = dict(rem)
            lines[d] = self.items[main - 1].quantity
            total = rtot + self.price(d) * self.cost_factor(main)
            ok = True
            for p in parts:
                sysm = self.system(p, main)
                fits = []
                for c in q[p]:
                    if sysm:
                        carried, naming = (c, d) if sysm[0] == p else (d, c)
                        good = self.link_holds(carried, naming, sysm[2]) is True
                    else:
                        good = self.code_link(c, d)
                    if good:
                        fits.append(c)
                if not fits:
                    ok = False
                    break
                best = min(fits, key=lambda i: self.price(i))
                lines[best] = self.items[p - 1].quantity
                total += self.price(best) * self.cost_factor(p)
            if not ok or len(lines) != len(self.items):
                continue
            if is_num(self.budget) and self.brief.get("budget_scope") != "each" and total > self.budget + 1e-9:
                continue
            sets.append({"ids": list(lines), "lines": lines, "total": total})
        sets.sort(key=lambda s: (s["total"], sorted(s["ids"])))
        return sets

    def set_text(self, sets):
        return "; ".join(" + ".join(i + ((" x%d" % u) if u > 1 else "") for i, u in s["lines"].items()) + " = " + gnum(s["total"]) for s in sets[:SETS_SHOWN])

    def run_cart_calls(self, calls, observe=True, stop_on_finish=True):
        tool = self.roles.get("cart")
        sc = self.schemas.get(tool) or {}
        done = []
        for a in calls:
            a2, f = shape_args(a, sc)
            if f:
                return done, False
            r = self.env(tool, a2)
            if r is None:
                return done, False
            if stop_on_finish and self.finished:
                return done, False
            self.note_cart(tool, a2)
            if observe:
                self.observe(tool, r.get("observation"))
            done.append(dump(a2))
        return done, True

    @soft(False)
    def cart_set(self, lines):
        cart = self.cart_ids()
        rem = [i for i in cart if i not in lines]
        ch = {i: u for i, u in lines.items() if self.cart_lines.get(i) != u}
        calls = self.cart_calls(ch, rem) if (ch or rem) else []
        if calls is None or not self.roles.get("cart") or len(calls) + 1 > self.left():
            return False
        _, ok = self.run_cart_calls(calls)
        if not ok:
            return False
        self.version += 1
        self.trace.append({"kind": "cart_set", "lines": lines})
        return True

    def cheaper_proven(self):
        if self.pick() != "cheapest" or not self.cat_key():
            return []
        cart = [i for i in self.cart_ids() if self.held(i) > 0]
        out = []
        for line in cart:
            lab = self.label_of(line)
            own = self.owners_of(line)
            p = self.price(line)
            if len(own) != 1 or p is None:
                continue
            reqs = self.resolved(own[0])
            if reqs is None:
                continue
            cands = [i for i in self.full if i not in cart and i not in self.gone and self.buyable(i) and not self.sold_out(i)
                     and self.label_of(i) == lab and self.price(i) is not None and self.price(i) < p - 1e-9
                     and self.proves(i, own[0], reqs) and self.keeps_links(own[0], i, cart)]
            if cands:
                best = min(cands, key=lambda i: self.price(i))
                out.append((line, p, best, self.price(best)))
        return out

    def cheaper_text(self, recs):
        ents = []
        for line, p, c, cp in recs:
            e = c + " at " + gnum(cp) + " instead of " + line + " at " + gnum(p)
            if self.proofs.get(c):
                e += " (" + "; ".join(self.proofs[c]) + ")"
            ents.append(e)
            self.cheaper_named.add((line, c))
        return ("The request chooses by lowest price, and an already-opened listing costs less and gives every requirement beneath "
                "the attribute key carrying that requirement's property: " + "; ".join(ents) + ". Swap that line, by the means the "
                "cart tool itself offers for removing and adding units, and then check out; the current line may stay only if the "
                "cheaper listing's record clearly violates one of the requirements." + self.swap_links(recs))

    @soft("")
    def swap_links(self, recs):
        bound = {x for pr in self.fit_pairs for x in pr}
        if not bound:
            return ""
        kept = []
        cart = self.cart_ids()
        for line, p, c, cp in recs:
            if not any(line in self.item_listings(n) for n in bound):
                continue
            ids = [c if x == line else x for x in cart]
            pat = re.compile(r"(?:^| )" + re.escape(c) + r"(?: |$)")
            for ln in self.code_fits(ids):
                if ln.startswith(c) or pat.search(ln):
                    kept.append(ln)
        if not kept:
            return ""
        return (" Fit by code: " + "; ".join(kept[:3]) + ". The store settles compatibility through these codes; a purpose, a size "
                "or a count of seats that some description mentions cannot overturn that.")

    @soft("")
    def agreed_swap(self):
        if self.swap_agreed or self.pick() != "cheapest":
            return ""
        cart = self.cart_ids()
        better = self.check_better.get("|".join(sorted(cart)) + "#" + str(self.version), [])

        def link(old, new):
            for n in range(1, len(self.items) + 1):
                if old in self.item_listings(n):
                    return any(n in pr for pr in self.fit_pairs) and self.keeps_links(n, new, cart)
            return False

        pairs = [(ln, c) for (ln, p, c, cp) in self.cheaper_proven() if (ln, c) in self.cheaper_named and (c in better or link(ln, c))]
        if not pairs:
            return ""
        wanted = {c: (self.cart_lines.get(ln) or 1) for ln, c in pairs}
        tool = self.roles.get("cart")
        calls = self.cart_calls(wanted, [ln for ln, c in pairs]) if tool else None
        if not tool or not calls or self.left() < len(calls) + 2 + self.reserve():
            return ""
        self.swap_agreed = True
        done, _ = self.run_cart_calls(calls)
        cur = set(self.cart_ids())
        for ln, c in pairs:
            if ln not in cur:
                self.dropped_ids.add(ln)
            if c in cur:
                self.dropped_ids.discard(c)
        built = [i for i in self.cart_ids() if not self.sold_out(i) and i not in self.dropped_ids]
        if len(built) >= len(self.built):
            self.built = built
        self.version += 1
        self.trace.append({"kind": "agreed_swap", "pairs": pairs, "calls": done})
        if all(c in better for ln, c in pairs):
            reason = "Cairn's reading of the pages and the separate review both point to the cheaper listing"
        else:
            reason = "Cairn's reading of the pages points to the cheaper listing, whose own codes preserve compatibility with the remaining cart lines"
        return ("Cairn carried out the swap on its own, because " + reason + ": " + "; ".join(c + " instead of " + ln for ln, c in pairs) +
                " (" + "; ".join(done) + "). Check out now.")

    def word_shown(self, line, req):
        lab = self.label_of(line)
        same = [i for i in self.order if i != line and self.label_of(i) == lab]
        opened = [i for i in same if attr_block(self.full.get(i))]
        if len(opened) < 3 or any(self.states_word(i, req, True) for i in opened):
            return True
        tk = self.title_key() or "title"
        toks = value_tokens(req.split(":", 1)[1] if ":" in req else "")
        for i in same:
            t = (self.rows.get(i) or {}).get(tk)
            if isinstance(t, str) and any(x in glued(t) for x in toks):
                return True
        return False

    def weak_lines(self):
        if not self.cat_key():
            return []
        ptr = {t for _, t in self.refs}
        out = []
        for line in [i for i in self.cart_ids() if self.held(i) > 0]:
            rec = self.full.get(line)
            block = attr_block(rec) if rec else None
            own = self.owners_of(line)
            if not block or len(own) != 1:
                continue
            n = own[0]
            weak = []
            for r in self.live_of(self.items[n - 1]):
                if r in ptr or ":" not in r or self.described(n, r):
                    continue
                u = self.measured(r)
                if u is not None:
                    if not self.gives_qty(block, r.split(":", 1)[0], u) or self.misread(block, r):
                        weak.append(r)
                elif not V3_OPENX.search(_OR_WORD.sub(" ", words(r.split(":", 1)[1]))) and not self.states_word(line, r, False) and self.word_shown(line, r):
                    weak.append(r)
            if weak:
                out.append((line, n, weak))
        return out

    def weak_text(self, wl):
        named = []
        cart = set(self.cart_ids())
        for line, n, reqs in wl[:2]:
            props = [r.split(":", 1)[0].strip() for r in reqs]
            lab = self.label_of(line)
            alts = [i for i in self.order if i not in cart and i != line and self.label_of(i) == lab and self.buyable(i)
                    and not self.sold_out(i) and i not in self.gone]
            if is_num(self.budget) and self.brief.get("budget_scope") == "each":
                alts = [i for i in alts if (self.price(i) or 0) <= self.budget]

            def settles(i, r):
                b = attr_block(self.full.get(i)) or {}
                u = self.measured(r)
                if u is not None:
                    return self.gives_qty(b, r.split(":", 1)[0], u) and not self.misread(b, r)
                return self.states_word(i, r, True)

            strong = [i for i in alts if i in self.full and all(settles(i, r) for r in reqs)]
            unopened = [i for i in alts if i not in self.full]
            pr = set()
            for p in props:
                pr |= roots(p)
            lrec = self.full.get(line)
            lt_raw = lrec.get("title") if lrec is not None else (self.rows.get(line) or {}).get("title")
            lt = roots(lt_raw) if isinstance(lt_raw, str) else set()
            unopened.sort(key=lambda i: (not (roots(dump(self.rows.get(i) or {})) & pr),
                                         -len(roots(str((self.rows.get(i) or {}).get("title") or "")) & lt),
                                         self.price(i) is None, self.price(i) or 0))
            block = attr_block(lrec) or {}
            sizes = [r.split(":", 1)[0].strip() for r in reqs if self.measured(r) is not None]
            wordings = [r.strip() for r in reqs if self.measured(r) is None]
            cl = []
            if sizes:
                cl.append(line + " does not give " + ", ".join(sizes) + " under a key bearing each property's name (a number filed "
                          "under some other quantity's key, a number printed within the title, or no number at all leaves grading "
                          "unable to decide the requirement, and the order gets failed on that account)")
                mis = [r.split(":", 1)[0].strip() for r in reqs if self.measured(r) is not None and self.misread(block, r)]
                if mis:
                    cl.append(line + " gives " + ", ".join(mis) + " only as a number without a unit; such a number is taken in the "
                              "unit the requirement uses, and so taken it lies far outside what the requirement allows")
            if wordings:
                cl.append("neither any attribute's value nor the title of " + line + " contains the value wanted by " + "; ".join(wordings) +
                          " (a neighbouring attribute carrying a different sort of value, such as a series of numbers, or wording "
                          "present solely in the line's description, keeps the requirement undecided unless the page expresses it some other way)")
            t = "; ".join(cl)
            if strong:
                strong.sort(key=lambda i: (self.price(i) is None, self.price(i) or 0))
                t += ("; the following already-opened listings of that same kind give it beneath the key of that very property: " +
                      ", ".join(i + ((" (" + gnum(self.price(i)) + ")") if self.price(i) is not None else "") for i in strong[:3]))
            elif unopened and self.left() > self.reserve() + 5:
                t += "; open first the following listings of the same kind: " + ", ".join(unopened[:3])
            else:
                continue
            named.append(t)
        if not named:
            return ""
        self.trace.append({"kind": "weak_hold", "lines": [w[0] for w in wl]})
        return (" | ".join(named) + ". Change to some listing that both states each requirement (a quantity bound beneath the key of its "
                "own property; a wanted word inside an attribute or inside the title) and satisfies it, while obeying the pick rule; "
                "after that, check out. The line may stay only if there is no listing that both states and satisfies every requirement in that way.")

    def proven_basket(self):
        tool = self.roles.get("cart")
        if not tool or not self.items:
            return False
        if self.pointer_items() or self.fit_pairs:
            return False
        lines = {}
        total = 0.0
        for n in range(1, len(self.items) + 1):
            c = [i for i in self.item_listings(n) if i in self.full and self.buyable(i) and not self.sold_out(i)
                 and self.price(i) is not None and self.proves(i, n)]
            if not c:
                return False
            best = min(c, key=lambda i: self.price(i))
            lines[best] = self.items[n - 1].quantity
            total += self.price(best) * self.cost_factor(n)
        if is_num(self.budget) and self.brief.get("budget_scope") != "each" and total > self.budget + 1e-9:
            return False
        calls = self.cart_calls(lines, [])
        if not calls or len(calls) + 1 > self.left():
            return False
        _, ok = self.run_cart_calls(calls, observe=False, stop_on_finish=False)
        if not ok:
            return False
        self.trace.append({"kind": "proven_basket", "lines": lines})
        return True



class G5A:
    @soft(dict)
    def proven_lines(self):
        each = self.brief.get("budget_scope") == "each"
        nit = len(self.items)
        res = {}
        tot = 0.0
        for n in range(1, nit + 1):
            cands = list(self.full) if nit == 1 else self.item_listings(n)
            cands = [i for i in cands if i not in self.gone and self.meets_words(i, n, True)]
            if each and is_num(self.budget):
                cands = [i for i in cands if (self.price(i) or 0) <= self.budget + 1e-9]
            if not cands:
                return {}
            best = min(cands, key=lambda i: (self.price(i) or 0, i))
            res[n] = best
            tot += (self.price(best) or 0) * self.items[n - 1].quantity
        if is_num(self.budget) and not each and tot > self.budget + 1e-9:
            return {}
        return res

    def line_fit(self, n, cand, dev):
        fi = self.fit_index()
        for part, main in self.fit_pairs:
            if part != n or not dev or dev not in self.item_listings(main):
                continue
            sysm = self.system(part, main)
            if sysm:
                carried, naming = (cand, dev) if sysm[0] == part else (dev, cand)
                h = self.link_holds(carried, naming, sysm[2])
                return 1 if h is True else (-1 if h is False else 0)
            dm = (fi.get(dev) or {}).get("models") or []
            fs = self.fit_set(cand)
            if not dm or not fs:
                return 0
            bar = (fi.get(cand) or {}).get("barred", [])
            return 1 if any(code_covers(c, d) for c in fs for d in dm) and not any(code_covers(b, d) for b in bar for d in dm) else -1
        return 0

    def need_hits(self, i, n):
        ptr = {t for (j, t) in self.refs if j == n}
        block = attr_block(self.full.get(i)) or {}
        met = 0
        judged = 0
        for r in self.live_of(self.items[n - 1]):
            if self.described(n, r):
                continue
            if r in ptr:
                v = str(self.ref_values.get(r) or "")
                if not v or v.startswith(PLACEHOLDER_LEAD) or V3_OPENX.search(words(v)):
                    continue
                r = r.split(":", 1)[0].strip() + ": " + v
            prop, _, val = r.partition(":")
            if self.measured(r) is not None:
                if not V13_FLOOR.search(val.strip()) and V3_OPENX.search(words(val)):
                    continue
                ok = self.literal(i, r) is True
            else:
                if V3_OPENX.search(_OR_WORD.sub(" ", words(val))):
                    continue
                if any(names(spelled(prop), spelled(k)) for k in block):
                    choices = [c.strip() for c in _CHOICE_SPLIT.split(val.strip()) if c.strip()] or [val.strip()]
                    ok = any(self.proves(i, n, [prop.strip() + ": " + c]) for c in choices)
                else:
                    ok = self.states_word(i, r, True)
            judged += 1
            met += 1 if ok else 0
        return met, judged

    def ok_hits(self, c, n):
        m, j = self.need_hits(c, n)
        return m > 0 or j == 0

    @soft(False)
    def closest_cart(self):
        r = self.roles
        if not r.get("cart") or not r.get("buy") or not self.cat_key() or self.finished or len(self.items) < 2:
            return False
        cur = [i for i in self.cart_ids() if self.held(i) > 0]
        if not cur and not self.ever_carted:
            return False
        nit = len(self.items)
        each = self.brief.get("budget_scope") == "each"

        def owner_of(i):
            return self.owner(self.label_of(i))

        def cu(n):
            return 1 if each else self.items[n - 1].quantity

        leads = {}
        for k, ids in self.lead_items.items():
            if _DIGITS.fullmatch(str(k)):
                leads[int(k)] = ids
        lines = {}
        for i in cur:
            o = owner_of(i)
            if 1 <= o <= nit and o not in lines and self.buyable(i) and i not in self.gone:
                lines[o] = i
        kept = dict(lines)

        def device(n):
            for part, main in self.fit_pairs:
                if part == n and main in lines:
                    return lines[main]
            return None

        def pool(n):
            ln = set(lines.values())
            return [i for i in self.item_listings(n) if i in self.full and self.buyable(i) and i not in self.gone and self.price(i) is not None and i not in ln]

        def rank(n, c):
            fs = self.line_fit(n, c, device(n))
            for part, main in self.fit_pairs:
                if main == n and part in lines:
                    fs += self.line_fit(part, lines[part], c)
            return (fs, c in self.ever_carted, c in leads.get(n, []), self.need_hits(c, n)[0], -(self.price(c) or 0), c)

        def room(cost):
            if not is_num(self.budget):
                return True
            if each:
                return cost <= self.budget + 1e-9
            held = 0.0
            for m, i in lines.items():
                p = self.price(i) or 0
                held += p * ((self.held(i, 0) or 1) if kept.get(m) == i else cu(m))
            return held + cost <= self.budget + 1e-9

        mains = sorted({m for p, m in self.fit_pairs})
        order = mains + [n for n in range(1, nit + 1) if n not in mains]
        swapped = []
        for n in order:
            dev = device(n)
            if n in lines:
                if self.line_fit(n, lines[n], dev) >= 0:
                    continue
                old = lines.pop(n)
                cands = sorted([c for c in pool(n) if self.line_fit(n, c, dev) == 1 and self.ok_hits(c, n)], key=lambda c: rank(n, c), reverse=True)
                pick = next((c for c in cands if room((self.price(c) or 0) * cu(n))), None)
                if pick:
                    lines[n] = pick
                    swapped.append(old)
                else:
                    lines[n] = old
            else:
                opts = sorted([c for c in pool(n) if self.line_fit(n, c, dev) >= 0 and self.ok_hits(c, n)], key=lambda c: rank(n, c), reverse=True)
                pick = next((c for c in opts if room((self.price(c) or 0) * cu(n))), None)
                if not pick:
                    self.trace.append({"kind": "closest_cart_gap", "item": n, "options": len(opts)})
                    return False
                lines[n] = pick
        wanted = {}
        for n, i in lines.items():
            wanted[i] = (self.cart_lines.get(i) or self.held(i, 0) or 1) if kept.get(n) == i else self.items[n - 1].quantity
        drops = list(swapped)
        for i in cur:
            if i not in wanted and i not in swapped and (not self.buyable(i) or i in self.gone) and owner_of(i) in lines:
                drops.append(i)
        calls = self.cart_calls(wanted, drops)
        if calls is None or len(calls) + 1 > self.left():
            return False
        done, ok = self.run_cart_calls(calls)
        if not ok:
            return False
        if done:
            self.version += 1
        self.trace.append({"kind": "closest_cart", "wanted": wanted, "drops": drops, "kept": list(kept.values())})
        return True

    def code_fits(self, ids):
        fi = self.fit_index()
        out = []
        for part, main in self.fit_pairs:
            ml = self.item_listings(main)
            devs = [i for i in ids if i in ml]
            if len(devs) != 1:
                continue
            d = devs[0]
            sysm = self.system(part, main)
            dm = (fi.get(d) or {}).get("models") or []
            pl = self.item_listings(part)
            for i in ids:
                if i not in pl:
                    continue
                if sysm:
                    carried, naming = (i, d) if sysm[0] == part else (d, i)
                    if self.link_holds(carried, naming, sysm[2]) is True:
                        shared = sorted(set(fi[carried]["series"]) & set(fi[naming]["named"]) & sysm[2])
                        out.append("%s (%s) and %s (%s): %s bears the series %s, which %s names" % (
                            i, self.items[part - 1].name, d, self.items[main - 1].name, carried, ", ".join(shared), naming))
                else:
                    fs = self.fit_set(i)
                    bar = (fi.get(i) or {}).get("barred", [])
                    cov = sorted(c for c in dm if any(code_covers(x, c) for x in fs) and not any(code_covers(b, c) for b in bar))
                    if cov:
                        out.append("%s (%s) names the code that identifies the device %s (%s): %s" % (
                            i, self.items[part - 1].name, d, self.items[main - 1].name, ", ".join(c.upper() for c in cov)))
        for i in ids:
            lo = self.owners_of(i)
            if len(lo) != 1:
                continue
            for n, r in self.live():
                if n != lo[0]:
                    continue
                codes = find_codes(r.split(":", 1)[1] if ":" in r else "")
                if codes and self.lists_codes(i, codes):
                    out.append("%s satisfies the requirement '%s': its fit clause lists %s" % (i, r, ", ".join(c.upper() for c in codes)))
        return out

    def line_faults(self):
        self.adopt()
        lines = [i for i in self.cart_ids() if self.held(i) > 0]
        if not lines or not self.cat_key():
            return []
        nit = len(self.items)
        owners = {i: [n for n in range(1, nit + 1) if self.owns(n, self.label_of(i))] for i in lines}
        seen = {self.label_of(i) for i in self.order}
        known = [n for n in range(1, nit + 1) if any(self.owns(n, x) for x in seen)]
        out = []
        for n in known:
            it = self.items[n - 1]
            mine = [i for i in lines if n in owners[i]]
            if not mine:
                f = "item %d (%s) lacks a cart line" % (n, it.name)
                own = self.label_text(n)
                if own:
                    ow = words(own)
                    orr = roots(own)
                    stand = [i for i in lines if self.label_of(i) and words(self.label_of(i)) != ow and roots(self.label_of(i)) & orr]
                    if stand:
                        bits = []
                        for i in stand:
                            lab = self.label_of(i)
                            x = "%s bears its own label '%s'" % (i, lab)
                            lo = [m for m in range(1, nit + 1) if self.owns(m, lab)]
                            if len(lo) == 1:
                                x += " (that label belongs to item %d)" % lo[0]
                            bits.append(x)
                        f += (" (this item's own listings bear its category label '%s'; %s, so %s not count toward item %d, whatever the "
                              "title says: list the label '%s' and source this item's line there)" % (
                                  own, ", ".join(bits), "this line does" if len(stand) == 1 else "these lines do", n, own))
                out.append(("other", f))
                continue
            if len([i for i in mine if owners[i] == [n]]) > 1:
                out.append(("other", "item %d (%s) has %d cart lines (%s); keep one" % (n, it.name, len(mine), ", ".join(mine))))
            for i in mine:
                h = self.held(i)
                if owners[i] == [n] and h != it.quantity:
                    out.append(("units", "%s is held at %d %s; item %d (%s) wants %d" % (i, h, "unit" if h == 1 else "units", n, it.name, it.quantity)))
                lab = self.label_of(i)
                alt = self.fuller_label(n, lab) or self.named_label(n, lab)
                if alt:
                    out.append(("other", "%s comes from the label %r while the store also has the label %r, which names item %d (%s) completely; source this line from %r instead" % (i, lab, alt, n, it.name, alt)))
        if len(known) == nit:
            for i in lines:
                if not owners[i]:
                    out.append(("other", "%s (%s) is a kind nobody requested; remove it" % (i, self.label_of(i) or "unknown kind")))
        for i in lines:
            if self.sold_out(i):
                out.append(("other", "%s is sold out" % i))
        if is_num(self.budget) and all(self.price(i) is not None for i in lines):
            if self.brief.get("budget_scope") == "each":
                for i in lines:
                    p = self.price(i)
                    if self.budget < p <= 10 * self.budget:
                        out.append(("other", "%s costs %s, over the per-item limit of %s" % (i, gnum(p), gnum(self.budget))))
            else:
                tot = sum(self.price(i) * self.held(i) for i in lines)
                if tot > self.budget + 1e-9 and tot <= 10 * self.budget:
                    out.append(("other", "the cart totals %s, over the budget of %s" % (gnum(tot), gnum(self.budget))))
        return out

    def cart_check(self, planned=None, limit=SOFT):
        ids = list(planned) if planned else self.cart_ids()
        key = "|".join(sorted(ids)) + "#" + str(self.version)
        js = self.judges(limit)
        if key in self.checked or not js or not ids:
            return ""
        self.checked.add(key)
        parts = [CHECK_PROMPT, "REQUEST:\n" + self.request, "REQUIREMENTS NOW BINDING:\n" + self.ledger()]
        if planned:
            parts.append("CART (planned only: judge it as though these listings sat in the cart, each at its asked quantity): " +
                         "; ".join("item %d: quantity %d" % (n, it.quantity) for n, it in enumerate(self.items, 1)) + "\n" + ", ".join(ids))
        else:
            parts.append("CART:\n" + self.cart_text())
        recs = []
        for i in ids:
            so = "SOLD OUT (the store reports this listing cannot be purchased any more) " if self.sold_out(i) else ""
            recs.append(i + ": " + so + self.rec_text(i))
        parts.append("RECORDS OF THE CARTED LISTINGS:\n" + "\n".join(recs))
        weak = [] if planned else self.weak_lines()
        if weak:
            parts.append("REQUIREMENTS THESE RECORDS LEAVE UNSTATED (a measured limit is counted only when it is filed beneath a key "
                         "carrying the name of the property; a word the shopper wants is counted only within some attribute's value or "
                         "within the title, never from an attribute that is related but holds a different sort of value, and never from "
                         "the description), so each requirement listed is to be taken as unmet unless the line's record expresses it in "
                         "different wording:\n" + "\n".join(ln + ": " + "; ".join(rs) for ln, n, rs in weak))
        cf = self.code_fits(ids)
        if cf:
            parts.append("FITS PROVEN BY CODES (these codes are how the store settles compatibility, between two listings or between a "
                         "listing and a device that is named, and every line below holds; a listing description naming a different "
                         "purpose, measurement or number of seats does not cancel it):\n" + "\n".join(cf))
        if PICKS3.fullmatch(self.pick()):
            parts.append("OTHER LISTINGS SEEN (newest first):\n" + "\n".join(self.others(set(ids), 15)))
        prompt = "\n\n".join(parts)
        ans = None
        if len(js) == 2 and not planned and not self.audited and not PICKS3.fullmatch(self.pick()) and not weak:
            ans = self.json_ask(prompt, [LIGHT], 3000)
            if ans is not None:
                js = [HEAVY] if (ans.get("ok") is False and HEAVY in self.judges(limit)) else []
        if js and not self.no_credit:
            a2 = self.json_ask(prompt, js, 3000)
            if a2 is not None:
                ans = a2
        self.trace.append({"kind": "cart_check", "ids": ids, "ok": None if ans is None else ans.get("ok")})
        self.verdicts[key] = ans is not None and ans.get("ok") is not False
        if ans is None or ans.get("ok") is not False:
            return ""
        self.leads = [x for x in self.leads if x not in ids]
        probs = [str(p) for p in listify(ans.get("problems"))][:5]
        better = [str(b) for b in listify(ans.get("better")) if str(b) in self.rows and not self.sold_out(str(b))][:4]
        if not planned:
            self.check_better[key] = better
        t = "A careful review finds the cart still wrong: " + ("; ".join(probs) if probs else "see the requirements in the ledger") + "."
        if better:
            t += " Candidates that seem preferable: " + ", ".join(better) + "."
        t += " Repair the cart, or else demonstrate that the reviewer erred by reading the records afresh, and then check out."
        return t


_SQUASH_DOT = re.compile(r"[^a-z0-9.]")
_SQUASH = re.compile(r"[^a-z0-9]")
_VTOK = re.compile(r"[a-z0-9][a-z0-9.]*")
_QSEP = re.compile(r"[,;]+")
_KEYRUN = re.compile(r"[a-z]{3,}")


class G5B:
    def shop_names(self, i):
        return self.name_cands(self.rows.get(i) or {})

    def names_shop(self, i, text):
        t = str(text).lower()
        return any(token_in(c.lower(), t) for c in self.shop_names(i))

    def key_words(self):
        out = set()
        for rec in self.full.values():
            for k in (attr_block(rec) or {}):
                out |= set(_KEYRUN.findall(words(k)))
        return out

    def read_misses(self, i, vals):
        if not vals or i not in self.full:
            return False
        lv = " ".join(str(v) for v in (attr_block(self.full[i]) or {}).values()).lower()
        if not lv:
            return False
        return any(not token_in(w, lv) for w in vals)

    def shop_rows(self, desc, ids, vals=None):
        d = desc.lower()
        return [i for i in ids if i not in self.opened and not (vals and self.read_misses(i, vals))
                and any(token_in(c.lower(), d) for c in self.name_cands(self.rows.get(i) or {}))]

    def chain_match(self, text, pend):
        for pt in pend:
            if pt[1].strip() == text:
                return pt
        if len(pend) == 1:
            return pend[0]
        ws = set(_ANYRUN.findall(text.lower()))
        scored = []
        for k, pt in enumerate(pend):
            pw = set(_ANYRUN.findall(pt[1].lower()))
            scored.append((len(ws & pw) / (len(ws | pw) or 1), k, pt))
        scored.sort(key=lambda x: (-x[0], x[1]))
        if ws and len(scored) >= 2 and scored[0][0] >= 0.6 and scored[0][0] - scored[1][0] > 0.15:
            return scored[0][2]
        return None

    def map_link_id(self, t):
        if not t or t in self.rows:
            return t
        cont = [i for i in self.rows if len(i) >= 6 and i in t]
        if len(cont) == 1:
            return cont[0]
        if len(t) < 3 or len(t) > 40 or not _DIGIT.search(t):
            return t
        pat = re.compile(r"(?<![a-z0-9])" + re.escape(t.lower()) + r"(?![a-z0-9])")
        tk = self.title_key()
        if tk:
            hits = [i for i in self.order if isinstance((self.rows.get(i) or {}).get(tk), str) and pat.search(self.rows[i][tk].lower())]
            if len(hits) == 1:
                self.trace.append({"kind": "link_id", "given": t, "id": hits[0]})
                return hits[0]
            if hits:
                return t
        hits = [i for i in self.order if pat.search(dump(self.full.get(i) or self.rows.get(i) or {}).lower())]
        if len(hits) == 1:
            self.trace.append({"kind": "link_id", "given": t, "id": hits[0]})
            return hits[0]
        return t

    def lacks_values(self, i, vt, src=None):
        blocks = [b for b in (attr_block(self.full.get(i)), attr_block(self.rows.get(i))) if b]
        if not blocks or not str(vt).strip():
            return []
        namew = set()
        for c in self.shop_names(i):
            namew |= set(_ANYRUN.findall(c.lower()))
        held = " ".join(dump(b) for b in blocks)
        tk = self.title_key()
        if tk:
            held += " " + str((self.rows.get(i) or {}).get(tk) or "")
        held = _SQUASH_DOT.sub("", held.lower())
        raw = _VTOK.findall(str(vt).lower())
        wanted = []
        for k, tkn in enumerate(raw):
            tkn = tkn.strip(".")
            if not tkn or not (len(tkn) >= 3 or tkn[0].isdigit()) or tkn in namew:
                continue
            if tkn.isalpha() and k > 0 and raw[k - 1][:1].isdigit():
                continue
            wanted.append(tkn)
        if src is not None:
            sl = src.lower()
            wanted = [w for w in wanted if (w[0].isdigit() or roots(w)) and token_in(w, sl)]
        out = []
        for w in wanted:
            if w not in held and w not in out:
                out.append(w)
        return out

    def sends_on(self, i, req, val):
        prop = req.split(":", 1)[0]
        phrase = " ".join(_ANYRUN.findall(prop.lower()))
        want = _SQUASH.sub("", val.lower())
        if len(phrase) < 3 or not want:
            return False
        tk = self.title_key()
        for rec in (self.rows.get(i), self.full.get(i)):
            if not isinstance(rec, dict):
                continue
            for k, v in rec.items():
                if not isinstance(v, str) or len(v) <= 40 or k == tk:
                    continue
                if token_in(phrase, " ".join(_ANYRUN.findall(v.lower()))) and want not in _SQUASH.sub("", v.lower()):
                    return True
        return False

    def trail(self, limit=None):
        pend = self.pending_refs()
        tool = self.roles.get("offer") or self.roles.get("open")
        tgt = self.single_target(tool) if tool else None
        seen = []
        lost = []
        while pend and self.spend < HARD and (limit is None or self.clock() <= limit):
            cap = self.chain_room if self.chain_room is not None else (6 if self.left() > 15 else 4)
            if self.chain_rounds >= cap:
                break
            self.chain_rounds += 1
            recs = []
            nopen = 0
            for i in reversed(self.order):
                r = self.full.get(i) or self.rows.get(i)
                if self.page_read(i) and r is not None and nopen < 45:
                    recs.append("OPENED " + rdump(r, 300, 1400))
                    nopen += 1
            for i in reversed(self.order):
                if len(recs) >= 60:
                    break
                r = self.full.get(i) or self.rows.get(i)
                if not self.page_read(i) or r is None:
                    if i in self.full:
                        recs.append("ROW " + dump(clip(self.full[i], 120))[:700])
                    elif i in self.rows:
                        recs.append("ROW " + dump(clip(self.rows[i], 80))[:300])
            p = (CHAIN_PROMPT + "\n\nREQUIREMENTS WHOSE VALUE SITS ON ANOTHER LISTING:\n" + "\n".join(t for _, t in pend) +
                 "\n\nTHE SHOPPER'S REQUEST (each requirement listed above is a brief restatement of this request; wherever the "
                 "request's wording itself states how the desired value stands against the value found along the chain, that "
                 "wording fixes the value, overriding the requirement's wording):\n" + self.request[:3000])
            if self.trail_notes:
                p += "\n\nWHAT CAIRN VERIFIED AGAINST THE RECORDS:\n" + "\n".join(self.trail_notes[-6:])
            p += "\n\nRECORDS (newest first):\n" + "\n".join(recs)
            ans = self.json_ask(p, [LIGHT], 4500)
            if ans is None and not (self.store_broke or self.no_credit or self.calls >= CALL_CAP) and self.spend + HEAVY_ROOM <= HARD:
                ans = self.json_ask(p, [HEAVY], 4500)
            ans = ans or {}
            reach = []
            lost = []
            gaps = []
            again = False
            chains = ans.get("chains")
            if isinstance(chains, dict):
                chains = [chains]
            if not isinstance(chains, list):
                chains = []
            for ch in chains:
                if not isinstance(ch, dict):
                    continue
                match = self.chain_match(str(ch.get("need") or "").strip(), pend)
                if match is None:
                    continue
                lk = ch.get("links")
                links = [x for x in (lk if isinstance(lk, list) else listify(lk)) if isinstance(x, dict)]
                lids = [self.map_link_id(str(x.get("id") or "").strip()) for x in links]
                for pidx, ln in enumerate(links):
                    lid = lids[pidx]
                    if pidx == 0:
                        src = match[1]
                    else:
                        prev = lids[pidx - 1]
                        src = dump(self.full.get(prev) or self.rows.get(prev) or {}) if prev else ""
                    vv = ln.get("values")
                    vt = vv if isinstance(vv, str) else ("" if vv is None else str(vv))
                    if not vt.strip():
                        ff = ln.get("find")
                        vt = ff if isinstance(ff, str) else ("" if ff is None else str(ff))
                    miss = []
                    if lid and (self.page_read(lid) or lid in self.full) and src:
                        miss = self.lacks_values(lid, vt, src)
                    if miss and not self.page_read(lid) and not any(w in self.key_words() for w in miss):
                        miss = []
                    if not miss:
                        continue
                    about = str(ln.get("about") or "")
                    note = lid + " is not the listing portrayed by \"" + about[:150] + "\": its attributes and its title both lack " + ", ".join(miss[:3])
                    if note in self.trail_notes:
                        continue
                    self.trail_notes.append(note)
                    self.trace.append({"kind": "link_rejected", "id": lid, "missing": miss[:3]})
                    shopt = (match[1] + " " + about).lower()
                    shop = next((c for c in self.shop_names(lid) if token_in(c.lower(), shopt)), "")
                    vvt = vv if isinstance(vv, str) else ("" if vv is None else str(vv))
                    sw = str(ln.get("find") or "").strip() or (shop + " " + vvt).strip()
                    nl = dict(ln)
                    nl["id"] = ""
                    nl["find"] = sw
                    links = links[:pidx] + [nl]
                    lids = lids[:pidx] + [""]
                    again = True
                    break
                val = str(ch.get("value") or "").strip()
                allread = bool(links) and all(x and self.page_read(x) for x in lids)
                if ch.get("done") is True and allread and val:
                    note = (lids[-1] + " mentions the property of \"" + match[1][:80] + "\" in its own prose but without the value " +
                            val[:40] + ": it therefore hands that property over to another listing, and the chain continues from "
                            "whatever its prose points to")
                    if self.sends_on(lids[-1], match[1], val) and note not in self.trail_notes:
                        self.trail_notes.append(note)
                        self.trace.append({"kind": "chain_onward", "id": lids[-1]})
                        again = True
                        continue
                    self.ref_values[match[1]] = val
                    self.version += 1
                    continue
                if allread and not str(links[-1].get("find") or "").strip():
                    self.ref_values[match[1]] = val or (PLACEHOLDER_LEAD + " " + lids[-1] + " shows")
                    self.version += 1
                    continue
                unread = [x for x in lids if x in self.rows and not self.page_read(x)]
                if unread:
                    for x in unread:
                        if x not in reach:
                            reach.append(x)
                    continue
                lkd = next((x for x, i in zip(links, lids) if i not in self.rows), None) or {}
                desc = str(lkd.get("about") or "").strip() or "the listing the requirement leads to"
                fw = str(lkd.get("find") or "").strip()
                lost.append(match[1] + " -> find " + desc + ((" (search: " + fw + ")") if fw else ""))
                gaps.append((desc, fw))
            pend = [pt for pt in pend if pt[1] not in self.ref_values]
            if not reach and gaps and tool and tgt and self.left() > 12:
                settled = []
                for gi, (desc, fw) in enumerate(gaps[:2]):
                    if self.link_searches >= CHAIN_SEARCHES:
                        break
                    ids, known = self.link_finder(desc, fw)
                    for x in ids:
                        if x not in reach:
                            reach.append(x)
                    if known:
                        seen.append(known + ": a page, already opened, of the shop the chain names, and its attributes contain every "
                                    "value stated by its description; take the value off that page.")
                        settled.append(gi)
                lost = [x for k, x in enumerate(lost) if k not in settled]
            if not reach or not tool or not tgt or self.finished:
                if again and pend and tool and tgt and not self.finished:
                    continue
                break
            if self.chain_room is not None:
                room = min(3, EARLY_OPENS - len(seen), self.left() - (3 * len(self.items) + self.reserve() + 1))
            else:
                room = min(3, 6 - len(seen)) if self.left() >= len(reach) + 4 else 0
            if room <= 0:
                break
            for x in reach[:room]:
                a, f = shape_args({tgt: x}, self.schemas.get(tool) or {})
                if f or self.rushed():
                    break
                r = self.env(tool, a)
                if r is None or self.finished:
                    break
                o = r.get("observation")
                self.observe(tool, o)
                seen.append(x + ": " + self.bshow(o, 1500))
        txt = ""
        if seen:
            txt += ("[Cairn opened the pages below while tracing the listings that requirements refer to; a page qualifies as one of "
                    "them only if it displays every value stated in that listing's description]\n" + "\n".join(seen) + "\n")
        if self.ref_values:
            txt += "[values taken from those pages] " + "; ".join(k + " -> " + str(v) for k, v in self.ref_values.items()) + "\n"
        hold = False
        if lost and self.chain_holds < (3 if self.left() > 15 else 2) and self.left() > 5:
            self.chain_holds += 1
            hold = True
            txt += ("The purchase is only valid once you have read completely every page that a requirement leads to (a result row "
                    "will not do), including each page that leads on to yet another listing. Not yet located or read: " +
                    " | ".join(lost[:3]) + ". Search using the shop's name plus the values in the description (another product of "
                    "that kind sold by the same shop is the wrong one), open whichever row from that shop has a page showing those "
                    "values, use the value printed on that page, and then order.")
        return txt.rstrip("\n"), hold

    def link_finder(self, desc, sw):
        bad = self.no_name_keys()
        shops = set(self.shop_rows(desc, self.order)) | set(self.opened_shops(desc))
        namew = set()
        for i in shops:
            for k, v in (self.rows.get(i) or {}).items():
                if k not in bad and isinstance(v, str) and len(v.strip()) <= 40 and not V24_PLACEHOLDER.fullmatch(v.strip().casefold()):
                    namew |= set(_ALNUM3.findall(v.lower()))
        src = sw or desc
        valw = [w for w in _ANYRUN.findall(src.lower()) if (len(w) >= 3 or w.isdigit()) and w not in namew and not _LINK_STOP1.fullmatch(w)]
        for i in self.opened_shops(desc):
            lv = " ".join(str(x) for x in (attr_block(self.full.get(i)) or {}).values()).lower()
            if valw and lv and all(token_in(w, lv) for w in valw):
                self.trace.append({"kind": "known_link", "id": i})
                return [], i
        kw = self.key_words()
        raw = _QSEP.sub(" ", sw).split()
        parts = [p for k, p in enumerate(raw) if k == 0 or p.lower() not in kw]
        votes = {}
        tpl = self.value_template()
        if tpl and parts:
            shop = parts[0]
            singles = [shop + " " + p for p in parts[1:] if len(p) >= 3 or _DIGIT.search(p)] if len(parts) >= 3 else []
            seq = []
            for q in [" ".join(parts)] + singles + [shop]:
                if q not in seq:
                    seq.append(q)
            for q in seq:
                if q == shop and votes:
                    break
                ids = self.link_query(tpl, q, desc, valw)
                if ids is None:
                    break
                fresh = self.shop_rows(desc, ids, valw)
                while not fresh and ids and self.link_pages.get(q.lower()) and all(self.names_shop(i, desc) for i in ids):
                    ids2 = self.link_query(tpl, q, desc, valw)
                    if not ids2 or len(ids2) == len(ids):
                        break
                    ids = ids2
                    fresh = self.shop_rows(desc, ids, valw)
                for f in fresh:
                    votes.setdefault(f, []).append(len(ids))
                if fresh and q not in singles:
                    break
        terms = {w for w in _ALNUM3.findall((desc + " " + sw).lower()) if w not in namew and not _LINK_STOP2.fullmatch(w)}

        def rank(ids, keep_all):
            sc = []
            for k, i in enumerate(ids):
                h = len(terms & set(_ALNUM3.findall(dump(self.rows.get(i) or {}).lower())))
                if h or keep_all or not terms:
                    sc.append((-h, k, i))
            sc.sort()
            return [i for _, _, i in sc]

        if votes:
            rk = rank(list(votes), True)
            pos = {i: k for k, i in enumerate(rk)}
            res = sorted(rk, key=lambda i: (-len(votes[i]), min(votes[i]), pos[i]))
        else:
            fb = rank(self.shop_rows(desc, list(reversed(self.order))), False)
            clear = [i for i in fb if not self.read_misses(i, valw)]
            res = clear + [i for i in fb if i not in clear]
        return res[:2], None

    def link_query(self, tpl, q, desc, valw):
        tool, fixed, field = tpl
        key = q.lower()
        mem = self.link_seen.get(key)
        nxt = self.link_pages.get(key) if mem is not None else None
        if mem is not None and (self.shop_rows(desc, mem, valw) or not nxt or not any(self.names_shop(i, desc) for i in mem)):
            return mem
        if self.link_searches >= CHAIN_SEARCHES or self.left() <= 12:
            return mem
        a = dict(fixed)
        a[field] = q
        if nxt:
            a[nxt[0]] = nxt[1]
        a, f = shape_args(a, self.schemas.get(tool) or {})
        if f:
            return mem
        self.link_searches += 1
        r = self.env(tool, a)
        if r is None:
            return mem
        o = r.get("observation")
        self.observe(tool, o)
        ids = [i for i, _ in self.records_of(o)]
        pl = self.paging(tool, o)
        self.link_pages[key] = (pl[2], pl[3]) if pl and pl[3] is not None else None
        new = list(mem or [])
        for i in ids:
            if i not in new:
                new.append(i)
        self.link_seen[key] = new
        self.trace.append({"kind": "link_query", "q": q[:80], "paged": bool(nxt), "shop_rows": self.shop_rows(desc, new, valw)[:4]})
        return new

    def chain_texts(self):
        pend = self.pending_refs()
        if not pend:
            return "", ""
        rt = " | ".join(t for _, t in pend)
        pw = []
        used = set()
        tk = self.title_key()
        for _ in range(5):
            known = rt + " " + " ".join(pw)
            new = [i for i in self.order if i not in used and self.page_read(i) and self.names_shop(i, known)]
            if not new:
                break
            for i in new:
                used.add(i)
                for k, v in (self.rows.get(i) or {}).items():
                    if isinstance(v, str) and len(v) > 40 and k != tk:
                        pw.append(v)
        return rt, " ".join(pw)

    def page_first(self, tool, args):
        op = self.roles.get("open")
        off = self.roles.get("offer")
        if tool != op or not off or off == op or off not in self.schemas:
            return tool, args, ""
        ot, ft = self.single_target(op), self.single_target(off)
        if not ot or not ft or not isinstance(args.get(ot), str):
            return tool, args, ""
        i = args[ot].strip()
        if i not in self.rows or self.page_read(i) or i in self.gone:
            return tool, args, ""
        lab = self.label_of(i)
        if not lab or self.owner(lab):
            return tool, args, ""
        rt, pw = self.chain_texts()
        if not rt or not self.names_shop(i, rt + " " + pw):
            return tool, args, ""
        a, f = shape_args({ft: i}, self.schemas.get(off) or {})
        if f:
            return tool, args, ""
        self.trace.append({"kind": "page_first", "id": i})
        note = ("\n[Cairn] displayed the page of " + i + " (" + off + ") in place of the attribute view: a requirement is still valued "
                "off a listing sold by this shop, and solely the page reveals where it refers onward or which value its value is paired "
                "with (an order is valid only once that page has been opened). Call " + op + " on that listing once more if its "
                "attributes are still needed.")
        return off, a, note

    def reread(self):
        tool = self.roles.get("offer") or self.roles.get("open")
        tgt = self.single_target(tool) if tool else None
        if not tool or not tgt:
            return ""
        cut = max(self.step - 2, self.refused_at)
        stale = [i for i in self.cart_ids() if i not in self.gone and self.offer_seen.get(i, -99) < cut]
        toread = stale
        if stale and self.left() < len(stale) + 5:
            unseen = [i for i in stale if not self.page_read(i)]
            toread = unseen if self.left() >= len(unseen) + self.reserve() else []
        if not toread:
            return ""
        lines = []
        for i in toread:
            a, f = shape_args({tgt: i}, self.schemas.get(tool) or {})
            if f or self.rushed():
                break
            before = dict(self.rows.get(i) or {})
            r = self.env(tool, a)
            if r is None or self.finished:
                break
            self.offer_seen[i] = self.step
            o = r.get("observation")
            self.observe(tool, o)
            after = self.rows.get(i) or {}
            ch = [k for k in before if k in after and after[k] != before[k] and not isinstance(after[k], (dict, list))]
            if ch:
                lines.append(i + " changed (" + ", ".join(str(k) for k in ch[:4]) + "): " + dump(clip(o, 300))[:900])
        if lines:
            self.version += 1
        return "\n".join(lines)

    def late_show(self):
        tool = self.roles.get("offer") or self.roles.get("open")
        if not tool or not self.single_target(tool) or self.rushed():
            return ""
        unseen = [i for i in self.cart_ids() if not self.page_read(i) and i not in self.gone]
        if len(unseen) != 1:
            return ""
        self.reread()
        if self.page_read(unseen[0]):
            self.trace.append({"kind": "late_show", "id": unseen[0]})
            return "displayed the page of " + unseen[0] + " first (one step): an order requires every line's page to have been displayed."
        return ""

    def sold_peers(self, lost):
        if self.pick() != "cheapest" or not self.cat_key():
            return []
        cart = set(self.cart_ids())
        out = []
        for line in lost:
            p = self.price(line)
            lab = self.label_of(line)
            if p is None or not lab:
                continue
            pool = [i for i in self.order if i not in lost and i not in cart and i not in self.full and self.buyable(i) and not self.sold_out(i)
                    and self.label_of(i) == lab and self.price(i) is not None and self.price(i) <= p + 1e-9]
            pool.sort(key=lambda i: self.price(i))
            for i in pool[:SOLD_PEERS]:
                if i not in out:
                    out.append(i)
        return out

    def swap_hint(self):
        lost = [i for i in self.cart_ids() if i not in self.gone and self.sold_out(i)]
        if not lost:
            return ""
        for i in lost:
            self.gone[i] = self.step
        self.leads = [x for x in self.leads if x not in lost]
        self.version += 1
        peers = self.sold_peers(lost)
        if peers:
            self.fill_facts(peers, self.reserve() + 5)
        reps = self.replacements(lost)
        floor = max((self.price(i) or 0) for i in lost)
        p0 = self.price(reps[0]) if reps else None
        t = ("[Cairn] " + ", ".join(lost) + " sold out from now on (the store shows they cannot be purchased any more); they are "
             "gone for good and must not be opened again. ")
        if reps and self.left() <= 6:
            t += ("Steps are scarce: within this very turn put " + reps[0] + " in the cart in the quantity asked and remove the line "
                  "that sold out (that is two calls), and then order. Other already-read listings that seem to match: " +
                  (", ".join(reps[1:]) or "none") + ".")
        elif reps and self.pick() == "cheapest" and (p0 is None or p0 > floor + 1e-9):
            t += ("Already-read listings that seem to match that item, lowest price first: " + ", ".join(reps) + ". The request "
                  "wants the lowest price, so unless you have already seen every matching listing, make one search capped below " +
                  reps[0] + "'s price" + ((" (" + gnum(p0) + ")") if p0 is not None else "") + " (through the search's price ceiling "
                  "argument, if the search has one) ahead of replacing the line that sold out with the lowest-priced matching listing.")
        elif reps:
            t += ("Already-read listings that seem to match that item: " + ", ".join(reps) + ". Within this turn remove the line that "
                  "sold out and put " + reps[0] + " in the cart in the quantity asked, and order after that.")
        else:
            t += "Remove that line and put in the best other matching listing, searching when none of those already read matches."
        return t


_FAULT_KIND = re.compile(r" sold out| over the ")
COMPLETION_OPEN = "[Cairn] The decline was not sent because Cairn acted in its place"


class G6A:
    def planned_basket(self, lead):
        ck = self.cat_key()

        def kind(i):
            if ck:
                v = (self.rows.get(i) or {}).get(ck)
                return ("" if v is None else str(v)).strip().lower()
            return i

        planned = {}
        pk = set()
        for key, ids in self.lead_items.items():
            m = _FIRST_DIGITS.search(str(key))
            n = int(m.group(0)) if m else (1 if len(self.items) == 1 else None)
            pick = next((i for i in ids if not self.sold_out(i)), None)
            if pick and n and 1 <= n <= len(self.items) and kind(pick) not in pk:
                planned[pick] = self.items[n - 1].quantity
                pk.add(kind(pick))
        if lead not in planned:
            return None
        keep = {}
        drops = []
        for i in self.cart_ids():
            if i in planned:
                continue
            if not self.sold_out(i) and kind(i) not in pk:
                keep[i] = self.cart_lines.get(i, 1)
            else:
                drops.append(i)
        if len(planned) + len({kind(i) for i in keep}) < len(self.items):
            return None
        wanted = dict(keep)
        wanted.update(planned)
        return wanted, drops

    def complete_cart(self):
        if self.completed or not self.confirmed or self.sold_out(self.confirmed) or not self.roles.get("cart") or not self.roles.get("buy"):
            return ""
        self.completed = True
        pb = self.planned_basket(self.confirmed)
        if not pb:
            return ""
        wanted, drops = pb
        calls = self.cart_calls(wanted, drops)
        if not calls or self.left() < len(calls) + 1:
            return ""
        ids = list(wanted)

        def vk():
            return "|".join(sorted(ids)) + "#" + str(self.version)

        self.fill_facts(ids, len(calls) + 3)
        self.show_links(ids, len(calls) + 3)
        self.cart_check(ids, HARD)
        if self.verdicts.get(vk()) is not True:
            return ""
        sent, ok = self.run_cart_calls(calls)
        if not ok:
            return ""
        buy = self.roles["buy"]
        oa, f = shape_args(dict(self.brief.get("buy_args") or {}), self.schemas.get(buy) or {})
        if f:
            return ""
        self.reread()
        kept = []
        gate_txt = ""
        for att in range(2):
            if att == 1:
                self.reread()
                self.cart_check(ids, HARD)
                if self.verdicts.get(vk()) is not True or self.left() < 1 or self.finished or any(self.sold_out(i) for i in ids):
                    break
            go, gt = self.gate("order")
            if gt:
                gate_txt = gt
            if not go:
                break
            r = self.env(buy, oa)
            if r is None:
                break
            self.checkouts += 1
            if not self.finished:
                self.refused_at = self.step
            o = r.get("observation")
            self.observe(buy, o)
            kept.append(self.show(o))
            if self.finished:
                break
        if not kept and not gate_txt:
            return ""
        t = (COMPLETION_OPEN + ": an independent check passed " + self.confirmed + ", so Cairn changed the cart (" + "; ".join(sent) +
             ") and placed the order.")
        if gate_txt:
            t += "\n" + gate_txt
        if kept:
            t += "\n" + " [then] ".join(kept)
        return t

    def direct_checkout(self, label, detail=None):
        buy = self.roles.get("buy")
        if not buy or self.finished or self.left() <= 0:
            return []
        if any(_FAULT_KIND.search(t) for _, t in self.line_faults()):
            return []
        if self.left() >= 2:
            self.reread()
            if self.finished or self.left() <= 0:
                return []
        oa, f = shape_args(dict(self.brief.get("buy_args") or {}), self.schemas.get(buy) or {})
        if f:
            return []
        kept = []
        for att in range(2):
            if att == 1 and (self.left() <= 0 or self.finished or any(self.sold_out(i) for i in self.cart_ids())):
                break
            if self.left() >= 2:
                go, gt = self.gate("order")
                if gt:
                    kept.append(gt)
                if not go:
                    break
            if self.finished or self.left() <= 0:
                break
            r = self.env(buy, oa)
            self.trace.append({"kind": label, "detail": detail, "answered": r is not None})
            if r is None:
                break
            self.checkouts += 1
            if not self.finished:
                self.refused_at = self.step
            o = r.get("observation")
            self.observe(buy, o)
            kept.append(self.show(o))
            if self.finished:
                break
        return kept

    def late_finish(self):
        if self.finished or not self.roles.get("buy") or not self.roles.get("cart"):
            return ""
        nit = len(self.items)
        usable = [i for i in self.built if not self.sold_out(i)]
        returned = []
        if len(usable) >= nit:
            cart = set(self.cart_ids())
            miss = [i for i in usable if i not in cart or (not self.fresh() and i in self.dropped_ids)]
            ck = self.cat_key()
            lines = {}
            for i in miss:
                own = [n for n in range(1, nit + 1) if ck and self.owns(n, self.label_of(i))]
                lines[i] = self.items[own[0] - 1].quantity if len(own) == 1 else 1
            calls = self.cart_calls(lines, []) if lines else []
            if calls is None or len(calls) + 1 > self.left():
                return ""
            _, ok = self.run_cart_calls(calls)
            if not ok:
                return ""
            returned = list(lines)
        elif nit >= 2 and self.cart_ids():
            if not self.fill_short() or len([i for i in self.cart_ids() if self.held(i) > 0]) < nit:
                return ""
        else:
            return ""
        kept = self.direct_checkout("late_finish", returned)
        if not kept:
            return ""
        t = (COMPLETION_OPEN + ": this near the end of the step budget, a decline earns zero when every requested item is already "
             "covered by a cart line")
        if returned:
            t += "; Cairn first put " + ", ".join(returned) + " back into the cart"
        return t + ", and Cairn ordered.\n" + " [then] ".join(kept)

    def closest_order(self):
        if self.clock() < CLOSEST_CLOCK or not self.closest_cart():
            return ""
        kept = self.direct_checkout("closest_order", dict(self.cart_lines))
        if not kept:
            return ""
        return (COMPLETION_OPEN + ": at this point of the clock a decline earns zero, and a shortage of time is no proof that the shop "
                "lacks a fitting product; Cairn rebuilt the cart as the nearest basket among the listings it had read (" + self.cart_text() +
                ") and ordered.\n" + " [then] ".join(kept))

    def short_cart(self):
        return len([i for i in self.cart_ids() if self.held(i) > 0]) < len(self.items) or bool(self.missing_items())

    def reopen(self):
        s = self.roles.get("search")
        if self.tools_reopened or self.checkouts or not s or self.left() <= self.reserve() + 3 or not self.short_cart():
            return ""
        if s in {t["function"]["name"] for t in self.offered()}:
            return ""
        self.tools_reopened = True
        self.trace.append({"kind": "reopened", "left": self.left()})
        return ("Search and the views for reading listings are available again, because some requested item lacks a cart line: locate "
                "and open a listing that suits that item, put it in the cart, and order, all inside the remaining steps.")

    def late_review(self):
        self.decline_blocks = 2
        if not self.leads and not self.audited and self.clock() <= WIND_DOWN and self.judges():
            self.audited = True
            fits = self.audit_fits(self.audit_call())
            if fits:
                self.lead_items = fits
                self.leads = [i for k in fits for i in fits[k]]
        first = next((i for i in self.leads if not self.sold_out(i)), None)
        pb = self.planned_basket(first) if first else None
        if not pb or self.clock() > WIND_DOWN:
            return ""
        wanted, drops = pb
        calls = self.cart_calls(wanted, drops)
        if not calls or len(calls) + 1 > self.left():
            return ""
        ids = sorted(wanted)
        self.cart_check(ids, HARD)
        if self.verdicts.get("|".join(ids) + "#" + str(self.version)) is not True:
            return ""
        self.confirmed = first
        self.trace.append({"kind": "late_review", "lead": first})
        return self.complete_cart()

    def offered(self):
        r = self.roles
        ends = [x for x in (r.get("buy"), r.get("refuse")) if x]
        lft = self.left()
        res = self.reserve()
        allow = None
        if ends:
            if lft <= res:
                allow = set(ends)
            elif lft <= res + 3:
                allow = set(ends) | {r.get("cart"), r.get("cart_view")}
                ft = self.facts_tool()
                if ft and lft >= 3 and self.missing_items():
                    allow.add(ft)
            elif lft <= len(self.items) + 5 and not self.checkouts and not (self.tools_reopened and self.short_cart()):
                allow = set(ends) | {r.get("cart"), r.get("cart_view"), r.get("offer")}
        ask = r.get("ask")
        hide = bool(ask) and self.msg_args("x" * 200) is not None
        base = [t for t in self.tools if not (hide and t["function"]["name"] == ask)]
        if allow is None:
            return base
        out = [t for t in base if t["function"]["name"] in allow]
        return out or base

    def zero_add(self, args):
        tool = self.roles.get("cart")
        props = (self.schemas.get(tool) or {}).get("properties") or {} if tool else {}
        cnts = [k for k, v in args.items() if isinstance(props.get(k), dict) and "integer" in kinds(props[k]) and not isinstance(v, (str, bool)) and count_of(v) is not None]
        if self.units_known or len(cnts) != 1:
            return args, ""
        k = cnts[0]
        c = count_of(args[k])
        if c > 0:
            self.units_known = True
            return args, ""
        if c != 0:
            return args, ""
        ids = [v for v in args.values() if isinstance(v, str) and v in self.rows]
        if len(ids) != 1:
            return args, ""
        if any(isinstance(props.get(kk), dict) and isinstance(props[kk].get("enum"), list) and v in props[kk]["enum"][1:] for kk, v in args.items()):
            return args, ""
        if any(isinstance(v, (list, dict)) for v in args.values()):
            return args, ""
        i = ids[0]
        if i in self.ever_carted or i in self.cart_lines or i in self.cart_ids() or (self.cart_view is not None and i in dump(self.cart_view)) or i in self.cart_said:
            return args, ""
        own = [n for n in range(1, len(self.items) + 1) if self.cat_key() and self.owns(n, self.label_of(i))]
        qs = {self.items[own[0] - 1].quantity} if len(own) == 1 else {it.quantity for it in self.items}
        if len(qs) != 1:
            return args, ""
        u = max(1, list(qs)[0])
        mx = props[k].get("maximum")
        if is_num(mx):
            u = min(u, mx)
        mn = props[k].get("minimum")
        if (is_num(mn) and mn > u) or u < 1:
            return args, ""
        u = int(u) if u == int(u) else u
        self.units_known = True
        self.trace.append({"kind": "zero_add", "id": i, "units": u})
        a = dict(args)
        a[k] = u
        return a, ("[Cairn] " + str(k) + " is a number of units, not an index into the rows or the cart lines; a zero count puts nothing in "
                   "the cart, so Cairn sent it with the requested quantity, " + str(k) + "=" + str(u) + ".")



class G6B:
    def dispatch(self, calls):
        joined = self.join_opens(calls)
        n_calls = len(joined)
        replies = []
        r = self.roles
        for cc, isj in joined:
            allowed = sorted({t["function"]["name"] for t in self.offered()})
            if isj:
                replies.append("[Cairn] This listing is in the comparison result given earlier in this turn, because Cairn read them jointly in a single step.")
                continue
            if self.finished:
                replies.append("[Cairn] This call was not executed, because the episode has ended.")
                continue
            tool = cc["function"]["name"]
            raw = cc["function"]["arguments"]
            if tool and tool == r.get("ask") and self.msg_args("x" * 200) is not None:
                replies.append(SKIP_OPEN + " Cairn's interviewer sends all shopper messages.")
                continue
            if tool not in self.schemas:
                replies.append(SKIP_OPEN + " unknown tool; the tools are: " + ", ".join(allowed))
                continue
            if tool not in allowed:
                replies.append(SKIP_OPEN + " Too few steps remain for this tool; use one of these instead: " + ", ".join(allowed))
                continue
            if isinstance(raw, dict):
                args = raw
            elif isinstance(raw, str) and raw.strip():
                args = obj_of(raw)
                if args is None:
                    replies.append(SKIP_OPEN + " The argument text did not form exactly one JSON object.")
                    continue
            else:
                args = {}
            args, faults = shape_args(args, self.schemas.get(tool) or {})
            if faults:
                replies.append(SKIP_OPEN + " " + "; ".join(faults[:6]))
                continue
            args, prob = self.map_titles(tool, args)
            if prob:
                replies.append(SKIP_OPEN + " " + prob + ".")
                continue
            tail = []
            if tool == r.get("cart"):
                args = self.whole_removal(args)
                args, zn = self.zero_add(args)
                if zn:
                    tail.append(zn)
            ct = self.cmp_target()
            if tool == r.get("compare") and ct and isinstance(args.get(ct), list) and self.cmp_bad and len(args[ct]) > self.cmp_room():
                room = self.cmp_room()
                rest = args[ct][room:]
                args = dict(args)
                args[ct] = args[ct][:room]
                tail.append("[Cairn] Only the first %d went out, as this store's comparison takes no more than %d; not yet sent: %s" % (
                    room, room, ", ".join(str(x) for x in rest)))
            st = self.single_target(tool)
            if st and tool in (r.get("open"), r.get("offer")) and isinstance(args.get(st), str) and args[st].strip() in self.gone:
                g = args[st].strip()
                replies.append(SKIP_OPEN + " This listing's sell-out was recorded at step %d and it will not return. Put a different "
                               "listing that fits in place of its cart line." % self.gone[g])
                continue
            if tool == r.get("cart") and any(not isinstance(v, str) and count_of(v) is not None and count_of(v) < 0 for v in args.values()):
                view = dump(self.cart_view) if self.fresh() else ""
                bad = next((v for v in args.values() if isinstance(v, str) and v in self.rows and v not in self.cart_lines
                            and v not in view and v not in self.cart_said), None)
                if bad:
                    replies.append(SKIP_OPEN + " " + bad + " is not held, so no units can come off it." + self.cart_footer())
                    continue
            is_ord = self.is_order(tool, args)
            is_dec = self.is_decline(tool, args)
            fin = is_ord or is_dec
            room_at = self.left()
            if fin and n_calls > 1:
                replies.append(SKIP_OPEN + " A finishing call must go alone, once the results of the other calls have been read.")
                continue
            if not fin and self.left() <= self.reserve() and (r.get("buy") or r.get("refuse")):
                replies.append(SKIP_OPEN + " The last few steps are reserved for the order" +
                               (" (with the shopper approving the basket first)" if self.reserve() == 2 else "") + " or for a decline.")
                continue
            plain_roles = {v for k, v in r.items() if k != "search"}
            search_like = tool not in plain_roles
            fresh = False
            if search_like:
                fresh = self.new_query(tool, args)
                if fresh:
                    a2 = self.first_look(tool, args, True)
                    if a2 != args:
                        tail.append("[Cairn] This being a new search, Cairn sent it for page one (you had sent %s)." % dump(args))
                        args = a2
            args = self.row_ids(tool, args)
            tool, args, redirect = self.page_first(tool, args)
            st = self.single_target(tool)
            if tool == r.get("search") and self.codes_dead and self.names_code(args):
                replies.append(SKIP_OPEN + " Code searches in this store returned nothing. Search with words and attribute values "
                               "instead, browse the category listing, and take the codes from the rows shown.")
                continue
            mark = tool + dump(args)
            if not fin and tool != r.get("cart") and mark in self.recent:
                replies.append(SKIP_OPEN + " This exact call was just made, with no change since; the earlier result stands.")
                continue
            if tool == r.get("search"):
                crt = self.cap_repeat(tool, args)
                if crt:
                    replies.append(crt)
                    continue
            reader = tool in (r.get("search"), r.get("open"), r.get("offer"), r.get("compare"))
            if reader and mark in self.read_cache and self.read_cache[mark][0] == self.version:
                _v, s, ctxt = self.read_cache[mark]
                replies.append(SKIP_OPEN + " The identical call at step %d gave the result below, with no change since then.\n%s" % (s, ctxt[:3000]))
                continue
            if reader and tool != r.get("compare") and st and isinstance(args.get(st), str):
                tv = args[st].strip()
                if (tv in self.rows and self.shown_already(tool, tv)) or (tool, tv) in self.factless:
                    replies.append(SKIP_OPEN + " This view has nothing new to show for that listing. Its record: " + self.rec_text(tv))
                    continue
            if tool == r.get("compare") and ct and isinstance(args.get(ct), list) and args[ct]:
                lst = args[ct]
                drop = [x for x in lst if isinstance(x, str) and self.shown_already(tool, x)]
                if drop and len(drop) == len(lst):
                    replies.append((SKIP_OPEN + " This view has nothing new to show for these listings.\n" +
                                    "\n".join(str(x) + ": " + self.rec_text(x) for x in lst))[:4000])
                    continue
                if drop:
                    tail.append("[Cairn] Left out as already shown in full with no change since: " + ", ".join(drop))
                    args = dict(args)
                    args[ct] = [x for x in lst if x not in drop]
                    mark = tool + dump(args)
            ttxt = ""
            if is_ord and self.left() > 2:
                if not self.cheaper_holds and self.left() <= self.reserve() + 3:
                    cp = self.cheaper_proven()
                    if cp and self.left() >= self.reserve() + 1 + 2 * len(cp):
                        self.cheaper_holds += 1
                        self.trace.append({"kind": "cheaper_hold", "late": True, "pairs": [(a, c) for a, _, c, _ in cp]})
                        replies.append(HOLD_OPEN + " " + self.cheaper_text(cp) + self.cart_footer())
                        continue
                hunt_txt = self.cheaper_hunt()
                w = self.wider_hold()
                if w:
                    replies.append(w + self.cart_footer())
                    continue
                changed = self.reread()
                if self.note_sold:
                    self.sold_search()
                if self.cart_touched and not self.fresh() and r.get("cart_view") and self.left() > 5 and not self.rushed():
                    cv = r["cart_view"]
                    a, f = shape_args({}, self.schemas.get(cv) or {})
                    if not f:
                        res = self.env(cv, a)
                        if res is not None:
                            o = res.get("observation")
                            self.cart_view = o
                            self.cart_seen_at = self.step
                            m = self.observe(cv, o)
                            if m:
                                self.queued = []
                                replies.append(HOLD_OPEN + " Viewing the cart revealed a change: " + m + self.cart_footer() +
                                               "\nApply it, repair the cart where necessary, then order.")
                                continue
                sh = self.swap_hint()
                gl = [i for i in self.cart_ids() if i in self.gone] if self.sold_holds < 2 else []
                if sh or gl:
                    if not sh:
                        self.sold_holds += 1
                    replies.append(HOLD_OPEN + " " + (sh or ("The carted lines " + ", ".join(gl) + " are sold out; replace that carted line first.")) + self.cart_footer())
                    continue
                ttxt, thold = self.trail()
                if thold:
                    replies.append(HOLD_OPEN + " " + ttxt + self.cart_footer())
                    continue
                if self.fit_holds < 2 and self.left() > self.reserve() + 3:
                    ff = self.fit_faults()
                    if ff:
                        self.fit_holds += 1
                        self.trace.append({"kind": "fit_hold", "faults": ff[:4]})
                        sets = self.read_sets()
                        t1 = ""
                        if sets:
                            t1 = (" Among the listings already opened there is one complete set, compatible through its codes, which spells "
                                  "out each of the requirements: " + self.set_text(sets) + ".")
                        replies.append(HOLD_OPEN + " A carted part is incompatible with the carted device: " + "; ".join(ff[:3]) +
                                       ". Replace the part, or else the device, and then order." + t1 + self.cart_footer())
                        continue
                if self.line_holds < 2 and self.left() > self.reserve() + 2:
                    lf = self.line_faults()
                    if lf and all(k == "units" for k, _ in lf):
                        fixes = self.count_fixes()
                        if fixes:
                            lf = self.line_faults()
                            if not lf:
                                self.line_holds += 1
                                replies.append(HOLD_OPEN + " Cairn adjusted the unit counts itself: " + "; ".join(fixes) +
                                               ". If the store rejected any of those fixes, correct those lines; then order." + self.cart_footer())
                                continue
                    if lf:
                        self.line_holds += 1
                        self.trace.append({"kind": "line_hold", "faults": [t for _, t in lf[:6]]})
                        replies.append(HOLD_OPEN + " The cart and the request do not match yet: " + "; ".join(t for _, t in lf[:6]) +
                                       ". Correct those lines with the means the cart tool offers for adding and removing units, and then order." + self.cart_footer())
                        continue
                ids = self.cart_ids()
                facts = self.fill_facts(ids, self.reserve() + (1 if len(ids) >= 2 else 3))
                self.show_links(ids, self.reserve() + 1)
                facts += self.cheaper_rows()
                block = ("[Cairn fetched the attribute records of the listings below at one step apiece]:\n" + "\n".join(facts) + "\n") if facts else ""
                if not self.cheaper_holds and self.left() > self.reserve() + 3:
                    cp = self.cheaper_proven()
                    if cp:
                        self.cheaper_holds += 1
                        self.trace.append({"kind": "cheaper_hold", "late": False, "pairs": [(a, c) for a, _, c, _ in cp]})
                        replies.append(HOLD_OPEN + (("\n" + block) if block else " ") + self.cheaper_text(cp) + self.cart_footer())
                        continue
                if not self.weak_holds and self.left() > self.reserve() + 3:
                    wt = self.weak_text(self.weak_lines())
                    if wt:
                        self.weak_holds += 1
                        replies.append(HOLD_OPEN + (("\n" + block) if block else " ") + wt + self.cart_footer())
                        continue
                ag = self.agreed_swap()
                if ag:
                    replies.append("[Cairn] This order has not run yet (what waits is the order; the cart calls reported next did consume "
                                   "steps). " + ag + self.cart_footer())
                    continue
                verdict = self.cart_check()
                if verdict:
                    t = BARE_HOLD
                    if ttxt:
                        t += " " + ttxt
                    if hunt_txt:
                        t += "\n" + hunt_txt + " " + self.below_cart() + "\n"
                    if facts:
                        t += "\n[Cairn fetched the attribute records of the listings below for this review, at one step apiece]\n" + "\n".join(facts)
                    replies.append(t + "\n" + verdict + self.cart_footer())
                    continue
                if changed and self.spend > SOFT:
                    replies.append(HOLD_OPEN + " Cairn has just fetched the cart's listings again: " + changed +
                                   "\nOrder again once all lines are still in stock and priced within budget; otherwise swap that line before ordering.")
                    continue
            if is_dec and self.left() > 5 and not self.set_holds:
                if self.fit_pairs:
                    sets = self.read_sets(True)
                    if sets:
                        self.set_holds += 1
                        self.trace.append({"kind": "set_hold", "sets": [s["ids"] for s in sets[:2]]})
                        replies.append(HOLD_OPEN + " A complete fitting set exists in this store: its listings were all opened before and, "
                                       "between their attribute blocks and titles, spell out each of the requirements, and each line bound "
                                       "to the device matches the device through its code: " + self.set_text(sets) + ". Make the basket one "
                                       "of these sets and order; decline solely when some listing's record plainly violates a requirement.")
                        continue
                else:
                    pl = self.proven_lines()
                    if pl:
                        self.set_holds += 1
                        self.trace.append({"kind": "proven_hold", "lines": pl})
                        ents = []
                        for n in sorted(pl):
                            i = pl[n]
                            pr = self.price(i)
                            ents.append("item %d (%s): %s" % (n, self.items[n - 1].name, i) + ((" (" + gnum(pr) + ")") if pr is not None else ""))
                        replies.append(HOLD_OPEN + " Opened, buyable listings satisfy all requirements in the way their pages put it (every "
                                       "wanted value sits under a key bearing its property's name, and every figure is taken literally from "
                                       "the page, even if it seems a typing slip): " + "; ".join(ents) + ". Put these listings into the "
                                       "basket in the quantities requested and order; decline solely when some record plainly violates a "
                                       "requirement, and in that case name the violated one in your own reply text (not a shopper message) "
                                       "and send the decline once more.")
                        continue
            if is_dec and self.left() > 5:
                dt = self.decline_trail()
                if dt:
                    replies.append(HOLD_OPEN + " " + dt)
                    continue
                self.fit_hunt()
                at = self.audit()
                if at:
                    replies.append(HOLD_OPEN + " " + at)
                    continue
                if self.leads and self.left() > 4 and self.decline_blocks == 0:
                    self.decline_blocks = 1
                    self.trace.append({"kind": "lead_hold", "leads": self.leads})
                    replies.append(HOLD_OPEN + " The review named listings that seem to fit: " + ", ".join(self.leads) + ". Open them "
                                   "where necessary, cart whichever fits best while obeying the pick rule, then order. Decline only if all of "
                                   "them plainly fail some requirement, and in that case state in your own reply text (not a shopper "
                                   "message) which one fails and send the decline once more.")
                    continue
                if self.leads and self.left() > 4 and self.decline_blocks == 1:
                    self.decline_blocks = 2
                    first = self.leads[0]
                    basket = None
                    if len(self.items) > 1:
                        pb = self.planned_basket(first)
                        basket = sorted(pb[0]) if pb else None
                    judged = basket if basket else [first]
                    self.cart_check(judged, HARD)
                    if self.verdicts.get("|".join(sorted(judged)) + "#" + str(self.version)) is True and first in self.leads:
                        self.confirmed = first
                        self.trace.append({"kind": "confirmed", "id": first, "judged": judged})
                        if basket:
                            replies.append(HOLD_OPEN + " A second, separate check run on the basket " + ", ".join(basket) + " finds that it "
                                           "satisfies all requirements, with exactly one line per requested item. Make the basket hold precisely "
                                           "these lines in the quantities requested and order; decline solely when some record plainly violates a requirement.")
                        else:
                            replies.append(HOLD_OPEN + " A second, separate check of " + first + "'s records finds that it satisfies all "
                                           "requirements. Cart it in the quantity asked and order; decline only when its record plainly breaks a requirement.")
                        continue
            if is_dec and 2 <= self.left() <= 5 and not self.confirmed and self.decline_blocks < 2 and len([i for i in self.built if not self.sold_out(i)]) < len(self.items):
                lr = self.late_review()
                if lr:
                    replies.append(lr + (" [episode finished]" if self.finished else ""))
                    continue
            try55 = False
            if is_dec and self.left() <= 5 and not self.late_held:
                self.late_held = True
                lf = self.late_finish()
                if lf:
                    replies.append(lf + (" [episode finished]" if self.finished else ""))
                    continue
                try55 = not self.finished
            if try55:
                built = [i for i in self.built if not self.sold_out(i)]
                cart = set(self.cart_ids())
                missing = [i for i in built if i not in cart or (not self.fresh() and i in self.dropped_ids)]
                if len(built) >= len(self.items) and len(missing) + 1 <= self.left():
                    self.trace.append({"kind": "late_decline_hold", "missing": missing})
                    t = (HOLD_OPEN + " A decline scores zero whenever a fitting listing exists, and running low on steps is no evidence "
                         "about whether one exists. ")
                    if missing:
                        t += "Cart these lines again in the quantities asked: " + ", ".join(missing) + ", and order. "
                    else:
                        t += "Order the cart unchanged. "
                    t += ("Decline only if the searching proved that, for one of the requested items, no listing satisfies its "
                          "requirements, and in that case send the decline once more.")
                    replies.append(t)
                    continue
            if is_dec and not self.leads and not self.pushed and room_at > self.budget_steps // 3 and self.left() > self.reserve() + len(self.items) + 2:
                self.pushed = True
                replies.append(HOLD_OPEN + (" %d steps remain. Try untried kinds of search before giving up: list every requested "
                                            "item's category and page onward through that listing using the page token, or offset value, "
                                            "returned by the store; try one-word queries of values and alternative names of the property; "
                                            "open any listing that could fit. Decline only after all that." % self.left()))
                continue
            if is_dec:
                ctx = self.complete_cart()
                if ctx:
                    replies.append(ctx + (" [episode finished]" if self.finished else ""))
                    continue
                ctx = self.closest_order()
                if ctx:
                    replies.append(ctx + (" [episode finished]" if self.finished else ""))
                    continue
                args = self.quiet_fill(args)
            if is_ord:
                lq = self.late_question()
                if lq:
                    replies.append(BARE_HOLD + " " + lq + self.cart_footer())
                    continue
            if is_ord and self.left() == 2 and self.checkouts >= 1:
                ls = self.late_show()
                if ls:
                    tail.insert(0, "[Cairn] " + ls)
            if fin and self.left() >= 2:
                go, gt = self.gate("order" if is_ord else "end")
                if not go:
                    replies.append(BARE_HOLD + " " + gt + self.cart_footer())
                    continue
                if gt:
                    tail.insert(0, "[Cairn] " + gt)
            res = self.env(tool, args)
            if res is None:
                replies.append("[Cairn] The call broke down through a network or server problem; you may retry it.")
                continue
            obs = res.get("observation")
            if tool == r.get("compare") and ct and isinstance(args.get(ct), list) and len(args[ct]) > 1:
                d = dump(obs)
                if not any(isinstance(x, str) and x in d for x in args[ct]):
                    self.cmp_bad = min(self.cmp_bad or 999, len(args[ct]))
                    tail.append("[Cairn] The comparison came back empty for %d listings. Send no more than %d per call." % (len(args[ct]), self.cmp_room()))
                else:
                    self.cmp_good = max(self.cmp_good, len(args[ct]))
            self.recent = (self.recent + [mark])[-3:]
            for k, v in args.items():
                vals = v if isinstance(v, list) and v else [v]
                if all(isinstance(x, str) and x in self.rows for x in vals):
                    self.id_args[(tool, k)] = True
            self.absorb(obs)
            if tool == r.get("compare"):
                recs = self.records_of(obs)
                if recs:
                    self.facts[tool] = self.facts.get(tool) is True or any(attr_block(x) for _, x in recs)
            if reader and tool != r.get("search"):
                self.note_view(tool, obs)
            notes = ""
            if search_like and not fin:
                notes += self.auto_page(tool, args, obs)
                if fresh:
                    notes += self.late_page(tool, args, obs)
                notes += self.shorter(tool, args, obs)
                notes += self.big_opens(tool, args, obs)
                notes += self.end_reads(tool, args, obs)
            if reader and not fin:
                notes += self.series_sweep()
            if st and tool not in (r.get("cart"), r.get("buy"), r.get("refuse"), r.get("ask")) and isinstance(obs, dict):
                lid = self.listing_id(obs, False, 0)
                if lid:
                    self.fact_note(tool, bool(attr_block(obs)))
                    if tool == self.roles.get("open") and self.facts.get(tool) is False:
                        for t in self.names:
                            if t == tool or not self.single_target(t) or self.facts.get(t) is False:
                                continue
                            if t in (r.get("cart"), r.get("buy"), r.get("refuse"), r.get("ask"), r.get("search")) or self.lists_things(t):
                                continue
                            self.roles["open"] = t
                            break
                    if self.facts.get(tool) is False and tool != self.roles.get("open") and not self.roles.get("offer"):
                        self.roles["offer"] = tool
                    if tool == self.roles.get("offer") or (tool == self.roles.get("open") and not self.roles.get("offer")):
                        self.offer_seen[lid] = self.step
            if tool == r.get("cart"):
                self.note_cart(tool, args)
                self.cart_said = dump(obs)
                self.recent = []
                cnts = [count_of(v) for v in args.values() if not isinstance(v, (str, bool)) and count_of(v) is not None]
                if cnts:
                    for v in args.values():
                        if isinstance(v, str) and v in self.rows:
                            if cnts[0] <= 0 and not row_present(v, obs):
                                self.dropped_ids.add(v)
                            elif cnts[0] > 0:
                                self.dropped_ids.discard(v)
                cur = [i for i in self.cart_ids() if not self.sold_out(i) and i not in self.dropped_ids]
                if len(cur) >= len(self.built):
                    self.built = cur
                if cnts and cnts[0] > 0:
                    dl = self.dear_page([v for v in args.values() if isinstance(v, str) and v in self.rows])
                    if dl:
                        tail.append(dl.lstrip("\n"))
                if self.pick() == "cheapest" and len(self.items) == 1 and not fin and not self.finished:
                    fl = self.list_below(self.cart_ids())
                    if fl:
                        tail.append(fl)
            if tool == r.get("search") and self.names_code(args):
                self.code_tries.append(bool(self.records_of(obs)))
                if len(self.code_tries) >= 2 and not any(self.code_tries):
                    self.codes_dead = True
            if tool == r.get("search") and self.records_of(obs):
                self.searched = (self.searched + [dict(args)])[-8:]
            if tool == r.get("cart_view"):
                self.cart_view = obs
                self.cart_seen_at = self.step
            if is_ord:
                self.checkouts += 1
                if not self.finished:
                    self.refused_at = self.step
            txt = self.show(obs) + notes + (("\n" + "\n".join(tail)) if tail else "")
            if search_like and not fin:
                txt += self.cheapest_here(obs) + self.cap_ignored(tool, args, obs)
            cacheable = txt
            ev = self.evidence(obs)
            if ev:
                txt += "\n" + ev
            if tool == r.get("cart"):
                c0 = [count_of(v) for v in args.values() if not isinstance(v, (str, bool)) and count_of(v) is not None]
                if c0 and c0[0] == 0 and any(isinstance(v, str) and v in self.rows and row_present(v, obs) for v in args.values()):
                    txt += ("\n[Cairn] A zero count did not remove the line, since this tool adds the number given to the line; "
                            "removing units takes a negative number.")
            self.note_sold = False
            lines = self.loose(obs)
            loose_sold = False
            named = False
            if lines:
                m = self.read_note(lines)
                loose_sold = self.note_sold
                named = self.note_named
                if m:
                    txt += "\n[note read] " + m + " Carry this change into the picks before ordering."
                    self.terms_seen += 1
            refused = is_ord and not self.finished
            again = refused and any(ln in self.spoken(obs) for ln in self.sold_lines)
            loosen = loose_sold and (refused or (not named and not is_ord))
            if (loosen or again) and self.cart_ids() and not self.finished:
                ss = self.sold_search()
                if ss:
                    txt += "\n[Cairn fetched the cart lines again following the rejection]\n" + ss
            if lines and (refused or loose_sold) and self.pick() == "cheapest" and len(self.items) == 1 and not self.finished:
                fl = self.list_below(self.cart_ids())
                if fl:
                    txt += "\n" + fl
            self.note_sold = False
            sh = self.swap_hint()
            if sh:
                txt += "\n" + sh
            if tool == r.get("cart") and self.fit_pairs and not self.finished:
                ff = self.fit_faults()
                if ff:
                    txt += "\n[Cairn] These lines are not yet compatible with each other: " + "; ".join(ff)
            if self.queued:
                txt += "\n[seen during Cairn's own calls] " + " | ".join(self.queued)
                self.queued = []
            txt += redirect
            if reader:
                self.read_cache[mark] = (self.version, self.step, cacheable)
            if self.finished:
                txt += " [episode finished]"
            replies.append(txt)
        return replies


    def finish(self, again=False):
        if self.finished or self.store_broke or self.left() <= 0:
            return ""
        fresh = self.fresh()
        holding = bool(self.cart_ids())
        whole = True
        nit = len(self.items)
        if holding and nit >= 2:
            ok = self.fill_short()
            whole = ok or not self.can_decline()
            if not whole and self.clock() >= CLOSEST_CLOCK and self.closest_cart():
                whole = True
            ids = self.cart_ids()
            if whole and len(ids) >= 2:
                self.fill_facts(ids, self.reserve())
                if self.left() >= 3 and self.room() > 5:
                    self.show_links(ids, self.reserve())
            if not whole:
                self.trace.append({"kind": "short_cart_decline"})
        if self.finished or self.left() <= 0:
            return ""
        buy = self.roles.get("buy")
        if not holding and buy and self.proven_basket():
            holding = True
        if not holding and buy and self.ever_carted and self.clock() >= CLOSEST_CLOCK and self.closest_cart():
            holding = True
        if buy and self.fit_pairs and not self.finished and self.left() >= 2:
            sets = self.read_sets(True)
            ids = self.cart_ids()
            mixed = (not holding) or bool(self.fit_faults()) or len(ids) < nit
            if sets and mixed and not any(set(s["ids"]) == set(ids) for s in sets) and self.cart_set(sets[0]["lines"]):
                holding = True
                whole = True
        if buy and holding and whole and self.fit_pairs and not self.finished and self.left() >= 3 and self.fit_faults():
            self.closest_cart()
        blind = (self.cart_touched and not fresh and self.left() >= 2 and not self.dropped_ids
                 and (self.checkouts == 0 or self.refused_at < self.cart_changed_at))
        if whole and buy and (holding or blind):
            oa, f = shape_args(dict(self.brief.get("buy_args") or {}), self.schemas.get(buy) or {})
            if not f:
                if self.left() >= 2 and holding:
                    self.reread()
                    if self.finished or self.left() <= 0:
                        return ""
                if self.left() >= 2:
                    self.gate("order")
                if self.finished or self.left() <= 0:
                    return ""
                res = self.env(buy, oa)
                self.trace.append({"kind": "forced_order", "answered": res is not None})
                if self.finished or self.left() <= 0:
                    return ""
                if again and res is not None:
                    self.checkouts += 1
                    self.refused_at = self.step
                    o = res.get("observation")
                    self.observe(buy, o)
                    return "the order was rejected: " + self.show(o)
        ref = self.roles.get("refuse")
        if ref:
            da, f = shape_args(self.quiet_fill(dict(self.brief.get("refuse_args") or {})), self.schemas.get(ref) or {})
            if not f:
                if self.left() >= 2:
                    self.gate("end")
                if self.finished or self.left() <= 0:
                    return ""
                res = self.env(ref, da)
                self.trace.append({"kind": "forced_decline", "answered": res is not None})
                if res is not None and not self.finished:
                    o = res.get("observation")
                    self.observe(ref, o)
                    return "the decline was rejected: " + self.show(o)
        return ""

    def money_key(self, obs, sh):
        recs = [r for _, r in self.records_of(obs)]
        if len(recs) < 3:
            return None
        roles = {v for k, v in sh.items() if isinstance(v, str) and k != "price"}
        figs = {}
        order = []
        for rec in recs:
            for k, v in rec.items():
                if k == self.stock_key or k in roles or V22_ID.search(str(k)):
                    continue
                m = money(v)
                if m is not None and m > 0:
                    if k not in figs:
                        figs[k] = []
                        order.append(k)
                    figs[k].append(m)
        floor = max(3, -(-2 * len(recs) // 3))
        cands = [k for k in order if len(figs[k]) >= floor and MONEY_WORDS.search(under(k))]
        if not cands:
            return None
        best = max(cands, key=lambda k: (len(set(figs[k])), len(figs[k]), -order.index(k)))
        return best if len(set(figs[best])) >= 3 else None

class Episode(G6B, G6A, G5B, G5A, G4B, G4A, G3B, G3A, E1, E2, E3, E4, E5, E6, E7, E8, E9):
    pass


def agent_main(problem_data):
    try:
        ep = Episode(problem_data)
    except Exception as e:
        return [{"kind": "crash", "error": (type(e).__name__ + ": " + str(e))[:400]}]
    try:
        ep.run()
    except Exception as e:
        ep.trace.append({"kind": "crash", "error": (type(e).__name__ + ": " + str(e))[:400]})
        if not ep.finished:
            try:
                ep.finish()
            except Exception as e2:
                ep.trace.append({"kind": "crash", "error": (type(e2).__name__ + ": " + str(e2))[:400]})
    return list(ep.trace)


__all__ = ["agent_main"]
