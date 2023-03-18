from typing import List, Dict


class InputTaskRequired(Dict):
    title: str


class InputTask(InputTaskRequired):
    group: str
    description: str
    status: str
    flag: bool
    startDate: int
    endDate: int
    order: int
    dueDate: int
    assignee: str


class OutputTaskRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: int
    title: str
    group: str
    status: str
    flag: bool
    order: int
    extraData: dict


class OutputTask(OutputTaskRequired):
    _updatedBy: str
    _updatedAt: int
    description: str
    startDate: int
    endDate: int
    assignee: str
    dueDate: int


class InputUpdateTask(Dict):
    title: str
    group: str
    description: str
    status: str
    flag: bool
    startDate: int
    endDate: int
    order: int
    dueDate: int
    assignee: str


class InputBulkUpdateTask(InputUpdateTask):
    ids: List[str]
