import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_list_parser import (  # noqa: E402
    ProjectListFormatError,
    ProjectVerificationError,
    extract_projects,
    verify_project,
)

EXPECTED_REF = "iwvmbdfkxrssduoqobgy"
EXPECTED_NAME = "SublimacionDobleR-prueba"


def project(**overrides):
    value = {
        "id": EXPECTED_REF,
        "ref": EXPECTED_REF,
        "name": EXPECTED_NAME,
        "status": "ACTIVE_HEALTHY",
        "linked": True,
    }
    value.update(overrides)
    return value


class ExtractProjectsTests(unittest.TestCase):
    def test_accepts_legacy_output_list(self):
        self.assertEqual(extract_projects([project()]), [project()])

    def test_accepts_cli_3_output_format_json_wrapper(self):
        payload = {"projects": [project()], "message": ""}
        self.assertEqual(extract_projects(payload), [project()])

    def test_accepts_structured_result_envelope(self):
        payload = {"type": "result", "data": {"projects": [project()]}}
        self.assertEqual(extract_projects(payload), [project()])

    def test_rejects_string_root(self):
        with self.assertRaisesRegex(ProjectListFormatError, "raíz JSON"):
            extract_projects("projects")

    def test_rejects_non_list_projects_field(self):
        with self.assertRaisesRegex(ProjectListFormatError, "debe ser una lista"):
            extract_projects({"projects": "invalid"})

    def test_rejects_non_object_project_before_get(self):
        with self.assertRaisesRegex(ProjectListFormatError, "índice 0 debe ser un objeto"):
            extract_projects({"projects": ["invalid"]})

    def test_rejects_non_text_identifier(self):
        with self.assertRaisesRegex(ProjectListFormatError, "campo 'id'.*debe ser texto"):
            extract_projects({"projects": [project(id=123)]})

    def test_rejects_unknown_object_wrapper(self):
        with self.assertRaisesRegex(ProjectListFormatError, "sin 'projects'"):
            extract_projects({"items": [project()]})


class VerifyProjectTests(unittest.TestCase):
    def test_verifies_exact_name_ref_and_status(self):
        result = verify_project(
            {"projects": [project()]},
            expected_ref=EXPECTED_REF,
            expected_name=EXPECTED_NAME,
        )
        self.assertEqual(result["id"], EXPECTED_REF)

    def test_accepts_ref_field_when_id_is_absent(self):
        value = project(ref=EXPECTED_REF)
        del value["id"]
        result = verify_project([value], expected_ref=EXPECTED_REF, expected_name=EXPECTED_NAME)
        self.assertEqual(result["ref"], EXPECTED_REF)

    def test_rejects_wrong_name_for_expected_ref(self):
        with self.assertRaisesRegex(ProjectVerificationError, "nombre distinto"):
            verify_project(
                [project(name="Otro")],
                expected_ref=EXPECTED_REF,
                expected_name=EXPECTED_NAME,
            )

    def test_rejects_missing_expected_ref(self):
        with self.assertRaisesRegex(ProjectVerificationError, "no contiene"):
            verify_project(
                [project(id="otro-ref", ref="otro-ref")],
                expected_ref=EXPECTED_REF,
                expected_name=EXPECTED_NAME,
            )

    def test_rejects_duplicate_expected_ref(self):
        with self.assertRaisesRegex(ProjectVerificationError, "aparece 2 veces"):
            verify_project(
                [project(), project()],
                expected_ref=EXPECTED_REF,
                expected_name=EXPECTED_NAME,
            )

    def test_rejects_conflicting_id_and_ref(self):
        with self.assertRaisesRegex(ProjectVerificationError, "contradictorios"):
            verify_project(
                [project(ref="otro-ref")],
                expected_ref=EXPECTED_REF,
                expected_name=EXPECTED_NAME,
            )

    def test_rejects_unhealthy_project(self):
        with self.assertRaisesRegex(ProjectVerificationError, "PAUSED"):
            verify_project(
                [project(status="PAUSED")],
                expected_ref=EXPECTED_REF,
                expected_name=EXPECTED_NAME,
            )


if __name__ == "__main__":
    unittest.main()
