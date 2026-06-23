/* ============================================================
   liquid-metal.js - 液态银流体粒子特效引擎
   Liquid Silver Fluid Particle Animation System
   ============================================================ */

const LiquidMetal = (() => {
  let canvas, ctx;
  let particles = [];
  let mouse = { x: -1000, y: -1000, vx: 0, vy: 0, prevX: -1000, prevY: -1000 };
  let scrollOffset = 0;
  let targetScroll = 0;
  let animationId = null;
  let isRunning = false;

  // Configuration
  const CONFIG = {
    // Particle count adapts to screen size
    get particleCount() {
      const w = window.innerWidth;
      if (w < 640) return 50;       // Mobile
      if (w < 1024) return 80;      // Tablet
      return 120;                    // Desktop
    },
    particleMinSize: 1.5,
    particleMaxSize: 4.5,
    flowSpeed: 0.3,
    mouseInfluence: 120,
    mouseRepel: 80,
    connectionDistance: 140,
    connectionOpacity: 0.12,
    // Liquid silver palette
    colors: [
      'rgba(192, 198, 210, OPACITY)',
      'rgba(168, 174, 188, OPACITY)',
      'rgba(212, 216, 226, OPACITY)',
      'rgba(150, 158, 172, OPACITY)',
      'rgba(180, 186, 198, OPACITY)',
    ],
    // Burst animation
    burstParticles: 30,
    burstLifetime: 60,
  };

  class Particle {
    constructor(x, y, isBurst = false) {
      this.reset(x, y, isBurst);
    }

    reset(x, y, isBurst = false) {
      this.x = x ?? Math.random() * canvas.width;
      this.y = y ?? Math.random() * canvas.height;
      this.size = CONFIG.particleMinSize + Math.random() * (CONFIG.particleMaxSize - CONFIG.particleMinSize);
      this.baseSize = this.size;
      this.speedX = (Math.random() - 0.5) * 0.4;
      this.speedY = (Math.random() - 0.5) * 0.4 + CONFIG.flowSpeed * 0.3;
      this.colorIndex = Math.floor(Math.random() * CONFIG.colors.length);
      this.opacity = 0.15 + Math.random() * 0.35;
      this.phase = Math.random() * Math.PI * 2;
      this.flowAngle = Math.random() * Math.PI * 2;
      this.isBurst = isBurst;
      this.life = isBurst ? CONFIG.burstLifetime : Infinity;
      this.maxLife = this.life;
    }

    update(mx, my, mvx, mvy) {
      // Flow movement (slow drift)
      this.flowAngle += (Math.random() - 0.5) * 0.02;
      this.x += Math.cos(this.flowAngle) * 0.15 + this.speedX;
      this.y += Math.sin(this.flowAngle) * 0.15 + this.speedY - CONFIG.flowSpeed * 0.15;

      // Scroll influence
      const scrollDelta = targetScroll - scrollOffset;
      this.y += scrollDelta * 0.003;

      // Mouse interaction
      const dx = this.x - mx;
      const dy = this.y - my;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < CONFIG.mouseInfluence) {
        const force = (CONFIG.mouseInfluence - dist) / CONFIG.mouseInfluence;

        // Attract/repel based on distance zone
        if (dist < CONFIG.mouseRepel) {
          // Repel: push away from cursor
          const repelForce = (CONFIG.mouseRepel - dist) / CONFIG.mouseRepel * 2;
          const angle = Math.atan2(dy, dx);
          this.x += Math.cos(angle) * repelForce * 3;
          this.y += Math.sin(angle) * repelForce * 3;
        } else {
          // Attract: gently pull toward cursor
          this.x -= dx * force * 0.02;
          this.y -= dy * force * 0.02;
        }

        // Add mouse velocity influence
        this.x += mvx * force * 0.03;
        this.y += mvy * force * 0.03;

        // Glow near mouse
        this.size = this.baseSize * (1 + force * 1.5);
        this.opacity = Math.min(0.7, this.opacity + force * 0.3);
      } else {
        // Return to base
        this.size += (this.baseSize - this.size) * 0.05;
      }

      // Burst particles fade
      if (this.isBurst) {
        this.life--;
        this.opacity = (this.life / this.maxLife) * 0.6;
        this.speedX *= 0.96;
        this.speedY *= 0.96;
      }

      // Boundary wrap with smooth transition
      const margin = 40;
      if (this.x < -margin) this.x = canvas.width + margin;
      if (this.x > canvas.width + margin) this.x = -margin;
      if (this.y < -margin) this.y = canvas.height + margin;
      if (this.y > canvas.height + margin) this.y = -margin;
    }

    draw(ctx) {
      if (this.isBurst && this.life <= 0) return;

      const color = CONFIG.colors[this.colorIndex].replace('OPACITY', this.opacity.toFixed(2));

      // Main particle with glow
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);

      // Radial gradient for liquid metal look
      const gradient = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, this.size * 2.5);
      gradient.addColorStop(0, color);
      gradient.addColorStop(0.4, color.replace(/[\d.]+\)$/, (this.opacity * 0.6).toFixed(2) + ')'));
      gradient.addColorStop(1, 'rgba(192, 198, 210, 0)');

      ctx.fillStyle = gradient;
      ctx.fill();

      // Specular highlight
      ctx.beginPath();
      ctx.arc(this.x - this.size * 0.25, this.y - this.size * 0.25, this.size * 0.35, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255, 255, 255, ${this.opacity * 0.5})`;
      ctx.fill();
    }
  }

  function init() {
    // Prevent double initialization
    if (isRunning) return;

    canvas = document.getElementById('particle-canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'particle-canvas';
      document.body.prepend(canvas);
    }

    ctx = canvas.getContext('2d');
    resize();
    createParticles();

    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('scroll', onScroll);
    window.addEventListener('click', onBurst);

    // Hover burst on cards and buttons
    document.addEventListener('mouseover', (e) => {
      const target = e.target.closest('.card, .btn, .device-mockup, .questionnaire-card, .model-option');
      if (target) {
        const rect = target.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        burstAt(cx, cy, 12);
      }
    });

    isRunning = true;
    animate();
  }

  function resize() {
    if (!canvas) return;
    canvas.width = window.innerWidth;
    canvas.height = document.documentElement.scrollHeight;
  }

  function createParticles() {
    particles = [];
    for (let i = 0; i < CONFIG.particleCount; i++) {
      particles.push(new Particle());
    }
  }

  function onMouseMove(e) {
    mouse.prevX = mouse.x;
    mouse.prevY = mouse.y;
    mouse.x = e.clientX;
    mouse.y = e.clientY;
    mouse.vx = mouse.x - mouse.prevX;
    mouse.vy = mouse.y - mouse.prevY;
  }

  function onScroll() {
    targetScroll = window.scrollY;
  }

  function burstAt(x, y, count = CONFIG.burstParticles) {
    for (let i = 0; i < count; i++) {
      const angle = (Math.PI * 2 * i) / count + Math.random() * 0.3;
      const speed = 1.5 + Math.random() * 4;
      const p = new Particle(x, y, true);
      p.speedX = Math.cos(angle) * speed;
      p.speedY = Math.sin(angle) * speed;
      p.size = 1 + Math.random() * 3;
      particles.push(p);
    }
  }

  function onBurst(e) {
    // Small burst on click
    burstAt(e.clientX, e.clientY, 8);
  }

  function animate() {
    if (!isRunning) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Smooth scroll interpolation
    scrollOffset += (targetScroll - scrollOffset) * 0.08;

    // Update and draw particles
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.update(mouse.x, mouse.y, mouse.vx, mouse.vy);
      p.draw(ctx);

      // Remove dead burst particles
      if (p.isBurst && p.life <= 0) {
        particles.splice(i, 1);
      }
    }

    // Draw connections between nearby particles
    drawConnections();

    // Maintain particle count
    while (particles.length < CONFIG.particleCount) {
      particles.push(new Particle());
    }
    // Cap particles
    while (particles.length > CONFIG.particleCount + 60) {
      particles.shift();
    }

    // Decay mouse velocity
    mouse.vx *= 0.9;
    mouse.vy *= 0.9;

    animationId = requestAnimationFrame(animate);
  }

  function drawConnections() {
    const maxDist = CONFIG.connectionDistance;
    const maxDistSq = maxDist * maxDist;

    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const a = particles[i];
        const b = particles[j];
        if (a.isBurst || b.isBurst) continue;

        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const distSq = dx * dx + dy * dy;

        if (distSq < maxDistSq) {
          const dist = Math.sqrt(distSq);
          const opacity = (1 - dist / maxDist) * CONFIG.connectionOpacity;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.strokeStyle = `rgba(180, 186, 200, ${opacity.toFixed(3)})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
  }

  function stop() {
    isRunning = false;
    if (animationId) {
      cancelAnimationFrame(animationId);
      animationId = null;
    }
  }

  // Public burst API
  function triggerBurst(x, y, count) {
    burstAt(x, y, count);
  }

  // Reset and reinitialize
  function refresh() {
    stop();
    createParticles();
    isRunning = true;
    animate();
  }

  return {
    init,
    stop,
    refresh,
    triggerBurst,
    resize,
  };
})();

// Auto-initialize
if (typeof window !== 'undefined') {
  window.LiquidMetal = LiquidMetal;
}
