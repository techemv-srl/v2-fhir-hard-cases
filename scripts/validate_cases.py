#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TechEMV S.r.l. and contributors
"""Structural checks for the cases under cases/.

Checks, per case:
  - case.yaml matches schema/case.schema.json and its id equals the folder name;
  - every file referenced by the manifest exists;
  - expected answers are JSON Bundles, and every expected/*.json is referenced;
  - SHA-256 values match the attachment files, their .sha256 sidecars, and the
    Base64 data embedded in message.hl7;
  - message.hl7 uses CR segment separators.

It does NOT run the FHIR validator. Cases with status 'todo' may have no
message.hl7 and no accepted answers.

Usage: python scripts/validate_cases.py [CASE_DIR ...]
"""

import base64
import binascii
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "case.schema.json"
CASES_DIR = ROOT / "cases"

SEGMENT_ID = re.compile(r"^[A-Z][A-Z0-9]{2}$")
SEGMENT_FIELD = re.compile(r"^([A-Z][A-Z0-9]{2})-([0-9]+)$")


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys instead of silently keeping the last one."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate key {key!r}", key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def check_message(path, errors):
    """Check CR separators and segment ids. Return the list of segments, or None."""
    raw = path.read_bytes()
    if not raw:
        errors.append("message.hl7 is empty")
        return None
    if not raw.startswith(b"MSH") or len(raw) < 8:
        errors.append("message.hl7 does not start with an MSH segment")
        return None
    if b"\n" in raw:
        errors.append("message.hl7 contains LF; segments must be separated by CR only")
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"message.hl7 is not valid UTF-8: {exc}")
        return None
    segments = text.split("\r")
    if segments[-1] == "":
        segments.pop()
    field_sep = text[3]
    for number, segment in enumerate(segments, start=1):
        if not segment:
            errors.append(f"message.hl7: empty segment at position {number}")
            continue
        seg_id = segment.split(field_sep, 1)[0]
        if not SEGMENT_ID.match(seg_id):
            errors.append(f"message.hl7: segment {number} has an invalid segment id {seg_id!r}")
    return segments


def get_field(segments, seg_name, field_no, occurrence):
    """Return the raw value of <seg_name>-<field_no> in the given occurrence, or None."""
    field_sep = segments[0][3]
    matches = [s for s in segments if s.split(field_sep, 1)[0] == seg_name]
    if len(matches) < occurrence:
        return None
    fields = matches[occurrence - 1].split(field_sep)
    # In MSH the field separator itself is MSH-1, so indexes shift by one.
    index = field_no - 1 if seg_name == "MSH" else field_no
    if index >= len(fields):
        return None
    return fields[index]


def check_embedded(segments, attachment, expected_sha, errors):
    match = SEGMENT_FIELD.match(attachment["segment_field"])
    seg_name, field_no = match.group(1), int(match.group(2))
    occurrence = attachment.get("occurrence", 1)
    label = f"{seg_name}-{field_no} (occurrence {occurrence})"
    value = get_field(segments, seg_name, field_no, occurrence)
    if value is None:
        errors.append(f"attachment {attachment['file']}: {label} not found in message.hl7")
        return
    encoding_chars = segments[0][4:8]
    component_sep, repetition_sep = encoding_chars[0], encoding_chars[1]
    first_repetition = value.split(repetition_sep, 1)[0]
    components = first_repetition.split(component_sep)
    # ED: source application ^ type of data ^ data subtype ^ encoding ^ data
    if len(components) != 5 or components[3].lower() != "base64":
        errors.append(f"attachment {attachment['file']}: {label} is not an ED value with Base64 encoding")
        return
    stripped = re.sub(r"\s+", "", components[4])
    try:
        decoded = base64.b64decode(stripped, validate=True)
    except (binascii.Error, ValueError) as exc:
        errors.append(f"attachment {attachment['file']}: {label} is not valid Base64 after removing whitespace: {exc}")
        return
    if sha256_hex(decoded) != expected_sha:
        errors.append(f"attachment {attachment['file']}: decoded {label} does not match sha256 {expected_sha}")


def check_case(case_dir, validator):
    errors = []
    manifest_path = case_dir / "case.yaml"
    if not manifest_path.is_file():
        return ["missing case.yaml"], None
    try:
        manifest = yaml.load(manifest_path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        return [f"case.yaml is not valid YAML: {exc}"], None

    schema_errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path))
    for err in schema_errors:
        location = "/".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"case.yaml {location}: {err.message}")
    if schema_errors:
        return errors, None

    status = manifest["status"]
    if manifest["id"] != case_dir.name:
        errors.append(f"id {manifest['id']!r} does not match folder name {case_dir.name!r}")

    segments = None
    message_path = case_dir / "message.hl7"
    if message_path.is_file():
        segments = check_message(message_path, errors)
    elif status != "todo":
        errors.append("missing message.hl7")

    referenced = set()
    for answer in manifest.get("accepted_answers", []):
        rel = answer["file"]
        if rel in referenced:
            errors.append(f"accepted answer {rel} is listed more than once")
            continue
        referenced.add(rel)
        path = case_dir / rel
        if not path.is_file():
            errors.append(f"accepted answer {rel} does not exist")
            continue
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"accepted answer {rel} is not valid JSON: {exc}")
            continue
        if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
            errors.append(f"accepted answer {rel} is not a Bundle (resourceType)")

    expected_dir = case_dir / "expected"
    if expected_dir.is_dir():
        for path in sorted(expected_dir.glob("*.json")):
            rel = path.relative_to(case_dir).as_posix()
            if rel not in referenced:
                errors.append(f"{rel} is not listed in accepted_answers")

    for attachment in manifest.get("attachments", []):
        rel = attachment["file"]
        path = case_dir / rel
        if not path.is_file():
            errors.append(f"attachment {rel} does not exist")
            continue
        actual = sha256_hex(path.read_bytes())
        if actual != attachment["sha256"]:
            errors.append(f"attachment {rel}: sha256 is {actual}, case.yaml says {attachment['sha256']}")
        sidecar = path.with_name(path.name + ".sha256")
        if sidecar.is_file():
            recorded = sidecar.read_text(encoding="utf-8").split()
            if not recorded or recorded[0].lower() != actual:
                errors.append(f"{sidecar.relative_to(case_dir).as_posix()} does not match the file")
        if segments is not None:
            check_embedded(segments, attachment, attachment["sha256"], errors)

    return errors, status


def main(argv):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    if argv:
        case_dirs = [Path(arg).resolve() for arg in argv]
    else:
        case_dirs = sorted(p for p in CASES_DIR.iterdir() if p.is_dir())
    if not case_dirs:
        print("no cases found")
        return 1

    failed = 0
    for case_dir in case_dirs:
        if not case_dir.is_dir():
            print(f"FAIL {case_dir}: not a directory")
            failed += 1
            continue
        errors, status = check_case(case_dir, validator)
        if errors:
            failed += 1
            print(f"FAIL {case_dir.name}")
            for error in errors:
                print(f"     - {error}")
        else:
            print(f"OK   {case_dir.name}" + (" (todo)" if status == "todo" else ""))

    print(f"\n{len(case_dirs) - failed} of {len(case_dirs)} cases passed structural checks")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
