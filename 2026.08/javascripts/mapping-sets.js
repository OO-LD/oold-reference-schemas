// One RDF reading visible at a time, selected from the mapping-set dropdown.
// The blocks are rendered unhidden, so a reader without JavaScript sees every reading
// stacked instead of an empty tab.

function bindMappingSets() {
  document.querySelectorAll("select[data-mapping-select]").forEach((select) => {
    const group = select.getAttribute("data-mapping-select");
    const blocks = document.querySelectorAll(`.mapping-set[data-group="${group}"]`);
    const show = () => blocks.forEach((block) => {
      block.hidden = block.getAttribute("data-set") !== select.value;
    });
    select.addEventListener("change", show);
    show();
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bindMappingSets);
} else {
  bindMappingSets();
}
