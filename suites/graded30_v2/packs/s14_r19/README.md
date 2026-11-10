# Race-19 Forged Field Suite (`s14_r19`, 45 Open Tasks, `w-forge-s14-r19`)

## 1. Overview & World Mechanics
- **Pack Path**: `~/sn15-ops/suites/graded30_v2/packs/s14_r19` (`pack_id: p-forge-s14-r19`, `world_id: w-forge-s14-r19`), built by `tools/forge/r19_forge/build_s14_r19.py` from `runs/r19_forge/` + `runs/r19forge1/r19_task_specs_v2.json` (lane r19forge1, FORGE19; a port of `tools/forge/r17_forge/` with race 18's batch view and price moves and race 16's one-at-a-time pool).
- **Corpus Provenance**: all `11,250` released Race-19 open episodes (250 agents x 45 tasks); `3,008` passing order episodes across `26` tasks, `216` passing declines on `1` decline task, `18` tasks with 0 passes.
- **`request_text` = race 19's PUBLIC request text, VERBATIM on 45/45 tasks**: race 19 released none (`query` is null on every episode); field agent `06af1dc4-7ecede47` sends its whole task input as numbered JSON chunks in the `message` tool's `textText` argument (a one-element list each; the runtime rejects the call - `$.textText: expected string` - and the released episode keeps the argument) on 45 tasks (`runs/r19_forge/r19_task_inputs.json`, `tools/forge/r19_forge/task_inputs_r19.py`); `34` texts are corroborated word for word by a second echo agent (`06af164c-272e7e66`, `tools/forge/public_queries.py --race 19`). The spec is forged FROM the text (`tools/forge/r19_forge/specs_r19.py`).
- **Tool declarations are the live ones** (same echo, `runs/r19_forge/r19_field_tools.json`): names, descriptions, argument schemas and order. Each task carries `params.policy_max_steps` = the live `policy_view.max_steps` of that task (43 x32, 98 x2, 110 x1, 126 x2, 138 x3, 141 x2, 153 x1, 165 x1, 181 x1); `simrace/world_sim.py` passes it as `policy_view.max_steps` (opt-in key added for `s14_r18`; no simulator change was needed for this pack).
- **Truth**: `lita` = shelf listings matching stated + hidden clauses (`clauses_r19.py`: the card's own key decides; an alias key is read only when the own key is absent; when a card shows no attribute for the property, the value in its title; amounts with unit conversion - on the one-line tasks this finds 79/79 field-accepted and admits 0/12 field-refused listings, `truth_eval_r19.py`) UNION every passing / `not_the_best_option` field cart item on that line MINUS listings a process-complete `request_not_met` order isolates; `reza` = stated-only fits UNION lita; one answer slot per event bitmask. Listings no field agent opened (`1,747` of `4,615`) carry no attributes: `showPage` shows them with an empty `facts` and they are never acceptable by clause.
- **Catalog**: all `4,615` listings seen in the episodes (`2,868` full cards, `577` with a seller note in `shop_good_to_know`); 0 listings whose recorded card varies; every listing is in stock in every episode (the requests' "leave aside anything that has sold out" never bites); 43 listings were seen at a second price - each time the first listing of an order list after a price notice.
- **Task mix**: 1L `22` / 2L `4` / 3L `9` / 4L `5` / 5L `4` / 6L `1`; hidden needs on `30/45` tasks (49 needs; 8 tasks carry one more need no field agent ever got revealed: `t-16b268420f`, `t-3c3213f972`, `t-4b1fcfe675`, `t-4f0d9fb1e4`, `t-521e07d9ca`, `t-676a0978ee`, `t-b067f89bb0`, `t-ea0ddfecfd`), reply-by-reference on `3/45`, reference chains on `6/45` (3 stated in the request, 3 revealed; 1 to 5 pages), store notices on `19/45` (all one-line: budget 16, drop 3, price 6), lowest-price tasks `11`, a ranked wish on `1`, decline-correct tasks `1`, did-not-understand tasks `21`, mattress compatibility on `2` tasks (6 pairs), car compatibility on `11`, conditional clauses on `7`, a per-line cap on `1`.
- **8 Race-19 Tools (`tools.json`)**: `huntListings` (search: 3 rows from the row offset `rowStart` 0..21, `num_hits_count` capped at 200, `onward` = `rowStart + 3` while more rows remain and `rowStart + 3 <= 21`, `findQ` <= 87 chars - at most 24 rows of a search can be seen), `closeTask` (`variant` checkout: an empty order list -> `{"issue_text": "E80"}`; no_order: a decline), `set` (`place` ADDS `itemUnits` (default 1) to the line, a line over 9 -> `E81`; `release` subtracts `itemUnits` (default 1), never below 0; unknown id -> `E80`; answers `{catalog_product_id, pieces_total}`), `balanceNow` (message meter `virase`), `bagList` (`selection` in the order the lines were first held + `grand_total_total`), `message` (2 replies, then `{"error": "budget_exceeded"}`), `showPage` (full card; unknown id -> `{"issue_text": "E80"}`), `matchUpItems` (the full cards of 1..5 ids in the order asked, each once; ids the store does not hold in `ids_unknown`).
- **Split view**: a `huntListings` row is `brand, catalog_product_id, category, charge, in_stock, listing_label, narrative, seller`; `facts` and `shop_good_to_know` (the seller's blurb, where the pointer sentences and pairing rules sit) appear only on `showPage` / `matchUpItems`.
- **Compatibility is strict**: a car part must SAY it fits the car's family (`narrative` opens with `Fits: every BER70xx model.` for a BER7010; a listing that names no car is not compatible); a headboard / bedding set / mattress pad fits a mattress when its `Fits: LIZ6240.` or `Fits: Nelin 624.` names the mattress's `Model number: LIZ6240. Also sold as Nelin 624.` (the number or the other name).
- **Reference chains**: a reference names a page by seller, shelf and attributes (`<relation> what is written on the page for the <shelf> from <Seller> that has <attrs>, either outright or by naming another listing`); decoy pages of the same seller sit beside it (`A set version exists elsewhere.`). The pointer sentence is in `shop_good_to_know` (`For type, refer to the other Bedding Sets from Vexrazen, for adults, unisex recommended gender, 350 thread count, not to this item.`). Relations: `matching` (that value), `something other than` (any other value), `works well with` / `able to work well with` (the page states a value AND a pairing rule, e.g. `The store's rule for make pairs isuzu with hyundai and mazda with mitsubishi.` or `sold as 1 pair, which goes together with 1 piece.`; the wanted value is the PARTNER).
- **Store Notices**: three triggers - `first_add` (the first `set` that leaves a line in the order list), `after_reveal` (first need revealed), `finish` (first `closeTask`); kinds `budget` (the whole-order cap moves to the amount the sentence names: 16 notices, raises and cuts; the wording does not tell the direction), `drop` (a stated requirement is waived), `price` (the FIRST listing of the order list is repriced to `old * pct // 100`; six tasks, 63% to 124%; the wording does not tell the direction either: `the amount for that selection has come down` moves 1883 to 2334). A notice echoes on the NEXT call as `{"muso": <obs>, "voboni": [<sentence>...]}` (`muso` = the bare reply string under `message`). Everything not yet fired fires at the first close, which is refused once (`{"observation": {"success_flag": true}, "refusal": [...]}`); a price notice is void on a `no_order` close or an empty order list (not in the refusal, echoed all the same); a close right after a refused close goes through. A notice that fired on the call right before a close is listed in that close's refusal too (the close's `observation` then carries the echo wrapper).
- **Persona**: 12 first-time-home-owner reveal frames (`tools/forge/r19_forge/r19_defs_frames.py`; mined from the released replies, 3,289 of 3,289 fit), 10 no-preference + 10 did-not-understand + 10 ONE-AT-A-TIME replies (`runs/r19_forge/r19_reply_pools.json`); 2 messages.
- **One at a time**: the shopper answers a message about ONE of its subjects (its hidden needs + decoy properties) and pushes a message about two or more back with the one-at-a-time pool. The decoy subjects of each task are read off the field's one-at-a-time replies (`subjects_r19.py`: decoys per task 1 x4, 2 x41); any other question gets the task's ONE off-need pool (`dnu_default` on 21 multi-line tasks, no-preference on the others).
- **Process rules** (derived from 9,445 labelled field orders, all explained - `prm_audit_r19.py`): every hidden need revealed via `message`; every page of a reference chain opened via `showPage` or `matchUpItems` (`answer.refs` stated chains - waived in the slots where the store dropped the chain's property; `answer.need_refs` chains of needs revealed by reference, orders only); EVERY ORDERED LISTING opened at some point (`process_rules: ["ordered_listing_opened"]`; the batch view counts). A decline is never process-missed (0 of 1,655 released declines).
- **Grading**: `not the best option` = acceptable but above the lowest total (on lowest-price tasks) or outside the ranked wish's best set; race 19 has no `changes missed` and no `needs not found` label (an order that violates a revealed need, or that a price move pushed over the cap, is `request not met`).
- **Not reproduced**: a call the runtime rejects before the world (`invalid_arguments`) does not spend one of the task's steps in the simulator's step meter (live: every call counts toward `max_steps`); after the step budget the simulator answers `budget_exceeded` instead of closing the session.
- **No acceptable basket derivable** (0 field passes; the clauses + field carts leave a line empty; a decline is still graded request_not_met as in the field): `t-c54adbea18`, `t-fab7ab538a`.
- **Never-revealed need** (every order is process-missed, as in the field): `t-16b268420f`, `t-3c3213f972`, `t-4b1fcfe675`, `t-4f0d9fb1e4`, `t-521e07d9ca`, `t-676a0978ee`, `t-b067f89bb0`, `t-ea0ddfecfd`.

## Search fit (forge3 method; `tools/forge/r19_forge/search_fit_r19.py`, artifact `/Users/administrator/sn15-ops/runs/r19_forge/search_fit_r19.json`; `--no-search-fit` rebuilds without it)
- `huntListings` reproduces the live engine as fitted on every distinct recorded search (40,605 (query, rowStart) pairs of 175,205 recorded calls): query prep `punct6`, OR over the analyzed terms of findQ, score = the sum of the idf of the matched terms (BM25 k1 0 / b 0), equal scores in id order, top 200, 3 rows from the offset rowStart (0..21); fields title, brand, dealer, category, facts (title, producer, seller, section, attribute VALUES; the description and the seller note are not searched).
- Race 19 is an OR engine - a listing that holds ANY of the first 6 words is a match (races 16-18 needed every word: an AND engine scores 828/3000 here) - and the matches come in tiers: the more and the rarer the words a listing holds, the earlier; inside a tier in ascending listing id.
- `world/index/jasu.json`: bm25 k1 0 / b 0 (the score is the sum of the idf of the matched terms), `analyzer` lucene_uax29 (Lucene EnglishAnalyzer replica), `df_override` + `n_docs` = the document frequencies the fit was made with (11,856 terms over 4615 listings).
- `brand` (index-only field; the cards show `brand` = the producer and `seller`) carries live-evidence search words for 0 listings.
- Fit score: first-page ids + order exact 20715/22942 distinct searches (20715/22942 from the catalog text alone), every (query, rowStart) 35965/40605.
- `num_hits_count` = max(own count, the live count the field recorded for the same query) capped at 200 (22,632 keys, `runs/r19_forge/r19_search_counts.json`); `onward` follows the pack's own rows.

## Question credit: race-19 fit (`tools/forge/r19_forge/credit_fit_r19.py` + `credit_r19.py`; `--no-credit-fit` rebuilds without it)
- Fitted on race 19 released open questions (21958 questions, first 2 per episode), read with FORGE4's parser (`tools/forge/credit_fit.py`) against this pack's subjects (needs + the decoys of `subjects_r19.py`); artifact `runs/r19_forge/credit_model_r19.json`.
- A message's cell = tier x shape (which of the task's subjects it names: none / one need / one decoy / a need first and others after / a decoy before the need / decoys only) x names (1 / 2-3 / 4-6 / 7+) x the need's place x shelf context; the cell gives the share TOLD, the share answered ONE AT A TIME, the rest is the task's off-need pool.

| tier | the message names | names | questions | told | one at a time | off-need |
|---|---|---|---|---|---|---|
| 1L | none of the task's subjects | 1 | 2366 | 0.043 | 0.025 | 0.932 |
| 1L | none of the task's subjects | 2-3 | 826 | 0.039 | 0.038 | 0.924 |
| 1L | none of the task's subjects | 4-6 | 160 | 0.075 | 0.050 | 0.875 |
| 1L | none of the task's subjects | 7+ | 11 | 0.091 | 0.182 | 0.727 |
| 1L | one subject: a need | 1 | 1515 | 0.953 | 0.046 | 0.001 |
| 1L | one subject: a need | 2-3 | 546 | 0.839 | 0.161 | 0.000 |
| 1L | one subject: a need | 4-6 | 79 | 0.595 | 0.405 | 0.000 |
| 1L | one subject: a need | 7+ | 13 | 0.462 | 0.538 | 0.000 |
| 1L | one subject: a decoy | 1 | 1046 | 0.001 | 0.022 | 0.977 |
| 1L | one subject: a decoy | 2-3 | 1020 | 0.000 | 0.185 | 0.815 |
| 1L | one subject: a decoy | 4-6 | 284 | 0.000 | 0.440 | 0.560 |
| 1L | one subject: a decoy | 7+ | 130 | 0.000 | 0.654 | 0.346 |
| 1L | a need first, other subjects after | 1 | 11 | 0.091 | 0.909 | 0.000 |
| 1L | a need first, other subjects after | 2-3 | 591 | 0.000 | 1.000 | 0.000 |
| 1L | a need first, other subjects after | 4-6 | 251 | 0.008 | 0.992 | 0.000 |
| 1L | a need first, other subjects after | 7+ | 456 | 0.000 | 1.000 | 0.000 |
| 1L | a decoy before the need | 1 | 5 | 0.000 | 1.000 | 0.000 |
| 1L | a decoy before the need | 2-3 | 185 | 0.027 | 0.973 | 0.000 |
| 1L | a decoy before the need | 4-6 | 155 | 0.000 | 1.000 | 0.000 |
| 1L | a decoy before the need | 7+ | 209 | 0.000 | 1.000 | 0.000 |
| 1L | two or more decoys, no need | 1 | 8 | 0.000 | 0.875 | 0.125 |
| 1L | two or more decoys, no need | 2-3 | 218 | 0.000 | 0.803 | 0.197 |
| 1L | two or more decoys, no need | 4-6 | 225 | 0.000 | 0.898 | 0.102 |
| 1L | two or more decoys, no need | 7+ | 430 | 0.000 | 0.956 | 0.044 |
| ML | none of the task's subjects | 1 | 2521 | 0.011 | 0.109 | 0.879 |
| ML | none of the task's subjects | 2-3 | 690 | 0.001 | 0.188 | 0.810 |
| ML | none of the task's subjects | 4-6 | 278 | 0.000 | 0.291 | 0.709 |
| ML | none of the task's subjects | 7+ | 176 | 0.000 | 0.222 | 0.778 |
| ML | one subject: a need | 1 | 1256 | 0.721 | 0.218 | 0.061 |
| ML | one subject: a need | 2-3 | 341 | 0.399 | 0.475 | 0.126 |
| ML | one subject: a need | 4-6 | 113 | 0.292 | 0.664 | 0.044 |
| ML | one subject: a need | 7+ | 67 | 0.328 | 0.672 | 0.000 |
| ML | one subject: a decoy | 1 | 1665 | 0.002 | 0.293 | 0.705 |
| ML | one subject: a decoy | 2-3 | 330 | 0.003 | 0.433 | 0.564 |
| ML | one subject: a decoy | 4-6 | 83 | 0.000 | 0.482 | 0.518 |
| ML | one subject: a decoy | 7+ | 47 | 0.000 | 0.596 | 0.404 |
| ML | a need first, other subjects after | 1 | 228 | 0.009 | 0.969 | 0.022 |
| ML | a need first, other subjects after | 2-3 | 472 | 0.004 | 0.987 | 0.008 |
| ML | a need first, other subjects after | 4-6 | 240 | 0.033 | 0.967 | 0.000 |
| ML | a need first, other subjects after | 7+ | 215 | 0.037 | 0.963 | 0.000 |
| ML | a decoy before the need | 1 | 275 | 0.058 | 0.265 | 0.676 |
| ML | a decoy before the need | 2-3 | 237 | 0.038 | 0.928 | 0.034 |
| ML | a decoy before the need | 4-6 | 136 | 0.022 | 0.971 | 0.007 |
| ML | a decoy before the need | 7+ | 161 | 0.006 | 0.994 | 0.000 |
| ML | two or more decoys, no need | 1 | 610 | 0.000 | 0.313 | 0.687 |
| ML | two or more decoys, no need | 2-3 | 539 | 0.000 | 0.751 | 0.249 |
| ML | two or more decoys, no need | 4-6 | 357 | 0.000 | 0.790 | 0.210 |
| ML | two or more decoys, no need | 7+ | 181 | 0.000 | 0.812 | 0.188 |

- Two draws per message from the episode's `credit_seed`, so a replay of the same nonce repeats them.
