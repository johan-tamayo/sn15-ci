# Race-16 Starlark World (`s14_r16`, 45 Open Tasks, `w-forge-s14-r16`)
# Reproduces the Race-16 mechanics seen in the released open episodes:
#   * 7 tools: ItemsSeek (phrase | match), FullSpecs, OfferShow, StashToBasket (sets one line), SummaryMyItems, OrderWrapUp (checkout|cancel), BuyerMessage
#   * ItemsSeek phrase: AND over the analyzed words, id-sorted, top 500; match: one shelf (+ Budget / ProductVendor), id-sorted; 6 cards per page, token vetu<offset>
#   * cards are JSON objects (pointers only on OfferShow; facts only on FullSpecs)
#   * 3-message allowance (BuyerMessage cost 1, budget 3)
#   * events: trigger finish (first commit with a cart refused once), first_add (first non-empty stash; echo on the next call),
#     after_reveal (first slot reveal; echo on the next call); kinds budget (new cap) | drop (relaxed clause) | stock (carted line sells out)
#   * persona: 12 reveal frames, nopref, DNU (dnu_default per task share)
#   * askBuyer credit: the live labeler's position / shelf-context rule, one PRNG draw per message (fit: runs/forge4/HANDOVER.md)
#   * graded: pointer chains opened via OfferShow / FullSpecs, hidden needs via BuyerMessage, one answer slot per fired-event bitmask

TEXT_INDEX = "jasu"
CATEGORY_INDEX = "nemogi"
BRAND_INDEX = "kojefe"
PAGE_ROWS = 6
TEXT_HITS_CAP = 500  # field phrase counts saturate at 500
ALL_TERMS = True
SHELF_LIVE_COUNT = {"200mb": 0, "200mb memory card": 0, "3mp 12v 5v cameras": 0, "3mp cameras": 0, "4 channel": 0, "4 channel cctv security cameras": 0, "4 channel security cameras": 0, "48mp": 0, "48mp usb plug video camera": 0, "48mp video camera": 0, "bed sheet": 0, "bed sheets": 824, "burgundy": 0, "burgundy slip-on closure slipcover": 0, "burgundy slipcovers and furniture covers": 0, "c": 0, "camcorders": 0, "camera support": 0, "cctv": 0, "cctv camera": 0, "cctv cameras": 0, "cctv security": 0, "cctv security camera": 0, "cctv security cameras": 880, "cctv security cameras kamo": 0, "cctv security cameras razen": 0, "cctv security cameras sanori": 0, "cctv security cameras torsa": 0, "cents us": 0, "chenille": 0, "chenille furniture covers": 0, "children": 0, "children bed sheets": 0, "couches": 0, "dome cctv cameras": 0, "dome cctv security camera": 0, "dome cctv security cameras": 0, "dome-style cctv security camera": 0, "dome-style cctv security cameras": 0, "fitted sheet": 0, "fitted sheet bed sheets": 0, "furniture cover": 0, "furniture covers": 403, "item": 0, "items": 0, "kg or lower please": 0, "loveseats": 0, "memory card": 0, "memory cards": 921, "memory cards belvosara": 0, "memory cards kaanmomi": 0, "memory cards kavomo": 0, "memory cards moqiqi": 0, "memory cards rabelralen": 0, "memory cards zensalen": 0, "microsdhc memory cards": 0, "nautical sofa cover": 0, "noritorno": 0, "noritorno 3 pieces": 0, "noritorno 3 pieces 200 thread count fitted sheet": 0, "noritorno bed sheets": 0, "only the": 0, "pvc": 0, "qilumi": 0, "qilumi class 10": 0, "qilumi class 10 flash 80 mb/s": 0, "qilumi memory cards": 0, "ramian": 0, "ramian 128 gb": 0, "ramian 128 gb flash sd card": 0, "ramian memory card": 0, "ramian memory cards": 0, "recliner sofa": 0, "recliner sofas": 0, "sectional sofas": 0, "security camera": 0, "security cameras": 0, "set bed sheets": 0, "set geometric pattern bed sheets": 0, "set of bed sheets": 0, "set of sofa covers & slips": 0, "slipcover": 0, "slipcover and furniture cover": 0, "slipcovers": 0, "slipcovers & furniture covers": 0, "slipcovers and": 0, "slipcovers and furniture covers": 184, "slipcovers and furniture covers dormovexvex": 0, "slipcovers and furniture covers sakaantor": 0, "slipcovers and furniture covers tadordor": 0, "slipcovers and furniture covers tortorkota": 0, "slipcovers and furniture covers zenanbel": 0, "sofa": 0, "sofa & couch": 0, "sofa beds": 0, "sofa cover": 0, "sofa cover & slip": 0, "sofa cover or slip": 0, "sofa covers": 0, "sofa covers & slips": 963, "sofa covers & slips kokoshitor": 0, "sofa covers & slips kotazen": 0, "sofa covers & slips noanno": 0, "sofa covers & slips qivexta": 0, "sofa covers & slips votavexzen": 0, "sofa covers & slips zenanra": 0, "sofa covers and slips": 0, "sofa sets": 0, "sofas": 757, "sofas & couches": 0, "sofas & loveseats": 0, "sofas doranshivex": 0, "sofas dorkomimo": 0, "sofas lensavexko": 0, "sofas shimolu": 0, "sofas tavexrador": 0, "suede fabric": 0, "suede fabric sofa covers & slips": 0, "suede fabric vintage sofa cover": 0, "tan furniture cover": 0, "textured": 0, "textured furniture cover": 0, "the product": 0, "tripod": 0, "tripod and camera support": 0, "tripod or camera support": 0, "tripods": 279, "tripods & camera supports": 0, "tripods and": 0, "tripods and camera supports": 984, "tripods and camera supports ankataan": 0, "tripods and camera supports koshikako": 0, "tripods and camera supports qitador": 0, "tripods and camera supports qitorlen": 0, "tripods and camera supports taramo": 0, "tripods and camera supports vozenqira": 0, "tripods anvotashi": 0, "tripods lenlenqi": 0, "tripods or camera supports": 0, "tripods qimobel": 0, "tripods tasanoqi": 0, "tripods torvextavex": 0, "tripods vexsazen": 0, "turret": 0, "turret cctv security cameras": 0, "turret white cctv camera": 0, "video camera": 259, "video camera dorkotor": 0, "video camera dorqiko": 0, "video camera salenshi": 0, "video camera shimokata": 0, "video camera tadortator": 0, "video camera vorator": 0, "video cameras": 0, "vokoshi": 0, "vokoshi tripods and camera supports black": 0}  # live shelf sizes (field match all_matches without filters)
TROUBLE_EMPTY = "Order list contains no selected items."
TROUBLE_REF = "Reference resolves to no existing listing."
TOOLS = ["ItemsSeek", "FullSpecs", "OfferShow", "StashToBasket", "SummaryMyItems", "OrderWrapUp", "BuyerMessage"]

def start(envelope):
    params = envelope["params"]
    for name in TOOLS:
        set_cost(name, "steps", 1)
    set_budget("steps", params.get("step_budget", 38))
    msg_cap = params.get("message_budget", 3)
    set_cost("BuyerMessage", "messages", 1)
    set_budget("messages", msg_cap)
    state_set("message_budget", msg_cap)
    state_set("events", params.get("events", []))
    state_set("fired_idx", [])
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
    state_set("credit_seed", rand_below(1000000007))  # FORGE4: the question-credit draws of this episode
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

def cart_total(lines, ov):
    total = 0
    for line in lines:
        row = row_of(line["id"])
        total += ov.get(line["id"], row.get("price", 0) if row != None else 0) * line["quantity"]
    return total

def fire_events(trigger, skip = False):
    # fire every not-yet-fired event of this trigger kind against the current cart; returns the notice sentences.
    # skip=True (closeRequest skip): a stock event is NOT fired - R15 field, 11 stock-only skips with a cart and 144 with an empty cart were all applied, 0 refused
    # (full-replay audit 2026-11-06: t-b16f7ebd5d 0fd41bab, t-4df1d81f4f c4ff23ec / b273e216, t-fdc76f3907 3f38b4b5, t-6bdda735d7 2f7a417e)
    events = state_get("events", [])
    lines = basket_get()
    sentences = []
    ov = state_get("ov_price", {})
    gone = state_get("gone", [])
    fired = state_get("fired_idx", [])
    step = counters()["step"]
    pend = state_get("pending", [])
    for i in range(len(events)):
        event = events[i]
        if (i in fired) or (event.get("trigger", "finish") != trigger):
            continue
        if skip and (event["kind"] == "stock"):
            continue
        if event.get("over_cap_only", False) and (cart_total(lines, ov) <= event["new_cap"]):
            continue  # calibration (t-c217fa5565): the budget sentence is only voiced when the cart is over the new limit
        li = event.get("target_line", 0)
        item = None
        if li < len(lines):
            item = lines[li]["id"]
        needs_target = event.get("needs_target", event["kind"] in ["stock", "price"])
        if (item == None) and needs_target:
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
        fired.append(i)
        ledger_append({"situ": i, "item": item, "kind": event["kind"], "step": step, "price_to": price_to, "silent": False})
        sentences.append(event["sent"])
        if event.get("echo", False):
            pend.append([step, event["sent"], trigger])
    state_set("ov_price", ov)
    state_set("gone", gone)
    state_set("pending", pend)
    state_set("fired_idx", fired)
    return sentences

def can_finish(order):
    events = state_get("events", [])
    fired = state_get("fired_idx", [])
    if (len(events) == 0):
        return {"observation": None, "ok": True}
    is_skip = (type(order) == "dict") and (order.get("kind") == "decline")
    ready = []
    if not is_skip:
        # field (R15 open, scratch/r15_timing + full-replay audit 2026-11-06): a commit that is the very next call after the first stash of a first_add + echo task is refused with the
        # not-yet-echoed sentence (4 of 4: t-7bc4ad4ab9 x3, t-6bdda735d7 x1); the call's own observation still carries the echo (the wrap consumes it)
        step_now = counters()["step"]
        # the finish check runs after the tool wrap, so the wrap has already consumed the echo: it leaves the first_add sentences it served at this step in "echoed_now"
        served = state_get("echoed_now", [0, []])
        if served[0] == step_now:
            ready = list(served[1])
    if (len(fired) >= len(events)):
        if len(ready) > 0:
            return {"observation": ready, "ok": False}
        return {"observation": None, "ok": True}
    empty_close = len(basket_get()) == 0
    sentences = ready + fire_events("finish", is_skip) + fire_events("first_add", is_skip) + fire_events("after_reveal", is_skip)
    if empty_close:
        # R15 field (t-672b184c42, episode 009cc0b8): the first close was a skip with an empty cart; the drop sentence refused it and the
        # stock event (no carted item to hit) was consumed - the later commit of the same listing was NOT refused (graded not-the-best-option).
        # A target-needing finish event that finds no target at the first close is therefore dropped, not retried at the next commit.
        fired = state_get("fired_idx", [])
        for i in range(len(events)):
            if (i not in fired) and (events[i].get("trigger", "finish") == "finish"):
                fired.append(i)
        state_set("fired_idx", fired)
    return {"observation": sentences if sentences else None, "ok": not sentences}

def pending_wrap(result):
    pend = state_get("pending", [])
    step = counters()["step"]
    ready = [p for p in pend if p[0] < step]
    if ready:
        state_set("pending", [p for p in pend if p[0] >= step])
        state_set("echoed_now", [step, [p[1] for p in ready if p[2] == "first_add"]])
        return {"pozo": result, "teve": [p[1] for p in ready]}
    return result

def desc_of(row):
    text = row.get("description")
    if type(text) != "string":
        return ""
    return text

def card_obj(row, page):
    out = {
        "category": row.get("category"),
        "headline_text": row.get("title"),
        "in_stock": eff_stock(row),
        "overview": desc_of(row),
        "price": eff_price(row),
        "seller": row.get("merchant"),
        "sku_code": row["id"],
        "vendor": row.get("maker"),
    }
    if page:
        out["pointers"] = row.get("seller_notes_text")
    return out

def clean_query(query):
    query = query.lower()
    for ch in ["(", ")", ",", "-", ".", ":", ";", "|"]:
        query = query.replace(ch, " ")
    tokens = []
    for tok in query.split(" "):
        if (len(tok) >= 1) and (tok not in tokens) and (not tok.isdigit()):
            tokens.append(tok)
    return tokens

def text_search_ids(query):
    if clean_query(query) == []:
        return []
    found = search(TEXT_INDEX, query, {"all_terms": ALL_TERMS, "k": 5000})
    if found["ok"] == False:
        return []
    out = []
    for hit in found["hits"]:
        if row_of(hit["id"]) != None:
            out.append(hit["id"])
    return sorted(out)

def group_ids(group):
    out = []
    for hit in search(CATEGORY_INDEX, group, {"all_terms": True, "k": 5000}).get("hits", []):
        row = row_of(hit["id"])
        if (row != None) and (type(row.get("category")) == "string") and (row["category"].lower().strip() == group):
            out.append(hit["id"])
    return sorted(out)

def vendor_ok(row, vendor):
    v = vendor.lower().strip()
    return (str(row.get("maker") or "").lower().strip() == v) or (str(row.get("merchant") or "").lower().strip() == v)

def tool_items_seek(args):
    mode = args.get("UsingType", "phrase")
    group = args.get("Group")
    budget = args.get("Budget")
    vendor = args.get("ProductVendor")
    count = None
    if mode == "match":
        if group == None:
            if vendor == None:
                return {"call_trouble": TROUBLE_EMPTY}
            return {"all_matches": 0, "follow_token": None, "matches_set": []}
        g = str(group).lower().strip()
        ids = group_ids(g)
        if (budget == None) and (vendor == None) and (g in SHELF_LIVE_COUNT):
            count = SHELF_LIVE_COUNT[g]
        if budget != None:
            ids = [i for i in ids if eff_price(row_of(i)) <= budget]
        if vendor != None:
            ids = [i for i in ids if vendor_ok(row_of(i), str(vendor))]
    else:
        words = str(args.get("SearchPhrase", "")).strip()
        ids = text_search_ids(words) if words != "" else []
        if vendor != None:
            ids = [i for i in ids if vendor_ok(row_of(i), str(vendor))]
        ids = ids[:TEXT_HITS_CAP]
    if count == None:
        count = len(ids)
    begin = 0
    tok = args.get("NextNext")
    if tok != None:
        s = str(tok)
        if s.startswith("vetu") and s[4:].isdigit():
            begin = int(s[4:])
    rows = ids[begin:begin + PAGE_ROWS]
    follow = ("vetu" + str(begin + PAGE_ROWS)) if (begin + PAGE_ROWS < count) else None
    return {"all_matches": count, "follow_token": follow, "matches_set": [card_obj(row_of(i), False) for i in rows]}

def tool_full_specs(args):
    row = row_of(args.get("ListingNumber", ""))
    if row == None:
        return {"call_trouble": TROUBLE_REF}
    return {"facts": row.get("facts", {}), "headline_text": row.get("title"), "sku_code": row["id"]}

def tool_offer_show(args):
    row = row_of(args.get("ItemIdCode", ""))
    if row == None:
        return {"call_trouble": TROUBLE_REF}
    return card_obj(row, True)

def bag_summary():
    lines_out = []
    total = 0
    for line in basket_get():
        row = row_of(line["id"])
        price = eff_price(row)
        total += price * line["quantity"]
        lines_out.append({"headline_text": row.get("title"), "number": line["quantity"], "price": price, "sku_code": line["id"]})
    return {"cart_total_cost": total, "current_contents": lines_out}

def tool_summary_my_items(args):
    return bag_summary()

def tool_stash_to_basket(args):
    pid = args.get("Product", "")
    if row_of(pid) == None:
        return {"call_trouble": TROUBLE_REF}
    basket_set(pid, args.get("ItemHowMany", 0))
    sig_parts = []
    for ln in basket_get():
        sig_parts.append(ln["id"] + ":" + str(ln["quantity"]))
    new_sig = ",".join(sorted(sig_parts))
    step = counters()["step"]
    prev_sig = state_get("last_cart_sig", "")
    if new_sig != prev_sig:
        state_set("last_cart_step", step)
        state_set("last_cart_sig", new_sig)
    first = (state_get("first_hold_step", 0) == 0) and (len(sig_parts) > 0)
    if first:
        state_set("first_hold_step", step)
    ledger_append({"cart_change_step": step, "changed_sig": new_sig != prev_sig, "sig": new_sig})
    if first:
        fire_events("first_add")
    return {"worked": True}

def tool_order_wrap_up(args):
    if args.get("Kind") == "cancel":
        request_decline()
        return {"worked": True}
    lines = basket_get()
    if len(lines) == 0:
        return {"call_trouble": TROUBLE_EMPTY}
    request_order(lines)
    return {"worked": True}

def tool_ask_buyer(args):
    state_set("messages_used", state_get("messages_used", 0) + 1)
    return {"value": send_message(args.get("ChatBody", ""))}

def call(handler, args):
    return pending_wrap({
        "items_seek": tool_items_seek,
        "full_specs": tool_full_specs,
        "offer_show": tool_offer_show,
        "stash_to_basket": tool_stash_to_basket,
        "summary_my_items": tool_summary_my_items,
        "order_wrap_up": tool_order_wrap_up,
        "ask_buyer": tool_ask_buyer,
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

def ack_reply(behaviour, text_low, step, dnu_default):
    ledger_append({"ack_step": step, "last_cart_step": state_get("last_cart_step", 0)})
    if state_get("first_answer_step", 0) == 0:
        state_set("first_answer_step", step)
    pool = behaviour["sase"][0] if dnu_default else behaviour["sase"][1]
    return pool[det_idx(text_low, len(pool))]

def message(text):
    behaviour = state_get("behaviour")
    shopper = state_get("shopper")
    step = counters()["step"]
    text_low = text.lower()
    dnu_default = bool(behaviour.get("dnu_default", False))

    # an approval / note cue ("before I order") with no question mark is a plain note; one WITH a question mark is still put to the labeler first: the field
    # answered "Quick check before I order: what material do you need?" with a reveal (full-replay audit 2026-11-06, t-c217fa5565 e77745e3 / da4bfbdd)
    approval = is_approval_or_note(text_low)
    if approval and ("?" not in text_low):
        return ack_reply(behaviour, text_low, step, dnu_default)

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
    if approval and (label < 0):
        return ack_reply(behaviour, text_low, step, dnu_default)

    state_set("questions_used", state_get("questions_used", 0) + 1)
    ledger_append({"question_step": step})
    if state_get("first_answer_step", 0) == 0:
        state_set("first_answer_step", step)
    if label == -3:
        pool = behaviour["tugo"]
        return pool[det_idx(text_low, len(pool))]
    if label >= 0:
        if label not in state_get("revealed"):
            state_set("revealed", state_get("revealed") + [label])
            ledger_append({"revealed_need": label})
            fire_events("after_reveal")
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
    if raw_hits == []:
        return [-2]
    return [credit_decide(behaviour, text, raw_hits)]  # FORGE4: the live credit of the hits by position / shelf context, one draw per message (runs/forge4/HANDOVER.md)

# ---------------------------------------------------------------- question credit (FORGE4: runs/forge4/HANDOVER.md)
# The live labeler credits a question that names a hidden need by WHERE the need sits among the question's names: the first name is
# always read, a later one about half the time, the last name of a long list rarely; on a multi-line task a name without the need's
# shelf word (singular or plural) is read less often and one with another line's shelf word almost never; a decoy named before the need blocks the reading
# ~40%; a second need after a read need is never credited.  One draw per message from the episode PRNG seed and the message index.
CREDIT_P_ORD = {"k1": {"first": 1.0, "unplaced": 0.767}, "k2": {"first": 0.957, "last": 0.764, "unplaced": 0.767}, "k3": {"first": 1.0, "last": 0.6, "second": 0.621, "unplaced": 0.767}, "k4-5": {"first": 0.986, "last": 0.233, "middle": 0.478, "second": 0.597, "unplaced": 0.767}, "k6+": {"first": 1.0, "last": 0.062, "middle": 0.481, "second": 0.757, "unplaced": 0.767}}
CREDIT_F_CTX = {"1L": 1.0, "neither": 0.529, "other": 0.034, "own": 1.0, "own+other k1": 0.768, "own+other list": 0.172}
CREDIT_DECOY_CONSUME = 0.302
CREDIT_INTERROGATIVES = ["what ", "which "]
CREDIT_WANT_FOR = ["want for ", "like for ", "need for ", "want on ", "want in ", "need in ", "care about ", "looking for ", "want from ", "need from ", "want ", "need "]
CREDIT_PREFERENCE = ["preference for the ", "preference for ", "preferences for ", "preference on ", "prefer "]
CREDIT_CUTS = [" would you", " do you", " should ", " for the ", " for your ", " for my ", " for a ", " for an ", " for this ", " of the ", " on the ", " in the ", " for example", " such as", " e.g.", " like ", " please", " so i ", " so that ", " - "]
CREDIT_SEPS = [",", ";", " or ", " and ", " / "]

def credit_draw(idx):
    x = (state_get("credit_seed", 0) * 2654435761 + idx * 40503 + 12345) % 4294967296
    x = ((x ^ (x >> 16)) * 2246822519) % 4294967296
    x = ((x ^ (x >> 13)) * 3266489917) % 4294967296
    x = x ^ (x >> 16)
    return x % 10000

def credit_span_end(ql, start):
    end = ql.find("?", start)
    if end < 0:
        end = len(ql)
    lo = start - 1
    if lo < 0:
        lo = 0
    for cut in CREDIT_CUTS:
        j = ql.find(cut, lo, end)
        if (j >= 0) and (j < end):
            end = j
            if end < start:
                end = start
    return end

def credit_last_marker(ql, markers, lo, hi):
    best = -1
    for m in markers:
        i = ql.rfind(m, lo, hi)
        if (i >= 0) and (i + len(m) > best):
            best = i + len(m)
    return best

def credit_split_span(ql, start, end):
    parts = []
    pos = start
    for n in range(64):
        best = -1
        blen = 0
        for sep in CREDIT_SEPS:
            j = ql.find(sep, pos, end)
            if (j >= 0) and ((best < 0) or (j < best)):
                best = j
                blen = len(sep)
        if best < 0:
            break
        parts.append([pos, best])
        pos = best + blen
    parts.append([pos, end])
    return [p for p in parts if ql[p[0]:p[1]].strip() != ""]

def credit_name_span(ql):
    # after the last interrogative before the first '?' (a colon after it wins when its list has more separators); if that span is
    # empty ("what do you want for ..."), after the last "want for"-type phrase after the interrogative; without an interrogative,
    # after a "preference for"-type phrase, else a colon, else the text start
    q_end = ql.find("?")
    if q_end < 0:
        q_end = len(ql)
    si = credit_last_marker(ql, CREDIT_INTERROGATIVES, 0, q_end)
    if si >= 0:
        ei = credit_span_end(ql, si)
        if ql[si:ei].strip() != "":
            c = ql.rfind(":", si, q_end)
            if c >= 0:
                ec = credit_span_end(ql, c + 1)
                if len(credit_split_span(ql, c + 1, ec)) > len(credit_split_span(ql, si, ei)):
                    return [c + 1, ec]
            return [si, ei]
        sw = credit_last_marker(ql, CREDIT_WANT_FOR, si, q_end)
        if sw >= 0:
            return [sw, credit_span_end(ql, sw)]
        c = ql.rfind(":", si, q_end)
        if c >= 0:
            return [c + 1, credit_span_end(ql, c + 1)]
        return [si, ei]
    sp = credit_last_marker(ql, CREDIT_PREFERENCE, 0, q_end)
    if sp >= 0:
        return [sp, credit_span_end(ql, sp)]
    c = ql.rfind(":", 0, q_end)
    if c >= 0:
        return [c + 1, credit_span_end(ql, c + 1)]
    return [0, credit_span_end(ql, 0)]

def credit_name_parts(ql):
    span = credit_name_span(ql)
    return credit_split_span(ql, span[0], span[1])

def credit_tokens(ql):
    out = []
    cur = ""
    start = -1
    for i in range(len(ql)):
        ch = ql[i]
        if ch.isalnum():
            if start < 0:
                start = i
            cur += ch
        else:
            if start >= 0:
                out.append([start, cur])
            cur = ""
            start = -1
    if start >= 0:
        out.append([start, cur])
    return out

def credit_stems(prop):
    words = []
    cur = ""
    for ch in prop.lower().elems():
        if ch.isalnum():
            cur += ch
        else:
            if cur != "":
                words.append(cur)
            cur = ""
    if cur != "":
        words.append(cur)
    return [(w[:-1] if (len(w) > 1 and w.endswith("s")) else w) for w in words]

def credit_phrase_span(toks, prop):
    st = credit_stems(prop)
    if len(st) == 0:
        return None
    for i in range(len(toks) - len(st) + 1):
        ok = True
        for j in range(len(st)):
            t = toks[i + j][1]
            if (t != st[j]) and (t != st[j] + "s"):
                ok = False
                break
        if ok:
            return [i, len(st)]
    return None

def credit_phrase_pos(toks, prop):
    sp = credit_phrase_span(toks, prop)
    if sp == None:
        return -1
    return toks[sp[0]][0]

def credit_shelf_matches(toks, lwords, own_words):
    # [own, other]: a line's shelf word present as a phrase (each token with an optional plural s); a match inside a LONGER
    # match of another line does not count ("phone case" inside "samsung galaxy phone case")
    found = []
    for lk in lwords:
        if not lk.startswith("line"):
            continue
        is_own = lwords[lk] == own_words
        for w in lwords[lk]:
            sp = credit_phrase_span(toks, w)
            if sp != None:
                found.append([sp[0], sp[1], is_own])
    own = False
    other = False
    for f in found:
        dominated = False
        for g in found:
            if (g[2] != f[2]) and (g[1] > f[1]) and (g[0] <= f[0]) and (f[0] + f[1] <= g[0] + g[1]):
                dominated = True
        if not dominated:
            if f[2]:
                own = True
            else:
                other = True
    return [own, other]

def credit_kcls(k):
    if k <= 1:
        return "k1"
    if k == 2:
        return "k2"
    if k == 3:
        return "k3"
    if k <= 5:
        return "k4-5"
    return "k6+"

def credit_ocls(o, k):
    if o < 0:
        return "unplaced"
    if o == 0:
        return "first"
    if o >= k - 1:
        return "last"
    if o == 1:
        return "second"
    return "middle"

def credit_prop(behaviour, key):
    parts = str(behaviour["botisi"][key]["instructions"]).split("'")
    if len(parts) >= 3:
        return parts[-2]
    return ""

def credit_ctx(toks, behaviour, key, k):
    lwords = behaviour.get("line_words", {})
    if "line1" not in lwords:
        return "1L"
    m = credit_shelf_matches(toks, lwords, lwords.get(key, []))
    own = m[0]
    other = m[1]
    if own and other:
        if k == 1:
            return "own+other k1"
        return "own+other list"
    if own:
        return "own"
    if other:
        return "other"
    return "neither"

def credit_decide(behaviour, text, hit_keys):
    ql = text.lower()
    parts = credit_name_parts(ql)
    k = len(parts)
    if k < 1:
        k = 1
    toks = credit_tokens(ql)
    hits = []
    for key in hit_keys:
        label = behaviour["viroju"][key]
        pos = credit_phrase_pos(toks, credit_prop(behaviour, key))
        ordinal = -1
        if pos >= 0:
            for i in range(len(parts)):
                if (parts[i][0] <= pos) and (pos < parts[i][1]):
                    ordinal = i
        ctx = credit_ctx(toks, behaviour, key, k)
        if ordinal < 0:
            rank = 1000000000 + (pos if pos >= 0 else 0)
        else:
            rank = ordinal * 100000 + pos
        hits.append([rank, key, label, ordinal, ctx])
    hits = sorted(hits)
    u = credit_draw(state_get("messages_used", 0)) / 10000.0
    acc = 0.0
    reach = 1.0
    kc = credit_kcls(k)
    for h in hits:
        label = h[2]
        vis = CREDIT_F_CTX[h[4]]
        if label >= 0:
            p = CREDIT_P_ORD[kc][credit_ocls(h[3], k)]
            p_credit = vis * p
            p_stop = vis * (1.0 - p)
        else:
            p_credit = 0.0
            p_stop = vis * CREDIT_DECOY_CONSUME
        if u < acc + reach * p_credit:
            return label
        if u < acc + reach * (p_credit + p_stop):
            return -2
        acc += reach * (p_credit + p_stop)
        reach *= (1.0 - p_credit - p_stop)
    return -2

# ---------------------------------------------------------------- grading
OPEN_TOOLS = ["OfferShow", "FullSpecs"]  # tools whose call counts as opening a pointer-chain listing
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

def fits_hold(lines, perm, fitok):
    # cross-line fits (R15 field: every violating cart is request_not_met): the accessory line must fit the device line it was told to fit
    inv = {}
    for i in range(len(perm)):
        inv[perm[i]] = i
    for pair in fitok:
        ia = inv.get(pair["a"])
        ib = inv.get(pair["b"])
        if (ia == None) or (ib == None):
            continue
        allowed = pair["ok"].get(lines[ia]["id"])
        if (allowed != None) and (lines[ib]["id"] not in allowed):
            return False
    return True

def lines_claim_answer_lines(lines, answer_lines, key, gone, fitok = []):
    if len(lines) != len(answer_lines):
        return False
    for perm in permutations_of(len(lines)):
        ok = True
        for i in range(len(lines)):
            target = answer_lines[perm[i]]
            if (lines[i]["id"] not in target[key]) or (lines[i]["id"] in gone) or (lines[i]["quantity"] != target["kudi"]):
                ok = False
                break
        if ok and fits_hold(lines, perm, fitok):
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

def accepted(slot, lines, reason, key, ov, gone, dyn):
    if reason == "decline":
        if slot.get("nodecline", False):
            return False
        if not dyn:
            return slot["tele"]
        cheapest = cheapest_total(slot, ov, gone)
        return (cheapest == None) or (cheapest > slot["suhe"])
    return lines_claim_answer_lines(lines, slot["tufa"], key, gone, slot.get("fitok", [])) and (order_total(lines, slot["fari"], ov) <= slot["suhe"])

def process_complete(episode, answer, reason):
    opened = {}
    revealed = {}
    for record in episode:
        if record["kind"] == "action":
            tool = record.get("tool")
            args = record.get("args", {})
            if tool in OPEN_TOOLS:
                opened[args.get("ItemIdCode", args.get("ListingNumber", ""))] = True
        elif record["kind"] == "event":
            data = record["data"]
            if (type(data) == "dict") and ("revealed_need" in data):
                revealed[data["revealed_need"]] = True
    for chain in answer.get("refs", []):
        for item_id in chain:
            if item_id not in opened:
                return False
    if (reason == "order") and ("view_after_add" in answer.get("process_rules", [])):
        # request-stated rule (r16 field, derive_specs_r16.py): each ordered listing's offer page is viewed after it was last put in the basket
        idx = 0
        last_add = {}
        last_view = {}
        for record in episode:
            if record["kind"] == "action":
                idx += 1
                args = record.get("args", {})
                if (record.get("tool") == "StashToBasket") and (args.get("ItemHowMany", 0) > 0):
                    last_add[args.get("Product", "")] = idx
                elif record.get("tool") == "OfferShow":
                    last_view[args.get("ItemIdCode", "")] = idx
        for line in episode[-1]["order"]["lines"]:
            if last_view.get(line["id"], -1) <= last_add.get(line["id"], 0):
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
    mask = 0
    for record in episode:
        if record["kind"] == "event":
            data = record["data"]
            if (type(data) == "dict") and ("situ" in data):
                mask = mask + [1, 2, 4, 8, 16, 32][data["situ"]]
                if data.get("item") != None:
                    if data.get("price_to") != None:
                        ov[data["item"]] = data["price_to"]
                    if data.get("kind") == "stock":
                        gone.append(data["item"])
    fired = mask != 0
    dova = answer["dova"]
    slot = dova[mask] if mask < len(dova) else dova[0]
    dyn = bool(answer.get("dynamic", False))
    if (reason == "order") or slot["tele"]:
        if not process_complete(episode, answer, reason):
            return {"category": "process requirement missed", "score": 0}
    jufuli = slot["jufuli"]
    # jufuli is calibrated per event bitmask at build time from the passing / not_the_best_option field carts (budget / drop slots carry their own cap and relaxed lists)
    verdict = 1 if accepted(slot, lines, reason, "lita", ov, gone, dyn and fired) else 0
    if (verdict == 1) and (reason == "order") and (order_total(lines, slot["fari"], ov) > jufuli):
        verdict = 2
    if (verdict == 1) and (reason == "order"):
        ranked = False
        for line in slot["tufa"]:
            if "best" in line:
                ranked = True
        if ranked:
            # "least height is best" / "most width": an acceptable line outside the best set is a not-the-best-option order
            best_lines = [{"kudi": line["kudi"], "best": line.get("best", line["lita"])} for line in slot["tufa"]]
            if not lines_claim_answer_lines(lines, best_lines, "best", gone, slot.get("fitok", [])):
                verdict = 2
    if verdict == 1:
        return {"category": None, "score": 1}
    if reason == "order":
        for line in lines:
            if line["id"] in gone:
                # R16 field (t-ece5a5fba1): an order still holding the listing that sold out is `changes missed` (5 of 6), not R15's `request not met`
                return {"category": "changes missed", "score": 0}
    if (verdict == 0) and accepted(slot, lines, reason, "reza", ov, gone, dyn and fired):
        return {"category": "needs not found", "score": 0}
    if verdict == 2:
        return {"category": "not the best option", "score": 0}
    return {"category": "request not met", "score": 0}

