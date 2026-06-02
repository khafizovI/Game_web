document.addEventListener('DOMContentLoaded', () => {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || getCookie('csrftoken');

    document.querySelectorAll('.inventory-tab').forEach((tab) => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.inventory-tab').forEach((entry) => entry.classList.remove('active'));
            document.querySelectorAll('.inventory-section').forEach((section) => section.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`inventory-${tab.dataset.tab}`)?.classList.add('active');
        });
    });

    document.querySelectorAll('.equip-item-btn, .unequip-btn').forEach((button) => {
        button.addEventListener('click', () => postAction(button.dataset.url, button));
    });

    document.querySelectorAll('.preview-btn').forEach((button) => {
        button.addEventListener('click', () => {
            showNotification(`${button.dataset.previewName} · ${button.dataset.previewType} · ${button.dataset.previewRarity}`, 'success');
        });
    });

    function postAction(url, button) {
        button.disabled = true;
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({}),
        })
            .then((response) => response.json())
            .then((data) => {
                if (!data.success) {
                    showNotification(data.message || 'Action failed.', 'error');
                    button.disabled = false;
                    return;
                }
                showNotification(data.message || 'Saved.', 'success');
                window.setTimeout(() => window.location.reload(), 450);
            })
            .catch(() => {
                showNotification('An error occurred. Please try again.', 'error');
                button.disabled = false;
            });
    }

    function showNotification(message, type) {
        document.querySelectorAll('.shop-notification').forEach((entry) => entry.remove());
        const notification = document.createElement('div');
        notification.className = `shop-notification alert alert-${type === 'success' ? 'success' : 'danger'} fade show`;
        notification.innerHTML = `<i class="fas fa-${type === 'success' ? 'check-circle' : 'triangle-exclamation'} me-2"></i>${escapeHtml(message)}`;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 4200);
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(';') : [];
        for (const cookie of cookies) {
            const trimmed = cookie.trim();
            if (trimmed.startsWith(`${name}=`)) {
                return decodeURIComponent(trimmed.slice(name.length + 1));
            }
        }
        return '';
    }
});
