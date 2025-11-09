// static/callPopup.js
(() => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const supportsSpeech = Boolean(SpeechRecognition);

  let ringAudio, replyAudio, recognition;
  let isInCall = false, isProcessing = false, micAuthorized = !supportsSpeech;
  let callPopup, statusEl, dialogEl, manualInput, sendBtn, hangupBtn, micBtn;
  let conversationLog = [];
  let currentPersona = { id: null, name: "", tone: "friendly", gender: "", review: "", descriptor: "" };

  function normalizeName(candidate, fallback) {
    if (!candidate) return fallback;
    if (typeof candidate === "string") return candidate;
    if (typeof candidate === "number") return String(candidate);
    if (typeof candidate === "object") {
      const firstKey = ["name", "fullName", "displayName", "value", "label"].find(key => candidate[key]);
      return firstKey ? String(candidate[firstKey]) : fallback;
    }
    return fallback;
  }

  function openCallPopup(personaDetails) {
    if (!personaDetails || typeof personaDetails !== "object" || !personaDetails.id) return;
    if (isInCall) return;
    isInCall = true;
    conversationLog = [];

    const displayName = normalizeName(personaDetails.name, `Persona ${personaDetails.id}`);
    const tone = typeof personaDetails.tone === "string" ? personaDetails.tone : "friendly";
    currentPersona = { id: personaDetails.id, name: displayName, tone, gender: personaDetails.gender || "" };

    callPopup = document.createElement("div");
    callPopup.className = "call-popup";
    callPopup.innerHTML = `
      <div class="call-popup-content">
        <div class="phone-icon-wrapper">
          <div class="phone-wave"></div><div class="phone-wave delay"></div>
          <div class="phone-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="38" height="38" fill="none" stroke="#00ff95" stroke-width="2" viewBox="0 0 24 24">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2A19.79 19.79 0 0 1 3.08 5.18A2 2 0 0 1 5 3h3a2 2 0 0 1 2 1.72a12.05 12.05 0 0 0 .7 2.81a2 2 0 0 1-.45 2.11l-1.27 1.27a16 16 0 0 0 6.29 6.29l1.27-1.27a2 2 0 0 1 2.11-.45a12.05 12.05 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
            </svg>
          </div>
        </div>
        <div class="call-status">
          <h3>${escapeHtml(currentPersona.name)}</h3>
          <p id="callStatusText">Connecting…</p>
        </div>
        <div class="call-dialog" id="callDialog"></div>
        <div class="call-manual-entry ${supportsSpeech ? "hidden" : ""}">
          <textarea id="callTextInput" placeholder="Type your message…"></textarea>
          <button id="callSendBtn" class="call-send-btn">Send</button>
        </div>
        <p class="call-footnote">${supportsSpeech ? "Tap 🎙️ to talk or speak automatically." : "Allow microphone access in Chrome for hands-free use."}</p>
        <div class="call-controls">
          <button id="micBtn" class="mic-btn hidden" title="Talk">🎙️</button>
          <button id="hangupBtn" class="hangup-btn">Hang Up</button>
        </div>
      </div>
    `;
    document.body.appendChild(callPopup);

    statusEl = callPopup.querySelector("#callStatusText");
    dialogEl = callPopup.querySelector("#callDialog");
    manualInput = callPopup.querySelector("#callTextInput");
    sendBtn = callPopup.querySelector("#callSendBtn");
    hangupBtn = callPopup.querySelector("#hangupBtn");
    micBtn = callPopup.querySelector("#micBtn");

    hangupBtn.addEventListener("click", endCall);
    sendBtn?.addEventListener("click", () => {
      const text = manualInput?.value.trim();
      if (!text || isProcessing) return;
      manualInput.value = "";
      handleUserUtterance(text);
    });
    micBtn?.addEventListener("click", toggleMic);

    startRinging();
    setTimeout(connectCall, 1800);
  }

  function startRinging() {
    stopAudio(ringAudio);
    ringAudio = new Audio("/static/audio/ring.mp3");
    ringAudio.play().catch(() => {});
  }

  async function connectCall() {
    if (!isInCall) return;
    stopAudio(ringAudio);
    statusEl.textContent = "Connecting…";

    if (supportsSpeech && navigator.mediaDevices) {
      try {
        await navigator.mediaDevices.getUserMedia({ audio: true });
        micAuthorized = true;
        ensureRecognition();
        micBtn?.classList.remove("hidden");
        console.log("✅ Mic authorized, speech recognition ready");
      } catch (err) {
        console.warn("❌ Mic access denied:", err);
        micAuthorized = false;
        const manualEntry = callPopup?.querySelector(".call-manual-entry");
        if (manualEntry) manualEntry.classList.remove("hidden");
      }
    } else if (!supportsSpeech) {
      console.warn("❌ Speech recognition not supported in this browser");
      const manualEntry = callPopup?.querySelector(".call-manual-entry");
      if (manualEntry) manualEntry.classList.remove("hidden");
    }

    sendUtterance("", { initial: true });
  }

  function ensureRecognition() {
    if (!supportsSpeech) return;
    if (recognition) {
      try {
        recognition.abort();
      } catch (e) {
        // Ignore abort errors
      }
    }

    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
      micBtn?.classList.add("recording");
      statusEl.textContent = "Listening…";
    };

    recognition.onerror = e => {
      console.error("🔴 Speech recognition error:", e.error, e);
      micBtn?.classList.remove("recording");

      // Don't auto-restart on error
      const errorMessages = {
        'not-allowed': "Mic access denied. Please allow microphone in browser settings.",
        'no-speech': "No speech detected. Click mic to try again.",
        'audio-capture': "Mic not found. Check your microphone connection.",
        'network': "Network error. Check your connection.",
        'aborted': "Recognition stopped.",
        'service-not-allowed': "Speech service not allowed. Use HTTPS or localhost."
      };

      statusEl.textContent = errorMessages[e.error] || `Mic error (${e.error}). Click mic to try again.`;

      // Show text input as fallback on persistent errors
      if (e.error === 'not-allowed' || e.error === 'audio-capture' || e.error === 'service-not-allowed') {
        const manualEntry = callPopup?.querySelector(".call-manual-entry");
        if (manualEntry) manualEntry.classList.remove("hidden");
      }
    };

    recognition.onresult = e => {
      const transcript = e.results?.[0]?.[0]?.transcript?.trim();
      if (transcript) {
        handleUserUtterance(transcript);
        statusEl.textContent = "Processing…";
      }
    };

    recognition.onend = () => {
      micBtn?.classList.remove("recording");
      if (!isProcessing && statusEl.textContent === "Listening…") {
        statusEl.textContent = "Click mic to speak";
      }
    };
  }

  function toggleMic() {
    console.log("🎙️ Mic button clicked, supportsSpeech:", supportsSpeech, "micAuthorized:", micAuthorized);

    if (!supportsSpeech) {
      statusEl.textContent = "Speech not supported. Use text input below.";
      const manualEntry = callPopup?.querySelector(".call-manual-entry");
      if (manualEntry) manualEntry.classList.remove("hidden");
      return;
    }

    if (!micAuthorized) {
      statusEl.textContent = "Please allow microphone access and reload.";
      return;
    }

    if (!recognition) {
      console.log("⚠️ No recognition object, creating one...");
      ensureRecognition();
      if (!recognition) {
        console.error("❌ Failed to create recognition object");
        return;
      }
    }

    // Don't start if already processing or recording
    if (isProcessing) {
      console.log("⏳ Already processing, ignoring mic click");
      return;
    }

    if (micBtn?.classList.contains("recording")) {
      console.log("🔴 Already recording, ignoring mic click");
      return;
    }

    try {
      console.log("▶️ Starting speech recognition...");
      recognition.start();
    } catch (e) {
      console.error("❌ Mic start error:", e.name, e.message);
      if (e.name === 'InvalidStateError') {
        // Recognition already started, stop and restart
        console.log("🔄 Attempting to restart recognition...");
        try {
          recognition.stop();
          setTimeout(() => {
            try {
              recognition.start();
              console.log("✅ Recognition restarted");
            } catch (err) {
              console.error("❌ Restart failed:", err);
              statusEl.textContent = "Mic restart failed. Reload page.";
            }
          }, 100);
        } catch (stopErr) {
          console.error("❌ Stop failed:", stopErr);
        }
      } else {
        statusEl.textContent = `Mic error: ${e.message}`;
      }
    }
  }

  function handleUserUtterance(text) {
    appendMessage("user", text);
    conversationLog.push({ role: "user", content: text });
    sendUtterance(text);
  }

  function sendUtterance(text, { initial = false } = {}) {
    if (!currentPersona.id) return;
    isProcessing = true;
    statusEl.textContent = "Processing…";
    disableInput(true);

    fetch(`/api/call/${currentPersona.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        message: text,
        persona_name: currentPersona.name,
        tone: currentPersona.tone,
        gender: currentPersona.gender,
        history: conversationLog,
        initial,
      }),
    })
      .then(res => res.json())
      .then(data => {
        const reply = data.reply || "Let's keep talking.";
        appendMessage("assistant", reply);
        conversationLog.push({ role: "assistant", content: reply });
        if (data.audio) playReplyAudio(data.audio);
      })
      .catch(err => {
        console.error("Call error:", err);
      })
      .finally(() => {
        disableInput(false);
        isProcessing = false;
      });
  }

  function playReplyAudio(base64Audio) {
    const binary = atob(base64Audio);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  
    stopAudio(replyAudio);
    replyAudio = new Audio(URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" })));
  
    statusEl.textContent = "Persona speaking…";
    micBtn.classList.remove("user-speaking");
    micBtn.classList.add("persona-speaking"); // 🔴 persona talking = red mic
  
    replyAudio.play().catch(err => {
      console.warn("Audio playback failed:", err);
    });
  
    replyAudio.onended = () => {
      statusEl.textContent = "Your turn to speak";
      micBtn.classList.remove("persona-speaking");
      micBtn.classList.add("user-speaking"); // 🟢 user talking = green mic
    };
  }
  

  function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = `call-message ${role}`;
    div.innerHTML = `<div class="call-avatar">${role === "assistant" ? "🤖" : "🧑"}</div><div class="call-bubble">${escapeHtml(text)}</div>`;
    dialogEl.appendChild(div);
    dialogEl.scrollTop = dialogEl.scrollHeight;
  }

  function disableInput(d) {
    if (sendBtn) sendBtn.disabled = d;
    if (manualInput) manualInput.disabled = d;
  }

  function stopAudio(a) {
    if (a) try { a.pause(); a.currentTime = 0; } catch {}
  }

  function endCall() {
    isInCall = false;
    stopAudio(ringAudio);
    stopAudio(replyAudio);
    if (recognition) recognition.abort();
    callPopup?.classList.add("fade-out");
    setTimeout(() => callPopup?.remove(), 300);
  }

  function escapeHtml(v) {
    const div = document.createElement("div");
    div.textContent = v ?? "";
    return div.innerHTML;
  }

  window.openCallPopup = openCallPopup;
})();
