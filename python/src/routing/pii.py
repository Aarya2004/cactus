import re
from dataclasses import dataclass, field


@dataclass
class PIIProfile:
    patient_name: str | None = None
    medications: list[str] = field(default_factory=list)
    supplements: list[str] = field(default_factory=list)


class PIIStripper:
    def strip(self, text: str, profile: PIIProfile) -> str:
        result = text

        if profile.patient_name:
            pattern = re.compile(
                re.escape(profile.patient_name), re.IGNORECASE
            )
            result = pattern.sub("[PATIENT]", result)

        for idx, med in enumerate(profile.medications):
            label = f"[DRUG_{chr(65 + idx)}]"
            pattern = re.compile(re.escape(med), re.IGNORECASE)
            result = pattern.sub(label, result)

        for idx, supp in enumerate(profile.supplements):
            label = f"[SUPP_{chr(65 + idx)}]"
            pattern = re.compile(re.escape(supp), re.IGNORECASE)
            result = pattern.sub(label, result)

        result = re.sub(r"\b\d+(\.\d+)?\s*mg\b", "[DOSE]", result, flags=re.IGNORECASE)

        result = re.sub(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", "[TIME]", result, flags=re.IGNORECASE)
        result = re.sub(
            r"\b(this morning|this evening|this afternoon|yesterday|today|tonight|at noon|at midnight)\b",
            "[TIME]",
            result,
            flags=re.IGNORECASE,
        )

        result = re.sub(r"\b\d{1,3}\s*(years?\s*old|yo)\b", "[AGE]", result, flags=re.IGNORECASE)
        result = re.sub(r"\bage\s*\d{1,3}\b", "[AGE]", result, flags=re.IGNORECASE)
        result = re.sub(r"\bI'?m\s+\d{1,3}\b", "I'm [AGE]", result, flags=re.IGNORECASE)

        return result
