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
            messages=[{"role": "user", "content": question_generation_prompt}],
            model="llama3-8b-8192",
            temperature=0.7,
            max_tokens=1024,
            top_p=1,
            stream=False,
        )
        generated_text = question_list_completion.choices[0].message.content
        question_texts = [
            line.strip().lstrip("1234567890. ")
            for line in generated_text.strip().splitlines()
            if line.strip()
        ]
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
        Do not include the question text or any other explanation.
        """
        try:
            options_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": options_generation_prompt}],
                model="llama3-8b-8192",
                response_format={"type": "json_object"}, # Use JSON mode for reliability
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
