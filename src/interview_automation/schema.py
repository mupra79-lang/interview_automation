from __future__ import annotations


SCRIPT_SCHEMA = {
    "type": "object",
    "required": [
        "title",
        "title_ideas",
        "audience",
        "difficulty",
        "questions",
        "narration",
        "chapters",
        "description",
        "tags",
        "thumbnail_text",
        "sources",
        "uniqueness_fingerprint",
    ],
    "properties": {
        "title": {"type": "string", "minLength": 8},
        "title_ideas": {"type": "array", "minItems": 3, "items": {"type": "string"}},
        "audience": {"type": "string"},
        "difficulty": {"type": "string"},
        "questions": {
            "type": "array",
            "minItems": 10,
            "items": {
                "type": "object",
                "required": ["number", "question", "answer", "key_points", "example"],
                "properties": {
                    "number": {"type": "integer", "minimum": 1},
                    "question": {"type": "string", "minLength": 12},
                    "answer": {"type": "string", "minLength": 60},
                    "key_points": {"type": "array", "items": {"type": "string"}},
                    "example": {"type": "string"},
                },
            },
        },
        "narration": {"type": "array", "items": {"type": "string"}},
        "chapters": {"type": "array", "items": {"type": "object"}},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "thumbnail_text": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"}},
        "uniqueness_fingerprint": {"type": "string"},
    },
}
