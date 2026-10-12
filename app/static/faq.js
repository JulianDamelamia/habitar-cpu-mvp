(() => {
  const search = document.querySelector("#faq-search");
  const items = Array.from(document.querySelectorAll(".faq-item"));
  const empty = document.querySelector("#faq-empty");
  const contactCta = document.querySelector("#faq-contact-cta");
  const contactForm = document.querySelector("#faq-contact-form");
  const searchContext = document.querySelector("#faq-search-context");
  const contactBody = document.querySelector("#faq-contact-body");

  if (!search || !empty) return;

  const normalize = (value) =>
    value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();

  search.addEventListener("input", () => {
    const query = normalize(search.value.trim());
    let visible = 0;
    items.forEach((item) => {
      const matches = normalize(item.dataset.search || "").includes(query);
      item.classList.toggle("hidden", !matches);
      if (matches) visible += 1;
    });
    const noMatches = query.length > 0 && visible === 0;
    empty.classList.toggle("hidden", !noMatches);
    contactCta?.classList.toggle("hidden", !noMatches);
    if (searchContext) searchContext.value = search.value.trim();
    if (contactBody && contactForm?.classList.contains("hidden")) {
      contactBody.value = query ? `Busqué: ${search.value.trim()}\n\n` : "";
    }
  });

  document.querySelector("#faq-contact-open")?.addEventListener("click", () => {
    if (searchContext) searchContext.value = search.value.trim();
    contactForm?.classList.remove("hidden");
    contactForm?.classList.add("faq-contact-form-visible");
    contactBody?.focus();
  });

  document.querySelector("#faq-contact-cancel")?.addEventListener("click", () => {
    contactForm?.classList.add("hidden");
    contactForm?.classList.remove("faq-contact-form-visible");
  });
})();
