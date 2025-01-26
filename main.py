
import aiohttp, asyncio, json, datetime as dt
from bs4 import BeautifulSoup

from oauth2 import update_tokens

class Video:
    def __init__(self, id, title, channel, status):
        self.id = id
        self.title = title
        self.channel = channel
        self.status = status

    def __str__(self):
        return (f"  id: {self.id}\n" +
                f"  title: {self.title}\n" +
                f"  channel: {self.channel}\n" +
                f'  status: {self.status}\n\n')


async def add_page_videos(session, resp_json: dict, playlist: list[Video]):
    items = resp_json["items"]

    for item in items:
        status = item["status"]["privacyStatus"]

        if (status == "public"):
            continue

        id = item["contentDetails"].get("videoId", "None")
        title = item["snippet"].get("title", "None")
        channel = item["snippet"].get("videoOwnerChannelTitle", "None")

        vid = Video(id, title, channel, status)

        playlist.append(vid)
        

async def get_unavailable_videos(session, 
                                 access_token, 
                                 playlistId) -> list[Video]:
    params = {
        "key": api_key,
        "access_token" : access_token,
        "playlistId": playlistId,
        "part": "id,snippet,contentDetails,status",
        "maxResults": 50
    }

    playlist = []
    pagetoken = " "

    while pagetoken:
        
        responce = await session.get(urls["playListItems"], params=params)
        responce.raise_for_status()

        resp_json: dict = await responce.json()

        await add_page_videos(session, resp_json, playlist)

        pagetoken = resp_json.get("nextPageToken", None)
        if (pagetoken):
            params["pageToken"] = pagetoken
            
    
    return playlist

async def find_video_titles(session, playlists: dict[str, list[Video]]):
    tasks = {}
    async with asyncio.TaskGroup() as tg:
        for pl in playlists:
            for v in playlists[pl]:
                if (v.title in ("Deleted video", "Private video")):
                    cor = session.get(f"https://filmot.com/video/{v.id}")
                    tasks[v.id] = tg.create_task(cor)

    for pl in playlists:
        for v in playlists[pl]:
            if v.id not in tasks:
                continue
            resp = tasks[v.id].result()

            find_title = "Not found"
            find_channel = "Not found"
            if (resp.status == 200):
                soup = BeautifulSoup(await resp.text(), 'html.parser')
                content_divs = soup.find(id="playerparrent").div.find_all("div") # type: ignore
                find_title = list(content_divs[0].strings)[0].lstrip()
                find_channel = content_divs[1].a.text.lstrip()

            v.title += f" [{find_title}]"
            if (v.channel == "None"):
                v.channel += f" [{find_channel}]"


def write_videos(playlists: dict[str, list[Video]], file):
    for pl in playlists:
        title_out = ("\nНедоступные видео\n" +
                    f"Плейлист: {pl}\n\n")
        file.write(title_out)

        for v in playlists[pl]:
            file.write(str(v))



api_key = "AIzaSyC3auZRbqqMWXzegiwdmiHUO4JfPQagZrU"

urls = {
    "search" : "https://www.googleapis.com/youtube/v3/search",
    "playlists": "https://www.googleapis.com/youtube/v3/playlists",
    "playListItems" : "https://www.googleapis.com/youtube/v3/playlistItems"
}


async def main():
    with open("tokens.json", "r") as f:
        tokens = json.load(f)

    params = {
        "key": api_key,
        "access_token" : tokens["access_token"],
        # "channelId": "UC1k3Wu9upSjz5xcxnHXOWUA", #azamat
        #"channelId": "UCsgvZjDA4ZDyNA5O2UhzmNA",  #islam
        "mine" : "true",
        "kind": "youtube#playlistListResponse",
        "part": "id,snippet,contentDetails",
        "maxResults": 50

    }

    playlists = {}
    async with aiohttp.ClientSession() as session:
        responce = await session.get(urls["playlists"], params=params)

        if (responce.status == 401):
            tokens = await update_tokens()
            params["access_token"] = tokens["access_token"]
            responce = await session.get(urls["playlists"], params=params)

        responce.raise_for_status()

        pls_json = (await responce.json())["items"]

        async with asyncio.TaskGroup() as tg:
            tasks = {}
            i = 1
            for pl in pls_json:
                cor = get_unavailable_videos(session, 
                                             tokens["access_token"],
                                             pl["id"])
                
                task = tg.create_task(cor)
                tasks[pl["snippet"]["title"]] = task

                print(f'playlist #{i}')
                print(f'  id: {pl["id"]}')
                print(f'  title: {pl["snippet"]["title"]}')
                print(f'  itemCount: {pl["contentDetails"]["itemCount"]}\n')
                i += 1
    

        for pl_name in tasks:
            playlists[pl_name] = tasks[pl_name].result()

        tasks.clear()

        await find_video_titles(session, playlists)


    dfname = f"out-{dt.date.today().strftime("%d-%m-%Y")}.txt"
    filename = input(f"\nВведите название файла(по умолчанию {dfname}):") 
    filename = filename or dfname

    with open(filename, "w") as f:
        write_videos(playlists, f)
    


if (__name__ == "__main__"):
    asyncio.run(main())