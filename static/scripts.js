(() => {
    const selectedCharacteristics = new Set();

    document.addEventListener('DOMContentLoaded', () => {
        setupIndexPage();
    });

    function setupIndexPage() {
        const reviewCountSlider = document.getElementById('reviewCount');
        const reviewCountValue = document.getElementById('reviewCountValue');
        const ageMinSlider = document.getElementById('ageMin');
        const ageMaxSlider = document.getElementById('ageMax');
        const ageMinValue = document.getElementById('ageMinValue');
        const ageMaxValue = document.getElementById('ageMaxValue');
        const generateButton = document.getElementById('generateButton');

        if (reviewCountSlider && reviewCountValue) {
            reviewCountSlider.addEventListener('input', () => {
                reviewCountValue.textContent = reviewCountSlider.value;
            });
        }

        if (ageMinSlider && ageMaxSlider && ageMinValue && ageMaxValue) {
            const updateAgeRange = () => {
                let minVal = parseInt(ageMinSlider.value, 10);
                let maxVal = parseInt(ageMaxSlider.value, 10);

                if (minVal > maxVal) {
                    [minVal, maxVal] = [maxVal, minVal];
                    ageMinSlider.value = minVal;
                    ageMaxSlider.value = maxVal;
                }

                ageMinValue.textContent = minVal;
                ageMaxValue.textContent = maxVal;

                const range = parseInt(ageMinSlider.max, 10) - parseInt(ageMinSlider.min, 10);
                const progress = document.getElementById('ageRangeProgress');
                if (progress) {
                    const minPercent = ((minVal - ageMinSlider.min) / range) * 100;
                    const maxPercent = ((maxVal - ageMinSlider.min) / range) * 100;
                    progress.style.left = `${minPercent}%`;
                    progress.style.width = `${maxPercent - minPercent}%`;
                }
            };

            ageMinSlider.addEventListener('input', updateAgeRange);
            ageMaxSlider.addEventListener('input', updateAgeRange);
            updateAgeRange();
        }

        if (generateButton) {
            generateButton.addEventListener('click', handleSubmit);
        }

        window.onclick = function (event) {
            const modal = document.getElementById('metadataModal');
            if (modal && event.target === modal) {
                closeModal();
            }
        };

        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                closeModal();
            }
        });
    }

    async function handleSubmit() {
        const textInput = document.getElementById('textInput');
        const reviewCountSlider = document.getElementById('reviewCount');
        const ageMinSlider = document.getElementById('ageMin');
        const ageMaxSlider = document.getElementById('ageMax');
        const genderSelect = document.getElementById('gender');
        const locationSelect = document.getElementById('location');
        const errorDiv = document.getElementById('error');
        const generateButton = document.getElementById('generateButton');

        if (!textInput || !reviewCountSlider || !errorDiv || !generateButton) {
            return;
        }

        const text = textInput.value.trim();
        const numReviews = parseInt(reviewCountSlider.value, 10);
        const ageMin = parseInt(ageMinSlider.value, 10);
        const ageMax = parseInt(ageMaxSlider.value, 10);
        const gender = (genderSelect.value || '').trim();
        const location = (locationSelect.value || '').trim();
        const characteristics = Array.from(selectedCharacteristics);

        if (!text) {
            showError('Please enter a product idea first!');
            return;
        }

        if (!characteristics.length) {
            showError('Please select at least one characteristic for your customer personas!');
            return;
        }

        clearError();
        generateButton.disabled = true;
        generateButton.textContent = 'Generating…';

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text,
                    numReviews,
                    ageMin,
                    ageMax,
                    gender,
                    location,
                    characteristics,
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                const details = Array.isArray(data.details) ? data.details.join('\n') : '';
                throw new Error(`${data.error || 'Generation failed.'}${details ? `\n${details}` : ''}`);
            }

            showFeedbackDashboard(data);
        } catch (error) {
            console.warn('Failed to fetch from /generate, using fallback personas. Reason:', error);
            const fallback = buildFallbackData(text, characteristics.length ? characteristics : ['Analytical']);
            showFeedbackDashboard(fallback);
        } finally {
            generateButton.disabled = false;
            generateButton.textContent = 'Generate AI Client Responses';
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
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function buildFallbackData(text, characteristics) {
        const personaBase = [
            {
                persona_name: 'Avery Chen',
                persona_descriptor: 'Strategy-focused product designer',
                tone: 'Supportive',
            },
            {
                persona_name: 'Jordan Ramirez',
                persona_descriptor: 'Data-driven growth specialist',
                tone: 'Analytical',
            },
            {
                persona_name: 'Morgan Patel',
                persona_descriptor: 'User empathy researcher',
                tone: 'Empathetic',
            },
        ];

        const reviews = characteristics.map((char, idx) => {
            const persona = personaBase[idx % personaBase.length];
            const rating = 3 + (idx % 3);
            return {
                index: idx + 1,
                review: `As a ${char} persona, I see potential in “${text.slice(0, 60)}${text.length > 60 ? '…' : ''}”. Focus on clarifying value for target customers and outlining next validation steps.`,
                metadata: {
                    persona_name: persona.persona_name,
                    persona_descriptor: persona.persona_descriptor,
                    initial: persona.persona_name[0],
                    characteristics,
                    sentiment_rating: rating > 5 ? 5 : rating,
                },
            };
        });

        return {
            reviews,
            fallbackMessage: 'Our live reviewers were unavailable, so here are simulated persona insights instead.',
        };
    }

    // Expose functions used from HTML
    window.handleSubmit = handleSubmit;
    window.toggleCharacteristic = toggleCharacteristic;
    window.showMetadata = showMetadata;
    window.closeModal = closeModal;
})();


