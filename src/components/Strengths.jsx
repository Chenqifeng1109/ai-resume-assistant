const Strengths = () => {
  React.useEffect(() => {
    var el = document.getElementById("vanta-bg");
    if (!el || el._vanta) return;
    if (typeof VANTA === "undefined") return;
    el._vanta = VANTA.NET({
      el: el,
      color: 0x00d4ff,
      backgroundColor: 0x050508,
      points: 12,
      maxDistance: 22,
      spacing: 18,
      showDots: false
    });
    return () => { if (el && el._vanta) { el._vanta.destroy(); el._vanta = null; } };
  }, []);
  const strengths = [
    { icon: "🎨", title: "视觉设计", desc: "擅长从0到1构建设计语言系统，让每个品牌拥有独特的视觉识别力", items: ["品牌VI设计","UI/UX设计","3D视觉","动态设计"] },
    { icon: "🤖", title: "AI 设计", desc: "深度整合AI工具链到设计工作流，用Stable Diffusion、Midjourney、DeepSeek提升创作效率", items: ["AI图像生成","Prompt工程","AI工作流","智能工具开发"] },
    { icon: "💻", title: "全栈开发", desc: "具备完整的前后端开发能力，能将设计构想直接落地为可运行的产品，缩短从想法到上线的距离", items: ["React/Vue","Python/FastAPI","Three.js","全栈部署"] },
    { icon: "🚀", title: "品牌策略", desc: "不止做设计，更关注品牌背后的商业逻辑，用设计驱动增长，让每个像素都为品牌创造价值", items: ["品牌定位","设计策略","用户体验","增长设计"] }
  ];

  return (
    <section id="优势" className="section" style={{ background: "var(--bg-surface)", position: "relative", overflow: "hidden" }}>
      <div style={{ height: 100, background: "linear-gradient(180deg, var(--bg-deep) 0%, transparent 100%)", position: "relative", zIndex: 2, pointerEvents: "none", marginTop: 0 }} />
      <div id="vanta-bg" style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none" }} />
      <div className="container" style={{ position: "relative", zIndex: 1 }}>
        <div className="section-label">Capabilities</div>
        <h2 className="section-title">个人优势</h2>
        <p className="section-desc">跨界融合的设计与技术能力，为每一个项目带来独特价值</p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 20, marginTop: 60 }}>
          {strengths.map((s, i) => (
            <div key={i} style={{
              background: "var(--bg-card)", borderRadius: "var(--radius-lg)", padding: "32px 28px",
              border: "1px solid var(--border)", transition: "var(--transition)",
              display: "flex", flexDirection: "column", gap: 16
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.boxShadow = "0 0 40px var(--accent-glow)"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.boxShadow = "none"; }}
            >
              <div style={{ fontSize: 40 }}>{s.icon}</div>
              <h3 style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.01em" }}>{s.title}</h3>
              <p style={{ fontSize: 14, color: "var(--text-dim)", lineHeight: 1.7, flex: 1 }}>{s.desc}</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {s.items.map(item => (
                  <span key={item} style={{ padding: "4px 12px", borderRadius: 20, fontSize: 11, background: "rgba(124,77,255,0.08)", color: "var(--accent2)", border: "1px solid rgba(124,77,255,0.2)" }}>{item}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
              <div style={{ height: 120, background: "linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-deep) 100%)", marginBottom: 0, position: "relative", zIndex: 2, pointerEvents: "none" }} />
    </section>  );
};