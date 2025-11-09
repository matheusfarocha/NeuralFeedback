(() => {
    const selectedCharacteristics = new Set();
  
    // Name pools by region
    const NAME_POOLS = {
      'North America': ['Jordan Miller', 'Avery Brooks', 'Taylor Reed', 'Cameron Lee', 'Madison Cole'],
      Europe: ['Luca Rossi', 'Sofia Müller', 'Noah Dupont', 'Elena Novak', 'Marta García'],
      Asia: ['Arjun Sharma', 'Mei Lin', 'Yuki Tanaka', 'Hana Park', 'Ravi Patel'],
      Africa: ['Amina Hassan', 'Kofi Mensah', 'Lerato Dlamini', 'Zainab Okafor', 'Kwame Boateng'],
      'South America': ['Camila Silva', 'Mateo Rodríguez', 'Luisa Torres', 'Diego Almeida', 'Valentina Costa'],
      Australia: ['Jack Thompson', 'Chloe Nguyen', 'Olivia Harris', 'Mason Wright', 'Isla Cooper'],
      'Middle East': ['Omar Al-Rashid', 'Layla Haddad', 'Yusuf Karim', 'Rania Khalil', 'Ali Mansour'],
      default: ['Alex Kim', 'Sam Rivera', 'Casey Morgan', 'Riley Ahmed', 'Jamie Flores']
    };
  
    document.addEventListener('DOMContentLoaded', setupIndexPage);
  
    function setupIndexPage() {
      const reviewCountSlider = document.getElementById('reviewCount');
      const reviewCountValue = document.getElementById('reviewCountValue');
      const ageMinSlider = document.getElementById('ageMin');
      const ageMaxSlider = document.getElementById('ageMax');
      const ageMinValue = document.getElementById('ageMinValue');
      const ageMaxValue = document.getElementById('ageMaxValue');
      const generateButton = document.getElementById('generateButton');
      const closeButton = document.getElementById('feedbackCloseButton');
  
      if (reviewCountSlider && reviewCountValue) {
        reviewCountSlider.addEventListener('input', () => {
          reviewCountValue.textContent = reviewCountSlider.value;
        });
      }
  
      if (ageMinSlider && ageMaxSlider && ageMinValue && ageMaxValue) {
        const updateAgeRange = () => {
          let minVal = +ageMinSlider.value;
          let maxVal = +ageMaxSlider.value;
          if (minVal > maxVal) [minVal, maxVal] = [maxVal, minVal];
          ageMinSlider.value = minVal;
          ageMaxSlider.value = maxVal;
          ageMinValue.textContent = minVal;
          ageMaxValue.textContent = maxVal;
          const range = ageMinSlider.max - ageMinSlider.min;
          const progress = document.getElementById('ageRangeProgress');
          if (progress) {
            const minPct = ((minVal - ageMinSlider.min) / range) * 100;
            const maxPct = ((maxVal - ageMinSlider.min) / range) * 100;
            progress.style.left = `${minPct}%`;
            progress.style.width = `${maxPct - minPct}%`;
          }
        };
        ageMinSlider.addEventListener('input', updateAgeRange);
        ageMaxSlider.addEventListener('input', updateAgeRange);
        updateAgeRange();
      }
  
      generateButton?.addEventListener('click', handleSubmit);
      closeButton?.addEventListener('click', hideOverlay);
  
      document.addEventListener('keydown', e => {
        if (e.key === 'Escape') hideOverlay();
      });
    }
  
    async function handleSubmit() {
      const text = document.getElementById('textInput')?.value.trim();
      const numReviews = +document.getElementById('reviewCount')?.value || 1;
      const ageMin = +document.getElementById('ageMin')?.value || 18;
      const ageMax = +document.getElementById('ageMax')?.value || 65;
      const gender = document.getElementById('gender')?.value.trim() || '';
      const location = document.getElementById('location')?.value.trim() || '';
      const generateButton = document.getElementById('generateButton');
      const errorDiv = document.getElementById('error');
      const characteristics = Array.from(selectedCharacteristics);
  
      if (!text) return showError('Please enter a product idea first!');
      if (!characteristics.length)
        return showError('Select at least one characteristic for your personas!');
  
      clearError();
      generateButton.disabled = true;
      generateButton.textContent = 'Generating…';
  
      try {
        const res = await fetch('/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, numReviews, ageMin, ageMax, gender, location, characteristics })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Generation failed.');
        showDashboard(data);
      } catch (err) {
        console.warn('Fallback personas used:', err);
        showDashboard(buildFallbackData(text, characteristics));
      } finally {
        generateButton.disabled = false;
        generateButton.textContent = 'Generate AI Client Responses';
      }
    }
  
    function showDashboard(data) {
      const overlay = document.getElementById('feedbackOverlay');
      const cardsContainer = document.getElementById('feedbackCards');
      const summary = document.getElementById('feedbackSummary');
      const mainWrapper = document.querySelector('.page-wrapper');
      if (!overlay || !cardsContainer) return;
  
      cardsContainer.innerHTML = '';
      const reviews = data.reviews || [];
      if (reviews.length) {
        const avg10 =
          reviews.reduce((s, r) => s + (r.metadata?.sentiment_rating || 0), 0) / reviews.length;
        const avg5 = (avg10 / 2).toFixed(1);
        summary.textContent = `Generated ${reviews.length} persona responses • Avg sentiment ${avg5}/5`;
  
        reviews.forEach(r => cardsContainer.appendChild(buildPersonaCard(r)));
      } else {
        summary.textContent =
          data.fallbackMessage || 'No responses generated. Adjust inputs and retry.';
      }
  
      overlay.classList.remove('hidden');
      mainWrapper?.classList.add('hidden');
    }
  
    function hideOverlay() {
      document.getElementById('feedbackOverlay')?.classList.add('hidden');
      document.querySelector('.page-wrapper')?.classList.remove('hidden');
    }
  
    // Build each persona card
    function buildPersonaCard(r) {
      const m = r.metadata || {};
      const region = m.location || m.region || '';
      const name = m.persona_name || pickName(region);
      const initial = m.initial || name[0];
      const descriptor =
        m.persona_descriptor || m.personality_description || 'Customer Persona';
      const rating10 = m.sentiment_rating || 0;
      const stars = Math.round(rating10 / 2);
      const label = `${(rating10 / 2).toFixed(1)}/5`;
      const traits = m.characteristics || [];
  
      const el = document.createElement('article');
      el.className = 'persona-card';
      el.innerHTML = `
        <div class="persona-header">
          <div class="persona-avatar">${escapeHtml(initial)}</div>
          <div>
            <h3 class="persona-name">${escapeHtml(name)}</h3>
            <p class="persona-meta">${escapeHtml(descriptor)}</p>
          </div>
        </div>
        <div class="persona-tags">
          ${traits.map(t => `<span class="persona-tag">${escapeHtml(t)}</span>`).join('')}
        </div>
        <div class="persona-rating">
          ${[...Array(5)]
            .map(
              (_, i) => `<svg class="star-icon${i < stars ? ' star-filled' : ''}" viewBox="0 0 24 24">
                <path d="m12 3 2.4 5.8 6.1.5-4.6 4 1.4 6-5.3-3.2-5.3 3.2 1.4-6-4.6-4 6.1-.5z"/>
              </svg>`
            )
            .join('')}
          <span class="rating-value">${label}</span>
        </div>
        <p class="persona-feedback">${escapeHtml(r.review || '')}</p>
        <div class="persona-actions">
          <button class="icon-btn" disabled><span>📞</span> Call</button>
          <button class="icon-btn persona-chat-btn"><span>💬</span> Chat</button>
        </div>
      `;
      el.querySelector('.persona-chat-btn').onclick = () => {
        window.location.href = `/chat/${r.index}`;
      };
      return el;
    }
  
    function pickName(region) {
      const pool =
        NAME_POOLS[region] ||
        NAME_POOLS[
          Object.keys(NAME_POOLS).find(k => region && region.includes(k)) || 'default'
        ] ||
        NAME_POOLS.default;
      return pool[Math.floor(Math.random() * pool.length)];
    }
  
    // ---- Error + helpers ----
    function showError(msg) {
      const e = document.getElementById('error');
      if (!e) return;
      e.textContent = msg;
      e.classList.add('show');
    }
    function clearError() {
      const e = document.getElementById('error');
      if (!e) return;
      e.textContent = '';
      e.classList.remove('show');
    }
    function escapeHtml(t) {
      const d = document.createElement('div');
      d.textContent = t ?? '';
      return d.innerHTML;
    }
  
    function buildFallbackData(text, chars) {
      const personas = [
        { persona_name: 'Avery Chen', persona_descriptor: 'Strategy-focused product designer' },
        { persona_name: 'Jordan Ramirez', persona_descriptor: 'Data-driven growth specialist' },
        { persona_name: 'Morgan Patel', persona_descriptor: 'User empathy researcher' }
      ];
      const reviews = chars.map((c, i) => {
        const p = personas[i % personas.length];
        const rating = 6 + (i % 3); // 6-8/10
        return {
          index: i + 1,
          review: `As a ${c} persona, I see potential in “${text.slice(0, 60)}${
            text.length > 60 ? '…' : ''
          }”. Focus on clarifying value and next validation steps.`,
          metadata: {
            persona_name: p.persona_name,
            persona_descriptor: p.persona_descriptor,
            initial: p.persona_name[0],
            characteristics: chars,
            sentiment_rating: rating
          }
        };
      });
      return { reviews, fallbackMessage: 'Using simulated persona insights (offline mode).' };
    }
  
    // Expose globally
    window.handleSubmit = handleSubmit;
    window.toggleCharacteristic = btn => {
      const c = btn.getAttribute('data-characteristic');
      if (!c) return;
      if (selectedCharacteristics.has(c)) {
        selectedCharacteristics.delete(c);
        btn.classList.remove('selected');
      } else {
        selectedCharacteristics.add(c);
        btn.classList.add('selected');
      }
    };
  })();
  