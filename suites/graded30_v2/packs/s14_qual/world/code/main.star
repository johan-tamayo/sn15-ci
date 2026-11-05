# Qualifying Twin World (`s14_qual`, `w-2385fe7c5e6d`)
# Reproduces the exact Qualifying world (`w-2385fe7c5e6d`, 8 tools, 38 steps, 3 messages):
#   * `find_goods`: 4-row pagination (`vuvepa4`, `vuvepa8`, ..., `vuvepa68`), `count_count` capped at 750,
#     results ordered by price ascending (preserving BM25 rank on ties -> 98.6% page-1 overlap with live `w-2385fe7c5e6d`)
#   * `detail_product`: returns `about_text`, `aisle_name`, `brand`, `facts`, `id`, `name`, `price`, `stock_ok`
#   * `contrast_products`: accepts 1..4 IDs (`>4` returns `{"issue": "too many items, remove some"}`)
#   * `put_quantity`: `verb_type` in `["plus", "discard"]`, returns `{"id": refube, "qty": tozi}`
#   * `trolley_contents`: returns `{"grand_total_cost": tasihu, "lines_lines": [...]}`
#   * `contact_customer`: metered 3 messages (`titu`), returns `{"value": reply}`
#   * `submit_purchase` / `decline`: returns `{"fine": True}` (`decline` checks `explanation_note` for leaked catalog IDs)

def start(takipi):
    set_cost("write_customer", "titu", 1)
    set_cost("shopperMessage", "titu", 1)
    set_cost("contact_customer", "titu", 1)
    set_budget("titu", 3)
    state_set("topola", takipi["params"].get("kule", []))
    state_set("dulu", [None for nefeso in state_get("topola")])
    state_set("jomune", state_get("dulu"))
    vihepa(takipi["params"]["bezifa"])
    return None

def zite(pevu):
    pevu = pevu.lower()
    for bisi in ["(", ")", ",", "-", ".", "/", ":", ";", "|"]:
        pevu = pevu.replace(bisi, " ")
    zupapi = []
    for gelima in pevu.split(" "):
        if (len(gelima) >= 2) and (gelima not in zupapi):
            zupapi.append(gelima)
    if zupapi == []:
        return []
    horisi = search("jasu", " ".join(zupapi[:6]), {"all_terms": True, "k": 750})
    if horisi["ok"] == False:
        return []
    return [zeroju["id"] for zeroju in horisi["hits"] if (catalog_get(zeroju["id"]) != None)]

def hifapu(jopapa):
    jovapu = []
    for rano in search("nemogi", jopapa, {"all_terms": True, "k": 1000}).get("hits", []):
        luji = catalog_get(rano["id"])
        if (luji != None) and ((type(luji.get("category")) == "string") and (luji["category"].lower().strip() == jopapa)):
            jovapu.append(rano["id"])
    return jovapu

def horo(jopapa):
    jovapu = []
    for rano in search("kojefe", jopapa, {"all_terms": True, "k": 1000}).get("hits", []):
        luji = catalog_get(rano["id"])
        if (luji != None) and ((type(luji.get("brand")) == "string") and (luji["brand"].lower().strip() == jopapa)):
            jovapu.append(rano["id"])
    return jovapu

def jemumi(refube):
    for dahe in basket_get():
        if dahe["id"] == refube:
            return dahe["quantity"]
    return 0

def _clean_facts(fx):
    if type(fx) != "dict":
        return {}
    out = {}
    for k in fx:
        if k != "_idx_terms":
            out[k] = fx[k]
    return out

def _qual_row(bivo):
    return {
        "about_text": bivo.get("description"),
        "aisle_name": bivo.get("category"),
        "brand": bivo.get("brand"),
        "id": bivo.get("id"),
        "name": bivo.get("title"),
        "price": bivo.get("price"),
        "stock_ok": bivo.get("in_stock"),
    }

def _qual_find(zilo):
    raw_ids = zite(zilo.get("free_search_for", ""))
    bivo = sorted(raw_ids, key=lambda pid: gegufa(pid).get("price", 0))
    tok = zilo.get("token_token", "")
    off = 0
    if (tok != None) and (tok != ""):
        if (type(tok) != "string") or (not tok.startswith("vuvepa")) or (not tok[6:].isdigit()):
            return {"issue": "no article has that id"}
        off = int(tok[6:])
        if (off <= 0) or ((off % 4) != 0) or (off >= len(bivo)):
            return {"issue": "no article has that id"}
    puva = bivo[off:off + 4]
    nxt = ("vuvepa" + str(off + 4)) if (((off + 4) < len(bivo)) and (off < 68)) else None
    return {
        "count_count": len(bivo),
        "further": nxt,
        "listings_set": [_qual_row(gegufa(luji)) for luji in puva],
    }

def _qual_detail(zilo):
    bivo = gegufa(zilo["chosen_item_id"])
    if bivo == None:
        return {}
    res = _qual_row(bivo)
    res["facts"] = _clean_facts(bivo.get("facts"))
    return res

def _qual_contrast(zilo):
    ids = zilo.get("chosen_listings", [])
    if len(ids) > 4:
        return {"issue": "too many items, remove some"}
    out = []
    for pid in ids:
        bivo = gegufa(pid)
        if bivo != None:
            r = _qual_row(bivo)
            r["facts"] = _clean_facts(bivo.get("facts"))
            out.append(r)
    return {"listings_set": out}

def _qual_put(zilo):
    refube = zilo["article"]
    if gegufa(refube) == None:
        return {"issue": "NO_MATCH"}
    qty = zilo.get("count_needed", 1)
    if zilo["verb_type"] == "plus":
        tozi = min(5, jemumi(refube) + qty)
    else:
        tozi = max(0, jemumi(refube) - qty)
    basket_set(refube, tozi)
    return {"id": refube, "qty": tozi}

def _qual_trolley(zilo):
    geveme = []
    tasihu = 0
    for dahe in basket_get():
        bivo = gegufa(dahe["id"])
        tasihu += bivo.get("price", 0) * dahe["quantity"]
        geveme.append({
            "id": dahe["id"],
            "name": bivo.get("title"),
            "price": bivo.get("price", 0),
            "qty": dahe["quantity"],
        })
    return {"grand_total_cost": tasihu, "lines_lines": geveme}

def _qual_msg(zilo):
    return {"value": send_message(zilo["note_text"])}

def _qual_submit(zilo):
    majuno = basket_get()
    if len(majuno) == 0:
        return {"issue": "nothing selected"}
    request_order(majuno)
    return {"fine": True}

def _qual_decline(zilo):
    if "explanation_note" in zilo:
        ledger_append({"vefagi": zilo["explanation_note"]})
    request_decline()
    return {"fine": True}

def bekika(jame, zilo):
    return {
        "_qual_find": _qual_find,
        "_qual_detail": _qual_detail,
        "_qual_contrast": _qual_contrast,
        "_qual_put": _qual_put,
        "_qual_trolley": _qual_trolley,
        "_qual_msg": _qual_msg,
        "_qual_submit": _qual_submit,
        "_qual_decline": _qual_decline,
    }[jame](zilo)

def call(jame, zilo):
    return pemiba(bekika(jame, zilo))

def juli(jozo, rani, zagi):
    vipo = state_get("topola")[jozo]
    netu = state_get("dulu")
    netu[jozo] = rani
    state_set("dulu", netu)
    kehodo = zagi[0] if zagi else None
    vebosa = None if (kehodo == None) else gegufa(kehodo)
    if ("givo" in vipo) and (vebosa != None):
        hunuzu = state_get("povu", {})
        zape = hunuzu.get(kehodo, {})
        for kefa in vipo["givo"]:
            if (kefa["rozaku"] == "price") and ("mult_pct" in kefa):
                cur_p = zape.get("price", vebosa.get("price", 0))
                zape["price"] = (cur_p * kefa["mult_pct"]) // 100
            else:
                zape[kefa["rozaku"]] = kefa["zobuno"]
        hunuzu[kehodo] = zape
        state_set("povu", hunuzu)
        netu = state_get("jomune")
        netu[jozo] = kehodo
        state_set("jomune", netu)
    else:
        kehodo = None
    ledger_append({"dazi": kehodo, "situ": jozo})
    if "futaka" in vipo:
        state_set("puli", state_get("puli", []) + [vipo["zabovu"]])

def turn():
    zufe = state_get("topola", [])
    netu = state_get("dulu", [])
    sibara = counters()
    zagi = [mivufi["id"] for mivufi in basket_get()]
    rikari = len(state_get("tuse", []))
    for jozo in range(len(zufe)):
        vipo = zufe[jozo]
        if (netu[jozo] == None) and (((("zinupa" in vipo) and (sibara["step"] >= vipo["zinupa"])) or (("ruto" in vipo) and ((sibara["step"] <= vipo["fakoso"]) and zagi))) or (("totepo" in vipo) and ((sibara["step"] <= vipo["fakoso"]) and (rikari >= vipo["totepo"])))):
            juli(jozo, sibara["step"], zagi)

def can_finish(soge):
    zufe = state_get("topola", [])
    rani = counters()["step"]
    zagi = [mivufi["id"] for mivufi in soge.get("lines", [])]
    for jozo in range(len(zufe)):
        if state_get("dulu")[jozo] == None:
            juli(jozo, rani, zagi)
    netu = state_get("dulu", [])
    jukake = []
    for jozo in range(len(zufe)):
        vipo = zufe[jozo]
        if netu[jozo] == rani:
            if ("salaho" in vipo) or (state_get("jomune")[jozo] in zagi):
                jukake.append(vipo["zabovu"])
    return {"observation": jukake if jukake else None, "ok": not jukake}

def pemiba(soge):
    fehi = state_get("puli", [])
    if fehi:
        state_set("puli", [])
        return {"zovi": soge, "lokabe": fehi}
    return soge

def gegufa(jozo):
    zape = catalog_get(jozo)
    hunuzu = state_get("povu", {}).get(jozo)
    if (zape == None) or (hunuzu == None):
        return zape
    zape = dict(zape)
    zape.update(hunuzu)
    return zape

def vihepa(kojune):
    state_set("duri", kojune)
    state_set("tuse", [])
    zepu = len(kojune["duno"])
    nube = list(range(zepu))
    for mado in range(zepu - 1):
        zunobu = mado + rand_below(zepu - mado)
        fataho = nube[mado]
        nube[mado] = nube[zunobu]
        nube[zunobu] = fataho
    kiha = "".join(["PSL39FKNYXC7ZMB8JU6RTGQEW42D5H"[rand_below(30)] for toku in range(12)])
    hore = dict(kojune["vovafo"])
    for mado in range(zepu):
        hore[kojune["melugo"][mado]] = kojune["ligubo"][nube[mado]]
    state_set("pugeze", {"pogila": hore, "sateje": (((kojune["meba"] + "\n".join([(kojune["melugo"][mado] + ": ") + kojune["duno"][nube[mado]] for mado in range(zepu)])) + kojune["fase"]) + kiha) + "\n", "tufe": kiha})

def message(mokame):
    kojune = state_get("duri")
    duropi = state_get("pugeze")
    mele = mokame
    for rumuro in range(len(mokame)):
        if duropi["tufe"] not in mele:
            break
        mele = "".join(mele.split(duropi["tufe"]))
    nuvila = -2
    for geki in kojune["kubono"]:
        if "meza" in geki:
            kuro = mifa(kojune, geki, mokame)
            if kuro != None:
                nuvila = kuro[0]
                break
        else:
            vupaza = model_call(geki["rahi"], (((duropi["sateje"] + mele) + "\n") + duropi["tufe"]) + kojune["sufe"], geki["gutubi"])
            nuvila = duropi["pogila"].get(vupaza["text"].strip(), -2) if vupaza["ok"] else -2
            if nuvila != -2:
                break
    fotivi = kojune["sase"][nuvila + 2]
    if nuvila >= 0:
        state_set("tuse", state_get("tuse") + [nuvila])
        ledger_append({"pifi": nuvila})
    return fotivi[rand_below(len(fotivi))]

def mifa(kojune, geki, mokame):
    vupaza = model_decide(geki["rahi"], {"message": mokame}, kojune["botisi"], geki["gutubi"])
    if not vupaza["ok"]:
        return None
    nafa = vupaza["answers"]
    if (type(nafa) == "dict") and ("answers" in nafa):
        nafa = nafa["answers"]
    if type(nafa) != "dict":
        return None
    pameti = {}
    for zune in kojune["botisi"]:
        dozipi = nafa.get(zune)
        if (type(dozipi) != "dict") or (type(dozipi.get("noul")) not in ["float", "int"]):
            return None
        kuro = dozipi["noul"]
        if ((kuro < 0) or (kuro > 1)) or ((kuro > geki["devizu"]) and (kuro < geki["meza"])):
            return None
        pameti[zune] = kuro
    kuro = [kojune["viroju"][zune] for zune in kojune["viroju"] if (pameti[zune] >= geki["meza"])]
    if len(kuro) > 1:
        return None
    nuvila = -1 if ((pameti[kojune["jekaro"]] >= geki["meza"]) or (kuro == [])) else kuro[0]
    return [nuvila]

def grade(guko, tijo):
    seki = guko[-1]
    lesomo = seki["reason"]
    if (lesomo != "order") and (lesomo != "decline"):
        return {"category": "did not finish", "score": 0}
    hefo = seki["order"]["lines"] if (lesomo == "order") else []
    popugu = 0
    tano = [0]
    nevare = []
    raveko = {}
    for jugota in guko:
        bukolu = jugota["kind"]
        if bukolu == "event":
            fugu = jugota["data"]
            if "situ" in fugu:
                popugu = popugu | [1, 2, 4][fugu["situ"]]
                tano.append(popugu)
                if fugu.get("dazi") != None:
                    nevare.append([fugu["situ"], fugu["dazi"]])
        elif bukolu == "action":
            raveko = jugota["args"]
    dofabo = tijo["dova"][popugu]
    dofabo = bumuzu(dofabo, nevare, tijo)
    mihahe = 1 if ligeta(dofabo, hefo, lesomo, "lita") else 0
    if ((mihahe == 1) and (lesomo == "order")) and (tuzo(hefo, dofabo["fari"]) > dofabo["jufuli"]):
        mihahe = 2
    if mihahe > 0:
        if mihahe == 1:
            return {"category": None, "score": 1}
    liti = [pusa for pusa, medi in (("needs not found", (mihahe == 0) and ligeta(dofabo, hefo, lesomo, "reza")), ("changes missed", (mihahe == 0) and any([ligeta(tijo["dova"][ninini], hefo, lesomo, "lita") for ninini in tano[:-1]])), ("not the best option", mihahe == 2), ("request not met", mihahe == 0)) if medi]
    return {"category": liti[0], "score": 0}

def bumuzu(dofabo, nevare, tijo):
    kuhufu = dict(dofabo.get("homu", []))
    if (not nevare) or (not kuhufu):
        return dofabo
    dofabo = dict(dofabo)
    pana = dict(dofabo["fari"])
    lori = []
    orig_k = dofabo["tufa"][0]["kudi"]
    orig_lino = [rafa for rafa in dofabo["tufa"][0]["lita"] if ((orig_k * dofabo["fari"][rafa]) <= dofabo["suhe"])]
    orig_min = min([orig_k * dofabo["fari"][misa] for misa in orig_lino]) if orig_lino else dofabo["suhe"]
    for nige in nevare:
        if nige[0] in kuhufu:
            mv = kuhufu[nige[0]]
            if mv == 0:
                lori.append(nige[1])
            elif (nige[1] in pana) and (mv > 0):
                pana[nige[1]] = (pana[nige[1]] * mv) // 100
    dusula = dict(dofabo["tufa"][0])
    dusula["lita"] = [rafa for rafa in dusula["lita"] if (rafa not in lori)]
    dusula["reza"] = [rafa for rafa in dusula["reza"] if (rafa not in lori)]
    dofabo["tufa"] = [dusula]
    dofabo["fari"] = pana
    lino = [rafa for rafa in dusula["lita"] if ((dusula["kudi"] * pana[rafa]) <= dofabo["suhe"])]
    if not lino:
        if lori:
            dofabo["tele"] = True
        return dofabo
    if dofabo["jufuli"] < dofabo["suhe"]:
        cand_juf = min([dusula["kudi"] * pana[misa] for misa in lino])
        if (lori and (dofabo["jufuli"] >= orig_min)) or (cand_juf < dofabo["jufuli"]):
            dofabo["jufuli"] = cand_juf
    return dofabo

def tuzo(negu, pana):
    hotisu = 0
    for rafa in negu:
        hotisu += pana[rafa["id"]] * rafa["quantity"]
    return hotisu

def gano(hefo, fivuli, suga):
    return ((len(hefo) == 1) and (len(fivuli) == 1)) and ((hefo[0]["id"] in fivuli[0][suga]) and (hefo[0]["quantity"] == fivuli[0]["kudi"]))

def ligeta(dofabo, hefo, lesomo, suga):
    if lesomo == "decline":
        return dofabo["tele"]
    return gano(hefo, dofabo["tufa"], suga) and (tuzo(hefo, dofabo["fari"]) <= dofabo["suhe"])
