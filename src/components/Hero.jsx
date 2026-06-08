const Hero = () => {
  return React.createElement("section", { id: "\u9996\u9875", style: { position: "relative", height: "100vh", overflow: "hidden", minHeight: 700 } },
    React.createElement("spline-viewer", {
      style: { position: "absolute", inset: 0, width: "100%", height: "100%", zIndex: 0 },
      url: "https://prod.spline.design/VIewdGKTd-X0WEFE/scene.splinecode"
    }),
    React.createElement("div", { style: { position: "absolute", bottom: 0, left: 0, right: 0, height: 200, zIndex: 1, background: "linear-gradient(to top, var(--bg-deep) 0%, transparent 100%)" } }),
    React.createElement("div", { style: { position: "absolute", bottom: 0, right: 0, zIndex: 2, width: 250, height: 80 } }),
    React.createElement("div", { style: { position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", zIndex: 2 } },
      React.createElement("div", { style: { animation: "fadeInUp 0.8s ease-out both 0.5s" } },
        React.createElement("span", { onClick: function(){ var el = document.getElementById("\u4f5c\u54c1"); if(el) el.scrollIntoView({ behavior: "smooth" }); }, style: { display: "inline-block", padding: "16px 80px", borderRadius: 50, background: "rgba(255,255,255,0.2)", color: "rgba(255,255,255,0.95)", fontWeight: 600, fontSize: 17, border: "1px solid rgba(255,255,255,0.4)", cursor: "pointer", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)", letterSpacing: "0.5px", transition: "all 0.3s" }, onMouseEnter: function(e){ e.currentTarget.style.borderColor="rgba(255,255,255,0.6)"; e.currentTarget.style.background="rgba(255,255,255,0.3)"; e.currentTarget.style.transform="scale(1.03)"; }, onMouseLeave: function(e){ e.currentTarget.style.borderColor="rgba(255,255,255,0.4)"; e.currentTarget.style.background="rgba(255,255,255,0.2)"; e.currentTarget.style.transform="scale(1)"; } }, "\u63a2\u7d22 \u529f\u80fd \u2192")
      )
    ),
    React.createElement("style", null, "spline-viewer { overflow: hidden; } spline-viewer canvas + div:last-child { opacity: 0 !important; pointer-events: none !important; } @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }")
  );
};