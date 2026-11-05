# Race-9 Starlark World (`s14_r9`, 45 Open Tasks, `w-forge-s14-r9`)
# Reproduces the Race-9 mechanics seen in the 20,070 released open episodes (223 agents x 2 validators x 45 tasks):
#   * 7 tools: itemsSeek, weigh, pageDescribe, buyerAsk, holdToCart (lineNumber = absolute pieces), itemsBag, taskClose
#   * itemsSeek: text = BM25 over the phrase (+ shelf words), 200 hits max, 11 rows per page, pages 1..2 (page_follow 2 | None);
#     browse = the whole shelf id-sorted (num_hits_number = shelf size)
#   * weigh accepts 1..2 known ids ({"call_problem": "I couldn't locate that listing."} otherwise), pageDescribe / holdToCart unknown id -> call_problem
#   * 4-message allowance (buyerAsk cost 1, budget 4)
#   * store notices ride on the NEXT tool observation as {"bujiri": <obs>, "lobofe": [<sentence>, ...]}; events not yet fired
#     at the first taskClose refuse it ({"observation": {"went_through": True}, "refusal": [...]}) and the episode continues
#   * persona: 12 reveal frames (reply-by-reference on 6 tasks), 10 nopref, 10 DNU (dnu_default on 21 multi-line tasks),
#     10 bundle-refusal strings (per-task share on non-slot questions)
#   * graded: reference chains opened via pageDescribe / weigh, hidden needs via buyerAsk, lines / quantities / suhe / jufuli

TEXT_INDEX = "jasu"
CATEGORY_INDEX = "nemogi"
BRAND_INDEX = "kojefe"
PAGE_ROWS = 11
MAX_PAGES = 2
TEXT_HITS_CAP = 200
MAX_WEIGH_REFS = 2
TOOLS = ["itemsSeek", "weigh", "pageDescribe", "buyerAsk", "holdToCart", "itemsBag", "taskClose"]
NOT_FOUND = {"call_problem": "I couldn't locate that listing."}

def start(envelope):
    params = envelope["params"]
    for name in TOOLS:
        set_cost(name, "steps", 1)
    set_budget("steps", params.get("step_budget", 43))
    msg_cap = params.get("message_budget", 4)
    set_cost("buyerAsk", "messages", 1)
    set_budget("messages", msg_cap)
    state_set("message_budget", msg_cap)
    events = params.get("kule", [])
    state_set("events", events)
    state_set("fired", [None for e in events])
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
    return catalog_get(item_id)

def trigger_met(event, step, basket_ids):
    trigger = event["trigger"]
    if trigger == "step":
        return step >= event["at"]
    if trigger == "first_add":
        return len(basket_ids) > 0
    if trigger == "after_reveal":
        return len(state_get("revealed", [])) >= 1
    return False

def fire(index, step):
    events = state_get("events")
    event = events[index]
    fired = state_get("fired")
    fired[index] = step
    state_set("fired", fired)
    ledger_append({"situ": index, "dazi": None, "kind": event["kind"], "step": step, "price_to": None, "silent": bool(event.get("silent", False))})
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
        fire(i, step)
        fired = state_get("fired", [])
    return None

def can_finish(order):
    events = state_get("events", [])
    step = counters()["step"]
    for i in range(len(events)):
        if state_get("fired")[i] != None:
            continue
        fire(i, step)
    sentences = []
    fired = state_get("fired")
    for i in range(len(events)):
        if fired[i] == step:
            sentences.append(events[i]["zabovu"])
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
        return {"bujiri": result, "lobofe": pending}
    return result

def blurb_of(row):
    text = row.get("description")
    if type(text) != "string":
        return ""
    if len(text) > 1200:
        return text[:1200]
    return text

def search_row(row):
    return {
        "blurb_body": blurb_of(row),
        "brand": row.get("maker"),
        "department": row.get("category"),
        "id": row.get("id"),
        "item_list_price": row.get("price", 0),
        "product_name_text": row.get("title"),
        "ready": row.get("in_stock"),
        "seller": row.get("merchant"),
    }

def full_card(row):
    card = search_row(row)
    card["item_good_to_know"] = row.get("seller_notes_text")
    card["product_properties"] = row.get("facts", {})
    return card

def text_search_ids(query):
    query = query.lower()
    for ch in ["(", ")", ",", "-", ".", "/", ":", ";", "|", "'", "&", "\""]:
        query = query.replace(ch, " ")
    tokens = []
    for tok in query.split(" "):
        if (len(tok) >= 1) and (tok not in tokens):
            tokens.append(tok)
    if tokens == []:
        return []
    found = search(TEXT_INDEX, " ".join(tokens[:10]), {"all_terms": False, "k": TEXT_HITS_CAP})
    if found["ok"] == False:
        return []
    ranked = sorted(found["hits"], key = lambda h: (-h["score"], h["id"]))
    return [hit["id"] for hit in ranked if (row_of(hit["id"]) != None)]

def shelf_ids(shelf_name):
    s_low = shelf_name.lower().strip()
    if s_low == "":
        return []
    out = []
    for hit in search(CATEGORY_INDEX, s_low, {"all_terms": True, "k": 1000}).get("hits", []):
        row = row_of(hit["id"])
        if (row != None) and (type(row.get("category")) == "string") and (row["category"].lower().strip() == s_low):
            out.append(hit["id"])
    return sorted(out)

def page_of(ids, page):
    if (page == None) or (page == 0):
        page = 1
    start_at = (page - 1) * PAGE_ROWS
    rows = ids[start_at:start_at + PAGE_ROWS]
    onward = 2 if ((page == 1) and (len(ids) > PAGE_ROWS)) else None
    return {
        "num_hits_number": len(ids),
        "page_follow": onward,
        "search_items": [search_row(row_of(i)) for i in rows],
    }

def tool_items_seek(args):
    strategy = args.get("strategy", "text")
    phrase = args.get("phrase")
    shelf = args.get("productShelf")
    if strategy == "browse":
        ids = shelf_ids(str(shelf)) if (shelf != None) else []
    else:
        if (phrase == None) or (str(phrase).strip() == ""):
            ids = []
        else:
            query = str(phrase)
            if shelf != None:
                query = query + " " + str(shelf)
            ids = text_search_ids(query)
    return page_of(ids, args.get("pageNumberNum"))

def tool_page_describe(args):
    row = row_of(args.get("idCode", ""))
    if row == None:
        return NOT_FOUND
    return full_card(row)

def tool_weigh(args):
    refs = args.get("targetRefs", [])
    if (type(refs) != "list") or (len(refs) < 1) or (len(refs) > MAX_WEIGH_REFS):
        return NOT_FOUND
    found = []
    for ref in refs:
        row = row_of(ref)
        if row == None:
            return NOT_FOUND
        found.append(full_card(row))
    return {"search_items": found}

def bag_summary():
    lines_out = []
    total = 0
    for line in basket_get():
        row = row_of(line["id"])
        price = row.get("price", 0)
        total += price * line["quantity"]
        lines_out.append({
            "count_held": line["quantity"],
            "id": line["id"],
            "item_list_price": price,
            "product_name_text": row.get("title"),
        })
    return {"basket_lines": lines_out, "cart_total_cost": total}

def tool_hold_to_cart(args):
    pid = args.get("item", "")
    if row_of(pid) == None:
        return NOT_FOUND
    qty = args.get("lineNumber", 1)
    if type(qty) != "int":
        return NOT_FOUND
    basket_set(pid, qty)
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
    return {"went_through": True}

def tool_items_bag(args):
    return bag_summary()

def tool_task_close(args):
    if args.get("lookupWay") == "none":
        request_decline()
        return {"went_through": True}
    lines = basket_get()
    if len(lines) == 0:
        return {"call_problem": "Your basket is empty right now."}
    request_order(lines)
    return {"went_through": True}

def tool_buyer_ask(args):
    state_set("messages_used", state_get("messages_used", 0) + 1)
    return {"value": send_message(args.get("words", ""))}

def call(handler, args):
    return pending_wrap({
        "items_seek": tool_items_seek,
        "weigh": tool_weigh,
        "page_describe": tool_page_describe,
        "buyer_ask": tool_buyer_ask,
        "hold_to_cart": tool_hold_to_cart,
        "items_bag": tool_items_bag,
        "task_close": tool_task_close,
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
    if det_idx(text_low + " |b", 1000) < bundle_pct * 10:
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

def process_complete(episode, answer, reason):
    opened = {}
    revealed = {}
    for record in episode:
        if record["kind"] == "action":
            tool = record.get("tool")
            args = record.get("args", {})
            if tool == "pageDescribe":
                opened[args.get("idCode", "")] = True
            elif tool == "weigh":
                refs = args.get("targetRefs", [])
                if (type(refs) == "list") and (len(refs) <= MAX_WEIGH_REFS):
                    for r in refs:
                        opened[r] = True
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
    mask = 0
    history = [0]
    for record in episode:
        if record["kind"] == "event":
            data = record["data"]
            if (type(data) == "dict") and ("situ" in data):
                mask = mask | [1, 2, 4][data["situ"]]
                history.append(mask)
    slot = answer["dova"][mask]
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
