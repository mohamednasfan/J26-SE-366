const state = {
  drug1: { id: "", name: "" },
  drug2: { id: "", name: "" },
};

const byId = (id) => document.getElementById(id);

function setError(message) {
  byId("form-error").textContent = message;
}

function chooseDrug(slot, drug) {
  state[slot] = { id: drug.drug_id, name: drug.display_name };
  byId(`${slot}-id`).value = drug.drug_id;
  byId(`${slot}-search`).value = drug.display_name;
  byId(`${slot}-selected`).textContent = `${drug.display_name} · ${drug.drug_id}`;
  byId(`${slot}-selected`).classList.add("is-selected");
  byId(`${slot}-results`).replaceChildren();
}

function renderSuggestions(slot, results) {
  const container = byId(`${slot}-results`);
  container.replaceChildren(...results.map((drug) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "suggestion";
    button.innerHTML = `${drug.display_name}<small>${drug.drug_id}</small>`;
    button.addEventListener("click", () => chooseDrug(slot, drug));
    return button;
  }));
}

async function searchDrugs(slot, query) {
  if (query.trim().length < 2) {
    byId(`${slot}-results`).replaceChildren();
    return;
  }
  try {
    const response = await fetch(`/api/s2/drugs?q=${encodeURIComponent(query)}&limit=8`);
    if (!response.ok) throw new Error("Drug search failed.");
    renderSuggestions(slot, (await response.json()).results);
  } catch (error) {
    setError(error.message);
  }
}

function connectSearch(slot) {
  const input = byId(`${slot}-search`);
  let timer;
  input.addEventListener("input", () => {
    if (input.value !== state[slot].name) {
      state[slot] = { id: "", name: "" };
      byId(`${slot}-id`).value = "";
      byId(`${slot}-selected`).textContent = "No drug selected";
      byId(`${slot}-selected`).classList.remove("is-selected");
    }
    clearTimeout(timer);
    timer = setTimeout(() => searchDrugs(slot, input.value), 250);
  });
}

function renderResult(result) {
  const interaction = result.interaction_flag;
  const score = result.model_score;
  byId("result-card").classList.remove("hidden");
  byId("result-badge").textContent = interaction ? "Interaction detected" : "No interaction detected";
  byId("result-badge").className = `result-badge ${interaction ? "interaction" : "no-interaction"}`;
  byId("result-icon").textContent = interaction ? "!" : "✓";
  byId("result-icon").className = `result-icon ${interaction ? "interaction" : ""}`;
  byId("result-heading").textContent = interaction
    ? "Possible interaction signal"
    : "No interaction signal detected";
  byId("result-description").textContent =
    `${result.drug1_name} + ${result.drug2_name}`;
  byId("score-value").textContent = score.toFixed(3);
  byId("score-bar").style.width = `${Math.max(0, Math.min(score, 1)) * 100}%`;
  byId("threshold-text").textContent =
    `Decision threshold: ${result.threshold.toFixed(3)} · Score at or above this value is flagged.`;
  byId("explanation-summary").textContent =
    `${result.explanation.method}. Contributions show how the model reached its result.`;
  byId("feature-list").replaceChildren(...result.explanation.top_features.slice(0, 5).map((feature) => {
    const row = document.createElement("div");
    row.className = "feature-row";
    const direction = feature.contribution >= 0 ? "+" : "";
    row.innerHTML = `<span>${feature.feature_group} · bit ${feature.bit_index}</span><strong>${direction}${feature.contribution.toFixed(3)}</strong>`;
    return row;
  }));
  byId("notice").textContent = result.notice;
  byId("result-card").scrollIntoView({ behavior: "smooth", block: "start" });
}

byId("prediction-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setError("");
  if (!state.drug1.id || !state.drug2.id) {
    setError("Please select both drugs from the search suggestions.");
    return;
  }
  if (state.drug1.id === state.drug2.id) {
    setError("Please select two different drugs.");
    return;
  }
  const button = byId("check-button");
  button.disabled = true;
  button.querySelector("span").textContent = "Checking...";
  try {
    const response = await fetch("/api/s2/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        drug1_id: state.drug1.id,
        drug2_id: state.drug2.id,
        top_k: 5,
        mode: "cold_start",
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Prediction failed.");
    renderResult(payload);
  } catch (error) {
    setError(error.message);
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "Check interaction";
  }
});

connectSearch("drug1");
connectSearch("drug2");
