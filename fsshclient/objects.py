from dataclasses import dataclass, asdict

@dataclass
class News:
    title: str
    content: str
    filecount: int
    unitname: str
    unit: int
    clicks: int
    name: str
    # issuer: int | str
    issuer: int
    time: str
    id: int
    url: str
    image_url: str | None=None
    is_sync: bool = False

    def to_dict(self):
        return asdict(self)

@dataclass
class PageInfo:
    num: int
    rows: int
    total: int

    def to_dict(self):
        return asdict(self)