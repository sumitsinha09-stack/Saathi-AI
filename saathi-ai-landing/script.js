/**
 * Saathi AI — Landing Page Interactive Scripts
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Mobile Menu Toggle
  const mobileToggle = document.getElementById('mobile-toggle');
  const navLinks = document.getElementById('nav-links');

  if (mobileToggle && navLinks) {
    mobileToggle.addEventListener('click', () => {
      navLinks.classList.toggle('active');
    });

    // Close menu when clicking a link
    navLinks.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        navLinks.classList.remove('active');
      });
    });
  }

  // 2. FAQ Accordion Interaction
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const questionBtn = item.querySelector('.faq-question');
    if (questionBtn) {
      questionBtn.addEventListener('click', () => {
        const isActive = item.classList.contains('active');
        
        // Close all other items
        faqItems.forEach(otherItem => {
          otherItem.classList.remove('active');
          const btn = otherItem.querySelector('.faq-question');
          if (btn) btn.setAttribute('aria-expanded', 'false');
        });

        // Toggle current item
        if (!isActive) {
          item.classList.add('active');
          questionBtn.setAttribute('aria-expanded', 'true');
        }
      });
    }
  });

  // Open first FAQ by default
  if (faqItems.length > 0) {
    faqItems[0].classList.add('active');
    const firstBtn = faqItems[0].querySelector('.faq-question');
    if (firstBtn) firstBtn.setAttribute('aria-expanded', 'true');
  }

  // 3. Interactive Mockup Buttons in Hero Section
  const chatButtons = document.querySelectorAll('.chat-btn');
  const chatMessages = document.getElementById('chat-messages');

  chatButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const text = e.target.textContent;
      
      // Visual feedback
      chatButtons.forEach(b => b.style.opacity = '0.5');
      e.target.style.opacity = '1';
      e.target.style.fontWeight = '800';

      // Append temporary user response bubble
      const userBubble = document.createElement('div');
      userBubble.className = 'wa-bubble wa-outgoing';
      userBubble.style.marginTop = '6px';
      userBubble.innerHTML = `
        <p>${text}</p>
        <div class="wa-time">Just now <span class="blue-ticks">✓✓</span></div>
      `;
      chatMessages.appendChild(userBubble);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    });
  });

  // 4. Navbar Shadow on Scroll
  const navbar = document.getElementById('navbar');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 20) {
      navbar.style.boxShadow = '0 4px 20px rgba(11, 20, 26, 0.08)';
    } else {
      navbar.style.boxShadow = 'none';
    }
  });
});
