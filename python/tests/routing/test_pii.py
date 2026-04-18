import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.routing.pii import PIIStripper, PIIProfile


class TestPIIStripper(unittest.TestCase):

    def setUp(self):
        self.profile = PIIProfile(
            patient_name="Sarah Johnson",
            medications=["lisinopril", "atorvastatin", "sertraline"],
            supplements=["fish oil", "vitamin D", "magnesium"],
        )
        self.stripper = PIIStripper()

    def test_strips_patient_name(self):
        text = "Sarah Johnson wants to know about her medication"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("Sarah Johnson", result)
        self.assertIn("[PATIENT]", result)

    def test_strips_patient_name_case_insensitive(self):
        text = "sarah johnson asked about side effects"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("sarah johnson", result)
        self.assertIn("[PATIENT]", result)

    def test_strips_medications(self):
        text = "Can I take ibuprofen with my lisinopril and atorvastatin?"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("lisinopril", result)
        self.assertNotIn("atorvastatin", result)
        self.assertIn("[DRUG_A]", result)
        self.assertIn("[DRUG_B]", result)

    def test_strips_supplements(self):
        text = "I'm taking fish oil and vitamin D daily"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("fish oil", result)
        self.assertNotIn("vitamin D", result)
        self.assertIn("[SUPP_A]", result)
        self.assertIn("[SUPP_B]", result)

    def test_strips_doses(self):
        text = "I take 10mg in the morning and 400 mg at night"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("10mg", result)
        self.assertNotIn("400 mg", result)
        self.assertEqual(result.count("[DOSE]"), 2)

    def test_strips_times(self):
        text = "I took it at 8am and then again at 8:30pm"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("8am", result)
        self.assertNotIn("8:30pm", result)
        self.assertEqual(result.count("[TIME]"), 2)

    def test_strips_time_expressions(self):
        text = "I took it this morning and will take another tonight"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("this morning", result)
        self.assertNotIn("tonight", result)
        self.assertEqual(result.count("[TIME]"), 2)

    def test_strips_ages(self):
        text = "I'm 62 years old and my husband is 65 yo"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("62 years old", result)
        self.assertNotIn("65 yo", result)
        self.assertEqual(result.count("[AGE]"), 2)

    def test_strips_age_patterns(self):
        text = "Patient age 72 with history of hypertension"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("age 72", result)
        self.assertIn("[AGE]", result)

    def test_preserves_unknown_drugs(self):
        text = "Can I take acetaminophen?"
        result = self.stripper.strip(text, self.profile)
        self.assertIn("acetaminophen", result)

    def test_empty_profile(self):
        empty_profile = PIIProfile()
        text = "I take lisinopril 10mg at 8am"
        result = self.stripper.strip(text, empty_profile)
        self.assertIn("lisinopril", result)
        self.assertNotIn("10mg", result)
        self.assertNotIn("8am", result)

    def test_combined_stripping(self):
        text = "Sarah Johnson, 62 years old, takes lisinopril 10mg at 8am with fish oil"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("Sarah Johnson", result)
        self.assertNotIn("62 years old", result)
        self.assertNotIn("lisinopril", result)
        self.assertNotIn("10mg", result)
        self.assertNotIn("8am", result)
        self.assertNotIn("fish oil", result)


class TestPIIProfile(unittest.TestCase):

    def test_creates_empty_profile(self):
        profile = PIIProfile()
        self.assertIsNone(profile.patient_name)
        self.assertEqual(profile.medications, [])
        self.assertEqual(profile.supplements, [])

    def test_creates_profile_with_data(self):
        profile = PIIProfile(
            patient_name="John Doe",
            medications=["aspirin"],
            supplements=["vitamin C"],
        )
        self.assertEqual(profile.patient_name, "John Doe")
        self.assertEqual(profile.medications, ["aspirin"])
        self.assertEqual(profile.supplements, ["vitamin C"])


if __name__ == "__main__":
    unittest.main()
