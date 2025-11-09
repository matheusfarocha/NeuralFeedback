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


    function showFeedbackDashboard(data) {
        const overlay = document.getElementById('feedbackOverlay');
        const cardsContainer = document.getElementById('feedbackCards');
        const summaryEl = document.getElementById('feedbackSummary');
        const mainWrapper = document.querySelector('.page-wrapper');

        if (!overlay || !cardsContainer) {
            return;
        }

        cardsContainer.innerHTML = '';

        if (Array.isArray(data.reviews) && data.reviews.length) {
            if (summaryEl) {
                if (data.fallbackMessage) {
                    summaryEl.textContent = data.fallbackMessage;
                } else {
                    const total = data.reviews.reduce((acc, review) => acc + (review.metadata?.sentiment_rating || 0), 0);
                    const average = (total / data.reviews.length).toFixed(1);
                    summaryEl.textContent = `Generated ${data.reviews.length} persona responses • Avg sentiment ${average}/10`;
                }
            }

            data.reviews.forEach(reviewItem => {
                const rating = reviewItem.metadata?.sentiment_rating || 0;
                const personaCard = document.createElement('article');
                personaCard.className = 'persona-card';
                personaCard.innerHTML = `
                    <div class="persona-header">
                        <div class="persona-avatar">${escapeHtml((reviewItem.metadata?.initial || reviewItem.index || 1).toString())}</div>
                        <div>
                            <h3 class="persona-name">${escapeHtml(reviewItem.metadata?.persona_name || `Persona #${reviewItem.index || 1}`)}</h3>
                            <p class="persona-meta">${escapeHtml(reviewItem.metadata?.persona_descriptor || reviewItem.metadata?.personality_description || 'Customer Persona')}</p>
                        </div>
                    </div>
                    <div class="persona-tags">
                        ${(reviewItem.metadata?.characteristics || []).map(char => `<span class="persona-tag">${escapeHtml(char)}</span>`).join('')}
                    </div>
                    <div class="persona-rating" aria-label="Sentiment rating">
                        ${Array.from({ length: 5 }).map((_, i) => `
                            <svg class="star-icon${i < rating ? ' star-filled' : ''}" viewBox="0 0 24 24" aria-hidden="true">
                                <path d="m12 3 2.4 5.8 6.1.5-4.6 4 1.4 6-5.3-3.2-5.3 3.2 1.4-6-4.6-4 6.1-.5z"/>
                            </svg>
                        `).join('')}
                        <span class="rating-value">${rating}/5</span>
                    </div>
                    <p class="persona-feedback">${escapeHtml(reviewItem.review || '')}</p>
                    <div class="persona-actions">
                        <a class="feedback-card-btn" href="#" onclick="return false;">View Chat (coming soon)</a>
                    </div>
                `;
                cardsContainer.appendChild(personaCard);
            });
        } else if (summaryEl) {
            summaryEl.textContent = data.fallbackMessage || 'We could not generate persona responses. Please adjust your input and try again.';
        }

        overlay.classList.remove('hidden');
        if (mainWrapper) {
            mainWrapper.classList.add('hidden');
        }

        const restartBtn = document.getElementById('feedbackRestartButton');
        if (restartBtn) {
            restartBtn.addEventListener('click', () => {
                overlay.classList.add('hidden');
                if (mainWrapper) {
                    mainWrapper.classList.remove('hidden');
                }
            }, { once: true });
        }
    }

    function showError(message) {
        const errorDiv = document.getElementById('error');
        if (!errorDiv) return;
        errorDiv.textContent = message;
        errorDiv.classList.add('show');
    }

    function clearError() {
        const errorDiv = document.getElementById('error');
        if (!errorDiv) return;
        errorDiv.textContent = '';
        errorDiv.classList.remove('show');
    }

    function showMetadata(reviewItem) {
        const modal = document.getElementById('metadataModal');
        const modalBody = document.getElementById('modalBody');
        if (!modal || !modalBody) return;

        const metadata = reviewItem.metadata || {};
        let content = `
            <div class="review-full-text">
                <div class="metadata-label">Customer Feedback</div>
                <div>${escapeHtml(reviewItem.review || '')}</div>
            </div>
        `;

        if (metadata.personality_description) {
            content += createMetadataBlock('Persona Profile', metadata.personality_description);
        }

        if (metadata.sentiment_rating !== undefined) {
            const sentimentLabel =
                metadata.sentiment_rating >= 8 ? '(Positive)' : metadata.sentiment_rating >= 4 ? '(Neutral)' : '(Negative)';
            content += createMetadataBlock(
                'Sentiment Rating',
                `${metadata.sentiment_rating}/10 ${sentimentLabel}`
            );
        }

        if (Array.isArray(metadata.characteristics)) {
            const traits = metadata.characteristics
                .map(char => {
                    const intensity = metadata.characteristic_intensities?.[char] || 1;
                    return `<div class="metadata-chip"><strong>${escapeHtml(char)}</strong>: ${Math.round(intensity * 100)}%</div>`;
                })
                .join('');
            content += `
                <div class="metadata-item">
                    <div class="metadata-label">Characteristics</div>
                    <div class="metadata-value">${traits}</div>
                </div>
            `;
        }

        if (metadata.age_range) {
            content += createMetadataBlock('Age Range', metadata.age_range);
        }

        if (metadata.gender) {
            content += createMetadataBlock('Gender', metadata.gender);
        }

        if (metadata.location) {
            content += createMetadataBlock('Location', metadata.location);
        }

        modalBody.innerHTML = content;
        modal.classList.add('show');
    }

    function createMetadataBlock(label, value) {
        return `
            <div class="metadata-item">
                <div class="metadata-label">${escapeHtml(label)}</div>
                <div class="metadata-value">${escapeHtml(value)}</div>
            </div>
        `;
    }

    function closeModal() {
        const modal = document.getElementById('metadataModal');
        if (!modal) return;
        modal.classList.remove('show');
    }

    function toggleCharacteristic(button) {
        if (!button) return;
        const characteristic = button.getAttribute('data-characteristic');
        if (!characteristic) return;

        if (selectedCharacteristics.has(characteristic)) {
            selectedCharacteristics.delete(characteristic);
            button.classList.remove('selected');
        } else {
            selectedCharacteristics.add(characteristic);
            button.classList.add('selected');
        }
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