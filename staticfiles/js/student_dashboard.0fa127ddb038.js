document.addEventListener('DOMContentLoaded', function() {
    // Handle equip button clicks in the collection section
    const equipButtons = document.querySelectorAll('.equip-btn');
    
    equipButtons.forEach(button => {
        button.addEventListener('click', function() {
            const itemId = this.getAttribute('data-item-id');
            equipFrame(itemId, this);
        });
    });
    
    function equipFrame(itemId, button) {
        // Disable button to prevent double clicks
        button.disabled = true;
        
        // Get CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch(`/accounts/shop/equip-frame/${itemId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({
                item_id: itemId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update UI to show equipped state
                updateEquippedState(itemId);
                showNotification('Frame equipped successfully!', 'success');
            } else {
                showNotification(data.message || 'Failed to equip frame', 'error');
                // Restore button
                button.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('An error occurred', 'error');
            // Restore button
            button.disabled = false;
        });
    }
    
    function updateEquippedState(itemId) {
        // Remove all equipped badges and restore equip buttons
        document.querySelectorAll('.equipped-badge').forEach(badge => {
            const parent = badge.parentElement;
            badge.remove();
            
            // Add equip button back
            const equipBtn = document.createElement('button');
            equipBtn.className = 'btn btn-sm btn-primary equip-btn';
            equipBtn.setAttribute('data-item-id', parent.closest('.collection-item').querySelector('.equip-btn, .equipped-badge').getAttribute('data-item-id') || '');
            equipBtn.textContent = 'Equip';
            parent.appendChild(equipBtn);
            
            // Add event listener to new button
            equipBtn.addEventListener('click', function() {
                const itemId = this.getAttribute('data-item-id');
                equipFrame(itemId, this);
            });
        });
        
        // Add equipped badge to the selected item
        const targetButton = document.querySelector(`[data-item-id="${itemId}"]`);
        if (targetButton) {
            const parent = targetButton.parentElement;
            targetButton.remove();
            
            const equippedBadge = document.createElement('span');
            equippedBadge.className = 'equipped-badge';
            equippedBadge.textContent = 'Equipped';
            parent.appendChild(equippedBadge);
        }
        
        // Update avatar frame in the header section
        updateAvatarFrame();
    }
    
    function updateAvatarFrame() {
        // Reload the page to update the avatar frame display
        // This is a simple approach - in a more complex app, you might update the frame dynamically
        setTimeout(() => {
            location.reload();
        }, 1000);
    }
    
    function showNotification(message, type) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 3000);
    }
});
