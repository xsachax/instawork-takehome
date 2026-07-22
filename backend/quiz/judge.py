"""LLM-backed judging for free-response and image answers."""

import base64
import json
import mimetypes
from dataclasses import dataclass

import requests


DEFAULT_BASE_URL = 'https://api.openai.com/v1'
DEFAULT_MODEL = 'gpt-4o-mini'
DEFAULT_TIMEOUT = 20


@dataclass(frozen=True)
class JudgeVerdict:
    correct: bool
    reason: str = ''


def judge_text_answer(question, response, *, api_key, model=None, base_url=None):
    messages = [
        {
            'role': 'system',
            'content': (
                'You are a strict quiz answer judge. Return only JSON with '
                'shape {"correct": true/false, "reason": "..."} and no prose.'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'Question: {question.prompt}\n'
                f'Accepted answers or keywords: '
                f'{json.dumps(question.text_answers or [])}\n'
                f'Text match mode: {question.text_match_mode}\n'
                f'User response: {response or ""}\n\n'
                'Mark correct only if the response satisfies the question and '
                'the accepted answers/keywords. If uncertain, mark incorrect.'
            ),
        },
    ]
    content = _call_chat_completion(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=messages,
    )
    return _parse_judge_content(content)


def judge_image_answer(question, image_file, *, api_key, model=None, base_url=None):
    if not image_file:
        return None
    try:
        data_url = _image_to_data_url(image_file)
    except Exception:
        return None

    messages = [
        {
            'role': 'system',
            'content': (
                'You are a strict quiz image judge. Return only JSON with '
                'shape {"correct": true/false, "reason": "..."} and no prose.'
            ),
        },
        {
            'role': 'user',
            'content': [
                {
                    'type': 'text',
                    'text': (
                        f'Question: {question.prompt}\n'
                        f'Image requirement: {question.image_requirement}\n\n'
                        'Mark correct only if the uploaded image clearly meets '
                        'the requirement. If uncertain, mark incorrect.'
                    ),
                },
                {'type': 'image_url', 'image_url': {'url': data_url}},
            ],
        },
    ]
    content = _call_chat_completion(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=messages,
    )
    return _parse_judge_content(content)


def _call_chat_completion(*, api_key, base_url, model, messages,
                          timeout=DEFAULT_TIMEOUT):
    url = f'{(base_url or DEFAULT_BASE_URL).rstrip("/")}/chat/completions'
    payload = {
        'model': model or DEFAULT_MODEL,
        'messages': messages,
        'temperature': 0,
        'response_format': {'type': 'json_object'},
    }
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return None


def _parse_judge_content(content):
    if not isinstance(content, str):
        return None
    raw = _strip_code_fence(content.strip())
    candidates = [raw]
    start = raw.find('{')
    end = raw.rfind('}')
    if start != -1 and end > start:
        candidates.append(raw[start:end + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        correct = _coerce_bool(data.get('correct'))
        if correct is None:
            continue
        reason = data.get('reason') or ''
        return JudgeVerdict(correct=correct, reason=str(reason))
    return None


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == 'true':
            return True
        if normalized == 'false':
            return False
    return None


def _strip_code_fence(value):
    if not value.startswith('```'):
        return value
    lines = value.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == '```':
        return '\n'.join(lines[1:-1]).strip()
    return value.strip('`').strip()


def _image_to_data_url(image_file):
    position = None
    try:
        position = image_file.tell()
    except (AttributeError, OSError):
        pass

    image_file.seek(0)
    data = image_file.read()
    image_file.seek(position or 0)

    content_type = getattr(image_file, 'content_type', '') or ''
    if not content_type:
        content_type = mimetypes.guess_type(getattr(image_file, 'name', ''))[0]
    content_type = content_type or 'application/octet-stream'
    encoded = base64.b64encode(data).decode('ascii')
    return f'data:{content_type};base64,{encoded}'
