# Race-16 Forged Field Suite (`s14_r16`, 45 Open Tasks, `w-forge-s14-r16`)

## 1. Overview & World Mechanics
- **Pack Path**: `~/sn15-ops/suites/graded30_v2/packs/s14_r16` (`pack_id: p-forge-s14-r16`, `world_id: w-forge-s14-r16`), built by `tools/forge/r16_forge/build_s14_r16.py` from `runs/r16_forge/` (lane C524 INGEST16).
- **Corpus Provenance**: all `10,395` released Race-16 open episodes; `1,095` passing order episodes across `17` tasks, `28` tasks with 0 passing orders.
- **`request_text` = race 16's PUBLIC request text** (C535 R16FORGE2, `runs/r16_forge/r16_verbatim_requests.json`, recovered by C532 from field agents' own echoes): `40` tasks verbatim (7 full task-input echoes + 33 multi-agent shared spans that cover the whole request), `5` `fidelity: partial` (the recovered span holds no item list: the item / budget span is composed from the old derived spec and appended; listed below). The spec is re-forged FROM the text (`tools/forge/r16_forge/specs_v2_r16.py`, per-task diff `runs/r16forge2/SPEC_DIFF.md`).

- **Truth**: `lita` = catalog items of the line's shelf matching stated + hidden clauses UNION every passing / `not_the_best_option` field cart item on that line; `reza` = stated-only fits UNION lita UNION `needs_not_found` cart items; `jufuli` calibrated on passing / `not_the_best_option` carts (cheapest tasks); one answer slot per event bitmask. Listings no agent opened with `FullSpecs` carry no facts and are never acceptable by clause.
- **Catalog**: all `5,041` cards seen in the episodes (`2,768` with `FullSpecs` facts, `330` with offer-page pointers).
- **Task mix**: 1L `12` / 2L `9` / 3L `18` / 4L `6`; hidden slots on `34/45` tasks (64 slots), reply-by-reference on `8/45`, pointer chains on `17/45`, mid-episode notices on `10/45`.
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
- **Compatibility pairs graded** (13 tasks, 29 pairs): `Whatever X you choose, the Y must be compatible with it` -> `answer.dova[].fitok` (a Y listing that does not fit the chosen X is `request_not_met`). Relation from the catalog cards (`tools/forge/r16_forge/compat_r16.py`): camera `Model: LIV nnnn` <-> accessory `Compatible with: LIV ... / every LIV nnxx model, except ... / also fits`; sofa `Takes part series SIn` <-> cover title `[SIn-....]`; unknown = compatible. Field check (`compat_r16.py check`): 103 of 103 PASS carts and 20 of 20 not_the_best_option carts fit; 129 of 174 request_not_met carts violate.
- **Conditionals graded** (3 tasks) as `fitok` pairs on the same device line: `Should the video camera's P turn out to be V, I need the Y's Q to be W` / `Y's Q must be W, except when the video camera's P is V1 or V2`; a listing without the fact is unknown = allowed.
- **References**: `identical to / partner piece to / within N of the one named - or pointed to - on ... listing` -> stated clause with `ref`, value resolved by walking the named listing's page pointers (`tools/forge/r16_forge/refwalk_r16.py`), every hop in `answer.refs`; field-inferred chains with no link in the text or a reveal are dropped.
- **hidden** = the observed field reveals (unchanged), re-indexed onto the text's lines; a reveal the text now states is dropped.
- **Keys** re-derived under the text clauses: `lita` = shelf listings matching stated + hidden UNION passing / not_the_best_option field carts (minus over-line-cap).
- **Re-view rule**: no re-view sentence in any request (0 of 45 public texts carry one); `view_after_add` stays a LABEL-INFERRED grader rule on 15 tasks (matches the live `process_requirement_missed` labels on 86% of 2,356 evidence-complete field orders).
- **Race-16 question-credit fit kept** (C524b).

### Partial request spans (`fidelity: partial`, composed span only)
- `t-2363ddf59f`: composed span appended: "Lowest total cost wins — sorry — if you can manage that. Sorry — I need 1 x bed sheets with pattern character; 1 x cctv security cameras with security camera style dome — if that's alright. Would you mind keeping the whole total at 2050 cents US or under — sorry."
- `t-237494d47b`: composed span appended: "Sorry — I need 1 x memory cards with color gold and cardtype sd and device interface sd card; 1 x tripods with leg lock type twist lock and load capacity 8 kg and material aluminum; 2 x tripods and camera supports with leg lock type twist lock and load capacity 8 kg and material aluminum — if that's alright. Would you mind keeping the whole total at 86000 cents US or under — sorry."
- `t-4bfd08dfb1`: composed span appended: "Sorry — I need 2 x furniture covers with color tan and material cotton; 2 x slipcovers and furniture covers with color white and material cotton; 1 x sofa covers & slips with style modern and pattern leaf and warranty policy set; 1 x sofas with furniture features slipcovered and style modern and warranty policy set — if that's alright. Would you mind keeping the whole total at 60500 cents US or under — sorry."
- `t-6444e764d5`: composed span appended: "Lowest total cost wins — sorry — if you can manage that. Sorry — I need 1 x memory cards; 2 x tripods; 1 x tripods and camera supports with leg lock type twist lock; 1 x video camera — if that's alright. Would you mind keeping the whole total at 79500 cents US or under — sorry."
- `t-9d5024ca80`: composed span appended: "Sorry — I need 1 x furniture covers with upholsterymaterial chenille; 1 x slipcovers and furniture covers with fabric chenille and closure type slip-on; 1 x sofa covers & slips with style antique and warranty policy set and material microfiber; 2 x sofas with furniture features slipcovered and style antique and warranty policy set — if that's alright. Would you mind keeping the whole total at 31500 cents US or under — sorry."

- `fits_infeasible` (fitting basket not in the pack catalog, priced without the pairs): `t-12580eb901`

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
