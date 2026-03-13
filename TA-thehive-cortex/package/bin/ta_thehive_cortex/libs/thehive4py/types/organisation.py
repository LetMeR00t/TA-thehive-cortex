from typing import List, Dict


class InputOrganisationLink(Dict):
    linkType: str
    otherLinkType: str


class InputBulkOrganisationLinkRequired(Dict):
    toOrganisation: str
    linkType: str
    otherLinkType: str


class InputBulkOrganisationLink(InputBulkOrganisationLinkRequired):
    avatar: str


class OutputSharingProfile(Dict):
    name: str
    description: str
    autoShare: bool
    editable: bool
    permissionProfile: str
    taskRule: str
    observableRule: str


class InputOrganisationRequired(Dict):
    name: str
    description: str


class InputOrganisation(InputOrganisationRequired):
    taskRule: str
    observableRule: str
    locked: bool


class OutputOrganisationRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: int
    name: str
    description: str
    taskRule: str
    observableRule: str
    locked: bool
    extraData: dict


class OutputOrganisation(OutputOrganisationRequired):
    _updatedBy: str
    _updatedAt: int
    links: List[InputOrganisationLink]
    avatar: str


class InputUpdateOrganisation(Dict):
    name: str
    description: str
    taskRule: str
    observableRule: str
    locked: bool
    avatar: str


class OutputOrganisationLink(Dict):
    linkType: str
    otherLinkType: str
    organisation: OutputOrganisation
