import spaces
import gradio as gr
import uvicorn
from api import app as fastapi_app

@spaces.GPU
def _noop():
    return "OK"

with gr.Blocks() as demo:
    gr.Markdown("## AKT Backend API")
    btn = gr.Button("Ping")
    out = gr.Textbox()
    btn.click(_noop, outputs=out)

app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860, proxy_headers=True, forwarded_allow_ips="*")
