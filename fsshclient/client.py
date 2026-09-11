import time
import aiohttp
import requests
from typing import overload, Literal

import json
import re

from bs4 import BeautifulSoup

from .enums import AnnouncementId, API_URL, ANN_URL
from .objects import News, PageInfo

class Client:
    def __init__(self):
        self._session: requests.Session | None = None
        self._update_time: float | None = None

    @property
    def session(self) -> requests.Session | None:
        return self._session

    @property
    def closed(self) -> bool:
        return self._session is None

    @property
    def update_time(self) -> float | None:
        return self._update_time

    @overload
    def get_news(self, uid: AnnouncementId, page: int=0, max_rows: int=30, keyword: str="", pageinfo: Literal[True]=True) -> tuple[list[News], PageInfo]: ...

    @overload
    def get_news(self, uid: AnnouncementId, page: int=0, max_rows: int=30, keyword: str="", pageinfo: Literal[False, None]=None) -> list[News]: ...

    def _init(self, *, force: bool=False) -> None:
        if self._session and not force:
            return
        if self._session:
            self.close()
        self._session = requests.Session()
        self._update_time = time.time()

    def _cleanup(self) -> None:
        self._session = None
        self._update_time = None

    def close(self) -> None:
        if self._session:
            self._session.close()
        self._cleanup()

    def _get_news(self, uid: AnnouncementId, page: int=0, max_rows: int=30, keyword: str=""):
        data = {
            "field": "time",
            "order": "DESC",
            "pageNum": page,
            "maxRows": max_rows,
            "keyword": keyword,
            "uid": uid.value,
            "tf": "1",
            "auth_type": "user",
        }

        resp = self.session.post(API_URL, data=data)
        return resp.json()

    def _get_detail(self, news_id: int) -> tuple[str, int]:
        url = f"https://www.fssh.khc.edu.tw/ischool/public/news_view/show.php?nid={news_id}"

        r = self.session.get(url)
        html = r.text

        soup = BeautifulSoup(html, "html.parser")
        content_element = soup.select_one("#content")
        content = content_element.get_text("\n", strip=True) if content_element else ""
        attachment_count = 0

        match = re.search(
            r"g_attached_file_json_data\s*=\s*(['\"])(.*?)\1",
            html,
            re.DOTALL
        )

        if match:
            try:
                files = json.loads(match.group(2))
                attachment_count = len(files)
            except json.JSONDecodeError:
                pass

        return content, attachment_count

    def get_news(self, uid: AnnouncementId, page: int=0, max_rows: int=30, keyword: str="", pageinfo: bool | None=None) -> list[News] | tuple[list[News], PageInfo]:
        self._init()
        data = self._get_news(uid, page, max_rows, keyword)

        results = []
        for news in data[1:]:
            content, filecount = self._get_detail(news["newsId"])
            results.append(
                News(
                    title=news["title"],
                    content=content,
                    filecount=filecount,
                    unitname=news["unit_name"],
                    unit=news["unit"],
                    clicks=news["clicks"],
                    name=news["name"],
                    issuer=int(news["issuer"]),
                    time=news["time"],
                    id=news["newsId"],
                    url=f"{ANN_URL}{news["newsId"]}",
                    image_url=news["news_image"],
                    is_sync=bool(news["is_sync"])
                )
            )

        if pageinfo:
            info = data[0]
            page = PageInfo(
                num=info["pageNum"],
                rows=info["maxRows"],
                total=info["totalPages"]
            )
            return results, page

        return results
    
class AsyncClient:
    def __init__(self, cache: bool=False):
        self._session: aiohttp.ClientSession | None=None
        self._update_time: float | None = None

    @property
    def session(self) -> aiohttp.ClientSession | None:
        return self._session

    @property
    def closed(self) -> bool:
        return True if not isinstance(self._session, aiohttp.ClientSession) else self._session.closed

    @property
    def update_time(self) -> float | None:
        return self._update_time

    @overload
    async def get_news(self, uid: AnnouncementId, page: int=0, max_rows: int=30, keyword: str="", pageinfo: Literal[True]=True) -> tuple[list[News], PageInfo]: ...

    @overload
    async def get_news(self, uid: AnnouncementId, page: int=0, max_rows: int=30, keyword: str="", pageinfo: Literal[False, None]=None) -> list[News]: ...

    async def _init(self, *, force: bool=False) -> None:
        if self._session and not self._session.closed and not force:
            return
        if self._session:
            await self.close()
        self._session = aiohttp.ClientSession()
        self._update_time = time.time()

    def _cleanup(self) -> None:
        self._session = None
        self._update_time = None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

        self._cleanup()

    async def _get_news(self, uid: AnnouncementId, page: int=0, max_rows: int=30, keyword: str=""):
        data = {
            "field": "time",
            "order": "DESC",
            "pageNum": page,
            "maxRows": max_rows,
            "keyword": keyword,
            "uid": uid.value,
            "tf": "1",
            "auth_type": "user",
        }
        # print(uid.value)
        async with self.session.post(API_URL, data=data) as resp:
            # text = await resp.text()
            # print(text)
            return await resp.json(content_type=None)

    async def _get_detail(self, news_id: int) -> tuple[str, int]:
        url = f"https://www.fssh.khc.edu.tw/ischool/public/news_view/show.php?nid={news_id}"

        async with self.session.get(url) as resp:
            # resp.raise_for_status()
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        content_element = soup.select_one("#content")
        content = content_element.get_text("\n", strip=True) if content_element else ""
        attachment_count = 0

        match = re.search(
            r"g_attached_file_json_data\s*=\s*(['\"])(.*?)\1",
            html,
            re.DOTALL
        )

        if match:
            try:
                files = json.loads(match.group(2))
                attachment_count = len(files)
            except json.JSONDecodeError:
                pass

        return content, attachment_count

    async def get_news(self, uid: AnnouncementId, page: int=0, max_rows: int=30, keyword: str="", pageinfo: bool | None = None) -> list[News] | tuple[list[News], PageInfo]:
        await self._init()
        data = await self._get_news(uid, page, max_rows, keyword)

        # print("current:", info["pageNum"])
        # print("max:", info["maxRows"])
        # print("total:", info["totalPages"])

        results = []
        for news in data[1:]:
            content, filecount = await self._get_detail(news["newsId"])
            results.append(
                News(
                    title=news["title"],
                    content=content,
                    filecount=filecount,
                    unitname=news["unit_name"],
                    unit=news["unit"],
                    clicks=news["clicks"],
                    name=news["name"],
                    issuer=int(news["issuer"]), 
                    time=news["time"],
                    id=news["newsId"],
                    url=f"{ANN_URL}{news["newsId"]}",
                    image_url=news["news_image"],
                    is_sync=bool(news["is_sync"])
                )
            )
        if pageinfo:
            info = data[0]

            page = PageInfo(
                num=info["pageNum"],
                rows=info["maxRows"],
                total=info["totalPages"]
            )
            return results, page

        return results