from typing import Dict


class InputObservableTypeRequired(Dict):
    name: str


class InputObservableType(InputObservableTypeRequired):
    isAttachment: bool


class OutputObservableTypeRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: int
    name: str
    isAttachment: bool


class OutputObservableType(OutputObservableTypeRequired):
    _updatedBy: str
    _updatedAt: int
