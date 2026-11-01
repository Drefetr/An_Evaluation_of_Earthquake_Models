# Publication privacy

Public attribution uses the supplied GitHub handles, Drefetr and magna-nz. The paper retains scholarly citations and the collaborators' AI-workflow disclosure. No legal names, personal contact addresses, or affiliations are inferred.

Public scientific provenance should use project-relative paths or stable archive identifiers. Personal machine roots, home directories, hostnames, process identifiers, and transient worker/control state are unnecessary unless a specific methodological claim requires a retained field. Original source identities remain recorded separately from explicitly transformed public variants; sanitization must not silently change scientific results or source custody.

Historical privacy and input-exclusion receipts are indexed in the [historical archive](../provenance/historical_archive.json). They describe the payload and inspection scope at their recorded date. In particular, an earlier scan of 140 files does not establish that every later addition was inspected. Current membership is recorded in `MANIFEST.json`, and current check coverage is described in [validation documentation](../validation/README.md).

Before publication, inspect staged content as well as filenames: common credential/private-key patterns, machine-specific paths and metadata, PDF text/metadata/attachments, and Git author/contact metadata. Ignore rules do not protect an already tracked file. Keep raw build logs, bytecode, local configuration, credentials, provider transcripts, and private investigation archives outside the public payload. Scientific source bindings may require recorded public variants when an operational path changes.

The October 2026 metadata cleanup removed a saved response cookie and transient request identifier from a catalogue extract while retaining retrieval dates, selection rules, and historical identities. Current tree cleanup does not remove material from earlier published Git commits. Pattern checks cannot guarantee detection of every sensitive value; a payload hash check alone is not a privacy audit.
