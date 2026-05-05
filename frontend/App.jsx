import { useState, useEffect, useRef } from "react";

const API = "http://localhost:8000";

/* ─── tiny fetch wrapper ─────────────────────────────────────────── */
async function api(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return { ok: res.ok, status: res.status, data };
}

/* ─── Screens ────────────────────────────────────────────────────── */

function EmailScreen({ onSuccess, onAlreadyRegistered }) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!email.trim()) return;
    setLoading(true);
    const { ok, status, data } = await api("/register", { email });
    setLoading(false);

    if (ok) {
      onSuccess(email);
    } else if (status === 409) {
      onAlreadyRegistered();
    } else {
      setError(data?.detail?.message || data?.detail || "Something went wrong.");
    }
  }

  return (
    <div className="card fade-in">
      <div className="card-icon">✉️</div>
      <h1 className="card-title">Create your account</h1>
      <p className="card-sub">Enter your email to get started. We'll send a verification code.</p>

      <form onSubmit={handleSubmit}>
        <div className="field-wrap">
          <input
            type="email"
            className="input"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={loading}
            required
            autoFocus
          />
        </div>
        {error && <p className="msg msg--error">{error}</p>}
        <button type="submit" className="btn btn--primary" disabled={loading}>
          {loading ? <span className="spinner" /> : "Send OTP"}
        </button>
      </form>
    </div>
  );
}

function OTPScreen({ email, onSuccess, onFailure }) {
  const [digits, setDigits] = useState(["", "", "", "", "", ""]);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState("");
  const [resendMsg, setResendMsg] = useState("");
  const [countdown, setCountdown] = useState(60); // 1 min
  const inputRefs = useRef([]);

  /* countdown timer */
  useEffect(() => {
    if (countdown <= 0) return;
    const t = setInterval(() => setCountdown((c) => c - 1), 1000);
    return () => clearInterval(t);
  }, []);

  const mm = String(Math.floor(countdown / 60)).padStart(2, "0");
  const ss = String(countdown % 60).padStart(2, "0");

  function handleDigit(i, val) {
    if (!/^\d*$/.test(val)) return;
    const next = [...digits];
    next[i] = val.slice(-1);
    setDigits(next);
    if (val && i < 5) inputRefs.current[i + 1]?.focus();
  }

  function handleKeyDown(i, e) {
    if (e.key === "Backspace" && !digits[i] && i > 0) {
      inputRefs.current[i - 1]?.focus();
    }
  }

  function handlePaste(e) {
    const text = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!text) return;
    e.preventDefault();
    const next = [...digits];
    [...text].forEach((ch, i) => { next[i] = ch; });
    setDigits(next);
    inputRefs.current[Math.min(text.length, 5)]?.focus();
  }

  async function handleVerify(e) {
    e.preventDefault();
    const otp = digits.join("");
    if (otp.length !== 6) { setError("Please enter all 6 digits."); return; }
    setError("");
    setLoading(true);
    const { ok, data } = await api("/verify-otp", { email, otp });
    setLoading(false);

    if (ok) {
      onSuccess();
    } else {
      const msg = data?.detail?.message || data?.detail || "Verification failed.";
      if (msg.toLowerCase().includes("expired") || msg.toLowerCase().includes("attempt")) {
        onFailure(msg);
      } else {
        setError(msg);
      }
    }
  }

  async function handleResend() {
    setResendMsg("");
    setError("");
    setResending(true);
    const { ok, data } = await api("/resend-otp", { email });
    setResending(false);
    if (ok) {
      setCountdown(60);
      setDigits(["", "", "", "", "", ""]);
      setResendMsg("A new OTP has been sent!");
    } else {
      setError(data?.detail?.message || "Failed to resend.");
    }
  }

  return (
    <div className="card fade-in">
      <div className="card-icon">🔐</div>
      <h1 className="card-title">Check your inbox</h1>
      <p className="card-sub">
        We sent a 6-digit code to <strong>{email}</strong>
      </p>

      <form onSubmit={handleVerify}>
        <div className="otp-row" onPaste={handlePaste}>
          {digits.map((d, i) => (
            <input
              key={i}
              ref={(el) => (inputRefs.current[i] = el)}
              className="otp-box"
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={d}
              onChange={(e) => handleDigit(i, e.target.value)}
              onKeyDown={(e) => handleKeyDown(i, e)}
              disabled={loading}
            />
          ))}
        </div>

        <div className="timer">
          {countdown > 0 ? (
            <span>Code expires in <strong>{mm}:{ss}</strong></span>
          ) : (
            <span className="expired">Code expired</span>
          )}
        </div>

        {error && <p className="msg msg--error">{error}</p>}
        {resendMsg && <p className="msg msg--ok">{resendMsg}</p>}

        <button type="submit" className="btn btn--primary" disabled={loading}>
          {loading ? <span className="spinner" /> : "Verify"}
        </button>
      </form>

      <button className="btn btn--ghost" onClick={handleResend} disabled={resending}>
        {resending ? "Sending…" : "Resend OTP"}
      </button>
    </div>
  );
}

function ResultScreen({ kind }) {
  const isSuccess = kind === "success";
  const isAlready = kind === "already";

  return (
    <div className={`card result-card fade-in ${isSuccess ? "result-success" : "result-fail"}`}>
      <div className="result-icon">{isSuccess ? "✅" : isAlready ? "⚠️" : "❌"}</div>

      {isSuccess && (
        <>
          <p className="success-label">Registration Successful!</p>
          <p className="result-sub">Your account has been created and verified.</p>
        </>
      )}
      {isAlready && (
        <>
          <p className="fail-label">User already registered</p>
          <p className="result-sub">This email is already associated with an account.</p>
        </>
      )}
      {kind === "failure" && (
        <>
          <p className="fail-label">Registration Unsuccessful</p>
          <p className="result-sub">OTP verification failed. Please try again.</p>
        </>
      )}
    </div>
  );
}

/* ─── Main App ───────────────────────────────────────────────────── */

export default function App() {
  // screen: "email" | "otp" | "success" | "already" | "failure"
  const [screen, setScreen] = useState("email");
  const [email, setEmail] = useState("");

  return (
    <div className="page">
      <div className="bg-blob blob1" />
      <div className="bg-blob blob2" />

      <header className="page-header">
        <span className="logo">⬡ Register</span>
      </header>

      <main className="page-main">
        {screen === "email" && (
          <EmailScreen
            onSuccess={(em) => { setEmail(em); setScreen("otp"); }}
            onAlreadyRegistered={() => setScreen("already")}
          />
        )}
        {screen === "otp" && (
          <OTPScreen
            email={email}
            onSuccess={() => setScreen("success")}
            onFailure={() => setScreen("failure")}
          />
        )}
        {(screen === "success" || screen === "already" || screen === "failure") && (
          <ResultScreen kind={screen} />
        )}

        {(screen === "already" || screen === "failure") && (
          <button
            className="btn btn--ghost back-btn"
            onClick={() => setScreen("email")}
          >
            ← Try again
          </button>
        )}
      </main>
    </div>
  );
}
