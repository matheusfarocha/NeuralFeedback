(() => {
  const selectedCharacteristics = new Set();

  const NAME_POOLS = {
    "North America": ["Jordan Miller", "Avery Brooks", "Taylor Reed", "Cameron Lee", "Madison Cole"],
    "South America": ["Camila Silva", "Mateo Rodríguez", "Luisa Torres", "Diego Almeida", "Valentina Costa"],
    Europe: ["Luca Rossi", "Sofia Müller", "Noah Dupont", "Elena Novak", "Marta García"],
    Asia: ["Arjun Sharma", "Mei Lin", "Yuki Tanaka", "Hana Park", "Ravi Patel"],
    Africa: ["Amina Hassan", "Kofi Mensah", "Lerato Dlamini", "Zainab Okafor", "Kwame Boateng"],
    Australia: ["Jack Thompson", "Chloe Nguyen", "Olivia Harris", "Mason Wright", "Isla Cooper"],
    "Middle East": ["Omar Al-Rashid", "Layla Haddad", "Yusuf Karim", "Rania Khalil", "Ali Mansour"],
    default: ["Alex Kim", "Sam Rivera", "Casey Morgan", "Riley Ahmed", "Jamie Flores"],
  };

  document.addEventListener("DOMContentLoaded", () => {
    setupIndexPage();
    setupChatPage();
  });

  function setupIndexPage() {
    const reviewCountSlider = document.getElementById("reviewCount");
    const reviewCountValue = document.getElementById("reviewCountValue");
    const ageMinSlider = document.getElementById("ageMin");
    const ageMaxSlider = document.getElementById("ageMax");
    const ageMinValue = document.getElementById("ageMinValue");
    const ageMaxValue = document.getElementById("ageMaxValue");
    const generateButton = document.getElementById("generateButton");
    const closeButton = document.getElementById("feedbackCloseButton");
    const ideaFileInput = document.getElementById("ideaFile");
    const attachmentDisplay = document.getElementById("attachmentDisplay");
    const attachmentName = document.getElementById("attachmentName");

    // Handle file selection
    if (ideaFileInput && attachmentDisplay && attachmentName) {
      ideaFileInput.addEventListener("change", (event) => {
        const file = event.target.files[0];
        if (file) {
          attachmentName.textContent = file.name;
          attachmentDisplay.classList.remove("hidden");
        } else {
          attachmentDisplay.classList.add("hidden");
        }
      });
    }

    if (reviewCountSlider && reviewCountValue) {
      reviewCountValue.textContent = reviewCountSlider.value;
      reviewCountSlider.addEventListener("input", () => {
        reviewCountValue.textContent = reviewCountSlider.value;




























      });
    }

    if (ageMinSlider && ageMaxSlider && ageMinValue && ageMaxValue) {
      const updateAgeRange = () => {
        let minVal = Number(ageMinSlider.value);
        let maxVal = Number(ageMaxSlider.value);

        if (minVal > maxVal) {
          [minVal, maxVal] = [maxVal, minVal];
        }

        ageMinSlider.value = minVal;
        ageMaxSlider.value = maxVal;
        ageMinValue.textContent = String(minVal);
        ageMaxValue.textContent = String(maxVal);

        const range = Number(ageMinSlider.max) - Number(ageMinSlider.min);
        const progress = document.getElementById("ageRangeProgress");
        if (progress && range > 0) {
          const minPercent = ((minVal - Number(ageMinSlider.min)) / range) * 100;
          const maxPercent = ((maxVal - Number(ageMinSlider.min)) / range) * 100;
          progress.style.left = `${minPercent}%`;
          progress.style.width = `${Math.max(0, maxPercent - minPercent)}%`;
        }

























































































      };

      ageMinSlider.addEventListener("input", updateAgeRange);
      ageMaxSlider.addEventListener("input", updateAgeRange);
      updateAgeRange();
    }

    generateButton?.addEventListener("click", handleSubmit);
    closeButton?.addEventListener("click", hideOverlay);

    document.addEventListener("keydown", event => {
      if (event.key === "Escape") hideOverlay();
    });
  }

  async function handleSubmit() {
    const text = document.getElementById("textInput")?.value.trim();
    const numReviews = Number(document.getElementById("reviewCount")?.value || 1);
    const ageMin = Number(document.getElementById("ageMin")?.value || 18);
    const ageMax = Number(document.getElementById("ageMax")?.value || 65);
    const gender = document.getElementById("gender")?.value.trim() || "";
    const location = document.getElementById("location")?.value.trim() || "";
    const generateButton = document.getElementById("generateButton");
    const characteristics = Array.from(selectedCharacteristics);
    const ideaFileInput = document.getElementById("ideaFile");

    if (!text) {
      showError("Please enter a product idea first!");
      return;
    }
    if (!characteristics.length) {
      showError("Please select at least one characteristic for your personas!");
      return;
    }

    clearError();
    if (generateButton) {
      generateButton.disabled = true;
      generateButton.textContent = "Generating…";
    }

    try {
      // Check if a file is attached
      const file = ideaFileInput?.files[0];
      
      let res;
      if (file) {
        // Use FormData if file is attached
        const formData = new FormData();
        formData.append("text", text);
        formData.append("numReviews", numReviews.toString());
        formData.append("ageMin", ageMin.toString());
        formData.append("ageMax", ageMax.toString());
        formData.append("gender", gender);
        formData.append("location", location);
        characteristics.forEach(char => {
          formData.append("characteristics", char);
        });
        formData.append("ideaFile", file);

        res = await fetch("/generate", {
          method: "POST",
          credentials: "same-origin",
          body: formData,
        });
      } else {
        // Use JSON if no file (backward compatibility)
        res = await fetch("/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ text, numReviews, ageMin, ageMax, gender, location, characteristics }),
        });
      }

      const data = await res.json();
      if (!res.ok) {
        console.warn("Generation failed, using fallback:", data);
        showDashboard(data);
        return;
      }
      showDashboard(data);
    } catch (err) {
      console.warn("Fetch error, using fallback personas:", err);
      showDashboard(buildFallbackData(text, characteristics, numReviews));
    } finally {
      if (generateButton) {
        generateButton.disabled = false;
        generateButton.textContent = "Generate AI Client Responses";
      }
    }
  }

  function showDashboard(data) {
    const overlay = document.getElementById("feedbackOverlay");
    const cardsContainer = document.getElementById("feedbackCards");
    const summary = document.getElementById("feedbackSummary");
    const summarySection = document.getElementById("feedbackSummarySection");
    const mainWrapper = document.querySelector(".page-wrapper");
    if (!overlay || !cardsContainer || !summary) return;

    cardsContainer.innerHTML = "";
    const reviews = Array.isArray(data.reviews) && data.reviews.length ? data.reviews : data.fallback || [];

    if (reviews.length) {
      const avg10 = reviews.reduce((sum, review) => sum + (review.metadata?.sentiment_rating || 0), 0) / reviews.length;
      const avg5 = (avg10 / 2).toFixed(1);
      summary.textContent = `Generated ${reviews.length} persona responses · Avg sentiment ${avg5}/5`;

      const usedNames = new Set();
      reviews.forEach(review => {
        const meta = review.metadata || {};
        if (!meta.persona_name) {
          meta.persona_name = pickName(meta.location || "");
        }
        if (usedNames.has(meta.persona_name)) {
          let counter = 2;
          let candidate = `${meta.persona_name} ${counter}`;
          while (usedNames.has(candidate)) {
            counter += 1;
            candidate = `${meta.persona_name} ${counter}`;
          }
          meta.persona_name = candidate;
        }
        usedNames.add(meta.persona_name);
        cardsContainer.appendChild(buildPersonaCard(review));
      });

      // Build and show summary section
      if (summarySection) {
        const glows = data.glows || [];
        const grows = data.grows || [];
        buildSummarySection(summarySection, reviews, avg10, glows, grows);
        summarySection.classList.remove("hidden");
      }
    } else {
      summary.textContent = data.message || data.fallbackMessage || "No responses generated. Adjust inputs and retry.";
      if (summarySection) {
        summarySection.classList.add("hidden");
      }
    }

    overlay.classList.remove("hidden");
    mainWrapper?.classList.add("hidden");
  }

  function buildSummarySection(container, reviews, avgRating10, glows = [], grows = []) {
    const avgRating5 = (avgRating10 / 2).toFixed(1);
    const filledStars = Math.round(avgRating10 / 2);
    const hasHalfStar = (avgRating10 / 2) % 1 >= 0.5 && filledStars < 5;
    const gradientId = `halfGradient-${Date.now()}`;

    const starsHtml = Array.from({ length: 5 }).map((_, i) => {
      if (i < filledStars) {
        return `<svg class="summary-star summary-star-filled" viewBox="0 0 24 24">
          <path d="m12 3 2.4 5.8 6.1.5-4.6 4 1.4 6-5.3-3.2-5.3 3.2 1.4-6-4.6-4 6.1-.5z"/>
        </svg>`;
      } else if (i === filledStars && hasHalfStar) {
        return `<svg class="summary-star summary-star-half" viewBox="0 0 24 24">
          <path d="m12 3 2.4 5.8 6.1.5-4.6 4 1.4 6-5.3-3.2-5.3 3.2 1.4-6-4.6-4 6.1-.5z" fill="url(#${gradientId})"/>
        </svg>`;
      } else {
        return `<svg class="summary-star" viewBox="0 0 24 24">
          <path d="m12 3 2.4 5.8 6.1.5-4.6 4 1.4 6-5.3-3.2-5.3 3.2 1.4-6-4.6-4 6.1-.5z"/>
        </svg>`;
      }
    }).join("");

    // Use provided glows/grows or fallback to placeholder text
    const glowsList = glows.length > 0 
      ? glows.map(glow => `<li>${escapeHtml(glow)}</li>`).join("")
      : `<li>Strong value proposition that addresses a clear market need</li>
         <li>Innovative approach to solving the problem</li>
         <li>Well-defined target audience and use cases</li>
         <li>Potential for scalability and growth</li>`;

    const growsList = grows.length > 0
      ? grows.map(grow => `<li>${escapeHtml(grow)}</li>`).join("")
      : `<li>Consider refining the user experience and onboarding flow</li>
         <li>Clarify the monetization strategy and pricing model</li>
         <li>Address potential technical challenges and scalability concerns</li>
         <li>Develop a more comprehensive go-to-market strategy</li>`;

    container.innerHTML = `
      <svg style="position: absolute; width: 0; height: 0;">
        <defs>
          <linearGradient id="${gradientId}">
            <stop offset="50%" stop-color="#facc15"/>
            <stop offset="50%" stop-color="rgba(55, 65, 81, 0.7)"/>
          </linearGradient>
        </defs>
      </svg>
      <div class="summary-header">
        <h3 class="summary-title">Overall Feedback Summary</h3>
        <div class="summary-rating-display">
          <div class="summary-stars">
            ${starsHtml}
          </div>
          <div class="summary-rating-value">${avgRating5}/5</div>
        </div>
      </div>
      <div class="summary-content">
        <div class="summary-column summary-glows">
          <div class="summary-column-header">
            <div class="summary-icon summary-icon-glow">✨</div>
            <h4 class="summary-column-title">Glows</h4>
          </div>
          <div class="summary-column-content">
            <ul class="summary-list">
              ${glowsList}
            </ul>
          </div>
        </div>
        <div class="summary-column summary-grows">
          <div class="summary-column-header">
            <div class="summary-icon summary-icon-grow">🌱</div>
            <h4 class="summary-column-title">Grows</h4>
          </div>
          <div class="summary-column-content">
            <ul class="summary-list">
              ${growsList}
            </ul>
          </div>
        </div>
      </div>
    `;
  }

  function hideOverlay() {
    document.getElementById("feedbackOverlay")?.classList.add("hidden");
    document.querySelector(".page-wrapper")?.classList.remove("hidden");
  }

  function buildPersonaCard(review) {
    const metadata = review.metadata || {};
    const personaId = review.id ?? review.index ?? 0;
    const name = metadata.persona_name || pickName(metadata.location || "");
    const descriptor = metadata.persona_descriptor || metadata.personality_description || "Customer Persona";
    const rating10 = metadata.sentiment_rating || 0;
    const ratingLabel = (rating10 / 2).toFixed(1);
    const traits = metadata.characteristics || [];

    const el = document.createElement("article");
    el.className = "persona-card";
    el.innerHTML = `
      <div class="persona-header">
        <div class="persona-avatar">${escapeHtml(name.charAt(0))}</div>
        <div>
          <h3 class="persona-name">${escapeHtml(name)}</h3>
          <p class="persona-meta">${escapeHtml(descriptor)}</p>
        </div>
      </div>
      <div class="persona-tags">
        ${traits.map(trait => `<span class="persona-tag">${escapeHtml(trait)}</span>`).join("")}
      </div>
      <div class="persona-rating">
        ${Array.from({ length: 5 }).map((_, i) => {
          const filled = i < Math.round(rating10 / 2);
          return `
            <svg class="star-icon${filled ? " star-filled" : ""}" viewBox="0 0 24 24">
              <path d="m12 3 2.4 5.8 6.1.5-4.6 4 1.4 6-5.3-3.2-5.3 3.2 1.4-6-4.6-4 6.1-.5z"/>
            </svg>
          `;
        }).join("")}
        <span class="rating-value">${ratingLabel}/5</span>
      </div>
      <p class="persona-feedback">${escapeHtml(review.review || "")}</p>
      <div class="persona-actions">
        <button class="feedback-card-btn btn-secondary-outline" type="button">
          <span>📞</span> Start Call
        </button>
        <a class="feedback-card-btn" href="/chat/${personaId}">
          <span>💬</span> Open Chat
        </a>
      </div>
    `;

    el.querySelector(".btn-secondary-outline")?.addEventListener("click", () => startCall(name));
    return el;
  }

  function pickName(region) {
    const fallback = NAME_POOLS.default;
    const normalizedRegion = region || "";
    const directPool = NAME_POOLS[normalizedRegion];
    if (directPool) {
      return directPool[Math.floor(Math.random() * directPool.length)];
    }
    const partialKey = Object.keys(NAME_POOLS).find(key => key !== "default" && normalizedRegion.includes(key));
    const pool = partialKey ? NAME_POOLS[partialKey] : fallback;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  function setupChatPage() {
    const chatWindow = document.getElementById("chatWindow");
    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const personaId = document.body?.dataset.personaId;
    const personaName = document.body?.dataset.personaName;

    if (!chatWindow || !chatForm || !chatInput || !personaId || !personaName) return;

    chatForm.addEventListener("submit", async event => {
      event.preventDefault();
      const text = chatInput.value.trim();
      if (!text) return;

      appendUserMessage(chatWindow, text);
      chatInput.value = "";

      const typingBubble = createTypingBubble(personaName);
      chatWindow.appendChild(typingBubble);
      chatWindow.scrollTop = chatWindow.scrollHeight;

      try {
        const res = await fetch(`/api/chat/${personaId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ message: text }),
        });

        const data = await res.json();
        typingBubble.remove();

        if (res.ok) {
          appendAiMessage(chatWindow, personaName, data.reply || "I'm reflecting on that — could you clarify a bit more?");
        } else {
          appendAiMessage(chatWindow, personaName, data.error || "⚠️ There was a problem connecting to the persona.");
        }
      } catch (err) {
        console.error("Chat API error:", err);
        typingBubble.remove();
        appendAiMessage(chatWindow, personaName, "⚠️ There was a problem connecting to the persona. Try again later.");
      }
    });
  }

  function appendUserMessage(container, text) {
    const block = document.createElement("div");
    block.className = "chat-message user-message fade-in";
    block.innerHTML = `
      <div class="message-avatar">🧑</div>
      <div class="message-content">
        <p class="message-text">${escapeHtml(text)}</p>
      </div>
    `;
    container.appendChild(block);
    container.scrollTop = container.scrollHeight;
  }

  function appendAiMessage(container, personaName, text) {
    const block = document.createElement("div");
    block.className = "chat-message ai-message fade-in";
    block.innerHTML = `
      <div class="message-avatar">${escapeHtml(personaName.charAt(0))}</div>
      <div class="message-content"><p class="message-text"></p></div>
    `;
    container.appendChild(block);

    const target = block.querySelector(".message-text");
    typeMessage(text, target);
    container.scrollTop = container.scrollHeight;
  }

  function createTypingBubble(personaName) {
    const typingBubble = document.createElement("div");
    typingBubble.className = "chat-message ai-message fade-in";
    typingBubble.innerHTML = `
      <div class="message-avatar">${escapeHtml(personaName.charAt(0))}</div>
      <div class="message-content typing-indicator">
        <span>.</span><span>.</span><span>.</span>
      </div>
    `;
    return typingBubble;
  }

  function typeMessage(text, target) {
    if (!target) return;
    let index = 0;
    const max = text.length;
    const interval = setInterval(() => {
      target.innerHTML += escapeHtml(text.charAt(index));
      index += 1;
      if (index >= max) clearInterval(interval);
    }, 20);
  }

  function startCall(personaName) {
    alert(`Simulating a live call with ${personaName}.`); // Placeholder for future integration
  }

  function showError(message) {
    const el = document.getElementById("error");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
  }

  function clearError() {
    const el = document.getElementById("error");
    if (!el) return;
    el.textContent = "";
    el.classList.remove("show");
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text ?? "";
    return div.innerHTML;
  }

  function buildFallbackData(text, characteristics, numReviews) {
    const personaBase = [
      { persona_name: "Avery Chen", persona_descriptor: "Strategy-focused product designer", location: "North America" },
      { persona_name: "Jordan Ramirez", persona_descriptor: "Data-driven growth specialist", location: "Europe" },
      { persona_name: "Morgan Patel", persona_descriptor: "User empathy researcher", location: "Asia" },
      { persona_name: "Sam Rivera", persona_descriptor: "Creative marketing strategist", location: "South America" },
      { persona_name: "Lena Schmidt", persona_descriptor: "Detail-oriented quality assurance", location: "Europe" },
    ];

    const traits = characteristics.length ? characteristics : ["Balanced"];
    const count = Math.max(1, numReviews || traits.length);
    const snippet = text.slice(0, 60) + (text.length > 60 ? "…" : "");

    const reviews = Array.from({ length: count }).map((_, index) => {
      const base = personaBase[index % personaBase.length];
      const rating = 6 + (index % 3);
      return {
        id: index + 1,
        index: index + 1,
        review: `As a ${base.persona_descriptor.toLowerCase()}, I've reviewed "${snippet}". It shows potential, but I'd clarify the value proposition and next validation steps.`,
        metadata: {
          persona_name: base.persona_name,
          persona_descriptor: base.persona_descriptor,
          characteristics: traits,
          sentiment_rating: rating,
          location: base.location,
          personality_description: base.persona_descriptor,
        },
      };
    });

    return {
      reviews,
      fallbackMessage: "Using simulated persona insights (offline mode).",
      message: "Using simulated persona insights (offline mode).",
    };
  }

  window.handleSubmit = handleSubmit;
  window.toggleCharacteristic = button => {
    const characteristic = button.getAttribute("data-characteristic");
    if (!characteristic) return;
    if (selectedCharacteristics.has(characteristic)) {
      selectedCharacteristics.delete(characteristic);
      button.classList.remove("selected");
    } else {
      selectedCharacteristics.add(characteristic);
      button.classList.add("selected");
    }
  };
  window.hideOverlay = hideOverlay;
  window.startCall = startCall;
  window.removeAttachment = () => {
    const ideaFileInput = document.getElementById("ideaFile");
    const attachmentDisplay = document.getElementById("attachmentDisplay");
    if (ideaFileInput) {
      ideaFileInput.value = "";
    }
    if (attachmentDisplay) {
      attachmentDisplay.classList.add("hidden");
    }
  };
})();