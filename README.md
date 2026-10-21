# fsshbot

建立於[fsshclient](https://github.com/littlecommandcat/fsshclient)、[fssaclient](https://github.com/littlecommandcat/fssaclient)及[Discordpy-Music](https://github.com/littlecommandcat/Discordpy-Music)的自動化機器人

## 設置

`.env.example`自行替換配製成`.env`
```ini
TOKEN=yourdiscordbottoken
ANNOUNCE_CHANNEL=yourchannelid
KBOOK_CHANNEL=yourchannelid
DYNAMIC_CHANNEL=yourchannelid
MUSIC_CHANNEL=yourchannelid

LAVALINK_HOST=https://yourhost
LAVALINK_PORT=443
LAVALINK_PASSWORD=yourpassword
```

`ANNOUNCE_CHANNEL` 及 `KBOOK_CHANNEL` 兩個頻道皆須為論壇頻道，`MUSIC_CHANNEL` 及 `DYNAMIC_CHANNEL` 則須為語音頻道。

## 安裝

安裝相關套件
```ini
pip install -r requirements.txt
```

## 功能

- 抓取校網的公告並發送貼文

- 抓取K書中心公告並發送貼文

- 動態語音頻道創見與刪除

- 無限循環播放校歌(可使用Lavalink或Nodelink)

## 測試

`test.py`進行測試[fsshclient](https://github.com/littlecommandcat/fsshclient)