// Shop JavaScript functionality
document.addEventListener('DOMContentLoaded', function() {
    const translate = window.t || ((key) => key);

    // Tab switching functionality
    const shopTabs = document.querySelectorAll('.shop-tab');
    const shopSections = document.querySelectorAll('.shop-section');
    
    shopTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const targetTab = this.dataset.tab;
            
            // Remove active class from all tabs and sections
            shopTabs.forEach(t => t.classList.remove('active'));
            shopSections.forEach(s => s.classList.remove('active'));
            
            // Add active class to clicked tab and corresponding section
            this.classList.add('active');
            document.getElementById(targetTab + '-section').classList.add('active');
        });
    });
    
    // Purchase functionality
    const purchaseButtons = document.querySelectorAll('.purchase-btn');
    const purchaseModal = new bootstrap.Modal(document.getElementById('purchaseModal'));
    const confirmPurchaseBtn = document.getElementById('confirm-purchase');
    let currentItemId = null;
    let currentItemPrice = null;
    let currentItemType = null;
    
    purchaseButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            currentItemId = this.dataset.itemId;
            currentItemPrice = parseInt(this.dataset.price);
            currentItemType = this.dataset.itemType || null;
            
            const currentCoins = parseInt(document.getElementById('coin-balance').textContent);
            const remainingBalance = currentCoins - currentItemPrice;
            
            // Update modal content
            document.getElementById('item-cost').textContent = currentItemPrice;
            document.getElementById('remaining-balance').textContent = remainingBalance;
            
            // Check if user has enough coins
            if (remainingBalance < 0) {
                document.getElementById('remaining-balance').style.color = '#ff6b6b';
                confirmPurchaseBtn.disabled = true;
                confirmPurchaseBtn.textContent = translate('Insufficient Coins');
            } else {
                document.getElementById('remaining-balance').style.color = '#6c757d';
                confirmPurchaseBtn.disabled = false;
                confirmPurchaseBtn.textContent = translate('Purchase');
            }
            
            purchaseModal.show();
        });
    });
    
    // Confirm purchase
    confirmPurchaseBtn.addEventListener('click', function() {
        if (currentItemId && currentItemPrice) {
            purchaseItem(currentItemId, currentItemPrice);
        }
    });
    
    // Equip functionality
    const equipButtons = document.querySelectorAll('.equip-btn');
    const equippedFramePreview = document.getElementById('equipped-frame-preview');
    const equippedFrameName = document.getElementById('equipped-frame-name');
    const knownFrameClasses = [
        'cosmic-frame',
        'dragon-frame',
        'crystal-frame',
        'neon-frame',
        'royal-frame',
        'ocean-frame',
        'flame-frame',
        'shadow-frame',
        'mythic-frame',
        'starlight-frame',
        'tempest-frame',
        'obsidian-frame'
    ];
    
    equipButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const itemId = this.dataset.itemId;
            equipFrame(itemId);
        });
    });
    
    // Purchase item function
    function purchaseItem(itemId, price) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        // Get the current language prefix from the URL
        const currentPath = window.location.pathname;
        const langPrefix = currentPath.match(/^\/([a-z]{2})\//)?.[0] || '/en/';
        
        fetch(`${langPrefix}accounts/shop/purchase/${itemId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update coin balance
                document.getElementById('coin-balance').textContent = data.new_coin_balance;
                
                // Update the button to show "Owned" or "Equip"
                const purchaseBtn = document.querySelector(`[data-item-id="${itemId}"]`);
                if (purchaseBtn) {
                    if ((data.item_type || currentItemType) === 'frame') {
                        purchaseBtn.className = 'btn btn-primary equip-btn';
                        purchaseBtn.innerHTML = `<i class="fas fa-hand-paper"></i> ${translate('Equip')}`;
                        purchaseBtn.dataset.itemId = itemId;
                        
                        // Add event listener for equip functionality
                        purchaseBtn.addEventListener('click', function() {
                            equipFrame(itemId);
                        });
                    } else {
                        purchaseBtn.className = 'btn btn-success';
                        purchaseBtn.innerHTML = `<i class="fas fa-check"></i> ${translate('Owned')}`;
                        purchaseBtn.disabled = true;
                    }
                }
                
                // Show success message
                showNotification(translate('Item purchased successfully!'), 'success');
                
                // Close modal
                purchaseModal.hide();
            } else {
                showNotification(data.message || translate('Purchase failed. Please try again.'), 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification(translate('An error occurred. Please try again.'), 'error');
        });
    }
    
    // Equip frame function
    function equipFrame(itemId) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        // Get the current language prefix from the URL
        const currentPath = window.location.pathname;
        const langPrefix = currentPath.match(/^\/([a-z]{2})\//)?.[0] || '/en/';
        
        fetch(`${langPrefix}accounts/shop/equip-frame/${itemId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update all equip buttons
                document.querySelectorAll('.equip-btn').forEach(btn => {
                    btn.className = 'btn btn-primary equip-btn';
                    btn.innerHTML = `<i class="fas fa-hand-paper"></i> ${translate('Equip')}`;
                    btn.disabled = false;
                });
                
                // Update the equipped item button
                const equippedBtn = document.querySelector(`[data-item-id="${itemId}"]`);
                if (equippedBtn) {
                    equippedBtn.className = 'btn btn-success';
                    equippedBtn.innerHTML = `<i class="fas fa-check"></i> ${translate('Equipped')}`;
                    equippedBtn.disabled = true;
                }

                document.querySelectorAll('[data-frame-card]').forEach(card => {
                    card.classList.remove('selected-frame-card');
                });
                const selectedCard = document.querySelector(`[data-frame-card="${itemId}"]`);
                if (selectedCard) {
                    selectedCard.classList.add('selected-frame-card');
                }

                if (equippedFramePreview && data.css_class) {
                    equippedFramePreview.classList.remove(...knownFrameClasses);
                    equippedFramePreview.classList.add(data.css_class);
                }

                if (equippedFrameName && data.item_name) {
                    equippedFrameName.textContent = data.item_name;
                }
                
                showNotification(translate('Frame equipped successfully!'), 'success');
            } else {
                showNotification(data.message || translate('Failed to equip frame'), 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification(translate('An error occurred. Please try again.'), 'error');
        });
    }
    
    // Notification function
    function showNotification(message, type) {
        // Remove existing notifications
        const existingNotifications = document.querySelectorAll('.shop-notification');
        existingNotifications.forEach(notification => notification.remove());
        
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `shop-notification alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        `;
        
        notification.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
                <span>${message}</span>
                <button type="button" class="btn-close ms-auto" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
    
    // Add CSRF token to all AJAX requests
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!csrfToken) {
        // Create CSRF token input if it doesn't exist
        const tokenInput = document.createElement('input');
        tokenInput.type = 'hidden';
        tokenInput.name = 'csrfmiddlewaretoken';
        tokenInput.value = getCookie('csrftoken');
        document.body.appendChild(tokenInput);
    }
    
    // Get CSRF token from cookies
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});
