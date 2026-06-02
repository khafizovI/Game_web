(function () {
    const avatarInput = document.getElementById('avatar');
    const imagePreview = document.getElementById('imagePreview');

    if (!avatarInput || !imagePreview) {
        return;
    }

    avatarInput.addEventListener('change', function () {
        const file = avatarInput.files && avatarInput.files[0];
        if (!file) {
            return;
        }

        const reader = new FileReader();
        reader.addEventListener('load', function (event) {
            imagePreview.style.backgroundImage = `url(${event.target.result})`;
            imagePreview.style.opacity = '0';
            window.setTimeout(function () {
                imagePreview.style.opacity = '1';
            }, 50);
        });
        reader.readAsDataURL(file);
    });
})();
