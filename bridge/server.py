from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from bridge import config, drafts, mm_client, mm_auth

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.MM_URL],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,
)


def get_user_id(authorization: str = Header(default=None)) -> str:
    """FastAPI dependency: extract + verify bearer token → user_id."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        return mm_auth.verify(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")


class ActionContext(BaseModel):
    draft_id: str


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    context: ActionContext


@app.post("/aegis/approve")
def approve(req: ActionRequest, user_id: str = Depends(get_user_id)) -> dict:
    draft = drafts.claim(req.context.draft_id)
    if draft is None:
        return {"update": {"message": "_Already handled._"}}
    try:
        mm_client.post_reply(
            channel_id=draft.target_channel_id,
            root_id=draft.root_id,
            text=draft.reply,
        )
    except Exception:
        drafts.put(draft)  # restore so user can retry
        raise             # FastAPI → 500; MM shows error, buttons remain
    return {"update": {"message": "✓ Sent to channel.", "props": {}}}


@app.post("/aegis/discard")
def discard(req: ActionRequest, user_id: str = Depends(get_user_id)) -> dict:
    drafts.claim(req.context.draft_id)  # atomic pop — drops it
    return {"update": {"message": "🗑 Discarded.", "props": {}}}
