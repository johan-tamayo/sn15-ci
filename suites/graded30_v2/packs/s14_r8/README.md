# Race-8 Forged Field Suite (`s14_r8`, 45 Open Tasks, `w-forge-s14-r8`)

## 1. Overview & World Mechanics (`[C398]` Item 3)
- **Pack Path**: `~/sn15-ops/suites/graded30_v2/packs/s14_r8` (`pack_id: p-forge-s14-r8`, `world_id: w-forge-s14-r8`)
- **Corpus Provenance**: Built from all `9,765` released Race-8 open episodes (`217` agents $\times$ `45` open tasks; `2,270` passing episodes across `33` tasks with `>0` passes + `12` `0`-pass tasks with exact stated + hidden clauses).
- **100% Real Verbatim `request_text`**: Every one of the 45 open tasks uses the exact verbatim shopper `request_text` recovered from the released Race-8 open transcripts (`~/sn15-ops/runs/r8_forge/r8_verbatim_requests.json`).
- **Zero Shelf-Injection Artefacts (`P16` / `P47` Lesson Applied)**: `lita` and `reza` are constructed strictly from all passing field order carts unioned with in-stock catalog items matching `stated + hidden` clauses minus `request_not_met`-only SKUs, with `jufuli` calibrated so `100%` of passing field carts (`2,270/2,270`) pass (`<= jufuli`) and `100%` of `not_the_best_option` field carts (`465/465`) stay `> jufuli`.
- **Complete 9,508-Item Catalog (`world/catalog.jsonl`)**: Includes all `9,508` catalog items seen across the `9,765` Race-8 episodes, including all `326` pointer-annotation cards (`annotations`) and reply-by-reference target cards.
- **8 Race-8 Tools (`tools.json`)**:
  - `QueryItems({"TextText", "NextContinueFrom"})` -> `4` rows per page (`gudadi4`, `gudadi8`, ..., `result_count` capped at `1000`)
  - `ScreenRange({"ItemShelf", "VendorName", "CostCap", "NextToken"})` -> `4` rows per page (`gudadi4`, `gudadi8`, ..., `{"status": "NO_ITEMS"}` if neither `ItemShelf` nor `VendorName` is provided)
  - `ReadDetails({"ItemIdNumber"})` -> full card with `annotations`, `facts`, `item_cost`, `in_stock`, `dealer`, `brand`, `category`, `listing_name`, `overview_text`
  - `LineUpListings({"PickedItems"})` -> `1..5` item IDs (`>5` returns `{"status": "UNRESOLVED"}`)
  - `AddToCart({"VerbKind": "add"|"release", "WhichItemId", "Pieces"})` -> delta/remove basket (`{"cart_subtotal", "your_bag"}`)
  - `MyItemsList({})` -> `{"cart_subtotal", "your_bag"}`
  - `AskShopper({"ReplyMessage"})` -> `{"value": <reply>}` (`5`-message allowance; 6th call returns `{"error": "budget_exceeded"}`)
  - `ConcludeTask({"Variant": "buy"|"skip"})` -> `{"applied": True}` (or `{"observation": {"applied": True}, "refusal": [...]}`)
- **Store Notices (`kubi` / `misale`)**: On the `12/45` mid-episode notice tasks (`~19%` of episodes), the step immediately following the first `AddToCart` wraps its observation as `{"kubi": [<notice_sentence>, ...], "misale": <obs>}` (`stockout`, `reprice`, `relax-drop`), plus `ConcludeTask` `refusal`s on finish-triggered events.
- **Process Rules**: Reference chains (`answer.refs`, `18/45` tasks) opened via `ReadDetails` or `LineUpListings` + hidden needs (`answer.needs`, `28/45` tasks: `22` value-revealing + `7` reply-by-reference with `t-aad4eba30e` in both) elicited via `AskShopper`. Basket notes are NOT a mandatory process gate (`process_rules: []`).
