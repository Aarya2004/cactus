import re
from dataclasses import dataclass, field


@dataclass
class PIIProfile:
    """Known PII for a patient session.

    Only identity info is stripped. Medical info — medications, supplements,
    dosages, age, times, city/state — is preserved because the cloud model
    needs it to give useful answers.
    """

    patient_name: str | None = None
    medications: list[str] = field(default_factory=list)
    supplements: list[str] = field(default_factory=list)
    additional_names: list[str] = field(default_factory=list)
    fine_locations: list[str] = field(default_factory=list)


class PIIStripper:
    """Strips personally identifiable information from text.

    Strips: patient name, additional names, fine-grained locations (clinics,
    hospitals, specific facilities), street addresses, phone numbers (E.164
    and North American formats), emails, SSNs.

    Preserves: medications, supplements, dosages, age, times, city/state.
    City and state are medically relevant (regional formularies, altitude,
    climate) and too coarse to identify a patient.
    """

    _PHONE_PATTERN = re.compile(
        r"(?:\+\d{1,3}[\s.-]?)?"
        r"(?:\(\d{1,4}\)[\s.-]?)?"
        r"\d{1,4}[\s.-]?\d{1,4}[\s.-]?\d{2,4}"
        r"(?:\s*(?:ext|x)\.?\s*\d{1,5})?"
    )

    _ADDRESS_PATTERN = re.compile(
        r"\b\d{1,5}\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd"
        r"|drive|dr|lane|ln|way|court|ct|place|pl)\.?\b",
        re.IGNORECASE,
    )

    _EMAIL_PATTERN = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )

    _SSN_PATTERN = re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b")

    def strip(self, text: str, profile: PIIProfile) -> str:
        result = text

        if profile.patient_name:
            pattern = re.compile(re.escape(profile.patient_name), re.IGNORECASE)
            result = pattern.sub("[PATIENT]", result)

        for idx, name in enumerate(profile.additional_names):
            label = f"[PERSON_{chr(65 + idx)}]"
            pattern = re.compile(re.escape(name), re.IGNORECASE)
            result = pattern.sub(label, result)

        for idx, loc in enumerate(profile.fine_locations):
            label = f"[FACILITY_{chr(65 + idx)}]"
            pattern = re.compile(re.escape(loc), re.IGNORECASE)
            result = pattern.sub(label, result)

        result = self._SSN_PATTERN.sub("[SSN]", result)
        result = self._PHONE_PATTERN.sub("[PHONE]", result)
        result = self._EMAIL_PATTERN.sub("[EMAIL]", result)
        result = self._ADDRESS_PATTERN.sub("[ADDRESS]", result)

        return result
