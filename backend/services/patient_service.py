"""
Patient service: ID generation, CRUD operations.
"""

import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


def generate_patient_id() -> str:
    """Generate a unique patient ID in format ROP-YYYYMMDD-XXXX."""
    date_part = datetime.now().strftime("%Y%m%d")
    unique_part = uuid.uuid4().hex[:4].upper()
    return f"ROP-{date_part}-{unique_part}"
