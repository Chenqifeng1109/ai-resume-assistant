const Projects = () => {
  const scrollTo = (id) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const projects = [
    { title: "AI 智能简历助手", tags: ["FastAPI", "DeepSeek", "全栈"], desc: "全栈AI求职工具，支持简历解析、岗位采集、智能匹配、一键投递。点击查看在线演示 →", img: "https://images.unsplash.com/photo-1633356122544-f134324a6cee?w=800&q=80", color: "#00d4ff", target: "功能" },
    { title: "品牌视觉项目", tags: ["Branding", "Figma"], desc: "即将上线，敬请期待", img: "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=800&q=80", color: "#7c4dff", target: null },
    { title: "数据可视化看板", tags: ["React", "D3.js"], desc: "即将上线，敬请期待", img: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&q=80", color: "#00e676", target: null },
    { title: "3D交互产品展示", tags: ["Three.js", "WebGL"], desc: "即将上线，敬请期待", img: "https://images.unsplash.com/photo-1633356122102-3fe601e05bd2?w=800&q=80", color: "#ff6d00", target: null }
  ];

  return (
    <section id="作品" className="section" style={{ position: "relative", overflow: "hidden" }}>
            <spline-viewer style={{ position: "absolute", inset: 0, width: "100%", height: "100%", zIndex: 0, pointerEvents: "none", opacity: 0.4 }} url="https://prod.spline.design/wSr4Sbr76TLnhCgV/scene.splinecode" />
      <div style={{ position: "absolute", inset: 0, zIndex: 0, background: "linear-gradient(180deg, var(--bg-deep) 0%, transparent 30%, transparent 70%, var(--bg-deep) 100%)", pointerEvents: "none" }} />
      <div className="container" style={{ position: "relative", zIndex: 1 }}>
        <div className="section-label">Selected Works</div>
        <h2 className="section-title">精选项目</h2>
        <p className="section-desc">每个项目都是对设计与技术的深度探索，点击卡片了解更多</p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 24, marginTop: 60 }}>
          {projects.map((p, i) => (
            <div key={i} style={{
              background: "var(--bg-card)", borderRadius: "var(--radius-lg)",
              border: `1px solid var(--border)`, overflow: "hidden",
              transition: "var(--transition)", cursor: p.target ? "pointer" : "default",
              position: "relative", opacity: p.target ? 1 : 0.5
            }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = p.color;
                if (p.target) e.currentTarget.style.transform = "translateY(-6px)";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.transform = "translateY(0)";
              }}
              onClick={() => p.target && scrollTo(p.target)}
            >
              <div style={{ height: 240, overflow: "hidden", position: "relative" }}>
                <div style={{ position: "absolute", inset: 0, background: `linear-gradient(180deg, transparent 50%, var(--bg-card) 100%)`, zIndex: 1 }} />
                <img src={p.img} alt={p.title} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                {!p.target && (
                  <div style={{ position: "absolute", inset: 0, zIndex: 2, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <span style={{ padding: "8px 20px", borderRadius: 50, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)", color: "var(--text-dim)", fontSize: 13, fontWeight: 500 }}>🚧 即将上线</span>
                  </div>
                )}
              </div>
              <div style={{ padding: "28px 32px 32px" }}>
                <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
                  {p.tags.map(t => (
                    <span key={t} style={{ padding: "3px 12px", borderRadius: 20, fontSize: 11, fontWeight: 500, background: "rgba(124,77,255,0.1)", color: "var(--accent2)", border: "1px solid rgba(124,77,255,0.2)" }}>{t}</span>
                  ))}
                  {p.target && (
                    <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--accent)", display: "flex", alignItems: "center", gap: 4 }}>
                      在线演示 <span style={{ fontSize: 14 }}>↗</span>
                    </span>
                  )}
                </div>
                <h3 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8, letterSpacing: "-0.01em" }}>{p.title}</h3>
                <p style={{ fontSize: 14, color: "var(--text-dim)", lineHeight: 1.7 }}>{p.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
          <div style={{ height: 120, background: "linear-gradient(180deg, transparent 0%, var(--bg-surface) 100%)", pointerEvents: "none", position: "relative", zIndex: 2 }} />
    </section>
  );
};
