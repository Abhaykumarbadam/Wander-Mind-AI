(function() {
  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      const el = entry.target;
      if (entry.isIntersecting) {
        el.classList.add('in-view');
        const icon = el.querySelector('.about-icon');
        if (icon) icon.style.transform = 'translateY(-6px) scale(1.02)';
      } else {
        el.classList.remove('in-view');
        const icon = el.querySelector('.about-icon');
        if (icon) icon.style.transform = 'none';
      }
    });
  }, { threshold: 0.15 });

  document.querySelectorAll('.animate-in').forEach(n => io.observe(n));
  document.querySelectorAll('.about-card').forEach(n => io.observe(n));
})();
