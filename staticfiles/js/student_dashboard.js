document.addEventListener('DOMContentLoaded', function() {
    // Handle equip button clicks in the collection section
    const equipButtons = document.querySelectorAll('.equip-btn');
    const equipThemeButtons = document.querySelectorAll('.equip-theme-btn');
    
    equipButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault(); // Prevent default link behavior
            const itemId = this.getAttribute('data-item-id');
            equipFrame(itemId, this);
        });
    });
    
    equipThemeButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault(); // Prevent default link behavior
            const itemId = this.getAttribute('data-item-id');
            equipTheme(itemId, this);
        });
    });
    
    function equipFrame(itemId, button) {
        // Disable button to prevent double clicks
        button.disabled = true;
        
        // Get CSRF token
        const csrfToken = getCsrfToken();
        
        if (!csrfToken) {
            showNotification('Security token not found. Please refresh the page.', 'error');
            button.disabled = false;
            return;
        }
        
        fetch(`/en/accounts/shop/equip-frame/${itemId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                item_id: itemId
            })
        })
        .then(response => {
            // Check if response is successful (status 200-299)
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return response.json();
        })
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
            console.error('Fetch error:', error);
            showNotification('An error occurred while equipping frame', 'error');
            // Restore button
            button.disabled = false;
        });
    }
    
    function equipTheme(itemId, button) {
        // Disable button to prevent double clicks
        button.disabled = true;
        
        // Get CSRF token
        const csrfToken = getCsrfToken();
        
        if (!csrfToken) {
            console.log('CSRF Token found:', 'No');
            console.log('Item ID:', itemId);
            console.log('Making POST request to:', `/en/accounts/shop/equip-theme/${itemId}/`);
            showNotification('Security token not found. Please refresh the page.', 'error');
            button.disabled = false;
            return;
        }
        
        console.log('CSRF Token found:', 'Yes');
        console.log('Item ID:', itemId);
        console.log('Making POST request to:', `/en/accounts/shop/equip-theme/${itemId}/`);
        
        fetch(`/en/accounts/shop/equip-theme/${itemId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest', // This helps Django identify AJAX requests
            },
            credentials: 'same-origin', // Include cookies for authentication
            body: JSON.stringify({
                item_id: itemId
            })
        })
        .then(response => {
            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Response data:', data);
            if (data.success) {
                showNotification('Theme equipped successfully!', 'success');
                // Reload page to show updated theme state
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                showNotification(data.message || 'Failed to equip theme', 'error');
                // Restore button
                button.disabled = false;
            }
        })
        .catch(error => {
            console.error('Fetch error:', error);
            showNotification('An error occurred while equipping theme', 'error');
            // Restore button
            button.disabled = false;
        });
    }
    
    function getCsrfToken() {
        // Try multiple methods to get CSRF token
        
        // Method 1: From hidden input
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) {
            return csrfInput.value;
        }
        
        // Method 2: From meta tag
        const csrfMeta = document.querySelector('meta[name=csrf-token]');
        if (csrfMeta) {
            return csrfMeta.getAttribute('content');
        }
        
        // Method 3: From cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        
        return null;
    }
    
    function updateEquippedState(itemId) {
        // Remove all equipped badges and restore equip buttons
        document.querySelectorAll('.equipped-badge').forEach(badge => {
            const parent = badge.parentElement;
            const collectionItem = parent.closest('.collection-item');
            
            // Get the item ID from the badge's data attribute or from the collection item
            let badgeItemId = badge.getAttribute('data-item-id');
            if (!badgeItemId && collectionItem) {
                // Try to find it from any element with data-item-id in the collection item
                const itemWithId = collectionItem.querySelector('[data-item-id]');
                badgeItemId = itemWithId ? itemWithId.getAttribute('data-item-id') : '';
            }
            
            badge.remove();
            
            // Add equip button back
            const equipBtn = document.createElement('button');
            equipBtn.className = 'btn btn-sm btn-primary equip-btn';
            equipBtn.setAttribute('data-item-id', badgeItemId || '');
            equipBtn.textContent = 'Equip';
            parent.appendChild(equipBtn);
            
            // Add event listener to new button
            equipBtn.addEventListener('click', function(e) {
                e.preventDefault(); // Prevent default link behavior
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
            equippedBadge.setAttribute('data-item-id', itemId); // Store the item ID
            equippedBadge.textContent = 'Equipped';
            parent.appendChild(equippedBadge);
        }
        
        // Update avatar frame in the header section
        updateAvatarFrame();
    }
    
    function updateEquippedThemeState(itemId) {
        // Find all theme items by looking for elements with theme-preview class
        const themeItems = document.querySelectorAll('.theme-preview');
        
        themeItems.forEach(themePreview => {
            const collectionItem = themePreview.closest('.collection-item');
            const collectionItemInfo = collectionItem.querySelector('.collection-item-info');
            const equippedBadge = collectionItemInfo.querySelector('.equipped-badge');
            const equipButton = collectionItemInfo.querySelector('.equip-theme-btn');
            
            // If there's an equipped badge, remove it and add equip button
            if (equippedBadge) {
                const currentItemId = equippedBadge.getAttribute('data-item-id') || 
                    equipButton?.getAttribute('data-item-id') || 
                    collectionItem.querySelector('[data-item-id]')?.getAttribute('data-item-id');
                
                equippedBadge.remove();
                
                // Add equip button back
                const equipBtn = document.createElement('button');
                equipBtn.className = 'btn btn-sm btn-primary equip-theme-btn';
                equipBtn.setAttribute('data-item-id', currentItemId);
                equipBtn.textContent = 'Equip';
                collectionItemInfo.appendChild(equipBtn);
                
                // Add event listener to new button
                equipBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    const itemId = this.getAttribute('data-item-id');
                    equipTheme(itemId, this);
                });
            }
        });
        
        // Add equipped badge to the selected item
        const targetButton = document.querySelector(`.equip-theme-btn[data-item-id="${itemId}"]`);
        if (targetButton) {
            const parent = targetButton.parentElement;
            targetButton.remove();
            
            const equippedBadge = document.createElement('span');
            equippedBadge.className = 'equipped-badge';
            equippedBadge.setAttribute('data-item-id', itemId);
            equippedBadge.textContent = 'Equipped';
            parent.appendChild(equippedBadge);
        }
    }
    
    function updateAvatarFrame() {
        // Reload the page to update the avatar frame display
        // This is a simple approach - in a more complex app, you might update the frame dynamically
        setTimeout(() => {
            location.reload();
        }, 1000);
    }
    
    function applyTheme(cssClass) {
        // Apply the theme to the page
        const dashboardContainer = document.querySelector('.dashboard-container');
        
        // Remove existing theme classes
        dashboardContainer.classList.remove('ocean-theme', 'dark-theme', 'sunset-theme');
        
        // Apply new theme CSS class
        if (cssClass) {
            dashboardContainer.classList.add(cssClass);
        }
        
        console.log(`Applied theme class: ${cssClass}`);
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
    
    // Rating System
    const starRating = document.getElementById('starRating');
    const submitRatingBtn = document.getElementById('submitRating');
    const currentRatingValue = document.getElementById('currentRatingValue');
    let selectedRating = 0;
    
    if (starRating) {
        const stars = starRating.querySelectorAll('.star');
        
        // Handle star hover effects
        stars.forEach((star, index) => {
            star.addEventListener('mouseenter', function() {
                highlightStars(index + 1);
            });
            
            star.addEventListener('click', function() {
                selectedRating = index + 1;
                highlightStars(selectedRating);
                submitRatingBtn.style.display = 'inline-block';
            });
        });
        
        // Reset stars on mouse leave
        starRating.addEventListener('mouseleave', function() {
            if (selectedRating > 0) {
                highlightStars(selectedRating);
            } else {
                highlightStars(0);
            }
        });
        
        function highlightStars(rating) {
            stars.forEach((star, index) => {
                if (index < rating) {
                    star.classList.add('active');
                } else {
                    star.classList.remove('active');
                }
            });
        }
        
        // Handle rating submission
        if (submitRatingBtn) {
            submitRatingBtn.addEventListener('click', function() {
                if (selectedRating === 0) {
                    showNotification('Please select a rating first.', 'error');
                    return;
                }
                
                submitRating(selectedRating);
            });
        }
    }
    
    function submitRating(rating) {
        const csrfToken = getCsrfToken();
        
        if (!csrfToken) {
            showNotification('Security token not found. Please refresh the page.', 'error');
            return;
        }
        
        // Disable submit button to prevent double submission
        submitRatingBtn.disabled = true;
        submitRatingBtn.textContent = 'Submitting...';
        
        fetch('/en/accounts/submit-rating/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                rating: rating
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Thank you for your rating!', 'success');
                
                // Hide the entire rating section after successful submission
                const ratingSection = document.querySelector('.dashboard-section:has(.rating-container)');
                if (ratingSection) {
                    ratingSection.style.transition = 'opacity 0.5s ease';
                    ratingSection.style.opacity = '0';
                    setTimeout(() => {
                        ratingSection.remove();
                    }, 500);
                }
            } else {
                showNotification(data.message || 'Failed to submit rating.', 'error');
                submitRatingBtn.disabled = false;
                submitRatingBtn.textContent = 'Submit Rating';
            }
        })
        .catch(error => {
            console.error('Error submitting rating:', error);
            showNotification('An error occurred while submitting your rating.', 'error');
            submitRatingBtn.disabled = false;
            submitRatingBtn.textContent = 'Submit Rating';
        });
    }
});
