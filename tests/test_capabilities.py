import itertools
import unittest

from app.capabilities import (
    FLAG_NAMES,
    CapabilityPolicy,
    denial_reason,
    is_publication_path,
    is_upload_path,
)


class TestCapabilityPolicy(unittest.TestCase):
    def policy(self, **overrides):
        values = {name: "false" for name in FLAG_NAMES}
        values.update(overrides)
        return CapabilityPolicy.from_mapping(values)

    def test_all_64_flag_combinations_preserve_broad_denials(self):
        for bits in itertools.product((False, True), repeat=len(FLAG_NAMES)):
            values = {name: str(value).lower() for name, value in zip(FLAG_NAMES, bits)}
            policy = CapabilityPolicy.from_mapping(values)
            if values["MAINTENANCE_MODE"] == "true":
                self.assertFalse(policy.public_reads)
                self.assertFalse(policy.writes)
                self.assertFalse(policy.uploads)
                self.assertFalse(policy.publication)
            if values["READ_ONLY_MODE"] == "true" or values["DISABLE_WRITES"] == "true":
                self.assertFalse(policy.writes)
                self.assertFalse(policy.uploads)
                self.assertFalse(policy.publication)

    def test_invalid_value_fails_closed(self):
        policy = self.policy(DISABLE_WRITES="maybe")
        self.assertFalse(policy.valid)
        self.assertTrue(policy.maintenance)
        self.assertEqual(policy.invalid_flags, ("DISABLE_WRITES",))

    def test_scoped_switches_do_not_overreach(self):
        upload = self.policy(DISABLE_UPLOADS="true")
        self.assertTrue(upload.writes)
        self.assertFalse(upload.uploads)
        self.assertTrue(upload.publication)

        publication = self.policy(DISABLE_PUBLICATION="true")
        self.assertTrue(publication.writes)
        self.assertTrue(publication.uploads)
        self.assertFalse(publication.publication)

    def test_route_classification(self):
        self.assertTrue(is_publication_path("POST", "/api/projects/prj_x/publish"))
        self.assertTrue(is_publication_path("POST", "/api/projects/prj_x/claims/clm_x/publish"))
        self.assertFalse(is_publication_path("POST", "/api/projects/prj_x/claims"))
        self.assertTrue(is_upload_path("POST", "/api/projects/prj_x/documents"))
        self.assertFalse(is_upload_path("POST", "/api/projects/prj_x/documents/doc_x/scan"))

    def test_health_and_ready_never_denied(self):
        policy = self.policy(MAINTENANCE_MODE="true")
        self.assertIsNone(denial_reason(policy, "GET", "/health", {}))
        self.assertIsNone(denial_reason(policy, "GET", "/ready", {}))

    def test_public_read_switch_allows_authenticated_private_read(self):
        policy = self.policy(DISABLE_PUBLIC_READS="true")
        self.assertEqual(denial_reason(policy, "GET", "/api/projects", {}), "public_reads_disabled")
        self.assertIsNone(
            denial_reason(policy, "GET", "/api/projects?include_private=1", {"Authorization": "Bearer x"})
        )

    def test_write_denials_precede_scoped_denials(self):
        policy = self.policy(DISABLE_WRITES="true", DISABLE_PUBLICATION="true")
        self.assertEqual(
            denial_reason(policy, "POST", "/api/projects/prj_x/publish", {"Authorization": "Bearer x"}),
            "writes_disabled",
        )


if __name__ == "__main__":
    unittest.main()
