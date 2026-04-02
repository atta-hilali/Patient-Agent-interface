# from __future__ import annotations
from __future__ import annotations

# import uuid
import uuid
# from typing import Optional
from typing import Optional

# from pydantic import BaseModel, Field
from pydantic import BaseModel, Field


# class PatientInput(BaseModel):
class PatientInput(BaseModel):
    # session_id: str = ""
    session_id: str = ""
    # message: str
    message: str
    # image_b64: Optional[str] = None
    image_b64: Optional[str] = None
    # modality: str = "text"
    modality: str = "text"
    # turn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    turn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


# class AgentEvent(BaseModel):
class AgentEvent(BaseModel):
    # type: str
    type: str
    # text: Optional[str] = None
    text: Optional[str] = None
    # citations: Optional[list] = None
    citations: Optional[list] = None
    # reason: Optional[str] = None
    reason: Optional[str] = None
    # turn_id: Optional[str] = None
    turn_id: Optional[str] = None
    # turn_complete: bool = False
    turn_complete: bool = False
