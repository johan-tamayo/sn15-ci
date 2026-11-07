# Race-16 Forged Field Suite (`s14_r16`, 45 Open Tasks, `w-forge-s14-r16`)

## 1. Overview & World Mechanics
- **Pack Path**: `~/sn15-ops/suites/graded30_v2/packs/s14_r16` (`pack_id: p-forge-s14-r16`, `world_id: w-forge-s14-r16`), built by `tools/forge/r16_forge/build_s14_r16.py` from `runs/r16_forge/` (lane C524 INGEST16).
- **Corpus Provenance**: all `10,395` released Race-16 open episodes; `1,095` passing order episodes across `17` tasks, `28` tasks with 0 passing orders.
- **`request_text` = race 16's PUBLIC request text** (C535 R16FORGE2, `runs/r16_forge/r16_verbatim_requests.json`, recovered by C532 from field agents' own echoes): `43` tasks verbatim (7 full task-input echoes + 33 multi-agent shared spans that cover the whole request), `2` `fidelity: partial` (the recovered span holds no item list: the item / budget span is composed from the old derived spec and appended; listed below). The spec is re-forged FROM the text (`tools/forge/r16_forge/specs_v2_r16.py`, per-task diff `runs/r16forge2/SPEC_DIFF.md`).

- **Truth**: `lita` = catalog items of the line's shelf matching stated + hidden clauses UNION every passing / `not_the_best_option` field cart item on that line; `reza` = stated-only fits UNION lita UNION `needs_not_found` cart items; `jufuli` calibrated on passing / `not_the_best_option` carts (cheapest tasks); one answer slot per event bitmask. Listings no agent opened with `FullSpecs` carry no facts and are never acceptable by clause.
- **Catalog**: all `5,041` cards seen in the episodes (`2,768` with `FullSpecs` facts, `330` with offer-page pointers).
- **Task mix**: 1L `12` / 2L `9` / 3L `18` / 4L `6`; hidden slots on `34/45` tasks (64 slots), reply-by-reference on `8/45`, pointer chains on `18/45`, mid-episode notices on `10/45`.
- **7 Race-16 Tools (`tools.json`)**: `ItemsSeek` (phrase search | shelf `match` browse, 6 per page, `vetu<offset>` tokens), `FullSpecs` (facts), `OfferShow` (offer page with `pointers`), `StashToBasket` (set one line), `SummaryMyItems` (basket), `OrderWrapUp` (checkout | cancel), `BuyerMessage` (3 replies).
- **Store Notices**: events ride on the NEXT tool observation as `{"pozo": <obs>, "teve": [<sentence>]}`; an event not yet fired at the first checkout refuses it (`{"observation": {"worked": true}, "refusal": [...]}`).
- **Persona**: 12 nurse reveal frames (`simrace/race2/shopper2.py` `_R16_REVEAL_FRAMES`), the learned race-16 no-preference / did-not-understand pools.
- **Process rules**: reference chains (`answer.refs`: reveal-by-reference chains + request-stated references inferred from the field) opened via `OfferShow` / `FullSpecs`; hidden needs (`answer.needs`, incl. `unrevealed_needs` on 0-pass tasks whose PRM orders stay unexplained) revealed via `BuyerMessage`; `process_rules: ["view_after_add"]` on `15` tasks (each ordered listing's `OfferShow` page viewed after it was last added; inferred per task from the field's process-complete vs PRM orders).

## Search / browse fit (lanes forge2 + forge3, applied by the builder from `/Users/administrator/sn15-ops/runs/r16_forge/search_fit_r16.json`; `--no-search-fit` rebuilds without it)
- search reproduces the live store's engine as fitted on every recorded search of the race: Lucene EnglishAnalyzer terms of the phrase, AND over every term across title / vendor / seller / category / fact values, ascending sku id, top 500, BM25 k1 1.2 / b 0.0 (score tiers in id order).
- `world/index/jasu.json`: k1 1.2, b 0.0, `analyzer` lucene_uax29 (Lucene EnglishAnalyzer replica).
- `brand` (index-only field; the cards show `maker` / `merchant`) carries live-evidence search words for 2117 pointer cards (listings no field agent opened).
- `ItemsSeek` match reports the live shelf size as `all_matches` when no Budget / ProductVendor filter is set; pages are the shelf's ids in ascending order, 6 per page.

## Question credit: race-16 fit (lane C524b; replaces FORGE4's race-14/15 table on THIS pack only - the `_fit2` packs keep FORGE4)
- Fitted by `tools/forge/r16_forge/credit_fit_r16.py` on race 16 released open questions (30026 questions, first 3 per episode), read with FORGE4's own parser; artifact `runs/r16_forge/credit_model_r16.json`.
- Side by side, the credited share of a question whose first named subject is the need:
  - **race 16 (this pack)** 1L: k1 first 0.75 / unplaced 0.41; k2-3 first 0.46 / last 0.28 / unplaced 0.16; k4+ first 0.04 / middle 0.02 / last 0.12 / unplaced 0.00
  - **race 16 (this pack)** ML (own shelf word): k1 first 0.83 / unplaced 0.62; k2-3 first 0.50 / last 0.35 / unplaced 0.20; k4+ first 0.25 / middle 0.15 / last 0.20 / unplaced 0.00; shelf context own 1.00 / none 0.76 / another line's 0.17; decoy first blocks 0.04
  - **races 14-15 (FORGE4, `s14_r14_fit2` / `s14_r15_fit2`)** one table for every tier: k1 first 1.00; k2 first 0.96 / last 0.76; k3 first 1.00 / second 0.62 / last 0.60; k4-5 first 0.99 / second 0.60 / middle 0.48 / last 0.23; k6+ first 1.00 / second 0.76 / middle 0.48 / last 0.06
- Push-back ('one at a time') on an uncredited question now depends on the number of names (race 16; FORGE4 drew it from a per-task share `bundle_pct` regardless of names): 1L k1 0.03 (need named 1.00), k2-3 0.16 (need named 0.98), k4+ 0.65 (need named 1.00); ML k1 0.17 (need named 0.59), k2-3 0.30 (need named 0.94), k4+ 0.61 (need named 0.99).
- One draw per message for the credit and one for the push-back, both from the episode's `credit_seed`, so a replay of the same nonce repeats them.

## Re-forge C535 R16FORGE2 (2026-11-07): spec FROM the public request text
- **stated** = the text's own clauses: category nouns as written, values, either/or sets, `not / anything but` exclusions, amounts with units (fact amounts in other units of the same measure are converted at key time), per-line price caps (`Keep each X at or under N cents US` -> `line_cap`, 2 lines), cheapest from `pick the cheapest` / `Lowest total cost wins` (28 tasks), budget / steps / messages from the text.
- **Compatibility pairs graded** (15 tasks, 35 pairs): `Whatever X you choose, the Y must be compatible with it` -> `answer.dova[].fitok` (a Y listing that does not fit the chosen X is `request_not_met`). Relation from the catalog cards (`tools/forge/r16_forge/compat_r16.py`): camera `Model: LIV nnnn` <-> accessory `Compatible with: LIV ... / every LIV nnxx model, except ... / also fits`; sofa `Takes part series SIn` <-> cover title `[SIn-....]`; unknown = compatible. Field check (`compat_r16.py check`): 103 of 103 PASS carts and 20 of 20 not_the_best_option carts fit; 129 of 174 request_not_met carts violate.
- **Conditionals graded** (5 tasks) as `fitok` pairs on the same device line: `Should the video camera's P turn out to be V, I need the Y's Q to be W` / `Y's Q must be W, except when the video camera's P is V1 or V2`; a listing without the fact is unknown = allowed.
- **References**: `identical to / partner piece to / within N of the one named - or pointed to - on ... listing` -> stated clause with `ref`, value resolved by walking the named listing's page pointers (`tools/forge/r16_forge/refwalk_r16.py`), every hop in `answer.refs`; field-inferred chains with no link in the text or a reveal are dropped.
- **hidden** = the observed field reveals (unchanged), re-indexed onto the text's lines. A reveal stays hidden even when the text states the same value under another property (`t-f868849bfc`: text `card type is microsdhc`, field shopper reveals `device interface microsdhc` and 128 of 128 field orders without that reveal are graded process_requirement_missed).
- **Cheapest cap per event state**: `jufuli` = the state's cheapest basket, raised to the field's passing totals, lowered to (cheapest not_the_best_option cart - 1) only when that stays at or above the state's own cheapest basket (an NBO cart below it was graded in another event state; `t-5a1196d6d2` no-drop states 129 -> 130).
- **Keys** re-derived under the text clauses: `lita` = shelf listings matching stated + hidden UNION passing / not_the_best_option field carts (minus over-line-cap).
- **Re-view rule**: no re-view sentence in any request (0 of 45 public texts carry one); `view_after_add` stays a LABEL-INFERRED grader rule on 15 tasks (matches the live `process_requirement_missed` labels on 86% of 2,356 evidence-complete field orders).
- **Race-16 question-credit fit kept** (C524b).
- **Checks** (`runs/r16forge2/R16_FIDELITY_CARD.md`): scripted oracle 245/245 (0 mismatches), tool shapes 19/19, field passing carts 1,092/1,095 PASS, field order re-grade 1,908/1,952 (97.75%), reply mix / 3-message cap / step budget = text 45/45, notice tasks 10 = field, `sn15 forge check` PASS; full transcript replay under the race-16 credit rule (`tools/forge/full_replay.py` nonce search reads the 1L / ML table) 10,024/10,395 = 96.43%, twin-adjusted 98.72%; per-task spec diff `runs/r16forge2/SPEC_DIFF.md`.

### Partial request spans (`fidelity: partial`, composed span only)
- `t-2363ddf59f`: composed span appended: "Lowest total cost wins — sorry — if you can manage that. Sorry — I need 1 x bed sheets with pattern character; 1 x cctv security cameras with security camera style dome — if that's alright. Would you mind keeping the whole total at 2050 cents US or under — sorry."
- `t-6444e764d5`: composed span appended: "Lowest total cost wins — sorry — if you can manage that. Sorry — I need 1 x memory cards; 2 x tripods; 1 x tripods and camera supports with leg lock type twist lock; 1 x video camera — if that's alright. Would you mind keeping the whole total at 79500 cents US or under — sorry."

- `fits_infeasible` (fitting basket not in the pack catalog, priced without the pairs): `t-12580eb901`

### C551 R16FIX: full request text from a field task-input echo (COACH 15:16 ruling on C550 R16KEYS)
- Three tasks that were `fidelity: partial` now carry their FULL public request: field agent KAKA echoed its whole task input (`runs/c551/r16_echo_requests.json`, `runs/c551/echo_requests.py`; C532's recovered span is a substring of it). Their old composed span carried clauses voted across sibling shelves (`sofa` in Sofas / Sofa Covers & Slips, `furniture covers` in two shelves, `tripods` in two shelves) and the seller field `warranty policy: Set` read from `sofa set`; with no listing meeting them the key fell back to the whole shelf on 7 lines.
- Now: per-line clauses from each line's own span only; `It's for our camera at home (a <model>), so the <line> must fit it.` = a `fits_model` clause (compat_r16: unknown = fits); a clause no listing on the shelf can satisfy is dropped (a hidden need: together with the line's text clauses), never widened to the shelf - the builder refuses a `shelf_with_facts` fallback on these tasks. Keys re-derived under these clauses (0 field pass / not_the_best_option carts on the three tasks). The other two partial tasks (`t-6444e764d5`, `t-2363ddf59f`) are unchanged.
- `t-237494d47b`: deciding words "1 tripod with a load capacity of at least 8 kg; 1 memory card in gold; and 2 tripods and camera supports with a twist lock leg lock type ... It's for our camera at home (a LIV 2110), so the memory cards must fit it ... The memory cards's device interface must be sd card, except when the tripods's material is aluminum or metal.". Was: twist lock + `8 kg` (as text) + aluminum voted onto BOTH tripod shelves, card type sd stated; now load capacity >= 8 kg on Tripods, twist lock on Tripods and Camera Supports, gold on Memory Cards, fits LIV 2110 on all three, the sd-card interface as the text's conditional on the tripod's material. Key `lita`: L0 Memory Cards 1 -> 1, L1 Tripods 99 -> 10, L2 Tripods and Camera Supports 2 -> 32. Dropped as unsatisfiable: hidden L2 `feet type eq retractable`.
- `t-4bfd08dfb1`: deciding words "1 x sofa where the furniture feature is slipcovered and the style is not traditional; 1 x sofa cover or slip where the pattern is the partner piece to the one named - or pointed to - on the page of the sofa covers & slips in Savoanzen's listing with style character; 2 x slipcovers and furniture covers where the color is white; and 2 x furniture covers where the color is tan ... The slipcovers and furniture covers's material must be cotton, except when the sofas's pattern is plaid or plain.". Was: style modern + warranty policy set on Sofas and Sofa Covers, cotton on both cover shelves; now the text's clauses, the leaf partner pattern by reference (chain `p-d543fdab1b1e`, 'Its novelty pattern goes together with leaf'), cotton as the text's conditional, 3 compat pairs. Key `lita`: L0 Furniture Covers 203 -> 8, L1 Slipcovers and Furniture Covers 1 -> 28, L2 Sofa Covers & Slips 556 -> 12, L3 Sofas 312 -> 11. Dropped as unsatisfiable: none.
- `t-9d5024ca80`: deciding words "2 x sofas where the furniture features is slipcovered and the style is the partner piece for the one named - or pointed to - on the page of the sofas in Rishivexshi's listing with upholstery microfiber and sofa type sofa set; 1 x sofa covers & slips where the style is antique; 1 x slipcovers and furniture covers where the closure type is slip-on and the pattern is solid or textured; 1 x furniture covers where the material is chenille". Was: style antique + warranty policy set on Sofas, chenille on Slipcovers, microfiber + warranty set on Sofa Covers; now the text's clauses, sofa style traditional by reference (chain `p-4cbba808f316`, 'Its colorful style goes together with traditional'), the field's hidden reveals kept. Key `lita`: L0 Furniture Covers 8 -> 8, L1 Slipcovers and Furniture Covers 137 -> 7, L2 Sofa Covers & Slips 556 -> 4, L3 Sofas 312 -> 1. Dropped as unsatisfiable: none.

## Known noise (full transcript replay, `runs/r16forge2/R16_FIDELITY_CARD.md`)
- Category match 10,024/10,395 = 96.43%; 238 of 371 residuals are twin-proven irreproducible (race 16's process label differs across same-evidence episodes; twin-adjusted 98.72%).
- 133 residuals are unproven and are read as known noise of this pack, not a gap to close:
  - `t-bdbd94913b`: field `PASS` -> pack `process requirement missed` x69
  - `t-cbfa267c8a`: field `PASS` -> pack `process requirement missed` x27
  - `t-6444e764d5`: field `request not met` -> pack `not the best option` x5
  - `t-3ee3aa35d6`: field `request not met` -> pack `did not finish` x5
  - `t-f868849bfc`: field `process requirement missed` -> pack `request not met` x4
  - `t-b4c5139927`: field `PASS` -> pack `changes missed` x3
  - `t-865b344413`: field `process requirement missed` -> pack `request not met` x3
  - `t-3fb0a80602`: field `process requirement missed` -> pack `did not finish` x2
  - `t-cbfa267c8a`: field `process requirement missed` -> pack `PASS` x2
  - `t-f868849bfc`: field `process requirement missed` -> pack `needs not found` x1
  - `t-ece5a5fba1`: field `request not met` -> pack `changes missed` x1
  - `t-d818f5604e`: field `process requirement missed` -> pack `request not met` x1
  - `t-cbfa267c8a`: field `process requirement missed` -> pack `request not met` x1
  - `t-b3fef9d2ba`: field `process requirement missed` -> pack `request not met` x1
  - `t-3fb0a80602`: field `process requirement missed` -> pack `changes missed` x1
  - `t-cbfa267c8a`: field `did not finish` -> pack `process requirement missed` x1
  - `t-e1b52611b6`: field `process requirement missed` -> pack `request not met` x1
  - `t-b4c5139927`: field `request not met` -> pack `changes missed` x1
  - `t-7323911eef`: field `process requirement missed` -> pack `not the best option` x1
  - `t-7323911eef`: field `process requirement missed` -> pack `request not met` x1
  - `t-5a1196d6d2`: field `not the best option` -> pack `did not finish` x1
  - `t-b064ec811d`: field `process requirement missed` -> pack `request not met` x1
