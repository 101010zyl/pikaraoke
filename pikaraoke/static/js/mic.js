let micSocket = null;
let micPeerConnection = null;
let micLocalStream = null;
let micAnalyser = null;
let micLevelAnimationId = null;
let micAudioContext = null;
let desiredMicConnection = false;
let currentSessionId = null;
let micMuted = false;
let currentStatusText = "Idle";
let currentStatusClass = "is-info";
let currentStatusDetailText = "";

const localHosts = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

const micPageRoot = () => document.querySelector("[data-mic-page='true']");
const statusPill = () => document.getElementById("mic-status-pill");
const sessionLabel = () => document.getElementById("mic-session-label");
const levelFill = () => document.getElementById("mic-level-fill");
const startButton = () => document.getElementById("mic-start-button");
const muteButton = () => document.getElementById("mic-mute-button");
const disconnectButton = () => document.getElementById("mic-disconnect-button");
const secureWarning = () => document.getElementById("mic-insecure-warning");
const embedWarning = () => document.getElementById("mic-embed-warning");
const secureLink = () => document.getElementById("mic-secure-link");
const statusDetail = () => document.getElementById("mic-status-detail");
const getMicConfig = () => window.MicConfig || {};

const isSecureContextAvailable = () =>
  window.isSecureContext || localHosts.has(window.location.hostname);

const setStatus = (text, cssClass) => {
  currentStatusText = text;
  currentStatusClass = cssClass;
  const pill = statusPill();
  if (!pill) return;
  pill.textContent = text;
  pill.className = `tag ${cssClass}`;
};

const setStatusDetail = (text = "") => {
  currentStatusDetailText = text;
  const detail = statusDetail();
  if (detail) {
    detail.textContent = text;
  }
};

const updateButtons = () => {
  const start = startButton();
  const mute = muteButton();
  const disconnect = disconnectButton();
  if (!start || !mute || !disconnect) return;
  const hasStream = !!micLocalStream;
  start.disabled = false;
  mute.disabled = !hasStream;
  disconnect.disabled = !hasStream && !currentSessionId;
  mute.textContent = micMuted ? "Unmute" : "Mute";
};

const getRequestedAudioConstraints = () => {
  const echoCancel = document.getElementById("mic-echo-cancel");
  const noiseSuppress = document.getElementById("mic-noise-suppress");
  const autoGain = document.getElementById("mic-auto-gain");
  return {
    echoCancellation: echoCancel ? echoCancel.checked : true,
    noiseSuppression: noiseSuppress ? noiseSuppress.checked : true,
    autoGainControl: autoGain ? autoGain.checked : true,
  };
};

const updateSecureWarning = () => {
  const needsWarning = !isSecureContextAvailable();
  const warning = secureWarning();
  const link = secureLink();
  const config = getMicConfig();
  if (warning) {
    warning.style.display = needsWarning ? "block" : "none";
  }
  if (link) {
    const target = config.secureServerUrl
      ? `${config.secureServerUrl}/mic`
      : config.preferredMicUrl;
    link.href = target || "#";
    link.textContent = target || "";
  }
  if (needsWarning) {
    setStatus("Secure context required", "is-warning");
    setStatusDetail("The browser will not show a microphone prompt until the page is loaded as HTTPS or localhost.");
  }
};

const releaseMicStream = () => {
  if (!micLocalStream) return;
  micLocalStream.getTracks().forEach((track) => track.stop());
  micLocalStream = null;
  micMuted = false;
};

const stopLevelMeter = () => {
  if (micLevelAnimationId) {
    cancelAnimationFrame(micLevelAnimationId);
    micLevelAnimationId = null;
  }
  if (levelFill()) {
    levelFill().style.width = "0%";
  }
};

const startLevelMeter = () => {
  stopLevelMeter();
  if (!micLocalStream) return;

  const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextCtor) return;

  if (!micAudioContext) {
    micAudioContext = new AudioContextCtor();
  }

  const source = micAudioContext.createMediaStreamSource(micLocalStream);
  micAnalyser = micAudioContext.createAnalyser();
  micAnalyser.fftSize = 512;
  source.connect(micAnalyser);

  const samples = new Uint8Array(micAnalyser.frequencyBinCount);
  const draw = () => {
    if (!micAnalyser) return;
    micAnalyser.getByteFrequencyData(samples);
    const peak = samples.reduce((max, value) => Math.max(max, value), 0);
    const fill = levelFill();
    if (!fill) {
      micLevelAnimationId = null;
      return;
    }
    fill.style.width = `${Math.max(4, Math.round((peak / 255) * 100))}%`;
    micLevelAnimationId = requestAnimationFrame(draw);
  };

  micLevelAnimationId = requestAnimationFrame(draw);
};

const closePeerConnection = () => {
  if (!micPeerConnection) return;
  micPeerConnection.ontrack = null;
  micPeerConnection.onicecandidate = null;
  micPeerConnection.onconnectionstatechange = null;
  micPeerConnection.close();
  micPeerConnection = null;
};

const updateSessionLabel = () => {
  const label = sessionLabel();
  if (label) {
    label.textContent = currentSessionId ? `Session: ${currentSessionId}` : "";
  }
};

const ensureSocket = () => {
  if (micSocket) return;

  micSocket = io();

  micSocket.on("connect", () => {
    if (desiredMicConnection && isSecureContextAvailable()) {
      micSocket.emit("register_mic");
    } else if (!desiredMicConnection) {
      setStatus("Ready", "is-info");
      setStatusDetail("");
    }
  });

  micSocket.on("disconnect", () => {
    closePeerConnection();
    if (desiredMicConnection) {
      setStatus("Reconnecting", "is-warning");
      setStatusDetail("Socket disconnected while the phone mic was active.");
    } else {
      setStatus("Disconnected", "is-dark");
      setStatusDetail("");
    }
    currentSessionId = null;
    updateSessionLabel();
    updateButtons();
  });

  micSocket.on("mic_registered", (payload) => {
    currentSessionId = payload.sessionId;
    updateSessionLabel();
    setStatus("Waiting for splash screen", "is-info");
    setStatusDetail("Microphone captured. Waiting for the splash player to request the stream.");
    updateButtons();
  });

  micSocket.on("mic_replaced", () => {
    closePeerConnection();
    currentSessionId = null;
    updateSessionLabel();
    desiredMicConnection = false;
    setStatus("Another phone took over", "is-warning");
    setStatusDetail("Only one active phone microphone is supported at a time.");
    updateButtons();
  });

  micSocket.on("mic_state", (payload) => {
    if (payload.sessionId && currentSessionId && payload.sessionId !== currentSessionId) {
      return;
    }

    currentSessionId = payload.sessionId;
    updateSessionLabel();

    if (!payload.micConnected) {
      closePeerConnection();
      setStatus(desiredMicConnection ? "Waiting for microphone" : "Disconnected", "is-dark");
      setStatusDetail(desiredMicConnection ? "Press Start Mic again to capture the microphone." : "");
    } else if (payload.connected) {
      setStatus("Live in splash mix", "is-success");
      setStatusDetail("Your phone microphone is now mixed into the splash screen audio.");
    } else if (payload.splashConnected) {
      setStatus("Negotiating connection", "is-warning");
      setStatusDetail("The player browser is finishing the WebRTC handshake.");
    } else {
      setStatus("Waiting for splash screen", "is-info");
      setStatusDetail("Microphone captured. Waiting for the splash player to request the stream.");
    }
    updateButtons();
  });

  micSocket.on("webrtc_offer", async (payload) => {
    if (!micLocalStream) {
      return;
    }

    try {
      currentSessionId = payload.sessionId;
      updateSessionLabel();
      closePeerConnection();

      micPeerConnection = new RTCPeerConnection();
      micLocalStream.getTracks().forEach((track) => micPeerConnection.addTrack(track, micLocalStream));

      micPeerConnection.onicecandidate = ({ candidate }) => {
        if (!candidate || !currentSessionId) return;
        micSocket.emit("webrtc_ice_candidate", {
          sessionId: currentSessionId,
          candidate,
        });
      };

      micPeerConnection.onconnectionstatechange = () => {
        const state = micPeerConnection?.connectionState;
        if (state === "connected") {
          setStatus("Live in splash mix", "is-success");
          setStatusDetail("Your phone microphone is now mixed into the splash screen audio.");
        } else if (state === "failed" || state === "disconnected") {
          setStatus("Connection interrupted", "is-warning");
          setStatusDetail(`WebRTC connection state: ${state}`);
        }
      };

      await micPeerConnection.setRemoteDescription(payload.description);
      const answer = await micPeerConnection.createAnswer();
      await micPeerConnection.setLocalDescription(answer);

      micSocket.emit("webrtc_answer", {
        sessionId: currentSessionId,
        description: micPeerConnection.localDescription,
      });
    } catch (error) {
      console.warn("Failed to respond to splash WebRTC offer", error);
      closePeerConnection();
      setStatus("Connection failed", "is-danger");
      setStatusDetail("The player browser could not finish the microphone connection.");
    }
  });

  micSocket.on("webrtc_ice_candidate", async (payload) => {
    if (!micPeerConnection || !payload.candidate) return;
    try {
      await micPeerConnection.addIceCandidate(payload.candidate);
    } catch (error) {
      console.warn("Failed to add ICE candidate", error);
    }
  });
};

const captureMicrophone = async () => {
  if (micLocalStream) return micLocalStream;

  micLocalStream = await navigator.mediaDevices.getUserMedia({
    audio: getRequestedAudioConstraints(),
    video: false,
  });

  micLocalStream.getAudioTracks().forEach((track) => {
    track.enabled = true;
  });

  startLevelMeter();
  updateButtons();
  return micLocalStream;
};

const startMic = async () => {
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus("Microphone unavailable", "is-danger");
    setStatusDetail("This browser does not expose navigator.mediaDevices.getUserMedia().");
    return;
  }

  if (!isSecureContextAvailable()) {
    updateSecureWarning();
    const config = getMicConfig();
    if (config.secureServerUrl) {
      setStatusDetail(`Open ${config.secureServerUrl}/mic in a directly trusted HTTPS tab, then try again.`);
    }
    return;
  }

  ensureSocket();
  desiredMicConnection = true;

  try {
    await captureMicrophone();
    setStatus("Registering microphone", "is-info");
    setStatusDetail("Microphone permission granted. Registering this phone with PiKaraoke.");
    if (micSocket.connected) {
      micSocket.emit("register_mic");
    }
  } catch (error) {
    console.error("Microphone access failed", error);
    desiredMicConnection = false;
    setStatus("Microphone permission denied", "is-danger");
    setStatusDetail(`${error?.name || "Error"}${error?.message ? `: ${error.message}` : ""}`);
  }
};

const disconnectMic = () => {
  desiredMicConnection = false;
  if (micSocket?.connected) {
    micSocket.emit("disconnect_mic");
  }
  closePeerConnection();
  currentSessionId = null;
  updateSessionLabel();
  releaseMicStream();
  stopLevelMeter();
  setStatus("Disconnected", "is-dark");
  setStatusDetail("");
  updateButtons();
};

const toggleMute = () => {
  if (!micLocalStream) return;
  micMuted = !micMuted;
  micLocalStream.getAudioTracks().forEach((track) => {
    track.enabled = !micMuted;
  });
  updateButtons();
};

window.addEventListener("beforeunload", () => {
  desiredMicConnection = false;
  if (micSocket?.connected) {
    micSocket.emit("disconnect_mic");
  }
  closePeerConnection();
  releaseMicStream();
  stopLevelMeter();
});

const renderCurrentState = () => {
  setStatus(currentStatusText, currentStatusClass);
  setStatusDetail(currentStatusDetailText);
  updateSessionLabel();
  updateButtons();
};

const initMicPage = () => {
  const root = micPageRoot();
  if (!root) return;

  ensureSocket();
  updateSecureWarning();
  renderCurrentState();
  if (micLocalStream) {
    startLevelMeter();
  } else {
    stopLevelMeter();
  }

  const warning = embedWarning();
  if (warning) {
    warning.style.display = window.self !== window.top ? "block" : "none";
  }

  const start = startButton();
  const mute = muteButton();
  const disconnect = disconnectButton();
  if (start) {
    start.onclick = () => void startMic();
  }
  if (mute) {
    mute.onclick = toggleMute;
  }
  if (disconnect) {
    disconnect.onclick = disconnectMic;
  }
};

window.PikaraokeMicPage = {
  init: initMicPage,
};
