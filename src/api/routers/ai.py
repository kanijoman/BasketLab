"""AI analysis router — streaming SSE text generation for team/player scouting.

Exposes ``POST /api/v1/ai/analyze/stream`` which emits Server-Sent Events (SSE)
as the AI generates the report.  API keys are read from environment variables:

    GEMINI_API_KEY   — Google Gemini
    OPENAI_API_KEY   — OpenAI
    GROQ_API_KEY     — Groq (default)

The endpoint:
1. Builds a statistics context using the desktop's ``ContextBuilder``.
2. Calls the selected provider's streaming API.
3. Streams each text chunk as an SSE ``data:`` event.
4. Emits ``{"done": true}`` on completion or ``{"error": "..."}`` on failure.

Additional endpoints:
  GET  /api/v1/ai/individual-scouting/docx  — full team DOCX scouting report
  POST /api/v1/ai/export-pdf                — convert streamed HTML to PDF
"""

from __future__ import annotations

import json
import os
import asyncio
from typing import AsyncIterator, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from sse_starlette.sse import EventSourceResponse

from src.api.deps import get_db
from src.ai.config import AnalysisConfig
from src.ai.context_builder import ContextBuilder

router = APIRouter()

# ---------------------------------------------------------------------------
# Request model (sent as query params — SSE uses GET for EventSource compat.)
# ---------------------------------------------------------------------------

# Query-param based so the browser's native EventSource can send them.
# The client uses the helper ``getAIAnalysisStreamUrl`` from client.ts which
# builds the ?-params URL already.

# ---------------------------------------------------------------------------
# Streaming helpers per provider
# ---------------------------------------------------------------------------


async def _stream_gemini(context: str, analysis_type: str) -> AsyncIterator[str]:
    """Yield text chunks from Google Gemini streaming API."""
    try:
        import google.generativeai as genai
        from src.ai.prompts import get_system_prompt

        genai.configure(api_key=AnalysisConfig.GEMINI_API_KEY)
        model_name = AnalysisConfig.GEMINI_MODELS.get("flash", "models/gemini-2.0-flash-exp")
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
        model = genai.GenerativeModel(model_name)

        system_prompt = get_system_prompt("gemini", analysis_type)
        prompt = f"{system_prompt}\n\n{context}"

        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": AnalysisConfig.TEMPERATURE,
                "max_output_tokens": AnalysisConfig.MAX_TOKENS,
            },
            stream=True,
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        yield f"\n\n⚠️ Error al generar análisis: {exc}"


async def _stream_groq_openai(context: str, analysis_type: str, provider: str) -> AsyncIterator[str]:
    """Yield text chunks from Groq or OpenAI streaming API."""
    try:
        import openai as _openai
        from src.ai.prompts import get_system_prompt

        if provider == "groq":
            client = _openai.OpenAI(
                api_key=AnalysisConfig.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
            )
            model_name = AnalysisConfig.GROQ_MODELS.get("fast", "llama-3.3-70b-versatile")
        else:
            client = _openai.OpenAI(api_key=AnalysisConfig.OPENAI_API_KEY)
            model_name = AnalysisConfig.OPENAI_MODELS.get("mini", "gpt-4o-mini")

        system_content = get_system_prompt("openai", analysis_type)

        stream = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": context},
            ],
            temperature=AnalysisConfig.TEMPERATURE,
            max_tokens=AnalysisConfig.MAX_TOKENS,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except Exception as exc:
        yield f"\n\n⚠️ Error al generar análisis: {exc}"


# ---------------------------------------------------------------------------
# SSE event generator
# ---------------------------------------------------------------------------


async def _sse_generator(
    collection: str,
    team: str,
    analysis_type: str,
    provider: str,
    include_recommendations: bool,
) -> AsyncIterator[dict[str, Any]]:
    """Build context then stream AI chunks as SSE events."""
    # Validate setup
    AnalysisConfig.load_api_keys()
    if not AnalysisConfig.has_api_key(provider):
        yield {"data": json.dumps({"error": f"Sin API key configurada para {provider}. Configura la variable de entorno correspondiente."})}
        return

    # Build context from DB stats
    try:
        from src.api.deps import _create_handler
        from src.services.team_stats_service import TeamStatsService
        db = _create_handler()
        svc_stats = db.get_team_stats(collection) or []
        team_row = next((t for t in svc_stats if t.get("team_name") == team), {})
        league_stats = db.get_league_stats(collection) or {}

        # Fetch consistency (CV) data; returns {} for FBCYL collections
        try:
            team_svc = TeamStatsService(db)
            consistency_raw = team_svc.get_consistency(collection) or {}
            consistency = consistency_raw.get("own", {}).get(team, {})
        except Exception:
            consistency = {}

        stats_payload = {
            "team_stats": team_row,
            "league_stats": league_stats,
            "consistency": consistency,
        }
        cb = ContextBuilder()
        context = cb.build_team_context(team, stats_payload, include_recommendations, analysis_type)
    except Exception as exc:
        yield {"data": json.dumps({"error": f"Error construyendo contexto: {exc}"})}
        return

    # Stream from provider
    if provider == "gemini":
        streamer = _stream_gemini(context, analysis_type)
    else:
        streamer = _stream_groq_openai(context, analysis_type, provider)

    async for text_chunk in streamer:
        yield {"data": json.dumps({"chunk": text_chunk})}
        # Brief yield to allow event loop to flush
        await asyncio.sleep(0)

    yield {"data": json.dumps({"done": True})}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/analyze/stream", summary="Stream AI team analysis via SSE")
async def stream_team_analysis(
    collection: str,
    team: str,
    analysis_type: str = "own",
    provider: str = "groq",
    include_recommendations: bool = True,
):
    """Stream an AI-generated team analysis report as Server-Sent Events.

    Args:
        collection: MongoDB collection name.
        team: Exact team name as stored in the DB.
        analysis_type: ``own`` (self-analysis), ``scouting`` (rival scouting),
            or ``individual`` (full roster scouting — see DOCX endpoint).
        provider: ``gemini``, ``openai``, or ``groq``.
        include_recommendations: Whether to ask the LLM for tactical recommendations.

    Returns:
        SSE stream.  Each event data is a JSON object with either:
        - ``{"chunk": "..."}`` — partial text
        - ``{"done": true}`` — generation finished
        - ``{"error": "..."}`` — error details
    """
    return EventSourceResponse(
        _sse_generator(
            collection=collection,
            team=team,
            analysis_type=analysis_type,
            provider=provider,
            include_recommendations=include_recommendations,
        ),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# DOCX export endpoint — Individual scouting
# ---------------------------------------------------------------------------

@router.get(
    "/individual-scouting/docx",
    summary="Download full team individual scouting report as DOCX",
)
def download_individual_scouting_docx(
    collection: str,
    team: str,
    include_ai_notes: bool = True,
    db=Depends(get_db),
):
    """Build a DOCX scouting report with one page per player and return it for download.

    Args:
        collection: MongoDB collection name.
        team: Exact team name as stored in the DB.
        include_ai_notes: Whether to call the AI for brief per-player notes.

    Returns:
        Binary DOCX file as an attachment.
    """
    try:
        from src.services.individual_scouting_service import IndividualScoutingDocxBuilder

        builder = IndividualScoutingDocxBuilder(
            collection=collection,
            team_name=team,
            db=db,
            include_ai_notes=include_ai_notes,
        )
        docx_bytes = builder.build()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generando DOCX: {exc}") from exc

    if not docx_bytes:
        raise HTTPException(status_code=404, detail="No se encontraron jugadores para el equipo indicado.")

    safe_team = "".join(c if c.isalnum() else "_" for c in team)
    filename = f"Scouting_{safe_team}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# PDF export endpoint — Own / Rival team analysis
# ---------------------------------------------------------------------------

class _ExportPDFRequest(BaseModel):
    html: str
    team: str = ""
    analysis_type: str = "own"


@router.post("/export-pdf", summary="Convert AI analysis HTML to PDF")
def export_analysis_pdf(req: _ExportPDFRequest):
    """Accept the streamed HTML from the AI analysis page and return a PDF.

    Args:
        req.html: Full HTML string generated by the AI streamer.
        req.team: Team name used for the title header.
        req.analysis_type: ``own`` or ``scouting`` (informational only).

    Returns:
        Binary PDF file as an attachment.
    """
    try:
        from src.ui.pdf_generator import PDFGenerator

        pdf_bytes = PDFGenerator.generate_bytes_from_html(
            html_content=req.html,
            team_name=req.team,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {exc}") from exc

    safe_team = "".join(c if c.isalnum() else "_" for c in req.team)
    label = "Scouting" if req.analysis_type == "scouting" else "Analisis"
    filename = f"{label}_{safe_team}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
