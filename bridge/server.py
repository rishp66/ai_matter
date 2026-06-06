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


class SendRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    draft_id: str
    text: str


@app.get("/aegis/drafts")
def list_drafts(user_id: str = Depends(get_user_id)) -> list[dict]:
    return [
        {
            "id": d.id,
            "reply": d.reply,
            "reason": d.reason,
            "provenance": d.provenance,
            "contexts": d.contexts,
            "trigger_text": d.trigger_text,
            "channel_id": d.target_channel_id,
        }
        for d in drafts.list_for_owner(user_id)
    ]


@app.post("/aegis/approve")
def approve(req: ActionRequest, user_id: str = Depends(get_user_id)) -> dict:
    draft = drafts.claim(req.context.draft_id)
    if draft is None:
        return {"update": {"message": "_Already handled._"}}
    if draft.owner_user_id != user_id:
        drafts.put(draft)  # restore — wrong owner
        raise HTTPException(status_code=403, detail="Not your draft")
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
    draft = drafts.claim(req.context.draft_id)
    if draft is None:
        return {"update": {"message": "_Already handled._"}}
    if draft.owner_user_id != user_id:
        drafts.put(draft)  # restore — wrong owner
        raise HTTPException(status_code=403, detail="Not your draft")
    return {"update": {"message": "🗑 Discarded.", "props": {}}}


@app.post("/aegis/send")
def send(req: SendRequest, user_id: str = Depends(get_user_id)) -> dict:
    draft = drafts.claim(req.draft_id)
    if draft is None:
        return {"update": {"message": "_Already handled._"}}
    if draft.owner_user_id != user_id:
        drafts.put(draft)  # restore — wrong owner
        raise HTTPException(status_code=403, detail="Not your draft")
    try:
        mm_client.post_reply(draft.target_channel_id, draft.root_id, req.text)
    except Exception:
        drafts.put(draft)
        raise
    return {"update": {"message": "✓ Sent to channel.", "props": {}}}
