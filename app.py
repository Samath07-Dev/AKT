import spaces
from gradio import Server
from api import app as fastapi_app

server = Server()

@spaces.GPU
@server.api(name="ping")
def ping() -> str:
    return "OK"

server.mount("/", fastapi_app)

if __name__ == "__main__":
    server.launch(server_name="0.0.0.0", server_port=7860)
