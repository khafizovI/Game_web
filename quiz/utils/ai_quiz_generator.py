import json
import re

import httpx
from django.conf import settings
from groq import Groq

DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"


def build_groq_client(api_key: str) -> Groq:
    # Groq 0.8.x can trip over httpx 0.28.x if it builds its own default client.
    # Passing an explicit httpx client avoids the removed `proxies` constructor arg.
    http_client = httpx.Client(
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
        trust_env=True,
    )
    return Groq(api_key=api_key, http_client=http_client)


def generate_quiz_from_topic(topic: str, num_questions: int, num_options: int) -> dict:
    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in the environment.")
    model_name = getattr(settings, "GROQ_MODEL", DEFAULT_GROQ_MODEL) or DEFAULT_GROQ_MODEL

    client = build_groq_client(api_key)
    try:
        question_generation_prompt = f"""
        Generate exactly {num_questions} quiz questions on the topic: '{topic}'.
        Return ONLY a numbered list of the question texts. Do not include answers or options.
        """
        try:
            question_list_completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": question_generation_prompt}],
                temperature=0.7,
                max_tokens=1024,
                top_p=1,
                stream=False,
            )
            generated_text = question_list_completion.choices[0].message.content
            question_texts = []
            for line in generated_text.strip().splitlines():
                if re.match(r"^\d+\.\s", line.strip()):
                    question_texts.append(line.strip().lstrip("1234567890. "))

            if not question_texts:
                lines = [line.strip() for line in generated_text.strip().splitlines() if line.strip()]
                if len(lines) > num_questions and not re.match(r"^\d+\.\s", lines[0]):
                    lines.pop(0)
                question_texts = [line.lstrip("1234567890. ") for line in lines]

            if not question_texts:
                raise ValueError("AI failed to generate question texts.")
        except Exception as e:
            raise RuntimeError(f"AI failed during question text generation: {e}")

        final_questions = []
        for q_text in question_texts:
            options_generation_prompt = f"""
            For the quiz question: '{q_text}'
            Generate exactly {num_options} multiple-choice options.
            Provide the output ONLY in JSON format with two keys:
            1. "options": a list of {num_options} string options.
            2. "answer": the string of the correct answer, which must be one of the options.
            """
            try:
                options_completion = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": options_generation_prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                    max_tokens=1024,
                    top_p=1,
                    stream=False,
                )
                options_data_text = options_completion.choices[0].message.content
                options_data = json.loads(options_data_text)

                options = options_data.get("options", [])
                answer = options_data.get("answer", "")
                if not answer or not options:
                    print(f"Warning: Missing options or answer for question '{q_text}'. Skipping.")
                    continue

                correct_option = None
                for option in options:
                    if option.strip().lower() == answer.strip().lower():
                        correct_option = option
                        break

                if not correct_option:
                    print(
                        f"Warning: AI-provided answer '{answer}' does not match any option for question '{q_text}'. Skipping."
                    )
                    continue

                final_questions.append(
                    {
                        "question": q_text,
                        "options": options,
                        "answer": correct_option,
                    }
                )
            except Exception as e:
                print(f"Warning: Failed to generate options for question '{q_text}'. Error: {e}")
                continue

        if not final_questions:
            raise ValueError("AI failed to generate any complete questions with options.")

        return {"questions": final_questions}
    finally:
        client.close()
