// js/script.js

const searchInput = document.getElementById("searchInput");
const resultsContainer = document.getElementById("resultsContainer");

let metadata = {};

// charge metadata.json (doit être à la racine : EliteKits/metadata.json)
fetch("metadata.json")
  .then(res => {
    if (!res.ok) throw new Error("metadata.json introuvable");
    return res.json();
  })
  .then(data => {
    metadata = data;
    console.log("Metadata chargée :", Object.keys(metadata).length, "images");
  })
  .catch(err => {
    console.error("Erreur chargement metadata:", err);
  });

// utilitaire : normalize path (si metadata contient "fan/xxx.jpg" on renvoie "images/fan/xxx.jpg")
function normalizeSrc(path) {
  if (!path) return "";
  // si path commence par http ou / ou images/ on garde
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("/")) return path;
  if (path.startsWith("images/")) return path;
  // sinon on suppose qu'il s'agit d'un chemin relatif comme "fan/medium-1.jpg"
  return `images/${path}`;
}

function createCard(src, team, score) {
  const card = document.createElement("div");
  card.className = "product-card";
  card.innerHTML = `
    <a href="${src}" target="_blank" class="card-link">
      <img src="${src}" alt="${team || "Maillot"}" loading="lazy">
      <div class="card-info">
        <p class="team">${team || "Inconnu"}</p>
        ${score ? `<small class="score">score: ${Number(score).toFixed(2)}</small>` : ""}
      </div>
    </a>
  `;
  return card;
}

function searchTeam(query) {
  resultsContainer.innerHTML = "";
  if (!query) return;
  const q = query.toLowerCase();
  let found = 0;

  for (const [path, info] of Object.entries(metadata)) {
    const team = (info && info.team) ? String(info.team) : "";
    if (team.toLowerCase().includes(q)) {
      const src = normalizeSrc(path);
      resultsContainer.appendChild(createCard(src, team, info.score));
      found++;
    }
  }

  if (found === 0) {
    resultsContainer.innerHTML = "<p>Aucun maillot trouvé.</p>";
  }
}

// écoute
searchInput.addEventListener("input", e => {
  const q = e.target.value.trim();
  searchTeam(q);
});
