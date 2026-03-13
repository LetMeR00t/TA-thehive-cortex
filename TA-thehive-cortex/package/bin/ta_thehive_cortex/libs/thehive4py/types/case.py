from typing import Any, List, Dict, Union

from thehive4py.types.observable import OutputObservable
from thehive4py.types.page import InputCasePage
from thehive4py.types.share import InputShare

from .custom_field import InputCustomFieldValue, OutputCustomFieldValue
from .task import InputTask

CaseStatusValue = [
    "New",
    "InProgress",
    "Indeterminate",
    "FalsePositive",
    "TruePositive",
    "Other",
    "Duplicated",
]


class CaseStatus:
    New: CaseStatusValue = "New"
    InProgress: CaseStatusValue = "InProgress"
    Indeterminate: CaseStatusValue = "Indeterminate"
    FalsePositive: CaseStatusValue = "FalsePositive"
    TruePositive: CaseStatusValue = "TruePositive"
    Other: CaseStatusValue = "Other"
    Duplicated: CaseStatusValue = "Duplicated"


ImpactStatusValue = ["NotApplicable", "WithImpact", "NoImpact"]


class ImpactStatus:
    NotApplicable: ImpactStatusValue = "NotApplicable"
    WithImpact: ImpactStatusValue = "WithImpact"
    NoImpact: ImpactStatusValue = "NoImpact"


class InputCaseRequired(Dict):
    title: str
    description: str


class InputCase(InputCaseRequired):
    severity: int
    startDate: int
    endDate: int
    tags: List[str]
    flag: bool
    tlp: int
    pap: int
    status: CaseStatusValue
    summary: str
    assignee: str
    access: dict
    customFields: Union[List[InputCustomFieldValue], dict]
    caseTemplate: str
    tasks: List[InputTask]
    pages: List[InputCasePage]
    sharingParameters: List[InputShare]
    taskRule: str
    observableRule: str


class OutputCaseRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: int
    number: int
    title: str
    description: str
    severity: int
    severityLabel: str
    startDate: int
    flag: bool
    tlp: int
    tlpLabel: str
    pap: int
    papLabel: str
    status: CaseStatusValue
    stage: str
    access: dict
    extraData: dict
    newDate: int
    timeToDetect: int


class OutputCase(OutputCaseRequired):
    _updatedBy: str
    _updatedAt: int
    endDate: int
    tags: List[str]
    summary: str
    impactStatus: ImpactStatusValue
    assignee: str
    customFields: List[OutputCustomFieldValue]
    userPermissions: List[str]
    inProgressDate: int
    closedDate: int
    alertDate: int
    alertNewDate: int
    alertInProgressDate: int
    alertImportedDate: int
    timeToTriage: int
    timeToQualify: int
    timeToAcknowledge: int
    timeToResolve: int
    handlingDuration: int


class InputUpdateCase(Dict):
    title: str
    description: str
    severity: int
    startDate: int
    endDate: int
    tags: List[str]
    flag: bool
    tlp: int
    pap: int
    status: str
    summary: str
    assignee: str
    impactStatus: str
    customFields: Union[List[InputCustomFieldValue], dict]
    taskRule: str
    observableRule: str
    addTags: List[str]
    removeTags: List[str]


class InputBulkUpdateCase(InputUpdateCase):
    ids: List[str]


class InputImportCaseRequired(Dict):
    password: str


class InputImportCase(InputImportCaseRequired):
    sharingParameters: List[InputShare]
    taskRule: str
    observableRule: str


class InputApplyCaseTemplateRequired(Dict):
    ids: List[str]
    caseTemplate: str


class InputApplyCaseTemplate(InputApplyCaseTemplateRequired):
    updateTitlePrefix: bool
    updateDescription: bool
    updateTags: bool
    updateSeverity: bool
    updateFlag: bool
    updateTlp: bool
    updatePap: bool
    updateCustomFields: bool
    importTasks: List[str]
    importPages: List[str]


class OutputCaseObservableMerge(Dict):
    untouched: int
    updated: int
    deleted: int


class OutputCaseLinkRequired(Dict):
    linksCount: int


class OutputCaseLink(OutputCase, OutputCaseLinkRequired):
    linkedWith: List[OutputObservable]


class OutputImportCaseRequired(Dict):
    case: OutputCase


class OutputImportCase(OutputImportCaseRequired):
    observables: List[OutputObservable]
    procedures: List[OutputObservable]
    errors: List[Any]


class InputCaseOwnerOrganisationRequired(Dict):
    organisation: str


class InputCaseOwnerOrganisation(InputCaseOwnerOrganisationRequired):
    keepProfile: str
    taskRule: str
    observableRule: str


class InputCaseAccess(Dict):
    access: dict  # TODO: refine type hint


class InputCaseLink(Dict):
    type: str
    caseId: str


class InputURLLink(Dict):
    type: str
    url: str
