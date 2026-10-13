from .constants import MIN_QUIZ_QUESTIONS
from .models import Question


def validate_question_answers(answer_texts, is_correct_list):
    """Return (is_valid, error_key) for a question's answers."""
    filled_answers = [text.strip() for text in answer_texts if text and text.strip()]
    if len(filled_answers) < 2:
        return False, "min_answers"

    has_correct = False
    for index, answer_text in enumerate(answer_texts):
        if not answer_text or not answer_text.strip():
            continue
        if str(index) in is_correct_list:
            has_correct = True
            break

    if not has_correct:
        return False, "correct_required"

    return True, None


def get_quiz_host_status(quiz):
    """Return whether a quiz can be hosted and why not."""
    questions = Question.objects.filter(quiz=quiz).prefetch_related("answers").order_by("order")
    question_count = questions.count()

    if question_count < MIN_QUIZ_QUESTIONS:
        return {
            "can_host": False,
            "reason": "min_questions",
            "question_count": question_count,
            "invalid_questions": [],
        }

    invalid_questions = []
    for question in questions:
        answers = [answer for answer in question.answers.all() if answer.text.strip()]
        if len(answers) < 2 or not any(answer.is_correct for answer in answers):
            invalid_questions.append(question)

    if invalid_questions:
        return {
            "can_host": False,
            "reason": "invalid_questions",
            "question_count": question_count,
            "invalid_questions": invalid_questions,
        }

    return {
        "can_host": True,
        "reason": None,
        "question_count": question_count,
        "invalid_questions": [],
    }
