# Race-24 Forged Field Suite (`s14_r24`, 45 Open Tasks, `w-forge-s14-r24`)

- **Pack**: `~/sn15-ops/suites/graded30_v2/packs/s14_r24` (`pack_id: p-forge-s14-r24`, `world_id: w-forge-s14-r24`), built by `tools/forge/r24_forge/build_s14_r24.py` (lane r24forge1, FORGE24; a port of `tools/forge/r22_forge/`). Card: `runs/r24forge1/R24_FIDELITY_CARD.md`.
- **Corpus**: all `11,970` released Race-24 open episodes (266 agents x 45 tasks); `3,273` passing orders on `28` tasks, `17` tasks with 0 passes.
- **Request text**: race 24's public text, verbatim on 45/45 tasks, from two field agents' list echoes of their task input (`06af5e8c-863f57a5`, `06af8981-305823d4`; `runs/r24_forge/r24_task_inputs.json`). Tool names, argument names, enums, descriptions and order come from the same echoes; the argument schemas are ours. `params.policy_max_steps` = the live `max_steps` (40 x24, 78 x5, 86 x3, 89 x4, 97 x6, 105 x3).
- **7 tools**: `LookupListings(TextString[, After])` keyword search, `ScreenShelf([ItemSection][, Vendor][, CostPriceMax][, Token])` filter listing - both `{n_results, next_page, outcomes[10 row strings]}`, pages by token `zasu<offset>`; `InspectItem(ListingIdKey)` -> `{value: card string}` (`{}` for an unknown id); `AddItem(CartOperation insert|release, ItemNumber[, QtyWanted])` edits ONE line (`{success_flag: true}`; no QtyWanted = 1 unit; a line over 5 -> `{fault: E38}`); `BagSummary()`; `AskShopper(ReplyMsg)` (3 messages); `WrapUpRequest(SearchBy buy|abstain[, DeclineNote])` (buy on an empty trolley -> `{fault: E39}`). No batch view, no meter.
- **Rows and cards are strings**: `listing_id_code: .. | listing_headline: .. | listing_merchant: .. | manufacturer: .. | unit_price: .. | on_hand: .. | category: .. | desc: ..`; the card adds `shop_good_to_know` (the seller's note: pointer sentences) and `facts: k=v; ...`.
- **Catalog**: `8,037` listings the field saw (`4,347` opened, `715` with a seller note) on 18 shelves; a listing no field agent opened shows empty facts.
- **Task mix**: 1L `16` / 2L `4` / 3L `12` / 4L `13`; 70 hidden needs on `35` tasks (4 told by reference); 5 stated reference chains; store notices on `15` (budget 8, drop 9, stock 1); lowest-price `24`; compatibility on `21` (42 pairs); conditionals on `11`; per-item caps on `4`; did-not-understand voice on `22`.
- **Compatibility**: cameras `Fits part series NE3.` pair with accessories whose title ends `- NE3-<n>`; sofas `Model: SEV-7620.` pair with covers whose `Compatible with:` list (or another listing's `Part <code> also fits:` sentence about the cover's title code) names the model.
- **Reference chains**: `whatever you arrive at by opening the page of <Seller>'s listed <shelf>, the one with <attrs>, and following every listing it names in turn`; told needs `not the same as what you get to from the page of ...`; pointer sentences in `shop_good_to_know` (`For megapixels, check the Lenrator point & shoot camera that ...`).
- **Shopper**: 12 reveal frames, ONE off-need voice a task (did-not-understand or no-preference); it ANSWERS a list (no one-at-a-time pool); the told share comes from the fitted credit table (below).
- **Process rules** (`prm_audit_r24.py`, 99.43% of 8,535 labelled orders): every hidden need revealed; every chain page opened (`InspectItem`); every ordered listing opened.
- **Not reproduced**: keyword search ranking where the live store's word statistics differ (first page exact on ~38% of distinct queries); `invalid_arguments` calls do not spend a step in the simulator.
- **No acceptable basket derivable** (0 field passes; the clauses + field carts leave a line empty; a decline is still graded request_not_met as in the field): `t-3003058f27`.

## Search fit (forge3 method; `tools/forge/r24_forge/search_fit_r24.py`, artifact `/Users/administrator/sn15-ops/runs/r24_forge/search_fit_r24.json`; `--no-search-fit` rebuilds without it)
- `ListingsSearch` with `SearchWay: phrase` reproduces the live engine as fitted on every distinct recorded keyword search (32,539 (query, offset) pairs of 131,672 recorded calls): LookupListings: query prep `punct4d1`, OR over the analyzed terms of TextString, BM25 k1 1.2 / b 0.0 with equal scores in id order, top 200, 10 rows from the token's offset; ScreenShelf: the section's (or the brand's) listings in ascending id, price <= CostPriceMax; fields title, brand, dealer, category, facts (title, producer, seller, shelf, attribute VALUES; the description and the seller note are not searched).
- Race 21 is the engine of races 16 and 17: a listing must hold EVERY word, and the matches come in ascending listing id (an OR engine scores None/None on the sweep sample, AND with a BM25 order None/None). `Aisle`, `ProductMake` and `LimitLimit` are not read in this style.
- `world/index/jasu.json`: bm25 k1 1.2 / b 0.0 (every match scores the same; the star sorts by id), `analyzer` lucene_uax29 (Lucene EnglishAnalyzer replica).
- `brand` (index-only field; the cards show `brand` = the producer and `merchant`) carries live-evidence search words for 0 listings (a listing the live store returned for a query holds every word of it).
- Fit score: first-page ids + order exact 7834/20696 distinct keyword searches (7834/20696 from the catalog text alone), every (query, offset) 10413/32539.
- `SearchWay: criteria` (filter): the Aisle's listings in ascending id, 7 a page, narrowed by `ProductMake` (the brand) and `LimitLimit` (the highest unit price let through); `FindTerms` is not read; recorded pages reproduced: 4458/4458 distinct (Aisle, ProductMake, LimitLimit, offset), 36893/36893 recorded calls.
- `found_number` = max(own count, the live count the field recorded for the same query / filter); a keyword search is capped at 200 (14,817 keyword keys, `runs/r24_forge/r24_search_counts.json`); `page_next_token` follows the pack's own rows and stops at 56.

## Question credit: race-21 fit (`tools/forge/r24_forge/credit_fit_r24.py` + `credit_r24.py`; `--no-credit-fit` rebuilds without it)
- Fitted on race 24 released open messages (32258 answered messages with a question mark; 17665 with a subject hit by the text labeler); artifact `runs/r24_forge/credit_model_r24.json`. The shopper TURNS BACK a message it reads as several questions (a one-at-a-time line).
- A message's cell = tier (one item / several items with the no-preference voice / several items with the did-not-follow voice) x the place of the first need it names (or `d`: only subjects the shopper has no view on) x names (1 / 2-3 / 4-6 / 7+) x first or later question x item context x subjects hit (one / two or more); the cell gives [the share TOLD, the share PUSHED BACK], the rest is the task's off-need pool. Two draws per message from the episode's `credit_seed`.

| tier | the message | subjects hit | questions | told (field) | pushed back (field) |
|---|---|---|---|---|---|
| one item | the need first | one | 1681 | 0.997 | 0.000 |
| one item | the need first | two or more | 520 | 0.971 | 0.000 |
| one item | the need second | one | 208 | 0.923 | 0.000 |
| one item | the need second | two or more | 186 | 0.839 | 0.000 |
| one item | the need third | one | 93 | 0.871 | 0.000 |
| one item | the need third | two or more | 92 | 0.913 | 0.000 |
| one item | the need fourth / fifth | one | 17 | 0.706 | 0.000 |
| one item | the need fourth / fifth | two or more | 25 | 0.760 | 0.000 |
| one item | the need sixth or later | one | 12 | 0.583 | 0.000 |
| one item | the need sixth or later | two or more | 10 | 0.500 | 0.000 |
| one item | a need hit, not among the names | one | 1 | 1.000 | 0.000 |
| one item | no need: only subjects with no view | one | 2830 | 0.007 | 0.000 |
| one item | no need: only subjects with no view | two or more | 1650 | 0.008 | 0.000 |
| several items, no-preference voice | the need first | one | 843 | 1.000 | 0.000 |
| several items, no-preference voice | the need first | two or more | 324 | 1.000 | 0.000 |
| several items, no-preference voice | the need second | one | 195 | 0.959 | 0.000 |
| several items, no-preference voice | the need second | two or more | 13 | 1.000 | 0.000 |
| several items, no-preference voice | the need third | one | 85 | 0.847 | 0.000 |
| several items, no-preference voice | the need third | two or more | 3 | 1.000 | 0.000 |
| several items, no-preference voice | the need fourth / fifth | one | 59 | 0.983 | 0.000 |
| several items, no-preference voice | the need fourth / fifth | two or more | 5 | 0.800 | 0.000 |
| several items, no-preference voice | the need sixth or later | one | 76 | 0.961 | 0.000 |
| several items, no-preference voice | the need sixth or later | two or more | 2 | 1.000 | 0.000 |
| several items, no-preference voice | no need: only subjects with no view | one | 564 | 0.055 | 0.000 |
| several items, no-preference voice | no need: only subjects with no view | two or more | 302 | 0.026 | 0.000 |
| several items, did-not-follow voice | the need first | one | 2310 | 0.990 | 0.000 |
| several items, did-not-follow voice | the need first | two or more | 579 | 0.986 | 0.000 |
| several items, did-not-follow voice | the need second | one | 1373 | 0.423 | 0.000 |
| several items, did-not-follow voice | the need second | two or more | 194 | 0.644 | 0.000 |
| several items, did-not-follow voice | the need third | one | 715 | 0.313 | 0.000 |
| several items, did-not-follow voice | the need third | two or more | 36 | 0.306 | 0.000 |
| several items, did-not-follow voice | the need fourth / fifth | one | 263 | 0.338 | 0.000 |
| several items, did-not-follow voice | the need fourth / fifth | two or more | 33 | 0.182 | 0.000 |
| several items, did-not-follow voice | the need sixth or later | one | 88 | 0.216 | 0.000 |
| several items, did-not-follow voice | the need sixth or later | two or more | 16 | 0.125 | 0.000 |
| several items, did-not-follow voice | a need hit, not among the names | one | 5 | 0.000 | 0.000 |
| several items, did-not-follow voice | a need hit, not among the names | two or more | 5 | 0.000 | 0.000 |
| several items, did-not-follow voice | no need: only subjects with no view | one | 1563 | 0.004 | 0.000 |
| several items, did-not-follow voice | no need: only subjects with no view | two or more | 689 | 0.006 | 0.000 |
| one item | no subject hit, two or more names | none | 1262 | 0.049 | 0.000 |
| several items, no-preference voice | no subject hit, two or more names | none | 2207 | 0.123 | 0.000 |
| several items, did-not-follow voice | no subject hit, two or more names | none | 6161 | 0.027 | 0.000 |
