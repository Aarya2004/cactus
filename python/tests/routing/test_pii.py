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
            additional_names=["Dr. Smith", "Mary Johnson"],
            fine_locations=["St. Michael's Hospital", "Sunnybrook Clinic"],
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

    def test_strips_additional_names(self):
        text = "Dr. Smith prescribed this and Mary Johnson is my wife"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("Dr. Smith", result)
        self.assertNotIn("Mary Johnson", result)
        self.assertIn("[PERSON_A]", result)
        self.assertIn("[PERSON_B]", result)

    def test_strips_fine_locations(self):
        text = "I was seen at St. Michael's Hospital and referred to Sunnybrook Clinic"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("St. Michael's Hospital", result)
        self.assertNotIn("Sunnybrook Clinic", result)
        self.assertIn("[FACILITY_A]", result)
        self.assertIn("[FACILITY_B]", result)

    def test_preserves_city_state(self):
        """City/state is medically relevant and too coarse to identify a patient."""
        text = "I live in Toronto, Ontario"
        result = self.stripper.strip(text, self.profile)
        self.assertIn("Toronto", result)
        self.assertIn("Ontario", result)

    def test_strips_phone_standard(self):
        text = "Call me at 555-123-4567"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("555-123-4567", result)
        self.assertIn("[PHONE]", result)

    def test_strips_phone_with_parentheses(self):
        text = "Call me at (555) 123-4567"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("(555) 123-4567", result)
        self.assertIn("[PHONE]", result)

    def test_strips_phone_e164(self):
        text = "My number is +1 647-937-2106"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("+1 647-937-2106", result)
        self.assertIn("[PHONE]", result)

    def test_strips_phone_dots(self):
        text = "Reach me at 555.987.6543"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("555.987.6543", result)
        self.assertIn("[PHONE]", result)

    def test_strips_email(self):
        text = "Email me at patient@example.com"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("patient@example.com", result)
        self.assertIn("[EMAIL]", result)

    def test_strips_ssn(self):
        text = "My SSN is 123-45-6789"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("123-45-6789", result)
        self.assertIn("[SSN]", result)

    def test_strips_address(self):
        text = "I live at 123 Main Street"
        result = self.stripper.strip(text, self.profile)
        self.assertNotIn("123 Main Street", result)
        self.assertIn("[ADDRESS]", result)

    def test_preserves_dates(self):
        """Dates must not be redacted as phone numbers."""
        text = "Symptoms started on 2026-04-18 and worsened by 2026-04-19"
        result = self.stripper.strip(text, self.profile)
        self.assertIn("2026-04-18", result)
        self.assertIn("2026-04-19", result)
        self.assertNotIn("[PHONE]", result)

    def test_preserves_medications(self):
        text = "Can I take ibuprofen with my lisinopril and atorvastatin?"
        result = self.stripper.strip(text, self.profile)
        self.assertIn("lisinopril", result)
        self.assertIn("atorvastatin", result)
        self.assertIn("ibuprofen", result)

    def test_preserves_supplements(self):
        text = "I'm taking fish oil and vitamin D daily"
        result = self.stripper.strip(text, self.profile)
        self.assertIn("fish oil", result)
        self.assertIn("vitamin D", result)

    def test_preserves_doses(self):
        text = "I take 10mg in the morning and 400 mg at night"
        result = self.stripper.strip(text, self.profile)
        self.assertIn("10mg", result)
        self.assertIn("400 mg", result)

    def test_preserves_times(self):
        text = "I took it at 8am and then again at 8:30pm"
        result = self.stripper.strip(text, self.profile)
        self.assertIn("8am", result)
        self.assertIn("8:30pm", result)

    def test_preserves_ages(self):
        text = "I'm 62 years old"
        result = self.stripper.strip(text, self.profile)
        self.assertIn("62 years old", result)

    def test_empty_profile(self):
        empty_profile = PIIProfile()
        text = "I take lisinopril 10mg at 8am, call me at 555-123-4567"
        result = self.stripper.strip(text, empty_profile)
        self.assertIn("lisinopril", result)
        self.assertIn("10mg", result)
        self.assertIn("8am", result)
        self.assertNotIn("555-123-4567", result)

    def test_combined_stripping(self):
        """Full example: strips identity PII, preserves medical info."""
        text = (
            "Sarah Johnson from Toronto, seen at St. Michael's Hospital, "
            "62 years old, takes lisinopril 10mg at 8am. Call (555) 123-4567"
        )
        result = self.stripper.strip(text, self.profile)
        # Identity stripped
        self.assertNotIn("Sarah Johnson", result)
        self.assertNotIn("St. Michael's Hospital", result)
        self.assertNotIn("(555) 123-4567", result)
        self.assertIn("[PATIENT]", result)
        self.assertIn("[FACILITY_A]", result)
        self.assertIn("[PHONE]", result)
        # City/state + medical info preserved
        self.assertIn("Toronto", result)
        self.assertIn("62 years old", result)
        self.assertIn("lisinopril", result)
        self.assertIn("10mg", result)
        self.assertIn("8am", result)


class TestPIIProfile(unittest.TestCase):

    def test_creates_empty_profile(self):
        profile = PIIProfile()
        self.assertIsNone(profile.patient_name)
        self.assertEqual(profile.medications, [])
        self.assertEqual(profile.supplements, [])
        self.assertEqual(profile.additional_names, [])
        self.assertEqual(profile.fine_locations, [])

    def test_creates_profile_with_data(self):
        profile = PIIProfile(
            patient_name="John Doe",
            medications=["aspirin"],
            supplements=["vitamin C"],
            additional_names=["Jane Doe"],
            fine_locations=["Mayo Clinic"],
        )
        self.assertEqual(profile.patient_name, "John Doe")
        self.assertEqual(profile.medications, ["aspirin"])
        self.assertEqual(profile.supplements, ["vitamin C"])
        self.assertEqual(profile.additional_names, ["Jane Doe"])
        self.assertEqual(profile.fine_locations, ["Mayo Clinic"])


if __name__ == "__main__":
    unittest.main()
