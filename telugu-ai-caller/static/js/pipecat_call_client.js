/**
 * Real-time Voice Call Client (Pipecat engine over WebRTC).
 *
 * Same public interface and callbacks as VoiceCallClient (call_client.js), so the
 * dashboard can switch engines without other changes:
 *   startCall(leadId, lang, { record }) · endCall() · sendTextMessage(text)
 *   setSilenceTimeout(ms) · forceFinishTurn()
 *   onStatusChange · onTranscript · onCallEnd · onWaveformUpdate · onSpeakingStateChange
 *   onResponseTime · onRecordingStateChange · onRecordingSaved
 *
 * Audio streams both ways over WebRTC (the server does speech detection, barge-in
 * and language switching). Transcripts, speaking state and reply timing arrive as
 * JSON on the WebRTC data channel (`lc` field). Optional recording mixes the mic
 * and the AI voice into one WebM and uploads it to the saved call.
 */

class PipecatCallClient {
  constructor() {
    this.pc = null;
    this.dc = null;
    this.localStream = null;
    this.remoteStream = null;
    this.remoteAudioEl = null;
    this.audioContext = null;
    this.pingTimer = null;
    this.sessionId = null;

    this.isCallActive = false;
    this.isPlayingAudio = false;
    this.silenceTimeoutMs = 900;
    this.lastBreakdown = null;
    this.summaryHandled = false;
    this.ending = false;
    this.pendingText = null;

    // Recording (mic + AI voice)
    this.recordEnabled = false;
    this.recordDestination = null;
    this.callRecorder = null;
    this.recordingChunks = [];
    this.recordingDone = null;

    // Callbacks (same as VoiceCallClient)
    this.onStatusChange = null;
    this.onTranscript = null;
    this.onCallEnd = null;
    this.onWaveformUpdate = null;
    this.onSpeakingStateChange = null;
    this.onResponseTime = null;
    this.onRecordingStateChange = null;
    this.onRecordingSaved = null;
  }

  setSilenceTimeout(ms) {
    const value = parseInt(ms, 10);
    if (!isNaN(value) && value >= 400 && value <= 3000) this.silenceTimeoutMs = value;
  }

  forceFinishTurn() {
    // Turn-taking is handled on the server (Silero VAD); nothing to do here.
  }

  status(text) {
    if (this.onStatusChange) this.onStatusChange(text);
  }

  async startCall(leadId = null, lang = null, options = {}) {
    if (this.isCallActive || this.pc) return;
    this.recordEnabled = Boolean(options.record);
    this.summaryHandled = false;
    this.ending = false;
    this.pendingText = null;
    this.lastBreakdown = null;
    this.status("కాల్ కనెక్ట్ అవుతోంది... (Connecting call...)");

    // Create inside the click handler so the browser allows audio playback
    try {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      if (this.audioContext.state === "suspended") this.audioContext.resume();
    } catch (e) {
      this.audioContext = null;
    }

    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
    } catch (err) {
      console.error("Microphone access error:", err);
      alert("Microphone access is required for AI Calling. Please allow microphone permissions or use the text box below.");
      this.status("మైక్రోఫోన్ అనుమతి అవసరం. (Mic Access Denied)");
      this.cleanup();
      return;
    }

    try {
      this.pc = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });

      // Server expects: transceiver 0 = audio, 1 = video (unused, kept for compatibility)
      const micTrack = this.localStream.getAudioTracks()[0];
      this.pc.addTransceiver(micTrack, { direction: "sendrecv", streams: [this.localStream] });
      this.pc.addTransceiver("video", { direction: "sendrecv" });

      this.dc = this.pc.createDataChannel("chat", { ordered: true });
      this.dc.onopen = () => {
        this.pingTimer = setInterval(() => {
          if (this.dc && this.dc.readyState === "open") this.dc.send(`ping: ${Date.now()}`);
        }, 1000);
        this.flushPendingText();
      };
      this.dc.onmessage = (event) => this.handleDataMessage(event.data);

      this.pc.ontrack = (event) => {
        if (event.track.kind !== "audio") return;
        this.remoteStream = event.streams && event.streams[0] ? event.streams[0] : new MediaStream([event.track]);
        this.attachRemoteAudio();
      };

      this.pc.onconnectionstatechange = () => {
        const state = this.pc ? this.pc.connectionState : "closed";
        if (state === "connected") {
          this.isCallActive = true;
          this.status("కాల్ ప్రారంభమైంది (Call Connected)");
          if (this.recordEnabled) this.startCallRecording();
          this.flushPendingText();
        } else if ((state === "failed" || state === "disconnected") && this.isCallActive) {
          this.status("కనెక్షన్ సమస్య వచ్చింది. (Connection lost)");
          this.endCall(true);
        }
      };

      const offer = await this.pc.createOffer();
      await this.pc.setLocalDescription(offer);
      await this.waitForIceGathering(2000);

      const resp = await fetch("/api/voice/offer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sdp: this.pc.localDescription.sdp,
          type: this.pc.localDescription.type,
          lead_id: leadId,
          lang: lang || null,
          wait_ms: this.silenceTimeoutMs
        })
      });
      if (!resp.ok) throw new Error(`Voice server returned ${resp.status}`);
      const answer = await resp.json();
      this.sessionId = answer.session_id;
      await this.pc.setRemoteDescription({ sdp: answer.sdp, type: answer.type });
    } catch (err) {
      console.error("Voice call setup failed:", err);
      this.status("కాల్ కనెక్ట్ కాలేదు. (Could not connect the call)");
      this.cleanup();
    }
  }

  waitForIceGathering(timeoutMs) {
    if (!this.pc || this.pc.iceGatheringState === "complete") return Promise.resolve();
    return new Promise((resolve) => {
      const done = () => {
        if (this.pc) this.pc.removeEventListener("icegatheringstatechange", check);
        resolve();
      };
      const check = () => { if (this.pc && this.pc.iceGatheringState === "complete") done(); };
      this.pc.addEventListener("icegatheringstatechange", check);
      setTimeout(done, timeoutMs);
    });
  }

  attachRemoteAudio() {
    if (!this.remoteStream) return;
    // Playing through an <audio> element keeps the browser's echo cancellation working
    if (!this.remoteAudioEl) {
      this.remoteAudioEl = document.createElement("audio");
      this.remoteAudioEl.autoplay = true;
      this.remoteAudioEl.style.display = "none";
      document.body.appendChild(this.remoteAudioEl);
    }
    this.remoteAudioEl.srcObject = this.remoteStream;
    this.remoteAudioEl.play().catch(() => {});
    if (this.recordDestination && this.audioContext) this.connectRemoteToRecorder();
  }

  // ------------------------------------------------------------------ data channel events
  handleDataMessage(raw) {
    let msg;
    try { msg = JSON.parse(raw); } catch (e) { return; }
    if (!msg || !msg.lc) return;

    switch (msg.lc) {
      case "transcript":
        if (this.onTranscript) {
          const isAi = msg.role === "assistant";
          const text = msg.interrupted ? `${msg.text} …` : msg.text;
          this.onTranscript(isAi ? "AI (Sales Closer)" : "You (Customer)", text, isAi ? "ai" : "user", msg.language);
        }
        break;
      case "status":
        this.status(msg.text);
        break;
      case "speaking":
        if (msg.who === "bot") {
          this.isPlayingAudio = msg.active;
          if (this.onWaveformUpdate) this.onWaveformUpdate(msg.active);
          this.status(msg.active ? "AI మాట్లాడుతోంది... (AI is speaking...)" : "🟢 వింటున్నాను... మీరు మాట్లాడండి (Listening... speak now)");
        } else if (msg.who === "user") {
          if (this.onWaveformUpdate) this.onWaveformUpdate(msg.active);
          if (msg.active) this.status("🎙️ శ్రద్ధగా వింటున్నాను... (Listening... speaking)");
        }
        break;
      case "breakdown":
        this.lastBreakdown = msg;
        break;
      case "latency":
        if (this.onResponseTime) {
          const b = this.lastBreakdown || {};
          this.onResponseTime(msg.total_ms, { stt_ms: b.stt || 0, llm_ms: b.llm || 0, tts_first_ms: b.tts || 0 });
        }
        break;
      case "call_ending":
        // The AI said goodbye and is ending the call: run the normal end-of-call flow
        this.status("👋 కాల్ ముగుస్తోంది... (AI ended the call)");
        setTimeout(() => this.endCall(false), 300);
        break;
      case "call_summary":
        this.finishWithSummary(msg);
        break;
      default:
        break;
    }
  }

  flushPendingText() {
    if (this.pendingText && this.isCallActive && this.dc && this.dc.readyState === "open") {
      const text = this.pendingText;
      this.pendingText = null;
      this.sendTextMessage(text);
    }
  }

  sendTextMessage(text) {
    if (this.pc && !this.isCallActive && !this.ending) {
      // Call is still connecting: send as soon as it is ready
      this.pendingText = text;
      return;
    }
    if (!this.isCallActive || !this.sessionId) {
      alert("Please click 'Start AI Call' first to initiate the session.");
      return;
    }
    this.status("🧠 మీ మెసేజ్‌ను విశ్లేషిస్తున్నాను... (Analyzing...)");
    const payload = { type: "lc-app", lc: "text_input", text };
    if (this.dc && this.dc.readyState === "open") {
      this.dc.send(JSON.stringify(payload));
    } else {
      fetch(`/api/voice/sessions/${this.sessionId}/text`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text })
      }).catch(() => {});
    }
  }

  // ------------------------------------------------------------------ recording
  startCallRecording() {
    if (!this.audioContext || !window.MediaRecorder || this.callRecorder) return;
    try {
      this.recordDestination = this.audioContext.createMediaStreamDestination();
      this.audioContext.createMediaStreamSource(this.localStream).connect(this.recordDestination);
      if (this.remoteStream) this.connectRemoteToRecorder();

      const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
      const mimeType = types.find(t => MediaRecorder.isTypeSupported(t)) || "";
      this.recordingMimeType = mimeType || "audio/webm";
      this.callRecorder = mimeType
        ? new MediaRecorder(this.recordDestination.stream, { mimeType })
        : new MediaRecorder(this.recordDestination.stream);
      this.recordingChunks = [];
      this.recordingDone = new Promise((resolve) => {
        this.callRecorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) this.recordingChunks.push(e.data); };
        this.callRecorder.onstop = () => {
          const blob = this.recordingChunks.length ? new Blob(this.recordingChunks, { type: this.recordingMimeType }) : null;
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
    }
  }

  connectRemoteToRecorder() {
    if (this.remoteRecordSource || !this.remoteStream) return;
    try {
      this.remoteRecordSource = this.audioContext.createMediaStreamSource(this.remoteStream);
      this.remoteRecordSource.connect(this.recordDestination);
    } catch (e) {
      console.warn("Could not add AI voice to the recording:", e);
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

  // ------------------------------------------------------------------ ending the call
  async endCall(notifyServer = true) {
    if (this.ending || (!this.pc && !this.isCallActive)) return;
    this.ending = true;
    const sessionId = this.sessionId;
    this.isCallActive = false;
    this.isPlayingAudio = false;
    if (this.onWaveformUpdate) this.onWaveformUpdate(false);
    if (this.onSpeakingStateChange) this.onSpeakingStateChange(false);
    this.stopCallRecording();

    if (!sessionId) { this.cleanup(); return; }
    this.status("📝 కాల్ సారాంశం సిద్ధమవుతోంది... (Preparing call summary...)");

    if (notifyServer) {
      try { await fetch(`/api/voice/sessions/${sessionId}/hangup`, { method: "POST" }); } catch (e) {}
    }

    // The summary may also arrive on the data channel; whichever comes first wins
    try {
      const resp = await fetch(`/api/voice/sessions/${sessionId}/summary?wait_seconds=30`);
      if (resp.ok) await this.finishWithSummary(await resp.json());
    } catch (e) {
      console.error("Could not load call summary:", e);
    }
    this.cleanup();
  }

  async finishWithSummary(data) {
    if (this.summaryHandled || !data) return;
    this.summaryHandled = true;
    if (this.recordingDone && data.call_id) {
      this.status("💾 రికార్డింగ్ సేవ్ అవుతోంది... (Saving call recording...)");
      const url = await this.uploadRecording(data.call_id);
      if (url) data.recording_url = url;
    }
    if (this.onCallEnd) this.onCallEnd(data);
    this.status("కాల్ ముగిసింది (Call Finished)");
  }

  cleanup() {
    if (this.pingTimer) { clearInterval(this.pingTimer); this.pingTimer = null; }
    if (this.dc) { try { this.dc.close(); } catch (e) {} this.dc = null; }
    if (this.pc) { try { this.pc.close(); } catch (e) {} this.pc = null; }
    if (this.localStream) { this.localStream.getTracks().forEach(t => t.stop()); this.localStream = null; }
    if (this.remoteAudioEl) { this.remoteAudioEl.srcObject = null; this.remoteAudioEl.remove(); this.remoteAudioEl = null; }
    this.remoteStream = null;
    this.remoteRecordSource = null;
    const recordingFlushed = this.recordingDone || Promise.resolve();
    recordingFlushed.then(() => {
      if (this.audioContext && this.audioContext.state !== "closed") {
        try { this.audioContext.close(); } catch (e) {}
      }
      this.audioContext = null;
      this.recordDestination = null;
    });
    this.callRecorder = null;
    this.sessionId = null;
    this.isCallActive = false;
  }
}

window.PipecatCallClient = PipecatCallClient;
