# Qualifying Twin Pack (`s14_qual`, 30 Tasks, `w-2385fe7c5e6d`)

- **Pack Path**: `~/sn15-ops/suites/graded30_v2/packs/s14_qual` (`pack_id: p-forge-s14-qual`, `world_id: w-2385fe7c5e6d`)
- **Corpus**: 120 primary Qualifying episodes (`fb_ours_06ae244e` 60 [`39/60 = 0.650`] + `fb_06ae23f7` KISAME 60 [`44/60 = 0.733`], `83/120` passing episodes) + 180 additional field Qualifying episodes (`fb_06ade337` C.RONALDO `49/60`, `fb_06ade49f` Hello World `50/60`, `fb_06ae0e63` TERRY `43/60` = `300` total episodes, `225/300` passing).
- **Catalog**: `3090` products across 22 aisles (`3,056` baseline + `34` additional items observed in the 300 Qualifying transcripts).
- **Tool Surface (`8` tools)**: `find_goods` (4-row price-ascending pagination via `token_token`/`further` `vuvepa4..vuvepa68`, `98.6%` page-1 overlap with live `w-2385fe7c5e6d`), `detail_product`, `contrast_products` (max 4 IDs), `put_quantity` (`plus`/`discard`), `trolley_contents`, `contact_customer` (metered 3 messages), `submit_purchase`, `decline`.
- **Hard Slice (`qual_hard18` / `ids_qual_hard18.txt`)**: `12` unique tasks covering all 18 of our `not_the_best_option` (7 eps) and `request_not_met` (11 eps) failures in `fb_ours_06ae244e` (`t-3254025544,t-32cbbe307e,t-3553587b35,t-38edeb49f9,t-4818b794cc,t-58da11237f,t-a9bf915ffc,t-b47de9595e,t-cfa0144fb0,t-e622afe641,t-fa3dff6e42,t-fc0b16b797`).
