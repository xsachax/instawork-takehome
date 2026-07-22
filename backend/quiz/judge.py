"""AI judge for non-deterministic question types (text and image).

Deterministic questions (single/multiple/numerical) are graded exactly by
``quiz.grading``. Free-response text and image-upload answers can't be graded
by simple rules, so — when the client supplies an API key on the request — we
ask an OpenAI-compatible Chat Completions model to decide whether the answer is
correct.

Design notes
------------
* The API key is supplied **per request by the client**. It is passed into these
  functions as an argument and only ever held in memory for the duration of the
  request. It is never persisted, logged, or attached to any model.
* The single outbound HTTP call lives in :func:`_call_chat_completion` so tests
  can monkeypatch it and never touch the network.
* Every public function degrades gracefully: on a missing key, a network error,
  a timeout, or an unparseable response it returns ``None`` so the caller can
  fall back to the existing heuristic grading. It never raises to the view.
"""

from __future__ import annotations

import base64
import json
import re

import requests


DEFAULT_BASE_URL = 'https://api.openai.com/v1'
# gpt-4o-mini is inexpensive and vision-capable, so it works for both the text
# and image judges.
DEFAULT_MODEL = 'gpt-4o-mini'
REQUEST_TIMEOUT = 30

_SYSTEM_PROMPT = (
    'You are a strict but fair quiz grader. Decide whether the student answer '
    'satisfies the question. Respond with ONLY a JSON object of the form '
    '{"correct": true or false, "reason": "a short explanation"}. Do not '
    'include any text outside the JSON object.'
)


def _call_chat_completion(messages, *, api_key, model, base_url,
                          timeout=REQUEST_TIMEOUT):
    """Make the actual Chat Completions request and return the reply content.

    Isolated as the single network boundary so tests can monkeypatch it. Raises
    on any HTTP/transport error — callers are responsible for handling failures.
    """
    url = base_url.rstrip('/') + '/chat/completions'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': messages,
        'temperature': 0,
        'response_format': {'type': 'json_object'},
    }
    response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return data['choices'][0]['message']['content']


def _parse_verdict(content):
    """Parse the model reply into a ``{'correct': bool, 'reason': str}`` dict.

    Tolerates a JSON object embedded in surrounding prose. Returns ``None`` if a
    boolean verdict can't be extracted.
    """
    if content is None:
        return None
    text = str(content).strip()
    data = None
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except (ValueError, TypeError):
                data = None
    if not isinstance(data, dict) or 'correct' not in data:
        return None
    return {
        'correct': bool(data.get('correct')),
        'reason': str(data.get('reason', '')),
    }


def _judge(messages, *, api_key, model, base_url):
    """Run one judge round-trip, swallowing errors into ``None``."""
    if not api_key:
        return None
    try:
        content = _call_chat_completion(
            messages,
            api_key=api_key,
            model=model or DEFAULT_MODEL,
            base_url=base_url or DEFAULT_BASE_URL,
        )
    except Exception:
        # Any transport/HTTP/parse error -> let the caller fall back. We
        # deliberately do not log the exception payload to avoid leaking the
        # key or answer contents.
        return None
    return _parse_verdict(content)


def judge_text(question, response, *, api_key, model=None, base_url=None):
    """Ask the judge whether a free-response answer is correct.

    Returns ``{'correct': bool, 'reason': str}`` or ``None`` to signal fallback.
    """
    accepted = [str(a) for a in (question.text_answers or []) if str(a).strip()]
    accepted_text = '; '.join(accepted) if accepted else '(none provided)'
    user_prompt = (
        f'Question: {question.prompt}\n'
        f'Accepted answers / keywords: {accepted_text}\n'
        f'Student answer: {response or ""}\n\n'
        'Is the student answer correct? Reply with the JSON object described.'
    )
    messages = [
        {'role': 'system', 'content': _SYSTEM_PROMPT},
        {'role': 'user', 'content': user_prompt},
    ]
    return _judge(messages, api_key=api_key, model=model, base_url=base_url)


def judge_image(question, data_url, *, api_key, model=None, base_url=None):
    """Ask a vision-capable judge whether an uploaded image meets the requirement.

    ``data_url`` should be a base64 ``data:`` URL. Returns the verdict dict or
    ``None`` for fallback.
    """
    if not data_url:
        return None
    requirement = question.image_requirement or '(no explicit requirement)'
    user_prompt = (
        f'Question: {question.prompt}\n'
        f'The uploaded image must satisfy this requirement: {requirement}\n\n'
        'Does the attached image satisfy the requirement? Reply with the JSON '
        'object described.'
    )
    messages = [
        {'role': 'system', 'content': _SYSTEM_PROMPT},
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': user_prompt},
                {'type': 'image_url', 'image_url': {'url': data_url}},
            ],
        },
    ]
    return _judge(messages, api_key=api_key, model=model, base_url=base_url)


def image_to_data_url(image_file):
    """Encode an uploaded image file into a base64 ``data:`` URL.

    Leaves the file pointer rewound so the file can still be saved afterwards.
    Returns ``None`` if the file can't be read.
    """
    if image_file is None:
        return None
    try:
        image_file.seek(0)
        raw = image_file.read()
        image_file.seek(0)
    except (OSError, ValueError):
        return None
    if not raw:
        return None
    content_type = getattr(image_file, 'content_type', None) or 'image/png'
    encoded = base64.b64encode(raw).decode('ascii')
    return f'data:{content_type};base64,{encoded}'
