# WR1 follow-up accepted

The reviewed candidate is `9ccf0f20a29733a7e0f2ea25ad972fbb49e84fa0`, with
the narrow follow-up `4ef1a3adea954ba936bc90249f7300304fde6bcc`.

The three new operational evidence references now pass through the existing
safe-path validator and must be canonical public `validation/` paths. Private
paths, traversal, authority paths including case variants, repeated slashes and
dot aliases reject. The resolved target must also remain in validation and
outside authorities. The canonical `experiments/` protocol and historical
comparator authority exceptions remain valid.

The public change consists only of this seven-line guard and its focused test.
The new private helper pins builder
`e4cb8d2c489ceab645e9654d8029c487fe402bdf0dd20ca6a1aad3a4384eb780`.
Its executable AST otherwise matches the prior helper; an explanatory comment
is the only additional textual change. The successor helper hash is
`a957d7e7df436fedf8fa587c6ba8476d22a52d390a9f2409447566c4d5acd56b`.

Independently reran twelve reporting controls, sixteen assembler controls and
all four prior review controls. All passed. The earlier WR1 counterexamples now
reject, including each of the three builder references and the helper route.
Valid public evidence still produces the invented report/metadata fixtures.
The numeric-binding and null/comparator controls also remain green. The earlier
eighty-four independent regression passes are reused because no other code or
consumer semantics changed.

All reviewed source bytes equal the committed blobs. The previous candidate's
private files, the original `47e8e5d...` helper and its receipts, and the prior
independent review are byte-exact and unchanged. WR1 is resolved by this new
receipt; the historical finding and failed review are preserved.

This accepts the source and private helper only. No actual cohort registry,
report, seal, scientific call, fit, publication installation or outcome
acceptance was performed by this review.
