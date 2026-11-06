# Race-14 Starlark World (`s14_r14`, 45 Open Tasks, `w-forge-s14-r14`)
# Reproduces the Race-14 mechanics seen in the 9,945 released open episodes (221 agents x 45 open tasks):
#   * 8 tools: LocateListings, OpenPage, AskBuyer, SetToCart (append|delete, line <= 4), BagList, BuyItem, PassOrder, StatusReport
#   * LocateListings: words = AND over the first 2 tokens (len >= 2, no group filter), BM25 k1 1.1 / b 0 tiers in id order, top 1000,
#     12 rows per page, BeginAtAt 0..95; browse = the whole group id-sorted   (fit: runs/forge2/HANDOVER.md)
#   * 3-message allowance (AskBuyer cost 1, budget 3)
#   * events (4 tasks): the first BuyItem with a cart is refused once; events hit the picked listing (price x factor | sold out);
#     echo events repeat on the next observation as {"hese": <obs>, "hufa": [<sentence>]}
#   * persona: 12 reveal frames, 10 nopref, 10 DNU (dnu_default per task share)
#   * graded: pointer chains opened via OpenPage, hidden needs via AskBuyer, lines / quantities / suhe / jufuli (re-priced per episode)

TEXT_INDEX = "jasu"
CATEGORY_INDEX = "nemogi"
BRAND_INDEX = "kojefe"
PAGE_ROWS = 12
MAX_BEGIN = 95
TEXT_HITS_CAP = 1000  # field counts saturate at 1000
LINE_CAP = 4
ALL_TERMS = True
TOOLS = ["LocateListings", "OpenPage", "AskBuyer", "SetToCart", "BagList", "BuyItem", "PassOrder", "StatusReport"]
UNKNOWN = {"trouble_message": "UNKNOWN"}

def start(envelope):
    params = envelope["params"]
    for name in TOOLS:
        set_cost(name, "steps", 1)
    set_budget("steps", params.get("step_budget", 43))
    msg_cap = params.get("message_budget", 3)
    set_cost("AskBuyer", "messages", 1)
    set_budget("messages", msg_cap)
    state_set("message_budget", msg_cap)
    state_set("events", params.get("events", []))
    state_set("fired", False)
    state_set("first_add_done", False)
    state_set("pending", [])
    state_set("ov_price", {})
    state_set("gone", [])
    state_set("messages_used", 0)
    state_set("questions_used", 0)
    state_set("last_cart_step", 0)
    state_set("last_cart_sig", "")
    state_set("first_hold_step", 0)
    state_set("first_answer_step", 0)
    setup_shopper(params["bezifa"])
    return None

def row_of(item_id):
    return catalog_get(item_id)

def eff_price(row):
    ov = state_get("ov_price", {})
    if row["id"] in ov:
        return ov[row["id"]]
    return row.get("price", 0)

def eff_stock(row):
    if row["id"] in state_get("gone", []):
        return False
    return row.get("in_stock")

def turn():
    return None

def apply_events():
    events = state_get("events", [])
    lines = basket_get()
    sentences = []
    ov = state_get("ov_price", {})
    gone = state_get("gone", [])
    step = counters()["step"]
    pend = state_get("pending", [])
    for i in range(len(events)):
        event = events[i]
        if event.get("at", "finish") != "finish":
            continue
        li = event.get("target_line", 0)
        item = None
        if li < len(lines):
            item = lines[li]["id"]
        if (item == None) and (event.get("needs_target", True)):
            continue
        price_to = None
        if item != None:
            row = row_of(item)
            if event["kind"] == "price":
                base = ov.get(item, row.get("price", 0))
                price_to = int(base * event["factor"] + 0.5)
                ov[item] = price_to
            elif event["kind"] == "stock":
                if item not in gone:
                    gone.append(item)
        ledger_append({"situ": i, "item": item, "kind": event["kind"], "step": step, "price_to": price_to, "silent": False})
        sentences.append(event["sent"])
        if event.get("echo", False):
            pend.append([step, event["sent"]])
    state_set("ov_price", ov)
    state_set("gone", gone)
    state_set("pending", pend)
    state_set("fired", True)
    return sentences

def can_finish(order):
    events = [e for e in state_get("events", []) if e.get("at", "finish") == "finish"]
    if (len(events) == 0) or state_get("fired", False):
        return {"observation": None, "ok": True}
    sentences = apply_events()
    return {"observation": sentences if sentences else None, "ok": not sentences}

def pending_wrap(result):
    pend = state_get("pending", [])
    step = counters()["step"]
    ready = [p for p in pend if p[0] < step]
    if ready:
        state_set("pending", [p for p in pend if p[0] >= step])
        return {"hese": result, "hufa": [p[1] for p in ready]}
    return result

def search_row(row):
    return {
        "brand": row.get("maker"),
        "description": desc_of(row),
        "id": row.get("id"),
        "list_price": eff_price(row),
        "merchant": row.get("merchant"),
        "on_hand": eff_stock(row),
        "product_shelf": row.get("category"),
        "title": row.get("title"),
    }

def desc_of(row):
    text = row.get("description")
    if type(text) != "string":
        return ""
    if len(text) > 1200:
        return text[:1200]
    return text

def full_card(row):
    card = search_row(row)
    card["facts"] = row.get("facts", {})
    card["good_to_know_text"] = row.get("seller_notes_text")
    return card

def text_search_ids(query, group):
    # live race-14 words search (runs/forge2/fit_search.py): the group is NOT a filter (same Words under any GroupName gave the same
    # page on 1,643/1,643 live cases), "-" is not split, tokens shorter than 2 are dropped, only the FIRST 2 tokens are searched (AND),
    # the engine ranks by BM25 k1 1.1 / b 0 (tiers of equal score in id order), top 1000
    query = query.lower()
    for ch in ["(", ")", ",", ".", "/", ":", ";", "|"]:
        query = query.replace(ch, " ")
    tokens = []
    for tok in query.split(" "):
        if (len(tok) >= 2) and (tok not in tokens):
            tokens.append(tok)
    if tokens == []:
        return []
    found = search(TEXT_INDEX, " ".join(tokens[:2]), {"all_terms": ALL_TERMS, "k": TEXT_HITS_CAP})
    if found["ok"] == False:
        return []
    ranked = sorted(found["hits"], key = lambda h: (-h["score"], h["id"]))
    out = []
    for hit in ranked:
        if row_of(hit["id"]) == None:
            continue
        out.append(hit["id"])
    return out[:TEXT_HITS_CAP]

def group_ids(group):
    out = []
    for hit in search(CATEGORY_INDEX, group, {"all_terms": True, "k": 5000}).get("hits", []):
        row = row_of(hit["id"])
        if (row != None) and (type(row.get("category")) == "string") and (row["category"].lower().strip() == group):
            out.append(hit["id"])
    return sorted(out)

def all_ids():
    out = []
    for hit in search(CATEGORY_INDEX, "", {"all_terms": False, "k": 100000}).get("hits", []):
        out.append(hit["id"])
    return sorted(out)

def page_of(ids, begin):
    if begin == None:
        begin = 0
    rows = ids[begin:begin + PAGE_ROWS]
    nxt = begin + PAGE_ROWS
    onward = nxt if ((nxt < len(ids)) and (nxt <= MAX_BEGIN)) else None
    return {
        "listings": [search_row(row_of(i)) for i in rows],
        "next_page_token": onward,
        "num_hits_number": len(ids),
    }

def tool_locate_listings(args):
    how = args.get("HowType", "words")
    group = args.get("GroupName")
    words = args.get("Words")
    if group != None:
        group = str(group).lower().strip()
    if how == "browse":
        ids = group_ids(group) if (group != None) else []
    else:
        if (words == None) or (str(words).strip() == ""):
            ids = group_ids(group) if (group != None) else []
        else:
            ids = text_search_ids(str(words), group)
            if (ids == []) and (group != None):
                ids = text_search_ids(str(words), None)  # field: a GroupName that leaves no hit is dropped (scratch/sf_chain14.py: count equal on +32 of 2983 recorded pages)
    return page_of(ids, args.get("BeginAtAt"))

def tool_open_page(args):
    row = row_of(args.get("ItemId", ""))
    if row == None:
        return {}
    return full_card(row)

def bag_summary():
    lines_out = []
    total = 0
    for line in basket_get():
        row = row_of(line["id"])
        price = eff_price(row)
        total += price * line["quantity"]
        lines_out.append({
            "amount_total": line["quantity"],
            "id": line["id"],
            "list_price": price,
            "title": row.get("title"),
        })
    return {"amount_due": total, "selection_items": lines_out}

def cart_qty(pid):
    for ln in basket_get():
        if ln["id"] == pid:
            return ln["quantity"]
    return 0

def apply_first_add_events(pid):
    if state_get("first_add_done", False):
        return None
    state_set("first_add_done", True)
    events = state_get("events", [])
    ov = state_get("ov_price", {})
    step = counters()["step"]
    for i in range(len(events)):
        event = events[i]
        if event.get("at", "finish") != "first_add":
            continue
        base = ov.get(pid, row_of(pid).get("price", 0))
        scaled = base * event["factor"]
        price_to = int(scaled) if event.get("floor", False) else int(scaled + 0.5)
        ov[pid] = price_to
        ledger_append({"situ": i, "item": pid, "kind": event["kind"], "step": step, "price_to": price_to, "silent": True})
    state_set("ov_price", ov)
    return None

def tool_set_to_cart(args):
    pid = args.get("Listing", "")
    if row_of(pid) == None:
        return UNKNOWN
    have = cart_qty(pid)
    number = args.get("Number")
    if args.get("ActType") == "append":
        add = 1 if number == None else number
        if have + add > LINE_CAP:
            return {"trouble_message": "CAPPED"}
        basket_set(pid, have + add)
        apply_first_add_events(pid)
    else:
        if (number == None) or (number >= have):
            basket_set(pid, 0)
        else:
            basket_set(pid, have - number)
    sig_parts = []
    for ln in basket_get():
        sig_parts.append(ln["id"] + ":" + str(ln["quantity"]))
    new_sig = ",".join(sorted(sig_parts))
    step = counters()["step"]
    prev_sig = state_get("last_cart_sig", "")
    if new_sig != prev_sig:
        state_set("last_cart_step", step)
        state_set("last_cart_sig", new_sig)
    if (state_get("first_hold_step", 0) == 0) and (len(sig_parts) > 0):
        state_set("first_hold_step", step)
    ledger_append({"cart_change_step": step, "changed_sig": new_sig != prev_sig, "sig": new_sig})
    return {"worked": True}

def tool_bag_list(args):
    return bag_summary()

def tool_buy_item(args):
    lines = basket_get()
    if len(lines) == 0:
        return UNKNOWN
    request_order(lines)
    return {"worked": True}

def tool_pass_order(args):
    request_decline()
    return {"worked": True}

def tool_status_report(args):
    used = state_get("messages_used", 0)
    cap = state_get("message_budget", 3)
    return {"tubogu": {"allowance_drawn_down": used, "available": cap - used}}

def tool_ask_buyer(args):
    state_set("messages_used", state_get("messages_used", 0) + 1)
    return {"value": send_message(args.get("ReplyNote", ""))}

def call(handler, args):
    return pending_wrap({
        "locate_listings": tool_locate_listings,
        "open_page": tool_open_page,
        "ask_buyer": tool_ask_buyer,
        "set_to_cart": tool_set_to_cart,
        "bag_list": tool_bag_list,
        "buy_item": tool_buy_item,
        "pass_order": tool_pass_order,
        "status_report": tool_status_report,
    }[handler](args))

def setup_shopper(behaviour):
    state_set("behaviour", behaviour)
    state_set("revealed", [])
    subjects = len(behaviour["duno"])
    order = list(range(subjects))
    for i in range(subjects - 1):
        j = i + rand_below(subjects - i)
        tmp = order[i]
        order[i] = order[j]
        order[j] = tmp
    marker = "".join(["PSL39FKNYXC7ZMB8JU6RTGQEW42D5H"[rand_below(30)] for k in range(12)])
    answers = dict(behaviour["vovafo"])
    for i in range(subjects):
        answers[behaviour["melugo"][i]] = behaviour["ligubo"][order[i]]
    prompt = behaviour["meba"] + "\n".join([(behaviour["melugo"][i] + ": ") + behaviour["duno"][order[i]] for i in range(subjects)]) + behaviour["fase"] + marker + "\n"
    state_set("shopper", {"answers": answers, "prompt": prompt, "marker": marker})

def det_idx(text_low, mod):
    if mod <= 0:
        return 0
    h = 0
    for i in range(len(text_low)):
        c = text_low[i]
        h = (h * 31 + len(c) + i) % 1000003
    for w in text_low.split(" "):
        h = (h * 17 + len(w)) % 1000003
    return h % mod

def has_line_word(text_low, words):
    if not words:
        return True
    for w in words:
        if w in text_low:
            return True
    return False

def has_any_line_word(text_low, lwords):
    if not lwords:
        return True
    for key in lwords:
        if has_line_word(text_low, lwords[key]):
            return True
    return False

def is_approval_or_note(text_low):
    if ("nothing is in the cart" in text_low) or ("could not find a " in text_low) or ("noted:" in text_low) or ("sorry for the confusion" in text_low) or ("i was asking" in text_low) or ("i am asking" in text_low) or ("i will ask one question" in text_low) or ("will not wait for your answer" in text_low):
        return False
    cues = [
        "final basket", "basket before", "your basket", "the basket", "in the basket", "current basket",
        "the cart", "your cart", "in the cart", "selection holds", "basket holds", "cart holds",
        "here is the basket", "here's the basket", "placing the order", "place the order", "buying it now", "buying now",
        "shall i order", "shall i place", "shall i buy",
        "before i place", "before i order", "before i buy", "before i finish", "before ordering", "ready to order", "total before ordering",
        "order total", "cart total", "your total is", "total:", "total is ", "total comes to ",
        "may i place", "is it all right to order", "reply yes", "confirm", "approve",
    ]
    for c in cues:
        if c in text_low:
            return True
    if "?" not in text_low:
        return True
    return False

def non_slot_reply(behaviour, text_low):
    dnu_default = bool(behaviour.get("dnu_default", False))
    bundle_pct = behaviour.get("bundle_pct", 0)
    if (bundle_pct > 0) and (det_idx(text_low + " |b", 1000) < bundle_pct * 10):
        pool = behaviour["tugo"]
        return pool[det_idx(text_low, len(pool))]
    pool = behaviour["sase"][0] if dnu_default else behaviour["sase"][1]
    return pool[det_idx(text_low, len(pool))]

def message(text):
    behaviour = state_get("behaviour")
    shopper = state_get("shopper")
    step = counters()["step"]
    text_low = text.lower()
    dnu_default = bool(behaviour.get("dnu_default", False))

    if is_approval_or_note(text_low):
        ledger_append({"ack_step": step, "last_cart_step": state_get("last_cart_step", 0)})
        if state_get("first_answer_step", 0) == 0:
            state_set("first_answer_step", step)
        pool = behaviour["sase"][0] if dnu_default else behaviour["sase"][1]
        return pool[det_idx(text_low, len(pool))]

    state_set("questions_used", state_get("questions_used", 0) + 1)
    ledger_append({"question_step": step})
    if state_get("first_answer_step", 0) == 0:
        state_set("first_answer_step", step)

    cleaned = text
    for k in range(len(text)):
        if shopper["marker"] not in cleaned:
            break
        cleaned = "".join(cleaned.split(shopper["marker"]))
    lwords = behaviour.get("line_words", {})
    is_multi_line = "line1" in lwords
    label = -2
    for s in behaviour["kubono"]:
        if "meza" in s:
            decided = decide_label(behaviour, s, text)
            if decided != None:
                label = decided[0]
                break
        else:
            if is_multi_line and (not has_any_line_word(text_low, lwords)):
                label = -2
                break
            reply = model_call(s["rahi"], (((shopper["prompt"] + cleaned) + "\n") + shopper["marker"]) + behaviour["sufe"], s["gutubi"])
            label = shopper["answers"].get(reply["text"].strip(), -2) if reply["ok"] else -2
            if label != -2:
                break
    if label == -3:
        pool = behaviour["tugo"]
        return pool[det_idx(text_low, len(pool))]
    if label >= 0:
        if label not in state_get("revealed"):
            state_set("revealed", state_get("revealed") + [label])
            ledger_append({"revealed_need": label})
        pool = behaviour["sase"][label + 2]
        return pool[det_idx(text_low, len(pool))]
    if ("warp core" in text_low) or ("antimatter" in text_low):
        pool = behaviour["sase"][0]
        return pool[det_idx(text_low, len(pool))]
    return non_slot_reply(behaviour, text_low)

def decide_label(behaviour, step, text):
    reply = model_decide(step["rahi"], {"message": text}, behaviour["botisi"], step["gutubi"])
    if not reply["ok"]:
        return None
    answers = reply["answers"]
    if (type(answers) == "dict") and ("answers" in answers):
        answers = answers["answers"]
    if type(answers) != "dict":
        return None
    scores = {}
    for key in behaviour["botisi"]:
        item = answers.get(key)
        if (type(item) != "dict") or (type(item.get("noul")) not in ["float", "int"]):
            return None
        value = item["noul"]
        if ((value < 0) or (value > 1)) or ((value > step["devizu"]) and (value < step["meza"])):
            return None
        scores[key] = value
    if scores[behaviour["jekaro"]] >= step["meza"]:
        return [-1]
    text_low = text.lower()
    lwords = behaviour.get("line_words", {})
    raw_hits = [key for key in behaviour["viroju"] if (scores[key] >= step["meza"])]
    named_hits = [behaviour["viroju"][key] for key in raw_hits]  # no shelf-word gate: the labeler instruction names the shelf and decides; the field reveals fire on questions that never say the shelf word (full-replay audit 2026-11-06)
    if named_hits == []:
        return [-2]
    if len(named_hits) > 1:
        return [-3]
    return [named_hits[0]]

# ---------------------------------------------------------------- grading
def price_of(prices, ov, item_id):
    if item_id in ov:
        return ov[item_id]
    if item_id in prices:
        return prices[item_id]
    row = catalog_get(item_id)
    return row.get("price", 0) if row != None else 0

def order_total(lines, prices, ov):
    total = 0
    for line in lines:
        total += price_of(prices, ov, line["id"]) * line["quantity"]
    return total

def permutations_of(n):
    perms = [[]]
    for k in range(n):
        grown = []
        for p in perms:
            for i in range(n):
                if i not in p:
                    grown.append(p + [i])
        perms = grown
    return perms

def lines_claim_answer_lines(lines, answer_lines, key, gone):
    if len(lines) != len(answer_lines):
        return False
    for perm in permutations_of(len(lines)):
        ok = True
        for i in range(len(lines)):
            target = answer_lines[perm[i]]
            if (lines[i]["id"] not in target[key]) or (lines[i]["id"] in gone) or (lines[i]["quantity"] != target["kudi"]):
                ok = False
                break
        if ok:
            return True
    return False

def cheapest_total(slot, ov, gone):
    total = 0
    for line in slot["tufa"]:
        best = None
        for pid in line["lita"]:
            if pid in gone:
                continue
            c = price_of(slot["fari"], ov, pid) * line["kudi"]
            if (best == None) or (c < best):
                best = c
        if best == None:
            return None
        total += best
    return total

def listing_in_any_line(slot, key, item_id):
    for line in slot["tufa"]:
        if item_id in line[key]:
            return True
    return False

def carted_listings_meet_stated(slot, lines, gone):
    if len(lines) == 0:
        return False
    all_full = True
    for line in lines:
        if (not listing_in_any_line(slot, "reza", line["id"])) or (line["id"] in gone):
            return False
        if not listing_in_any_line(slot, "lita", line["id"]):
            all_full = False
    return not all_full

def accepted(slot, lines, reason, key, ov, gone, dyn):
    if reason == "decline":
        if not dyn:
            return slot["tele"]
        cheapest = cheapest_total(slot, ov, gone)
        return (cheapest == None) or (cheapest > slot["suhe"])
    return lines_claim_answer_lines(lines, slot["tufa"], key, gone) and (order_total(lines, slot["fari"], ov) <= slot["suhe"])

def process_complete(episode, answer, reason):
    opened = {}
    revealed = {}
    for record in episode:
        if record["kind"] == "action":
            tool = record.get("tool")
            args = record.get("args", {})
            if tool == "OpenPage":
                opened[args.get("ItemId", "")] = True
        elif record["kind"] == "event":
            data = record["data"]
            if (type(data) == "dict") and ("revealed_need" in data):
                revealed[data["revealed_need"]] = True
    for chain in answer.get("refs", []):
        for item_id in chain:
            if item_id not in opened:
                return False
    if reason == "order":
        for label in range(answer.get("needs", 0)):
            if label not in revealed:
                return False
    return True

def grade(episode, answer):
    last = episode[-1]
    reason = last["reason"]
    if (reason != "order") and (reason != "decline"):
        return {"category": "did not finish", "score": 0}
    lines = last["order"]["lines"] if (reason == "order") else []
    ov = {}
    gone = []
    fired = False
    for record in episode:
        if record["kind"] == "event":
            data = record["data"]
            if (type(data) == "dict") and ("situ" in data):
                fired = True
                if data.get("item") != None:
                    if data.get("price_to") != None:
                        ov[data["item"]] = data["price_to"]
                    if data.get("kind") == "stock":
                        gone.append(data["item"])
    slot = answer["dova"][0]
    dyn = bool(answer.get("dynamic", False))
    if (reason == "order") or slot["tele"]:
        if not process_complete(episode, answer, reason):
            return {"category": "process requirement missed", "score": 0}
    jufuli = slot["jufuli"]
    if dyn and fired and slot.get("cheapest", False):
        cheapest = cheapest_total(slot, ov, gone)
        jufuli = cheapest if cheapest != None else slot["suhe"]
    verdict = 1 if accepted(slot, lines, reason, "lita", ov, gone, dyn and fired) else 0
    if (verdict == 1) and (reason == "order") and (order_total(lines, slot["fari"], ov) > jufuli):
        verdict = 2
    if verdict == 1:
        return {"category": None, "score": 1}
    if (verdict == 0) and accepted(slot, lines, reason, "reza", ov, gone, dyn and fired):
        return {"category": "needs not found", "score": 0}
    if (verdict == 0) and (reason == "order") and (len(lines) != len(slot["tufa"])) and carted_listings_meet_stated(slot, lines, gone):
        # wrong number of lines, yet every carted listing meets the stated requirements of some line and at least one misses a revealed need
        # (field: 46 of 48 carts with a line count different from the request fit this; all-acceptable carts stay `request not met`)
        return {"category": "needs not found", "score": 0}
    if fired and lines_claim_answer_lines(lines, slot["tufa"], "lita", []):
        # the order is the right shape (line count, quantities, acceptable listings) except that it still holds a sold-out listing;
        # field evidence: a sold-out pick carted next to a second listing on a one-line request is `request not met`
        for line in lines:
            if line["id"] in gone:
                return {"category": "changes missed", "score": 0}
    if verdict == 2:
        return {"category": "not the best option", "score": 0}
    return {"category": "request not met", "score": 0}
