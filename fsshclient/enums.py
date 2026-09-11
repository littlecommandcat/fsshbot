from enum import StrEnum

class AnnouncementId(StrEnum):
    ACADEMIC = "WID_0_2_0f075596d6cfd282f38872677912f105e9857086"       # 教務處公告
    STUDENT = "WID_0_2_b97df2647ed3f39629cf3b375fb5626df177a509"       # 學務處公告
    GENERAL = "WID_0_2_eb73f90747eaf1addc6d6ec6722acbd1deee9283"       # 總務處公告
    COUNSELING = "WID_0_2_d15d7e8c61796cb73c28c3e7efa2b067eefc2cef"       # 輔導室公告
    LIBRARY = "WID_0_2_fbeb2e84aae88a689cedc717974d1929154aad87"       # 圖書館公告
    MILITARY = "WID_0_2_a8bd7a4f048a7cfdeba0c6c915b89a32ee22df8b"       # 教官室公告
    OTHER = "WID_0_2_a5b6a9e2b61ae9c07d425bca74688ef922ed8fed"       # 其他公告

API_URL = "https://www.fssh.khc.edu.tw/ischool/widget/site_news/news_query_json.php"
ANN_URL = "https://www.fssh.khc.edu.tw/ischool/public/news_view/show.php?nid="