from __future__ import annotations

import copy
import json
import random
import re
import time
from typing import Any

from src.agent.proxy_client import ProxyClient

LIGHT = "anthropic/claude-haiku-5.5"
HEAVY = "anthropic/claude-sonnet-5.5"
SPARE = "openai/gpt-6-luna"

LOOP_CALLS = 42
ALL_CALLS = 60
SPEND_SOFT = 0.055
SPEND_HARD = 0.078
WAITS = (4, 10, 20, 35)
WAIT_TOTAL = 45
SHOW_CHARS = 450
OBS_LIMIT = 15000
HISTORY_LIMIT = 150_000
# a cut of the history goes down to this size at once: cutting a little on every turn would change the history's middle
# each time, and each change makes the model read the whole history again at full price instead of from its cache
TRIM_TO = 90000
KEEP_RESULTS = 6
# the episode's wall clock is 300 s: no actor turn or interview starts after LOOP_STOP, no model call runs past CALL_END
LOOP_STOP = 240
CALL_END = 285
NOTE_FROM = 0.6             # the budget line can show once 60% of the spend cap or of LOOP_STOP is used
GATE_ROUNDS = 3
AUTO_PAGES = 6
DEEP_STEPS = 6              # steps per episode for reading on the search that found a cart line and opening its cheaper rows
DEEP_KEEP = 6               # steps that stay free after those reads: open, swap, cart view, checkout

_llm = ProxyClient(timeout=50, max_retries=1, retry_delay=1)
_env = ProxyClient(timeout=95, max_retries=3, retry_delay=1)


GUIDE = """You are Kyo, a careful buyer working for one shopper in an online store. You can act only by calling the store's tools. The episode is graded 1 or 0: it earns 1 only when the finish is exactly right. A purchase must contain every requested item at the requested quantity, each meeting every requirement in force when you check out, inside the budget; or, when the store truly has nothing that meets everything, the episode must end with the no-purchase tool in the way the request asks.

HOW THE STORE WORKS
- Every tool call is one step and steps are limited; thinking costs nothing. Tool names, argument names and result shapes are particular to this store: read each tool's description and schema and use the exact argument names and allowed values.
- Search tools can be narrow: a category filter, a keyword mode that may only read the first words of the query, a page size of a few rows, a token or offset for the next page. Compare the reported total with the rows you have seen and page on (with the exact token or offset the store gives) when the answer depends on seeing all of them. Keyword queries work best short and value-first (the wanted value plus the product noun). A filtered search that returns no rows usually means the filter value or the filter parameter is wrong: retry with the label exactly as result rows show it, or with another filter parameter.
- Search rows are summaries. Stores split a listing's record differently: one view can show its attributes (properties), another only its offer and description, and a side-by-side view may carry either. The ledger names the tool that shows attributes once Kyo knows it. Judge every requirement on a property from those attributes, so read them for each listing you may buy; one call that shows several listings saves steps when it shows what you need. Never open a listing again when nothing has changed since you read it.
- Questions to the shopper are handled for you by Kyo's interviewer, so you never message the shopper yourself. Its answers arrive in the conversation and are added to the ledger.
- The request can also ask for steps along the way: an approval, a message, something to check or read first. The ledger lists them. Kyo carries out the ones due just before the order or the ending itself when you call the checkout or the ending tool, so never wait for those and never end without a purchase because of them; do any others with the store's tools (product questions go through Kyo's interviewer).

WHAT COUNTS AS A FIT
- The kind of product is decided by the listing's category label: only the label that matches the requested item as a whole counts, never a neighbouring one.
- A requirement on a property is met when the listing's attribute for that property states the value. Key spelling does not matter (spaces, underscores, camel case, prefixes), and one element of a comma or slash list is enough. Values match by their words: case, singular or plural and plain synonyms are fine, and a value that contains the required value's words counts ("deep teal" meets teal, "extra roomy fit" meets roomy). A value with different words does not count (an abbreviation or code is not the word it stands for, and "teal green" is not "sea green"). Units are converted before comparing numbers, limits include the edge value, and a range must lie wholly inside a limit.
- An attribute whose key names the requirement's property (under that name or a plain synonym) decides: if it says something else, the listing fails whatever other keys or the title say. But several keys naming that same property (the same words spelled differently, such as "lid colour" and "lid_colour") are one attribute: a required word value is met when any of them states it, never a conflict that fails the listing; this does not hold for a required number, and a band such as 500-1000 is not 500. A key for a different property, even a related one (a handle colour is not the body's colour), decides nothing about the requirement. Kyo adds [evidence] lines after opened listings with the keys whose names match a requirement.
- When the listing has no attribute for that property, the wanted value stated under another attribute (for example a list of styles or features that includes it) or in the title or description counts. A number of another kind does not (a weight is not a capacity), nor a bare figure whose text does not say what it measures.
- When the category label itself states a requirement's value (a season or audience in the label), that requirement is met by the category.
- A requirement can point at another listing instead of giving a value ("the same X as the listing sold by <shop> with <property>", "within N of the X on the page of ..."). Resolve it first: find that listing (search its category, brand, shop or words), open its page in full with the single-item or side-by-side tool (a search row is not enough), and when that page refers you to a further listing for the property, find and open that one the same way; the last page gives the value. The order counts only when every page of that chain was opened. When the wanted value is anything but that other listing's value, the rule excludes only listings sharing that exact value, and never end without a purchase because of it alone.
- When a listing you are about to buy sends you to another page for more about it, look at that page before you buy.
- When one requested item must fit another (an accessory for a device), choose the two together from the listings' own words (a list of what it fits, a model or series code that both pages carry). When no accessory that meets its own requirements fits the device you picked, switch to another device that meets its requirements and that such an accessory fits; never end without a purchase while that switch is untried.
- Respect exclusions and closed lists. Wishes ("ideally", "would be nice") are tie-breakers only.
- Never buy an item that the store shows as sold out; the total (price times quantity, summed over every line) may not exceed the budget; equal is fine.

CHOOSING
- When the request asks for the cheapest (lowest total, smallest price), the order must hold the lowest-priced listing among ALL listings that fit. Find the whole fitting set (page through it: result rows are often in no price order, and Kyo reads the next pages of a short result itself), check candidates in ascending price, and take the first that fully fits. When a search takes a maximum price, use it: list the category below the price of your current best pick, so only cheaper candidates are left to check.
- When the request asks for the most or least of some measure, compare every fitting listing on that measure and take the extreme; a listing that does not state the measure cannot win.
- Otherwise any listing that meets everything is right: do not waste steps hunting for something better.
- Cart each item as soon as you have opened a listing that meets every requirement for it (with a cheapest, most or least pick: once you have compared the fitting set), then move on. Stores often sell out a carted line soon after it is added, and an early cart leaves steps to replace it.
- A request for several different items needs one cart line per item, each at its requested quantity.

CHANGES WHILE YOU WORK
- The shopper or the store can change things: a new budget, a requirement added or dropped, a price change, a listing sold out. They appear inside tool results, often when you try to check out (a refusal); a note counts whichever tool's result shows it, and the ledger lists the requirements in force. The episode goes on after a refusal: apply every change, fix the cart and check out again.
- Re-read a chosen listing's record shortly before checking out, because price and stock can change silently.

FINISHING
- Put exactly the chosen lines in the cart (remove anything else), look at the cart once, then check out with a call on its own.
- End without a purchase only after a real search finds no listing that meets everything. Running short of steps proves nothing of the kind: then check out the best cart you have. Follow the request's wording for that ending, and when a remark is needed, keep it short and name no listing.
- Every reply must call at least one tool. Keep your text short: what you know, then the next move."""


BRIEF = """You prepare a shopping task for an agent. Read the shopper's request and the store's tools and return ONE JSON object (compact, no indentation, nothing else) with these keys:

"items": a list with one entry per distinct product the shopper wants bought, each {"name": the kind of product in the request's words, "shelf": the store's category label for it when a tool lists labels (copy it exactly), else "", "quantity": units of that one listing (integer, 1 when not stated; a pair or a set that is one listing counts as 1), "musts": a list of firm requirements on that product, each "property: constraint" with the exact value, limit, exclusion or closed list. Name the property with the request's own word for it ("meant for a lakeside occasion" gives "occasion: lakeside", "a 12-inch blade" gives "blade length: 12 inch"); do not swap it for a neighbouring property. A must whose value is read from another listing is ONE must holding the whole description of that listing ("rim colour: unlike the rim colour of the kettle Ovarno sells with a glass lid"): words that describe that other listing (its shop, its kind, "with <property> <value> and <property> <value>" after it) stay inside that one must and are never musts of this product}. Never put price, budget, stock or quantity into musts. The story around the request (the person meant to use it, where it will stand, what went wrong before, the occasion behind it) is context, not a must, unless it states a property's value or limit outright; and never turn words that are part of what the product is called (a season, an audience or a use named with the product) into musts: those belong to "name". A product the request names in one phrase joined by "and" (one "I want ..." with one quantity, often the name of one store department) is ONE item; make separate items only when the request gives each product its own quantity or its own requirements.
"budget": the most the shopper will pay in total as a number in the request's own unit, or null.
"budget_unit": that unit in words (for example "cents"), or null.
"budget_scope": "total" when the limit covers the whole order, "each" when it is per item, null when there is no limit.
"in_stock_only": true unless the request clearly accepts items that are not available.
"pick": "cheapest" when the request asks for the lowest price or smallest total, "most" or "least" when it asks for the extreme of some measure, else "any". Remarks that money is tight are not a pick rule.
"pick_measure": what is maximised or minimised for "most"/"least", else "".
"messages": how many messages the shopper allows the agent to send (integer), or null when not stated.
"steps": how many steps, moves or tool calls the request allows (integer), or null.
"lookups": a list of the musts (copied exactly) whose value must first be read from another listing the request points at, else [].
"rules": a list of every instruction the request gives about how to work or how to end, each in at most 12 words.
"wishes": a list of things the shopper would merely like.
"ask_first": a list of things the request explicitly says to check with the shopper before choosing (empty when none).
"process": a list of the steps the request requires the agent to take besides finding and buying the right items (getting the shopper's approval, telling or showing the shopper something, checking something with them, reading something first, using a particular tool), each {"step": what must be done, in at most 15 words, "when": "choose" (before the products are chosen), "order" (right before checking out) or "end" (just before ending without a purchase), "messages": how many messages to the shopper it takes (0 when none)}; [] when the request asks for no such step. Requirements on the items, the budget, stock, the limits on messages and steps, and how to end when nothing fits are not steps.
"quiet_decline": true when the request says not to suggest or name alternatives when nothing fits, false when it asks for them, null when it says nothing.
"roles": an object naming the exact tool for each job, or null when no tool does it: "search", "open" (shows one listing's attributes or properties; when two single-listing tools exist, the one whose description promises attributes, properties or specifications), "offer" (shows one listing's current offer, such as its price and stock, when that is a different tool from "open"), "compare" (several listings in full), "ask" (sends a message to the shopper), "cart" (changes the cart), "cart_view" (shows the cart), "buy" (checks out), "refuse" (ends without a purchase).
"buy_args": the fixed arguments that make the "buy" tool check out (for a tool with a mode argument, that mode), else {}.
"refuse_args": the fixed arguments that make the "refuse" tool end without a purchase, else {}.
"""


PLAN = """You choose the questions a shopping agent sends to a shopper. Shoppers hold a few firm preferences they did not write down, each about one property of one requested product. A question reveals a preference only when it names that exact property, and each question is answered only about the first property it names, so every question costs one property.

You get the request, the items with what the request already settles for each, and a numbered list of attribute keys seen on opened listings of each item's category, with how many of those listings carry the key and example values. An unwritten preference may be on a property that no listed key names.

Choose the properties in this order:
0. What the request itself asks you to check with the shopper (listed under ASK FIRST when there is any), each named by the property it is about.
1. Hinted properties. The request's story often points at an unwritten preference without giving its value: a sentence about something the shopper cannot judge or leaves to you, someone whose taste decides, the product's looks or the setting it belongs in, the person meant to use or wear it, or what is inside it. For each such sentence, name the one property it points at and the item it is about, in the order the story gives them.
Name a hinted property by its plain name: a hint about who will wear it points at gender, a hint about its looks at colour or finish (whichever the request leaves open).
2. Then the listed keys, ranked: favour the properties a buyer of that kind of product chooses between first (often its size, capacity or dimensions, its type, its material or its colour, whichever that kind of product is bought by) and keys carried by most of the item's listings; avoid keys seen on only one or two of them.
Skip a property the request already settles for that item, a second name for a property already chosen, a key that lists purchase variants (a mix of sizes, colours and pack counts), identifiers, warranty and other logistics. With several items, put every item's hinted properties first, then take turns between the items.
"label" is the property's plain name: for a listed key, all of the key's words in plain spelling ("lid colour" for lidColour, "rim finish" for rim_finish; never shortened to "colour" or "finish"); only the property's name, no example values, no brackets, no second property.
Choose up to COUNT, best first. Return ONE JSON object and nothing else: {"ask": [{"item": item number, "label": "...", "hint": "at most 8 of the story's words it comes from, or an empty string"}]}"""


HEAR = """A shopping agent asked a shopper some questions. Read each answer and return ONE JSON object and nothing else:
{"needs": [{"item": item number, "need": "property: constraint", "points": true when the value is to be read from another listing, else false}], "drop": [{"item": item number, "property": "a requirement the shopper now gives up"}], "free": [{"item": item number, "property": "..."}], "crowded": [numbers of the questions whose answer complains that the message asked about too many things or wants a single question; not answers that only say they did not follow it], "budget": new total limit as a number or null}
- "needs": every firm preference an answer states, with the exact value or limit and its unit ("at least 30 cm", "oval", "not wicker"). Name the need by the property the answer itself names, which may differ from the one asked about; several answers about one property make one need. Copy the value word for word as the answer says it, keeping its nouns and units ("at least 3 shelves", not "at least 3").
- An answer can give the value by pointing at another listing (a value like, unlike or near the one on some shop's product, that product picked out by a few of its properties): that is ONE need on the property the answer names, with "points": true. Its value is the answer's own words copied exactly, from the comparison words to the end of that description, including what it says about a listing that page may name; never shorten or reword it. The properties describing the other product are not needs of this item.
- "free": the property of each question the shopper said they do not mind about.
- Folksy or roundabout wording that names a value still states that value."""


NOTE = """While a shopping agent works, the store showed this note (it may come from the shopper or the store). Return ONE JSON object and nothing else:
{"kind": "change" when the note changes the task (budget, requirements, a price, availability, a refusal of the order), "error" when it only reports that a call was malformed or not accepted, "other" for anything else, "budget": the new total limit as a number in the request's unit, or null, "add": [{"item": item number, "need": "property: constraint"}], "drop": [{"item": item number, "need": "the requirement no longer wanted"}], "gone": [listing ids said to be unavailable], "sold_out": true when it says a chosen listing is gone, sold out or no longer available (even without naming it), "price_moved": true when it says a price changed, "summary": "one short sentence"}
A replaced requirement is a drop of the old one plus an add of the new one. Report every change in the note."""


CHECK = """You are the last check before a shopping agent checks out. Decide from the records shown whether this cart is exactly right.
Reading rules: a requirement is met when the listing's attribute for that property states the value (any key spelling, one element of a list is enough, case, singular/plural and plain synonyms count, a value containing the required value's words counts, such as "deep teal" for teal, units converted, limits include the edge, a range must lie wholly inside); an attribute whose key names the same property as the requirement decides, and if it says something else the listing fails; several keys naming that same property (the same words spelled differently, such as "lid colour" and "lid_colour") are one attribute: a required word value is met when any of them states it, never a conflict that fails the listing; this does not hold for a required number, and a band such as 500-1000 is not 500; a key for a different property, even a related one (a handle colour is not the body's colour), decides nothing; when the listing has no attribute for that property, the wanted value stated under another attribute or in the title or description counts (a number of another kind does not: a weight is not a capacity; nor does a bare figure whose text does not say what it measures); a requirement the category label itself states is met by that category; the category label must match the requested item as a whole; a rule of being unlike another listing's value counts as met unless the records show that same value. Each requested item must appear as a separate cart line at the requested quantity, nothing else may be in the cart, nothing shown out of stock, and the total of price times quantity over all lines must be within the budget. The newest record of a listing wins.
When the pick rule is cheapest, most or least, also look at the other listings shown: if one of them clearly fits every requirement and beats the cart's choice on that rule, the cart is wrong.
Return ONE JSON object and nothing else: {"ok": true or false, "problems": ["short, concrete problem", ...], "better": [listing ids that should replace a cart line, best first]}. Use ok=false only for a problem the records clearly show or a requirement no record addresses."""


READING = """the listing's attribute for a property decides when its key names that same property (any key spelling, one element of a list is enough, synonyms and unit conversions count, a value containing the required value's words counts, such as "deep teal" for teal, limits include the edge); several keys naming that same property (the same words spelled differently, such as "lid colour" and "lid_colour") are one attribute: a required word value is met when any of them states it, never a conflict that fails the listing; this does not hold for a required number, and a band such as 500-1000 is not 500; a key for a different property, even a related one (a handle colour is not the body's colour), decides nothing; when no attribute names that property, the wanted value stated under another attribute or in the title or description counts (a bare figure that does not say what it measures counts for nothing); a requirement the category label itself states is met by that category; the category label must match the item; a rule of being unlike another listing's value counts as met unless the records show that same value; out-of-stock listings and listings that break the budget do not fit."""

AUDIT = """A shopping agent wants to end without buying because it thinks nothing fits. Check the listing records shown against the requirements, with these reading rules: """ + READING + """
Records marked ROW were seen only as a search result row: their page (the attributes) has not been read, so they can be neither passed nor failed on a property the row does not show.
Return ONE JSON object and nothing else: {"fits": {"item number": [listing ids that appear to meet every requirement, cheapest first, at most 4]}, "open": [ids of ROW listings of a requested kind, inside the budget, whose page could show that they fit, most promising first, at most 6], "unseen": [numbers of the requested items of whose kind no listing appears in the records at all], "reason": "one sentence"}"""

UNMIX = """A shopper's request was read into firm requirements on a product. Some requirements take their value from another listing the request points at, and the words that pick out that other listing (its kind, its shop, the properties named after it with "with ...") are sometimes read by mistake as requirements on the product being bought. Using the request's wording, say which of the OTHER REQUIREMENTS below only describe that other listing. Return ONE JSON object and nothing else: {"describe_other": [those requirements copied exactly; empty when every one is a real requirement on the product]}"""

TRAIL = """A shopping agent is about to check out. Some requirements take their value from another listing instead of stating it, and a listing's page can send the reader on to a further listing for that property. The order counts only when the agent has opened in full every listing along each such chain. Follow each requirement's chain from the requirement's own description, link by link, through the pages' own words, using the records below (OPENED: the agent has opened that page; ROW: seen only as a search result row, its page not read).
Return ONE JSON object and nothing else: {"chains": [{"need": the requirement copied exactly, "links": [{"id": the listing id when a record below is that link, else "", "about": how the requirement or the previous page describes that listing}], "done": true when the last link is an OPENED page that states the property's value itself, else false, "value": the property's value as stated on that last page, or ""}]}
List each chain's links in order and stop at the first link whose page is not OPENED or not found, since its words are still unknown."""

GATE = """A shopping agent is about to STAGE. The shopper's request asks for the steps below along the way. Decide from the numbered RECORD of what the agent has done whether each step due before this STAGE is done for the cart as it is now. A step counts as done only when a RECORD line shows it being done and, for a step about the cart or the order, that line comes after the cart last changed and its reply grants it; questions on a product's properties do not do a step.
When a step is still missing, give the one store call that does it next: a tool from TOOLS with its arguments. A message to the shopper goes through the messaging tool: one short sentence or question about that step alone, in plain words, naming no product properties or values the step does not need. Give no call when every due step is done or when the messages or steps left cannot do the missing one.
Return ONE JSON object and nothing else: {"steps": [{"step": the step, "done": true or false, "lines": [the RECORD line numbers that show it done]}], "call": {"tool": "...", "args": {...}} or null, "hold": what a reply asks to change before going on, or "", "needs": [{"item": item number, "need": "property: constraint"} for each firm requirement such a reply states]}"""

SWAP = """A listing in a shopping agent's cart has just sold out. Find replacements for that cart line among the other listing records shown, with these reading rules: """ + READING + """
Return ONE JSON object and nothing else: {"fits": [{"id": listing id, "price": its price as a number as the record shows it} for every listing that appears to meet every requirement of the sold-out line's item, at most 6], "reason": "one sentence"}"""

SHAPE = """A store tool returned the result below. Name its parts by the exact keys the result and the tool's parameters use. Return ONE JSON object and nothing else: {"rows": the key of the list of listings, "count": the key holding how many listings matched in all (not how many are shown), or null, "next": the key holding the value that asks for the following page, or null, "next_arg": the tool parameter that takes that value, or null, "price": the key, inside a row, of the listing's price, or null, "stock": the key, inside a row, that says whether the listing can be bought now, or null}"""


def _dump(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(value)


def _has_rows(node: Any) -> bool:
    return isinstance(node, dict) and any(isinstance(v, list) and v and all(isinstance(r, dict) for r in v) for v in node.values())


def _payload(observation: Any) -> Any:
    """A result whose rows sit one level down beside other parts (a store reply that carries a note): that inner part,
    when it is the only one holding rows; anything else as it is."""
    if not isinstance(observation, dict) or _has_rows(observation):
        return observation
    inner = [v for v in observation.values() if _has_rows(v)]
    return inner[0] if len(inner) == 1 else observation


def _clip(value: Any, limit: int, depth: int = 0) -> Any:
    if depth > 7:
        return "..."
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "..."
    if isinstance(value, dict):
        return {k: _clip(v, limit, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip(v, limit, depth + 1) for v in value]
    return value


def _json_obj(text: Any) -> dict[str, Any] | None:
    if not isinstance(text, str):
        return None
    text = text.strip()
    fence = re.match(r"^```[A-Za-z]*\s*(.*?)\s*```$", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        got = json.loads(text)
        return got if isinstance(got, dict) else None
    except ValueError:
        pass
    left, right = text.find("{"), text.rfind("}")
    if 0 <= left < right:
        try:
            got = json.loads(text[left:right + 1])
            return got if isinstance(got, dict) else None
        except ValueError:
            return None
    return None


def _words(key: str) -> str:
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(key))
    return re.sub(r"[\s_.\-]+", " ", key).strip().lower()


def _stem(text: str) -> frozenset[str]:
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in _words(text).split())


def _names(prop: frozenset[str], key: frozenset[str]) -> bool:
    if not prop or not key:
        return False
    return prop == key or prop <= key or (len(key) >= 2 and key <= prop)


def _kinds(schema: dict[str, Any]) -> list[str]:
    kind = schema.get("type")
    if isinstance(kind, str):
        return [kind]
    return [k for k in kind or [] if isinstance(k, str)]


def _fits_kind(value: Any, kind: str) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "array":
        return isinstance(value, list)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "null":
        return value is None
    return True


def _shape(value: Any, schema: Any, where: str, faults: list[str], cut: bool = True) -> Any:
    if not isinstance(schema, dict):
        return value
    kinds = _kinds(schema)
    if kinds and not any(_fits_kind(value, k) for k in kinds):
        for kind in kinds:
            if kind == "integer" and isinstance(value, float) and value.is_integer():
                value = int(value)
                break
            if kind in ("integer", "number") and isinstance(value, str) and re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", value):
                number = float(value)
                value = int(number) if kind == "integer" or number.is_integer() else number
                break
            if kind == "string" and isinstance(value, (int, float)) and not isinstance(value, bool):
                value = str(value)
                break
            if kind == "boolean" and isinstance(value, str) and value.strip().lower() in ("true", "false"):
                value = value.strip().lower() == "true"
                break
            if kind == "array" and not isinstance(value, list) and value is not None:
                value = [value]
                break
        if not any(_fits_kind(value, k) for k in kinds):
            faults.append(f"{where} should be {'/'.join(kinds)}")
            return value
    options = schema.get("enum")
    if isinstance(options, list) and value not in options:
        if isinstance(value, str):
            low = value.strip().lower()
            match = [o for o in options if isinstance(o, str) and o.lower() == low]
            if match:
                value = match[0]
        if value not in options:
            faults.append(f"{where}: allowed values are {options}")
    if isinstance(value, str) and isinstance(schema.get("maxLength"), int) and len(value) > schema["maxLength"]:
        if cut:
            value = _fit(value, schema["maxLength"])
        else:
            # a cut query loses its last word half-way and finds nothing: the caller writes a shorter one instead
            faults.append(f"{where} has {len(value)} characters and this tool takes at most {schema['maxLength']}: "
                          "send a shorter value that keeps the words that matter")
    if isinstance(value, str) and isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
        faults.append(f"{where} is too short")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(schema.get("minimum"), (int, float)) and value < schema["minimum"]:
            faults.append(f"{where} is below {schema['minimum']}")
        if isinstance(schema.get("maximum"), (int, float)) and value > schema["maximum"]:
            faults.append(f"{where} is above {schema['maximum']}")
    if isinstance(value, list):
        if isinstance(schema.get("maxItems"), int) and len(value) > schema["maxItems"]:
            faults.append(f"{where} allows at most {schema['maxItems']} entries")
        if isinstance(schema.get("minItems"), int) and len(value) < schema["minItems"]:
            faults.append(f"{where} needs at least {schema['minItems']} entries")
        if isinstance(schema.get("items"), dict):
            value = [_shape(v, schema["items"], f"{where}[{i}]", faults, cut) for i, v in enumerate(value)]
    if isinstance(value, dict):
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        if schema.get("additionalProperties") is False:
            for name in [n for n in value if n not in props]:
                faults.append(f"{where}.{name} is not an allowed argument")
        for name in schema.get("required") or []:
            if name not in value:
                faults.append(f"{where}.{name} is required")
        value = {k: _shape(v, props.get(k), f"{where}.{k}", faults, cut) if k in props else v for k, v in value.items()}
    return value


def _fit(text: str, limit: int) -> str:
    """The text cut to the limit at a word boundary when that keeps most of it."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    room = head.rsplit(" ", 1)[0].rstrip(" ,;:-") if " " in head else head
    return room if len(room) >= limit // 2 else head


def _list_args(schema: Any) -> list[str]:
    """Arguments that take a list of plain values (listing ids)."""
    props = (schema or {}).get("properties") or {} if isinstance(schema, dict) else {}
    found = []
    for key, spec in props.items():
        if isinstance(spec, dict) and "array" in _kinds(spec):
            inner = spec.get("items")
            if not isinstance(inner, dict) or not _kinds(inner) or "string" in _kinds(inner):
                found.append(key)
    return found


_MOST = r"(?:up to|at most|no more than|not more than|maximum of|max(?:imum)?\.?)\s+(\d+)"


def _said_cap(text: str) -> int | None:
    """How many entries one call takes, when a tool's description says so in words ("up to 5", "1 or 2 listings")."""
    found = [int(n) for n in re.findall(_MOST, text, re.I)]
    found += [max(int(a), int(b)) for a, b in re.findall(r"\b(\d+)\s*(?:or|to|-)\s*(\d+)\s+(?:listings?|items?|products?|ids?|entries|records)\b", text, re.I)]
    found += [max(int(a), int(b)) for a, b in re.findall(r"\bbetween\s+(\d+)\s+and\s+(\d+)\b", text, re.I)]
    found = [n for n in found if 1 <= n <= 100]
    return min(found) if found else None


def _said_chars(text: str, arg: str, only: bool) -> int | None:
    """A text argument's length limit stated in a tool's description (next to the argument's name, or anywhere when the
    tool has one text argument)."""
    limit = _MOST + r"\s+(?:characters|chars|letters)"
    found = re.search(re.escape(arg) + r"[^.;]{0,60}?" + limit, text, re.I) or (re.search(limit, text, re.I) if only else None)
    if not found:
        return None
    number = int(found.group(1))
    return number if 0 < number <= 100_000 else None


def _items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, (str, dict)) and value:
        return [value]
    return []


def _count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\s*\d+(\.0+)?\s*", value):
        return int(float(value))
    return None


def _id_like(value: Any, named: bool = False) -> bool:
    if not isinstance(value, str) or not 3 <= len(value.strip()) <= 64 or " " in value.strip():
        return False
    return named or bool(re.search(r"\d", value))


def _learn_id(rows: list[dict[str, Any]]) -> str | None:
    best = None
    for key in rows[0]:
        values = [row.get(key) for row in rows]
        if not all(_id_like(v, "id" in str(key).lower()) for v in values):
            continue
        values = [v.strip() for v in values]
        if len(rows) > 1 and len(set(values)) < len(values):
            continue
        score = ("id" in str(key).lower(), sum(len(v) for v in values) / len(values))
        if best is None or score > best[0]:
            best = (score, key)
    return best[1] if best else None


def _in_rows(node: Any, ident: str, depth: int = 0) -> bool:
    if depth > 5:
        return False
    if isinstance(node, list):
        return any(isinstance(v, dict) and ident in [str(x).strip() for x in v.values() if isinstance(x, str)] for v in node) or any(_in_rows(v, ident, depth + 1) for v in node)
    if isinstance(node, dict):
        return any(_in_rows(v, ident, depth + 1) for v in node.values())
    return False


def _fact_block(node: Any) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    best = None
    for value in node.values():
        if isinstance(value, dict) and len(value) >= 2:
            scalars = {k: v for k, v in value.items() if isinstance(v, (str, int, float)) and not isinstance(v, bool)}
            if len(scalars) >= 2 and (best is None or len(scalars) > len(best)):
                best = scalars
    return best


def _twin_keys(pairs: list[tuple[str, Any]]) -> list[str]:
    """Keys that name one property twice (the same words in another spelling) with differing values."""
    groups: dict[str, list[tuple[str, str]]] = {}
    for key, value in pairs:
        groups.setdefault(_words(key), []).append((key, str(value).strip().lower()))
    return [k for kv in groups.values() if len(kv) > 1 and len({v for _, v in kv}) > 1 for k, _ in kv]


def _chain_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:[.,][0-9]+)?", str(text))


def _chain_stem(text: str) -> frozenset[str]:
    """Word stems of a sentence, punctuation dropped (a plural s off words longer than 3 letters)."""
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", str(text))]
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def _chain_score(hits: list[str]) -> int:
    """Named values a page shows, once each (key spellings folded): 2 for a value named after its key, 1 for a bare value."""
    seen: dict[str, int] = {}
    for hit in hits:
        weight = 2 if hit.startswith("+") else 1
        key = re.sub(r"[^a-z0-9=]", "", hit.lower())
        seen[key] = max(seen.get(key, 0), weight)
    return sum(seen.values())


def _phrase_in(phrase: str, text: str, case: bool = False) -> bool:
    """A value occurs in a text as whole words (case-insensitive unless asked)."""
    phrase = str(phrase).strip()
    if len(phrase) < 2:
        return False
    flags = 0 if case else re.I
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(phrase) + r"(?![A-Za-z0-9])", str(text), flags) is not None


def _one_word_names(record: dict[str, Any], skip: str | None) -> list[tuple[str, str]]:
    """A record's own short name-like values: top-level one-word capitalised strings (a shop or a brand)."""
    out = []
    for key, value in record.items():
        if key == skip or not isinstance(value, str):
            continue
        value = value.strip()
        if re.fullmatch(r"[A-Z][a-z]{2,29}", value):
            out.append((key, value))
    return out


class Item:
    def __init__(self, name: str, shelf: str, qty: int, musts: list[str]):
        self.name = name
        self.shelf = shelf
        self.qty = qty
        self.musts = musts
        self.told: list[str] = []
        self.dropped: list[str] = []
        self.free: list[str] = []


class Kyo:
    def __init__(self, problem: dict[str, Any]):
        environment = problem["environment"]
        self.binding = dict(environment["binding"])
        self.view = environment["policy_view"]
        self.request = str(self.view.get("query") or "")
        self.tools = [t for t in self.view.get("tools") or [] if isinstance(t, dict) and isinstance(t.get("function"), dict) and isinstance(t["function"].get("name"), str)]
        # Kyo's own copy: limits found in the descriptions are added here, never to the tools the model is shown
        self.schemas = {t["function"]["name"]: copy.deepcopy(t["function"].get("parameters")) if isinstance(t["function"].get("parameters"), dict) else {"type": "object", "properties": {}} for t in self.tools}
        # per (tool, list argument): entries a call may carry by the description, the most seen to work, the fewest seen to fail
        self.list_caps: dict[tuple[str, str], int] = {}
        self.list_ok: dict[tuple[str, str], int] = {}
        self.list_bad: dict[tuple[str, str], int] = {}
        steps = _count(self.view.get("max_steps"))
        if steps is None and isinstance(self.view.get("max_steps"), float):
            steps = int(self.view["max_steps"])
        self.max_steps = steps if steps and steps > 0 else 30
        self.step = 0
        self.finished = bool(self.view.get("finished"))
        self.broke = False
        self.no_credit = False
        self.waited = 0
        self.misses = 0
        self.cost = 0.0
        self.calls = 0
        self.loop_calls = 0
        self.trace: list[dict[str, Any]] = []
        self.brief: dict[str, Any] = {}
        self.roles: dict[str, str] = {}
        self.items: list[Item] = []
        self.budget: Any = None
        self.msg_limit = 0
        self.msg_used = 0
        self.process: list[dict[str, Any]] = []
        self.reserve = 0
        self.gate_msgs = 0
        self.gate_ok: set[tuple[str, str]] = set()
        self.done_log: list[str] = []
        self.done_steps: list[int] = []
        self.asked = False
        self.qa: list[tuple[str, str]] = []
        self.rows: dict[str, dict[str, Any]] = {}
        self.full: dict[str, dict[str, Any]] = {}
        self.seen_order: list[str] = []
        self.heard: set[str] = set()
        self.notes: list[str] = []
        self.version = 0
        self.cart_touched = False
        self.cart_at = -1
        self.cart_seen_at = -1
        self.cart_view: Any = None
        self.cart_lines: dict[str, int] = {}
        self.checked: set[str] = set()
        self.audited = False
        self.audits = 0
        self.audit_version = -1
        self.unseen: list[int] = []
        self.offer_seen: dict[str, int] = {}
        self.gone: dict[str, int] = {}
        self.unavailable: set[str] = set()
        self.sold_lines: set[str] = set()
        self.note_sold = False
        self.held = 0
        self.id_args: set[tuple[str, str]] = set()
        self.cart_said = ""
        self.refused_at = -1
        self.leads: list[str] = []
        self.refuse_blocks = 0
        self.pushed = False
        self.built: list[str] = []
        self.dropped: set[str] = set()
        self.late_held = False
        self.lead_items: dict[str, list[str]] = {}
        self.verdicts: dict[str, bool] = {}
        self.confirmed: str | None = None
        self.completed = False
        self.confirm_at: int | None = None
        self.last_note: dict[str, Any] = {}
        self.id_key: str | None = None
        self.facts_from: dict[str, bool] = {}
        self.queued: list[str] = []
        self.buys = 0
        self.refusals = 0
        self.recent: list[str] = []
        self.chat: list[dict[str, Any]] = []
        self.opened: set[str] = set()
        self.refs: list[tuple[int, str]] = []
        self.ref_values: dict[str, str] = {}
        self.trails = 0
        self.trail_blocks = 0
        # the cart as the cart tool's own reply lists it, once the key of a line's count is known
        self.qty_key: str | None = None
        self.cart_list_key: str | None = None
        self.cart_from_reply = False
        # id-like words seen anywhere in results (an id a note names counts as seen)
        self.id_words: set[str] = set()
        self.id_dropped: list[str] = []
        self.tool_keys: dict[str, set[str]] = {}
        self.view_keys: dict[str, tuple[int, set[str]]] = {}
        self.read_cache: dict[str, tuple[int, int, str]] = {}
        self.pages_read = 0
        self.shapes: dict[str, dict[str, Any] | None] = {}
        self.price_key: str | None = None
        self.stock_key: str | None = None
        self.wider_held = False
        self.paged_obs: list[Any] = []
        # cheapest pick: per search call (tool + args) its next-page parameter and value (None on the last page), and
        # per listing the search call that first showed it and whether those rows came in price order
        self.page_next: dict[str, tuple[str, Any] | None] = {}
        self.found_in: dict[str, tuple[str, dict[str, Any], str, bool]] = {}
        self.deep_done: set[str] = set()
        self.deep_steps = 0
        self.read_limits()

    def read_limits(self) -> None:
        """Limits a tool states only in words: how many listings one call carries, how long a text may be."""
        for tool in self.tools:
            fn = tool["function"]
            name, text = fn["name"], str(fn.get("description") or "")
            schema = self.schemas.get(name) or {}
            lists = _list_args(schema)
            cap = _said_cap(text) if len(lists) == 1 else None
            if cap:
                self.list_caps[(name, lists[0])] = cap
            props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
            texts = [k for k, v in props.items() if isinstance(v, dict) and "string" in _kinds(v) and "enum" not in v]
            for arg in texts:
                limit = _said_chars(text, arg, len(texts) == 1)
                have = props[arg].get("maxLength")
                if limit and not (isinstance(have, int) and have <= limit):
                    props[arg] = {**props[arg], "maxLength": limit}
        if self.list_caps:
            self.trace.append({"kind": "limits", "lists": {f"{t}.{a}": n for (t, a), n in self.list_caps.items()}})

    def list_room(self, tool: str, arg: str, default: int | None = 4) -> int | None:
        """Entries one call of this tool may carry in this list argument: below the fewest seen to fail (halved from it
        until a size works), never above the schema's or the description's limit; `default` when nothing is known."""
        key = (tool, arg)
        spec = (((self.schemas.get(tool) or {}).get("properties") or {}).get(arg) or {})
        told = [n for n in (spec.get("maxItems"), self.list_caps.get(key)) if isinstance(n, int) and not isinstance(n, bool) and n > 0]
        ok, bad = self.list_ok.get(key, 0), self.list_bad.get(key)
        if bad:
            room = min(bad - 1, max(ok, bad // 2, 1))
        elif told:
            room = min(told)
        elif default is None:
            return None
        else:
            room = max(default, ok)
        if told:
            room = min(room, min(told))
        return max(1, room)

    def note_list_result(self, tool: str, arg: str, ids: list[Any], observation: Any) -> bool:
        """A call that carried several listings: it worked when the result shows any of them; one that shows none of them
        marks that size as too many for this tool. Returns whether it worked."""
        if not isinstance(ids, list) or len(ids) < 2:
            return True
        key = (tool, arg)
        shown = _dump(observation)
        if any(str(i) in shown for i in ids):
            self.list_ok[key] = max(self.list_ok.get(key, 0), len(ids))
            return True
        self.list_bad[key] = min(self.list_bad.get(key) or 999, len(ids))
        self.trace.append({"kind": "list_fail", "tool": tool, "size": len(ids), "room": self.list_room(tool, arg)})
        return False

    def left(self) -> int:
        return self.max_steps - self.step

    def msgs_free(self) -> int:
        return self.msg_limit - self.msg_used - max(0, self.reserve - self.gate_msgs)

    def cart_mark(self) -> str:
        return _dump(sorted(self.cart_lines.items()))

    def page_tools(self) -> set[str]:
        page = self.roles.get("offer") or self.roles.get("open")
        return {t for t in (page, self.roles.get("compare")) if t}

    def facts_tool(self) -> str | None:
        known = next((t for t, ok in self.facts_from.items() if ok and self.single_target(t)), None)
        if known:
            return known
        tool = self.roles.get("open")
        return tool if self.facts_from.get(tool or "") is not False and self.single_target(tool) else None

    def compare_facts(self) -> bool | None:
        return self.facts_from.get(self.roles.get("compare") or "")

    def compare_bare(self) -> bool:
        seen = self.compare_facts()
        return seen is False or (seen is None and (self.facts_from.get(self.facts_tool() or "") is True or bool(self.roles.get("offer"))))

    def gate_due(self, stage: str) -> bool:
        return any(p["when"] == stage for p in self.process) and (stage, self.cart_mark() + f"#{self.version}") not in self.gate_ok

    def tail(self) -> int:
        talk = any(p["when"] == "order" and p["messages"] > 0 for p in self.process)
        return 2 if talk and self.msg_used < self.msg_limit and self.gate_due("order") else 1

    def elapsed(self) -> float:
        """Seconds since the episode began: run() marks the start, 2 s early for the setup before it."""
        if getattr(self, "started", None) is None:
            self.started = time.monotonic() - 2
        return time.monotonic() - self.started

    def turns_left(self) -> float | None:
        """Actor turns that the spend cap and the clock still allow, at the median pace of the last five turns (their model
        calls of every kind and their time; the median, so a one-off interview or check does not count as the pace);
        None before three turns."""
        marks = getattr(self, "marks", None) or []
        if len(marks) < 3:
            return None
        seq = marks[-5:] + [(time.monotonic(), self.cost, self.step)]
        costs = sorted(b[1] - a[1] for a, b in zip(seq, seq[1:]))
        times = sorted(b[0] - a[0] for a, b in zip(seq, seq[1:]))
        middle = len(costs) // 2
        per_cost = max(costs[middle] if len(costs) % 2 else (costs[middle - 1] + costs[middle]) / 2, 0.0005)
        per_time = max(times[middle] if len(times) % 2 else (times[middle - 1] + times[middle]) / 2, 1.0)
        by_spend = (getattr(self, "spend_cap", SPEND_HARD) - self.cost) / per_cost
        by_time = (LOOP_STOP - self.elapsed()) / per_time
        return max(0.0, min(by_spend, by_time))

    def budget_note(self) -> str:
        """A line for the actor when the spend cap or the clock, not the steps, will end the episode within a few turns:
        at that point Kyo checks out the cart as it stands, so a confirmed listing left out of the cart is lost."""
        turns = self.turns_left()
        if turns is None or self.buys or self.finished:
            return ""
        # only in the last part of either budget: earlier, the pace says little about the end
        if self.cost < NOTE_FROM * getattr(self, "spend_cap", SPEND_HARD) and self.elapsed() < NOTE_FROM * LOOP_STOP:
            return ""
        per_step = max(1.0, self.step / max(1, len(self.marks)))
        if turns * per_step >= self.left():
            return ""
        left = max(1, int(turns))
        if left <= 2:
            level, text = 2, (f"\n[Kyo] Budget nearly spent: about {left} more of your replies before Kyo ends the episode (the model budget "
                              "and the time run out, not the steps). Set the cart to the chosen line for each item and check out now.")
        elif left <= len(self.items) + 5:
            level, text = 1, (f"\n[Kyo] Budget: about {left} more of your replies before Kyo has to end the episode (the model budget and the "
                              "time run out before the steps do). Kyo then checks out the cart as it stands. Put each item's listing in the "
                              "cart as soon as its page confirms it fits, and check out once every item has its line.")
        else:
            return ""
        if level > getattr(self, "noted", 0):
            self.noted = level
            self.trace.append({"kind": "budget_note", "level": level, "turns": round(turns, 1), "step": self.step,
                               "cost": round(self.cost, 5), "elapsed": round(self.elapsed(), 1)})
        return text

    def think(self, messages: list[dict[str, Any]], models: list[str], max_tokens: int, tools: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
        for model in models:
            if self.calls >= ALL_CALLS or self.elapsed() >= CALL_END - 5:
                return None
            self.calls += 1
            tries = 0
            while True:
                message, status = self.call_model(model, messages, max_tokens, tools)
                if message is not None:
                    return message
                passing = status is None or status in (402, 408, 425, 429) or (isinstance(status, int) and status >= 500)
                if (not passing or tries >= (1 if status in (None, 408) else len(WAITS)) or self.waited + WAITS[tries] > WAIT_TOTAL
                        or self.elapsed() + WAITS[tries] + 10 > CALL_END):
                    break
                pause = WAITS[tries] * (0.8 + 0.4 * random.random())
                self.waited += WAITS[tries]
                tries += 1
                time.sleep(pause)
            if status == 402:
                self.no_credit = True
                return None
        return None

    def call_model(self, model: str, messages: list[dict[str, Any]], max_tokens: int, tools: list[dict[str, Any]] | None) -> tuple[dict[str, Any] | None, Any]:
        sent = messages
        if model.startswith("anthropic/") and len(messages) > 1:
            sent = [dict(m) for m in messages]
            marks = [0] + ([len(sent) - 1] if len(sent) > 1 else [])
            for index in marks:
                content = sent[index].get("content")
                if isinstance(content, str) and content:
                    sent[index]["content"] = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
        body: dict[str, Any] = {"model": model, "messages": sent, "max_tokens": max_tokens, "temperature": 0}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        # the client reads its timeout per request: near the end of the clock a call gets only the time that is left
        _llm.timeout = max(5, min(50, int(CALL_END - self.elapsed())))
        result = _llm.post_verbose("/inference/chat/completions", body)
        data = result.data
        if isinstance(data, dict) and data.get("choices"):
            usage = data.get("usage") or {}
            if isinstance(usage.get("cost"), (int, float)):
                self.cost += float(usage["cost"])
            message = data["choices"][0].get("message") or {}
            if message.get("content") or message.get("tool_calls"):
                return message, 200
            self.trace.append({"kind": "llm_fail", "model": model, "status": 0})
            return None, 0
        error = result.error or {}
        status = error.get("status")
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            status = _count(data["error"].get("code"))
            error = {"body": data["error"].get("message")}
        self.trace.append({"kind": "llm_fail", "model": model, "status": status, "body": str(error.get("body") or "")[:200]})
        return None, status

    def ask_json(self, prompt: str, models: list[str], max_tokens: int = 1800) -> dict[str, Any] | None:
        for model in models:
            message = self.think([{"role": "user", "content": prompt}], [model], max_tokens)
            got = _json_obj((message or {}).get("content"))
            if got is not None:
                return got
            if self.broke or self.no_credit or self.calls >= ALL_CALLS:
                return None
        return None

    def act(self, name: str, args: dict[str, Any]) -> dict[str, Any] | None:
        payload = dict(self.binding)
        payload["step"] = self.step + 1
        payload["action"] = {"name": name, "args": args}
        for _ in range(4):
            result = _env.post_verbose("/environment/call", payload)
            if isinstance(result.data, dict):
                data = result.data
                self.step = data["step"] if isinstance(data.get("step"), int) else self.step + 1
                if data.get("finished"):
                    self.finished = True
                seen = data.get("observation")
                if name in self.page_tools() and not (isinstance(seen, dict) and seen.get("error")):
                    for value in args.values():
                        self.opened.update(v.strip() for v in (value if isinstance(value, list) else [value]) if isinstance(v, str))
                return data
            error = result.error or {}
            status = error.get("status")
            body = str(error.get("body") or "")
            self.trace.append({"kind": "env_fail", "status": status, "body": body[:200]})
            if status == 409:
                low = body.lower()
                if "finish" in low or "quarantin" in low or "finaliz" in low:
                    self.finished = True
                    return None
                found = re.search(r"expected (\d+)", body)
                if found:
                    self.step = int(found.group(1)) - 1
                    payload["step"] = self.step + 1
                    continue
                if "reuse" in low or "different action" in low:
                    self.step += 1
                    payload["step"] = self.step + 1
                    continue
                return None
            if status in (400, 401, 402, 403, 404, 422):
                if status == 402:
                    self.broke = True
                return None
        return None

    def read_request(self) -> None:
        lines = []
        for tool in self.tools:
            fn = tool["function"]
            lines.append(f"- {fn['name']}: {fn.get('description', '')} | parameters: {_dump(fn.get('parameters') or {})}")
        prompt = BRIEF + "\nTOOLS:\n" + "\n".join(lines) + "\n\nREQUEST:\n" + self.request
        if self.view.get("opening") is not None:
            prompt += "\n\nOPENING NOTE FROM THE STORE:\n" + _dump(_clip(self.view.get("opening"), 1500))
        brief = self.ask_json(prompt, [LIGHT], 4000) or {}
        if not self.no_credit and (not _items(brief.get("items")) or not isinstance(brief.get("roles"), dict) or not brief["roles"].get("buy")):
            brief = self.ask_json(prompt, [HEAVY, LIGHT], 2500) or brief
        self.brief = brief
        roles = brief.get("roles") if isinstance(brief.get("roles"), dict) else {}
        self.roles = {k: v for k, v in roles.items() if isinstance(v, str) and v in self.schemas}
        for key in ("buy_args", "refuse_args"):
            if not isinstance(brief.get(key), dict):
                brief[key] = {}
        buy, refuse = self.roles.get("buy"), self.roles.get("refuse")
        if buy and buy == refuse and (not brief["buy_args"] or not brief["refuse_args"] or brief["buy_args"] == brief["refuse_args"]):
            ask = (f"The store tool {buy} both checks out and ends without a purchase, depending on its arguments. Its schema: "
                   + _dump(self.schemas.get(buy)) + "\nReturn ONE JSON object and nothing else: {\"buy_args\": the fixed arguments that check out, \"refuse_args\": the fixed arguments that end without a purchase} (only the arguments that choose the mode).")
            fixed = self.ask_json(ask, [LIGHT, HEAVY], 600) or {}
            if isinstance(fixed.get("buy_args"), dict) and isinstance(fixed.get("refuse_args"), dict) and fixed["buy_args"] != fixed["refuse_args"]:
                brief["buy_args"], brief["refuse_args"] = fixed["buy_args"], fixed["refuse_args"]
        for entry in _items(brief.get("items")):
            if not isinstance(entry, dict):
                continue
            quantity = _count(entry.get("quantity"))
            count = quantity if quantity and quantity > 0 else 1
            musts = [str(m) for m in _items(entry.get("musts")) if m]
            self.items.append(Item(str(entry.get("name") or "the product"), str(entry.get("shelf") or ""), count, musts))
        if not self.items:
            self.items = [Item("the requested product", "", 1, [])]
        for lookup in _items(brief.get("lookups")):
            text = str(lookup).strip()
            if not any(text in item.musts for item in self.items):
                key = _words(text.split(":")[0])
                text = next((m for item in self.items for m in item.musts if _words(m.split(":")[0]) == key), text)
            number = next((n for n, item in enumerate(self.items, 1) if text in item.musts), 1)
            if text and (number, text) not in self.refs:
                self.refs.append((number, text))
        self.unmix()
        budget = brief.get("budget")
        if isinstance(budget, str) and re.fullmatch(r"\s*\d+(\.\d+)?\s*", budget):
            budget = float(budget)
        if isinstance(budget, (int, float)) and not isinstance(budget, bool) and budget > 0:
            self.budget = budget
        limit = _count(brief.get("messages"))
        if limit is not None and limit >= 0:
            self.msg_limit = limit
        elif self.roles.get("ask"):
            self.msg_limit = 3
        steps = _count(brief.get("steps"))
        if steps is not None and 10 <= steps < self.max_steps:
            self.max_steps = steps
        for entry in _items(brief.get("process")):
            if isinstance(entry, dict) and str(entry.get("step") or "").strip():
                when = str(entry.get("when") or "").strip().lower()
                self.process.append({"step": str(entry["step"]).strip(), "when": when if when in ("choose", "order", "end") else "order",
                                     "messages": max(0, _count(entry.get("messages")) or 0)})
        if self.roles.get("ask"):
            talk = [p["messages"] for p in self.process if p["when"] in ("order", "end") and p["messages"]]
            self.reserve = min(max(talk), self.msg_limit) if talk else 0

    def unmix(self) -> None:
        for number, item in enumerate(self.items, 1):
            pointers = [need for n, need in self.refs if n == number and need in item.musts]
            rest = [m for m in item.musts if m not in pointers]
            if not pointers or not rest:
                continue
            prompt = (UNMIX + "\n\nREQUEST:\n" + self.request + f"\n\nPRODUCT: {item.name}\nREQUIREMENTS POINTING AT ANOTHER LISTING:\n"
                      + "\n".join(pointers) + "\nOTHER REQUIREMENTS:\n" + "\n".join(rest))
            got = self.ask_json(prompt, [HEAVY, LIGHT], 500) or {}
            moved = [m for m in rest if m in [str(x).strip() for x in _items(got.get("describe_other"))]]
            if not moved:
                continue
            item.musts = [m for m in item.musts if m not in moved]
            joined = pointers[0] + " (that listing: " + "; ".join(moved) + ")"
            item.musts = [joined if m == pointers[0] else m for m in item.musts]
            self.refs = [(n, joined if (n, need) == (number, pointers[0]) else need) for n, need in self.refs]
            self.trace.append({"kind": "unmix", "item": number, "moved": moved})

    def shelf_musts(self) -> None:
        """A must whose value is the category the request names the item by ("... from <label>"), that the request mentions
        only there and never states as a requirement, is the item's shelf when the brief gave the item no other shelf: once a
        seen row shows that label as its category, the must is dropped and the label becomes the shelf."""
        pending = self.__dict__.get("_label_musts")
        if pending is None:
            if not self.items:
                return
            named = {_words(m) for m in re.findall(r"\bfrom\s+([^;.\n]+)", self.request, re.I)}
            pending = []
            for number, item in enumerate(self.items, 1):
                for must in item.musts:
                    value = must.partition(":")[2].strip()
                    if not value or _words(value) not in named:
                        continue
                    # the brief already gave this item another category: the "from" phrase is not its label
                    if item.shelf and _words(item.shelf) != _words(value):
                        continue
                    spots = [m.start() for m in re.finditer(r"(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])", self.request, re.I)]
                    # stated anywhere but right after "from" (a requirement that names another item's label): keep it
                    if spots and all(re.search(r"\bfrom\s+$", self.request[max(0, s - 8):s], re.I) for s in spots):
                        pending.append((number, must, value))
            self._label_musts = pending
        if not pending:
            return
        # the category of a seen row only; a label listed in some tool's enum may be a seller or a shop
        cat_key = self.category_key() if self.rows else None
        shown = {_words(row[cat_key]) for row in self.rows.values() if isinstance(row.get(cat_key), str)} if cat_key else set()
        left = []
        for number, must, value in pending:
            item = self.items[number - 1]
            if must not in item.musts:
                continue
            if _words(value) not in shown:
                left.append((number, must, value))
                continue
            item.musts = [m for m in item.musts if m != must]
            self.refs = [(n, need) for n, need in self.refs if need != must]
            if not item.shelf:
                item.shelf = value
            self.trace.append({"kind": "shelf_must", "item": number, "must": must})
        self._label_musts = left

    def ledger(self) -> str:
        self.shelf_musts()
        parts = []
        many = len(self.items) > 1
        for number, item in enumerate(self.items, 1):
            needs = [m + (f" (the page it points at gives: {self.ref_values[m]})" if m in self.ref_values else "") for m in item.musts + item.told if m not in item.dropped]
            head = f"item {number}: {item.name}" if many else f"item: {item.name}"
            if item.shelf:
                head += f" (store label: {item.shelf})"
            head += f", quantity {item.qty}"
            text = head + "; requirements: " + ("; ".join(needs) if needs else "none beyond the kind of product")
            if item.free:
                text += "; shopper does not mind: " + ", ".join(item.free)
            parts.append(text)
        brief = self.brief
        if self.budget is not None:
            scope = "for each item" if brief.get("budget_scope") == "each" else "in total"
            parts.append(f"budget: at most {self.budget} {brief.get('budget_unit') or ''} {scope}".replace("  ", " "))
        pick = brief.get("pick")
        if pick == "cheapest":
            parts.append("pick: the cheapest listing that fits (lowest price)")
        elif pick in ("most", "least"):
            parts.append(f"pick: the {pick} {brief.get('pick_measure') or ''} among fitting listings".replace("  ", " "))
        else:
            parts.append("pick: any listing that fits everything")
        if brief.get("in_stock_only", True) is not False:
            parts.append("in stock only")
        for wish in _items(brief.get("wishes")):
            parts.append(f"wish (tie-breaker only): {wish}")
        for rule in _items(brief.get("rules")):
            parts.append(f"rule from the request: {rule}")
        if brief.get("quiet_decline") is True:
            parts.append("if nothing fits: end without naming or suggesting any listing")
        for entry in self.process:
            when = {"choose": "before choosing", "order": "at the order (Kyo does it when you check out)", "end": "at an ending without a purchase (Kyo does it then)"}[entry["when"]]
            parts.append(f"step the request asks for, {when}: {entry['step']}")
        facts = self.facts_tool()
        if facts and (self.facts_from.get(facts) is True or self.roles.get("offer")):
            bare = sorted(t for t in self.page_tools() | {self.roles.get("offer") or ""} if t and self.facts_from.get(t) is False)
            pages = sorted(t for t in self.page_tools() if t != facts)
            parts.append(f"listing attributes come from {facts}" + (f"; {', '.join(bare)} show none" if bare else "")
                         + (f"; a listing's page (what a chain of pages or a page check means) is shown by {' or '.join(pages)}" if pages else ""))
        return "\n".join("- " + p for p in parts)

    def status(self) -> str:
        left = self.left()
        text = f"[Kyo] step {self.step} of {self.max_steps} used, {left} left."
        if left <= self.tail() + 1:
            text += " FINAL STEPS: check out now when the cart holds a line for each item; end without a purchase only when your search showed that an item has no fitting listing (running out of steps does not show that)."
        elif left <= 6 or (left <= len(self.items) + 5 and self.buys == 0):
            text += " Few steps left: set the cart to the chosen lines and check out now."
        elif self.buys == 0 and left <= 12:
            text += " Steps are running low: settle on your picks, fill the cart and check out within the next few steps."
        elif self.buys == 0 and not self.cart_touched and self.step >= self.max_steps // 2:
            text += " Half the steps are used and the cart is empty: cart each item's fitting listing now (the store may still sell one out)."
        live = {need for _, need in self.needs_now()}
        lookups = [need for _, need in self.refs if need in live and need not in self.ref_values]
        if lookups and self.buys == 0:
            text += "\n[resolve first: open the listing each of these points at, and every listing its page refers to; the last page gives the value] " + " | ".join(lookups[:3])
        if self.leads:
            text += "\n[review candidates] " + ", ".join(self.leads)
        if self.notes:
            text += "\n[changes so far] " + " | ".join(self.notes[-4:])
        text += "\n[ledger]\n" + self.ledger()
        return text

    def ident(self, node: Any, in_list: bool = False, depth: int = 0) -> str | None:
        if not isinstance(node, dict) or len(node) < 3:
            return None
        if self.id_key and _id_like(node.get(self.id_key), True):
            return node[self.id_key].strip()
        nested = any(isinstance(v, dict) for v in node.values())
        if not (in_list or depth == 0 or nested):
            return None
        found = _learn_id([node])
        if found and ("id" in str(found).lower() or node[found].strip() in self.rows):
            return node[found].strip()
        return None

    def learn_rows(self, node: list[Any]) -> bool:
        rows = [n for n in node if isinstance(n, dict) and len(n) >= 3]
        if not rows or len(rows) < len(node) / 2:
            return False
        if self.id_key and all(_id_like(r.get(self.id_key), True) for r in rows):
            return True
        found = _learn_id(rows)
        if found:
            self.id_key = found
            return True
        return False

    def absorb(self, observation: Any) -> None:
        if len(self.id_words) < 20000:
            self.id_words.update(w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-:.]{2,63}", _dump(observation)) if re.search(r"\d", w))

        def walk(node: Any, depth: int, in_list: bool = False) -> None:
            if depth > 6:
                return
            if isinstance(node, dict):
                ident = self.ident(node, in_list, depth)
                if ident:
                    if ident not in self.rows:
                        self.seen_order.append(ident)
                        self.rows[ident] = {}
                    old = self.rows[ident]
                    if any(old.get(k) is True and v is False for k, v in node.items()):
                        self.unavailable.add(ident)
                    elif any(old.get(k) is False and v is True for k, v in node.items()):
                        self.unavailable.discard(ident)
                    self.rows[ident].update(node)
                    if _fact_block(node):
                        self.full[ident] = dict(self.rows[ident])
                    elif ident in self.full:
                        self.full[ident].update(node)
                    return
                for value in node.values():
                    walk(value, depth + 1)
            elif isinstance(node, list):
                rows = self.learn_rows(node)
                for value in node:
                    walk(value, depth + 1, rows)

        walk(observation, 0)

    def labels(self) -> set[str]:
        found: set[str] = set()

        def walk(schema: Any, depth: int) -> None:
            if depth > 6 or not isinstance(schema, dict):
                return
            for option in schema.get("enum") or []:
                if isinstance(option, str):
                    found.add(option.strip().lower())
            for value in schema.values():
                if isinstance(value, dict):
                    walk(value, depth + 1)

        for schema in self.schemas.values():
            walk(schema, 0)
        return found

    def category_key(self) -> str | None:
        counts: dict[str, set[str]] = {}
        present: dict[str, int] = {}
        for row in self.rows.values():
            for key, value in row.items():
                if isinstance(value, str) and 0 < len(value) <= 40 and not re.search(r"\d{3}", value):
                    counts.setdefault(key, set()).add(value)
                    present[key] = present.get(key, 0) + 1
        total = max(1, len(self.rows))
        known = self.labels()
        best = None
        for key, values in counts.items():
            if present[key] < 0.8 * total or len(values) > 40:
                continue
            listed = sum(1 for v in values if v.strip().lower() in known) / len(values)
            mean = sum(len(v) for v in values) / len(values)
            score = (-listed, len(values), -present[key], -mean)
            if best is None or score < best[0]:
                best = (score, key)
        return best[1] if best else None

    def key_table(self) -> list[tuple[str, str, int, list[str]]]:
        cat_key = self.category_key()
        groups: dict[str, dict[str, Any]] = {}
        for ident in self.seen_order:
            record = self.full.get(ident)
            if not record:
                continue
            block = _fact_block(record) or {}
            label = str(record.get(cat_key) or "listings") if cat_key else "listings"
            group = groups.setdefault(label, {"n": 0, "keys": {}})
            group["n"] += 1
            done: set[str] = set()
            for key, value in block.items():
                name = _words(key)
                if not name or name in done:
                    continue
                done.add(name)
                slot = group["keys"].setdefault(name, {"n": 0, "values": [], "per": {}})
                slot["n"] += 1
                text = str(value).strip().lower()
                slot["per"][ident] = text
                if text not in slot["values"]:
                    slot["values"].append(text)
        wanted = [(_words(item.shelf or ""), _words(item.name), {w for w in _stem(item.shelf or "") | _stem(item.name) if len(w) >= 4}) for item in self.items]
        matched = {label for label in groups if any(_words(label) in (shelf, name) or {w for w in _stem(label) if len(w) >= 4} & long for shelf, name, long in wanted)}
        if matched:
            groups = {label: group for label, group in groups.items() if label in matched}
        table = []
        for label, group in sorted(groups.items(), key=lambda kv: -kv[1]["n"]):
            kept: list[tuple[str, dict[str, Any]]] = []
            for name, slot in sorted(group["keys"].items(), key=lambda kv: -kv[1]["n"]):
                values = list(slot["per"].values())
                if not values:
                    continue
                mean = sum(len(v) for v in values) / len(values)
                if mean > 40 or sum(1 for v in values if " / " in v) * 2 >= len(values):
                    continue
                if len(values) >= 4 and len(set(values)) == len(values) and mean > 12:
                    continue
                twin = any(name.startswith(other + " ") and slot["per"] == spec["per"] for other, spec in kept)
                if twin:
                    continue
                kept.append((name, slot))
            for name, slot in kept[:14]:
                table.append((label, name, slot["n"], [v[:40] for v in slot["values"][:4]]))
        return table

    def item_groups(self) -> list[list[str]]:
        cat_key = self.category_key()
        groups: dict[str, list[str]] = {}
        for ident in self.seen_order:
            label = str(self.rows[ident].get(cat_key) or "") if cat_key else ""
            groups.setdefault(label, []).append(ident)
        wanted = [(_words(item.shelf or ""), _words(item.name), {w for w in _stem(item.shelf or "") | _stem(item.name) if len(w) >= 4}) for item in self.items]
        matched = [ids for label, ids in groups.items() if any(_words(label) in (shelf, name) or {w for w in _stem(label) if len(w) >= 4} & long for shelf, name, long in wanted)]
        pool = matched or list(groups.values())
        return sorted(pool, key=lambda ids: -len(ids))[: max(1, len(self.items))]

    def single_target(self, tool: str | None) -> str | None:
        schema = self.schemas.get(tool or "") or {}
        props = schema.get("properties") or {}
        texts = [k for k, v in props.items() if isinstance(v, dict) and "string" in _kinds(v) and "enum" not in v]
        target = next((k for k in schema.get("required") or [] if k in texts), None) or (texts[0] if len(texts) == 1 else None)
        if not tool or not target or any(k != target for k in schema.get("required") or []):
            return None
        return target

    def price_of(self, ident: str) -> float | None:
        value = (self.rows.get(ident) or {}).get(self.price_key) if self.price_key else None
        if isinstance(value, dict):
            value = next((v for v in value.values() if isinstance(v, (int, float)) and not isinstance(v, bool)), None)
        if isinstance(value, str) and re.fullmatch(r"\s*\d+(\.\d+)?\s*", value):
            value = float(value)
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    def buyable(self, ident: str) -> bool:
        if self.sold_out(ident):
            return False
        value = (self.rows.get(ident) or {}).get(self.stock_key) if self.stock_key else None
        return not (value is False or (isinstance(value, (int, float)) and not isinstance(value, bool) and value <= 0))

    def records_in(self, observation: Any) -> list[tuple[str, dict[str, Any]]]:
        if isinstance(observation, dict):
            ident = self.ident(observation)
            if ident:
                return [(ident, observation)]
            found: list[tuple[str, dict[str, Any]]] = []
            for value in observation.values():
                if isinstance(value, list):
                    found += [(i, r) for r in value if isinstance(r, dict) for i in [self.ident(r, True)] if i]
                elif isinstance(value, dict):
                    found += [(i, r) for v in value.values() if isinstance(v, list) for r in v if isinstance(r, dict) for i in [self.ident(r, True)] if i]
            return found
        if isinstance(observation, list):
            return [(i, r) for r in observation if isinstance(r, dict) for i in [self.ident(r, True)] if i]
        return []

    def note_view(self, name: str, observation: Any) -> None:
        for ident, record in self.records_in(observation):
            keys = set(record)
            self.tool_keys.setdefault(name, set()).update(keys)
            version, have = self.view_keys.get(ident, (-1, set()))
            self.view_keys[ident] = (self.version, (have if version == self.version else set()) | keys)

    def shown_already(self, name: str, ident: str) -> bool:
        version, have = self.view_keys.get(ident, (-1, set()))
        keys = self.tool_keys.get(name)
        return bool(keys) and version == self.version and keys <= have and ident not in self.gone

    def read_shape(self, name: str, observation: Any) -> dict[str, Any] | None:
        if name in self.shapes:
            return self.shapes[name]
        if not isinstance(observation, dict):
            return None
        lists = [k for k, v in observation.items() if isinstance(v, list) and len(v) >= 2 and all(isinstance(r, dict) for r in v)]
        if not lists:
            return None
        self.shapes[name] = None
        sample = {k: (v[:3] if k in lists else v) for k, v in observation.items()}
        prompt = (SHAPE + "\n\nTOOL: " + name + " | parameters: " + _dump(self.schemas.get(name) or {})
                  + "\n\nRESULT (first rows only):\n" + _dump(_clip(sample, 120))[:4000])
        got = self.ask_json(prompt, [LIGHT, HEAVY], 1500) or {}
        rows = got.get("rows") if got.get("rows") in lists else None
        if not rows:
            return None
        first = observation[rows][0]
        props = (self.schemas.get(name) or {}).get("properties") or {}

        def named(key: Any, where: dict[str, Any]) -> str | None:
            return key if isinstance(key, str) and key in where else None

        shape = {"rows": rows, "count": named(got.get("count"), observation), "next": named(got.get("next"), observation),
                 "next_arg": named(got.get("next_arg"), props), "price": named(got.get("price"), first), "stock": named(got.get("stock"), first)}
        if shape["count"] and (isinstance(observation[shape["count"]], bool) or not isinstance(observation[shape["count"]], int)):
            shape["count"] = None
        self.shapes[name] = shape
        self.price_key = self.price_key or shape["price"]
        self.stock_key = self.stock_key or shape["stock"]
        self.trace.append({"kind": "shape", "tool": name, "shape": shape})
        return shape

    def paging(self, name: str, observation: Any) -> tuple[int, int, str, Any] | None:
        observation = _payload(observation)
        shape = self.read_shape(name, observation)
        if not shape or not shape["count"] or not shape["next"] or not shape["next_arg"] or not isinstance(observation, dict):
            return None
        rows, count, value = observation.get(shape["rows"]), observation.get(shape["count"]), observation.get(shape["next"])
        if not isinstance(rows, list) or not rows or isinstance(count, bool) or not isinstance(count, int):
            return None
        if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int))):
            return None
        return count, len(rows), shape["next_arg"], value

    def price_sorted(self, observation: Any) -> bool:
        prices = [self.price_of(i) for i, _ in self.records_in(observation)]
        return len(prices) >= 3 and None not in prices and all(a <= b for a, b in zip(prices, prices[1:]))

    def more_pages(self, name: str, args: dict[str, Any], observation: Any) -> str:
        self.paged_obs = []
        pick = self.brief.get("pick")
        plan = self.paging(name, observation) if pick in ("cheapest", "most", "least") else None
        if pick == "cheapest":
            self.note_search(name, args, observation, plan)
        if not plan:
            return ""
        count, shown, param, value = plan
        given = args.get(param)
        later = given not in (None, 0, 1) if isinstance(given, int) and not isinstance(given, bool) else bool(str(given or "").strip())
        if value is None or later or count <= shown:
            return ""
        if pick == "cheapest" and self.price_sorted(observation):
            return ""
        pages = -(-(count - shown) // shown)
        if pages > 2 or self.pages_read + pages > AUTO_PAGES or self.left() - self.tail() - pages < 12:
            return (f"\n[Kyo] This search matched {count} listings and showed {shown}, in no price order. The pick counts every fitting listing: "
                    f"search with narrower words (the requirement's value) or page on with {param}={_dump(value)}.")
        texts = []
        for _ in range(pages):
            faults: list[str] = []
            call = _shape({**args, param: value}, self.schemas.get(name), "args", faults)
            if faults:
                break
            reply = self.act(name, call)
            if reply is None or self.finished:
                break
            self.pages_read += 1
            seen = reply.get("observation")
            self.observe(name, seen)
            self.paged_obs.append(seen)
            shown_text = self.show(seen)
            self.read_cache[name + _dump(call)] = (self.version, self.step, shown_text)
            texts.append(f"{param}={_dump(value)}: {shown_text}")
            after = self.paging(name, seen)
            if pick == "cheapest":
                self.note_search(name, call, seen, after)
            value = after[3] if after else None
            if value is None:
                break
        self.trace.append({"kind": "pages", "tool": name, "read": len(texts)})
        return ("\n[Kyo read the rest of this search itself, one step a page]\n" + "\n".join(texts)) if texts else ""

    def cheapest_here(self, observations: list[Any]) -> str:
        if self.brief.get("pick") != "cheapest" or not self.price_key:
            return ""
        found = {i for seen in observations for i, _ in self.records_in(seen)}
        rows = [(self.price_of(i), i) for i in found if self.buyable(i) and self.price_of(i) is not None]
        if len(rows) < 2:
            return ""
        return "\n[Kyo] buyable rows here, cheapest first: " + ", ".join(f"{i} ({p:g})" for p, i in sorted(rows)[:6])

    def note_search(self, name: str, args: dict[str, Any], observation: Any, plan: tuple[int, int, str, Any] | None) -> None:
        """Remember a search call for reading on later: its next-page parameter and value (None when it has no further
        page), and, for each listing it shows, that this call showed it first and whether its rows came in price order."""
        mark = name + _dump(args)
        self.page_next[mark] = (plan[2], plan[3]) if plan and plan[3] is not None else None
        ordered = self.price_sorted(observation)
        for ident, _ in self.records_in(observation):
            self.found_in.setdefault(ident, (name, dict(args), mark, ordered))

    def cheaper_further(self) -> str:
        """Under a cheapest pick, at the checkout (the final cart): stores list search rows in no price order, so a cheaper
        fitting listing is often on a later page of the very search that found a cart line. Read on that search (up to 2
        pages, one step each, no model call) and open the cheapest buyable rows of the line's own category priced below
        it (up to 2, one step each), so the check before checkout weighs them among the other listings. Once per line."""
        if self.brief.get("pick") != "cheapest" or not self.price_key or self.cost > SPEND_SOFT:
            return ""
        cat = self.category_key()
        texts: list[str] = []
        done: list[str] = []
        offered: list[str] = []
        for ident in self.cart_ids():
            if ident in self.deep_done or ident in self.gone or self.sold_out(ident):
                continue
            self.deep_done.add(ident)
            source = self.found_in.get(ident)
            price = self.price_of(ident)
            kind = (self.rows.get(ident) or {}).get(cat) if cat else None
            if not source or source[3] or price is None or not isinstance(kind, str):
                continue
            name, args, mark, _ = source
            step = self.page_next.get(mark)
            read: list[str] = []
            new: list[str] = []
            walked = {mark}
            while step and len(read) < 2 and self.deep_steps < DEEP_STEPS and not self.finished and self.left() - self.tail() - 1 >= DEEP_KEEP:
                param, value = step
                faults: list[str] = []
                call = _shape({**args, param: value}, self.schemas.get(name), "args", faults)
                if faults:
                    break
                later = name + _dump(call)
                if later in walked:
                    break
                walked.add(later)
                args = call
                if later in self.page_next:
                    # a page read already (by the agent or by Kyo) costs no step: walk on past it
                    step = self.page_next[later]
                    continue
                reply = self.act(name, call)
                if reply is None:
                    break
                self.deep_steps += 1
                self.pages_read += 1
                seen = reply.get("observation")
                self.observe(name, seen)
                self.note_search(name, call, seen, self.paging(name, seen))
                shown = self.show(seen)
                self.read_cache[later] = (self.version, self.step, shown)
                read.append(f"{param}={_dump(value)}")
                new += [i for i, _ in self.records_in(seen)]
                step = self.page_next.get(later)
            if not read:
                continue
            done.append(ident)
            lines = self.cart_ids()
            cheaper = sorted({(self.price_of(i), i) for i in new if i not in lines and self.buyable(i) and self.price_of(i) is not None
                              and self.price_of(i) < price and (self.rows.get(i) or {}).get(cat) == kind})
            # the pages' rows stay out of the agent's context (cost); the same call made again is answered from read_cache
            texts.append(f"Kyo read {len(read)} more page(s) of the search that found {ident} ({price:g}): {', '.join(read)}, {len(new)} rows.")
            if not cheaper:
                texts.append(f"No buyable row of {ident}'s category there costs less than it.")
                continue
            offered += [i for _, i in cheaper[:6]]
            texts.append(f"Buyable rows of {ident}'s category there that cost less: " + ", ".join(f"{i} ({p:g})" for p, i in cheaper[:6]) + ".")
            room = min(2, DEEP_STEPS - self.deep_steps)
            opened = self.fill_facts([i for _, i in cheaper[:room]], self.tail() + DEEP_KEEP) if room > 0 else []
            self.deep_steps += len(opened)
            if opened:
                texts.append("Kyo opened the cheapest of them (one step each):\n" + "\n".join(opened))
        if not texts:
            return ""
        self.trace.append({"kind": "deeper", "lines": done, "steps": self.deep_steps, "cheaper": offered})
        return "[Kyo read on the searches that found the cart's lines, since the pick is the cheapest and their rows came in no price order]\n" + "\n".join(texts) + "\n"

    def wider_hold(self) -> str:
        if self.wider_held or self.brief.get("pick") != "cheapest" or self.left() < 14 + 2 * len(self.items):
            return ""
        self.wider_held = True
        lines = [f"{i} at {self.price_of(i):g}" for i in self.cart_ids() if self.price_of(i) is not None]
        return (f"Not run yet (no step used). {self.left()} steps are left and the pick is the cheapest. Searches match a listing's title,"
                " so a requirement's value (often only in the attributes) finds few of the fitting listings, and rows come in no price order."
                " Before checking out, run a few more searches for each item under other names for the product (its plain one-word name,"
                " synonyms, words from fitting titles you have seen) and look only at buyable rows priced below the cart's line"
                + (f" ({'; '.join(lines)})" if lines else "") + "; read the attributes of the cheapest such rows, swap in any that fits, then check out.")

    def fill_facts(self, ids: list[str], keep: int) -> list[str]:
        tool = self.facts_tool()
        target = self.single_target(tool)
        if not tool or not target:
            return []
        texts = []
        for ident in [i for i in ids if i in self.rows and i not in self.full and not self.sold_out(i)]:
            if self.left() <= keep or self.finished or self.facts_from.get(tool) is False:
                break
            faults: list[str] = []
            args = _shape({target: ident}, self.schemas.get(tool), "args", faults)
            if faults:
                break
            reply = self.act(tool, args)
            if reply is None:
                break
            seen = reply.get("observation")
            self.observe(tool, seen)
            self.note_view(tool, seen)
            if isinstance(seen, dict) and self.ident(seen):
                self.facts_from[tool] = self.facts_from.get(tool, False) or bool(_fact_block(seen))
            texts.append(f"{ident}: " + self.show(seen)[:1500])
        if texts:
            self.trace.append({"kind": "fill_facts", "n": len(texts)})
        return texts

    def observe(self, name: str, observation: Any) -> str:
        self.absorb(observation)
        lines = self.loose_lines(observation)
        if not lines:
            return ""
        meaning = self.take_note(lines)
        if meaning:
            self.queued.append(f"(seen on {name}) {meaning}")
        return meaning

    def widen(self) -> None:
        tool = self.roles.get("compare")
        schema = self.schemas.get(tool or "") or {}
        props = schema.get("properties") or {}
        target = next((k for k, v in props.items() if isinstance(v, dict) and "array" in _kinds(v)), None)
        if not tool or not target or any(k != target for k in schema.get("required") or []) or self.compare_bare():
            self.widen_singly()
            return
        if self.left() <= 12:
            return
        cap = self.list_room(tool, target) or 4
        ranked = self.item_groups()
        share = max(1, cap // max(1, len(ranked)))
        picks: list[str] = []
        for ids in ranked:
            picks += [i for i in ids if i not in self.full][:share]
        picks = picks[:cap]
        if len(picks) < 2:
            # room a kind with nothing new to open leaves goes to the other kinds
            picks += [i for ids in ranked for i in ids if i not in self.full and i not in picks][:cap - len(picks)]
        if len(picks) < 2:
            return
        faults: list[str] = []
        args = _shape({target: picks}, schema, "args", faults)
        if faults:
            return
        before = len(self.full)
        reply = self.act(tool, args)
        if reply is not None:
            seen = reply.get("observation")
            self.observe(tool, seen)
            self.note_list_result(tool, target, picks, seen)
            self.note_view(tool, seen)
            rows = self.records_in(seen)
            if rows:
                self.facts_from[tool] = self.facts_from.get(tool, False) or any(_fact_block(r) for _, r in rows)
            self.trace.append({"kind": "widen", "ids": picks, "opened": len(self.full) - before})
            if rows and self.facts_from.get(tool) is False:
                self.widen_singly()
                return
            room = self.list_room(tool, target) or 2
            if len(self.full) == before and len(picks) > room and self.left() > 12:
                faults = []
                args = _shape({target: picks[:room]}, schema, "args", faults)
                if not faults:
                    reply = self.act(tool, args)
                    if reply is not None:
                        self.observe(tool, reply.get("observation"))
                        self.note_list_result(tool, target, picks[:room], reply.get("observation"))

    def widen_singly(self) -> None:
        tool = self.facts_tool()
        target = self.single_target(tool)
        if not tool or not target:
            return
        lanes: list[list[str]] = []
        for ids in self.item_groups():
            opened = sum(1 for i in ids if i in self.full)
            pool = [i for i in ids if i not in self.full and self.buyable(i)]
            if self.brief.get("pick") == "cheapest":
                pool.sort(key=lambda i: self.price_of(i) if self.price_of(i) is not None else float("inf"))
            lanes.append(pool[: max(0, min(2, 8 - opened))])
        queue = [lane[k] for k in range(2) for lane in lanes if k < len(lane)]
        self.fill_facts(queue[:5], 22)

    def ready_to_ask(self) -> bool:
        if self.asked or not self.roles.get("ask") or self.msgs_free() <= 0:
            return False
        if self.left() <= 8:
            return False
        opened = len(self.full)
        if opened >= 3 * len(self.items) + 1:
            return True
        return self.step >= max(8, self.max_steps // 4)

    def message_args(self, text: str) -> dict[str, Any] | None:
        name = self.roles.get("ask")
        schema = self.schemas.get(name or "") or {}
        props = schema.get("properties") or {}
        texts = [k for k, v in props.items() if isinstance(v, dict) and "string" in _kinds(v) and "enum" not in v]
        target = next((k for k in schema.get("required") or [] if k in texts), None) or (texts[0] if texts else None)
        if not target:
            return None
        args: dict[str, Any] = {target: text}
        for key in schema.get("required") or []:
            if key not in args:
                spec = props.get(key) or {}
                if isinstance(spec.get("enum"), list) and spec["enum"]:
                    args[key] = spec["enum"][0]
                else:
                    return None
        faults: list[str] = []
        args = _shape(args, schema, "args", faults)
        return None if faults else args

    def interview(self) -> str:
        self.asked = True
        count = self.msgs_free()
        if count <= 0:
            return ""
        self.widen()
        table = self.key_table()
        settled = []
        for number, item in enumerate(self.items, 1):
            settled.append(f"item {number}: {item.name} - settled by the request: " + ("; ".join(item.musts) or "nothing"))
        listing = []
        last = None
        for index, (label, name, carried, values) in enumerate(table, 1):
            if label != last:
                listing.append(f"category {label!r}:")
                last = label
            listing.append(f"  {index}. {name} (on {carried}): " + " | ".join(values))
        prompt = PLAN.replace("COUNT", str(count + 1)) + "\n\nREQUEST:\n" + self.request + "\n\nITEMS:\n" + "\n".join(settled)
        first = [str(x) for x in _items(self.brief.get("ask_first")) if str(x).strip()]
        if first:
            prompt += "\n\nASK FIRST (the request asks to be asked about these):\n" + "\n".join(first)
        prompt += "\n\nATTRIBUTE KEYS SEEN:\n" + ("\n".join(listing) or "(no full listing records yet)")
        plan = self.ask_json(prompt, [HEAVY, LIGHT], 1800) or {}
        ordered: list[tuple[int, str]] = []
        for pick in _items(plan.get("ask")):
            if not isinstance(pick, dict):
                continue
            number = min(max(1, _count(pick.get("item") or 1) or 1), len(self.items))
            label = re.split(r"\s+(?:and|or)\s+|[/,;(]", str(pick.get("label") or ""))[0].strip().rstrip("?.")
            if not label or len(label.split()) > 5:
                continue
            if self.settles(number, label):
                # the request already gives this property for that item: its answer cannot be a held-back need
                self.trace.append({"kind": "ask_skip", "why": "stated", "item": number, "label": label})
                continue
            if all(_words(label) != _words(other) for n, other in ordered if n == number):
                ordered.append((number, label))
        self.trace.append({"kind": "plan", "ask": _clip(plan.get("ask"), 120)})
        sent: list[tuple[int, str, str]] = []
        told: list[str] = []
        # all messages but the last first; the last goes to the next pick
        head = ordered[: count - 1] if count >= 2 else ordered[:count]
        batch = self.send([(number, label, self.question(number, label)) for number, label in head])
        if not batch:
            return ""
        sent += batch
        heard = self.hear(batch)
        self.take_heard(heard, told)
        pick = self.last_pick(head[: len(batch)], ordered[len(head):], heard) if count >= 2 and self.msgs_free() > 0 else None
        if pick:
            number, label = pick
            batch = self.send([(number, label, self.question(number, label))])
            if batch:
                sent += batch
                self.take_heard(self.hear(batch, (LIGHT, HEAVY)), told)
        if told:
            self.version += 1
        lines = [f"Q: {q}\nA: {a}" for _, q, a in sent]
        summary = "Kyo's interviewer asked the shopper (each question used one step):\n" + "\n".join(lines)
        summary += "\nNew firm requirements from these answers: " + ("; ".join(told) if told else "none")
        summary += ". Apply them to every pick (search again with the new values where needed)."
        pointed = [need for _, need in self.refs if any(need in t for t in told)]
        if pointed:
            summary += (" These take their value from another listing: " + " | ".join(pointed) + ". Find that listing, open its page in full,"
                        " and open every listing its page refers to; the last page gives the value, and the order counts only after all of them are opened.")
        if self.queued:
            summary += "\n[notes seen meanwhile] " + " | ".join(self.queued)
            self.queued = []
        return summary

    def question(self, number: int, label: str) -> str:
        return f"What {label} would you like for the {self.items[number - 1].name}?"

    def settles(self, number: int, label: str) -> bool:
        """The request already states this property for that item (the label's words are among the property's)."""
        want = _stem(label)
        for must in self.items[number - 1].musts:
            prop = _stem(must.split(":")[0]) if ":" in must else frozenset()
            if want and prop and want <= prop:
                return True
        return False

    def heard_prop(self, number: int, label: str) -> bool:
        """The label asks again about a need already heard for that item, or about a property the shopper does not mind."""
        want = _stem(label)
        item = self.items[number - 1]
        for said in item.told + item.free:
            prop = _stem(re.split(r"\s+of\s+", said.split(":")[0])[0])
            if want and prop and (want == prop or (len(want) >= 2 and want <= prop) or (len(prop) >= 2 and prop <= want)):
                return True
        return False

    def last_pick(self, asked: list[tuple[int, str]], rest: list[tuple[int, str]], heard: dict[str, Any]) -> tuple[int, str] | None:
        """The last message, chosen after the batch's answers were read (no model call, no extra step)."""
        done = {(n, _stem(l)) for n, l in asked}
        # "one question at a time" to a label of several words: the same property once more, by its last word alone
        for index in (_count(x) for x in _items(heard.get("crowded"))):
            if not index or not 1 <= index <= len(asked):
                continue
            number, label = asked[index - 1]
            item = self.items[number - 1]
            words = [w for w in _words(label).split() if w.isalpha() and len(w) >= 3]
            if len(words) < 2 or item.told or _stem(words[-1]) & (_stem(item.name) | _stem(item.shelf or "")) or (number, _stem(words[-1])) in done:
                continue
            self.trace.append({"kind": "ask_pick", "why": "one_word", "item": number, "label": words[-1], "was": label})
            return number, words[-1]
        left = [(n, l) for n, l in rest if (n, _stem(l)) not in done and not self.heard_prop(n, l)]
        fresh = [(n, l) for n, l in left if not self.items[n - 1].told]
        pick = (fresh or left or [None])[0]
        if rest and pick != rest[0]:
            self.trace.append({"kind": "ask_pick", "why": ("open_item" if fresh else "not_heard") if pick else "none_left",
                               "item": pick[0] if pick else None, "label": pick[1] if pick else None, "was": rest[0][1]})
        return pick

    def send(self, questions: list[tuple[int, str, str]], floor: int = 6) -> list[tuple[int, str, str]]:
        tool = self.roles["ask"]
        sent: list[tuple[int, str, str]] = []
        for number, _, text in questions:
            if self.finished or self.left() <= floor or self.msg_used >= self.msg_limit:
                break
            args = self.message_args(text)
            if not args:
                break
            reply = self.act(tool, args)
            if reply is None:
                break
            self.msg_used += 1
            answer = reply.get("observation")
            words = self.spoken(answer)
            sent.append((number, text, words))
            self.done_log.append(f"step {self.step}: message to the shopper {text!r} -> reply {words[:300]!r} (cart then: {self.cart_mark()})")
            self.done_steps.append(self.step)
            self.trace.append({"kind": "ask", "q": text, "a": words[:300]})
            if isinstance(answer, dict) and answer.get("error"):
                break
        return sent

    def take_heard(self, heard: dict[str, Any], told: list[str]) -> None:
        many = len(self.items) > 1
        for entry in _items(heard.get("needs")):
            if not isinstance(entry, dict) or not str(entry.get("need") or "").strip():
                continue
            number = min(max(1, _count(entry.get("item")) or 1), len(self.items))
            need = str(entry["need"]).strip()
            if need not in self.items[number - 1].told:
                self.items[number - 1].told.append(need)
                told.append(f"item {number}: {need}" if many else need)
            if entry.get("points") is True and (number, need) not in self.refs:
                self.refs.append((number, need))
        for entry in _items(heard.get("drop")):
            if isinstance(entry, dict) and str(entry.get("property") or "").strip():
                item = self.items[min(max(1, _count(entry.get("item")) or 1), len(self.items)) - 1]
                gone = _words(str(entry["property"]).split(":")[0])
                hit = [m for m in item.musts + item.told if m not in item.dropped and _words(m.split(":")[0]) == gone]
                item.dropped.extend(hit)
                told.extend(f"dropped {m}" for m in hit)
        for entry in _items(heard.get("free")):
            if isinstance(entry, dict) and entry.get("property"):
                number = min(max(1, _count(entry.get("item")) or 1), len(self.items))
                self.items[number - 1].free.append(str(entry["property"]))
        if isinstance(heard.get("budget"), (int, float)) and not isinstance(heard.get("budget"), bool) and heard["budget"] > 0:
            self.budget = heard["budget"]

    def hear(self, sent: list[tuple[int, str, str]], models: tuple[str, ...] = (HEAVY, LIGHT)) -> dict[str, Any]:
        prompt = HEAR + "\n\nITEMS:\n" + "\n".join(f"item {n}: {it.name}" for n, it in enumerate(self.items, 1))
        prompt += "\n\nQUESTIONS AND ANSWERS:\n" + "\n".join(f"{i}. (about item {n}) Q: {q}\nA: {a}" for i, (n, q, a) in enumerate(sent, 1))
        return self.ask_json(prompt, list(models), 1500) or {}

    def gate(self, stage: str) -> tuple[bool, str]:
        steps = [p for p in self.process if p["when"] == stage]
        if not steps or self.finished or not self.gate_due(stage):
            return True, ""
        ending = {self.roles.get("buy"), self.roles.get("refuse")} - {None}
        tools = [f"- {t['function']['name']}: {t['function'].get('description', '')} | parameters: {_dump(t['function'].get('parameters') or {})}"
                 for t in self.tools if t["function"]["name"] not in ending]
        said: list[str] = []
        nudged = False
        for _ in range(GATE_ROUNDS):
            prompt = (GATE.replace("STAGE", "place the order" if stage == "order" else "end without a purchase")
                      + "\n\nREQUEST:\n" + self.request + "\n\nSTEPS DUE NOW:\n" + "\n".join(f"- {p['step']}" for p in steps)
                      + "\n\nLEDGER:\n" + self.ledger() + "\n\nCART NOW: " + self.cart_text()
                      + "\n\nRECORD (messages and step calls so far):\n" + ("\n".join(f"{i}. {line}" for i, line in enumerate(self.done_log, 1)) or "(nothing yet)")
                      + ("\n\nSTORE NOTES SEEN:\n" + "\n".join(self.notes[-4:]) if self.notes else "")
                      + f"\n\nMESSAGES LEFT: {max(0, self.msg_limit - self.msg_used)}   STEPS LEFT: {self.left()} (the {'order' if stage == 'order' else 'ending'} itself takes one)"
                      + "\n\nTOOLS:\n" + "\n".join(tools))
            got = self.ask_json(prompt, [HEAVY, LIGHT] if nudged else [LIGHT, HEAVY], 2000)
            if got is None:
                break
            told: list[str] = []
            hold = ""
            if said:
                self.take_heard({"needs": got.get("needs")}, told)
                hold = str(got.get("hold") or "").strip()
            call = got.get("call") if isinstance(got.get("call"), dict) else None
            self.trace.append({"kind": "gate", "stage": stage, "call": _clip(call, 200), "steps": _clip(got.get("steps"), 120), "hold": hold[:200], "told": told})
            if told or hold:
                self.version += 1
                return False, ("Before going on, Kyo did the steps the request asks for:\n" + "\n".join(said) + "\n" if said else "") + (
                    "The shopper's reply changes the task: " + "; ".join(told + ([hold] if hold else [])) + ". Fix the cart for it, then check out again.")
            name = str((call or {}).get("tool") or "")
            shown = [e for e in _items(got.get("steps")) if isinstance(e, dict)]
            talk = stage == "order" and any(p["messages"] > 0 for p in steps)
            lines = range(1, len(self.done_log) + 1)
            proof = {i for i in lines if not talk or (i <= len(self.done_steps) and self.done_steps[i - 1] > self.cart_at)}
            unproven = [e for e in shown if e.get("done") is not True or not any((_count(n) or 0) in proof for n in _items(e.get("lines")))]
            if not call and unproven and not said and not nudged and self.roles.get("ask") and self.msg_used < self.msg_limit and self.left() >= 2:
                nudged = True
                self.trace.append({"kind": "gate_unproven", "steps": _clip(unproven, 120)})
                self.done_log.append(f"(Kyo: no line made since the cart last changed at step {self.cart_at} shows " + "; ".join(str(e.get("step") or "") for e in unproven)[:200]
                                     + f" done, and {self.msg_limit - self.msg_used} message(s) and {self.left()} steps are left: give the call that does it)")
                self.done_steps.append(-1)
                continue
            if not call or name not in self.schemas or name in ending:
                if not call:
                    self.gate_ok.add((stage, self.cart_mark() + f"#{self.version}"))
                break
            if self.left() < 2 or (name == self.roles.get("ask") and self.msg_used >= self.msg_limit):
                break
            faults: list[str] = []
            args = _shape(call.get("args") if isinstance(call.get("args"), dict) else {}, self.schemas[name], "args", faults)
            if faults:
                break
            if name == self.roles.get("ask"):
                text = next((v for v in args.values() if isinstance(v, str)), "")
                batch = self.send([(1, "", text)], 1)
                if not batch:
                    break
                self.gate_msgs += 1
                said.append(f"Q: {text}\nA: {batch[0][2]}")
                continue
            reply = self.act(name, args)
            if reply is None:
                break
            seen = reply.get("observation")
            self.absorb(seen)
            self.done_log.append(f"step {self.step}: {name} {_dump(args)} -> {self.show(seen)[:300]} (cart then: {self.cart_mark()})")
            self.done_steps.append(self.step)
            said.append(f"{name} {_dump(args)} -> {self.show(seen)[:400]}")
        return True, ("Before going on, Kyo did the steps the request asks for:\n" + "\n".join(said)) if said else ""

    def spoken(self, observation: Any) -> str:
        if isinstance(observation, str):
            return observation
        found: list[str] = []

        def walk(node: Any, depth: int) -> None:
            if depth > 4:
                return
            if isinstance(node, str) and len(node.split()) >= 2:
                found.append(node)
            elif isinstance(node, dict):
                for value in node.values():
                    walk(value, depth + 1)
            elif isinstance(node, list):
                for value in node:
                    walk(value, depth + 1)

        walk(observation, 0)
        return " ".join(found)[:800] if found else _dump(observation)[:400]

    def loose_lines(self, observation: Any) -> list[str]:
        lines: list[str] = []
        if isinstance(observation, dict) and not self.ident(observation):
            for key, value in observation.items():
                if isinstance(value, str) and len(value.split()) >= 5:
                    lines.append(value)
                elif isinstance(value, list) and value and all(isinstance(v, str) for v in value):
                    lines.extend(v for v in value if len(v.split()) >= 5)
                elif isinstance(value, dict) and not self.ident(value, False, 1):
                    for inner in value.values():
                        if isinstance(inner, str) and len(inner.split()) >= 6:
                            lines.append(inner)
        return [line for line in lines if line not in self.heard]

    def take_note(self, lines: list[str]) -> str:
        self.heard.update(lines)
        prompt = NOTE + "\n\nITEMS AND REQUIREMENTS NOW:\n" + self.ledger() + "\n\nTHE NOTE:\n" + "\n".join(lines)
        got = self.ask_json(prompt, [LIGHT, SPARE], 1200) or {}
        self.last_note = {}
        gone = [str(g) for g in _items(got.get("gone")) if isinstance(g, (str, int))]
        self.unavailable.update(g for g in gone if g in self.rows)
        self.note_sold = bool(gone) or got.get("sold_out") is True
        if self.note_sold and len(lines) == 1:
            self.sold_lines.update(lines)
        if got.get("kind") not in (None, "change"):
            return ""
        changed = []
        budget = got.get("budget")
        if isinstance(budget, (int, float)) and not isinstance(budget, bool) and budget > 0 and budget != self.budget:
            self.budget = budget
            changed.append(f"budget now {budget}")
        added: set[str] = set()
        drops = [e for e in _items(got.get("drop")) if isinstance(e, dict) and str(e.get("need") or "").strip()]
        adds = [e for e in _items(got.get("add")) if isinstance(e, dict) and str(e.get("need") or "").strip()]

        self.last_note = {"step": self.step, "drops": len(drops), "adds": len(adds), "budget": got.get("budget"), "gone": bool(gone),
                          "sold": self.note_sold, "price": got.get("price_moved") is True}
        for entry in drops:
            item = self.items[min(max(1, _count(entry.get("item")) or 1), len(self.items)) - 1]
            target = str(entry["need"]).strip()
            live = [m for m in item.musts + item.told if m not in item.dropped]
            hit = [m for m in live if m == target]
            if not hit:
                hit = [m for m in live if _words(m.split(":")[0]) == _words(target.split(":")[0])][:1]
            item.dropped.extend(hit or [target])
            changed.append(f"dropped {target}")
        for entry in adds:
            item = self.items[min(max(1, _count(entry.get("item")) or 1), len(self.items)) - 1]
            need = str(entry["need"]).strip()
            if need in item.dropped:
                item.dropped.remove(need)
            if need not in item.musts + item.told:
                item.told.append(need)
            added.add(need)
            changed.append(f"added {need}")
        if gone:
            changed.append("unavailable: " + ", ".join(gone))
        if got.get("price_moved") is True:
            changed.append("a price changed")
        summary = str(got.get("summary") or "").strip()
        if changed or summary:
            self.version += 1
            self.recent = []
            self.notes.append(summary or "; ".join(changed))
        return (summary + (" (" + "; ".join(changed) + ")" if changed else "")).strip()

    def needs_now(self) -> list[tuple[int, str]]:
        self.shelf_musts()
        out = []
        for number, item in enumerate(self.items, 1):
            for need in item.musts + item.told:
                if need not in item.dropped:
                    out.append((number, need))
        return out

    # ---------- reference chains ----------
    def chain_state(self) -> dict[str, Any]:
        state = self.__dict__.get("_chains")
        if state is None:
            state = self.__dict__["_chains"] = {"said": {}, "opens": 0, "tried": set(), "pages": {}}
        return state

    def chain_index(self) -> dict[tuple[str, str], list[str]]:
        """Name values of the seen listings: {(key, value): ids}."""
        names: dict[tuple[str, str], list[str]] = {}
        for ident in self.seen_order:
            for pair in _one_word_names(self.rows.get(ident) or {}, self.id_key):
                names.setdefault(pair, []).append(ident)
        return names

    def chain_known(self, ids: list[str]) -> dict[str, set[str]]:
        """The attribute values the candidates (one shop's listings) show, per attribute: a value one sibling shows and
        the text names, while another sibling shows a different one, tells them apart."""
        known: dict[str, set[str]] = {}
        for ident in ids:
            for key, value in (_fact_block(self.full.get(ident) or {}) or {}).items():
                value = str(value).strip()
                if 3 <= len(value) <= 40 and not re.search(r"\d", value):
                    known.setdefault(_words(key), set()).add(value)
        return known

    def chain_names(self, text: str, skip: list[str], names: dict[tuple[str, str], list[str]], pool: list[str] | None = None) -> list[str]:
        """Seen listings a pointer text names by a one-word name value, case-sensitive (the smallest matching group);
        the names of `skip` (the page the text is on) do not count."""
        own = {v for i in skip for _, v in _one_word_names(self.rows.get(i) or {}, self.id_key)}
        groups = [[i for i in ids if i not in skip] for (key, value), ids in names.items()
                  if value not in own and _phrase_in(value, text, case=True)]
        groups = [ids for ids in groups if ids]
        if not groups:
            return []
        least = min(len(ids) for ids in groups)
        found: list[str] = []
        for ids in groups:
            if len(ids) == least:
                found += [i for i in ids if i not in found and (pool is None or i in pool)]
        return found

    def chain_match(self, ident: str, text: str, known: dict[str, set[str]], prop: str = "") -> tuple[list[str], list[str]]:
        """(attribute values of the listing that the text names, attributes the text gives another value) - a number
        is never a conflict (unit conversions), a named number is a match."""
        block = _fact_block(self.full.get(ident) or self.rows.get(ident) or {}) or {}
        head = _stem(re.split(r"\s+of\s+", prop.strip(), maxsplit=1)[0]) if prop else frozenset()
        figures = set(re.findall(r"\d+(?:\.\d+)?", text))
        hits, clash = [], []
        for key, value in block.items():
            value, name = str(value).strip(), _words(key)
            if not value or len(value) > 60 or (prop and (_names(_stem(prop), _stem(key)) or _names(head, _stem(key)))):
                continue
            numbers = re.findall(r"\d+(?:\.\d+)?", value)
            keyed = _phrase_in(name, text)
            # a value the text names after its own key ("pack size 1 piece") weighs 2, a bare value 1
            mark = ("+" if keyed else "") + f"{name}={value}"
            if numbers:
                if all(n in figures for n in numbers) and (keyed or _phrase_in(value, text)):
                    hits.append(mark)
                continue
            if _phrase_in(value, text):
                hits.append(mark)
            elif _phrase_in(name, text) or any(v != value and _phrase_in(v, text) for v in known.get(name, ())):
                clash.append(f"{name}={value}")
        return hits, clash

    def chain_sentence(self, ident: str, prop: str) -> str:
        """The sentence on a chain page that sends the property on to another listing, or ""."""
        record = self.rows.get(ident) or {}
        names = {v for _, v in _one_word_names(record, self.id_key)}
        stems = _chain_stem(prop)
        head = _chain_stem(re.split(r"\s+of\s+", prop.strip(), maxsplit=1)[0])
        for key, value in record.items():
            if key == self.id_key or not isinstance(value, str) or len(value.split()) < 6:
                continue
            for sentence in re.split(r"(?<=[.;!?])\s+", value):
                have = _chain_stem(sentence)
                if not ((stems and stems <= have) or (head and head <= have)):
                    continue
                if any(re.fullmatch(r"[A-Z][a-z]{2,29}", w) and w not in names for w in _chain_words(sentence)[1:]):
                    return sentence.strip()
        return ""

    def chain_walk(self, need: str, names: dict[tuple[str, str], list[str]]) -> dict[str, Any]:
        """Follow one reference need through the opened pages: chain pages, the open frontier and its candidates."""
        prop = need.split(":", 1)[0].strip()
        text, pages, unsure = need, [], {}
        for _ in range(8):
            cands = self.chain_names(text, pages[-1:], names)
            known = self.chain_known(cands)
            scored = [(i,) + self.chain_match(i, text, known, prop) for i in cands]
            good = [s for s in scored if s[0] in self.opened and s[1] and not s[2]]
            if not good:
                return {"pages": pages, "text": text, "cands": scored, "end": False, "unsure": unsure}
            ranked = sorted(good, key=lambda s: -_chain_score(s[1]))
            page, top = ranked[0][0], _chain_score(ranked[0][1])
            if page in pages:
                break
            pages.append(page)
            # the named listing for sure: it beats every other opened listing of that shop, and either none is left
            # unread or it shows two values under their own keys
            rest = [s[0] for s in scored if s[0] not in self.opened and not self.sold_out(s[0])]
            tied = len(ranked) > 1 and _chain_score(ranked[1][1]) >= top
            if tied or (rest and top < 4):
                unsure[page] = rest or [s[0] for s in ranked[1:]]
            nxt = self.chain_sentence(page, prop)
            if not nxt:
                return {"pages": pages, "text": text, "cands": [], "end": True, "unsure": unsure}
            text = nxt
        return {"pages": pages, "text": text, "cands": [], "end": False, "unsure": unsure}

    def chain_open(self, walk: dict[str, Any], observation: Any, names: dict[tuple[str, str], list[str]]) -> str:
        """Open the one unopened listing of the frontier's shop that the newest result shows (one step)."""
        state = self.chain_state()
        tool = self.roles.get("offer") or self.roles.get("open")
        target = self.single_target(tool)
        if walk["end"] or not tool or not target or state["opens"] >= 3 or self.finished or self.left() <= self.tail() + 6:
            return ""
        shown = [i for i, _ in self.records_in(observation)]
        fresh = [i for i in self.chain_names(walk["text"], walk["pages"][-1:], names, shown) if i not in self.opened]
        if len(fresh) != 1 or fresh[0] in state["tried"] or self.sold_out(fresh[0]):
            return ""
        ident = fresh[0]
        state["tried"].add(ident)
        faults: list[str] = []
        args = _shape({target: ident}, self.schemas.get(tool), "args", faults)
        if faults:
            return ""
        reply = self.act(tool, args)
        if reply is None:
            return ""
        state["opens"] += 1
        seen = reply.get("observation")
        self.observe(tool, seen)
        self.note_view(tool, seen)
        self.trace.append({"kind": "chain_open", "id": ident, "text": walk["text"][:200]})
        return f"[Kyo opened {ident}, the one listing of the shop a reference points at in that result (one step)] " + self.show(seen)[:1500]

    def chain_hint(self, observation: Any) -> str:
        """After each of the actor's calls: the state of every pending reference chain, said again only when it changed."""
        live = {need for _, need in self.needs_now()}
        pending = [need for _, need in self.refs if need in live and need not in self.ref_values]
        if not pending or self.finished:
            return ""
        state = self.chain_state()
        names = self.chain_index()
        out = []
        for need in pending[:3]:
            walk = self.chain_walk(need, names)
            if not walk["end"] and not any(s[0] in self.opened and s[1] and not s[2] for s in walk["cands"]):
                opened = self.chain_open(walk, observation, names)
                if opened:
                    out.append(opened)
                    names = self.chain_index()
                    walk = self.chain_walk(need, names)
            state["pages"][need] = list(walk["pages"])
            prop = need.split(":", 1)[0].strip()
            if walk["end"] and not walk["unsure"]:
                line = (f"[reference chain for {prop}] complete: " + " -> ".join(walk["pages"])
                        + f". The last page ({walk['pages'][-1]}) gives the {prop} (or the rule that turns it into the value).")
            elif walk["end"]:
                page, rest = next(iter(walk["unsure"].items()))
                line = (f"[reference chain for {prop}] probably " + " -> ".join(walk["pages"]) + f", but {page} is not certain: "
                        + "listings of the same shop not opened yet: " + ", ".join(rest[:6])
                        + ". The listing meant is the one whose page shows every value named; open those before relying on the value.")
            elif not walk["pages"] and not walk["cands"]:
                if not any(re.fullmatch(r"[A-Z][a-z]{2,29}", w) for w in _chain_words(need)[1:]):
                    continue
                line = f"[reference chain for {prop}] no listing of the shop it names has been seen yet: search for that shop's listing with the values it names, then open its page."
            else:
                done = (" -> ".join(walk["pages"]) + " (opened). ") if walk["pages"] else ""
                bad = [f"{i} ({'; '.join(c[:2])})" for i, h, c in walk["cands"] if i in self.opened and c]
                weak = [i for i, h, c in walk["cands"] if i in self.opened and not c and not h]
                rows = [i for i, h, c in walk["cands"] if i not in self.opened and not self.sold_out(i)]
                line = f"[reference chain for {prop}] {done}Next: the listing named by \"{walk['text'][:300]}\"."
                if bad:
                    line += " Opened listings of that shop that are NOT it (their page shows another value): " + ", ".join(bad[:4]) + "."
                if weak:
                    line += " Opened, none of the named values shown: " + ", ".join(weak[:4]) + "."
                if rows:
                    line += " Same-shop listings seen but not opened yet: " + ", ".join(rows[:6]) + "."
                line += " The right one is the page that shows the values named; open it and follow what its page says for this property."
            if state["said"].get(need) != line:
                state["said"][need] = line
                out.append(line)
        return "\n".join(out)

    def evidence(self, observation: Any) -> str:
        chain = self.chain_hint(observation)
        found = self.facts_proof(observation)
        return "\n".join(t for t in (chain, found) if t)

    def facts_proof(self, observation: Any) -> str:
        ids: list[str] = []

        def walk(node: Any, depth: int) -> None:
            if depth > 6:
                return
            if isinstance(node, dict):
                ident = self.ident(node, False, depth)
                if ident and _fact_block(node) and ident not in ids:
                    ids.append(ident)
                    return
                for value in node.values():
                    walk(value, depth + 1)
            elif isinstance(node, list):
                for value in node:
                    walk(value, depth + 1)

        walk(observation, 0)
        needs = self.needs_now()
        if not ids or not needs:
            return ""
        many = len(self.items) > 1
        lines = []
        for ident in ids[:12]:
            block = _fact_block(self.full.get(ident) or {}) or {}
            parts = []
            for number, need in needs[:8]:
                prop = need.split(":", 1)[0].strip()
                named = [(k, v) for k, v in block.items() if _names(_stem(prop), _stem(k))]
                # word requirements only: a number requirement keeps v2b's line (no live evidence for numbers)
                twins = [] if re.search(r"\d", need.partition(":")[2]) else _twin_keys(named)
                # stable: the twin keys first (no change of order when there are none)
                named.sort(key=lambda kv: kv[0] not in twins)
                hits = [f"{k}={str(v)[:120 if k in twins else 50]}" for k, v in named]
                tag = f"(item {number}) " if many else ""
                if hits:
                    parts.append(f"{tag}{prop} -> " + ", ".join(hits[:max(3, len(twins))])
                                 + (f" ({' and '.join(twins)} are one property: a word value is met when any of them states it)" if twins else ""))
            if parts:
                lines.append(f"{ident}: " + "; ".join(parts))
        if not lines:
            return ""
        return "[evidence: keys whose names contain a requirement's property; one naming a different property (another part or aspect) decides nothing, and a key with another name may still hold the same property] " + " | ".join(lines)

    def cart_text(self) -> str:
        if self.cart_view is not None and self.cart_seen_at >= self.cart_at:
            return _dump(_clip(self.cart_view, 300))[:3000]
        return "lines by Kyo's record of the cart calls (listing: units): " + _dump(self.cart_lines)

    def cart_ids(self) -> list[str]:
        if self.cart_view is not None and self.cart_seen_at >= self.cart_at:
            text = _dump(self.cart_view)
            return [i for i in self.rows if i in text]
        return list(self.cart_lines)

    def record_of(self, ident: str) -> str:
        record = self.full.get(ident) or self.rows.get(ident)
        return _dump(_clip(record, 400))[:3000] if record else "(no record seen)"

    def others(self, skip: list[str], limit: int = 30) -> str:
        lines = []
        order = list(reversed(self.seen_order))
        if self.brief.get("pick") == "cheapest":
            order.sort(key=lambda i: (i not in self.full, self.price_of(i) if self.price_of(i) is not None else float("inf")))
        for ident in order:
            if ident in skip or self.sold_out(ident):
                continue
            record = self.full.get(ident) or self.rows.get(ident)
            lines.append(_dump(_clip(record, 160))[:900])
            if len(lines) >= limit:
                break
        return "\n".join(lines)

    def check_key(self, ids: list[str]) -> str:
        return "|".join(sorted(ids)) + f"#{self.version}"

    def check_cart(self, ids: list[str] | None = None, limit: float = SPEND_SOFT) -> str:
        lead = ids is not None
        ids = ids if lead else self.cart_ids()
        key = self.check_key(ids)
        if key in self.checked or self.cost > limit or not ids:
            return ""
        self.checked.add(key)
        prompt = CHECK + "\n\nREQUEST:\n" + self.request + "\n\nREQUIREMENTS IN FORCE:\n" + self.ledger()
        if lead:
            quantity = "; ".join(f"item {n}: quantity {it.qty}" for n, it in enumerate(self.items, 1))
            prompt += "\n\nCART (planned, judge these listings as if they were carted at the requested quantities: " + quantity + "):\n" + ", ".join(ids)
        else:
            prompt += "\n\nCART:\n" + self.cart_text()
        prompt += "\n\nRECORDS OF THE CART'S LISTINGS:\n" + "\n".join(f"{i}: " + ("SOLD OUT (the store says it can no longer be bought). " if self.sold_out(i) else "") + self.record_of(i) for i in ids)
        if self.brief.get("pick") in ("cheapest", "most", "least"):
            prompt += "\n\nOTHER LISTINGS SEEN (newest first):\n" + self.others(ids, 15)
        got = self.ask_json(prompt, [HEAVY, LIGHT], 1500)
        self.trace.append({"kind": "check", "cart": ids, "got": got})
        self.verdicts[key] = bool(got) and got.get("ok") is not False
        if not got or got.get("ok") is not False:
            return ""
        self.leads = [i for i in self.leads if i not in ids]
        problems = [str(p) for p in _items(got.get("problems"))][:5]
        better = [str(b) for b in _items(got.get("better")) if str(b) in self.rows and not self.sold_out(str(b))][:4]
        text = "A careful review says this cart is not right yet: " + "; ".join(problems or ["see the requirements"])
        if better:
            text += ". Listings that look better: " + ", ".join(better)
        return text + ". Fix the cart (or show the review is wrong by re-reading the records), then check out."

    def trail(self) -> tuple[str, bool]:
        live = {need for _, need in self.needs_now()}
        pending = [need for _, need in self.refs if need in live and need not in self.ref_values]
        tool = self.roles.get("offer") or self.roles.get("open")
        target = self.single_target(tool)
        seen: list[str] = []
        lost: list[str] = []
        while pending and self.trails < 4 and self.cost < SPEND_HARD:
            self.trails += 1
            records = []
            for ident in reversed(self.seen_order):
                record = (self.full.get(ident) or self.rows.get(ident)) if ident in self.opened else None
                if record:
                    records.append("OPENED " + _dump(_clip(record, 300))[:1400])
                else:
                    records.append("ROW " + _dump(_clip(self.rows.get(ident), 80))[:300])
                if len(records) >= 60:
                    break
            prompt = TRAIL + "\n\nREQUIREMENTS WITH A VALUE ON ANOTHER LISTING:\n" + "\n".join(pending)
            prompt += "\n\nRECORDS (newest first):\n" + "\n".join(records)
            got = self.ask_json(prompt, [LIGHT, HEAVY], 1800) or {}
            self.trace.append({"kind": "trail", "pending": pending, "got": _clip(got, 150)})
            reach: list[str] = []
            lost = []
            for chain in _items(got.get("chains")):
                if not isinstance(chain, dict):
                    continue
                need = next((p for p in pending if p == str(chain.get("need") or "").strip()), None) or (pending[0] if len(pending) == 1 else None)
                if not need:
                    continue
                links = [l for l in _items(chain.get("links")) if isinstance(l, dict)]
                ids = [str(l.get("id") or "").strip() for l in links]
                if chain.get("done") is True and links and all(i in self.opened for i in ids) and str(chain.get("value") or "").strip():
                    self.ref_values[need] = str(chain["value"]).strip()
                    self.version += 1
                    continue
                closed = [i for i in ids if i in self.rows and i not in self.opened]
                if closed:
                    reach += [i for i in closed if i not in reach]
                else:
                    about = next((str(l.get("about") or "") for l, i in zip(links, ids) if i not in self.rows), "") or "the listing it points at"
                    lost.append(f"{need} -> find {about}")
            pending = [p for p in pending if p not in self.ref_values]
            if not reach or not tool or not target or self.left() < len(reach) + 4 or self.finished:
                break
            for ident in reach[: max(0, min(3, 6 - len(seen)))]:
                faults: list[str] = []
                args = _shape({target: ident}, self.schemas.get(tool), "args", faults)
                if faults:
                    break
                reply = self.act(tool, args)
                if reply is None or self.finished:
                    break
                self.observe(tool, reply.get("observation"))
                seen.append(f"{ident}: " + self.show(reply.get("observation"))[:1500])
        text = ""
        if seen:
            text += "[Kyo opened the pages a requirement points at]\n" + "\n".join(seen) + "\n"
        if self.ref_values:
            text += "[values read from the pages requirements point at] " + "; ".join(f"{k} -> {v}" for k, v in self.ref_values.items()) + "\n"
        hold = bool(lost) and self.trail_blocks < 2 and self.left() > 5
        if hold:
            self.trail_blocks += 1
            text += ("The order counts only after every page a requirement points at has been opened in full (a search row is not enough), following each page that refers to a further listing. Still to find and open: "
                     + " | ".join(lost[:3]) + ". Search for it by its shop, brand or words, open it, apply the value its page gives, then check out.")
        return text, hold

    def offer_tool(self) -> str | None:
        return self.roles.get("offer") or self.roles.get("open")

    def reread_offers(self) -> str:
        tool = self.offer_tool()
        target = self.single_target(tool)
        if not tool or not target:
            return ""
        since = max(self.step - 2, self.refused_at)
        stale = [i for i in self.cart_ids() if self.offer_seen.get(i, -99) < since and i not in self.gone]
        if not stale or self.left() < len(stale) + 3:
            return ""
        lines = []
        for ident in stale:
            faults: list[str] = []
            args = _shape({target: ident}, self.schemas.get(tool), "args", faults)
            if faults:
                break
            before = dict(self.rows.get(ident) or {})
            reply = self.act(tool, args)
            if reply is None or self.finished:
                break
            observation = reply.get("observation")
            self.offer_seen[ident] = self.step
            self.observe(tool, observation)
            after = self.rows.get(ident) or {}
            moved = [k for k, v in after.items() if k in before and before[k] != v and not isinstance(v, (dict, list))]
            if moved:
                lines.append(f"{ident} changed ({', '.join(moved[:4])}): {_dump(_clip(observation, 300))[:900]}")
        self.trace.append({"kind": "reread", "ids": stale, "changed": len(lines)})
        if lines:
            self.version += 1
        return "\n".join(lines)

    def sold_out(self, ident: str) -> bool:
        return ident in self.unavailable or ident in self.gone

    def swap_hint(self) -> str:
        lost = [i for i in self.cart_ids() if i not in self.gone and self.sold_out(i)]
        if not lost:
            return ""
        for ident in lost:
            self.gone[ident] = self.step
        self.leads = [i for i in self.leads if i not in lost]
        self.version += 1
        picks = self.replacements(lost)
        text = f"[Kyo] Sold out now: {', '.join(lost)} (the store shows it cannot be bought). It will not come back, so do not open it again."
        if picks and self.left() <= 6:
            return text + f" Few steps are left: in this turn add {picks[0]} at the requested quantity and remove the sold-out line (two calls), then check out. Other listings already read that appear to fit: {', '.join(picks[1:]) or 'none'}."
        if picks and self.brief.get("pick") == "cheapest":
            return text + f" Listings already read that appear to fit that item instead, cheapest first: {', '.join(picks)}. The pick rule is the cheapest, so unless you have already seen the whole fitting set, run one search under {picks[0]}'s price (the search's maximum price, if it has one) before you swap the sold-out line for the cheapest fitting listing."
        if picks:
            return text + f" Listings already read that appear to fit that item instead: {', '.join(picks)}. In this turn take the sold-out line out of the cart and add {picks[0]} at the requested quantity, then check out."
        return text + " Remove that line from the cart and add the best other listing that fits; search for one if none you have read fits."

    def find_sold(self) -> str:
        ids = [i for i in self.cart_ids() if i not in self.gone]
        if any(self.sold_out(i) for i in ids):
            return ""
        if len(ids) == 1:
            self.unavailable.add(ids[0])
            return ""
        return self.reread_offers() if ids else ""

    def replacements(self, lost: list[str]) -> list[str]:
        if self.cost > SPEND_SOFT:
            return []
        records = []
        for ident in reversed(self.seen_order):
            if ident in lost or ident in self.gone or self.sold_out(ident):
                continue
            records.append(_dump(_clip(self.full.get(ident) or self.rows.get(ident), 200))[:1200])
            if len(records) >= 25:
                break
        if not records:
            return []
        prompt = SWAP + "\n\nREQUEST:\n" + self.request + "\n\nREQUIREMENTS IN FORCE:\n" + self.ledger()
        prompt += "\n\nSOLD-OUT CART LINE:\n" + "\n".join(f"{i}: {self.record_of(i)}" for i in lost) + "\n\nCART NOW:\n" + self.cart_text()
        prompt += "\n\nOTHER LISTING RECORDS SEEN (newest first):\n" + "\n".join(records)
        got = self.ask_json(prompt, [HEAVY, LIGHT], 1200)
        fits: list[tuple[float, str]] = []
        for entry in _items((got or {}).get("fits")):
            ident = str(entry.get("id") if isinstance(entry, dict) else entry)
            price = entry.get("price") if isinstance(entry, dict) else None
            if ident in self.rows and ident not in lost and ident not in self.gone and ident not in self.cart_ids() and ident not in [i for _, i in fits]:
                fits.append((float(price) if isinstance(price, (int, float)) and not isinstance(price, bool) else float("inf"), ident))
        ranked = [i for _, i in sorted(fits, key=lambda f: f[0])] if self.brief.get("pick") == "cheapest" else [i for _, i in fits]
        self.trace.append({"kind": "swap", "lost": lost, "fits": fits})
        return ranked[:4]

    def audit(self) -> str:
        # one review per state of the requirements in force (a told need, a drop, a budget or stock note makes a new state),
        # at most two an episode; the light model reviews, so a late review is affordable too
        if self.audits >= 2 or self.audit_version == self.version or self.cost > SPEND_HARD - 0.01:
            return ""
        self.audited = True
        self.audits += 1
        self.audit_version = self.version
        got = self.audit_call()
        named = self.audit_fits(got)
        if not named:
            # rows whose page was never read can still fit: open the promising ones the steps allow and look again
            rows = [str(i) for i in _items((got or {}).get("open")) if str(i) in self.rows and str(i) not in self.opened and not self.sold_out(str(i))]
            if rows and self.open_rows(rows):
                got = self.audit_call()
                named = self.audit_fits(got)
        self.unseen = sorted({n for n in (_count(i) for i in _items((got or {}).get("unseen"))) if n and 1 <= n <= len(self.items)})
        if not named:
            return ""
        self.lead_items = named
        self.leads = [i for ids in named.values() for i in ids]
        return "A careful review thinks these listings may fit: " + "; ".join(f"item {k}: {', '.join(v)}" for k, v in named.items()) + (f" ({got.get('reason')})" if got.get("reason") else "") + ". Open them and buy what truly fits; end without a purchase only if each one fails."

    def audit_call(self) -> dict[str, Any] | None:
        records = []
        for ident in reversed(self.seen_order):
            if self.sold_out(ident):
                continue
            record = self.full.get(ident) if ident in self.full else None
            records.append(("OPENED " + _dump(_clip(record, 200))[:1200]) if record else ("ROW " + _dump(_clip(self.rows.get(ident), 120))[:500]))
            if len(records) >= 30:
                break
        if not records:
            return None
        prompt = AUDIT + "\n\nREQUEST:\n" + self.request + "\n\nREQUIREMENTS IN FORCE:\n" + self.ledger()
        prompt += "\n\nLISTING RECORDS SEEN (newest first):\n" + "\n".join(records)
        # the light model reasons before it answers: give it room (at 1500 tokens it answered 0 of 9 reviews in a paid pair)
        got = self.ask_json(prompt, [LIGHT], 4000)
        if got is None and self.cost <= SPEND_SOFT and not self.broke and not self.no_credit and self.calls < ALL_CALLS:
            got = self.ask_json(prompt, [HEAVY], 1500)
        self.trace.append({"kind": "audit", "got": got})
        return got

    def audit_fits(self, got: dict[str, Any] | None) -> dict[str, list[str]]:
        fits = (got or {}).get("fits")
        if not isinstance(fits, dict):
            return {}
        named: dict[str, list[str]] = {}
        for k, v in fits.items():
            key = str(k)
            if not _count(key):
                word = key.strip().lower()
                key = next((str(n) for n, it in enumerate(self.items, 1) if word and word in (it.name.strip().lower(), it.shelf.strip().lower())), key)
            named.setdefault(key, []).extend(str(i) for i in _items(v) if str(i) in self.rows and not self.sold_out(str(i)))
        named = {k: list(dict.fromkeys(v))[:4] for k, v in named.items()}
        return {k: v for k, v in named.items() if v}

    def lead_plan(self) -> dict[str, int] | None:
        """The basket the review's leads make, read the same way complete_cart reads them: one lead per requested item at
        its quantity, plus the cart's lines of the kinds no lead covers; None when some requested item would have no line."""
        cat_key = self.category_key()

        def kind(ident: str) -> str:
            return str((self.rows.get(ident) or {}).get(cat_key) or "").strip().lower() if cat_key else ident

        plan: dict[str, int] = {}
        for number, ids in self.lead_items.items():
            index = _count(number)
            pick = next((i for i in ids if not self.sold_out(i) and i not in plan), None)
            if pick and index and 1 <= index <= len(self.items):
                plan[pick] = self.items[index - 1].qty
        keep = {i: self.cart_lines.get(i, 1) for i in self.cart_ids() if i not in plan and not self.sold_out(i) and kind(i) not in {kind(p) for p in plan}}
        if not plan or len(plan) + len({kind(i) for i in keep}) < len(self.items):
            return None
        return {**keep, **plan}

    def confirm_leads(self) -> str | None:
        """One independent check of the review's whole basket (lead_plan) as the planned cart; the first lead in it when the
        check passes, else None. A basket that leaves a requested item without a line is not checked: it cannot pass."""
        self.confirm_at = self.audit_version
        plan = self.lead_plan()
        if not plan:
            return None
        ids = list(plan)
        self.check_cart(ids, SPEND_HARD)
        if not self.verdicts.get(self.check_key(ids)):
            return None
        return next((i for i in ids if i in self.leads), None)

    def open_rows(self, rows: list[str]) -> bool:
        """Open listings seen only as search rows, as many as the steps allow (at most 6, keeping the cart, the checkout and a
        few more steps free): side by side in the group size the store takes when that view shows attributes, else one by one."""
        many, joiner = self.compare_target(), self.roles.get("compare")
        tool = self.facts_tool()
        target = self.single_target(tool)
        room = min(6, len(rows), self.left() - len(self.items) - 4)
        if room < 1:
            return False
        rows = rows[:room]
        if many and joiner and not self.compare_bare():
            size = max(1, self.compare_room())
            plan = [(joiner, {many: rows[i:i + size]}) for i in range(0, len(rows), size)]
        elif tool and target:
            plan = [(tool, {target: i}) for i in rows]
        else:
            return False
        if self.left() < len(plan) + 5:
            return False
        before = len(self.full)
        for name, args in plan:
            faults: list[str] = []
            args = _shape(args, self.schemas.get(name), "args", faults)
            if faults:
                return False
            reply = self.act(name, args)
            if reply is None or self.finished:
                break
            self.observe(name, reply.get("observation"))
            for arg in _list_args(self.schemas.get(name)):
                self.note_list_result(name, arg, args.get(arg), reply.get("observation"))
        self.trace.append({"kind": "audit_open", "rows": rows, "opened": len(self.full) - before})
        return len(self.full) > before

    def cart_calls(self, lines: dict[str, int], drop: list[str]) -> list[dict[str, Any]] | None:
        name = self.roles.get("cart") or ""
        schema = self.schemas.get(name) or {}
        props = schema.get("properties") or {}
        for key, spec in props.items():
            shape = spec.get("items") if isinstance(spec, dict) and "array" in _kinds(spec) else None
            if isinstance(shape, dict) and isinstance(shape.get("properties"), dict):
                inner = shape["properties"]
                id_key = next((k for k, s in inner.items() if isinstance(s, dict) and "string" in _kinds(s) and "enum" not in s), None)
                count_key = next((k for k, s in inner.items() if isinstance(s, dict) and "integer" in _kinds(s)), None)
                if not id_key:
                    return None
                return [{key: [{id_key: i, **({count_key: n} if count_key else {})} for i, n in lines.items()]}]
        texts = [k for k, s in props.items() if isinstance(s, dict) and "string" in _kinds(s) and "enum" not in s]
        target = (next((k for t, k in self.id_args if t == name and k in texts), None)
                  or next((k for k in schema.get("required") or [] if k in texts), None) or (texts[0] if len(texts) == 1 else None))
        count = next((k for k, s in props.items() if isinstance(s, dict) and "integer" in _kinds(s)), None)
        mode = next((k for k, s in props.items() if isinstance(s, dict) and isinstance(s.get("enum"), list) and len(s["enum"]) >= 2), None)
        if not target:
            return None
        calls: list[dict[str, Any]] = []
        for ident in drop:
            have = self.cart_lines.get(ident, 1)
            if mode:
                calls.append({target: ident, mode: props[mode]["enum"][1], **({count: have} if count else {})})
            elif count and self.cart_sets(name):
                calls.append({target: ident, count: 0})
            elif count and isinstance(props[count].get("minimum"), int) and props[count]["minimum"] <= -have:
                calls.append({target: ident, count: -have})
            else:
                return None
        for ident, want in lines.items():
            have = self.cart_lines.get(ident, 0) if ident in self.cart_ids() else 0
            if have == want:
                continue
            if have and not self.cart_sets(name):
                return None
            calls.append({target: ident, **({mode: props[mode]["enum"][0]} if mode else {}), **({count: want} if count else {})})
        return calls

    def complete_cart(self) -> str:
        """The agent ends without buying although the independent check confirmed a reviewed basket: Kyo carts the reviewed
        lines itself (one per item, keeping cart lines of the other items) and checks out, when a fresh check passes that
        cart. A line that sells out on the way (a store can sell out the line just carted) is replaced by the next lead of
        its item and the basket checked again, three tries at most; a review newer than the last confirm gets its own."""
        cart, buy = self.roles.get("cart"), self.roles.get("buy")
        if not cart or not buy or self.finished:
            return ""
        # a confirm is spent once per review, not per episode: leads from a newer review get one independent check
        if self.audits and self.leads and self.confirm_at != self.audit_version and (not self.confirmed or self.completed):
            first = self.confirm_leads()
            if first:
                self.confirmed, self.completed = first, False
                self.trace.append({"kind": "refuse_blocked", "confirmed": first, "basket": ", ".join(self.lead_plan() or {first: 1}), "rearmed": True})
        if self.completed or not self.confirmed:
            return ""
        self.completed = True
        faults: list[str] = []
        buy_args = _shape(dict(self.brief.get("buy_args") or {}), self.schemas.get(buy), "args", faults)
        if faults:
            return ""
        done: list[str] = []
        replies: list[str] = []
        tried: list[dict[str, int]] = []
        for _ in range(3):
            lines = self.lead_plan()
            # the same basket is tried again only once (after a refusal that sold nothing out)
            if not lines or tried.count(lines) >= 2:
                break
            tried.append(dict(lines))
            drop = [i for i in self.cart_ids() if i not in lines]
            calls = self.cart_calls(lines, drop)
            if calls is None or len(calls) + 1 > self.left():
                break
            # acting costs no model call; a basket the checks have not passed yet gets one check, up to the hard spend cap
            self.fill_facts(list(lines), len(calls) + 3)
            self.check_cart(list(lines), SPEND_HARD)
            if not self.verdicts.get(self.check_key(list(lines))) or self.finished:
                break
            carted = True
            for args in calls:
                shape_faults: list[str] = []
                args = _shape(args, self.schemas.get(cart), "args", shape_faults)
                if shape_faults:
                    carted = False
                    break
                reply = self.act(cart, args)
                if reply is None or self.finished:
                    carted = False
                    break
                self.note_cart(cart, args)
                self.read_cart_reply(reply.get("observation"))
                self.observe(cart, reply.get("observation"))
                done.append(_dump(args))
            if not carted:
                break
            go, said = self.gate("order")
            if said:
                replies.append(said)
            if not go or self.finished or self.left() < 1:
                break
            lost = [i for i in lines if self.sold_out(i)]
            if lost:
                # the record of a freshly carted line turned to sold out: the next lead of that item takes its place
                replies.append("sold out after carting: " + ", ".join(lost))
                continue
            reply = self.act(buy, buy_args)
            self.trace.append({"kind": "completed", "lines": lines, "drop": drop, "reply": _clip(reply, 200)})
            if reply is None:
                break
            self.buys += 1
            if not reply.get("finished"):
                self.refused_at = self.step
            observation = reply.get("observation")
            self.note_sold = False
            self.observe(buy, observation)
            replies.append(self.show(observation))
            if self.finished or reply.get("finished"):
                break
            # refused: a sell-out marks its line (a lone line is the one; several are re-read), else re-read the lines once
            if self.note_sold or any(line in self.spoken(observation) for line in self.sold_lines):
                self.find_sold()
            else:
                self.reread_offers()
        if not done and not replies:
            return ""
        head = ("Not run (Kyo acted instead): the independent check confirmed the review's basket, so Kyo set the cart ("
                + ("; ".join(done) or "it already held those lines") + ")")
        if self.finished:
            return head + " and checked out. Store reply: " + " | then: ".join(replies)
        return (head + " and tried to check out, but NO order was placed. Store replies: " + (" | then: ".join(replies) or "none")
                + "\nCart now: " + self.cart_text())

    def recheckout(self, args: dict[str, Any]) -> str:
        """The store refused a checkout with a note that cannot break this cart: it only drops requirements or sets a budget
        the cart's total still meets; nothing added, sold out or repriced. When the pick rule is not cheapest, most or least
        and the newest independent check of exactly these lines passed, the cart still fits: Kyo sends the same checkout
        again (after the steps the request asks for at the order)."""
        note = self.last_note
        buy = self.roles.get("buy")
        if not buy or not note or note.get("step") != self.step or self.note_sold:
            return ""
        if note.get("adds") or note.get("gone") or note.get("sold") or note.get("price"):
            return ""
        budget = note.get("budget")
        budget = budget if isinstance(budget, (int, float)) and not isinstance(budget, bool) and budget > 0 else None
        ids = self.cart_ids()
        if not (note.get("drops") or budget) or not ids or self.brief.get("pick") in ("cheapest", "most", "least") or self.left() < 2:
            return ""
        if any(self.sold_out(i) for i in ids):
            return ""
        if budget is not None:
            prices = [self.price_of(i) for i in ids]
            if any(p is None for p in prices) or sum(p * max(1, self.cart_lines.get(i, 1)) for p, i in zip(prices, ids)) > budget:
                return ""
        mark = "|".join(sorted(ids)) + "#"
        seen = sorted((int(k[len(mark):]), v) for k, v in self.verdicts.items() if k.startswith(mark) and k[len(mark):].lstrip("-").isdigit())
        if not seen or not seen[-1][1]:
            return ""
        go, said = self.gate("order")
        if not go or self.finished or self.left() < 1:
            return ("[Kyo] " + said) if said else ""
        reply = self.act(buy, args)
        self.trace.append({"kind": "recheckout", "cart": ids, "note": dict(note), "reply": _clip(reply, 200)})
        if reply is None:
            return ""
        self.buys += 1
        if not reply.get("finished"):
            self.refused_at = self.step
        self.observe(buy, reply.get("observation"))
        return ("[Kyo] The refusal only " + ("dropped a requirement" if note.get("drops") else "set a budget the cart still meets")
                + ", which cannot make the checked cart fail, so Kyo checked out the same cart again. Store reply: "
                + self.show(reply.get("observation")) + (" [episode finished]" if self.finished or reply.get("finished") else ""))

    def is_buy(self, name: str, args: dict[str, Any]) -> bool:
        if name != self.roles.get("buy"):
            return False
        fixed = self.brief.get("buy_args") if isinstance(self.brief.get("buy_args"), dict) else {}
        return all(args.get(k) == v for k, v in fixed.items())

    def is_refuse(self, name: str, args: dict[str, Any]) -> bool:
        if name != self.roles.get("refuse"):
            return False
        fixed = self.brief.get("refuse_args") if isinstance(self.brief.get("refuse_args"), dict) else {}
        return all(args.get(k) == v for k, v in fixed.items())

    def offered(self) -> list[dict[str, Any]]:
        left = self.left()
        ask = self.roles.get("ask")
        keep: set[str] | None = None
        ends = {self.roles.get("buy"), self.roles.get("refuse")} - {None}
        if left <= self.tail():
            keep = set(ends)
        elif left <= self.tail() + 3:
            keep = set(ends) | {self.roles.get("cart"), self.roles.get("cart_view")}
        elif left <= len(self.items) + 5 and self.buys == 0:
            keep = set(ends) | {self.roles.get("cart"), self.roles.get("cart_view"), self.roles.get("offer")}
        tools = [t for t in self.tools if t["function"]["name"] != ask]
        if keep is not None and ends:
            narrowed = [t for t in tools if t["function"]["name"] in keep]
            tools = narrowed or tools
        return tools

    def quiet(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        schema = self.schemas.get(name) or {}
        props = schema.get("properties") or {}
        out = dict(args)
        for key, spec in props.items():
            if not isinstance(spec, dict) or "string" not in _kinds(spec) or "enum" in spec:
                continue
            value = out.get(key)
            if value is None and key not in (schema.get("required") or []):
                continue
            text = str(value or "")
            named = any(ident in text for ident in self.rows) or self.brief.get("quiet_decline") is not False
            if named or not text:
                out[key] = "Sorry, nothing in the store meets all of your requirements, so I am not buying anything."[: spec.get("maxLength", 200)]
        return out

    def id_shaped(self, value: str) -> bool:
        """Whether a word looks like the store's listing ids: a length seen among them and their common start."""
        ids = list(self.rows)
        if not ids:
            return False
        start = ids[0]
        for ident in ids[1:]:
            while start and not ident.startswith(start):
                start = start[:-1]
        return len(value) in {len(i) for i in ids} and value.startswith(start[:3])

    def id_keys(self, name: str) -> list[str]:
        """Arguments of this tool that take listing ids: the single listing of the page views, the list of the side-by-side
        view, the cart's one free argument, and any argument a call was seen carrying ids in."""
        if name in {self.roles.get(r) for r in ("search", "ask", "buy", "refuse")} - {None}:
            return []
        props = (self.schemas.get(name) or {}).get("properties") or {}
        free = [k for k, v in props.items() if isinstance(v, dict) and ("string" in _kinds(v) or "array" in _kinds(v)) and "enum" not in v]
        keys = [k for k in free if (name, k) in self.id_args]
        if name == self.roles.get("cart") and len(free) == 1:
            keys.append(free[0])
        if name in (self.roles.get("open"), self.roles.get("offer")) and self.single_target(name):
            keys.append(self.single_target(name) or "")
        if name == self.roles.get("compare") and self.compare_target():
            keys.append(self.compare_target() or "")
        return [k for k in dict.fromkeys(keys) if k]

    def resolve_ids(self, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """A listing given by its title, or by a cut or padded copy of its id, where a tool takes listing ids: use the id
        when one seen listing matches; otherwise say what is wrong, so no step is spent on a call the store cannot match."""
        self.id_dropped = []
        if not self.id_key or len(self.rows) < 3:
            return args, ""
        keys = self.id_keys(name)
        if not keys:
            return args, ""

        def fix(value: Any) -> tuple[Any, str]:
            if not isinstance(value, str) or not value.strip():
                return value, ""
            word = value.strip()
            if word in self.rows:
                return word, ""
            if not _id_like(word, True) and len(word) >= 8:
                low = word.lower()
                hits = [i for i, row in self.rows.items() if any(k != self.id_key and isinstance(v, str) and v.strip().lower().startswith(low) for k, v in row.items())]
                if len(hits) == 1:
                    return hits[0], ""
                if hits:
                    return value, f"several listings carry the text {value!r} ({', '.join(hits[:6])}); pass one listing id"
                return value, f"{value!r} is not a listing id; pass the id from the result rows (their {self.id_key} field)"
            # a copy of a seen id with characters lost or added
            near = [i for i in self.rows if len(word) >= 5 and (i.startswith(word) or word.startswith(i) or word in i)]
            if len(near) == 1:
                return near[0], ""
            # an id a result named without showing its row
            if word in self.id_words and self.id_shaped(word):
                return word, ""
            return value, f"{value!r} is not the id of any listing shown so far; pass the {self.id_key} value of a result row (search for the listing first)"

        out = dict(args)
        for key in keys:
            if key not in args:
                continue
            fixed = [fix(v) for v in args[key]] if isinstance(args[key], list) else [fix(args[key])]
            problem = next((p for _, p in fixed if p), "")
            if problem and isinstance(args[key], list) and any(not p for _, p in fixed):
                # a list keeps the entries the store can match; the others are named in the result
                self.id_dropped += [p for _, p in fixed if p]
                fixed = [(v, p) for v, p in fixed if not p]
                problem = ""
            if problem:
                return args, problem
            out[key] = [v for v, _ in fixed] if isinstance(args[key], list) else fixed[0][0]
        return out, ""

    def cart_sets(self, name: str) -> bool:
        props = self.schemas.get(name, {}).get("properties") or {}
        if any(isinstance(s, dict) and isinstance(s.get("enum"), list) and len(s["enum"]) >= 2 for s in props.values()):
            return False
        return any(isinstance(s, dict) and "integer" in _kinds(s) and s.get("minimum") == 0 for s in props.values())

    def note_cart(self, name: str, args: dict[str, Any]) -> None:
        self.cart_touched = True
        self.cart_at = self.step
        spec = self.schemas.get(name, {}).get("properties") or {}
        removal = False
        for key, value in args.items():
            options = (spec.get(key) or {}).get("enum")
            if isinstance(options, list) and len(options) >= 2 and value in options[1:]:
                removal = True
        loose_count = next((_count(v) for v in args.values() if _count(v) is not None and not isinstance(v, str)), None)
        lines: list[tuple[str, int | None]] = []
        whole = False
        for key, value in args.items():
            if isinstance(value, list):
                shape = (spec.get(key) or {}).get("items") or {}
                if not value and isinstance(shape, dict) and (shape.get("type") == "object" or "properties" in shape):
                    whole = True
                for line in value:
                    if isinstance(line, dict):
                        whole = True
                        ident = next((v for v in line.values() if isinstance(v, str) and v in self.rows), None)
                        count = next((_count(v) for v in line.values() if _count(v) is not None and not isinstance(v, str)), 1)
                        if ident:
                            lines.append((ident, count))
                    elif isinstance(line, str) and line in self.rows:
                        lines.append((line, loose_count))
            elif isinstance(value, str) and value in self.rows:
                lines.append((value, loose_count))
        if whole:
            self.cart_lines = {i: c for i, c in lines if c and c > 0}
            return
        sets = self.cart_sets(name)
        for ident, count in lines:
            have = self.cart_lines.get(ident, 0)
            if removal:
                if count:
                    have = have - count
                elif count is None and self.count_arg(name):
                    # a count argument left out takes its default, one piece
                    have = have - 1
                else:
                    have = 0
            elif sets:
                have = count if count is not None else 1
            else:
                have = have + (count if count is not None else 1)
            if have > 0:
                self.cart_lines[ident] = have
            else:
                self.cart_lines.pop(ident, None)

    def count_arg(self, name: str) -> str | None:
        """The cart tool's optional count argument, if it has one."""
        schema = self.schemas.get(name) or {}
        props = schema.get("properties") or {}
        return next((k for k, s in props.items() if isinstance(s, dict) and "integer" in _kinds(s) and k not in (schema.get("required") or [])), None)

    def read_cart_reply(self, observation: Any) -> None:
        """A cart tool (or cart view) that answers with the whole cart: its lines replace Kyo's own record of the cart calls,
        once the key holding a line's count is known (learned from a reply that agrees with the record)."""
        found: list[Any] = []

        def walk(node: Any, depth: int, key: str | None) -> None:
            if found or depth > 3:
                return
            if isinstance(node, list):
                rows = [r for r in node if isinstance(r, dict)]
                lines = [(self.ident(r, True), r) for r in rows]
                if rows and len(rows) == len(node) and all(i and i in self.rows for i, _ in lines):
                    found.append((key, lines))
                elif not node and key is not None and key == self.cart_list_key:
                    found.append((key, []))
            elif isinstance(node, dict):
                for k, v in node.items():
                    walk(v, depth + 1, k)

        walk(observation, 0, None)
        if not found:
            return
        key, lines = found[0]
        if self.qty_key is None and lines:
            ints = [k for k in lines[0][1] if all(isinstance(r.get(k), int) and not isinstance(r.get(k), bool) for _, r in lines)]
            match = [k for k in ints if all(r[k] == self.cart_lines.get(i) for i, r in lines)]
            if len(match) == 1:
                self.qty_key = match[0]
        if self.qty_key is None or (key != self.cart_list_key and self.cart_list_key is not None):
            return
        if not all(isinstance(r.get(self.qty_key), int) and not isinstance(r.get(self.qty_key), bool) for _, r in lines):
            return
        self.cart_list_key = key
        self.cart_lines = {i: r[self.qty_key] for i, r in lines if r[self.qty_key] > 0}
        self.cart_from_reply = True

    def show(self, observation: Any) -> str:
        text = _dump(_clip(observation, SHOW_CHARS))
        if len(text) > OBS_LIMIT:
            text = text[:OBS_LIMIT] + "...(cut)"
        return text

    def compare_target(self) -> str | None:
        schema = self.schemas.get(self.roles.get("compare") or "") or {}
        props = schema.get("properties") or {}
        target = next((k for k, v in props.items() if isinstance(v, dict) and "array" in _kinds(v)), None)
        if not target or any(k != target for k in schema.get("required") or []):
            return None
        return target

    def compare_room(self) -> int:
        """How many listings one side-by-side call may carry (see list_room)."""
        return self.list_room(self.roles.get("compare") or "", self.compare_target() or "") or 4

    def join_opens(self, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        opener, joiner, target = self.roles.get("open"), self.roles.get("compare"), self.single_target(self.roles.get("open"))
        many = self.compare_target()
        if not opener or not joiner or not target or not many or opener == joiner:
            return calls
        if self.compare_bare():
            return calls
        picks: list[tuple[int, str]] = []
        for index, call in enumerate(calls):
            fn = call.get("function") or {}
            args = _json_obj(fn.get("arguments")) if isinstance(fn.get("arguments"), str) else None
            ident = str((args or {}).get(target) or "").strip()
            if fn.get("name") == opener and args and set(args) == {target} and ident in self.rows and ident not in self.gone:
                picks.append((index, ident))
        picks = picks[: self.compare_room()]
        if len(picks) < 2:
            return calls
        first = picks[0][0]
        out = []
        for index, call in enumerate(calls):
            if index == first:
                out.append({"id": call["id"], "type": "function", "function": {"name": joiner, "arguments": _dump({many: [i for _, i in picks]})}})
            elif index in {i for i, _ in picks}:
                out.append({"id": call["id"], "joined": True})
            else:
                out.append(call)
        self.trace.append({"kind": "joined", "ids": [i for _, i in picks]})
        return out

    def run_calls(self, calls: list[dict[str, Any]]) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        calls = self.join_opens(calls)
        for index, call in enumerate(calls):
            allowed = {t["function"]["name"] for t in self.offered()}
            cid = call["id"]
            if call.get("joined"):
                out.append((cid, "Shown in the side-by-side result above: Kyo opened these listings together in one step."))
                continue
            fn = call.get("function") or {}
            name = fn.get("name")
            raw = fn.get("arguments")
            if self.finished:
                out.append((cid, "Not run: the episode is over."))
                continue
            if name == self.roles.get("ask"):
                out.append((cid, "Not run (no step used): Kyo's interviewer handles every message to the shopper."))
                continue
            if name not in self.schemas:
                out.append((cid, f"Not run (no step used): unknown tool. Tools: {', '.join(sorted(allowed))}."))
                continue
            if name not in allowed:
                out.append((cid, "Not run (no step used): too few steps are left for that; use: " + ", ".join(sorted(allowed)) + "."))
                continue
            if isinstance(raw, dict):
                args = raw
            else:
                args = _json_obj(raw) if (raw or "").strip() else {}
                if args is None:
                    out.append((cid, "Not run (no step used): the arguments were not one JSON object."))
                    continue
            trimmed = ""
            for arg in _list_args(self.schemas[name]):
                room = self.list_room(name, arg, None)
                if room and isinstance(args.get(arg), list) and len(args[arg]) > room:
                    trimmed += f"\n[Kyo] Sent the first {room} listings only: this store takes at most {room} per call. Not shown yet: {', '.join(map(str, args[arg][room:]))}."
                    args = {**args, arg: args[arg][:room]}
            faults: list[str] = []
            # a decline's text is replaced by Kyo's own sentence anyway, so only it may be cut
            args = _shape(args, self.schemas[name], "args", faults, cut=name == self.roles.get("refuse"))
            if faults:
                out.append((cid, "Not run (no step used): " + "; ".join(faults[:6])))
                continue
            args, wrong = self.resolve_ids(name, args)
            if wrong:
                out.append((cid, "Not run (no step used): " + wrong + "."))
                continue
            if self.id_dropped:
                trimmed += "\n[Kyo] Left out of this call: " + "; ".join(self.id_dropped[:4]) + "."
            many = self.compare_target() if name == self.roles.get("compare") else None
            target = self.single_target(name)
            if target and name in (self.roles.get("open"), self.roles.get("offer")) and str(args.get(target)) in self.gone:
                out.append((cid, f"Not run (no step used): {args[target]} sold out at step {self.gone[str(args[target])]} and will not come back. Replace its cart line with another fitting listing."))
                continue
            if name == self.roles.get("cart") and any((_count(v) or 0) < 0 for v in args.values() if not isinstance(v, str)):
                view = _dump(self.cart_view) if self.cart_seen_at >= self.cart_at else ""
                absent = [v for v in args.values() if isinstance(v, str) and v in self.rows and v not in self.cart_lines and v not in view and v not in self.cart_said]
                if absent:
                    out.append((cid, f"Not run (no step used): {absent[0]} is not in the cart, so there is nothing to take off. Cart now: " + self.cart_text()))
                    continue
            ending = self.is_buy(name, args) or self.is_refuse(name, args)
            if ending and len(calls) > 1:
                out.append((cid, "Not run (no step used): send the finishing call on its own, after reading your other results."))
                continue
            if not ending and self.left() <= self.tail() and (self.roles.get("buy") or self.roles.get("refuse")):
                out.append((cid, "Not run (no step used): the last steps are kept for checking out (with the shopper's approval of the basket when it is due) or ending without a purchase."))
                continue
            mark = name + _dump(args)
            if not ending and name != self.roles.get("cart") and mark in self.recent:
                out.append((cid, "Not run (no step used): you just made this same call and nothing changed; its result is above."))
                continue
            readers = {self.roles.get(r) for r in ("search", "open", "offer", "compare")} - {None}
            cached = self.read_cache.get(mark)
            if name in readers and cached and cached[0] == self.version:
                out.append((cid, f"Not run (no step used): the same call at step {cached[1]} returned this, and nothing has changed since:\n" + cached[2][:3000]))
                continue
            if target and name in readers and name != self.roles.get("compare") and self.shown_already(name, str(args.get(target))):
                out.append((cid, f"Not run (no step used): {args[target]} has shown everything this view gives since the last change. Its record: " + self.record_of(str(args[target]))))
                continue
            if many and isinstance(args.get(many), list) and args[many]:
                keep = [i for i in args[many] if not self.shown_already(name, str(i))]
                if not keep:
                    out.append((cid, "Not run (no step used): these listings have shown everything this view gives since the last change. Their records:\n"
                                + "\n".join(f"{i}: {self.record_of(str(i))}" for i in args[many])[:4000]))
                    continue
                if len(keep) < len(args[many]):
                    trimmed += f"\n[Kyo] Left out {', '.join(str(i) for i in args[many] if i not in keep)}: shown in full already, nothing changed since."
                    args = {**args, many: keep}
                    mark = name + _dump(args)
            if ending and self.left() > 2:
                if self.is_buy(name, args):
                    wider = self.wider_hold()
                    if wider:
                        out.append((cid, wider + "\nCart now: " + self.cart_text()))
                        continue
                    reread = self.reread_offers()
                    if self.cart_touched and self.cart_seen_at < self.cart_at and self.roles.get("cart_view") and self.left() > 3:
                        faults = []
                        view_args = _shape({}, self.schemas.get(self.roles["cart_view"]), "args", faults)
                        view = self.act(self.roles["cart_view"], view_args) if not faults else None
                        if view is not None:
                            self.cart_view = view.get("observation")
                            self.cart_seen_at = self.step
                            change = self.observe(self.roles["cart_view"], self.cart_view)
                            if change:
                                self.queued = []
                                out.append((cid, "Not run yet (no step used). Looking at the cart showed a change: " + change + "\nCart now: " + self.cart_text() + "\nApply the change, fix the cart if needed, then check out."))
                                continue
                    swap = self.swap_hint()
                    held = [i for i in self.cart_ids() if i in self.gone] if self.held < 2 else []
                    if swap or held:
                        self.held += 0 if swap else 1
                        out.append((cid, "Not run yet (no step used). " + (swap or f"{', '.join(held)} in the cart is sold out: replace that line first.") + "\nCart now: " + self.cart_text()))
                        continue
                    chain, hold = self.trail()
                    if hold:
                        out.append((cid, "Not run yet (no step used). " + chain + "\nCart now: " + self.cart_text()))
                        continue
                    # cheapest pick: read on the searches that found the cart's lines, so the check below weighs their cheaper rows
                    noted = len(self.queued)
                    deeper = self.cheaper_further()
                    if len(self.queued) > noted:
                        # a page read on carried a note that changed something: the agent applies it before any checkout
                        change = " | ".join(self.queued[noted:])
                        del self.queued[noted:]
                        out.append((cid, "Not run yet. A page Kyo read on showed a change: " + change + "\n" + deeper + "Cart now: " + self.cart_text()
                                    + "\nApply the change, fix the cart if needed, then check out."))
                        continue
                    # the check judges attributes: read the cart lines' own
                    read = self.fill_facts(self.cart_ids(), self.tail() + 3)
                    verdict = self.check_cart()
                    if verdict:
                        seen = ("Kyo read these listings' attributes for the check (one step each):\n" + "\n".join(read) + "\n") if read else ""
                        out.append((cid, "Not run yet. " + chain + seen + deeper + verdict + "\nCart now: " + self.cart_text()))
                        continue
                    if reread and self.cost > SPEND_SOFT:
                        out.append((cid, "Not run yet (no step used). Kyo re-read the cart's listings just now:\n" + reread + "\nCheck out again when every line still shows stock and a price inside the budget; otherwise replace that line first."))
                        continue
                else:
                    # with 5 or fewer steps left there is no room for the agent to act on a hold: the review still runs, and a
                    # basket the independent check confirms is carted and checked out by Kyo below (complete_cart)
                    late = self.left() <= 5 or self.elapsed() >= LOOP_STOP - 15
                    review = self.audit()
                    if review and not late:
                        out.append((cid, "Not run yet (no step used). " + review))
                        continue
                    if self.leads and not late and self.refuse_blocks == 0:
                        self.refuse_blocks = 1
                        self.trace.append({"kind": "refuse_blocked", "leads": list(self.leads)})
                        out.append((cid, "Not run yet (no step used). The review found listings that appear to fit: " + ", ".join(self.leads) + ". Open them if needed, put the best fitting one in the cart (respecting the pick rule) and check out. End without a purchase only if each of them clearly fails a requirement; then say which one in your text and send the ending call again."))
                        continue
                    if self.leads and not self.confirmed and (self.refuse_blocks == 1 or (late and self.refuse_blocks == 0)):
                        self.refuse_blocks = 2
                        first = self.confirm_leads()
                        if first:
                            self.confirmed = first
                            basket = ", ".join(self.lead_plan() or {first: 1})
                            self.trace.append({"kind": "refuse_blocked", "confirmed": first, "basket": basket, "late": late})
                            if not late:
                                out.append((cid, f"Not run yet (no step used). An independent check of the review's basket ({basket}) says it meets every requirement. Put those listings in the cart at the requested quantities and check out; end without a purchase only if a record clearly breaks a requirement."))
                                continue
            if self.is_refuse(name, args) and self.left() <= 5 and not self.late_held and not (self.confirmed and not self.completed):
                lines = [i for i in self.built if not self.sold_out(i)]
                fresh = self.cart_view is not None and self.cart_seen_at >= self.cart_at
                missing = [i for i in lines if i not in self.cart_ids() or (i in self.dropped and not fresh)]
                if len(lines) >= len(self.items) and len(missing) + 1 <= self.left():
                    self.late_held = True
                    self.trace.append({"kind": "late_decline_held", "lines": lines, "missing": missing})
                    redo = f"Put {', '.join(missing)} back in the cart at the requested quantities, then check out." if missing else "Check out the cart as it is."
                    out.append((cid, "Not run yet (no step used). Ending without a purchase earns nothing when the store has a fitting listing, and running short of steps does not show that it has none. "
                                + redo + " End without a purchase only if your search showed that some requested item has no listing that meets its requirements; then send the ending call again."))
                    continue
            if self.is_refuse(name, args) and not self.leads and not self.pushed and (self.left() > self.max_steps // 3 or (self.unseen and self.left() >= len(self.items) + 6)):
                self.pushed = True
                unseen = "; ".join(f"item {n} ({self.items[n - 1].name})" for n in self.unseen)
                out.append((cid, f"Not run yet (no step used). {self.left()} steps are still left, so search in ways you have not tried before ending: browse the category of each requested item and page through it with the token or offset the store returns, try single-word value queries and the property's other names, and open the listings that might fit. End without a purchase only after that."
                            + (f" No listing of {unseen} has been seen at all yet: search for it first." if unseen else "")))
                continue
            if self.is_refuse(name, args):
                done = self.complete_cart()
                if done:
                    out.append((cid, done + (" [episode finished]" if self.finished else "")))
                    continue
                args = self.quiet(name, args)
            if ending and self.left() >= 2:
                go, said = self.gate("order" if self.is_buy(name, args) else "end")
                if not go:
                    out.append((cid, "Not run yet. " + said + "\nCart now: " + self.cart_text()))
                    continue
                if said:
                    trimmed = "\n[Kyo] " + said + trimmed
            reply = self.act(name, args)
            if reply is None:
                out.append((cid, "The call failed (network or server). You may try again."))
                continue
            observation = reply.get("observation")
            for arg in _list_args(self.schemas.get(name)):
                ids = args.get(arg)
                if isinstance(ids, list) and len(ids) > 1 and not self.note_list_result(name, arg, ids, observation):
                    trimmed += f"\n[Kyo] {name} showed nothing for these {len(ids)} listings: this store takes at most {self.list_room(name, arg)} per call, so send them in smaller groups."
            self.recent = (self.recent + [mark])[-3:]
            self.id_args.update((name, k) for k, v in args.items() if (v if isinstance(v, list) else [v]) and all(isinstance(x, str) and x in self.rows for x in (v if isinstance(v, list) else [v])))
            self.absorb(observation)
            if name == self.roles.get("compare"):
                rows = self.records_in(observation)
                if rows:
                    self.facts_from[name] = self.facts_from.get(name, False) or any(_fact_block(r) for _, r in rows)
            if name in readers - {self.roles.get("search")}:
                self.note_view(name, observation)
            plain = {tool for job, tool in self.roles.items() if job != "search"}
            paged = self.more_pages(name, args, observation) if name not in plain and not ending else ""
            if self.single_target(name) and name not in (self.roles.get("cart"), self.roles.get("buy"), self.roles.get("refuse"), self.roles.get("ask")):
                listing = self.ident(observation) if isinstance(observation, dict) else None
                if listing:
                    self.facts_from[name] = self.facts_from.get(name, False) or bool(_fact_block(observation))
                    if name == self.roles.get("open") and not self.facts_from[name]:
                        other = next((t for t in self.schemas if t != name and self.single_target(t) and self.facts_from.get(t) is not False
                                      and t not in (self.roles.get("cart"), self.roles.get("buy"), self.roles.get("refuse"), self.roles.get("ask"), self.roles.get("search"))), None)
                        if other:
                            self.roles["open"] = other
                    if not self.facts_from[name] and name != self.roles.get("open") and not self.roles.get("offer"):
                        self.roles["offer"] = name
                    if name == self.offer_tool():
                        self.offer_seen[listing] = self.step
            if name == self.roles.get("cart"):
                self.note_cart(name, args)
                self.read_cart_reply(observation)
                self.cart_said = _dump(observation)
                self.recent = []
                counts = [_count(v) for v in args.values() if not isinstance(v, str) and _count(v) is not None]
                for value in args.values():
                    if counts and isinstance(value, str) and value in self.rows:
                        if counts[0] <= 0 and not _in_rows(observation, value):
                            self.dropped.add(value)
                        elif counts[0] > 0:
                            self.dropped.discard(value)
                lines = [i for i in self.cart_ids() if not self.sold_out(i) and i not in self.dropped]
                if len(lines) >= len(self.built):
                    self.built = lines
            if name == self.roles.get("cart_view"):
                self.cart_view = observation
                self.cart_seen_at = self.step
                self.read_cart_reply(observation)
            if self.is_buy(name, args):
                self.buys += 1
                if not reply.get("finished"):
                    self.refused_at = self.step
            text = self.show(observation) + paged + trimmed
            if name not in plain and not ending:
                text += self.cheapest_here([observation] + self.paged_obs)
            base = text
            proof = self.evidence(observation)
            if proof:
                text += "\n" + proof
            if name == self.roles.get("cart") and any(_count(v) == 0 for v in args.values() if not isinstance(v, str)):
                if any(isinstance(v, str) and v in self.rows and _in_rows(observation, v) for v in args.values()):
                    text += "\n[Kyo] A count of 0 left that line in the cart: this tool adds the count to the line, so a negative count takes units off."
            self.note_sold = False
            lines = self.loose_lines(observation)
            if lines:
                meaning = self.take_note(lines)
                if meaning:
                    text += "\n[note read] " + meaning + ". Apply this change to your picks before checking out."
            if self.is_buy(name, args) and not reply.get("finished") and (self.note_sold or any(line in self.spoken(observation) for line in self.sold_lines)):
                seen = self.find_sold()
                if seen:
                    text += "\n[Kyo re-read the cart's lines after the refusal]\n" + seen
            if self.is_buy(name, args) and not reply.get("finished") and not self.finished:
                again = self.recheckout(args)
                if again:
                    text += "\n" + again
            swap = self.swap_hint()
            if swap:
                text += "\n" + swap
            if self.queued:
                text += "\n[notes seen on Kyo's own calls] " + " | ".join(self.queued)
                self.queued = []
            if name in readers:
                self.read_cache[mark] = (self.version, self.step, base)
            if reply.get("finished"):
                text += " [episode finished]"
            out.append((cid, text))
        return out

    def finish(self, again: bool = False) -> str:
        if self.finished or self.broke or self.left() <= 0:
            return ""
        buy, refuse = self.roles.get("buy"), self.roles.get("refuse")
        # a forced end honours a basket the independent check confirmed: Kyo carts it and checks out (complete_cart)
        if self.confirmed and not self.completed and self.elapsed() < CALL_END:
            done = self.complete_cart()
            if done or self.finished or self.left() <= 0:
                return ""
        fresh = self.cart_view is not None and self.cart_seen_at >= self.cart_at
        holding = bool(self.cart_ids()) if fresh else bool(self.cart_lines)
        # a cart with fewer lines than the request has items cannot pass as an order; an ending without a purchase can
        if holding and len(self.items) > 1 and len(self.cart_ids()) < len(self.items):
            self.trace.append({"kind": "partial_not_bought", "lines": len(self.cart_ids()), "items": len(self.items)})
            holding = False
            fresh = True
        if buy and (holding or (self.cart_touched and not fresh and not self.cart_from_reply and self.left() >= 2)):
            faults: list[str] = []
            args = _shape(dict(self.brief.get("buy_args") or {}), self.schemas.get(buy), "args", faults)
            if not faults:
                if self.left() >= 2:
                    self.gate("order")
                if self.finished or self.left() <= 0:
                    return ""
                reply = self.act(buy, args)
                self.trace.append({"kind": "forced_buy", "reply": _clip(reply, 200)})
                if self.finished or self.left() <= 0:
                    return ""
                if reply is not None and again:
                    self.buys += 1
                    self.refused_at = self.step
                    self.observe(buy, reply.get("observation"))
                    return "the checkout was refused: " + self.show(reply.get("observation"))
        if refuse:
            faults = []
            args = _shape(self.quiet(refuse, dict(self.brief.get("refuse_args") or {})), self.schemas.get(refuse), "args", faults)
            if not faults:
                if self.left() >= 2:
                    self.gate("end")
                if self.finished or self.left() <= 0:
                    return ""
                reply = self.act(refuse, args)
                self.trace.append({"kind": "forced_refuse", "reply": _clip(reply, 200)})
                if reply is not None and not self.finished:
                    self.observe(refuse, reply.get("observation"))
                    return "ending without a purchase was refused: " + self.show(reply.get("observation"))
        return ""

    def trim(self) -> None:
        size = sum(len(_dump(m.get("content"))) for m in self.chat)
        if size <= HISTORY_LIMIT:
            return
        tools = [i for i, m in enumerate(self.chat) if m.get("role") == "tool"]
        # oldest first, down to TRIM_TO in one go, so the history's start stays the same for many turns after a cut; the
        # newest KEEP_RESULTS results stay whole (a share of all results would grow with the episode and cut every turn again)
        for index in tools[: max(1, len(tools) - KEEP_RESULTS)]:
            if size <= TRIM_TO:
                break
            content = self.chat[index].get("content") or ""
            if len(content) > 600:
                ids = re.findall(r'"([A-Za-z0-9][A-Za-z0-9_\-:.]{5,40})"', content)
                ids = [i for i in dict.fromkeys(ids) if i in self.rows][:20]
                short = content[:400] + f"...(older result shortened; listings in it: {', '.join(ids)})"
                size += len(_dump(short)) - len(_dump(content))
                self.chat[index]["content"] = short

    def run(self) -> list[dict[str, Any]]:
        self.started = time.monotonic() - 2
        self.marks: list[tuple[float, float, int]] = []
        if self.finished:
            return self.trace
        self.read_request()
        self.trace.append({"kind": "brief", "brief": self.brief})
        opening = self.view.get("opening")
        if opening is not None:
            self.absorb(opening)
        intro = "SHOPPER'S REQUEST:\n" + self.request
        if opening is not None:
            intro += "\n\nWHAT THE STORE SHOWS FIRST:\n" + self.show(opening)
        intro += "\n\nStart by searching for each item in its category and opening several listings in full, so the interviewer can see which properties these listings carry.\n\n" + self.status()
        self.chat = [{"role": "system", "content": GUIDE}, {"role": "user", "content": intro}]
        self.work(LOOP_CALLS, SPEND_HARD)
        if not self.finished:
            turned = self.finish(again=True)
            if turned and not self.finished and not self.broke and not self.no_credit and self.left() > 1:
                self.chat.append({"role": "user", "content": "[Kyo] Kyo tried to end the episode and " + turned + "\nApply what the store says, then finish.\n" + self.status()})
                self.work(self.loop_calls + 10, SPEND_HARD + 0.01)
            if not self.finished:
                self.finish()
        self.trace.append({"kind": "end", "finished": self.finished, "steps": self.step, "cost": round(self.cost, 5), "calls": self.calls,
                           "elapsed": round(self.elapsed(), 1)})
        return self.trace

    def work(self, loop_cap: int, spend_cap: float) -> None:
        idle = 0
        self.spend_cap = spend_cap
        if getattr(self, "marks", None) is None:
            self.marks = []
        while (not self.finished and not self.broke and self.left() > 0 and self.loop_calls < loop_cap and self.cost < spend_cap
               and self.elapsed() < LOOP_STOP):
            if self.ready_to_ask():
                summary = self.interview()
                if summary:
                    self.chat.append({"role": "user", "content": summary + "\n" + self.status() + self.budget_note()})
                continue
            self.trim()
            self.loop_calls += 1
            self.marks.append((time.monotonic(), self.cost, self.step))
            message = self.think(self.chat, [LIGHT, SPARE], 3000, self.offered())
            if message is None:
                self.misses += 1
                if self.no_credit or self.calls >= ALL_CALLS or self.misses > 2:
                    break
                continue
            calls = []
            for number, call in enumerate(message.get("tool_calls") or []):
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") if isinstance(call.get("function"), dict) else {}
                raw = fn.get("arguments")
                parsed = raw if isinstance(raw, dict) else (_json_obj(raw) if isinstance(raw, str) and raw.strip() else {})
                calls.append({"id": str(call.get("id") or f"k{self.loop_calls}_{number}"), "type": "function",
                              "function": {"name": str(fn.get("name") or ""), "arguments": _dump(parsed if isinstance(parsed, dict) else {})}})
            content = message.get("content")
            if not isinstance(content, str):
                content = _dump(content) if content else ""
            if not calls:
                idle += 1
                self.chat.append({"role": "assistant", "content": content or "(no call)"})
                self.chat.append({"role": "user", "content": "Call one of the tools to continue.\n" + self.status() + self.budget_note()})
                if idle >= 3:
                    break
                continue
            idle = 0
            committing = {self.roles.get("cart"), self.roles.get("buy"), self.roles.get("refuse")} - {None}
            if not self.asked and self.roles.get("ask") and self.msgs_free() > 0 and any(c["function"]["name"] in committing for c in calls) and self.left() > 8:
                self.chat.append({"role": "assistant", "content": content or None, "tool_calls": calls})
                for call in calls:
                    self.chat.append({"role": "tool", "tool_call_id": call["id"], "content": "Not run (no step used): the shopper is asked first."})
                summary = self.interview()
                self.chat.append({"role": "user", "content": (summary or "The interviewer had nothing to ask.") + "\n" + self.status() + self.budget_note()})
                continue
            self.chat.append({"role": "assistant", "content": content or None, "tool_calls": calls})
            self.trace.append({"kind": "turn", "text": content[:300], "calls": [c["function"] for c in calls]})
            replies = self.run_calls(calls)
            for index, (cid, text) in enumerate(replies):
                if index == len(replies) - 1:
                    text += "\n" + self.status() + self.budget_note()
                self.chat.append({"role": "tool", "tool_call_id": cid, "content": text})
        why = ("finished" if self.finished else "broke" if self.broke else "steps" if self.left() <= 0 else "turns" if self.loop_calls >= loop_cap
               else "spend" if self.cost >= spend_cap else "clock" if self.elapsed() >= LOOP_STOP else "other")
        self.trace.append({"kind": "loop_end", "why": why, "elapsed": round(self.elapsed(), 1), "cost": round(self.cost, 5),
                           "turns": self.loop_calls, "steps": self.step})


def agent_main(problem_data: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        episode = Kyo(problem_data)
    except Exception as exc:
        return [{"kind": "crash", "error": f"{type(exc).__name__}: {exc}"[:400]}]
    try:
        return episode.run()
    except Exception as exc:
        episode.trace.append({"kind": "crash", "error": f"{type(exc).__name__}: {exc}"[:400]})
        try:
            if not episode.finished:
                episode.finish()
        except Exception as again:
            episode.trace.append({"kind": "crash", "error": f"{type(again).__name__}: {again}"[:400]})
        return episode.trace


__all__ = ["agent_main"]
