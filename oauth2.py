import webbrowser, asyncio, aiohttp
import string, random, base64, json
from hashlib import sha256
from http.client import responses
from urllib.parse import urlencode, parse_qs, urlparse

class HttpResponce:
    def __init__(self,
                 content:bytes = b"",
                 content_type:str = None,
                 status:int = 200,
                 reason:str = None,
                 charset:str = None,
                 headers:dict = None,
                 ) -> None:
        self.http_ver: str = "1.1"
        self.status_code: int = int(status)
        if not 100 <= self.status_code <= 599:
            raise ValueError("HTTP status code must be an integer from 100 to 599.")
        
        self.reason_phrase = reason or responses[self.status_code]
        self._charset = charset or "utf-8"
        self.content: bytes = content
        self.headers: dict = headers if headers else {}

        if ("Content-Type" not in self.headers):
            self.headers["Content-Type"] = (f"{content_type or 'text/html'}; "
                                            + f"charset={self._charset}")

    def serialize_headers(self) -> bytes:
        res = f"HTTP/{self.http_ver} {self.status_code} {self.reason_phrase}\r\n"
        for key, value in self.headers.items():
            res += f"{key}: {value}\r\n"
        if ("Content-Length" not in self.headers):
            res += f"Content-Length: {len(self.content)}\r\n"

        return res.encode()

    def serialize(self) -> bytes:
        return self.serialize_headers() + b"\r\n" + self.content



async def http_sendFile(writer : asyncio.StreamWriter, filename : str):
    f = open(filename, "rb")
    resp = HttpResponce(f.read())

    writer.write(resp.serialize())
    await writer.drain()


async def run_server(address : tuple) -> str:
    async def print_path(reader: asyncio.StreamReader, 
                         writer : asyncio.StreamWriter):
        line = await reader.readline()
        line = line.decode()

        path = line.split(" ")[1]

        query = parse_qs(urlparse(path).query)

        nonlocal code 
        if ("code" in query):
            await http_sendFile(writer, "success_page.html")
            print("stop serving")

            code = query["code"][0]

            server.close()
            await server.wait_closed()
        elif ("error" in query): 
            raise RuntimeError(f"error: {query['error'][0]}")
        else:
            writer.write(HttpResponce(status=404))
            writer.drain()

        writer.close()
        await writer.wait_closed()
    
    code = ""
    server = await asyncio.start_server(print_path, *address)

    print("start serving")
    
    try:
        await server.serve_forever()
    except asyncio.CancelledError:
        pass

    return code


async def getAuthorizationCode(client_secret : dict, 
                         code_verifier: str,
                         scopes : list) -> str:
    
    s256_hash = sha256(code_verifier.encode("ascii")).digest()
    b64_encode = base64.urlsafe_b64encode(s256_hash).rstrip(b'=')

    params = {
        "client_id" : client_secret["client_id"],
        "code_challenge" : b64_encode.decode('ascii'),
        "code_challenge_method" : "S256",
        "response_type" : "code",
        "scope" : " ".join(scopes),

    }

    server = {
        "ip" : "localhost",
        "port" : 8080
    }

    params["redirect_uri"] = f"http://{server['ip']}:{server['port']}"

    url = client_secret["auth_uri"] + "?" + urlencode(params)

    print("please grant permitions to your google account va browser\n")
    webbrowser.open_new_tab(url)

    code = await run_server(("localhost", 8080))

    return code

async def exchangeCodeForTokens(code: str, 
                          client_secret: dict, 
                          code_verifier: str) -> dict:
    data = {
        "client_id" : client_secret["client_id"],
        "client_secret" : client_secret["client_secret"],
        "code" : code,
        "code_verifier" : code_verifier,
        "grant_type" : "authorization_code",
        "redirect_uri" : "http://localhost:8080"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(client_secret["token_uri"], data=data) as resp:
            resp_json = await resp.json()

    return resp_json

async def getTokens(client_secret: dict) -> dict:
    code_verifier = ''.join(random.choices(string.ascii_uppercase + 
                                           string.ascii_lowercase + 
                                           string.digits, k=53))
    
    scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
    
    code = await getAuthorizationCode(client_secret, code_verifier, scopes)
    tokens = await exchangeCodeForTokens(code, client_secret, code_verifier)

    return tokens


async def update_tokens() -> dict:
    with open("client_secret.json", "r") as f:
        secret = json.load(f)
    
    tokens = await getTokens(secret["installed"])

    with open("tokens.json", "w") as f:
        json.dump(tokens, f, indent=4)
    print("tokens saved to file \"tokens2.json\"\n")

    return tokens

if (__name__ == "__main__"):
    tokens = asyncio.run(update_tokens())
    print(f"tokens:\n{tokens}")

    







    
