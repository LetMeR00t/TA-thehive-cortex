from typing import Dict


class OutputShareRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: int
    caseId: str
    profileName: str
    organisationName: str
    owner: bool
    taskRule: str
    observableRule: str


class OutputShare(OutputShareRequired):
    _updatedBy: str
    _updatedAt: int


class InputShareRequired(Dict):
    organisation: str


class InputShare(InputShareRequired):
    share: bool
    profile: str
    taskRule: str
    observableRule: str
