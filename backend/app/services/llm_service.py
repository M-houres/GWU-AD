from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any, Mapping

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.exceptions import BizError
from app.models import SystemConfig, TaskType

settings = get_settings()
logger = logging.getLogger("app.services.llm_service")

LOCAL_MOCK_PROVIDER = "local_mock"
_RETRYABLE_LLM_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}

LLM_PROVIDER_PRESETS = {
    "openai": {
        "label": "OpenAI",
        "api_style": "openai",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "api_style": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-3-5-sonnet-latest",
    },
    "gemini": {
        "label": "Google Gemini",
        "api_style": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.0-flash",
    },
    "deepseek": {
        "label": "DeepSeek",
        "api_style": "openai",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "qwen": {
        "label": "Qwen / DashScope",
        "api_style": "openai",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "doubao": {
        "label": "Doubao / Ark",
        "api_style": "openai",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "",
    },
    "moonshot": {
        "label": "Moonshot / Kimi",
        "api_style": "openai",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
    },
    "zhipu": {
        "label": "Zhipu GLM",
        "api_style": "openai",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
    },
    "custom_openai": {
        "label": "Custom OpenAI Compatible",
        "api_style": "openai",
        "base_url": "",
        "model": "",
    },
    LOCAL_MOCK_PROVIDER: {
        "label": "Local Mock LLM",
        "api_style": LOCAL_MOCK_PROVIDER,
        "base_url": "",
        "model": "local-mock-v1",
    },
}

SUPPORTED_LLM_PROVIDERS = set(LLM_PROVIDER_PRESETS)


def normalize_llm_provider(provider: str | None) -> str:
    raw = str(provider or "").strip().lower()
    if raw in {"openai_compatible", "custom", "compatible"}:
        return "custom_openai"
    if raw in {"local_mock", "mock", "local", "offline"}:
        return LOCAL_MOCK_PROVIDER
    if raw in SUPPORTED_LLM_PROVIDERS:
        return raw
    return "openai"


def resolve_llm_config(value: dict | None = None) -> dict:
    raw = value if isinstance(value, dict) else {}
    provider = normalize_llm_provider(raw.get("provider"))
    preset = LLM_PROVIDER_PRESETS[provider]
    base_url = str(raw.get("base_url") or preset["base_url"] or settings.llm_api_base_url).rstrip("/")
    api_key = str(raw.get("api_key") or settings.llm_api_key)
    if provider == LOCAL_MOCK_PROVIDER:
        base_url = ""
    return {
        "enabled": bool(raw.get("enabled", settings.llm_enabled_default)),
        "provider": provider,
        "api_style": preset["api_style"],
        "base_url": base_url,
        "api_key": api_key,
        "model": str(raw.get("model") or preset["model"] or settings.llm_model),
        "timeout_seconds": int(raw.get("timeout_seconds", settings.llm_timeout_seconds)),
        "retry_attempts": max(int(raw.get("retry_attempts", settings.llm_retry_attempts) or settings.llm_retry_attempts), 1),
        "retry_backoff_seconds": max(
            float(raw.get("retry_backoff_seconds", settings.llm_retry_backoff_base_seconds) or settings.llm_retry_backoff_base_seconds),
            0.1,
        ),
        "max_output_tokens": int(raw.get("max_output_tokens", 2048) or 2048),
        "temperature": float(raw.get("temperature", 0.3) or 0.3),
    }


def load_llm_config(db: Session) -> dict:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == "llm")
        .first()
    )
    value = row.config_value if row and isinstance(row.config_value, dict) else {}
    return resolve_llm_config(value)


def _build_prompt(task_type: TaskType, text: str) -> str:
    if task_type == TaskType.DEDUP:
        return (
            "Rewrite the academic text to reduce duplication risk without changing meaning. "
            "Return only the rewritten text without explanation.\n\n"
            f"Source:\n{text}"
        )
    if task_type == TaskType.REWRITE:
        return (
            "Rewrite the academic text to sound more natural and compliant while preserving arguments and data. "
            "Return only the rewritten text without explanation.\n\n"
            f"Source:\n{text}"
        )
    if task_type == TaskType.AIGC_DETECT:
        return (
            "You are an academic text risk assessor. Estimate the AI-generated likelihood for the text.\n"
            "Return strict JSON only with fields: ai_score (0-1 float), label (high|medium|low), reason (short).\n\n"
            f"Text:\n{text}"
        )
    return text


def _is_local_mock_config(cfg: Mapping[str, Any]) -> bool:
    provider = str(cfg.get("provider", "")).strip().lower()
    api_style = str(cfg.get("api_style", "")).strip().lower()
    return provider == LOCAL_MOCK_PROVIDER or api_style == LOCAL_MOCK_PROVIDER


def _build_http_client(cfg: Mapping[str, Any]) -> httpx.Client:
    timeout_seconds = max(float(cfg.get("timeout_seconds") or settings.llm_timeout_seconds or 25), 1.0)
    return httpx.Client(timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 8.0)))


def _should_retry_llm_exception(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError, httpx.PoolTimeout)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        return bool(response is not None and response.status_code in _RETRYABLE_LLM_STATUS_CODES)
    return False


def _llm_backoff_seconds(cfg: Mapping[str, Any], attempt: int) -> float:
    base = max(float(cfg.get("retry_backoff_seconds") or settings.llm_retry_backoff_base_seconds or 0.8), 0.1)
    return min(base * (2 ** max(attempt - 1, 0)), 8.0)


def _raise_llm_error(exc: Exception) -> None:
    if isinstance(exc, httpx.TimeoutException):
        raise BizError(code=4603, message="LLM 服务超时，请稍后重试") from exc
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code if exc.response is not None else 0
        if status_code in {400, 401, 403, 404}:
            raise BizError(code=4604, message="LLM 配置或鉴权失败，请联系管理员") from exc
        raise BizError(code=4604, message="LLM 服务暂时不可用，请稍后重试") from exc
    if isinstance(exc, (httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError, httpx.PoolTimeout)):
        raise BizError(code=4604, message="LLM 服务连接失败，请稍后重试") from exc
    raise BizError(code=4605, message="LLM 调用失败，请稍后重试") from exc


def generate_with_llm(db: Session, *, task_type: TaskType, text: str) -> str:
    cfg = load_llm_config(db)
    if not cfg["enabled"]:
        raise BizError(code=4601, message="LLM is disabled")

    try:
        if _is_local_mock_config(cfg):
            content = _call_local_mock(task_type=task_type, text=text)
        else:
            if not cfg["api_key"]:
                raise BizError(code=4602, message="LLM API key is missing")
            attempts = max(int(cfg.get("retry_attempts") or settings.llm_retry_attempts or 1), 1)
            last_exc: Exception | None = None
            with _build_http_client(cfg) as client:
                for attempt in range(1, attempts + 1):
                    try:
                        if cfg["api_style"] == "anthropic":
                            content = _call_anthropic(client, cfg=cfg, task_type=task_type, text=text)
                        elif cfg["api_style"] == "gemini":
                            content = _call_gemini(client, cfg=cfg, task_type=task_type, text=text)
                        else:
                            content = _call_openai_compatible(client, cfg=cfg, task_type=task_type, text=text)
                        last_exc = None
                        break
                    except Exception as exc:
                        last_exc = exc
                        retryable = _should_retry_llm_exception(exc)
                        logger.warning(
                            "llm_call_attempt_failed",
                            extra={
                                "provider": cfg.get("provider"),
                                "model": cfg.get("model"),
                                "task_type": task_type.value,
                                "attempt": attempt,
                                "retryable": retryable,
                                "error_type": exc.__class__.__name__,
                            },
                        )
                        if not retryable or attempt >= attempts:
                            break
                        time.sleep(_llm_backoff_seconds(cfg, attempt))
            if last_exc is not None:
                _raise_llm_error(last_exc)
    except BizError:
        raise
    except Exception as exc:
        _raise_llm_error(exc)

    if not isinstance(content, str) or not content.strip():
        raise BizError(code=4606, message="LLM returned empty content")
    return content.strip()


def _call_openai_compatible(client: httpx.Client, *, cfg: Mapping[str, Any], task_type: TaskType, text: str) -> str:
    url = f"{cfg['base_url']}/chat/completions"
    payload: dict[str, Any] = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": "You are a reliable academic writing assistant."},
            {"role": "user", "content": _build_prompt(task_type, text)},
        ],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_output_tokens"],
    }
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    resp = client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    body = resp.json()
    content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    return content if isinstance(content, str) else ""


def _call_anthropic(client: httpx.Client, *, cfg: Mapping[str, Any], task_type: TaskType, text: str) -> str:
    url = f"{cfg['base_url']}/messages"
    payload = {
        "model": cfg["model"],
        "max_tokens": cfg["max_output_tokens"],
        "temperature": cfg["temperature"],
        "system": "You are a reliable academic writing assistant.",
        "messages": [{"role": "user", "content": _build_prompt(task_type, text)}],
    }
    headers = {
        "x-api-key": cfg["api_key"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    resp = client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    body = resp.json()
    content_blocks = body.get("content", [])
    texts = []
    for item in content_blocks:
        if isinstance(item, dict) and item.get("type") == "text":
            texts.append(str(item.get("text", "")))
    return "\n".join(texts).strip()


def _call_gemini(client: httpx.Client, *, cfg: Mapping[str, Any], task_type: TaskType, text: str) -> str:
    url = f"{cfg['base_url']}/models/{cfg['model']}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": "You are a reliable academic writing assistant."}]},
        "contents": [{"role": "user", "parts": [{"text": _build_prompt(task_type, text)}]}],
        "generationConfig": {
            "temperature": cfg["temperature"],
            "maxOutputTokens": cfg["max_output_tokens"],
        },
    }
    resp = client.post(url, params={"key": cfg["api_key"]}, json=payload)
    resp.raise_for_status()
    body = resp.json()
    candidates = body.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "\n".join(str(item.get("text", "")) for item in parts if isinstance(item, dict)).strip()


def _call_local_mock(*, task_type: TaskType, text: str) -> str:
    if task_type == TaskType.AIGC_DETECT:
        payload = _local_mock_detect_payload(text)
        return json.dumps(payload, ensure_ascii=False)
    return _local_mock_transform_text(task_type=task_type, text=text)


def _local_mock_transform_text(*, task_type: TaskType, text: str) -> str:
    normalized = _normalize_local_text(text)
    if not normalized:
        return ""

    seed = int(hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8], 16)
    output = normalized
    common_replacements = (
        ("首先", "第一"),
        ("其次", "第二"),
        ("因此", "由此可见"),
        ("但是", "然而"),
        ("总之", "综合来看"),
        ("可以看出", "据此可见"),
    )
    rewrite_replacements = (
        ("研究表明", "已有研究指出"),
        ("我们发现", "分析结果显示"),
        ("非常", "较为"),
        ("重要", "关键"),
    )

    for src, dst in common_replacements:
        output = output.replace(src, dst)
    if task_type == TaskType.REWRITE:
        for src, dst in rewrite_replacements:
            output = output.replace(src, dst)

    if task_type == TaskType.DEDUP:
        output = _rotate_clause_segments(output, seed=seed)
    else:
        output = _inject_transition_tokens(output, seed=seed)

    if output == normalized:
        output = f"{normalized}\n\n[local-mock-llm-refined]"
    return output.strip()


def _local_mock_detect_payload(text: str) -> dict[str, Any]:
    normalized = _normalize_local_text(text)
    if not normalized:
        return {"ai_score": 0.02, "label": "low", "reason": "empty_text"}

    chunks = [part.strip() for part in re.split(r"[。！？.!?\n]+", normalized) if part.strip()]
    sentence_count = len(chunks)
    avg_len = sum(len(part) for part in chunks) / max(sentence_count, 1)
    unique_ratio = len(set(normalized)) / max(len(normalized), 1)
    repeat_signal = max(0.0, min(1.0, 1.0 - unique_ratio))
    punctuation_signal = len(re.findall(r"[，,；;。.!?！？]", normalized)) / max(len(normalized), 1)

    seed = int(hashlib.sha256(normalized.encode("utf-8")).hexdigest()[-8:], 16)
    jitter = ((seed % 11) - 5) / 1000.0

    raw_score = 0.22 + (avg_len / 120.0) * 0.4 + repeat_signal * 0.33 + punctuation_signal * 1.6 + jitter
    score = round(_clamp01(raw_score), 4)
    if score >= 0.65:
        label = "high"
    elif score >= 0.35:
        label = "medium"
    else:
        label = "low"

    reason = (
        f"local_mock_estimate(avg_sentence_len={avg_len:.1f}, "
        f"repeat_signal={repeat_signal:.2f}, sentence_count={sentence_count})"
    )
    return {"ai_score": score, "label": label, "reason": reason}


def _normalize_local_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _rotate_clause_segments(text: str, *, seed: int) -> str:
    clauses = [item.strip() for item in re.split(r"[，,；;]", text) if item.strip()]
    if len(clauses) < 2:
        return text
    shift = seed % len(clauses)
    rotated = clauses[shift:] + clauses[:shift]
    return "，".join(rotated)


def _inject_transition_tokens(text: str, *, seed: int) -> str:
    tokens = ("从结构上看，", "进一步而言，", "在此基础上，", "换个角度看，")
    chunks = re.split(r"([。！？.!?])", text)
    if not chunks:
        return text

    rebuilt: list[str] = []
    sentence_index = 0
    for index in range(0, len(chunks), 2):
        body = chunks[index].strip()
        punct = chunks[index + 1] if index + 1 < len(chunks) else ""
        if not body:
            continue
        if sentence_index > 0:
            token = tokens[(seed + sentence_index) % len(tokens)]
            if not body.startswith(token):
                body = f"{token}{body}"
        rebuilt.append(f"{body}{punct}")
        sentence_index += 1
    return "".join(rebuilt).strip()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
