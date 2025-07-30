import json
import re
from django.conf import settings
from groq import Groq

# Switched to the Groq API for better reliability and a free solution.
# Using a powerful and free model: llama3-8b-8192

def generate_quiz_from_topic(topic: str, num_questions: int, num_options: int) -> dict:
    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in the environment.")

    client = Groq(api_key=api_key)

    # --- Step 1: Generate a list of question texts --- 
    question_generation_prompt = f"""
    Generate exactly {num_questions} quiz questions on the topic: '{topic}'.
    Return ONLY a numbered list of the question texts. Do not include answers or options.
    """
    try:
        question_list_completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": question_generation_prompt}],
            temperature=0.7,
            max_tokens=1024,
            top_p=1,
            stream=False,
        )
        generated_text = question_list_completion.choices[0].message.content
        # Filter out the introductory line and process only the actual questions.
        question_texts = []
        for line in generated_text.strip().splitlines():
            # A valid question line typically starts with a number and a period.
            if re.match(r"^\d+\.\s", line.strip()):
                question_texts.append(line.strip().lstrip("1234567890. "))

        if not question_texts:
            # Fallback for cases where the AI doesn't number the questions
            lines = [line.strip() for line in generated_text.strip().splitlines() if line.strip()]
            # If there's a title-like first line, remove it.
            if len(lines) > num_questions and not re.match(r"^\d+\.\s", lines[0]):
                lines.pop(0)
            question_texts = [l.lstrip("1234567890. ") for l in lines]

        if not question_texts:
            raise ValueError("AI failed to generate question texts.")

    except Exception as e:
        raise RuntimeError(f"AI failed during question text generation: {e}")

    # --- Step 2: For each question, generate its options and answer --- 
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
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": options_generation_prompt}],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1024,
                top_p=1,
                stream=False,
            )
            options_data_text = options_completion.choices[0].message.content
            options_data = json.loads(options_data_text)

            final_questions.append({
                "question": q_text,
                "options": options_data.get('options', []),
                "answer": options_data.get('answer', '')
            })

        except Exception as e:
            # If one question fails, we can skip it and continue
            print(f"Warning: Failed to generate options for question '{q_text}'. Error: {e}")
            continue

    if not final_questions:
        raise ValueError("AI failed to generate any complete questions with options.")

    return {"questions": final_questions}
