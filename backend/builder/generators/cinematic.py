"""
backend/builder/generators/cinematic.py
Generates a cinematic/showcase website with:
  - Full-screen hero with parallax
  - Smooth scroll-reveal animations (CSS-only)
  - Dramatic typography & color grading
  - Video-ready background sections
  - Immersive section transitions
"""


def generate(prefs: dict) -> dict:
    design = prefs.get("design", "cinematic")
    
    # Color palettes per design style
    palettes = {
        "cinematic": {
            "bg": "#0a0a0a", "surface": "#111111", "accent": "#e8c547",
            "text": "#f0f0f0", "muted": "#888888", "gradient": "linear-gradient(135deg, #e8c547 0%, #d4a017 100%)"
        },
        "modern": {
            "bg": "#0b0b12", "surface": "#12121a", "accent": "#00f0ff",
            "text": "#f0f0f0", "muted": "#888888", "gradient": "linear-gradient(135deg, #00f0ff 0%, #8b5cf6 100%)"
        },
        "premium": {
            "bg": "#0a0a0a", "surface": "#111111", "accent": "#c9a84c",
            "text": "#f5f5f5", "muted": "#999999", "gradient": "linear-gradient(135deg, #c9a84c 0%, #8b6914 100%)"
        },
        "minimal": {
            "bg": "#fafafa", "surface": "#ffffff", "accent": "#111111",
            "text": "#111111", "muted": "#666666", "gradient": "linear-gradient(135deg, #111111 0%, #333333 100%)"
        },
        "colorful": {
            "bg": "#0f0f1a", "surface": "#1a1a2e", "accent": "#ff6b6b",
            "text": "#f0f0f0", "muted": "#aaaaaa", "gradient": "linear-gradient(135deg, #ff6b6b 0%, #feca57 50%, #48dbfb 100%)"
        },
    }
    p = palettes.get(design, palettes["cinematic"])

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cinematic Showcase</title>
    <meta name="description" content="An immersive cinematic showcase website built with DreamAgent.">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        /* ── Reset & Base ─────────────────────────────────────── */
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        :root {{
            --bg: {p["bg"]};
            --surface: {p["surface"]};
            --accent: {p["accent"]};
            --text: {p["text"]};
            --muted: {p["muted"]};
            --gradient: {p["gradient"]};
        }}

        html {{
            scroll-behavior: smooth;
            overflow-x: hidden;
        }}

        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            overflow-x: hidden;
        }}

        /* ── Scroll Reveal Animation ─────────────────────────── */
        .reveal {{
            opacity: 0;
            transform: translateY(60px);
            transition: opacity 1s cubic-bezier(0.16, 1, 0.3, 1),
                        transform 1s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .reveal.visible {{
            opacity: 1;
            transform: translateY(0);
        }}
        .reveal-left {{
            opacity: 0;
            transform: translateX(-80px);
            transition: opacity 1s cubic-bezier(0.16, 1, 0.3, 1),
                        transform 1s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .reveal-left.visible {{
            opacity: 1;
            transform: translateX(0);
        }}
        .reveal-right {{
            opacity: 0;
            transform: translateX(80px);
            transition: opacity 1s cubic-bezier(0.16, 1, 0.3, 1),
                        transform 1s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .reveal-right.visible {{
            opacity: 1;
            transform: translateX(0);
        }}
        .reveal-scale {{
            opacity: 0;
            transform: scale(0.85);
            transition: opacity 1.2s cubic-bezier(0.16, 1, 0.3, 1),
                        transform 1.2s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .reveal-scale.visible {{
            opacity: 1;
            transform: scale(1);
        }}

        /* ── Navigation ──────────────────────────────────────── */
        nav {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 100;
            padding: 1.5rem 4rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: transparent;
            transition: background 0.5s, backdrop-filter 0.5s, padding 0.5s;
        }}
        nav.scrolled {{
            background: rgba(10, 10, 10, 0.85);
            backdrop-filter: blur(20px);
            padding: 1rem 4rem;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        .nav-logo {{
            font-family: 'Playfair Display', serif;
            font-size: 1.5rem;
            font-weight: 900;
            background: var(--gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 2px;
        }}
        .nav-links a {{
            color: var(--muted);
            text-decoration: none;
            margin-left: 2.5rem;
            font-size: 0.85rem;
            font-weight: 500;
            letter-spacing: 2px;
            text-transform: uppercase;
            transition: color 0.3s;
        }}
        .nav-links a:hover {{ color: var(--accent); }}

        /* ── Hero ─────────────────────────────────────────────── */
        .hero {{
            position: relative;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            overflow: hidden;
        }}
        .hero-bg {{
            position: absolute;
            inset: 0;
            background: 
                radial-gradient(ellipse at 20% 50%, rgba(232, 197, 71, 0.08) 0%, transparent 60%),
                radial-gradient(ellipse at 80% 20%, rgba(232, 197, 71, 0.05) 0%, transparent 50%),
                var(--bg);
            z-index: 0;
        }}
        .hero-particles {{
            position: absolute;
            inset: 0;
            z-index: 1;
            overflow: hidden;
        }}
        .particle {{
            position: absolute;
            width: 2px;
            height: 2px;
            background: var(--accent);
            border-radius: 50%;
            opacity: 0;
            animation: float-up 8s infinite;
        }}
        @keyframes float-up {{
            0% {{ opacity: 0; transform: translateY(100vh) scale(0); }}
            10% {{ opacity: 0.6; }}
            90% {{ opacity: 0.3; }}
            100% {{ opacity: 0; transform: translateY(-10vh) scale(1); }}
        }}
        .hero-content {{
            position: relative;
            z-index: 2;
            max-width: 900px;
            padding: 0 2rem;
        }}
        .hero-tag {{
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 6px;
            text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 2rem;
            opacity: 0;
            animation: fade-in 1s 0.3s forwards;
        }}
        .hero-title {{
            font-family: 'Playfair Display', serif;
            font-size: clamp(3rem, 8vw, 6.5rem);
            font-weight: 900;
            line-height: 1.05;
            margin-bottom: 1.5rem;
            opacity: 0;
            animation: slide-up 1.2s 0.5s forwards;
        }}
        .hero-title span {{
            background: var(--gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .hero-subtitle {{
            font-size: 1.15rem;
            color: var(--muted);
            max-width: 600px;
            margin: 0 auto 3rem;
            font-weight: 300;
            opacity: 0;
            animation: fade-in 1s 0.9s forwards;
        }}
        .hero-cta {{
            display: inline-flex;
            align-items: center;
            gap: 0.75rem;
            padding: 1rem 2.5rem;
            background: var(--gradient);
            color: var(--bg);
            font-weight: 600;
            font-size: 0.85rem;
            letter-spacing: 2px;
            text-transform: uppercase;
            text-decoration: none;
            border-radius: 0;
            border: none;
            cursor: pointer;
            transition: transform 0.3s, box-shadow 0.3s;
            opacity: 0;
            animation: fade-in 1s 1.2s forwards;
        }}
        .hero-cta:hover {{
            transform: translateY(-2px);
            box-shadow: 0 20px 40px rgba(232, 197, 71, 0.3);
        }}
        .scroll-indicator {{
            position: absolute;
            bottom: 3rem;
            left: 50%;
            transform: translateX(-50%);
            z-index: 2;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.5rem;
            opacity: 0;
            animation: fade-in 1s 1.5s forwards;
        }}
        .scroll-line {{
            width: 1px;
            height: 50px;
            background: var(--accent);
            animation: scroll-pulse 2s infinite;
        }}
        @keyframes scroll-pulse {{
            0%, 100% {{ opacity: 0.2; transform: scaleY(0.5); }}
            50% {{ opacity: 1; transform: scaleY(1); }}
        }}
        @keyframes fade-in {{
            to {{ opacity: 1; }}
        }}
        @keyframes slide-up {{
            from {{ opacity: 0; transform: translateY(40px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* ── Sections ────────────────────────────────────────── */
        section {{
            padding: 8rem 4rem;
            position: relative;
        }}
        .section-tag {{
            font-size: 0.7rem;
            font-weight: 600;
            letter-spacing: 5px;
            text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 1rem;
        }}
        .section-title {{
            font-family: 'Playfair Display', serif;
            font-size: clamp(2rem, 5vw, 3.5rem);
            font-weight: 700;
            margin-bottom: 1.5rem;
            line-height: 1.15;
        }}
        .section-desc {{
            color: var(--muted);
            max-width: 600px;
            font-size: 1.05rem;
            font-weight: 300;
            line-height: 1.8;
        }}

        /* ── About / Split Section ────────────────────────────── */
        .split {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6rem;
            align-items: center;
            max-width: 1400px;
            margin: 0 auto;
        }}
        .split-image {{
            width: 100%;
            aspect-ratio: 4/5;
            background: var(--surface);
            border: 1px solid rgba(255,255,255,0.05);
            position: relative;
            overflow: hidden;
        }}
        .split-image::after {{
            content: '';
            position: absolute;
            inset: 0;
            background: var(--gradient);
            opacity: 0.1;
        }}
        .split-image .placeholder-icon {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 4rem;
            opacity: 0.3;
        }}

        /* ── Features Grid ───────────────────────────────────── */
        .features-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 2rem;
            max-width: 1400px;
            margin: 4rem auto 0;
        }}
        .feature-card {{
            background: var(--surface);
            border: 1px solid rgba(255,255,255,0.05);
            padding: 3rem 2.5rem;
            position: relative;
            overflow: hidden;
            transition: transform 0.5s, border-color 0.5s;
        }}
        .feature-card:hover {{
            transform: translateY(-5px);
            border-color: rgba(232, 197, 71, 0.2);
        }}
        .feature-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--gradient);
            transform: scaleX(0);
            transform-origin: left;
            transition: transform 0.5s;
        }}
        .feature-card:hover::before {{
            transform: scaleX(1);
        }}
        .feature-icon {{
            font-size: 2rem;
            margin-bottom: 1.5rem;
        }}
        .feature-card h3 {{
            font-family: 'Playfair Display', serif;
            font-size: 1.3rem;
            margin-bottom: 1rem;
        }}
        .feature-card p {{
            color: var(--muted);
            font-size: 0.95rem;
            font-weight: 300;
            line-height: 1.7;
        }}

        /* ── Showcase / Full Width Section ────────────────────── */
        .showcase {{
            min-height: 80vh;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            background: var(--surface);
            position: relative;
        }}
        .showcase::before {{
            content: '';
            position: absolute;
            inset: 0;
            background: 
                radial-gradient(circle at 30% 50%, rgba(232, 197, 71, 0.06) 0%, transparent 50%),
                radial-gradient(circle at 70% 30%, rgba(232, 197, 71, 0.04) 0%, transparent 40%);
        }}
        .showcase-inner {{
            position: relative;
            z-index: 1;
            max-width: 800px;
            padding: 0 2rem;
        }}
        .showcase .big-number {{
            font-family: 'Playfair Display', serif;
            font-size: clamp(4rem, 12vw, 10rem);
            font-weight: 900;
            background: var(--gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 1;
            margin-bottom: 2rem;
        }}

        /* ── Testimonial ─────────────────────────────────────── */
        .testimonial {{
            max-width: 900px;
            margin: 0 auto;
            text-align: center;
        }}
        .testimonial blockquote {{
            font-family: 'Playfair Display', serif;
            font-size: clamp(1.5rem, 3vw, 2.5rem);
            font-style: italic;
            line-height: 1.5;
            margin-bottom: 2rem;
            position: relative;
        }}
        .testimonial blockquote::before {{
            content: '\\201C';
            font-size: 6rem;
            position: absolute;
            top: -2rem;
            left: -1rem;
            color: var(--accent);
            opacity: 0.3;
            font-style: normal;
        }}
        .testimonial-author {{
            color: var(--accent);
            font-weight: 600;
            font-size: 0.85rem;
            letter-spacing: 3px;
            text-transform: uppercase;
        }}

        /* ── CTA Section ─────────────────────────────────────── */
        .cta-section {{
            text-align: center;
            padding: 10rem 4rem;
        }}
        .cta-section .section-title {{
            font-size: clamp(2.5rem, 6vw, 4.5rem);
        }}

        /* ── Footer ──────────────────────────────────────────── */
        footer {{
            padding: 4rem;
            border-top: 1px solid rgba(255,255,255,0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 2rem;
        }}
        footer .footer-logo {{
            font-family: 'Playfair Display', serif;
            font-size: 1.2rem;
            font-weight: 700;
            background: var(--gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        footer .footer-links a {{
            color: var(--muted);
            text-decoration: none;
            margin-left: 2rem;
            font-size: 0.8rem;
            letter-spacing: 1px;
            transition: color 0.3s;
        }}
        footer .footer-links a:hover {{ color: var(--accent); }}

        /* ── Responsive ──────────────────────────────────────── */
        @media (max-width: 768px) {{
            nav {{ padding: 1rem 1.5rem; }}
            nav.scrolled {{ padding: 0.75rem 1.5rem; }}
            .nav-links {{ display: none; }}
            section {{ padding: 5rem 1.5rem; }}
            .split {{ grid-template-columns: 1fr; gap: 3rem; }}
            footer {{ flex-direction: column; text-align: center; padding: 3rem 1.5rem; }}
            footer .footer-links a {{ margin: 0 1rem; }}
        }}
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav id="mainNav">
        <div class="nav-logo">DREAMVISION</div>
        <div class="nav-links">
            <a href="#about">About</a>
            <a href="#features">Features</a>
            <a href="#showcase">Showcase</a>
            <a href="#contact">Contact</a>
        </div>
    </nav>

    <!-- Hero -->
    <section class="hero">
        <div class="hero-bg"></div>
        <div class="hero-particles" id="particles"></div>
        <div class="hero-content">
            <div class="hero-tag">Experience The Future</div>
            <h1 class="hero-title">Where <span>Vision</span> Meets Reality</h1>
            <p class="hero-subtitle">
                An immersive digital experience crafted with precision, 
                designed to captivate and inspire. Every pixel tells a story.
            </p>
            <a href="#about" class="hero-cta">
                Explore &darr;
            </a>
        </div>
        <div class="scroll-indicator">
            <div class="scroll-line"></div>
        </div>
    </section>

    <!-- About -->
    <section id="about">
        <div class="split">
            <div class="reveal-left">
                <div class="section-tag">Our Story</div>
                <h2 class="section-title">Crafted With Purpose</h2>
                <p class="section-desc">
                    We believe in the power of visual storytelling. Every project we undertake 
                    is an opportunity to push boundaries, challenge conventions, and create 
                    something truly unforgettable.
                </p>
                <p class="section-desc" style="margin-top: 1.5rem;">
                    Our approach blends cinematic artistry with cutting-edge technology, 
                    resulting in experiences that resonate on a deeper level.
                </p>
            </div>
            <div class="reveal-right">
                <div class="split-image">
                    <div class="placeholder-icon">🎬</div>
                </div>
            </div>
        </div>
    </section>

    <!-- Features -->
    <section id="features" style="background: var(--surface);">
        <div style="text-align: center;" class="reveal">
            <div class="section-tag">What We Offer</div>
            <h2 class="section-title">Unmatched Capabilities</h2>
        </div>
        <div class="features-grid">
            <div class="feature-card reveal" style="transition-delay: 0.1s;">
                <div class="feature-icon">🎥</div>
                <h3>Cinematic Design</h3>
                <p>Full-screen visuals with parallax depth, dramatic reveals, and theatrical pacing that captivates visitors.</p>
            </div>
            <div class="feature-card reveal" style="transition-delay: 0.2s;">
                <div class="feature-icon">⚡</div>
                <h3>Lightning Fast</h3>
                <p>Optimized for performance with no framework overhead. Pure CSS animations ensure buttery smooth 60fps.</p>
            </div>
            <div class="feature-card reveal" style="transition-delay: 0.3s;">
                <div class="feature-icon">📱</div>
                <h3>Fully Responsive</h3>
                <p>Every element adapts fluidly across devices. Desktop grandeur meets mobile elegance seamlessly.</p>
            </div>
            <div class="feature-card reveal" style="transition-delay: 0.4s;">
                <div class="feature-icon">🎨</div>
                <h3>Bold Typography</h3>
                <p>Carefully curated font pairings create visual hierarchy that guides the eye and enhances readability.</p>
            </div>
            <div class="feature-card reveal" style="transition-delay: 0.5s;">
                <div class="feature-icon">✨</div>
                <h3>Micro Interactions</h3>
                <p>Subtle hover effects, scroll reveals, and transitions add life and delight to every interaction.</p>
            </div>
            <div class="feature-card reveal" style="transition-delay: 0.6s;">
                <div class="feature-icon">🔒</div>
                <h3>Production Ready</h3>
                <p>Clean semantic HTML, accessible markup, and optimized assets. Ready to deploy from day one.</p>
            </div>
        </div>
    </section>

    <!-- Showcase -->
    <section id="showcase" class="showcase">
        <div class="showcase-inner reveal-scale">
            <div class="big-number">∞</div>
            <h2 class="section-title">Limitless Possibilities</h2>
            <p class="section-desc" style="margin: 1.5rem auto 0; text-align: center;">
                From brand showcases to product launches, our cinematic approach 
                transforms ordinary presentations into extraordinary experiences.
            </p>
        </div>
    </section>

    <!-- Testimonial -->
    <section>
        <div class="testimonial reveal">
            <blockquote>
                This isn't just a website — it's an experience. 
                The attention to detail and cinematic quality is 
                unlike anything we've seen before.
            </blockquote>
            <div class="testimonial-author">— Creative Director, Studio X</div>
        </div>
    </section>

    <!-- CTA -->
    <section id="contact" class="cta-section">
        <div class="reveal">
            <div class="section-tag">Ready?</div>
            <h2 class="section-title">Let's Create Something <br>Extraordinary</h2>
            <a href="#" class="hero-cta" style="margin-top: 2rem; display: inline-flex;">
                Get Started →
            </a>
        </div>
    </section>

    <!-- Footer -->
    <footer>
        <div class="footer-logo">DREAMVISION</div>
        <div class="footer-links">
            <a href="#about">About</a>
            <a href="#features">Features</a>
            <a href="#showcase">Showcase</a>
            <a href="#contact">Contact</a>
        </div>
    </footer>

    <script>
        // ── Scroll Reveal ──────────────────────────────────────
        const revealElements = document.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale');
        const revealObserver = new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting) {{
                    entry.target.classList.add('visible');
                    revealObserver.unobserve(entry.target);
                }}
            }});
        }}, {{ threshold: 0.15, rootMargin: '0px 0px -50px 0px' }});
        revealElements.forEach(el => revealObserver.observe(el));

        // ── Nav scroll effect ──────────────────────────────────
        const nav = document.getElementById('mainNav');
        window.addEventListener('scroll', () => {{
            nav.classList.toggle('scrolled', window.scrollY > 80);
        }});

        // ── Particles ──────────────────────────────────────────
        const particleContainer = document.getElementById('particles');
        for (let i = 0; i < 30; i++) {{
            const p = document.createElement('div');
            p.className = 'particle';
            p.style.left = Math.random() * 100 + '%';
            p.style.animationDelay = Math.random() * 8 + 's';
            p.style.animationDuration = (6 + Math.random() * 6) + 's';
            p.style.width = p.style.height = (1 + Math.random() * 2) + 'px';
            particleContainer.appendChild(p);
        }}

        // ── Parallax on hero ───────────────────────────────────
        const heroContent = document.querySelector('.hero-content');
        window.addEventListener('scroll', () => {{
            const scrolled = window.scrollY;
            if (scrolled < window.innerHeight) {{
                heroContent.style.transform = `translateY(${{scrolled * 0.3}}px)`;
                heroContent.style.opacity = 1 - (scrolled / window.innerHeight);
            }}
        }});
    </script>
</body>
</html>'''
    
    files = {
        "index.html": html,
    }
    
    return files
