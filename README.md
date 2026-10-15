# fsshbot

建立於[fsshclient](https://github.com/littlecommandcat/fsshclient)之基礎上

`.env.example`自行替換配製成`.env`
```ini
TOKEN=yourdiscordbottoken  # bot token
ANNOUNCE_CHANNEL=yourchannelid  # 公告論壇頻道id
KBOOK_CHANNEL=yourkbookchannelid  # K書中心公告論壇頻道id（與 ANNOUNCE_CHANNEL 不同）
```

`ANNOUNCE_CHANNEL` 供 `cogs/announcement.py` 使用（`last_id` 記錄於 `data.json`）；`KBOOK_CHANNEL` 供 `cogs/kbook_announcement.py` 使用，負責轉發 [K書中心](https://kbook.fssh.khc.edu.tw/) 公告（`last_id` 與已發布清單 `seen_ids` 記錄於 `kbook_data.json`）。兩個頻道皆須為 Discord 論壇頻道。

安裝相關套件
```ini
pip install requirements.txt
```

`test.py`進行測試[fsshclient](https://github.com/littlecommandcat/fsshclient)