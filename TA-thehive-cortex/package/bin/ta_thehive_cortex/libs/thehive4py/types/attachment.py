from typing import List, Dict


class OutputAttachmentRequired(Dict):
    _id: str
    _type: str
    _createdBy: str
    _createdAt: int
    name: str
    size: int
    contentType: str
    id: str


class OutputAttachment(OutputAttachmentRequired):
    _updatedBy: str
    _updatedAt: int
    hashes: List[str]
