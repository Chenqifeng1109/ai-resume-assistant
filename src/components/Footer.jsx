const Footer = () => {
  React.useEffect(() => {
    var el = document.getElementById("vanta-dots");
    if (!el || el._vanta) return;
    if (typeof VANTA === "undefined") return;
    el._vanta = VANTA.DOTS({
      el: el,
      color: 0x00d4ff,
      color2: 0x7c4dff,
      backgroundColor: 0x0a0a0f,
      size: 3,
      spacing: 25,
      showLines: true
    });
    return () => { if (el && el._vanta) { el._vanta.destroy(); el._vanta = null; } };
  }, []);
  const [form, setForm] = React.useState({ name: "", email: "", message: "" });

  return (
    <section id="联系" style={{ position: "relative", overflow: "hidden",
      position: "relative", minHeight: "100vh", display: "flex", alignItems: "center",
      background: "linear-gradient(180deg, var(--bg-deep) 0%, #020208 100%)",
      borderTop: "1px solid var(--border)"
    }}>
      {/* Background decoration */}
      <div id="vanta-dots" style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none" }} />
      <div style={{ position: "absolute", inset: 0, zIndex: 0, background: "rgba(5,5,8,0.3)" }} />
      <div style={{ position: "absolute", top: "20%", right: "10%", width: 400, height: 400, borderRadius: "50%", background: "radial-gradient(circle, rgba(0,212,255,0.06) 0%, transparent 70%)", filter: "blur(60px)" }} />
      <div style={{ position: "absolute", bottom: "10%", left: "5%", width: 300, height: 300, borderRadius: "50%", background: "radial-gradient(circle, rgba(124,77,255,0.06) 0%, transparent 70%)", filter: "blur(60px)" }} />
      <div style={{ position: "absolute", inset: 0, zIndex: 0, background: "linear-gradient(180deg, var(--bg-deep) 0%, transparent 20%, transparent 80%, var(--bg-deep) 100%)", pointerEvents: "none" }} />
<div className="container" style={{ position: "relative", zIndex: 1, width: "100%" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 80, alignItems: "center" }}>
          {/* Left - Info */}
          <div>
            <div className="section-label">Get in Touch</div>
            <h2 style={{ fontSize: "clamp(36px, 5vw, 56px)", fontWeight: 700, lineHeight: 1.15, letterSpacing: "-0.02em", marginBottom: 20 }}>
              开始你的<span style={{ background: "linear-gradient(135deg, var(--accent), var(--accent2))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>下一个</span>
              <br />项目合作
            </h2>
            <p style={{ fontSize: 18, color: "var(--text-dim)", lineHeight: 1.7, marginBottom: 40 }}>
              无论你想做一个品牌网站、AI工具，还是需要完整的设计方案，都欢迎联系我
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {[
                { icon: "📧", text: "2367538177@qq.com" },
                { icon: "📍", text: "中国 · 广州" },
                { icon: "💬", text: "微信: Clex620" }
              ].map((item, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 15, color: "var(--text-dim)" }}>
                  <span style={{ fontSize: 18 }}>{item.icon}</span>
                  <span>{item.text}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right - Form */}
          <div style={{
            background: "var(--bg-card)", borderRadius: "var(--radius-lg)",
            border: "1px solid var(--border)", padding: "48px 40px"
          }}>
            <h3 style={{ fontSize: 24, fontWeight: 700, marginBottom: 32, letterSpacing: "-0.01em" }}>发送消息</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--text-dim)", marginBottom: 8, letterSpacing: 1, textTransform: "uppercase" }}>姓名</label>
                <input type="text" value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                  style={{ width: "100%", padding: "14px 18px", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", color: "var(--text)", fontSize: 15, outline: "none", fontFamily: "var(--font-sans)", transition: "var(--transition)" }}
                  onFocus={e => e.target.style.borderColor = "var(--accent)"}
                  onBlur={e => e.target.style.borderColor = "var(--border)"}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--text-dim)", marginBottom: 8, letterSpacing: 1, textTransform: "uppercase" }}>邮箱</label>
                <input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})}
                  style={{ width: "100%", padding: "14px 18px", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", color: "var(--text)", fontSize: 15, outline: "none", fontFamily: "var(--font-sans)", transition: "var(--transition)" }}
                  onFocus={e => e.target.style.borderColor = "var(--accent)"}
                  onBlur={e => e.target.style.borderColor = "var(--border)"}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--text-dim)", marginBottom: 8, letterSpacing: 1, textTransform: "uppercase" }}>消息</label>
                <textarea rows={4} value={form.message} onChange={e => setForm({...form, message: e.target.value})}
                  style={{ width: "100%", padding: "14px 18px", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", color: "var(--text)", fontSize: 15, outline: "none", fontFamily: "var(--font-sans)", resize: "vertical", transition: "var(--transition)" }}
                  onFocus={e => e.target.style.borderColor = "var(--accent)"}
                  onBlur={e => e.target.style.borderColor = "var(--border)"}
                />
              </div>
              <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center", marginTop: 8 }}>发送消息 →</button>
            </div>
          </div>
        </div>

        {/* Copyright */}
        <div style={{ marginTop: 80, paddingTop: 32, borderTop: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "var(--text-muted)" }}>© 2026 QZDESIGN. All rights reserved.</span>
          <div style={{ display: "flex", gap: 32 }}></div>
        </div>
      </div>
    </section>  );
};