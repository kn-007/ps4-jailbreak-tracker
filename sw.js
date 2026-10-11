function createCard(item) {
  const tags = (item.reasons || [])
    .filter(r => !["PS4", "14.00"].includes(r))
    .slice(0, 4)
    .map(r => `<span class="tag \( {r.toLowerCase()}"> \){r}</span>`)
    .join("");

  return `
    <article class="card" onclick="window.open('${item.url}', '_blank')">
      <div class="card-header">
        <h3 class="card-title">${item.title}</h3>
        <span class="card-time">${formatTime(item.updated_at)}</span>
      </div>
      <p class="card-summary">${item.summary || ""}</p>
      <div class="card-tags">${tags}</div>
    </article>
  `;
}
