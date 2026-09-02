from __future__ import annotations

import json


def fake_qwen_generator(prompt: str, **kwargs):
    topics = [
        ("state schema", "shared state object"),
        ("nodes", "small units of graph work"),
        ("conditional edges", "routing decisions"),
        ("reducers", "merge rules for updates"),
        ("checkpointing", "resume and persistence"),
        ("tool loops", "controlled tool execution"),
        ("human review", "approval steps"),
        ("RAG routing", "retrieval quality handling"),
        ("error recovery", "fallback branches"),
        ("observability", "debugging transitions"),
    ]
    questions = []
    narration = [
        "Welcome to Top 10 LangGraph Interview Questions. Today we will practice ten practical interview questions with clear sample answers, key points, and examples so you can answer with confidence."
    ]
    for index, (name, meaning) in enumerate(topics, start=1):
        questions.append(
            {
                "number": index,
                "question": f"How would you explain LangGraph {name} in an interview?",
                "answer": (
                    f"LangGraph {name} matters because it describes {meaning} and helps candidates explain how stateful AI workflows are designed, controlled, "
                    "tested, and resumed. A strong interview answer connects graph nodes, state updates, routing decisions, and practical "
                    "failure handling instead of describing agents as uncontrolled model calls."
                ),
                "key_points": ["state", "routing", "reliability"],
                "example": "A support agent can route from retrieval to validation before producing the final response.",
            }
        )
        narration.append(
            f"Question {index}. How would you explain LangGraph {name}? Sample answer. LangGraph {name} helps build reliable stateful agent workflows."
        )
    narration.append("That completes this interview practice set. Rehearse each answer out loud and adapt the examples to your own projects.")
    return [
        {
            "generated_text": json.dumps(
                {
                    "title": "Top 10 LangGraph Interview Questions",
                    "title_ideas": [
                        "Top 10 LangGraph Interview Questions",
                        "LangGraph Interview Prep",
                        "Agentic AI LangGraph Questions",
                    ],
                    "audience": "Students and developers preparing for GenAI interviews.",
                    "difficulty": "intermediate",
                    "questions": questions,
                    "narration": narration,
                    "chapters": [{"time": "00:00", "title": "Intro"}],
                    "description": "Original LangGraph interview preparation with practical sample answers.",
                    "tags": ["LangGraph", "GenAI", "Agentic AI"],
                    "thumbnail_text": "Top 10 LangGraph Interview Questions",
                    "sources": ["Original educational content"],
                    "uniqueness_fingerprint": "",
                }
            )
        }
    ]
