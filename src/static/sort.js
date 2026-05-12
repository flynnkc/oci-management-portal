function sortCardsByCost() {
  const container = document.getElementById("inventory");
  if (!container) return;

  const cards = Array.from(container.querySelectorAll("form.card"));
  if (cards.length === 0) return;

  cards.sort((a, b) => {
    const costA = parseFloat(a.dataset.cost || 0);
    const costB = parseFloat(b.dataset.cost || 0);
    return costB - costA;
  });

  cards.forEach((card) => container.appendChild(card));
}

document.body.addEventListener("htmx:afterSwap", function (evt) {
  if (evt.target && evt.target.id === "inventory") {
    sortCardsByCost();
  }
});

document.addEventListener("DOMContentLoaded", function () {
  sortCardsByCost();
});
