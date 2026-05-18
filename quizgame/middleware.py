import json

from django.shortcuts import render

from .translation_utils import (
    TRANSLATABLE_HTML_TYPES,
    TRANSLATABLE_JSON_TYPES,
    replace_in_html,
    translate_json_payload,
)


class UiTranslationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if getattr(response, "streaming", False):
            return response

        content_type = response.get("Content-Type", "")
        if not content_type:
            return response

        if hasattr(response, "render") and callable(response.render) and not response.is_rendered:
            response.render()

        language_code = getattr(request, "LANGUAGE_CODE", None)

        if any(content_type.startswith(item) for item in TRANSLATABLE_HTML_TYPES):
            try:
                content = response.content.decode(response.charset or "utf-8")
                translated = replace_in_html(content, language_code)
                response.content = translated.encode(response.charset or "utf-8")
                response["Content-Length"] = str(len(response.content))
            except Exception:
                return response
            return response

        if any(content_type.startswith(item) for item in TRANSLATABLE_JSON_TYPES):
            try:
                payload = json.loads(response.content.decode(response.charset or "utf-8"))
                translated_payload = translate_json_payload(payload, language_code)
                response.content = json.dumps(translated_payload, ensure_ascii=False).encode(response.charset or "utf-8")
                response["Content-Length"] = str(len(response.content))
            except Exception:
                return response

        return response


class MethodNotAllowedPageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        accepts = request.headers.get("Accept", "")
        wants_html = "text/html" in accepts or "*/*" in accepts or not accepts
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if response.status_code != 405 or not wants_html or is_ajax:
            return response

        template_response = render(request, "405.html", status=405)
        allow_header = response.headers.get("Allow")
        if allow_header:
            template_response["Allow"] = allow_header
        return template_response
