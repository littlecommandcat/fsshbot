from fsshclient import Client, AnnouncementId
import requests
cli = Client()
cli._init(force=True)
r = cli.get_news(AnnouncementId.ACADEMIC)
print(r[2].content)