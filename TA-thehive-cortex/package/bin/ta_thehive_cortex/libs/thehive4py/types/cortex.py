from typing import Any, Dict, List, Dict


class OutputAnalyzerRequired(Dict):
    id: str
    name: str
    version: str
    description: str


class OutputAnalyzer(OutputAnalyzerRequired):
    dataTypeList: List[str]
    cortexIds: List[str]


class OutputResponderRequired(Dict):
    id: str
    name: str
    version: str
    description: str


class OutputResponder(OutputResponderRequired):
    dataTypeList: List[str]
    cortexIds: List[str]


class OutputAnalyzerJobRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: str
    analyzerId: str
    analyzerName: str
    analyzerDefinition: str
    status: str
    startDate: str
    cortexId: str
    cortexJobId: str
    id: str
    operations: str


class OutputAnalyzerJob(OutputAnalyzerJobRequired):
    _updatedBy: str
    _updatedAt: str
    endDate: str
    report: Dict[str, Any]
    case_artifact: Dict[str, Any]


class OutputResponderActionRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: str
    responderId: str
    status: str
    startDate: str
    cortexId: str
    cortexJobId: str
    id: str
    operations: str


class OutputResponderAction(OutputResponderActionRequired):
    _updatedBy: str
    _updatedAt: str
    endDate: str
    report: Dict[str, Any]
    responderName: str
    responderDefinition: str


class InputResponderActionRequired(Dict):
    objectId: str
    objectType: str
    responderId: str


class InputResponderAction(InputResponderActionRequired):
    parameters: Dict[str, Any]
    tlp: int


class InputAnalyzerJobRequired(Dict):
    analyzerId: str
    cortexId: str
    artifactId: str


class InputAnalyzerJob(InputAnalyzerJobRequired):
    parameters: Dict[str, Any]
