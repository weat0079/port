// Theme toggler
const themeToggle = document.getElementById('theme-toggle');
const html = document.documentElement;

themeToggle.addEventListener('click', () => {
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', newTheme);
    
    // Update icon
    const icon = themeToggle.querySelector('i');
    icon.className = newTheme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
});

// Scroll reveal
const reveals = document.querySelectorAll('.reveal');

function revealOnScroll() {
    reveals.forEach(element => {
        const elementTop = element.getBoundingClientRect().top;
        const windowHeight = window.innerHeight;
        
        if (elementTop < windowHeight - 100) {
            element.classList.add('active');
        }
    });
}

window.addEventListener('scroll', revealOnScroll);
revealOnScroll(); // Initial check 

// Custom cursor
document.addEventListener('mousemove', (e) => {
    const cursor = document.querySelector('.cursor');
    const follower = document.querySelector('.cursor-follower');
    
    cursor.style.left = e.clientX + 'px';
    cursor.style.top = e.clientY + 'px';
    
    follower.style.left = e.clientX + 'px';
    follower.style.top = e.clientY + 'px';
});

// Counter animation
const counters = document.querySelectorAll('.counter');
const speed = 200;

const animateCounter = (counter) => {
    const target = +counter.getAttribute('data-target');
    let count = 0;
    
    const updateCount = () => {
        const increment = target / speed;
        
        if(count < target) {
            count += increment;
            counter.innerText = Math.ceil(count);
            setTimeout(updateCount, 1);
        } else {
            counter.innerText = target;
        }
    };
    
    updateCount();
};

// Intersection Observer for counters
const observerOptions = {
    threshold: 0.5
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if(entry.isIntersecting) {
            const counter = entry.target;
            animateCounter(counter);
            observer.unobserve(counter);
        }
    });
}, observerOptions);

counters.forEach(counter => observer.observe(counter));

// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelector(this.getAttribute('href')).scrollIntoView({
            behavior: 'smooth'
        });
    });
});

// Parallax scrolling effect
const parallaxElements = document.querySelectorAll('.parallax-text');
const floatingShapes = document.querySelectorAll('.floating-shape');
const scrollProgress = document.querySelector('.scroll-progress');

// Parallax scroll handler
function handleParallax() {
    const scrolled = window.pageYOffset;
    
    parallaxElements.forEach(element => {
        const speed = element.dataset.speed || 0.5;
        const yPos = -(scrolled * speed);
        element.style.setProperty('--parallax-y', `${yPos}px`);
    });

    // Update scroll progress bar
    const height = document.documentElement.scrollHeight - window.innerHeight;
    const progress = (scrolled / height) * 100;
    scrollProgress.style.transform = `scaleX(${progress / 100})`;
    
    // Animate floating shapes
    floatingShapes.forEach((shape, index) => {
        const speed = index % 2 === 0 ? 0.3 : -0.3;
        shape.style.transform = `translate3d(0, ${scrolled * speed}px, 0) rotate(${scrolled * 0.1}deg)`;
    });
}

// Smooth parallax scrolling
let ticking = false;
window.addEventListener('scroll', () => {
    if (!ticking) {
        window.requestAnimationFrame(() => {
            handleParallax();
            ticking = false;
        });
        ticking = true;
    }
});

// Initialize parallax
handleParallax();

// Add smooth hover effect for cursor on interactive elements
document.querySelectorAll('a, button, .service-card').forEach(element => {
    element.addEventListener('mouseenter', () => {
        document.querySelector('.cursor-follower').style.transform = 'scale(1.5)';
    });
    
    element.addEventListener('mouseleave', () => {
        document.querySelector('.cursor-follower').style.transform = 'scale(1)';
    });
});

// Navbar scroll effect
window.addEventListener('scroll', () => {
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 50) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
});

// Mobile menu toggle
const menuToggle = document.querySelector('.menu-toggle');
const navLinks = document.querySelector('.nav-links');

menuToggle.addEventListener('click', () => {
    menuToggle.classList.toggle('active');
    navLinks.classList.toggle('active');
});