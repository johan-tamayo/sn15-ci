# Race-16 Forged Field Suite (`s14_r16`, 45 Open Tasks, `w-forge-s14-r16`)

## 1. Overview & World Mechanics
- **Pack Path**: `~/sn15-ops/suites/graded30_v2/packs/s14_r16` (`pack_id: p-forge-s14-r16`, `world_id: w-forge-s14-r16`), built by `tools/forge/r16_forge/build_s14_r16.py` from `runs/r16_forge/` (lane C524 INGEST16).
- **Corpus Provenance**: all `10,395` released Race-16 open episodes; `1,095` passing order episodes across `17` tasks, `28` tasks with 0 passing orders.
- **`request_text` is RECONSTRUCTED, not verbatim**: race 16 released no request text (`query` is null on every episode) and no field agent echoes it. Each task's text is composed from the derived spec: lines (cart shapes of the passing field orders), stated clauses voted from the field agents' close notes and search phrases (`runs/r16_forge/r16_spec_log.txt`), the budget voted from the same, the step budget = the field's longest episode.
- **Truth**: `lita` = catalog items of the line's shelf matching stated + hidden clauses UNION every passing / `not_the_best_option` field cart item on that line; `reza` = stated-only fits UNION lita UNION `needs_not_found` cart items; `jufuli` calibrated on passing / `not_the_best_option` carts (cheapest tasks); one answer slot per event bitmask. Listings no agent opened with `FullSpecs` carry no facts and are never acceptable by clause.
- **Catalog**: all `5,041` cards seen in the episodes (`2,768` with `FullSpecs` facts, `330` with offer-page pointers).
- **Task mix**: 1L `12` / 2L `10` / 3L `17` / 4L `6`; hidden slots on `34/45` tasks (64 slots), reply-by-reference on `8/45`, pointer chains on `19/45`, mid-episode notices on `10/45`.
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

## Rebuild C524b (2026-11-07): event-cap lists, public request sentences, re-view text
- `t-3fb0a80602`: listings `p-006348264dc4`, `p-0237b6142e22`, `p-430a4824a4b9` made acceptable on every slot: field-carted, fit every stated value, at or under the lowest notice cap. Inferred from 150 field RNM declines, 0 process-complete field orders (0 passes; 1 non-process-missed order(s), changes missed, kept the sold-out pick).
- `t-d7bc159989`: request sentence restored from race 16's public text (replaces the composed item list): "Sorry — I need 1 set of bed sheets with a thread count identical to the one named — or pointed to — on the page of the bed sheets in Voqilenlu's listing with a geometric pattern where the age group is not adults — and also 2 tripods and camera supports with a twist lock leg lock type — if that's alright."; reference chain [['p-04b1fbc48257']] (full public query echoed by field agents; the sentence links only Voqilenlu's bed-sheet listing (p-04b1fbc48257, not adults, its page points to the geometric one); the old chain's tripod p-0331a3d51cfe has no link in the public text).
- `t-f0b9845346`: request sentence restored from race 16's public text (replaces the generic pointer sentence): "Sorry — the load capacity should be within 1.87 kg of the one named — or pointed to — on the page of the tripods and camera supports in Vokoshi's listing with color black and folded length 52.07 cm in either direction."; reference chain [['p-2bf6e7935b89']] (public request quoted by field agents; 222/231 field episodes wrote 'Vokoshi' before any observation showed it; the named listing (Vokoshi, black, folded 20.5 in = 52.07 cm) was opened by 169/169 passing episodes, the old chain p-21db5d211046 by 157/169).
- `t-f868849bfc`: request sentence restored from race 16's public text (replaces the composed item list): "Sorry — I need 3 microsdhc memory cards — the card type is microsdhc — and 3 bed sheets, where the thread count lands within 95.15 thread count, in either direction, of the one named — or pointed to — on the page of the bed sheets in Torsaqimi's listing with material silk, recommended gender unisex and pack size 4 pieces — if that's alright."; reference chain [['p-3ba076ef0b67']] (public request quoted by field agents; the sentence names Torsaqimi's silk unisex 4-piece listing (p-3ba076ef0b67); the old chain p-97cc23842c6e has no link in the public text (opened by 6/93 non-process-missed field episodes)).
- The re-view sentence ('Before you check out, please look at each chosen item's offer page once more.') is NOT in race 16's public text (`runs/r16_forge/r16_public_queries.json`, 15/15 rule tasks) and is left out; the `view_after_add` grader rule stays (field labels).

## Known noise (full transcript replay, `runs/r16forge1/R16_FIDELITY_CARD.md`)
- Category match 10,071/10,395 = 96.88%; 253 of 324 residuals are twin-proven irreproducible (race 16's process label differs across same-evidence episodes; twin-adjusted 99.32%).
- 71 residuals are unproven and are read as known noise of this pack, not a gap to close:
  - `t-8bd61534f3`: field `not the best option` -> pack `process requirement missed` x8
  - `t-be80caa191`: field `not the best option` -> pack `process requirement missed` x5
  - `t-3ee3aa35d6`: field `request not met` -> pack `did not finish` x5
  - `t-6444e764d5`: field `request not met` -> pack `not the best option` x5
  - `t-8bd61534f3`: field `PASS` -> pack `process requirement missed` x4
  - `t-480fb22da9`: field `PASS` -> pack `process requirement missed` x4
  - `t-480fb22da9`: field `request not met` -> pack `process requirement missed` x4
  - `t-b4c5139927`: field `PASS` -> pack `changes missed` x3
  - `t-938f1af50e`: field `process requirement missed` -> pack `PASS` x3
  - `t-938f1af50e`: field `process requirement missed` -> pack `request not met` x3
  - `t-18a38d31ce`: field `request not met` -> pack `PASS` x3
  - `t-480fb22da9`: field `request not met` -> pack `PASS` x2
  - `t-3fb0a80602`: field `process requirement missed` -> pack `did not finish` x2
  - `t-cbfa267c8a`: field `process requirement missed` -> pack `PASS` x2
  - `t-7323911eef`: field `process requirement missed` -> pack `PASS` x2
  - `t-7c2132dac7`: field `request not met` -> pack `not the best option` x2
  - `t-d818f5604e`: field `process requirement missed` -> pack `request not met` x1
  - `t-cbfa267c8a`: field `process requirement missed` -> pack `request not met` x1
  - `t-b3fef9d2ba`: field `process requirement missed` -> pack `request not met` x1
  - `t-cbfa267c8a`: field `did not finish` -> pack `process requirement missed` x1
  - `t-865b344413`: field `request not met` -> pack `process requirement missed` x1
  - `t-e1b52611b6`: field `process requirement missed` -> pack `request not met` x1
  - `t-865b344413`: field `process requirement missed` -> pack `PASS` x1
  - `t-b4c5139927`: field `request not met` -> pack `changes missed` x1
  - `t-190e3ed035`: field `PASS` -> pack `process requirement missed` x1
  - `t-5a1196d6d2`: field `not the best option` -> pack `did not finish` x1
  - `t-b064ec811d`: field `process requirement missed` -> pack `request not met` x1
  - `t-ece5a5fba1`: field `request not met` -> pack `changes missed` x1
  - `t-7da8a1ce4d`: field `PASS` -> pack `process requirement missed` x1
  - `t-54b7a4a371`: field `not the best option` -> pack `process requirement missed` x1
