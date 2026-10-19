# Contributing

Contributions are welcome: new cases, additional accepted answers for existing
cases, and fixes to the tooling.

## No PHI, ever

Every message, Bundle and attachment must be either synthetic or scrubbed.
If it is scrubbed, `case.yaml` must say how (`provenance: scrubbed` and
`scrubbing_method`). A pull request that contains real patient data is closed
and the repository history is rewritten to remove it.

## Developer Certificate of Origin

Contributions are accepted under the Developer Certificate of Origin 1.1, whose
text is in the [DCO](DCO) file. Every commit must carry a `Signed-off-by` line
with your real name and email address, certifying that you have the right to
submit the contribution under the licenses of this repository:

```
git commit -s
```

Case data under `cases/` and documentation are contributed under CC-BY-4.0,
and code under `scripts/`, `schema/` and other tooling under Apache-2.0 (see
[NOTICE](NOTICE)).

## One case per pull request

Each pull request adds or changes one case. In the description, explain why the
case is hard, not only what it contains: which implementations disagree, what
goes wrong, and which hop is affected (`v2-to-enterprise` or
`enterprise-to-repository`).

A new case needs:

- a folder `cases/<NNN>-<short-slug>/`, using the next free number;
- `message.hl7`, with segments separated by CR (`\r`) only;
- `case.yaml`, following [`schema/case.schema.json`](schema/case.schema.json);
- one JSON Bundle in `expected/` per accepted answer;
- for embedded attachments, the original binary in `attachments/` and its
  SHA-256 in `case.yaml` and in a `<file>.sha256` file.

A case may be submitted with `status: todo` and no accepted answers yet, so that
others can propose answers.

Run the structural checks before opening the pull request:

```
pip install -r scripts/requirements.txt
python scripts/validate_cases.py
```

When you add an accepted answer, state in `validation` what your pass covered:
the Bundle including its entries, the pinned package versions, and the SNOMED CT
edition.

## Disagreeing with an existing answer

Add another accepted answer, with its own Bundle, rationale and exchange
pattern. Do not replace or edit the existing answer to match your view. If an
existing answer contains a plain error (for example an invalid Bundle, or a
value that contradicts the message), open an issue or a pull request that
explains the error.
