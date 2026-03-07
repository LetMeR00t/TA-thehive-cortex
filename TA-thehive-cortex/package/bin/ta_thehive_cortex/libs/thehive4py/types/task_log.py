from typing import List, Dict

from thehive4py.types.attachment import OutputAttachment


class InputTaskLogRequired(Dict):
    message: str


class InputTaskLog(InputTaskLogRequired):
    startDate: int
    includeInTimeline: int
    attachments: List[str]


class OutputTaskLogRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: int
    message: str
    date: int
    owner: str
    extraData: dict


class OutputTaskLog(OutputTaskLogRequired):
    _updatedBy: str
    _updatedAt: int
    attachments: List[OutputAttachment]
    includeInTimeline: int


class InputUpdateTaskLog(Dict):
    message: str
    includeInTimeline: int
