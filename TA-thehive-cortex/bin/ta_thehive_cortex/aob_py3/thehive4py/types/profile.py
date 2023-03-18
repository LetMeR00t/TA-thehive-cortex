from typing import List, Dict


class InputProfileRequired(Dict):
    name: str


class InputProfile(InputProfileRequired):
    permissions: List[str]


class OutputProfileRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: int
    name: str
    editable: bool
    isAdmin: bool


class OutputProfile(OutputProfileRequired):
    _updatedBy: str
    _updatedAt: int
    permissions: List[str]


class InputUpdateProfile(Dict):
    name: str
    permissions: List[str]
