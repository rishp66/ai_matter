# Skill: foundry_helpers API

**In production today**, function sandboxes expose `kb`, `storage`, `vision`, `video`, `image`, `models`, `asr`, `audio`, `media`, `qwen3_asr`, `qwen3_tts`, plus the `@function` / `@tool` entry decorators (`tool` is an alias for `function`). Use explicit imports when you reference modules in code: `from foundry_helpers import kb, storage, asr, qwen3_asr, qwen3_tts`, etc.

**MCP server code** can use either `from fastmcp import FastMCP` (recommended — create your own instance) or `from foundry_helpers import mcp` (convenience — pre-created instance). Both work with `@mcp.tool()` to define tools. The `requirements.txt` must include `fastmcp` (not `mcp`).

All `foundry_helpers` modules are available in production: `asr`, `audio`, `media`, `kb`, `storage`, `vision`, `video`, `image`, `models`, `qwen3_asr`, `qwen3_tts`.

## When to Use Which Module (production)

**Documents & knowledge:**
- `kb` — RAG (search, embed, ingest). Use when the workflow needs to search over uploaded documents.
- `storage` — File I/O. Functions run in isolated VMs with no shared filesystem — use storage to persist and share files between steps.

**Images:**
- `vision` — Image *analysis* (describe, extract text, answer questions about images) and video analysis via `vision.analyze_video` / `vision.extract_frames`.
- `image` — Image *generation* and editing. Don't confuse with vision.

**Generation:**
- `video` — Video *generation* from prompts. Not for analysis.
- `image` — Image *generation* and editing.

**Speech & Audio:**
- `asr` — Speech-to-text transcription. Transcribe audio files, video files, or long recordings with chunked processing. Backed by NeMo ASR (NVIDIA Canary).
- `qwen3_asr` — Qwen3-ASR-1.7B speech recognition via vLLM. 52+ languages, word-level timestamps, batch transcription, and conversational ASR via chat completions with audio input. Prefer over `asr` for multilingual needs or when word-level timestamps are required.
- `audio` — Audio extraction and inspection. Extract WAV audio from video, get duration and metadata. Used as a building block for ASR pipelines.
- `media` — High-level multimodal pipelines combining ASR + vision. `media.analyze_video` runs speech-to-text and visual analysis in parallel; `media.summarize_video` produces a unified summary.
- `qwen3_tts` — Text-to-speech via Qwen3-TTS. 10 languages, 9 built-in speakers, voice design from natural-language description, and voice cloning from reference audio.

**Models:**
- `models` — Discover available models and defaults. Use `models.list_available("chat")` to check what's deployed before hardcoding model names.

## Common Patterns

**Video understanding (production — vision):**
```python
result = await vision.analyze_video(video_path, prompt="Summarize what happens in this video.", model=None)
# Returns model-dependent structured output; pass to the next workflow step or return as JSON.
```

**RAG retrieval:**
```python
from foundry_helpers import kb

results = await kb.search(kb_id, query, top_k=5, rerank=True)
context = "\n".join(r["content"] for r in results)
return {"context": context, "hits": len(results)}
```
Use an **agent** step downstream for natural-language answers, or call an LLM with `httpx`.

**Download → process → upload:**
```python
await storage.download_file(storage_id, "input/video.mp4", "/tmp/video.mp4")
analysis = await vision.analyze_video("/tmp/video.mp4", prompt="Describe scenes.", model=None)
await storage.upload(storage_id, "output/analysis.json", json.dumps(analysis).encode())
```

### Large payloads / big objects (videos, datasets, model bundles)

Function sandboxes are small Firecracker VMs (~256 MiB RAM) behind a Cloudflare edge that caps any single request body at **100 MiB**. Two things will break a naive implementation:

1. `storage.download_file` / `storage.upload_file` buffer the whole object → OOM at a few hundred MiB.
2. `storage.upload()` with > 100 MiB of bytes → Cloudflare 413 before the request even reaches GraphN.

**Rules of thumb:**

- **Anything the workflow produces or consumes that might exceed ~64 MiB** → use `storage.upload_object(...)` / `storage.download_object(...)`. They stream from disk and auto-switch to S3 multipart above the threshold, capping peak RAM at `part_size * concurrency` (default 64 MiB).
- **Handing a large file to a multimodal model** (`vision.analyze_video`, external VLMs, ASR on hour-long audio) → do **not** download it into the VM. Mint a presigned GET URL and pass the URL. The model/gateway resolves it directly from storage.
- **Accepting a large file as workflow input** (webhook trigger with a > 100 MiB file) → return a presigned PUT URL (or a set of per-part presigned URLs via `initiate_multipart_upload` + `get_upload_part_url`) and let the client upload directly. Your function never sees the bytes.

```python
from foundry_helpers import storage, vision

@function
async def summarize_video(storage_id: str = "", key: str = "", **kwargs) -> dict:
    # No download. Hand vLLM a short-lived URL; it streams the bytes itself.
    url = await storage.get_download_url(storage_id, key, expires_in=1800)
    summary = await vision.analyze_video(url, prompt="Summarize this video.")
    return {"summary": summary}
```

```python
from foundry_helpers import storage

@function
async def ingest_large_asset(storage_id: str = "", key: str = "", **kwargs) -> dict:
    # Large artifact produced locally (e.g. ffmpeg transcode). 32 MiB parts,
    # 2 in flight → 64 MiB ceiling, comfortable in a 256 MiB VM.
    result = await storage.upload_object(
        storage_id, key, "/tmp/transcoded.mp4",
        part_size=32 * 1024 * 1024,
        concurrency=2,
    )
    return {"uploaded": result["key"], "size": result["size"], "etag": result["etag"]}
```

**Debugging:** `foundry_helpers.storage.upload_object` logs `initiate → part N uploaded → complete` traces; if you see a hanging `complete` call, one of the part PUTs almost certainly failed without an abort — always wrap MPU logic in `try/except` with `abort_multipart_upload` on error if you're driving it by hand (the `upload_object` helper does this for you).

**Transcribe audio (production — asr):**
```python
from foundry_helpers import asr

result = await asr.transcribe("/tmp/recording.wav", language="en")
print(result["text"])  # full transcript
```

**Video analysis with ASR + vision in parallel (production pattern from Video Analysis template):**
```python
from foundry_helpers import vision, storage, asr
import asyncio, tempfile, os, json

@function
async def analyze_video(video: str = "", prompt: str = "", **kwargs) -> str:
    parts = video.split("/", 1)
    storage_id, file_path = parts[0], parts[1]

    with tempfile.TemporaryDirectory() as tmp:
        local_path = os.path.join(tmp, os.path.basename(file_path))
        await storage.download_file(storage_id, file_path, local_path)

        async def do_visual():
            frames = vision.extract_frames(local_path, fps=0.5, max_frames=4)
            if not frames:
                return "(no frames extracted)"
            return await vision.analyze(frames, prompt or "Describe this video.", model=None)

        async def do_asr():
            try:
                result = await asr.transcribe_video(local_path)
                return result.get("text", "")
            except Exception as e:
                return f"(ASR unavailable: {e})"

        visual_result, transcript = await asyncio.gather(do_visual(), do_asr())
        return json.dumps({"visual_analysis": visual_result, "transcript": transcript})
```

**Long audio transcription with chunked processing:**
```python
from foundry_helpers import asr

result = await asr.transcribe_chunked("/tmp/long_recording.wav", chunk_duration=30.0, overlap=2.0, language="en")
print(result["text"])  # merged transcript from all chunks
```

**Multilingual transcription with word-level timestamps (qwen3_asr):**
```python
from foundry_helpers import qwen3_asr

result = await qwen3_asr.transcribe("/tmp/audio.wav", language="ja", return_timestamps=True)
print(result["text"])
for seg in result.get("segments", []):
    for word in seg.get("words", []):
        print(f"  [{word['start']:.1f}s] {word['word']}")
```

**Conversational ASR with custom instructions (qwen3_asr):**
```python
from foundry_helpers import qwen3_asr

text = await qwen3_asr.transcribe_chat("/tmp/meeting.wav", language="en",
    prompt="Transcribe this meeting accurately. Include speaker labels if discernible.")
```

**Batch transcription (qwen3_asr):**
```python
from foundry_helpers import qwen3_asr

results = await qwen3_asr.transcribe_batch(
    ["/tmp/clip1.wav", "/tmp/clip2.wav", "/tmp/clip3.wav"],
    languages=["en", "ja", None],  # None = auto-detect
)
for r in results:
    print(r["text"])
```

**Text-to-speech with built-in speaker (qwen3_tts):**
```python
from foundry_helpers import qwen3_tts
import base64

result = await qwen3_tts.generate_speech(
    text="Hello, welcome to GraphN!",
    language="English",
    speaker="Aiden",  # American male voice
    instruct="Speak warmly and clearly",
)
audio_bytes = base64.b64decode(result["audio"])
with open("/tmp/output.wav", "wb") as f:
    f.write(audio_bytes)
```

**Voice cloning (qwen3_tts):**
```python
from foundry_helpers import qwen3_tts

result = await qwen3_tts.generate_voice_clone(
    text="This is synthesized with a cloned voice.",
    language="English",
    ref_audio="/tmp/reference_clip.wav",  # ~3s reference
    ref_text="This is the original speaker.",
)
```

## Important Notes

- Functions run in **isolated Firecracker VMs** with their own filesystem. Files created in one step are NOT available in another — use `storage` to pass files between steps.
- `httpx` is pre-installed. Use it for external API calls. Always set timeouts.
- `ffmpeg` and `ffprobe` are available in the VM for audio/video processing.
- `vision.extract_frames` is a **synchronous** subprocess call. Wrap in `asyncio.to_thread` if mixing with other async work.

---

## API Reference

### Function decorator (`function` / `tool`)
```python
# @function is auto-imported in main.py — no import statement needed
@function
async def my_function(text: str = "", **kwargs) -> str:
    """Process text input."""
    return f"Result: {text}"

# Equivalent: @tool (alias for @function)
```
The `@function` / `@tool` decorator marks the entry point. Without it, the platform falls back to the first async function.

### MCP (MCP server code)

**Option A — recommended (explicit FastMCP instance):**
```python
from fastmcp import FastMCP
mcp = FastMCP("MyTools")

@mcp.tool()
async def semantic_search(query: str, top_k: int = 5) -> list:
    """Example tool — implement with kb, storage, etc."""
    from foundry_helpers import kb
    return await kb.search("KB_ID", query, top_k=top_k)
```

**Option B — convenience (pre-created instance):**
```python
from foundry_helpers import mcp

@mcp.tool()
async def semantic_search(query: str, top_k: int = 5) -> list:
    """Example tool — implement with kb, storage, etc."""
    from foundry_helpers import kb
    return await kb.search("KB_ID", query, top_k=top_k)
```

**CRITICAL:** `requirements.txt` must include `fastmcp` (not `mcp` or `mcp[server]`).

### Knowledge Base (RAG)
```python
from foundry_helpers import kb

# Core operations
results = await kb.search(kb_id, query, top_k=5, rerank=True, reranker_model=None)
kbs = await kb.list_kbs()
all_kbs = await kb.list_kbs_all(page_size=50)
new_kb = await kb.create(name, description=None)
info = await kb.get(kb_id)
await kb.upload_document(kb_id, content, filename, metadata=None)
docs = await kb.list_documents(kb_id)
all_docs = await kb.list_documents_all(kb_id, page_size=50)
await kb.ingest_from_storage(kb_id, storage_id, file_path, metadata=None)
await kb.delete(kb_id)  # always permanent; all vectors + documents are purged

# Embeddings
embeddings = await kb.embed(text, normalize=True)
batch = await kb.embed_batch(texts, normalize=True)

# Batch operations — all return {"total": N, "succeeded": N, "failed": N, "results": [...]}
result = await kb.batch_get(ids)
result = await kb.batch_delete(ids)  # always permanent
result = await kb.batch_update(items)  # items: [{"id": ..., "name": ..., "description": ...}]
result = await kb.batch_get_documents(kb_id, ids)
result = await kb.batch_delete_documents(kb_id, ids)
```

### Storage (S3-compatible)
```python
from foundry_helpers import storage

# --- Small objects (< ~64 MiB): in-memory helpers ---
await storage.upload(storage_id, key, data)               # bytes/str
await storage.upload_file(storage_id, key, local_path)    # buffers the whole file
data = await storage.download(storage_id, key)            # returns bytes
await storage.download_file(storage_id, key, local_path)  # buffers the whole file

# --- Large objects (> ~64 MiB, videos, datasets, model bundles) ---
# auto-switches between single-PUT and S3 multipart; peak memory = part_size*concurrency
result = await storage.upload_object(
    storage_id, key, source,                    # bytes OR local file path (str)
    content_type="application/octet-stream",
    part_size=None,                             # default 32 MiB, max 64 MiB
    concurrency=2,                              # parallel part PUTs
    on_progress=lambda done, total: None,       # optional callback (sync or async)
)
# result = {"key", "storage_id", "size", "etag"}
result = await storage.download_object(
    storage_id, key, dest,                      # local path
    part_size=None, concurrency=2,
    on_progress=None,
)
# result = {"key", "storage_id", "size"}

# --- Presigned URLs (give vLLM / external tools / multimodal models direct access) ---
# NOTE: presigned GETs let vLLM fetch the object directly from storage,
#       sidestepping Cloudflare's 100 MiB request-body cap for large media.
get_url  = await storage.get_download_url(storage_id, key, expires_in=3600)
put_url  = await storage.get_upload_url(
    storage_id, key, expires_in=3600,
    max_size=None, content_type=None,
)
# Back-compat alias (same as get_download_url):
url = await storage.presigned_url(storage_id, key, expires_in=3600)

# --- Low-level multipart (only if you need custom chunking / resume logic) ---
init = await storage.initiate_multipart_upload(storage_id, key, content_type="application/octet-stream")
# init = {"key", "upload_id", "max_part_size"}
part_url = await storage.get_upload_part_url(storage_id, key, init["upload_id"], part_number, expires_in=3600)
await storage.complete_multipart_upload(storage_id, key, init["upload_id"], parts=[{"part_number": 1, "etag": "..."}])
await storage.abort_multipart_upload(storage_id, key, init["upload_id"])  # cleanup on error

# --- Misc ---
files = await storage.list(storage_id, prefix="", max_keys=1000)
objects = await storage.list_objects(storage_id, prefix="", max_keys=10000)  # auto-paginates, returns [{key, size, last_modified, etag}]
await storage.delete(storage_id, key)
await storage.copy(storage_id, source_key, dest_key)
exists = await storage.exists(storage_id, key)
stores = await storage.list_stores()
new_store = await storage.create(name, description="")
```

**When to pick which upload/download:**

| Size | Helper | Why |
|------|--------|-----|
| < 32 MiB | `upload` / `download` | Simplest, no streaming overhead |
| 32–64 MiB | `upload_object` / `download_object` | Streams from disk, stays flat in RAM |
| 64 MiB – 5 GiB | `upload_object` / `download_object` | Auto-multipart, parallel parts, bypasses the 100 MiB edge cap |
| Feeding vLLM / vision / ASR a large media file | `get_download_url` + pass the URL to the model | Model fetches directly from storage; your function returns instantly |

**Handing large media to multimodal models:** never `download()` a 2 GB video just to pass its bytes to `vision.analyze_video`. Mint a presigned GET URL and pass the URL — the model/gateway resolves it directly. Example:

```python
video_url = await storage.get_download_url(store_id, key, expires_in=1800)
result = await vision.analyze_video(video_url, prompt="describe motion")
```

**Accepting large user uploads from a workflow trigger:** mint a presigned PUT URL, return it, and let the client `curl -T` directly to storage. Your function never receives the bytes — Cloudflare's 100 MiB body cap does not apply. Pair with `initiate_multipart_upload` + `get_upload_part_url` for > 100 MiB uploads (one presigned URL per part, client uploads parts in parallel, then calls back to complete).

### Vision (Image + Video Analysis)
```python
from foundry_helpers import vision

# Image analysis
result = await vision.analyze(image, prompt, model=None)
desc = await vision.describe(image_url)
text = await vision.extract_text(image_path)

# Video analysis (native video_url input to Qwen3-VL for temporal/motion-aware analysis)
result = await vision.analyze_video(video_source, prompt, model=None, temperature=0.3, max_tokens=None)
# video_source: file path, http(s):// URL, data: URI, or raw bytes

# Frame extraction (ffmpeg — returns list of base64 JPEG strings)
frames_b64 = vision.extract_frames(video_path, fps=1.0, max_frames=16)
```

### Video Generation

**Veo 3.1 (Google) — short and long video, with synchronized audio.** Use this
for any new video work; it produces 8s clips at 720p/1080p in 16:9 or 9:16.
For voice in the output the prompt MUST contain dialogue verbatim, e.g.
`'she walks in and says \"hello\"'`; otherwise only ambient audio is generated.

```python
from foundry_helpers import veo, nanobanana, media_tools

# 1. Single 8s clip from a text prompt
clip = await veo.generate(
    prompt='a corgi sprints through a sunlit meadow, says \"woohoo!\"',
    aspect_ratio="16:9", resolution="720p", duration=8,
    storage_id="default", generate_audio=True,
)

# 2. Image-to-video: condition the first frame on a NanoBanana avatar
avatar = await nanobanana.generate(
    "a smiling 30-year-old woman in a red coat, photoreal",
    style="realistic", aspect_ratio="16:9", storage_id="default",
)
clip = await veo.generate_from_image(
    'she waves and says \"good morning, team\"',
    avatar["storage_path"],            # path or storage path of the keyframe
    aspect_ratio="16:9", duration=8, resolution="720p", storage_id="default",
)

# 3. Long video with consistent character (≤ ~148s, 8s per segment)
result = await veo.generate_consistent_long(
    reference_image="default/people/anchor.png",   # or a new avatar from nanobanana.generate
    scenes=[
        "she walks into the office, smiles, sets down a coffee",
        "she sits at her desk, opens a laptop, frowns at the screen",
        "she stands up and says \"alright team, war room — five minutes\"",
    ],
    aspect_ratio="16:9", resolution="720p", style="realistic",
    storage_id="default", generate_audio=True,
)
# result -> {status, video_id, storage_path, segments, segment_paths, keyframe_paths, ...}

# 4. Lower-level chaining (only if you need full control over each extend)
seg1 = await veo.generate_from_image(scenes[0], avatar["storage_path"], ...)
long_result = await veo.generate_long(
    prompt=scenes[0],
    image_source=avatar["storage_path"],
    extension_prompts=scenes[1:],          # one prompt per extension; required for variety
    extensions=len(scenes) - 1,
    concat_segments=True,                  # ffmpeg-stitch all segments into one mp4
    storage_id="default",
)

# 5. Stitch arbitrary clips you already produced
final = await media_tools.concat(
    ["default/clips/seg_0.mp4", "default/clips/seg_1.mp4", "default/clips/seg_2.mp4"],
    storage_id="default",
)
```

**Legacy Wan2.2 helper (kept for existing factories):**
```python
from foundry_helpers import video
result = await video.generate(prompt, size="1280*720", frame_num=81, duration=4.0)
enhanced = await video.enhance_prompt(prompt)  # returns enhanced prompt string
```

### Image Generation
```python
from foundry_helpers import image

result = await image.generate(prompt, width=1664, height=928, num_inference_steps=50)
result = await image.edit(image_url, prompt, mask_image_url=None)
```

### Models
```python
from foundry_helpers import models

available = models.list_available(type_filter="chat")  # or "vision", etc.
default = models.get_default("chat")
models.configure(alias, endpoint, model_name)  # register custom model
config = models.get_config(model=None)  # returns {"endpoint": str, "model": str}
```

### ASR (Speech-to-Text)
```python
from foundry_helpers import asr

# Transcribe audio (WAV file path or raw bytes)
result = await asr.transcribe(audio_source, language="en")
# result: {"text": "full transcript"}

# Transcribe audio extracted from a video file (extracts WAV automatically)
result = await asr.transcribe_video(video_path, language="en")

# Chunked transcription for long recordings (splits, transcribes, merges)
result = await asr.transcribe_chunked(audio_path, language="en", chunk_duration=30.0, overlap=2.0)
```

### Audio Helpers
```python
from foundry_helpers import audio

# Extract audio from video as 16 kHz mono WAV (required format for ASR)
wav_path = audio.extract(video_path, output_path=None, sample_rate=16000, mono=True)

# Get file duration in seconds
duration = audio.get_duration(file_path)

# Get media metadata (duration, codecs, resolution, fps)
metadata = audio.get_metadata(file_path)
```

### Media Pipeline (ASR + Vision)
```python
from foundry_helpers import media

# Full video understanding: ASR transcription + VLM frame analysis in parallel
result = await media.analyze_video(video_path, prompt=None, vision_model=None, language="en", max_frames=16, fps=1.0)
# result: {"transcript": {...}, "visual_analysis": "...", "duration": float, "metadata": {...}}

# One-shot video summary combining both modalities via an LLM
summary = await media.summarize_video(video_path, language="en", model=None)
```

### Qwen3 ASR (Multilingual Speech-to-Text)
```python
from foundry_helpers import qwen3_asr

# Transcribe audio (WAV/MP3 path or raw bytes). 52+ languages.
result = await qwen3_asr.transcribe(audio_source, language=None, return_timestamps=False, max_tokens=4096, model=None)
# result: {"text": "..."} — with return_timestamps=True also includes "segments" with word-level timing

# Conversational ASR via chat completions (custom prompt guides transcription)
text = await qwen3_asr.transcribe_chat(audio_source, language=None, prompt=None, model=None, max_tokens=4096)
# Returns raw transcription string

# Batch transcription (concurrent)
results = await qwen3_asr.transcribe_batch(audio_sources, languages=None, return_timestamps=False, model=None)
# Returns list of transcription dicts in same order as input

# Transcribe video (extracts audio first, then transcribes)
result = await qwen3_asr.transcribe_video(video_path, language=None, return_timestamps=False, model=None)

# Chunked transcription for long audio (splits, transcribes, merges)
result = await qwen3_asr.transcribe_chunked(audio_path, language=None, chunk_duration=30.0, overlap=2.0, model=None)
```

### Qwen3 TTS (Text-to-Speech)
```python
from foundry_helpers import qwen3_tts

# Generate speech with a built-in speaker (9 voices available)
# Languages: Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian
# Speakers: Vivian, Serena, Uncle_Fu, Dylan, Eric, Ryan, Aiden, Ono_Anna, Sohee
result = await qwen3_tts.generate_speech(text, language="Auto", speaker="Ono_Anna", instruct=None)
# result: {"audio": "<base64 WAV>", "sample_rate": int, "format": "wav", "encoding": "base64"}
# Decode: audio_bytes = base64.b64decode(result["audio"])

# Voice design from natural-language description (no reference audio needed)
result = await qwen3_tts.generate_voice_design(text, language="Auto", instruct="Young female voice with a warm, gentle tone")

# Voice cloning from reference audio (~3s clip recommended)
result = await qwen3_tts.generate_voice_clone(text, language="Auto", ref_audio=ref_audio_path, ref_text="transcript of ref", x_vector_only_mode=False)

# Batch: pass lists for text, language, speaker/instruct to generate multiple utterances
result = await qwen3_tts.generate_speech(["Hello", "Goodbye"], language=["English", "English"], speaker=["Aiden", "Ryan"])
# result: {"audio": ["<base64>", "<base64>"], ...}

# Utilities
speakers = qwen3_tts.get_supported_speakers()   # {name: {description, native_language}}
languages = qwen3_tts.get_supported_languages()  # ["Chinese", "English", ...]
```

