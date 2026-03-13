from typing import Any, Dict


class InputCustomFieldValueRequired(Dict):
    name: str


class InputCustomFieldValue(InputCustomFieldValueRequired):
    value: Any
    order: int


class OutputCustomFieldValue(Dict):
    _id: str
    name: str
    description: str
    type: str
    value: Any
    order: int


class InputCustomFieldRequired(Dict):
    name: str
    group: str
    description: str
    type: str


class InputCustomField(InputCustomFieldRequired):
    displayName: str
    mandatory: bool
    options: list


class OutputCustomFieldRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: int
    name: str
    displayName: str
    group: str
    description: str
    type: str
    mandatory: bool


class OutputCustomField(OutputCustomFieldRequired):
    _updatedBy: str
    _updatedAt: int
    options: list


class InputUpdateCustomField(Dict):
    displayName: str
    group: str
    description: str
    type: str
    options: list
    mandatory: bool
