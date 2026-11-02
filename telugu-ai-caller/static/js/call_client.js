/**
 * Advanced Natural Voice Call Client.
 * Connects browser microphone & speakers with Telugu AI Caller WebSocket.
 * Features:
 *  - Real-time Voice Activity Detection (VAD) with Web Audio Analyser
 *  - 1.8-second Silence Endpoint Detection (ensures customer completes sentence without interruption)
 *  - Half-Duplex Echo Prevention (mutes mic during AI playback to prevent echo-loops)
 *  - Human Breathing Space (600ms natural conversational pause between turns)
 *  - Audio Queueing (guarantees zero speech overlap)
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
    this.silenceTimeoutMs = 1800; // 1.8s sustained silence threshold
    this.silenceTimer = null;
    this.turnStartTime = 0;
    this.audioChunks = [];

    this.audioQueue = [];
    this.currentAudioElement = null;

    // Callbacks
    this.onStatusChange = null;
    this.onTranscript = null;
    this.onCallEnd = null;
    this.onWaveformUpdate = null;
    this.onSpeakingStateChange = null; // notifies UI when customer is actively speaking
  }

  async startCall(leadId = null, lang = null) {
    if (this.isCallActive) return;

    this.currentLeadId = leadId;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const params = new URLSearchParams();
    if (leadId) params.append("lead_id", leadId);
    if (lang) params.append("lang", lang);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const wsUrl = `${protocol}//${window.location.host}/ws/web-call${qs}`;

    if (this.onStatusChange) this.onStatusChange("కాల్ కనెక్ట్ అవుతోంది... (Connecting call...)");

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
    }
  }

  initVoiceActivityDetection() {
    if (!this.audioStream) return;

    try {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      this.source = this.audioContext.createMediaStreamSource(this.audioStream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 512;
      this.source.connect(this.analyser);

      const bufferLength = this.analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      // Determine best audio MIME type
      let mimeType = 'audio/webm;codecs=opus';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        if (MediaRecorder.isTypeSupported('audio/webm')) mimeType = 'audio/webm';
        else if (MediaRecorder.isTypeSupported('audio/mp4')) mimeType = 'audio/mp4';
        else mimeType = '';
      }
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
            // Start the 1.8s silence timer if not already ticking
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

    // Filter out micro-noises/coughs shorter than 600ms
    if (speechDuration < 600) {
      this.audioChunks = [];
      if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
        try { this.mediaRecorder.stop(); } catch (e) {}
      }
      if (this.onStatusChange) {
        this.onStatusChange("🟢 వింటున్నాను... మీరు మాట్లాడండి (Listening... speak now)");
      }
      return;
    }

    // Customer turn is complete!
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
      this.completeCustomerTurn();
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
    if (this.currentAudioElement) {
      try { this.currentAudioElement.pause(); } catch (e) {}
    }
    this.isPlayingAudio = false;
    this.isCustomerSpeaking = false;
    this.isListeningActive = false;
    if (this.silenceTimer) clearTimeout(this.silenceTimer);

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

      if (data.audio) {
        // Enqueue audio to ensure perfectly sequential, non-overlapping playback
        this.audioQueue.push({
          audio: data.audio,
          text: data.text,
          lang: data.language
        });

        if (!this.isPlayingAudio) {
          this.processAudioQueue();
        }
      } else {
        // No audio attached; wait 600ms and reopen mic
        setTimeout(() => {
          this.isListeningActive = true;
          if (this.onStatusChange) {
            this.onStatusChange("🟢 వింటున్నాను... మీరు మాట్లాడండి (Listening... speak now)");
          }
        }, 600);
      }

    } else if (event === "user_speech") {
      if (this.onTranscript) this.onTranscript("You (Customer)", data.text, "user", data.language);

    } else if (event === "call_summary") {
      if (this.onCallEnd) this.onCallEnd(data);

    } else if (event === "error") {
      if (this.onStatusChange) this.onStatusChange(data.message);
      // Re-arm listening on transient error
      setTimeout(() => {
        this.isListeningActive = true;
      }, 1000);
    }
  }

  processAudioQueue() {
    if (this.audioQueue.length === 0) {
      this.isPlayingAudio = false;
      if (this.onWaveformUpdate) this.onWaveformUpdate(false);

      // NATURAL HUMAN BREATHING GAP:
      // Wait 600ms after AI finishes speaking before opening the microphone gate.
      // This prevents the AI from cutting in immediately and allows the customer time to process.
      setTimeout(() => {
        if (this.isCallActive && !this.isPlayingAudio) {
          this.isListeningActive = true;
          if (this.onStatusChange) {
            this.onStatusChange("🟢 వింటున్నాను... మీరు మాట్లాడండి (Listening... speak now)");
          }
        }
      }, 600);
      return;
    }

    const nextItem = this.audioQueue.shift();
    this.isPlayingAudio = true;
    this.isListeningActive = false; // MUTE mic while AI is talking

    if (this.onStatusChange) {
      this.onStatusChange("AI మాట్లాడుతోంది... (AI is speaking...)");
    }
    if (this.onWaveformUpdate) this.onWaveformUpdate(true);

    try {
      const audioBytes = atob(nextItem.audio);
      const arrayBuffer = new ArrayBuffer(audioBytes.length);
      const view = new Uint8Array(arrayBuffer);
      for (let i = 0; i < audioBytes.length; i++) {
        view[i] = audioBytes.charCodeAt(i);
      }

      const blob = new Blob([arrayBuffer], { type: 'audio/wav' });
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      this.currentAudioElement = audio;

      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        this.currentAudioElement = null;
        // Proceed to next queued audio, or finish playback
        this.processAudioQueue();
      };

      audio.onerror = (e) => {
        console.warn("Audio playback error:", e);
        URL.revokeObjectURL(audioUrl);
        this.currentAudioElement = null;
        this.processAudioQueue();
      };

      audio.play().catch(e => {
        console.warn("Autoplay audio blocked or error:", e);
        this.processAudioQueue();
      });

    } catch (err) {
      console.error("Audio decode error:", err);
      this.processAudioQueue();
    }
  }

  endCall(notifyServer = true) {
    if (!this.isCallActive) return;

    this.isCallActive = false;
    this.isPlayingAudio = false;
    this.isListeningActive = false;
    this.isCustomerSpeaking = false;
    this.audioQueue = [];

    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }

    if (this.vadInterval) {
      clearInterval(this.vadInterval);
      this.vadInterval = null;
    }

    if (this.currentAudioElement) {
      try { this.currentAudioElement.pause(); } catch (e) {}
      this.currentAudioElement = null;
    }

    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      try { this.mediaRecorder.stop(); } catch (e) {}
    }

    if (this.source) {
      try { this.source.disconnect(); } catch (e) {}
      this.source = null;
    }

    if (this.audioContext && this.audioContext.state !== "closed") {
      try { this.audioContext.close(); } catch (e) {}
      this.audioContext = null;
    }

    if (this.audioStream) {
      this.audioStream.getTracks().forEach(track => track.stop());
      this.audioStream = null;
    }

    if (this.ws) {
      if (notifyServer && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ event: "hangup" }));
      }
      setTimeout(() => {
        try { this.ws.close(); } catch (e) {}
        this.ws = null;
      }, 400);
    }

    if (this.onSpeakingStateChange) this.onSpeakingStateChange(false);
    if (this.onWaveformUpdate) this.onWaveformUpdate(false);
    if (this.onStatusChange) this.onStatusChange("కాల్ ముగిసింది (Call Finished)");
  }
}

window.VoiceCallClient = VoiceCallClient;
