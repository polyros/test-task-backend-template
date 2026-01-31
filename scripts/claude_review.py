#!/usr/bin/env python3
"""
Скрипт для автоматического code review через Claude Code CLI.
Используется в GitHub Actions после прохождения автотестов.

Требует установленный Claude Code CLI и токен CLAUDE_CODE_OAUTH_TOKEN.
"""

import argparse
import json
import os
import subprocess
import sys


# Промпт для оценки Backend задания
BACKEND_PROMPT = '''Ты - senior Python разработчик, проводящий code review тестового задания.

ЗАДАНИЕ:
Кандидат должен был найти проблемы в коде, описать их в REVIEW.md, исправить и написать тесты.

ИЗВЕСТНЫЕ ПРОБЛЕМЫ В ОРИГИНАЛЬНОМ КОДЕ (Backend):
1. SQL Injection - raw query с f-string (критичная уязвимость)
2. N+1 queries - цикл с lazy load (проблема производительности)
3. Блокирующий вызов - requests в async функции (блокирует event loop)
4. PII в логах - пароль пишется в logger.info (нарушение безопасности)
5. Race condition - global counter без блокировки (конкурентность)
6. Отсутствие валидации - dict вместо Pydantic schema (надежность)

REVIEW.md КАНДИДАТА:
{review_content}

DIFF (изменения кандидата):
{diff_content}

КРИТЕРИИ ОЦЕНКИ:
- Найденные проблемы (0-30 баллов): сколько из 6 проблем описано в REVIEW.md
- Качество исправлений (0-35 баллов): правильность и чистота кода
- Качество review (0-15 баллов): понятность описания, best practices
- Качество тестов (0-20 баллов): покрытие критичных случаев

ОТВЕТЬ СТРОГО В JSON ФОРМАТЕ:
{{
  "score": <итоговый балл 0-100>,
  "problems_found": ["sql_injection", "n_plus_one", "blocking_call", "pii_in_logs", "race_condition", "no_validation"],
  "problems_fixed": ["sql_injection", ...],
  "breakdown": {{
    "problems": <0-30>,
    "fixes": <0-35>,
    "review": <0-15>,
    "tests": <0-20>
  }},
  "summary": "<2-3 предложения на русском о работе кандидата>",
  "strengths": ["сильная сторона 1", "сильная сторона 2"],
  "improvements": ["что можно улучшить 1", "что можно улучшить 2"],
  "recommendation": "pass|review|reject"
}}

Где recommendation:
- "pass" - оценка >= 60, автоматическое прохождение
- "review" - оценка 40-59, требуется ручная проверка рекрутером
- "reject" - оценка < 40, автоматический отказ

ВАЖНО: Отвечай ТОЛЬКО валидным JSON, без markdown, без комментариев.'''

# Таймаут по умолчанию (секунд)
DEFAULT_TIMEOUT = 120


def read_file(path: str) -> str:
    """Читает содержимое файла."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""


def call_claude_cli(prompt: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Вызывает Claude через CLI (подписка).

    Args:
        prompt: промпт для Claude
        timeout: таймаут в секундах (по умолчанию 120)

    Returns:
        dict с результатами review

    Raises:
        RuntimeError: если CLI вернул ошибку
        subprocess.TimeoutExpired: если запрос превысил timeout
    """
    try:
        # claude --print принимает prompt из stdin и выводит ответ
        result = subprocess.run(
            ["claude", "--print", "--output-format", "json"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI error: {result.stderr}")

        response = result.stdout.strip()

        # Парсим JSON ответ от CLI
        try:
            cli_response = json.loads(response)
        except json.JSONDecodeError:
            # Если ответ не JSON, возможно это plain text
            cli_response = {"result": response}

        # Извлекаем текст ответа из CLI response
        if isinstance(cli_response, dict) and "result" in cli_response:
            response_text = cli_response["result"]
        elif isinstance(cli_response, str):
            response_text = cli_response
        else:
            response_text = response

        # Парсим JSON из ответа Claude
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Попытка извлечь JSON из текста
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(response_text[start:end])
            raise ValueError(f"Не удалось распарсить JSON из ответа Claude: {response_text}")

    except subprocess.TimeoutExpired:
        # Fallback при timeout - возвращаем результат для ручной проверки
        return {
            "score": 50,
            "recommendation": "review",
            "summary": "AI review не завершён в отведённое время. Требуется ручная проверка.",
            "breakdown": {"problems": 0, "fixes": 0, "review": 0, "tests": 0},
            "problems_found": [],
            "problems_fixed": [],
            "strengths": [],
            "improvements": ["Не удалось выполнить автоматическую проверку в отведённое время"]
        }


def main():
    parser = argparse.ArgumentParser(description='Claude AI Code Review (CLI)')
    parser.add_argument('--diff', required=True, help='Путь к файлу с diff')
    parser.add_argument('--review', required=True, help='Путь к REVIEW.md')
    parser.add_argument('--output', required=True, help='Путь для сохранения результата')
    parser.add_argument(
        '--task-type',
        default='backend',
        choices=['backend', 'frontend', 'fullstack']
    )
    args = parser.parse_args()

    # Проверяем наличие токена
    if not os.environ.get('CLAUDE_CODE_OAUTH_TOKEN'):
        print("Предупреждение: CLAUDE_CODE_OAUTH_TOKEN не установлен", file=sys.stderr)

    diff_content = read_file(args.diff)
    review_content = read_file(args.review)

    if not diff_content:
        print("Ошибка: diff файл пустой или не существует", file=sys.stderr)
        sys.exit(1)

    prompt = BACKEND_PROMPT.format(
        diff_content=diff_content,
        review_content=review_content or "(REVIEW.md не заполнен)"
    )

    try:
        result = call_claude_cli(prompt)
    except Exception as e:
        print(f"Ошибка при вызове Claude CLI: {e}", file=sys.stderr)
        # Возвращаем fallback результат для ручной проверки
        result = {
            "score": 0,
            "problems_found": [],
            "problems_fixed": [],
            "breakdown": {"problems": 0, "fixes": 0, "review": 0, "tests": 0},
            "summary": f"Ошибка AI review: {str(e)}. Требуется ручная проверка.",
            "strengths": [],
            "improvements": [],
            "recommendation": "review",
            "error": str(e)
        }

    # Сохраняем результат
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Оценка: {result.get('score', 'N/A')}/100")
    print(f"Рекомендация: {result.get('recommendation', 'N/A')}")

    # Возвращаем код выхода в зависимости от результата
    if result.get('error'):
        sys.exit(1)


if __name__ == '__main__':
    main()
