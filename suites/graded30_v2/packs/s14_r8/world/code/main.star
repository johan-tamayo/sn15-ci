# Race-8 Starlark World (`s14_r8`, 45 Open Tasks, `w-forge-s14-r8`)
# Reproduces all Race-8 mechanics from the 9,765 open episodes (`217` agents x `45` tasks):
#   * 8 tools: QueryItems, ScreenRange, ReadDetails, LineUpListings, AddToCart, MyItemsList, AskShopper, ConcludeTask
#   * 4-row pagination (`gudadi4`, `gudadi8`, ..., `result_count` capped at 1000)
#   * `LineUpListings` accepts 1..5 IDs; >5 IDs or unknown `ReadDetails` / `AddToCart` or bad `QueryItems` token returns `{"status": "UNRESOLVED"}`
#   * `ScreenRange` without `ItemShelf` or `VendorName`, or `ConcludeTask(Variant="buy")` on empty bag, returns `{"status": "NO_ITEMS"}`
#   * 5-message allowance (`AskShopper` cost 1, budget 5)
#   * Store notices returned under `{"kubi": [<event_sentence>, ...], "misale": <obs>}` on the step after `AddToCart`,
#     or `ConcludeTask` refusal when finish-only events fire
#   * Buyer persona: 12 reveal frames (incl. reply-by-reference on 7 tasks), 10 nopref, 10 DNU
#   * Graded process requirements:
#     - Reference chains (`answer.refs`) opened via `ReadDetails` or `LineUpListings`
#     - Hidden needs (`answer.needs`) elicited via `AskShopper`
#     - Basket notes are NOT a mandatory process gate when `process_rules` is empty (`CHIDORI`/`KYO`/`Zeus` pass with 0-2 notes)

TEXT_INDEX = "jasu"
CATEGORY_INDEX = "nemogi"
BRAND_INDEX = "kojefe"
PAGE_ROWS = 4
MAX_HITS_REPORTED = 1000
TOKEN_PREFIX = "gudadi"
MAX_LINEUP_REFS = 5
TOOLS = ["QueryItems", "ScreenRange", "ReadDetails", "LineUpListings", "AddToCart", "MyItemsList", "AskShopper", "ConcludeTask"]
LISTING_KINDS = ["stockout", "price"]

def start(envelope):
    params = envelope["params"]
    for name in TOOLS:
        set_cost(name, "steps", 1)
    set_budget("steps", params.get("step_budget", 37))
    msg_cap = params.get("message_budget", 5)
    set_cost("AskShopper", "messages", 1)
    set_budget("messages", msg_cap)
    state_set("message_budget", msg_cap)
    events = params.get("kule", [])
    state_set("events", events)
    state_set("fired", [None for e in events])
    state_set("overrides", {})
    state_set("pending", [])
    state_set("messages_used", 0)
    state_set("questions_used", 0)
    state_set("last_cart_step", 0)
    state_set("last_cart_sig", "")
    state_set("first_hold_step", 0)
    state_set("first_answer_step", 0)
    setup_shopper(params["bezifa"])
    return None

def row_of(item_id):
    row = catalog_get(item_id)
    over = state_get("overrides", {}).get(item_id)
    if (row == None) or (over == None):
        return row
    row = dict(row)
    row.update(over)
    return row

def trigger_met(event, step, basket_ids):
    trigger = event["trigger"]
    if trigger == "step":
        return step >= event["at"]
    if trigger == "first_add":
        return len(basket_ids) > 0
    if trigger == "after_reveal":
        return len(state_get("revealed", [])) >= 1
    return False

def fire(index, step, held_pool):
    events = state_get("events")
    event = events[index]
    held = held_pool[0] if ((event["kind"] in LISTING_KINDS) and held_pool) else None
    fired = state_get("fired")
    fired[index] = step
    state_set("fired", fired)
    new_price = None
    if held != None:
        over = state_get("overrides", {})
        entry = dict(over.get(held, {}))
        if event["kind"] == "stockout":
            entry["in_stock"] = False
        elif event["kind"] == "price":
            if "price_map" in event and held in event["price_map"]:
                new_price = event["price_map"][held]
            elif "mult_pct" in event:
                cur_p = entry.get("price", catalog_get(held).get("price", 0))
                new_price = (cur_p * event["mult_pct"]) // 100
            elif "price_to" in event and event["price_to"] != None:
                new_price = event["price_to"]
            else:
                new_price = int(catalog_get(held).get("price", 0) * 80 // 100)
            entry["price"] = new_price
        over[held] = entry
        state_set("overrides", over)
    ledger_append({"situ": index, "dazi": held, "kind": event["kind"], "step": step, "price_to": new_price, "silent": bool(event.get("silent", False))})
    if (not event.get("silent", False)) and (event["trigger"] != "finish"):
        state_set("pending", state_get("pending", []) + [event["zabovu"]])

def turn():
    events = state_get("events", [])
    fired = state_get("fired", [])
    step = counters()["step"]
    basket_ids = [line["id"] for line in basket_get()]
    for i in range(len(events)):
        event = events[i]
        if (fired[i] != None) or (event["trigger"] == "finish"):
            continue
        if not trigger_met(event, step, basket_ids):
            continue
        if (event["kind"] in LISTING_KINDS) and (len(basket_ids) == 0):
            continue
        fire(i, step, basket_ids)
        fired = state_get("fired", [])
    return None

def can_finish(order):
    events = state_get("events", [])
    step = counters()["step"]
    ids = [line["id"] for line in order.get("lines", [])]
    for i in range(len(events)):
        event = events[i]
        if state_get("fired")[i] != None:
            continue
        if (event["kind"] in LISTING_KINDS) and (len(ids) == 0):
            continue
        fire(i, step, ids)
    sentences = []
    fired = state_get("fired")
    for i in range(len(events)):
        event = events[i]
        if fired[i] == step:
            if (event["kind"] not in LISTING_KINDS) or (len(ids) > 0):
                sentences.append(event["zabovu"])
    pending = state_get("pending", [])
    if pending:
        state_set("pending", [])
        for s in pending:
            if s not in sentences:
                sentences.append(s)
    return {"observation": sentences if sentences else None, "ok": not sentences}

def pending_wrap(result):
    pending = state_get("pending", [])
    if pending:
        state_set("pending", [])
        return {"kubi": pending, "misale": result}
    return result

def overview_of(row):
    text = row.get("description")
    if type(text) != "string":
        return ""
    if len(text) > 1200:
        return text[:1200]
    return text

def search_row(row):
    return {
        "brand": row.get("maker"),
        "category": row.get("category"),
        "dealer": row.get("merchant"),
        "id": row.get("id"),
        "in_stock": row.get("in_stock"),
        "item_cost": row.get("price", 0),
        "listing_name": row.get("title"),
        "overview_text": overview_of(row),
    }

def detail_card(row):
    card = search_row(row)
    card["annotations"] = row.get("seller_notes_text")
    card["facts"] = row.get("facts", {})
    return card

def text_search_ids(query):
    query = query.lower()
    for ch in ["(", ")", ",", "-", ".", "/", ":", ";", "|", "'", "&"]:
        query = query.replace(ch, " ")
    tokens = []
    for tok in query.split(" "):
        if (len(tok) >= 1) and (tok not in tokens):
            tokens.append(tok)
    if tokens == []:
        return []
    found = search(TEXT_INDEX, " ".join(tokens[:6]), {"all_terms": True, "k": 1000})
    if found["ok"] == False:
        return []
    return [hit["id"] for hit in found["hits"] if (row_of(hit["id"]) != None)]

def shelf_search_ids(shelf_name):
    s_low = shelf_name.lower().strip()
    if s_low == "":
        return []
    out = []
    for hit in search(CATEGORY_INDEX, s_low, {"all_terms": True, "k": 1000}).get("hits", []):
        row = row_of(hit["id"])
        if (row != None) and (type(row.get("category")) == "string") and (row["category"].lower().strip() == s_low):
            out.append(hit["id"])
    return out

def vendor_search_ids(vendor_name):
    v_low = vendor_name.lower().strip()
    if v_low == "":
        return []
    out = []
    for hit in search(BRAND_INDEX, v_low, {"all_terms": True, "k": 1000}).get("hits", []):
        row = row_of(hit["id"])
        if row != None:
            mk = (row.get("maker") or "").lower().strip()
            br = (row.get("brand") or "").lower().strip()
            if (mk == v_low) or (br == v_low) or (v_low in br.split(" ")):
                out.append(hit["id"])
    return out

def token_offset(token):
    if (token == None) or (token == ""):
        return 0
    if (type(token) != "string") or (not token.startswith(TOKEN_PREFIX)):
        return -1
    digits = token[len(TOKEN_PREFIX):]
    if (digits == "") or (not digits.isdigit()):
        return -1
    val = int(digits)
    if (val < 0) or ((val % PAGE_ROWS) != 0):
        return -1
    return val

def page_of(ids, token, err_status):
    ids = sorted(ids)
    start_at = token_offset(token)
    if start_at < 0:
        return {"status": err_status}
    capped = len(ids) if len(ids) < MAX_HITS_REPORTED else MAX_HITS_REPORTED
    rows = ids[start_at:start_at + PAGE_ROWS]
    onward = (TOKEN_PREFIX + str(start_at + PAGE_ROWS)) if ((start_at + PAGE_ROWS) < capped) else None
    return {
        "next_page": onward,
        "page_found_items": [search_row(row_of(i)) for i in rows],
        "result_count": capped,
    }

def tool_query_items(args):
    return page_of(text_search_ids(args.get("TextText", "")), args.get("NextContinueFrom"), "UNRESOLVED")

def tool_screen_range(args):
    has_shelf = ("ItemShelf" in args) and (args.get("ItemShelf") != None) and (str(args.get("ItemShelf")).strip() != "")
    has_vendor = ("VendorName" in args) and (args.get("VendorName") != None) and (str(args.get("VendorName")).strip() != "")
    if (not has_shelf) and (not has_vendor):
        return {"status": "NO_ITEMS"}
    ids = None
    if has_shelf:
        ids = shelf_search_ids(str(args.get("ItemShelf")))
    if has_vendor:
        v_ids = vendor_search_ids(str(args.get("VendorName")))
        ids = v_ids if (ids == None) else [i for i in ids if (i in v_ids)]
    if ids == None:
        return {"status": "NO_ITEMS"}
    if ("CostCap" in args) and (args.get("CostCap") != None):
        cap = args.get("CostCap")
        ids = [i for i in ids if (row_of(i).get("price", 0) <= cap)]
    return page_of(ids, args.get("NextToken"), "NO_ITEMS")

def tool_read_details(args):
    row = row_of(args.get("ItemIdNumber", ""))
    if row == None:
        return {"status": "UNRESOLVED"}
    return detail_card(row)

def tool_line_up_listings(args):
    refs = args.get("PickedItems", [])
    if (type(refs) != "list") or (len(refs) < 1) or (len(refs) > MAX_LINEUP_REFS):
        return {"status": "UNRESOLVED"}
    found = []
    for ref in refs:
        row = row_of(ref)
        if row == None:
            return {"status": "UNRESOLVED"}
        found.append(detail_card(row))
    return {"page_found_items": found}

def current_qty(pid):
    for line in basket_get():
        if line["id"] == pid:
            return line["quantity"]
    return 0

def bag_summary():
    lines_out = []
    total = 0
    for line in basket_get():
        row = row_of(line["id"])
        price = row.get("price", 0)
        total += price * line["quantity"]
        lines_out.append({
            "id": line["id"],
            "item_cost": price,
            "line_count": line["quantity"],
            "listing_name": row.get("title"),
        })
    return {"cart_subtotal": total, "your_bag": lines_out}

def tool_add_to_cart(args):
    pid = args.get("WhichItemId", "")
    if row_of(pid) == None:
        return {"status": "UNRESOLVED"}
    qty = args.get("Pieces", 1)
    if type(qty) != "int":
        return {"status": "UNRESOLVED"}
    if args.get("VerbKind") == "add":
        if qty == 0:
            new_qty = 0
        else:
            new_qty = current_qty(pid) + qty
        if (new_qty < 0) or (new_qty > 10):
            return {"status": "UNRESOLVED"}
    else:
        new_qty = current_qty(pid) - qty
        if new_qty < 0:
            new_qty = 0
    basket_set(pid, new_qty)
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
    return bag_summary()

def tool_my_items_list(args):
    return bag_summary()

def tool_conclude_task(args):
    if args.get("Variant") == "skip":
        request_decline()
        return {"applied": True}
    lines = basket_get()
    if len(lines) == 0:
        return {"status": "NO_ITEMS"}
    request_order(lines)
    return {"applied": True}

def tool_ask_shopper(args):
    state_set("messages_used", state_get("messages_used", 0) + 1)
    return {"value": send_message(args.get("ReplyMessage", ""))}

def call(handler, args):
    return pending_wrap({
        "query_items": tool_query_items,
        "screen_range": tool_screen_range,
        "read_details": tool_read_details,
        "line_up_listings": tool_line_up_listings,
        "add_to_cart": tool_add_to_cart,
        "my_items_list": tool_my_items_list,
        "ask_shopper": tool_ask_shopper,
        "conclude_task": tool_conclude_task,
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

def check_lists_basket(text_low):
    lines = basket_get()
    if len(lines) == 0:
        return False
    for line in lines:
        lid = line["id"].lower()
        row = row_of(line["id"])
        shop = (row.get("merchant") or "").lower()
        title = (row.get("title") or "").lower()
        cat = (row.get("category") or "").lower()
        price_str = str(row.get("price", -1))
        matched = (lid in text_low) or ((shop != "") and (shop in text_low)) or (price_str in text_low)
        if not matched:
            for w in (title + " " + cat).split(" "):
                if (len(w) >= 3) and (w in text_low):
                    matched = True
                    break
        if not matched:
            return False
    return True

def message(text):
    behaviour = state_get("behaviour")
    shopper = state_get("shopper")
    step = counters()["step"]
    text_low = text.lower()
    dnu_default = bool(behaviour.get("dnu_default", False))

    if is_approval_or_note(text_low):
        lists_b = check_lists_basket(text_low)
        ledger_append({
            "ack_step": step,
            "last_cart_step": state_get("last_cart_step", 0),
            "lists_basket": lists_b,
        })
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
        pool = behaviour["sase"][0] if dnu_default else behaviour["sase"][1]
        return pool[det_idx(text_low, len(pool))]
    if label >= 0:
        if label not in state_get("revealed"):
            state_set("revealed", state_get("revealed") + [label])
            ledger_append({"revealed_need": label})
        pool = behaviour["sase"][label + 2]
        return pool[det_idx(text_low, len(pool))]
    if dnu_default or ("warp core" in text_low) or ("antimatter" in text_low) or (is_multi_line and (not has_any_line_word(text_low, lwords))):
        pool = behaviour["sase"][0]
        return pool[det_idx(text_low, len(pool))]
    pool = behaviour["sase"][1]
    return pool[det_idx(text_low, len(pool))]

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
    named_hits = [behaviour["viroju"][key] for key in raw_hits if has_line_word(text_low, lwords.get(key, []))]
    if named_hits == []:
        return [-2]
    if len(named_hits) > 1:
        return [-3]
    return [named_hits[0]]

def price_of(prices, item_id):
    if item_id in prices:
        return prices[item_id]
    row = catalog_get(item_id)
    return row.get("price", 0) if row != None else 0

def order_total(lines, prices):
    total = 0
    for line in lines:
        total += price_of(prices, line["id"]) * line["quantity"]
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

def lines_claim_answer_lines(lines, answer_lines, key):
    if len(lines) != len(answer_lines):
        return False
    for perm in permutations_of(len(lines)):
        ok = True
        for i in range(len(lines)):
            target = answer_lines[perm[i]]
            if (lines[i]["id"] not in target[key]) or (lines[i]["quantity"] != target["kudi"]):
                ok = False
                break
        if ok:
            return True
    return False

def accepted(slot, lines, reason, key):
    if reason == "decline":
        return slot["tele"]
    return lines_claim_answer_lines(lines, slot["tufa"], key) and (order_total(lines, slot["fari"]) <= slot["suhe"])

def adjusted(slot, removed, repriced):
    if (not removed) and (not repriced):
        return slot
    slot = dict(slot)
    if repriced:
        fari = dict(slot["fari"])
        for item_id in repriced:
            fari[item_id] = repriced[item_id]
        slot["fari"] = fari
    new_lines = []
    cheapest = 0
    empty = False
    for line in slot["tufa"]:
        line = dict(line)
        line["lita"] = [i for i in line["lita"] if i not in removed]
        line["reza"] = [i for i in line["reza"] if i not in removed]
        fits = [i for i in line["lita"] if (line["kudi"] * price_of(slot["fari"], i)) <= slot["suhe"]]
        if not fits:
            empty = True
        else:
            cheapest += min([line["kudi"] * price_of(slot["fari"], i) for i in fits])
        new_lines.append(line)
    slot["tufa"] = new_lines
    if empty:
        slot["tele"] = True
        return slot
    if slot["jufuli"] < slot["suhe"]:
        slot["jufuli"] = cheapest
    return slot

def process_complete(episode, answer, reason):
    opened = {}
    revealed = {}
    acks = []
    last_cart_step = 0
    for record in episode:
        if record["kind"] == "action":
            tool = record.get("tool")
            args = record.get("args", {})
            if tool == "ReadDetails":
                opened[args.get("ItemIdNumber", "")] = True
            elif tool == "LineUpListings":
                refs = args.get("PickedItems", [])
                if (type(refs) == "list") and (len(refs) <= MAX_LINEUP_REFS):
                    for r in refs:
                        opened[r] = True
        elif record["kind"] == "event":
            data = record["data"]
            if type(data) == "dict":
                if "revealed_need" in data:
                    revealed[data["revealed_need"]] = True
                if ("cart_change_step" in data) and data.get("changed_sig", True):
                    last_cart_step = data["cart_change_step"]
                if "ack_step" in data:
                    acks.append(data)

    for chain in answer.get("refs", []):
        for item_id in chain:
            if item_id not in opened:
                return False

    if reason == "order":
        for label in range(answer.get("needs", 0)):
            if label not in revealed:
                return False
        rules = answer.get("process_rules", [])
        for r in rules:
            if r == "approval_after_final_cart":
                ok = False
                for a in acks:
                    if (a["ack_step"] > last_cart_step) and a.get("lists_basket"):
                        ok = True
                if not ok:
                    return False
    return True

def grade(episode, answer):
    last = episode[-1]
    reason = last["reason"]
    if (reason != "order") and (reason != "decline"):
        return {"category": "did not finish", "score": 0}
    lines = last["order"]["lines"] if (reason == "order") else []
    mask = 0
    history = [0]
    removed = []
    repriced = {}
    for record in episode:
        if record["kind"] == "event":
            data = record["data"]
            if (type(data) == "dict") and ("situ" in data):
                mask = mask | [1, 2, 4][data["situ"]]
                history.append(mask)
                if (data.get("dazi") != None) and (data.get("kind") == "stockout"):
                    removed.append(data["dazi"])
                if (data.get("dazi") != None) and (data.get("kind") == "price") and (data.get("price_to") != None):
                    repriced[data["dazi"]] = data["price_to"]
    slot = adjusted(answer["dova"][mask], removed, repriced)
    if (reason == "order") or slot["tele"]:
        if not process_complete(episode, answer, reason):
            return {"category": "process requirement missed", "score": 0}
    verdict = 1 if accepted(slot, lines, reason, "lita") else 0
    if (verdict == 1) and (reason == "order") and (order_total(lines, slot["fari"]) > slot["jufuli"]):
        verdict = 2
    if verdict == 1:
        return {"category": None, "score": 1}
    if (verdict == 0) and accepted(slot, lines, reason, "reza"):
        return {"category": "needs not found", "score": 0}
    for earlier in history[:-1]:
        eslot = answer["dova"][earlier]
        if (earlier != mask) and accepted(eslot, lines, reason, "lita"):
            if (verdict == 0) or ((verdict == 2) and (order_total(lines, eslot["fari"]) <= eslot["jufuli"])):
                return {"category": "changes missed", "score": 0}
    if verdict == 2:
        return {"category": "not the best option", "score": 0}
    return {"category": "request not met", "score": 0}
