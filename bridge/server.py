from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from bridge import drafts, mm_client

app = FastAPI()


class ActionContext(BaseModel):
    draft_id: str


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    context: ActionContext


@app.post("/aegis/approve")
def approve(req: ActionRequest) -> dict:
    draft = drafts.claim(req.context.draft_id)
    if draft is None:
        return {"update": {"message": "_Already handled._"}}
    mm_client.post_reply(
        channel_id=draft.target_channel_id,
        root_id=draft.root_id,
        text=draft.reply,
    )
    return {"update": {"message": "✓ Sent to channel.", "props": {}}}


@app.post("/aegis/discard")
def discard(req: ActionRequest) -> dict:
    drafts.claim(req.context.draft_id)  # atomic pop — drops it
    return {"update": {"message": "🗑 Discarded.", "props": {}}}
