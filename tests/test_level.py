"""What level a schema change forces. Anything not recognised fails towards major."""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import level  # noqa: E402

SPEC = "https://oo-ld.org/1.0.1/meta/oold-meta-schema.json"

BASE = {
    "$schema": SPEC,
    "$id": "A.schema.json",
    "title": "A",
    "description": "an A",
    "type": "object",
    "@context": {"value": "qudt:value", "unit": {"@id": "qudt:hasUnit", "@type": "@vocab"}},
    "properties": {
        "value": {"type": "number", "minimum": 0, "description": "the number"},
        "unit": {"type": "string", "enum": ["a", "b"]},
        "note": {"type": "string"},
    },
    "required": ["value"],
}


def changed(edit):
    schema = copy.deepcopy(BASE)
    edit(schema)
    return level.compare(BASE, schema)[0]


class Breaks(unittest.TestCase):
    def test_a_tightened_constraint_is_major(self):
        self.assertEqual(changed(lambda s: s["properties"]["value"].update(minimum=10)), "major")

    def test_a_new_constraint_keyword_is_major(self):
        self.assertEqual(changed(lambda s: s["properties"]["note"].update(pattern="^x")), "major")

    def test_a_property_gaining_a_ref_is_major(self):
        edit = lambda s: s["properties"]["note"].update(  # noqa: E731
            {"$ref": "B.schema.json"})
        self.assertEqual(changed(edit), "major")

    def test_a_nested_constraint_is_major(self):
        def edit(s):
            s["properties"]["list"] = {"type": "array", "items": {"type": "number"}}
        base = copy.deepcopy(BASE)
        base["properties"]["list"] = {"type": "array", "items": {"type": "number"}}
        tight = copy.deepcopy(base)
        tight["properties"]["list"]["items"]["maximum"] = 5
        self.assertEqual(level.compare(base, tight)[0], "major")

    def test_a_schema_level_keyword_is_major(self):
        self.assertEqual(changed(lambda s: s.update(additionalProperties=False)), "major")

    def test_a_defs_constraint_is_major(self):
        base = copy.deepcopy(BASE)
        base["$defs"] = {"D": {"type": "number", "minimum": 0}}
        tight = copy.deepcopy(base)
        tight["$defs"]["D"]["minimum"] = 1
        self.assertEqual(level.compare(base, tight)[0], "major")

    def test_a_changed_default_is_major(self):
        self.assertEqual(changed(lambda s: s["properties"]["note"].update(default="x")), "major")

    def test_a_context_coercion_change_is_major(self):
        edit = lambda s: s["@context"]["unit"].update({"@type": "@id"})  # noqa: E731
        self.assertEqual(changed(edit), "major")

    def test_a_property_becoming_optional_is_major(self):
        self.assertEqual(changed(lambda s: s.update(required=[])), "major")

    def test_a_required_name_outside_properties_is_tracked(self):
        base = copy.deepcopy(BASE)
        base["required"] = ["value", "inherited"]
        looser = copy.deepcopy(base)
        looser["required"] = ["value"]
        self.assertEqual(level.compare(base, looser)[0], "major")


class Safe(unittest.TestCase):
    def test_prose_is_a_patch(self):
        def edit(s):
            s["title"] = "A better title"
            s["description"] = "clearer"
            s["properties"]["value"]["description"] = "the number, clearer"
            s["examples"] = [{"value": 1}]
            s["$comment"] = "note"
        self.assertEqual(changed(edit), "patch")

    def test_prose_inside_a_defs_entry_is_a_patch(self):
        base = copy.deepcopy(BASE)
        base["$defs"] = {"D": {"type": "number", "description": "old"}}
        new = copy.deepcopy(base)
        new["$defs"]["D"]["description"] = "new"
        self.assertEqual(level.compare(base, new)[0], "patch")

    def test_a_property_named_description_is_not_mistaken_for_prose(self):
        base = copy.deepcopy(BASE)
        base["properties"]["description"] = {"type": "string"}
        new = copy.deepcopy(base)
        new["properties"]["description"]["type"] = "number"
        self.assertEqual(level.compare(base, new)[0], "major")

    def test_enum_data_named_title_is_not_stripped(self):
        base = copy.deepcopy(BASE)
        base["properties"]["kind"] = {"type": "string", "default": {"title": "x"}}
        new = copy.deepcopy(base)
        new["properties"]["kind"]["default"] = {"title": "y"}
        self.assertEqual(level.compare(base, new)[0], "major")

    def test_an_optional_property_is_still_minor(self):
        self.assertEqual(changed(lambda s: s["properties"].update(extra={"type": "string"})),
                         "minor")

    def test_a_new_enum_member_is_still_minor(self):
        self.assertEqual(changed(lambda s: s["properties"]["unit"]["enum"].append("c")), "minor")

    def test_adding_a_schema_uuid_is_a_patch(self):
        self.assertEqual(changed(lambda s: s.update({"x-oold-uuid": "d06f35fd"})), "patch")

    def test_changing_or_removing_a_schema_uuid_is_major(self):
        base = copy.deepcopy(BASE)
        base["x-oold-uuid"] = "d06f35fd"
        other = copy.deepcopy(base)
        other["x-oold-uuid"] = "461f22a8"
        self.assertEqual(level.compare(base, other)[0], "major")
        gone = copy.deepcopy(base)
        del gone["x-oold-uuid"]
        self.assertEqual(level.compare(base, gone)[0], "major")

    def test_no_change_is_none(self):
        self.assertEqual(level.compare(BASE, copy.deepcopy(BASE))[0], "none")

    def test_provenance_of_a_mapping_is_a_patch(self):
        base = copy.deepcopy(BASE)
        base["x-oold-context"] = {"value": {"emmo:V": {"x-oold-sssom": {
            "predicate_id": "skos:exactMatch", "mapping_set_id": "s", "confidence": 0.5}}}}
        new = copy.deepcopy(base)
        new["x-oold-context"]["value"]["emmo:V"]["x-oold-sssom"]["confidence"] = 1.0
        self.assertEqual(level.compare(base, new)[0], "patch")


class Reasons(unittest.TestCase):
    def test_the_reason_names_what_changed(self):
        schema = copy.deepcopy(BASE)
        schema["properties"]["value"]["minimum"] = 10
        _, reasons = level.compare(BASE, schema)
        self.assertTrue(any("value" in r and "minimum" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
