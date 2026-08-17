// Inside a module, the version that matters is the module's, not the site's.
//
// A documentation snapshot pins one version of every module, so switching module version
// means moving to the snapshot that pinned it, on the same page. The header selector is
// rewritten to offer those, and left alone everywhere else, where the site version is what
// a reader is choosing between.

function pageParts() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  const at = parts.indexOf("modules");
  if (at < 0 || !parts[at + 1]) return null;
  return {
    docs: at > 0 ? parts.slice(0, at).join("/") : "",
    module: parts[at + 1],
    rest: parts.slice(at).join("/"),
  };
}

function rewrite(selector, module, entries, docs) {
  const current = entries.find((entry) => entry.docs === docs) || entries[0];
  const button = selector.querySelector(".md-version__current");
  if (button) button.textContent = `${module} ${current.label}`;

  const list = selector.querySelector(".md-version__list");
  if (!list) return;
  list.replaceChildren(...entries.map((entry) => {
    const item = document.createElement("li");
    item.className = "md-version__item";
    const link = document.createElement("a");
    link.className = "md-version__link";
    link.href = `/${entry.docs}/${pageParts().rest}`;
    link.textContent = `${module} ${entry.label}`;
    item.appendChild(link);
    return item;
  }));
}

async function moduleVersionSelector() {
  const parts = pageParts();
  if (!parts) return;
  let catalogue;
  try {
    const response = await fetch(`/${parts.docs}/module-versions.json`);
    if (!response.ok) return;
    catalogue = await response.json();
  } catch {
    return;
  }
  const entry = catalogue[parts.module];
  if (!entry || entry.versions.length < 2) return;

  // The site selector is built by the theme after load, so wait for it rather than
  // assuming it is there.
  const observer = new MutationObserver(() => {
    const selector = document.querySelector(".md-version");
    if (selector) {
      observer.disconnect();
      rewrite(selector, parts.module, entry.versions, parts.docs);
    }
  });
  const selector = document.querySelector(".md-version");
  if (selector) rewrite(selector, parts.module, entry.versions, parts.docs);
  else observer.observe(document.body, { childList: true, subtree: true });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", moduleVersionSelector);
} else {
  moduleVersionSelector();
}
