document.addEventListener('DOMContentLoaded', () => {
    const translate = window.t || ((key, fallback) => fallback || key);
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || getCookie('csrftoken');
    const coinBalance = document.getElementById('coin-balance');
    const confirmModalElement = document.getElementById('boxConfirmModal');
    const confirmModal = confirmModalElement ? new bootstrap.Modal(confirmModalElement) : null;
    const confirmOpenButton = document.getElementById('confirm-open-box');
    const confirmText = document.getElementById('box-confirm-text');
    const rewardModalElement = document.getElementById('rewardModal');
    const rewardModal = rewardModalElement ? new bootstrap.Modal(rewardModalElement) : null;
    const rewardPreview = document.getElementById('reward-preview');
    const rewardRarity = document.getElementById('reward-rarity');
    const rewardName = document.getElementById('reward-name');
    const rewardMeta = document.getElementById('reward-meta');
    const historyToggle = document.getElementById('toggle-shop-history');
    const historyPanel = document.getElementById('shop-history');
    let pendingButton = null;

    document.querySelectorAll('.open-box-btn').forEach((button) => {
        button.addEventListener('click', () => askToOpenBox(button));
    });

    confirmOpenButton?.addEventListener('click', () => {
        if (pendingButton) {
            confirmModal?.hide();
            openBox(pendingButton);
        }
    });

    historyToggle?.addEventListener('click', () => {
        historyPanel?.classList.toggle('history-collapsed');
        const isOpen = !historyPanel?.classList.contains('history-collapsed');
        const label = isOpen ? historyToggle.dataset.hideLabel : historyToggle.dataset.showLabel;
        const labelSpan = historyToggle.querySelector('span');
        if (labelSpan && label) {
            labelSpan.textContent = label;
        }
    });

    function askToOpenBox(button) {
        const price = parseInt(button.dataset.price || '0', 10);
        const currentCoins = parseInt(coinBalance?.textContent || '0', 10);
        if (currentCoins < price) {
            showNotification(translate('Not enough coins', 'Not enough coins'), 'error');
            return;
        }

        const boxName = button.dataset.boxName || translate('this item', 'this item');
        pendingButton = button;
        if (confirmText) {
            confirmText.textContent = translate(
                'Are you sure you want to purchase {item_name}?',
                `Are you sure you want to purchase ${boxName}?`
            ).replace('{item_name}', boxName);
        }
        confirmModal?.show();
    }

    function openBox(button) {
        button.disabled = true;
        button.classList.add('is-opening');

        fetch(button.dataset.url, {
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
                    showNotification(data.message || translate('Box opening failed.', 'Box opening failed.'), 'error');
                    return;
                }

                if (coinBalance) {
                    coinBalance.textContent = data.new_coin_balance;
                }

                if (data.pet) {
                    renderPetReward(data.pet, data.duplicate);
                } else if (data.item) {
                    renderItemReward(data.item, data.duplicate);
                }

                rewardModal?.show();
            })
            .catch(() => showNotification(translate('An error occurred. Please try again.', 'An error occurred. Please try again.'), 'error'))
            .finally(() => {
                button.disabled = false;
                button.classList.remove('is-opening');
                pendingButton = null;
            });
    }

    function renderItemReward(item, duplicate) {
        rewardPreview.className = `reward-preview rarity-rail-${item.rarity}`;
        rewardPreview.innerHTML = item.type === 'avatar'
            ? `<img src="${item.preview}" alt="${escapeHtml(item.name)}">`
            : `<i class="fas ${iconForType(item.type)}"></i>`;
        rewardRarity.textContent = item.rarity_label;
        rewardRarity.className = `reward-rarity rarity-text-${item.rarity}`;
        rewardName.textContent = item.name;
        rewardMeta.textContent = `${item.type_label}${duplicate ? ` · ${translate('Duplicate item', 'Duplicate item')}` : ` · ${translate('Added to inventory', 'Added to inventory')}`}`;
    }

    function renderPetReward(pet, duplicate) {
        rewardPreview.className = `reward-preview pet-reward rarity-rail-${pet.rarity}`;
        rewardPreview.innerHTML = pet.image && pet.image.includes('/')
            ? `<img src="${escapeHtml(pet.image)}" alt="${escapeHtml(pet.name)}">`
            : escapeHtml(pet.image || pet.name);
        rewardRarity.textContent = pet.rarity_label;
        rewardRarity.className = `reward-rarity rarity-text-${pet.rarity}`;
        rewardName.textContent = pet.name;
        rewardMeta.textContent = `${pet.unlocked_at}${duplicate ? ` · ${translate('Duplicate pet', 'Duplicate pet')}` : ` · ${translate('Added to inventory', 'Added to inventory')}`}`;
    }

    function iconForType(type) {
        const icons = {
            border: 'fa-circle-notch',
            banner: 'fa-image',
            title: 'fa-tag',
        };
        return icons[type] || 'fa-star';
    }

    function showNotification(message, type) {
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
