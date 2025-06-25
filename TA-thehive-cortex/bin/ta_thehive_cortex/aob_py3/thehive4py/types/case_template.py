from typing import List, Dict, Union

from .custom_field import InputCustomFieldValue
from .task import InputTask, OutputTask

SeverityValue = [1, 2, 3, 4]
TlpValue = [0, 1, 2, 3, 4]
PapValue = [0, 1, 2, 3]


class InputCaseTemplateRequired(Dict):
    name: str


class InputCaseTemplate(InputCaseTemplateRequired):
    displayName: str
    titlePrefix: str
    description: str
    severity: int
    tags: List[str]
    flag: bool
    tlp: int
    pap: int
    summary: str
    tasks: List[InputTask]
    pageTemplateIds: List[str]
    customFields: Union[dict, List[InputCustomFieldValue]]


class OutputCaseTemplateRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: int
    name: str


class OutputCaseTemplate(OutputCaseTemplateRequired):
    _updatedBy: str
    _updatedAt: int
    displayName: str
    titlePrefix: str
    description: str
    severity: int
    tags: List[str]
    flag: bool
    tlp: int
    pap: int
    summary: str
    tasks: List[OutputTask]
    pageTemplateIds: List[str]
    customFields: Union[dict, List[InputCustomFieldValue]]
