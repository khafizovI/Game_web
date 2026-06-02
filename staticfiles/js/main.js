document.addEventListener('DOMContentLoaded', function() {
    const loadingOverlay = document.getElementById('site-loading');

    function hideLoadingOverlay() {
        if (loadingOverlay) {
            loadingOverlay.classList.add('is-hidden');
            loadingOverlay.setAttribute('aria-busy', 'false');
        }
    }

    function showLoadingOverlay() {
        if (loadingOverlay) {
            loadingOverlay.classList.remove('is-hidden');
            loadingOverlay.setAttribute('aria-busy', 'true');
        }
    }

    // Function to get CSRF token from cookies
    function getCSRFToken() {
        const name = 'csrftoken=';
        const decodedCookie = decodeURIComponent(document.cookie);
        const ca = decodedCookie.split(';');
        for(let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') {
                c = c.substring(1);
            }
            if (c.indexOf(name) === 0) {
                return c.substring(name.length, c.length);
            }
        }
        return null;
    }
    
    // Add CSRF token to all AJAX requests
    const token = getCSRFToken();
    if (token) {
        // For standard XHR requests
        const originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function() {
            originalOpen.apply(this, arguments);
            this.setRequestHeader('X-CSRFToken', token);
        };
        
        // For fetch API
        const originalFetch = window.fetch;
        window.fetch = function(resource, options = {}) {
            options.headers = options.headers || {};
            options.headers['X-CSRFToken'] = token;
            return originalFetch(resource, options);
        };
    }

    // Initialize and show all toast messages
    const toastElements = document.querySelectorAll('.toast');
    toastElements.forEach(toastEl => {
        const toast = new bootstrap.Toast(toastEl, {
            delay: 5000 // 5 seconds
        });
        toast.show();
    });

    document.querySelectorAll('input[type="password"]').forEach(input => {
        if (input.dataset.passwordToggleReady === 'true') {
            return;
        }

        const parent = input.parentElement;
        if (!parent) {
            return;
        }

        parent.classList.add('password-toggle-field');
        input.classList.add('password-toggle-input');
        input.dataset.passwordToggleReady = 'true';

        const toggleButton = document.createElement('button');
        toggleButton.type = 'button';
        toggleButton.className = 'password-toggle-btn';
        toggleButton.setAttribute('aria-label', window.t ? window.t('Show password', 'Show password') : 'Show password');
        toggleButton.innerHTML = '<i class="fas fa-eye" aria-hidden="true"></i>';

        toggleButton.addEventListener('click', function () {
            const isHidden = input.type === 'password';
            input.type = isHidden ? 'text' : 'password';
            toggleButton.setAttribute(
                'aria-label',
                isHidden
                    ? (window.t ? window.t('Hide password', 'Hide password') : 'Hide password')
                    : (window.t ? window.t('Show password', 'Show password') : 'Show password')
            );
            toggleButton.innerHTML = isHidden
                ? '<i class="fas fa-eye-slash" aria-hidden="true"></i>'
                : '<i class="fas fa-eye" aria-hidden="true"></i>';
        });

        input.insertAdjacentElement('afterend', toggleButton);
    });

    document.addEventListener('click', function(event) {
        const link = event.target.closest('a[href]');
        if (!link) {
            return;
        }

        const href = link.getAttribute('href');
        if (
            !href ||
            href.startsWith('#') ||
            href.startsWith('javascript:') ||
            link.hasAttribute('download') ||
            link.getAttribute('target') === '_blank' ||
            event.ctrlKey ||
            event.metaKey ||
            event.shiftKey ||
            event.button !== 0
        ) {
            return;
        }

        showLoadingOverlay();
    }, true);

    document.addEventListener('submit', function() {
        showLoadingOverlay();
    }, true);

    window.addEventListener('pageshow', hideLoadingOverlay);
    hideLoadingOverlay();
});
