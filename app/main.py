import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import OUTPUTS_DIR, SERVICE_NAME
from app.schemas import HealthResponse, SynthesisMode, SynthesizeRequest, TextRequest
from app.services import nlp_adapter, tts_adapter
from app.services.errors import IntegrationContractError, IntegrationUnavailableError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Madrigal TTS API", version="0.2.0", lifespan=lifespan)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME)


def _integration_http_error(exc: Exception) -> HTTPException:
    logger.warning("Integration error: %s", exc)
    if isinstance(exc, IntegrationUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail="Нарушен контракт интеграционного модуля.")


@app.post("/api/analyze")
async def analyze(request: TextRequest) -> dict:
    try:
        return await run_in_threadpool(nlp_adapter.analyze_text, request.text)
    except (IntegrationUnavailableError, IntegrationContractError) as exc:
        raise _integration_http_error(exc) from exc
    except Exception as exc:
        logger.exception("NLP analysis failed")
        raise HTTPException(status_code=503, detail="Не удалось выполнить анализ текста.") from exc


@app.post("/api/synthesize")
async def synthesize(request: SynthesizeRequest) -> dict:
    text_used = request.text
    applied = None
    if request.mode == SynthesisMode.auto:
        try:
            applied = await run_in_threadpool(nlp_adapter.auto_resolve_pronunciations, request.text)
            text_used = applied["text_used"]
        except (IntegrationUnavailableError, IntegrationContractError) as exc:
            raise _integration_http_error(exc) from exc
        except Exception as exc:
            logger.exception("AUTO NLP preparation failed")
            raise HTTPException(status_code=503, detail="Не удалось автоматически подготовить текст для синтеза.") from exc

    filename = f"madrigal-{uuid4().hex}.wav"
    output_path = OUTPUTS_DIR / filename
    try:
        result = await run_in_threadpool(tts_adapter.synthesize, text_used, output_path, request.voice)
    except (IntegrationUnavailableError, IntegrationContractError) as exc:
        raise _integration_http_error(exc) from exc
    except Exception as exc:
        logger.exception("Speech synthesis failed")
        raise HTTPException(status_code=503, detail="Не удалось синтезировать аудио.") from exc

    response = {
        "audio_url": f"/outputs/{filename}",
        "mode": request.mode.value,
        "duration_seconds": result["duration_seconds"],
        "generation_seconds": result["generation_seconds"],
        "text_used": text_used,
    }
    if applied is not None:
        response["auto_decisions"] = applied.get("auto_decisions", [])
        response["warnings"] = applied.get("warnings", [])
    return response


@app.get("/outputs/{filename}")
def output_file(filename: str) -> FileResponse:
    path = Path(filename)
    if path.name != filename or filename in {"", ".", ".."}:
        raise HTTPException(status_code=404, detail="Аудиофайл не найден.")
    resolved_output = (OUTPUTS_DIR / path.name).resolve()
    if resolved_output.parent != OUTPUTS_DIR.resolve() or not resolved_output.is_file():
        raise HTTPException(status_code=404, detail="Аудиофайл не найден.")
    return FileResponse(resolved_output, media_type="audio/wav", filename=path.name)
