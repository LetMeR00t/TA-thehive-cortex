from typing import Dict


class InputComment(Dict):
    message: str


class OutputCommentRequired(Dict):
    _id: str
    _type: str
    createdBy: str
    createdAt: int
    message: str
    isEdited: bool


class OutputComment(OutputCommentRequired):
    updatedAt: str


class InputUpdateComment(Dict):
    message: str
