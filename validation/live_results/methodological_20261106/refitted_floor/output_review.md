# Independent audit of completed S04B floor sensitivity

Verdict: PASS_SAVED_OUTPUT_AUDIT. All eighty saved case reports, four exact pilot reuses, 480 historical floor comparisons, 400 procedure contrasts and twenty aggregate rows reconcile. The reviewer performed hash checks and saved-output arithmetic only: no additional fit, native build/load, simulation or eventwise score evaluation.

## Main result

For the matched broad/long immigrant generator, the saved raw magnitude-scaled immigrant procedure has mean gain 5.163051793339105 against the train-refitted floor, with nineteen strict-positive wins in twenty histories. Its historical mean gain was 48.38675124400008; the floor's mean held-out score increase is 43.22369945066097.

For the matched broad/long total generator, the saved raw total-attenuation procedure has mean gain 9.736735835918074 against the train-refitted floor, with eighteen wins in twenty histories. Its historical mean gain was 53.233233302568976; the floor's mean score increase is 43.49649746665091.

Every aggregate was independently recomputed from its twenty saved cases; the maximum discrepancy from the published run summary is zero. The complete reaggregated twenty-row table and per-regime floor-change distributions are in result.json. These are comparator-sensitivity results on the fixed synthetic roster, not significance, parameter-recovery or prospective-validation findings.

## Identities and numerical checks

- Full result SHA-256: 127e281a63279e1cdaed94f7d96f1f320991f08cb690e1f3ce1b9c6e03593bd0.
- Pilot result SHA-256: 93ee3e17b7c5ef3d7c86a9c0febd691e5704e228cd9feb1ba9124bbee2b69968.
- Runner: a91c6e9d8337e5b5856bd21e13e73da33e3f538718117f81bd53e91be8d4207a.
- Protocol: a1794b96655812cc83291f56f6f3fe58a51baca98d96aa2de089ebcc8c9d7a29.
- Native radial library: 0601867389ac82f96e7999d5a0af00c49b0ed1ccbd811300475d50666c35c990.

The pilot and full source/input/native identities are identical. All ten scientific source pins and all 560 required original input files match the frozen manifest. Every case report matches its recorded hash. The four reused pilot reports are byte-identical, and the remaining seventy-six are marked as new scalar training fits. All four fixed seed ranges are complete without duplicates or substitutions.

For each original model fit, the review independently reconstructs the selected candidate from the saved eligible training records. Original raw/BIC choices, selected state indices, off-floor indicators, original gains and saved test scores are unchanged. Every refitted gain agrees with both direct saved-score subtraction and old gain minus floor score change; their maximum discrepancies are zero.

The score review checks all historical/refitted phase decompositions, C=-E, NLL=-joint, timing+location+mark, delta signs, unchanged mark and trigger terms, and the exact closed-form background integral at the recorded intercept. Maximum discrepancies:
- Historical floor reconstruction against saved state: 6.821210263296962e-13 nats.
- Joint decomposition: 5.684341886080802e-14 nats.
- Timing/location decomposition: 2.2737367544323206e-13 nats.
- Delta decomposition: 1.9895196601282805e-13 nats.
- Independently evaluated background integral: 1.4210854715202004e-14 nats.
- Reported archived-formula control residual: 2.2737367544323206e-13 nats.

All eighty fitted intercepts are inside the declared box and classified interior, with opposing endpoint derivative signs. Maximum recorded relative derivative residual is 2.8530901378251477e-13, and maximum root iterations is fifteen. Every training joint score improves; the smallest improvement is 0.0008291696078686073 nats. The fitted intercept range is [-3.761461446346846,-1.4060109094580728].

The root residuals and archived-formula residuals are audited recorded diagnostics, not newly recomputed eventwise derivatives. The immutable reviewed algorithm and execution receipts support their interpretation; this review does not disguise saved-output arithmetic as a second fitting campaign.

## Execution and recovery

The initial attempt passed all nineteen deterministic controls and the native compilation. The supervisor then refused to proceed because its identified MSVC vctip helper remained alive. The initial phase list contains only fixtures and compilation; no pilot/full output directory exists for that attempt.

The recovery record names the same PID and creation time captured by the build supervisor, records termination and no remaining owned process, and states zero scientific histories executed. The continuation pins the failed-attempt and recovery records and reuses the exact successful build and controls. All execution/log hashes reconcile. A fresh read-only process-identity check found none of the recorded owned processes still alive.

Continuation outer wall times were approximately 1.856 seconds for the pilot and 6.886 seconds for the full phase. The measured numerical process-tree RSS peak was 80,457,728 bytes; the largest sampled peak including compilation was 150,933,504 bytes. Elapsed UTC time from the initial attempt through cleanup and completed continuation was 50.908999 seconds. The pilot workload projection independently recomputes exactly and is inside the unchanged budget.

Memory was sampled every 0.1 seconds with threshold-triggered termination; this is not an instantaneous hard OS memory proof. Every successful execution phase records exit zero, no stop reason and no remaining owned processes.

## Scope

No additional scientific campaign was run during this review. It confirms the saved comparator-sensitivity arithmetic, immutable original decisions, declared optimizer checks and custody/resource chain. It does not certify the global optimality of historical inhibited fits or attribute held-out losses to null heavy-tail moments.

