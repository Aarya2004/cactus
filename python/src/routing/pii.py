import re
from dataclasses import dataclass, field


@dataclass
class PIIProfile:
    """Known PII for a patient session.

    Only identity info (names) is stripped. Medical info — medications,
    supplements, dosages, age, times — is preserved because the cloud
    model needs it to give useful answers.
    """

    patient_name: str | None = None
    medications: list[str] = field(default_factory=list)
    supplements: list[str] = field(default_factory=list)
    additional_names: list[str] = field(default_factory=list)


class PIIStripper:
    """Strips personally identifiable information from text.

    Strips: patient name, additional names (family, doctors), locations,
    addresses, phone numbers, emails, SSNs.

    Does NOT strip: medications, supplements, dosages, age, times — these
    are medically relevant and the cloud model needs them.
    """

    def strip(self, text: str, profile: PIIProfile) -> str:
        result = text

        if profile.patient_name:
            pattern = re.compile(re.escape(profile.patient_name), re.IGNORECASE)
            result = pattern.sub("[PATIENT]", result)

        for idx, name in enumerate(profile.additional_names):
            label = f"[PERSON_{chr(65 + idx)}]"
            pattern = re.compile(re.escape(name), re.IGNORECASE)
            result = pattern.sub(label, result)

        result = re.sub(
            r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE]", result
        )

        result = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "[EMAIL]",
            result,
        )

        result = re.sub(
            r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b", "[SSN]", result
        )

        result = re.sub(
            r"\b\d{1,5}\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|court|ct|place|pl)\.?\b",
            "[ADDRESS]",
            result,
            flags=re.IGNORECASE,
        )

        return result
