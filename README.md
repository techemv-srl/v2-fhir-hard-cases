# v2-fhir-hard-cases

A small, shared corpus of difficult HL7 v2 to FHIR R4 conversion cases. It is
not an implementation guide and not a competing specification: the HL7 v2-to-FHIR
IG maps the intent of the standard, while this corpus records what real-world
messages do to implementations. Disagreements about a conversion usually end in
prose; a case gives people something executable to disagree against.

## What a case contains

Each case lives in its own folder, `cases/<NNN>-<short-slug>/`:

- `message.hl7`: the source v2 message, with segments separated by CR (`\r`),
  as on the wire.
- `case.yaml`: the manifest. It states the v2 version, the message type as in
  MSH-9, the trigger event, the hop, the transaction and actors, whether the
  message initiates a workflow, what a validation pass covers, the accepted
  answers, the declared losses, the embedded attachments, and the provenance of
  the data. The format is defined by [`schema/case.schema.json`](schema/case.schema.json).
- `expected/`: one FHIR JSON Bundle per accepted answer.
- `attachments/`: the original binaries of embedded attachments, with their
  SHA-256.

A case with `status: todo` is work in progress and may have no message or no
accepted answers yet.

## Key principles

**More than one accepted answer.** A case can have several accepted answers,
each with its rationale and the exchange pattern it serves. A single expected
Bundle would only move the disagreement to whoever committed first.

**Distinguish the hop.** Converting v2 to an enterprise model should be
lossless, so that hop gets a strict diff. Moving from the enterprise model to a
specific repository is lossy by design, so multiple answers are normal there.
Each case declares which hop it is about.

**A pass states what it covered.** A pass names the Bundle including its
entries, the pinned package set, and the SNOMED CT edition. Two tools can both
say "pass" after validating different things.

**Attachments ship a SHA-256.** Embedded attachments come with the SHA-256 of
the original bytes, so "same bytes" can be checked rather than assumed.

**Workflow initiation is declared.** Whether a message initiates a workflow
(for example a Task) is declared by the case, not inferred from the message.

## Repository layout

```
cases/
  <NNN>-<short-slug>/
    case.yaml           manifest
    message.hl7         source v2 message, CR-separated
    expected/           one FHIR JSON Bundle per accepted answer
    attachments/        original binaries and their .sha256 files
schema/
  case.schema.json      JSON Schema for case.yaml
scripts/
  validate_cases.py     structural checks (does not run the FHIR validator)
  requirements.txt
CONTRIBUTING.md
DCO
LICENSE-CODE            Apache-2.0, for scripts/ and other tooling
LICENSE-DATA            CC-BY-4.0, for everything under cases/
NOTICE
```

To run the structural checks:

```
pip install -r scripts/requirements.txt
python scripts/validate_cases.py
```

The script checks that each manifest matches the schema, that every referenced
file exists, that SHA-256 values match (including the Base64 data embedded in
the message), and that `message.hl7` uses CR separators. It does not run the
FHIR validator.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: no PHI, one case per pull
request, contributions signed off under the DCO, and disagreement is expressed
by adding an accepted answer rather than replacing one.

## License

Copyright 2026 TechEMV S.r.l. and contributors. Case data under `cases/` is
licensed under CC-BY-4.0 ([LICENSE-DATA](LICENSE-DATA)); code under `scripts/`
and other tooling is licensed under Apache-2.0 ([LICENSE-CODE](LICENSE-CODE)).
See [NOTICE](NOTICE).

---

Maintained by TechEMV (https://www.techemv.it), makers of BridgeLab.
