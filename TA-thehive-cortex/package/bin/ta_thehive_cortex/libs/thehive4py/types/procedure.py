from typing import Dict


class InputProcedureRequired(Dict):
    occurDate: int
    patternId: str


class InputProcedure(InputProcedureRequired):
    tactic: str
    description: str


class OutputProcedureRequired(Dict):
    _id: str
    _createdAt: int
    _createdBy: str
    occurDate: int
    tactic: str
    tacticLabel: str
    extraData: dict


class OutputProcedure(OutputProcedureRequired):
    _updatedAt: int
    _updatedBy: str
    description: str
    patternId: str
    patternName: str


class InputUpdateProcedure(Dict):
    description: str
    occurDate: int
