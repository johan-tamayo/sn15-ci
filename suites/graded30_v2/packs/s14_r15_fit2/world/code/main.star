# Race-15 Starlark World (`s14_r15`, 45 Open Tasks, `w-forge-s14-r15`)
# Reproduces the Race-15 mechanics seen in the released open episodes:
#   * 8 tools: lookupItems, listRange, showPage, weighItems, stashItem (replaces the cart), bagItems, closeRequest (commit|skip), askBuyer
#   * lookupItems: AND over the first 8 words ("( ) , - . : ; |" split), BM25 k1 1.5 / b 0 tiers in id order, top 1000, 7 cards per
#     page, pages 1..7; listRange: the whole shelf id-sorted, 7 per page, pages 1..7, count = live shelf size   (fit: runs/forge3/HANDOVER.md)
#   * cards are pipe-delimited strings (shop_comments + facts only on showPage / weighItems)
#   * 3-message allowance (askBuyer cost 1, budget 3)
#   * events: trigger finish (first commit with a cart refused once), first_add (first non-empty stash; echo on the next call),
#     after_reveal (first slot reveal; echo on the next call); kinds budget (new cap) | drop (relaxed clause) | stock (carted line sells out)
#   * persona: 12 reveal frames, nopref, DNU (dnu_default per task share)
#   * askBuyer credit: the live labeler's position / shelf-context rule, one PRNG draw per message (fit: runs/forge4/HANDOVER.md)
#   * graded: pointer chains opened via showPage / weighItems, hidden needs via askBuyer, one answer slot per fired-event bitmask

TEXT_INDEX = "jasu"
CATEGORY_INDEX = "nemogi"
BRAND_INDEX = "kojefe"
PAGE_ROWS = 7
MAX_PAGE = 7
TEXT_HITS_CAP = 1000  # field counts saturate at 1000 (692 recorded queries report exactly 1000)
ALL_TERMS = True
SHELF_LIVE_COUNT = {"business laptops": 971, "face scrubs & exfoliators": 842, "google pixel cases": 703, "laptop and tablet screen protectors": 242, "laptop chargers and adapters": 953, "laptop replacement parts": 893, "macbooks": 156, "ottomans": 342, "pa and studio speakers": 880, "phone and tablet screen protectors": 798, "phone cases": 506, "phone screen protectors": 278, "samsung galaxy phone cases": 788, "smartphones": 949, "vinegar & cooking wine": 839}  # live shelf sizes (field listRange count)
TOOLS = ["lookupItems", "listRange", "showPage", "weighItems", "stashItem", "bagItems", "closeRequest", "askBuyer"]

def start(envelope):
    params = envelope["params"]
    for name in TOOLS:
        set_cost(name, "steps", 1)
    set_budget("steps", params.get("step_budget", 38))
    msg_cap = params.get("message_budget", 3)
    set_cost("askBuyer", "messages", 1)
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
        if event.get("over_cap_only", False) and (len(lines) > 0) and (cart_total(lines, ov) <= event["new_cap"]):
            continue  # calibration (t-c217fa5565): a NON-EMPTY cart at or under the new limit does not voice the budget sentence (47/48 field refusals); an empty-cart close voices it (24/24; runs/forge3/task4_r15_notice_timing.log)
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
        # field (R15 open episodes): a wrapped showPage / askBuyer carries the bare string in `jezudo` (1067 + 36 str vs 1 dict), not {"value": ...}
        inner = result["value"] if ((type(result) == "dict") and (len(result) == 1) and ("value" in result)) else result
        return {"harafo": [p[1] for p in ready], "jezudo": inner}
    return result

def desc_of(row):
    text = row.get("description")
    if type(text) != "string":
        return ""
    if len(text) > 1200:
        return text[:1200]
    return text

def card_str(row, full):
    parts = [
        "ref_ref: " + str(row.get("id")),
        "sold_by_name: " + str(row.get("merchant")),
        "title: " + str(row.get("title")),
        "brand: " + str(row.get("maker")),
        "price: " + str(eff_price(row)),
    ]
    if full:
        parts.append("shop_comments: " + str(row.get("seller_notes_text")))
    parts.append("on_hand: " + str(eff_stock(row)))
    parts.append("category: " + str(row.get("category")))
    if full:
        facts = row.get("facts", {})
        parts.append("facts: " + "; ".join([k + "=" + str(facts[k]) for k in sorted(facts.keys())]))
    parts.append("item_blurb: " + desc_of(row))
    return " | ".join(parts)

def text_search_ids(query):
    # live race-15 lookupItems (runs/forge3/HANDOVER.md, fitted on every recorded search): lowercase; "( ) , - . : ; |" become spaces
    # ("'" "&" "/" and the double quote do NOT: Niko's, scrubs & exfoliators, charger/adapter each count as ONE word and the analyzer
    # handles them); split on spaces; dedup; only the FIRST 8 words are searched, AND over all their terms; the engine ranks by
    # BM25 k1 1.5 / b 0 (equal-score tiers in id order), top 1000
    query = query.lower()
    for ch in ["(", ")", ",", "-", ".", ":", ";", "|"]:
        query = query.replace(ch, " ")
    tokens = []
    for tok in query.split(" "):
        if (len(tok) >= 1) and (tok not in tokens):
            tokens.append(tok)
    if tokens == []:
        return []
    found = search(TEXT_INDEX, " ".join(tokens[:8]), {"all_terms": ALL_TERMS, "k": TEXT_HITS_CAP})
    if found["ok"] == False:
        return []
    ranked = sorted(found["hits"], key = lambda h: (-h["score"], h["id"]))
    out = []
    for hit in ranked:
        row = row_of(hit["id"])
        if row == None:
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

def page_of(ids, page, count = None):
    if page == None:
        page = 1
    if count == None:
        count = len(ids)
    begin = (page - 1) * PAGE_ROWS
    rows = ids[begin:begin + PAGE_ROWS]
    onward = (page + 1) if ((page * PAGE_ROWS < count) and (page < MAX_PAGE)) else None
    return {
        "count": count,
        "matches_set": [card_str(row_of(i), False) for i in rows],
        "next_page": onward,
    }

def tool_lookup_items(args):
    words = str(args.get("searchForInput", "")).strip()
    ids = text_search_ids(words) if words != "" else []
    return page_of(ids, args.get("viewPageNumber"))

def tool_list_range(args):
    group = str(args.get("itemSection", "")).lower().strip()
    ids = group_ids(group)
    # live shelf size (field listRange `count`, constant per shelf): the catalog holds the seen listings only, the pages 1..7 are the
    # 49 lowest ids of the shelf and reproduce the field exactly (runs/forge3/HANDOVER.md)
    return page_of(ids, args.get("leaf"), max(len(ids), SHELF_LIVE_COUNT.get(group, 0)))

def tool_show_page(args):
    row = row_of(args.get("listingCode", ""))
    if row == None:
        return {"call_failure": "E17"}
    return {"value": card_str(row, True)}

def tool_weigh_items(args):
    rows = []
    seen = []
    for pid in args.get("pickedIds", []):
        row = row_of(pid)
        if (row == None) or (pid in seen):
            continue  # field: an id the store does not hold is skipped, a repeated id is returned once (page_fidelity.py: 61 recorded weighItems calls, scratch/wi_probe.py)
        seen.append(pid)
        rows.append(card_str(row, True))
    return {"matches_set": rows}

def bag_summary():
    lines_out = []
    total = 0
    for line in basket_get():
        row = row_of(line["id"])
        price = eff_price(row)
        total += price * line["quantity"]
        lines_out.append({
            "amount_held": line["quantity"],
            "price": price,
            "ref_ref": line["id"],
            "title": row.get("title"),
        })
    return {"amount_due": total, "selection": lines_out}

def tool_bag_items(args):
    return bag_summary()

def tool_stash_item(args):
    wanted = {}
    order = []
    for entry in args.get("newSelection", []):
        pid = entry.get("productNumber", "")
        if row_of(pid) == None:
            return {"call_failure": "E17"}
        if pid not in wanted:
            order.append(pid)
            wanted[pid] = 0
        wanted[pid] = wanted[pid] + entry.get("amount", 0)
    for ln in basket_get():
        basket_set(ln["id"], 0)
    for pid in order:
        if wanted[pid] > 0:
            basket_set(pid, wanted[pid])
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
    return bag_summary()

def tool_close_request(args):
    if args.get("byType") == "skip":
        request_decline()
        return {"applied": True}
    lines = basket_get()
    if len(lines) == 0:
        return {"call_failure": "E19"}
    request_order(lines)
    return {"applied": True}

def tool_ask_buyer(args):
    state_set("messages_used", state_get("messages_used", 0) + 1)
    return {"value": send_message(args.get("bodyText", ""))}

def call(handler, args):
    return pending_wrap({
        "lookup_items": tool_lookup_items,
        "list_range": tool_list_range,
        "show_page": tool_show_page,
        "weigh_items": tool_weigh_items,
        "stash_item": tool_stash_item,
        "bag_items": tool_bag_items,
        "close_request": tool_close_request,
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
            if tool == "showPage":
                opened[args.get("listingCode", "")] = True
            elif tool == "weighItems":
                for pid in args.get("pickedIds", []):
                    opened[pid] = True
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
    if (verdict == 0) and accepted(slot, lines, reason, "reza", ov, gone, dyn and fired):
        return {"category": "needs not found", "score": 0}
    # R15 field: 0 of 4490 non-process fails carry a `changes missed` label; an order holding a sold-out listing is `request not met`
    if verdict == 2:
        return {"category": "not the best option", "score": 0}
    return {"category": "request not met", "score": 0}
