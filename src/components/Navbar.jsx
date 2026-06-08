const Navbar = () => {
  const [scrolled, setScrolled] = React.useState(false);
  React.useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const navStyle = {
    position: "fixed", top: 0, left: 0, right: 0, zIndex: 1000,
    padding: scrolled ? "12px 0" : "24px 0",
    background: scrolled ? "rgba(5,5,8,0.85)" : "transparent",
    backdropFilter: scrolled ? "blur(20px)" : "none",
    borderBottom: scrolled ? "1px solid var(--border)" : "1px solid transparent",
    transition: "all 0.3s cubic-bezier(0.4,0,0.2,1)"
  };

  return (
    <nav style={navStyle}>
      <div className="container" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{ width: 36, height: 36, borderRadius: "50%", background: "linear-gradient(135deg, var(--accent), var(--accent2))", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 16, color: "#000" }}>Q</div>
          <span style={{ fontWeight: 900, fontSize: 20, letterSpacing: "-0.02em", fontFamily: '"SimHei", "Microsoft YaHei", sans-serif', color: "#fff", textShadow: "0 0 20px rgba(0,212,255,0.5)" }}>CHEN</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "40px" }}>
          {["首页","作品","功能","优势","联系"].map(item => (
            <a key={item} href={`#${item}`} style={{ color: "var(--text-dim)", textDecoration: "none", fontSize: 14, fontWeight: 500, transition: "color 0.2s" }}
              onMouseEnter={e => e.target.style.color = "var(--text)"}
              onMouseLeave={e => e.target.style.color = "var(--text-dim)"}
            >{item}</a>
          ))}

        </div>
      </div>
    </nav>
  );
};
