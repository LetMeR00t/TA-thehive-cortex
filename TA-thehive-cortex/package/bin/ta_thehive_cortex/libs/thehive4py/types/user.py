from typing import List, Dict


class InputUserRequired(Dict):
    login: str
    name: str
    profile: str


class InputUser(InputUserRequired):
    email: str
    password: str
    organisation: str
    type: str


class OutputOrganisationProfile(Dict):
    organisationId: str
    organisation: str
    profile: str


class OutputUserRequired(Dict):
    _id: str
    _createdBy: str
    _createdAt: int
    login: str
    name: str
    hasKey: bool
    hasPassword: bool
    hasMFA: bool
    locked: bool
    profile: str
    organisation: str
    type: str
    extraData: dict


class OutputUser(OutputUserRequired):
    _updatedBy: str
    _updatedAt: int
    email: str
    permissions: List[str]
    avatar: str
    organisations: List[OutputOrganisationProfile]
    defaultOrganisation: str


class InputUpdateUser(Dict):
    name: str
    organisation: str
    profile: str
    locked: bool
    avatar: str
    email: str
    defaultOrganisation: str


class InputUserOrganisationRequired(Dict):
    organisation: str
    profile: str


class InputUserOrganisation(InputUserOrganisationRequired):
    default: bool


class OutputUserOrganisation(Dict):
    organisation: str
    profile: str
    default: bool
