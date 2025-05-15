// Language Switcher JavaScript - Simple Direct Version
function changeLanguage(langCode) {
    // Set the language cookie
    document.cookie = "django_language=" + langCode + "; path=/; max-age=31536000";
    
    // Create a temporary form
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/i18n/setlang/';
    form.style.display = 'none';
    
    // Add CSRF token
    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrfmiddlewaretoken';
    csrfInput.value = getCSRFToken();
    form.appendChild(csrfInput);
    
    // Add language
    const langInput = document.createElement('input');
    langInput.type = 'hidden';
    langInput.name = 'language';
    langInput.value = langCode;
    form.appendChild(langInput);
    
    // Add next URL - current page
    const nextInput = document.createElement('input');
    nextInput.type = 'hidden';
    nextInput.name = 'next';
    nextInput.value = window.location.pathname;
    form.appendChild(nextInput);
    
    // Add form to body and submit
    document.body.appendChild(form);
    form.submit();
}

// Get CSRF token from cookies
function getCSRFToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='));
        
    if (cookieValue) {
        return cookieValue.split('=')[1];
    }
    
    // If not found in cookies, try to get from DOM
    const csrfElement = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfElement) {
        return csrfElement.value;
    }
    
    return '';
}
