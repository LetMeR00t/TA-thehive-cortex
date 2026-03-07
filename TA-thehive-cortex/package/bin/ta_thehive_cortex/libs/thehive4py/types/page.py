from typing import Dict


class InputCasePageRequired(Dict):
    title: str
    content: str
    category: str


class InputCasePage(InputCasePageRequired):
    order: int


class OutputCasePageRequired(Dict):
    _id: str
    id: str
    createdBy: str
    createdAt: int
    title: str
    content: str
    _type: str
    slug: str
    order: int
    category: str


class OutputCasePage(OutputCasePageRequired):
    updatedBy: str
    updatedAt: int


class InputUpdateCasePage(Dict):
    title: str
    content: str
    category: str
    order: int
