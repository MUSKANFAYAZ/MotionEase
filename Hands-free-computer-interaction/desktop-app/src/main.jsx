import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const api = (path, method = "GET", body) => {
  if (window.motionEase?.request) {
    return window.motionEase.request(path, method, body);
  }
  return fetch(`http://127.0.0.1:5000${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  }).then(async (response) => {
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || data.message || response.statusText);
    return data;
  });
};

const voiceCommandGroups = [
  {
    title: "Mouse clicks",
    commands: [
      { phrase: "left click · click · select · confirm", action: "Perform a single left click." },
      { phrase: "double click", action: "Perform a double left click." },
      { phrase: "right click", action: "Perform a right click." },
    ],
  },
  {
    title: "Scrolling",
    commands: [
      { phrase: "scroll up", action: "Scroll upward." },
      { phrase: "scroll down", action: "Scroll downward." },
    ],
  },
  {
    title: "Open an app or folder",
    commands: [
      { phrase: "open notepad", action: "Open Notepad (TextEdit on macOS, gedit on Linux)." },
      { phrase: "open calculator", action: "Open the system calculator." },
      { phrase: "open files", action: "Open your home folder." },
      { phrase: "open chrome · open edge", action: "Open a new Google Chrome or Microsoft Edge window." },
      { phrase: "open keyboard", action: "Open the operating system's on-screen keyboard for typing in any app." },
      { phrase: "focus address bar", action: "Focus the browser address bar with Ctrl+L (Command+L on macOS)." },
    ],
  },
  {
    title: "Blink-confirmed actions",
    commands: [
      { phrase: "select with blink · confirm with blink · use blink to select", action: "Arm a single left click; blink within 3 seconds." },
      { phrase: "double click with blink", action: "Arm a double click; blink within 3 seconds." },
      { phrase: "right click with blink · use blink for right click", action: "Arm a right click; blink within 3 seconds." },
    ],
  },
  {
    title: "Dictation",
    commands: [
      { phrase: "start typing · start dictating", action: "Type recognized speech into the currently focused text field." },
      { phrase: "enter", action: "Press Enter in the focused app; for example, submit a browser search." },
      { phrase: "stop dictating", action: "Stop typing recognized speech." },
      { phrase: "comma · period · full stop · question mark · exclamation mark · new line", action: "Speak these phrases during dictation to insert punctuation or a line break." },
    ],
  },
];

const virtualKeyboardRows = [
  ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
  ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
  ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
  ["z", "x", "c", "v", "b", "n", "m"],
];

function DwellKey({ label, onActivate, utility = false }) {
  const timer = useRef(null);
  const fired = useRef(false);

  const cancelDwell = () => {
    window.clearTimeout(timer.current);
    timer.current = null;
    fired.current = false;
  };

  const startDwell = () => {
    cancelDwell();
    timer.current = window.setTimeout(() => {
      fired.current = true;
      onActivate();
    }, 5000);
  };

  useEffect(() => () => window.clearTimeout(timer.current), []);

  return (
    <button
      type="button"
      className={`virtual-key${utility ? " utility-key" : ""}`}
      aria-label={`${label}; hold pointer for 5 seconds to activate`}
      onPointerEnter={startDwell}
      onPointerLeave={cancelDwell}
      onPointerDown={(event) => event.preventDefault()}
      onClick={(event) => {
        if (event.detail === 0 && !fired.current) onActivate();
      }}
    >
      {label}
    </button>
  );
}

function GuidePage() {
  return (
    <section className="guide-page" aria-labelledby="guide-title">
      <div className="guide-heading">
        <div>
          <p className="eyebrow">MOTIONEASE · QUICK START</p>
          <h2 id="guide-title">How to use MotionEase</h2>
          <p>Set up the local services, then use voice or head gestures to control your computer.</p>
        </div>
      </div>

      <section className="panel guide-panel">
        <div className="panel-head">
          <div className="icon">1</div>
          <div><h3>Start the app</h3><p>One-time setup, then launch the desktop app</p></div>
        </div>
        <ol className="guide-steps">
          <li>From the project folder, install the Python requirements and download the Vosk speech model once if it is not already present:</li>
          <li className="guide-code"><code>python -m venv venv</code><code>.\venv\Scripts\Activate.ps1</code><code>python -m pip install -r backend\requirements.txt</code><code>python backend\scripts\download_vosk_model.py</code></li>
          <li>Install the desktop dependencies with <code>npm install</code> in <code>desktop-app</code>, then start the app there with <code>npm run dev</code>.</li>
          <li>When the control window opens, head tracking and offline voice recognition start automatically. Allow microphone and camera access if prompted.</li>
        </ol>
        <p className="guide-note">If the app is already set up, launch it with <code>npm run dev</code> from the <code>desktop-app</code> folder. The model download is needed only once.</p>
      </section>

      <section className="guide-section" aria-labelledby="commands-title">
        <div className="guide-section-heading">
          <div>
            <p className="eyebrow">SPEAK NATURALLY, ONE ACTION AT A TIME</p>
            <h3 id="commands-title">Voice commands</h3>
          </div>
          <span className="guide-status">Voice must be running</span>
        </div>
        <div className="guide-command-grid">
          {voiceCommandGroups.map((group) => (
            <section className="panel guide-command-card" key={group.title}>
              <h4>{group.title}</h4>
              <dl>
                {group.commands.map((command) => (
                  <div className="guide-command" key={command.phrase}>
                    <dt><code>{command.phrase}</code></dt>
                    <dd>{command.action}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
        <p className="guide-note">For browser search: say “open chrome” or “open edge”, then “focus address bar”, then “start typing” and speak your search. Say “enter” to submit it and “stop dictating” when finished. Focus a text field before dictating. Say “open keyboard” to launch your system keyboard for any app; the Predictive text box also has an on-screen keyboard whose keys activate after a five-second pointer dwell.</p>
      </section>

      <section className="guide-lower-grid">
        <section className="panel guide-panel">
          <div className="panel-head">
            <div className="icon">⌖</div>
            <div><h3>Head and gesture controls</h3><p>Use the camera preview while tracking is running</p></div>
          </div>
          <ul className="guide-list">
            <li>Move your head to move the pointer.</li>
            <li>Left-eye blink: single click. Right-eye blink: double click.</li>
            <li>Open and close your mouth to right-click.</li>
            <li>Press <kbd>D</kbd> in the camera window to toggle dwell-click mode; hold the pointer still over a target for five seconds to select it once.</li>
            <li>Press <kbd>C</kbd> to re-center your neutral head position.</li>
            <li>Press <kbd>Q</kbd> to close the camera window and stop head tracking.</li>
          </ul>
        </section>
        <section className="panel guide-panel">
          <div className="panel-head">
            <div className="icon voice-icon">〰</div>
            <div><h3>Check status and troubleshoot</h3><p>Use the controls page to see what happened</p></div>
          </div>
          <ul className="guide-list">
            <li>“Last heard” shows the latest recognized transcript; “Last action” shows the routed result.</li>
            <li>If voice is stopped, select <strong>Start listening</strong>. If the local model is missing, use the setup command above and restart voice.</li>
            <li>If speech is not recognized, check that the correct microphone is connected and that the Voice status is running.</li>
            <li>Use the Stop buttons on the controls page to stop either service. Restart it there when needed.</li>
          </ul>
        </section>
      </section>
    </section>
  );
}

function App() {
  const [state, setState] = useState(null);
  const [page, setPage] = useState("controls");
  const [message, setMessage] = useState("");
  const [draft, setDraft] = useState("");
  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [busy, setBusy] = useState(false);
  const requestId = useRef(0);
  const draftRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      setState(await api("/api/state"));
    } catch (error) {
      setMessage(error.message);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const startServices = async () => {
      setBusy(true);
      setMessage("Loading local models and starting hands-free controls...");
      try {
        const current = await api("/api/state");
        if (!active) return;
        setState(current);

        const services = [];
        if (current.eye_tracking?.status !== "running") {
          services.push({ label: "Head tracking", path: "/start-eye-tracking" });
        }
        if (!["running", "starting"].includes(current.voice?.status)) {
          services.push({ label: "Offline voice", path: "/api/voice/start" });
        }

        const results = await Promise.all(services.map(async (service) => {
          try {
            await api(service.path, "POST");
            return { label: service.label };
          } catch (error) {
            return { label: service.label, error: error.message };
          }
        }));
        if (!active) return;

        const started = results.filter((result) => !result.error);
        const failed = results.filter((result) => result.error);
        const alreadyRunning = [
          current.eye_tracking?.status === "running" && "Head tracking",
          ["running", "starting"].includes(current.voice?.status) && "Offline voice",
        ].filter(Boolean);
        const messages = [
          started.length && `Started ${started.map((result) => result.label).join(" and ").toLowerCase()}.`,
          alreadyRunning.length && `${alreadyRunning.join(" and ")} already running.`,
          ...failed.map((result) => `${result.label} failed to start: ${result.error}`),
        ].filter(Boolean);
        setMessage(messages.join(" "));
        await refresh();
      } catch (error) {
        if (active) setMessage(`Could not start local models: ${error.message}`);
      } finally {
        if (active) setBusy(false);
      }
    };

    startServices();
    const timer = window.setInterval(refresh, 1200);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [refresh]);

  useEffect(() => {
    const id = ++requestId.current;
    if (!draft.trim()) {
      setSuggestions([]);
      return;
    }
    const timer = window.setTimeout(async () => {
      try {
        const result = await api("/api/suggestions", "POST", { text: draft });
        if (id === requestId.current) setSuggestions(result.suggestions || []);
      } catch {
        if (id === requestId.current) setSuggestions([]);
      }
    }, 140);
    return () => window.clearTimeout(timer);
  }, [draft]);

  const run = async (label, path, method = "POST") => {
    setBusy(true);
    setMessage("");
    try {
      const result = await api(path, method);
      setMessage(result.message || `${label} complete`);
      await refresh();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const useSuggestion = (word) => {
    const nextDraft = draft.replace(/\S+$/, word) + " ";
    setDraft(nextDraft);
    setSuggestions([]);
  };

  const insertDraftText = (text) => {
    const field = draftRef.current;
    const start = field?.selectionStart ?? draft.length;
    const end = field?.selectionEnd ?? start;
    setDraft(`${draft.slice(0, start)}${text}${draft.slice(end)}`);
    window.requestAnimationFrame(() => {
      if (!field) return;
      field.focus();
      field.setSelectionRange(start + text.length, start + text.length);
    });
  };

  const deleteDraftCharacter = () => {
    const field = draftRef.current;
    const start = field?.selectionStart ?? draft.length;
    const end = field?.selectionEnd ?? start;
    if (start === end && start === 0) return;
    const removeStart = start === end ? start - 1 : start;
    setDraft(`${draft.slice(0, removeStart)}${draft.slice(end)}`);
    window.requestAnimationFrame(() => {
      if (!field) return;
      field.focus();
      field.setSelectionRange(removeStart, removeStart);
    });
  };

  const learnPhrase = async () => {
    try {
      await api("/api/autocomplete/learn", "POST", { text: draft });
      setMessage("Phrase learned locally for future suggestions");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const voice = state?.voice || {};
  const action = state?.last_interaction?.action;
  const startupError = /failed|could not|error/i.test(message);

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand-mark">M</div>
        <div>
          <p className="eyebrow">MOTIONEASE · ON-DEVICE ASSISTIVE INPUT</p>
          <h1>Hands-free control</h1>
        </div>
        <span className={`service-pill ${state?.eye_tracking?.status === "running" ? "online" : ""}`}>
          <i /> Head {state?.eye_tracking?.status || "loading"}
        </span>
        <span className={`service-pill ${voice.status === "running" ? "online" : ""}`}>
          <i /> Voice {voice.status || "loading"}
        </span>
        <button
          className="secondary guide-toggle"
          onClick={() => setPage(page === "guide" ? "controls" : "guide")}
          aria-current={page === "guide" ? "page" : undefined}
          aria-label={page === "guide" ? "Return to controls" : "Open user guide"}
        >
          {page === "guide" ? "Back to controls" : "How to use"}
        </button>
      </header>

      {page === "guide" ? <GuidePage /> : (
        <>
      <section className="hero">
        <div>
          <span className="eyebrow">YOUR WORKSPACE, WITHOUT THE MOUSE</span>
          <h2>Move, speak, and interact.</h2>
          <p>Head tracking and speech processing run locally on this computer.</p>
        </div>
        <div className="orb" aria-hidden="true"><span /></div>
      </section>

      <div className="grid">
        <section className="panel">
          <div className="panel-head">
            <div className="icon">⌖</div>
            <div><h3>Head control</h3><p>Cursor, blink, mouth gesture, dwell</p></div>
          </div>
          <div className="button-row">
            <button disabled={busy} onClick={() => run("Head tracking started", "/start-eye-tracking")}>Start tracking</button>
            <button className="secondary" disabled={busy} onClick={() => run("Head tracking stopped", "/stop-eye-tracking")}>Stop</button>
          </div>
          <p className="hint">In the camera window: <kbd>C</kbd> re-center · <kbd>D</kbd> dwell click · <kbd>Q</kbd> quit</p>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div className="icon voice-icon">〰</div>
            <div><h3>Offline voice</h3><p>Vosk speech recognition · no cloud audio</p></div>
          </div>
          <div className="button-row">
            <button disabled={busy || voice.status === "running"} onClick={() => run("Voice recognition started", "/api/voice/start")}>Start listening</button>
            <button className="secondary" disabled={busy || voice.status === "stopped"} onClick={() => run("Voice recognition stopped", "/api/voice/stop")}>Stop</button>
          </div>
          <div
            className={`voice-model-status ${voice.model_ready ? "ready" : "setup-needed"}`}
            role="status"
          >
            <span className="voice-model-indicator" aria-hidden="true" />
            <span>{voice.model_ready ? "Speech model ready" : "Speech model setup required"}</span>
            {!voice.model_ready && (
              <button type="button" className="setup-link" onClick={() => setPage("guide")}>
                View setup
              </button>
            )}
          </div>
          <p className="hint">
            Say “open chrome” or “open edge”, “focus address bar”, then “start typing” to dictate into the focused field; say “enter” to submit and “stop dictating” to finish. You can also say left click, double click, right click, scroll up/down, or open notepad/calculator/files. For blink confirmation, say “select with blink”, “double click with blink”, or “right click with blink”, then blink.
          </p>
        </section>
      </div>

      <section className="panel assistant-panel">
        <div className="panel-head">
          <div className="icon text-icon">Aa</div>
        <div><h3>Predictive text</h3><p>Private local suggestions and a five-second dwell keyboard for this text box</p></div>
        </div>
        <label className="sr-only" htmlFor="draft">Write or edit text</label>
        <textarea
          id="draft"
          ref={draftRef}
          value={draft}
          onFocus={() => setKeyboardVisible(true)}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Tab" && suggestions.length) {
              event.preventDefault();
              useSuggestion(suggestions[0].word);
            }
          }}
          placeholder="Start typing to see next-word suggestions…"
          rows="3"
        />
        <div className="keyboard-toolbar">
          <span className="hint">Hold a key for 5 seconds, or use a physical keyboard; say “open keyboard” for other apps.</span>
          <button
            type="button"
            className="secondary"
            aria-expanded={keyboardVisible}
            aria-controls="virtual-keyboard"
            onClick={() => setKeyboardVisible(!keyboardVisible)}
          >
            {keyboardVisible ? "Hide keyboard" : "Show keyboard"}
          </button>
        </div>
        {keyboardVisible && (
          <div className="virtual-keyboard" id="virtual-keyboard" aria-label="On-screen keyboard">
            {virtualKeyboardRows.map((row, rowIndex) => (
              <div className="keyboard-row" key={`row-${rowIndex}`}>
                {row.map((key) => (
                  <DwellKey key={key} label={key} onActivate={() => insertDraftText(key)} />
                ))}
                {rowIndex === 3 && (
                  <DwellKey label="Backspace" utility onActivate={deleteDraftCharacter} />
                )}
              </div>
            ))}
            <div className="keyboard-row keyboard-actions">
              <DwellKey label="Space" utility onActivate={() => insertDraftText(" ")} />
              <DwellKey label="Enter" utility onActivate={() => insertDraftText("\n")} />
              <DwellKey
                label="Clear"
                utility
                onActivate={() => {
                  setDraft("");
                  draftRef.current?.focus();
                }}
              />
            </div>
          </div>
        )}
        <div className="suggestions" aria-live="polite">
          {suggestions.map((item) => (
            <button key={item.word} className="suggestion" onClick={() => useSuggestion(item.word)}>
              {item.word}<span>Tab</span>
            </button>
          ))}
          {!suggestions.length && <span className="hint">Suggestions appear as you type. Your text stays on this device.</span>}
        </div>
        <div className="learn-row">
          <span className="hint">Only word-transition counts are saved locally; original phrases are not stored.</span>
          <button className="secondary" disabled={!draft.trim()} onClick={learnPhrase}>Learn phrase</button>
        </div>
      </section>

      <section className="status-row">
        <div><span className="status-dot" /> Last heard <strong>{voice.last_transcript || "Nothing yet"}</strong></div>
        <div>Last action <strong>{action?.action || action?.message || "—"}</strong></div>
      </section>
      {(message || voice.error) && <div className={`notice ${voice.error || startupError ? "error" : ""}`}>{voice.error || message}</div>}
        </>
      )}
      <footer>Privacy by design <span>•</span> Camera, audio, and autocomplete data stay local</footer>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
