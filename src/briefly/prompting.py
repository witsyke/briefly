from enum import Enum
from pathlib import Path

EXTRACTOR_FILE = Path(__file__).parent / "roles" / "extractor.md"


class BackendType(Enum):
    EXTRACTION = "extraction"
    DIGESTION = "digestion"
    REVISION = "revision"


def build_prompt(path: Path, type: BackendType) -> str:
    if type == BackendType.EXTRACTION:
        with open(EXTRACTOR_FILE) as extractor_file:
            base_prompt = extractor_file.read()
        return base_prompt.replace("{PDF}", str(path))
    else:
        raise NotImplementedError("Only Extraction is implemented so far.")
