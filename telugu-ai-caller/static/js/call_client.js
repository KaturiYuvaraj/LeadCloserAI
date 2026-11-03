/**
 * Advanced Natural Voice Call Client.
 * Connects browser microphone & speakers with Telugu AI Caller WebSocket.
 * Features:
 *  - Real-time Voice Activity Detection (VAD) with Web Audio Analyser
 *  - Configurable silence endpoint (default 0.9s) so replies start within ~2-3 seconds
 *  - Half-Duplex Echo Prevention (mutes mic during AI playback to prevent echo-loops)
 *  - Short breathing gap (250ms) before the mic reopens after the AI speaks
 *  - Sentence-chunked audio queue (first sentence plays while the rest is synthesized)
 *  - Optional call recording: customer mic + AI voice mixed into one WebM file,
 *    uploaded to the call record when the call ends
 */

class VoiceCallClient {
  constructor() {
    this.ws = null;
    this.mediaRecorder = null;
    this.audioStream = null;
    this.audioContext = null;
    this.analyser = null;
    this.source = null;
    this.vadInterval = null;

    this.isCallActive = false;
    this.isPlayingAudio = false;
    this.isListeningActive = false;
    this.isCustomerSpeaking = false;

    this.speechThreshold = 0.022; // calibrated for typical laptop / headset mic
    this.silenceTimeoutMs = 900;  // sustained silence that ends the customer's turn
    this.minSpeechMs = 400;       // ignore coughs / clicks shorter than this
    this.listenGapMs = 250;       // pause after AI audio before the mic reopens
    this.silenceTimer = null;
    this.turnStartTime = 0;
    this.turnEndedAt = null;      // when the customer's turn ended (for reply timing)
    this.lastTiming = null;
    this.audioChunks = [];

    this.audioQueue = [];
    this.currentAudioElement = null;
    this.currentSourceNode = null;

    // Call recording (customer + AI mixed)
    this.recordEnabled = false;
    this.recordDestination = null;
    this.callRecorder = null;
    this.recordingChunks = [];
    this.recordingDone = null;
    this.summaryWaitTimer = null;

    // Auto-hangup state
    this.pendingAutoHangup = false;
    this.autoHangupTimer = null;

    // Callbacks
    this.onStatusChange = null;
    this.onTranscript = null;
    this.onCallEnd = null;
    this.onCallEnding = null;
    this.onWaveformUpdate = null;
    this.onSpeakingStateChange = null; // notifies UI when customer is actively speaking
    this.onResponseTime = null;        // (totalMs, serverTiming) after each AI reply starts
    this.onRecordingStateChange = null; // (isRecording)
    this.onRecordingSaved = null;      // (callId, recordingUrl)
  }

  isClosingPhrase(text) {
    if (!text || typeof text !== 'string') return false;
    const lower = text.toLowerCase();

    // Spoken farewell markers in Telugu
    const teluguMarkers = [
      'సెలవు', 'ఉంటానండి', 'ఉంటాను', 'వీడ్కోలు', 'మంచి రోజు',
      'బై', 'బై బై', 'కాల్ ముగిస్తున్నాను', 'కలుద్దాం. ఉంటాను'
    ];
    for (const marker of teluguMarkers) {
      if (text.includes(marker)) return true;
    }

    // Spoken farewell markers in Hindi
    const hindiMarkers = [
      'अलविदा', 'बाय', 'बाय बाय', 'शुभ दिन', 'दिन शुभ हो', 'फिर मिलेंगे'
    ];
    for (const marker of hindiMarkers) {
      if (text.includes(marker)) return true;
    }

    // Spoken farewell markers in English
    const englishMarkers = [
      'goodbye', 'good-bye', 'have a great day', 'have a wonderful day',
      'have a nice day', 'have a good day', 'take care, bye', 'take care!',
      'talk to you tomorrow', 'talk soon', 'bye for now', 'bye!', 'bye.'
    ];
    for (const marker of englishMarkers) {
      if (lower.includes(marker)) return true;
    }

    return false;
  }

  setSilenceTimeout(ms) {
    const value = parseInt(ms, 10);
    if (!isNaN(value) && value >= 400 && value <= 3000) {
      this.silenceTimeoutMs = value;
    }
  }

  async startCall(leadId = null, lang = null, options = {}) {
    if (this.isCallActive) return;

    this.pendingAutoHangup = false;
    if (this.autoHangupTimer) {
      clearTimeout(this.autoHangupTimer);
      this.autoHangupTimer = null;
    }

    this.currentLeadId = leadId;
    this.recordEnabled = Boolean(options.record);
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const params = new URLSearchParams();
    if (leadId) params.append("lead_id", leadId);
    if (lang) params.append("lang", lang);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const wsUrl = `${protocol}//${window.location.host}/ws/web-call${qs}`;

    if (this.onStatusChange) this.onStatusChange("కాల్ కనెక్ట్ అవుతోంది... (Connecting call...)");

    // Create the audio context inside the click handler so the browser allows playback
    try {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      if (this.audioContext.state === "suspended") this.audioContext.resume();
    } catch (e) {
      console.warn("AudioContext unavailable, falling back to <audio> playback:", e);
      this.audioContext = null;
    }

    try {
      // 1. Request microphone with hardware echo cancellation & noise suppression
      this.audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      // 2. Open WebSocket
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.isCallActive = true;
        this.initVoiceActivityDetection();
        if (this.recordEnabled) this.startCallRecording();
        if (this.onStatusChange) this.onStatusChange("కాల్ ప్రారంభమైంది (Call Connected)");
      };

      this.ws.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleServerMessage(data);
        } catch (err) {
          console.error("Message parse error:", err);
        }
      };

      this.ws.onclose = () => {
        if (this.summaryWaitTimer) {
          clearTimeout(this.summaryWaitTimer);
          this.summaryWaitTimer = null;
        }
        this.endCall(false);
      };

      this.ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        if (this.onStatusChange) this.onStatusChange("కనెక్షన్ సమస్య వచ్చింది. (Connection Error)");
      };

    } catch (err) {
      console.error("Microphone access error:", err);
      alert("Microphone access is required for AI Calling. Please allow microphone permissions or use the text tester below.");
      if (this.onStatusChange) this.onStatusChange("మైక్రోఫోన్ అనుమతి అవసరం. (Mic Access Denied)");
      this.closeAudioContext();
    }
  }

  getSupportedMimeType() {
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'];
    for (const type of candidates) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(type)) return type;
    }
    return '';
  }

  initVoiceActivityDetection() {
    if (!this.audioStream) return;

    try {
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      }
      this.source = this.audioContext.createMediaStreamSource(this.audioStream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 512;
      this.source.connect(this.analyser);

      const bufferLength = this.analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      // Determine best audio MIME type
      const mimeType = this.getSupportedMimeType();
      this.mimeType = mimeType;

      this.mediaRecorder = mimeType
        ? new MediaRecorder(this.audioStream, { mimeType })
        : new MediaRecorder(this.audioStream);

      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          this.audioChunks.push(e.data);
        }
      };

      // VAD Analysis Loop running every 60ms
      this.vadInterval = setInterval(() => {
        if (!this.isCallActive) return;

        // Mute mic input while AI is speaking or during post-AI breathing gap
        if (this.isPlayingAudio || !this.isListeningActive) {
          return;
        }

        this.analyser.getByteTimeDomainData(dataArray);

        // Calculate Root Mean Square (RMS) volume level
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          const v = (dataArray[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / bufferLength);

        // Voice Activity Detection Logic
        if (rms > this.speechThreshold) {
          // --- USER IS CURRENTLY SPEAKING ---
          if (!this.isCustomerSpeaking) {
            this.isCustomerSpeaking = true;
            this.turnStartTime = Date.now();
            this.audioChunks = [];

            if (this.mediaRecorder.state === "inactive") {
              try { this.mediaRecorder.start(100); } catch (e) {}
            }

            if (this.onStatusChange) {
              this.onStatusChange("🎙️ శ్రద్ధగా వింటున్నాను... మీరు మాట్లాడుతున్నారు (Listening... speaking)");
            }
            if (this.onWaveformUpdate) this.onWaveformUpdate(true);
            if (this.onSpeakingStateChange) this.onSpeakingStateChange(true);
          }

          // If silence timer was ticking, cancel it because customer resumed speaking
          if (this.silenceTimer) {
            clearTimeout(this.silenceTimer);
            this.silenceTimer = null;
          }

        } else {
          // --- USER HAS PAUSED OR STOPPED SPEAKING ---
          if (this.isCustomerSpeaking) {
            if (!this.silenceTimer) {
              this.silenceTimer = setTimeout(() => {
                this.completeCustomerTurn();
              }, this.silenceTimeoutMs);
            }
          }
        }
      }, 60);

    } catch (e) {
      console.error("VAD setup error:", e);
    }
  }

  // ------------------------------------------------------------------
  // CALL RECORDING (customer mic + AI playback mixed into one track)
  // ------------------------------------------------------------------
  startCallRecording() {
    if (!this.audioContext || !this.source || !window.MediaRecorder) {
      console.warn("Call recording not supported in this browser.");
      this.recordEnabled = false;
      if (this.onRecordingStateChange) this.onRecordingStateChange(false);
      return;
    }

    try {
      this.recordDestination = this.audioContext.createMediaStreamDestination();
      this.source.connect(this.recordDestination);

      const mimeType = this.getSupportedMimeType();
      this.recordingMimeType = mimeType || 'audio/webm';
      this.callRecorder = mimeType
        ? new MediaRecorder(this.recordDestination.stream, { mimeType })
        : new MediaRecorder(this.recordDestination.stream);
      this.recordingChunks = [];

      this.recordingDone = new Promise((resolve) => {
        this.callRecorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) this.recordingChunks.push(e.data);
        };
        this.callRecorder.onstop = () => {
          const blob = this.recordingChunks.length
            ? new Blob(this.recordingChunks, { type: this.recordingMimeType })
            : null;
          this.recordingChunks = [];
          resolve(blob);
        };
      });

      this.callRecorder.start(1000);
      if (this.onRecordingStateChange) this.onRecordingStateChange(true);
    } catch (e) {
      console.error("Failed to start call recording:", e);
      this.callRecorder = null;
      this.recordingDone = null;
      if (this.onRecordingStateChange) this.onRecordingStateChange(false);
    }
  }

  stopCallRecording() {
    if (this.callRecorder && this.callRecorder.state !== "inactive") {
      try { this.callRecorder.stop(); } catch (e) {}
    }
    if (this.onRecordingStateChange) this.onRecordingStateChange(false);
  }

  async uploadRecording(callId) {
    if (!this.recordingDone || !callId) return null;
    const blob = await this.recordingDone;
    this.recordingDone = null;
    if (!blob || blob.size === 0) return null;

    const form = new FormData();
    form.append("file", blob, `call_${callId}.webm`);
    try {
      const resp = await fetch(`/api/calls/${callId}/recording`, { method: "POST", body: form });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const result = await resp.json();
      if (this.onRecordingSaved) this.onRecordingSaved(callId, result.recording_url);
      return result.recording_url;
    } catch (e) {
      console.error("Recording upload failed:", e);
      return null;
    }
  }

  // ------------------------------------------------------------------

  completeCustomerTurn() {
    if (!this.isCustomerSpeaking) return;

    this.isCustomerSpeaking = false;
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }

    if (this.onSpeakingStateChange) this.onSpeakingStateChange(false);
    if (this.onWaveformUpdate) this.onWaveformUpdate(false);

    const speechDuration = Date.now() - this.turnStartTime;

    // Filter out micro-noises/coughs
    if (speechDuration < this.minSpeechMs) {
      this.audioChunks = [];
      if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
        try { this.mediaRecorder.stop(); } catch (e) {}
      }
      if (this.onStatusChange) {
        this.onStatusChange("🟢 వింటున్నాను... మీరు మాట్లాడండి (Listening... speak now)");
      }
      return;
    }

    // Customer turn is complete! Measure from the moment they actually stopped talking.
    this.turnEndedAt = Date.now() - this.silenceTimeoutMs;
    if (this.onStatusChange) {
      this.onStatusChange("🧠 మీ సమాధానాన్ని విశ్లేషిస్తున్నాను... (Analyzing what you said...)");
    }

    // Temporarily pause listening while backend analyzes and generates response
    this.isListeningActive = false;

    if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
      this.mediaRecorder.onstop = async () => {
        if (this.audioChunks.length > 0 && this.isCallActive) {
          const blob = new Blob(this.audioChunks, { type: this.mimeType || 'audio/webm' });
          this.audioChunks = [];
          await this.sendAudioToServer(blob);
        }
      };
      try { this.mediaRecorder.stop(); } catch (e) {}
    } else if (this.audioChunks.length > 0) {
      const blob = new Blob(this.audioChunks, { type: this.mimeType || 'audio/webm' });
      this.audioChunks = [];
      this.sendAudioToServer(blob);
    }
  }

  forceFinishTurn() {
    // Allows user to click "Done Speaking" to skip silence wait time
    if (this.isCustomerSpeaking) {
      if (this.silenceTimer) clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
      this.completeCustomerTurn();
      this.turnEndedAt = Date.now();
    }
  }

  async sendAudioToServer(blob) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    const reader = new FileReader();
    reader.onloadend = () => {
      const base64Audio = reader.result.split(',')[1];
      this.ws.send(JSON.stringify({
        event: "audio_input",
        audio: base64Audio
      }));
    };
    reader.readAsDataURL(blob);
  }

  sendTextMessage(text) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      alert("Please click 'Start AI Call' first to initiate the session.");
      return;
    }

    // Stop ongoing speech & playback
    this.stopPlayback();
    this.isCustomerSpeaking = false;
    this.isListeningActive = false;
    if (this.silenceTimer) clearTimeout(this.silenceTimer);
    this.turnEndedAt = Date.now();

    if (this.onStatusChange) {
      this.onStatusChange("🧠 మీ మెసేజ్‌ను విశ్లేషిస్తున్నాను... (Analyzing...)");
    }

    this.ws.send(JSON.stringify({
      event: "text_input",
      text: text,
      generate_audio: true
    }));
  }

  handleServerMessage(data) {
    const event = data.event;

    if (event === "status") {
      if (this.onStatusChange) this.onStatusChange(data.message);

    } else if (event === "ai_speech") {
      if (this.onTranscript) this.onTranscript("AI (Sales Closer)", data.text, "ai", data.language);
      this.lastTiming = data.timing || null;

      // Detect call completion: explicit server flag or client-side farewell phrase detection
      if (data.should_hangup || this.isClosingPhrase(data.text)) {
        this.pendingAutoHangup = true;
        console.log("[VoiceCallClient] Call completion signaled. Auto-hangup scheduled after final speech.");
      }

      if (data.audio) {
        // First chunk of a reply: reply timing is measured when it starts playing
        this.audioQueue.push({ audio: data.audio, first: true });
        if (!this.isPlayingAudio) this.processAudioQueue();
      } else {
        this.reportResponseTime();
        if (this.pendingAutoHangup) {
          this.isListeningActive = false;
          if (this.onStatusChange) {
            this.onStatusChange("📞 సంభాషణ ముగిసింది. కాల్ ముగుస్తోంది... (Call concluded. Hanging up...)");
          }
          this.autoHangupTimer = setTimeout(() => {
            if (this.isCallActive) {
              this.endCall(true);
            }
          }, 1200);
        } else {
          setTimeout(() => {
            if (this.isCallActive && !this.isPlayingAudio && !this.pendingAutoHangup) {
              this.isListeningActive = true;
              if (this.onStatusChange) {
                this.onStatusChange("🟢 వింటున్నాను... మీరు మాట్లాడండి (Listening... speak now)");
              }
            }
          }, this.listenGapMs);
        }
      }

    } else if (event === "ai_audio") {
      // Follow-up sentence chunks of the same reply
      if (data.audio) {
        this.audioQueue.push({ audio: data.audio, first: false });
        if (!this.isPlayingAudio) this.processAudioQueue();
      }

    } else if (event === "user_speech") {
      if (this.onTranscript) this.onTranscript("You (Customer)", data.text, "user", data.language);

    } else if (event === "call_summary") {
      this.finishWithSummary(data);

    } else if (event === "error") {
      if (this.onStatusChange) this.onStatusChange(data.message);
      // Re-arm listening on transient error
      setTimeout(() => {
        this.isListeningActive = true;
      }, 1000);
    }
  }

  async finishWithSummary(data) {
    if (this.summaryWaitTimer) {
      clearTimeout(this.summaryWaitTimer);
      this.summaryWaitTimer = null;
    }
    if (this.recordingDone && data.call_id) {
      if (this.onStatusChange) this.onStatusChange("💾 రికార్డింగ్ సేవ్ అవుతోంది... (Saving call recording...)");
      const url = await this.uploadRecording(data.call_id);
      if (url) data.recording_url = url;
    }
    if (this.onCallEnd) this.onCallEnd(data);
    if (this.onStatusChange) this.onStatusChange("కాల్ ముగిసింది (Call Finished)");
  }

  reportResponseTime() {
    if (!this.turnEndedAt) return;
    const totalMs = Date.now() - this.turnEndedAt;
    this.turnEndedAt = null;
    if (this.onResponseTime) this.onResponseTime(totalMs, this.lastTiming);
  }

  base64ToArrayBuffer(b64) {
    const binary = atob(b64);
    const buffer = new ArrayBuffer(binary.length);
    const view = new Uint8Array(buffer);
    for (let i = 0; i < binary.length; i++) view[i] = binary.charCodeAt(i);
    return buffer;
  }

  onPlaybackFinished() {
    this.currentSourceNode = null;
    this.currentAudioElement = null;
    this.processAudioQueue();
  }

  async processAudioQueue() {
    if (this.audioQueue.length === 0) {
      this.isPlayingAudio = false;
      if (this.onWaveformUpdate) this.onWaveformUpdate(false);

      if (this.pendingAutoHangup) {
        this.isListeningActive = false;
        if (this.onStatusChange) {
          this.onStatusChange("📞 సంభాషణ ముగిసింది. కాల్ ముగుస్తోంది... (Call concluded. Hanging up...)");
        }
        // Polite natural 1.2s pause after final speech finishes before hanging up
        this.autoHangupTimer = setTimeout(() => {
          if (this.isCallActive) {
            console.log("[VoiceCallClient] Triggering auto-hangup now.");
            this.endCall(true);
          }
        }, 1200);
        return;
      }

      // Short breathing gap before the mic reopens so the AI doesn't hear its own tail
      setTimeout(() => {
        if (this.isCallActive && !this.isPlayingAudio && !this.pendingAutoHangup) {
          this.isListeningActive = true;
          if (this.onStatusChange) {
            this.onStatusChange("🟢 వింటున్నాను... మీరు మాట్లాడండి (Listening... speak now)");
          }
        }
      }, this.listenGapMs);
      return;
    }

    const nextItem = this.audioQueue.shift();
    this.isPlayingAudio = true;
    this.isListeningActive = false; // MUTE mic while AI is talking

    if (this.onStatusChange) {
      this.onStatusChange("AI మాట్లాడుతోంది... (AI is speaking...)");
    }
    if (this.onWaveformUpdate) this.onWaveformUpdate(true);

    let arrayBuffer;
    try {
      arrayBuffer = this.base64ToArrayBuffer(nextItem.audio);
    } catch (err) {
      console.error("Audio decode error:", err);
      this.processAudioQueue();
      return;
    }

    // Preferred path: Web Audio (also feeds the call recording)
    if (this.audioContext && this.audioContext.state !== "closed") {
      try {
        const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer.slice(0));
        const node = this.audioContext.createBufferSource();
        node.buffer = audioBuffer;
        node.connect(this.audioContext.destination);
        if (this.recordDestination) node.connect(this.recordDestination);
        node.onended = () => this.onPlaybackFinished();
        this.currentSourceNode = node;
        node.start();
        if (nextItem.first) this.reportResponseTime();
        return;
      } catch (e) {
        console.warn("Web Audio playback failed, using <audio> fallback:", e);
      }
    }

    // Fallback path: HTML audio element (not included in the recording)
    try {
      const blob = new Blob([arrayBuffer], { type: 'audio/wav' });
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      this.currentAudioElement = audio;
      audio.onended = () => { URL.revokeObjectURL(audioUrl); this.onPlaybackFinished(); };
      audio.onerror = () => { URL.revokeObjectURL(audioUrl); this.onPlaybackFinished(); };
      await audio.play();
      if (nextItem.first) this.reportResponseTime();
    } catch (e) {
      console.warn("Autoplay audio blocked or error:", e);
      this.onPlaybackFinished();
    }
  }

  stopPlayback() {
    this.audioQueue = [];
    if (this.autoHangupTimer) {
      clearTimeout(this.autoHangupTimer);
      this.autoHangupTimer = null;
    }
    this.pendingAutoHangup = false;
    if (this.currentSourceNode) {
      try { this.currentSourceNode.onended = null; this.currentSourceNode.stop(); } catch (e) {}
      this.currentSourceNode = null;
    }
    if (this.currentAudioElement) {
      try { this.currentAudioElement.pause(); } catch (e) {}
      this.currentAudioElement = null;
    }
    this.isPlayingAudio = false;
  }

  closeAudioContext() {
    if (this.audioContext && this.audioContext.state !== "closed") {
      try { this.audioContext.close(); } catch (e) {}
    }
    this.audioContext = null;
    this.recordDestination = null;
  }

  endCall(notifyServer = true) {
    if (!this.isCallActive) return;

    if (this.autoHangupTimer) {
      clearTimeout(this.autoHangupTimer);
      this.autoHangupTimer = null;
    }
    this.pendingAutoHangup = false;

    if (this.onCallEnding) {
      try { this.onCallEnding(); } catch (e) {}
    }

    this.isCallActive = false;
    this.isListeningActive = false;
    this.isCustomerSpeaking = false;
    this.stopPlayback();

    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }

    if (this.vadInterval) {
      clearInterval(this.vadInterval);
      this.vadInterval = null;
    }

    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      try { this.mediaRecorder.stop(); } catch (e) {}
    }

    // Stop the call recording first, then release audio once it has flushed
    const recordingFlushed = this.recordingDone || Promise.resolve();
    this.stopCallRecording();

    if (this.source) {
      try { this.source.disconnect(); } catch (e) {}
      this.source = null;
    }

    recordingFlushed.then(() => this.closeAudioContext());

    if (this.audioStream) {
      this.audioStream.getTracks().forEach(track => track.stop());
      this.audioStream = null;
    }

    if (this.ws) {
      const ws = this.ws;
      if (notifyServer && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ event: "hangup" }));
        if (this.onStatusChange) this.onStatusChange("📝 కాల్ సారాంశం సిద్ధమవుతోంది... (Preparing call summary...)");
        // Keep the socket open until the server sends the call summary (max 20s)
        this.summaryWaitTimer = setTimeout(() => {
          try { ws.close(); } catch (e) {}
        }, 20000);
      } else {
        try { ws.close(); } catch (e) {}
      }
      this.ws = null;
    }

    if (this.onSpeakingStateChange) this.onSpeakingStateChange(false);
    if (this.onWaveformUpdate) this.onWaveformUpdate(false);
    if (!notifyServer && this.onStatusChange) this.onStatusChange("కాల్ ముగిసింది (Call Finished)");
  }
}

window.VoiceCallClient = VoiceCallClient;
