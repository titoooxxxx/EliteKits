// === script.js ===

// Sélection des éléments du DOM
const searchInput = document.getElementById("searchInput");
const resultsContainer = document.getElementById("resultsContainer");

// Charger le fichier metadata.json
let metadata = {};

fetch("metadata.json")
  .then(response => {
    if (!response.ok) {
      throw new Error("Erreur lors du chargement de metadata.json");
    }
    return response.json();
  })
  .then(data => {
    metadata = data;
    console.log("✅ Metadata chargée :", Object.keys(metadata).length, "images");
  })
  .catch(error => {
    console.error("❌ Erreur de chargement metadata :", error);
  });

// Fonction de recherche
function searchTeam(query) {
  resultsContainer.innerHTML = "";

  if (!query) return;

  query = query.toLowerCase();
  let found = false;

  for (const [path, info] of Object.entries(metadata)) {
    if (info.team && info.team.toLowerCase().includes(query)) {
      found = true;

      const card = document.createElement("div");
      card.classList.add("product-card");
      card.innerHTML = `
        <img src="images/${path}" alt="${info.team}">
        <p>${info.team}</p>
      `;
      resultsContainer.appendChild(card);
    }
  }

  if (!found) {
    resultsContainer.innerHTML = "<p>Aucun maillot trouvé.</p>";
  }
}

// Événement sur la recherche
searchInput.addEventListener("input", e => {
  const query = e.target.value.trim();
  searchTeam(query);
});
// === Animation d'apparition au scroll ===
const reveals = document.querySelectorAll(".reveal");

function revealOnScroll() {
  for (let i = 0; i < reveals.length; i++) {
    const windowHeight = window.innerHeight;
    const elementTop = reveals[i].getBoundingClientRect().top;
    const revealPoint = 150;

    if (elementTop < windowHeight - revealPoint) {
      reveals[i].classList.add("active");
    }
  }
}

window.addEventListener("scroll", revealOnScroll);

