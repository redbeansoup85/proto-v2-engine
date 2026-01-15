from pydantic import BaseModel
from typing import List


class InterpretationCard(BaseModel):
    title: str
    structural_summary: str
    actor_summaries: List[str]
    relation_summary: str
    risk_level: str
