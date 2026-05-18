from .translation_utils import dumps_client_translations, normalize_language_code


def app_i18n(request):
    language_code = normalize_language_code(getattr(request, "LANGUAGE_CODE", None))
    return {
        "app_i18n_json": dumps_client_translations(language_code),
        "app_language_code": language_code,
    }
