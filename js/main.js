// ========================================
// Portfolio Website JavaScript
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initNavigation();
    initTestimonialSlider();
    initScrollAnimations();
    initSmoothScroll();
    initRotatingText();
});

// ========================================
// Mobile Navigation
// ========================================
function initNavigation() {
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.nav-menu');

    if (!navToggle || !navMenu) return;

    navToggle.addEventListener('click', function() {
        navToggle.classList.toggle('active');
        navMenu.classList.toggle('active');
        document.body.style.overflow = navMenu.classList.contains('active') ? 'hidden' : '';
    });

    // Close menu when clicking a link
    navMenu.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', function() {
            navToggle.classList.remove('active');
            navMenu.classList.remove('active');
            document.body.style.overflow = '';
        });
    });

    // Close menu when clicking outside
    document.addEventListener('click', function(e) {
        if (!navMenu.contains(e.target) && !navToggle.contains(e.target)) {
            navToggle.classList.remove('active');
            navMenu.classList.remove('active');
            document.body.style.overflow = '';
        }
    });
}

// ========================================
// Testimonial Slider
// ========================================
function initTestimonialSlider() {
    const slides = document.querySelectorAll('.testimonial-slide');
    const dots = document.querySelectorAll('.slider-dots .dot');
    const prevBtn = document.querySelector('.slider-arrow.prev');
    const nextBtn = document.querySelector('.slider-arrow.next');

    if (!slides.length) return;

    let currentSlide = 0;
    let autoSlideInterval;

    function showSlide(index) {
        // Handle wrap around
        if (index >= slides.length) index = 0;
        if (index < 0) index = slides.length - 1;

        currentSlide = index;

        // Update slides
        slides.forEach((slide, i) => {
            slide.classList.remove('active');
            if (i === index) {
                slide.classList.add('active');
            }
        });

        // Update dots
        dots.forEach((dot, i) => {
            dot.classList.remove('active');
            if (i === index) {
                dot.classList.add('active');
            }
        });
    }

    function nextSlide() {
        showSlide(currentSlide + 1);
    }

    function prevSlide() {
        showSlide(currentSlide - 1);
    }

    function startAutoSlide() {
        autoSlideInterval = setInterval(nextSlide, 4000);
    }

    function stopAutoSlide() {
        clearInterval(autoSlideInterval);
    }

    // Event listeners
    if (nextBtn) {
        nextBtn.addEventListener('click', function() {
            nextSlide();
            stopAutoSlide();
            startAutoSlide();
        });
    }

    if (prevBtn) {
        prevBtn.addEventListener('click', function() {
            prevSlide();
            stopAutoSlide();
            startAutoSlide();
        });
    }

    dots.forEach((dot, i) => {
        dot.addEventListener('click', function() {
            showSlide(i);
            stopAutoSlide();
            startAutoSlide();
        });
    });

    // Touch/swipe support
    let touchStartX = 0;
    let touchEndX = 0;
    const slider = document.querySelector('.testimonial-slider');

    if (slider) {
        slider.addEventListener('touchstart', function(e) {
            touchStartX = e.changedTouches[0].screenX;
        }, { passive: true });

        slider.addEventListener('touchend', function(e) {
            touchEndX = e.changedTouches[0].screenX;
            handleSwipe();
        }, { passive: true });
    }

    function handleSwipe() {
        const swipeThreshold = 50;
        const diff = touchStartX - touchEndX;

        if (Math.abs(diff) > swipeThreshold) {
            if (diff > 0) {
                nextSlide();
            } else {
                prevSlide();
            }
            stopAutoSlide();
            startAutoSlide();
        }
    }

    // Start auto-sliding
    startAutoSlide();
}

// ========================================
// Scroll Animations
// ========================================
function initScrollAnimations() {
    // Add scroll-animate class to elements
    const animateElements = document.querySelectorAll(
        '.project-card, .client-logo, .content-section, .timeline-item, .skill-category, .case-study-section'
    );

    animateElements.forEach(el => {
        el.classList.add('scroll-animate');
    });

    // Intersection Observer for scroll animations
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, observerOptions);

    document.querySelectorAll('.scroll-animate').forEach(el => {
        observer.observe(el);
    });

    // Parallax effect for dot pattern behind hero image
    const dotPattern = document.getElementById('dotPattern');
    if (dotPattern) {
        window.addEventListener('scroll', function() {
            const scrolled = window.pageYOffset;
            if (scrolled < window.innerHeight) {
                // Move dots slightly on scroll for parallax effect
                const translateY = scrolled * 0.15;
                const translateX = scrolled * 0.05;
                dotPattern.style.transform = `translate(${translateX}px, ${translateY}px)`;
            }
        }, { passive: true });
    }

    // Nav background on scroll - adds scrolled class for styling
    const nav = document.querySelector('.main-nav');
    if (nav) {
        window.addEventListener('scroll', function() {
            if (window.scrollY > 100) {
                nav.classList.add('scrolled');
            } else {
                nav.classList.remove('scrolled');
            }
        }, { passive: true });
    }
}

// ========================================
// Smooth Scroll
// ========================================
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;

            const target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                const navHeight = document.querySelector('.main-nav')?.offsetHeight || 0;
                const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navHeight;

                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

// ========================================
// Image Lazy Loading (Native + Fallback)
// ========================================
if ('loading' in HTMLImageElement.prototype) {
    // Native lazy loading supported
    document.querySelectorAll('img[data-src]').forEach(img => {
        img.src = img.dataset.src;
    });
} else {
    // Fallback for older browsers
    const lazyImages = document.querySelectorAll('img[data-src]');

    if (lazyImages.length) {
        const lazyLoad = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                    lazyLoad.unobserve(img);
                }
            });
        });

        lazyImages.forEach(img => lazyLoad.observe(img));
    }
}

// ========================================
// Rotating Hero Text
// ========================================
function initRotatingText() {
    const el = document.getElementById('rotating-text');
    if (!el) return;

    const words = [
        'Artificial Intelligence',
        'User Experience',
        'Design Leadership',
        'Strategy & Innovation'
    ];
    let index = 0;

    setInterval(() => {
        // Fade out
        el.classList.add('fade-out');

        setTimeout(() => {
            // Advance to next word and swap
            index = (index + 1) % words.length;
            el.textContent = words[index];
            // Fade back in
            el.classList.remove('fade-out');
        }, 300); // matches CSS transition duration
    }, 2000);
}

// ========================================
// Page Load Animation
// ========================================
window.addEventListener('load', function() {
    document.body.classList.add('loaded');

    // Animate hero elements on page load
    const heroElements = document.querySelectorAll('.hero h1, .hero-text, .social-links, .scroll-arrow');
    heroElements.forEach((el, i) => {
        el.style.animationDelay = `${i * 0.2}s`;
    });
});
