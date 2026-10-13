document.addEventListener('DOMContentLoaded', () => {
    const pet = document.getElementById('site-pet');
    if (!pet) {
        return;
    }

    const dialog = document.getElementById('site-pet-dialog');
    const frame = document.getElementById('site-pet-frame');
    const petName = pet.dataset.petName || 'Pet';
    const staticBase = (pet.dataset.petStaticBase || '/static/pets').replace(/\/$/, '');
    const storageKey = `quizbattle.pet.position.${petName}`;
    const lines = {
        Cat: ['Meow! 😸', "Let's win this quiz!", 'Trust your instincts!'],
        Dog: ['Woof! 🐶', "You're doing great!", 'I believe in you!'],
        Cow: ['Moo! 🐮', 'Slow and steady wins!'],
        Fox: ['Hello friend! 🦊', 'Think smart, move fast!'],
        Panda: ['Stay focused! 🐼', 'You can do it!'],
        Owl: ['Time to learn! 📚', 'Read carefully!'],
        Penguin: ['Keep going! 🐧', 'Stay cool!'],
        Robot: ['System ready. 🤖', 'Calculating confidence...', 'Focus mode activated.'],
    };
    const gameLines = {
        lobby: [
            'Get ready to the battle!',
            'Battle is coming. Stay sharp!',
            'Warm up your brain!',
        ],
        motivation: [
            'Keep going, you can win!',
            'Stay focused!',
            'Nice try, next one is yours!',
            'You are getting stronger!',
            'Trust yourself!',
        ],
        correct: [
            'Great answer!',
            'Nice job!',
            'You are on fire!',
        ],
        incorrect: [
            'No worries, keep going!',
            'Next question, new chance!',
            'Do not give up!',
        ],
    };
    const answerColors = ['red', 'blue', 'yellow', 'green'];

    let dragging = false;
    let moved = false;
    let offsetX = 0;
    let offsetY = 0;
    let hideTimer = null;
    let animationTimer = null;
    let ambientTimer = null;
    let isAnimating = false;

    const spriteSets = {
        Cat: {
            default: `${staticBase}/cat/default.png`,
            walk: Array.from({ length: 10 }, (_, index) => `${staticBase}/cat/Walk%20(${index + 1}).png`),
            jump: Array.from({ length: 8 }, (_, index) => `${staticBase}/cat/Jump%20(${index + 1}).png`),
            ambientAction: 'walk',
            ambientInterval: 30000,
            frameMs: 95,
        },
        Robot: {
            default: `${staticBase}/cat/robot/default.png`,
            jump: Array.from({ length: 10 }, (_, index) => `${staticBase}/cat/robot/Jump%20(${index + 1}).png`),
            jumpmelee: Array.from({ length: 8 }, (_, index) => `${staticBase}/cat/robot/JumpMelee%20(${index + 1}).png`),
            ambientAction: 'jumpmelee',
            ambientInterval: 20000,
            frameMs: 90,
        },
    };

    restorePosition();
    setupImageFallback();
    setupSpritePet();

    pet.addEventListener('pointerdown', (event) => {
        dragging = true;
        moved = false;
        pet.classList.add('dragging');
        const rect = pet.getBoundingClientRect();
        offsetX = event.clientX - rect.left;
        offsetY = event.clientY - rect.top;
        pet.setPointerCapture(event.pointerId);
    });

    pet.addEventListener('pointermove', (event) => {
        if (!dragging) {
            return;
        }
        moved = true;
        const x = clamp(event.clientX - offsetX, 0, window.innerWidth - pet.offsetWidth);
        const y = clamp(event.clientY - offsetY, 0, window.innerHeight - pet.offsetHeight);
        pet.style.left = `${x}px`;
        pet.style.top = `${y}px`;
        pet.style.bottom = 'auto';
    });

    window.quizBattlePet = {
        speak,
        speakRandom,
        predictAnswerColor,
        motivate: () => speakRandom('motivation'),
    };

    pet.addEventListener('pointerup', (event) => {
        dragging = false;
        pet.classList.remove('dragging');
        pet.releasePointerCapture(event.pointerId);
        savePosition();
        if (!moved) {
            speak();
        }
    });

    pet.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            speak();
        }
    });

    function speak(message, options = {}) {
        const petLines = lines[petName] || ['Ready!'];
        dialog.textContent = message || petLines[Math.floor(Math.random() * petLines.length)];
        dialog.classList.add('visible');
        playSpriteAnimation(options.animation || 'jump', options.frameMs || 80);
        clearTimeout(hideTimer);
        hideTimer = setTimeout(() => {
            dialog.classList.remove('visible');
        }, options.duration || 2600);
    }

    function speakRandom(groupName, options = {}) {
        const petLines = gameLines[groupName] || lines[petName] || ['Ready!'];
        speak(petLines[Math.floor(Math.random() * petLines.length)], options);
    }

    function predictAnswerColor(availableCount = answerColors.length, options = {}) {
        const colors = answerColors.slice(0, Math.max(1, Math.min(availableCount, answerColors.length)));
        const color = colors[Math.floor(Math.random() * colors.length)];
        speak(`Answer may be ${color}.`, options);
    }

    function setupImageFallback() {
        if (!frame || frame.tagName !== 'IMG') {
            return;
        }

        frame.addEventListener('error', () => {
            const fallback = frame.dataset.fallback || pet.dataset.petImage || '🤖';
            const fallbackNode = document.createElement('span');
            fallbackNode.id = frame.id;
            fallbackNode.textContent = fallback;
            frame.replaceWith(fallbackNode);
        }, { once: true });
    }

    function setupSpritePet() {
        const sprites = spriteSets[petName];
        if (!sprites || !frame || frame.tagName !== 'IMG') {
            return;
        }

        frame.src = sprites.default;
        preloadFrames(Object.values(sprites).flat().filter((value) => typeof value === 'string' && value.endsWith('.png')));
        ambientTimer = window.setInterval(() => {
            if (!dragging && !isAnimating) {
                playSpriteAnimation(sprites.ambientAction, sprites.frameMs);
            }
        }, sprites.ambientInterval);
    }

    function playSpriteAnimation(type, frameMs) {
        const sprites = spriteSets[petName];
        if (!sprites || !frame || frame.tagName !== 'IMG') {
            pet.classList.add('pet-bounce');
            window.setTimeout(() => pet.classList.remove('pet-bounce'), 420);
            return;
        }

        const frames = sprites[type] || [];
        if (!frames.length) {
            return;
        }

        window.clearTimeout(animationTimer);
        isAnimating = true;
        pet.classList.toggle('pet-walking', type === 'walk' || type === 'jumpmelee');
        let index = 0;

        const tick = () => {
            if (index >= frames.length) {
                frame.src = sprites.default;
                isAnimating = false;
                pet.classList.remove('pet-walking');
                return;
            }

            frame.src = frames[index];
            index += 1;
            animationTimer = window.setTimeout(tick, frameMs);
        };

        tick();
    }

    function preloadFrames(paths) {
        paths.forEach((path) => {
            const image = new Image();
            image.src = path;
        });
    }

    function savePosition() {
        const rect = pet.getBoundingClientRect();
        localStorage.setItem(storageKey, JSON.stringify({ left: rect.left, top: rect.top }));
    }

    function restorePosition() {
        try {
            const saved = JSON.parse(localStorage.getItem(storageKey));
            if (!saved) {
                return;
            }
            pet.style.left = `${clamp(saved.left, 0, window.innerWidth - pet.offsetWidth)}px`;
            pet.style.top = `${clamp(saved.top, 0, window.innerHeight - pet.offsetHeight)}px`;
            pet.style.bottom = 'auto';
        } catch (error) {
            localStorage.removeItem(storageKey);
        }
    }

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), Math.max(min, max));
    }
});
