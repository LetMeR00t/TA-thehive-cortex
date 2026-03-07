from typing import List, Dict


class OutputTimelineEventRequired(Dict):
    date: int
    kind: str
    entity: str
    entityId: str
    details: dict


class OutputTimelineEvent(OutputTimelineEventRequired):
    endDate: int


class OutputTimeline(Dict):
    events: List[OutputTimelineEvent]


class InputCustomEventRequired(Dict):
    date: int
    title: str


class InputCustomEvent(InputCustomEventRequired):
    endDate: int
    description: str


class OutputCustomEventRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: int
    date: int
    title: str


class OutputCustomEvent(OutputCustomEventRequired):
    _updatedBy: str
    _updatedAt: int
    endDate: int
    description: str


class InputUpdateCustomEvent(Dict):
    date: int
    endDate: int
    title: str
    description: str
