const App = () => {
  return (
    <div>
      <Navbar />
      <Hero />
      <Projects />
      <AIAssistant />
      <Strengths />
      <Footer />
    </div>
  );
};

ReactDOM.render(<App />, document.getElementById("root"));
