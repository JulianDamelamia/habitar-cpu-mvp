(() => {
  const search = document.querySelector("#faq-search");
  const items = Array.from(document.querySelectorAll(".faq-item"));
  const empty = document.querySelector("#faq-empty");
  const contactCta = document.querySelector("#faq-contact-cta");
  const contactForm = document.querySelector("#faq-contact-form");
  const searchContext = document.querySelector("#faq-search-context");
  const contactBody = document.querySelector("#faq-contact-body");
  const categorySearch = document.querySelector("#faq-category-search");
  const categoryId = document.querySelector("#categoria_id");
  const categoryDropdown = document.querySelector("#faq-category-dropdown");
  const categoryEmpty = document.querySelector("#faq-category-empty");
  const adminCategorySearch = document.querySelector("#faq-admin-category-search");
  const adminCategoryDropdown = document.querySelector("#faq-admin-category-dropdown");
  const adminCategoryEmpty = document.querySelector("#faq-admin-category-empty");
  const normalize = (value) =>
    value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();

  document.querySelectorAll(".faq-category-edit-open").forEach((button) => {
    const row = button.closest("li");
    const name = row?.querySelector(".faq-category-name");
    const form = row?.querySelector(".faq-category-edit");
    const input = form?.querySelector('input[name="nombre"]');
    const cancel = form?.querySelector(".faq-category-edit-cancel");
    if (!row || !name || !(form instanceof HTMLFormElement) || !(input instanceof HTMLInputElement) || !cancel) {
      return;
    }

    const closeEditor = () => {
      input.value = name.textContent.trim();
      form.classList.add("hidden");
      name.classList.remove("hidden");
      button.classList.remove("hidden");
    };
    button.addEventListener("click", () => {
      form.classList.remove("hidden");
      name.classList.add("hidden");
      button.classList.add("hidden");
      input.focus();
      input.select();
    });
    cancel.addEventListener("click", closeEditor);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeEditor();
      }
    });
  });

  if (adminCategorySearch && adminCategoryDropdown) {
    const adminCategoryOptions = Array.from(
      adminCategoryDropdown.querySelectorAll(".faq-admin-category-option"),
    );
    const closeAdminCategoryDropdown = () => {
      adminCategoryDropdown.classList.add("hidden");
      adminCategorySearch.setAttribute("aria-expanded", "false");
    };
    const selectAdminCategory = (option) => {
      adminCategorySearch.value = option.dataset.name || option.textContent.trim();
      closeAdminCategoryDropdown();
      adminCategorySearch.focus();
    };
    const filterAdminCategories = () => {
      const query = normalize(adminCategorySearch.value.trim());
      let visible = 0;
      adminCategoryOptions.forEach((option) => {
        const matches = normalize(option.dataset.name || "").includes(query);
        option.classList.toggle("hidden", !matches);
        option.setAttribute("aria-selected", "false");
        if (matches) visible += 1;
      });
      adminCategoryEmpty?.classList.toggle("hidden", visible > 0);
      adminCategoryDropdown.classList.remove("hidden");
      adminCategorySearch.setAttribute("aria-expanded", "true");
    };

    adminCategorySearch.addEventListener("focus", filterAdminCategories);
    adminCategorySearch.addEventListener("click", filterAdminCategories);
    adminCategorySearch.addEventListener("input", filterAdminCategories);
    adminCategoryDropdown.addEventListener("pointerdown", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const option = target.closest(".faq-admin-category-option");
      if (!(option instanceof HTMLButtonElement) || option.classList.contains("hidden")) return;
      event.preventDefault();
      selectAdminCategory(option);
    });
    adminCategorySearch.addEventListener("keydown", (event) => {
      const visibleOptions = adminCategoryOptions.filter(
        (option) => !option.classList.contains("hidden"),
      );
      if (event.key === "ArrowDown" && visibleOptions.length) {
        event.preventDefault();
        visibleOptions[0].focus();
      } else if (event.key === "Enter" && visibleOptions.length === 1) {
        event.preventDefault();
        selectAdminCategory(visibleOptions[0]);
      } else if (event.key === "Escape") {
        closeAdminCategoryDropdown();
      }
    });
    adminCategoryDropdown.addEventListener("keydown", (event) => {
      const target = event.target;
      if (
        !(target instanceof HTMLButtonElement)
        || !target.classList.contains("faq-admin-category-option")
      ) {
        return;
      }
      const visibleOptions = adminCategoryOptions.filter(
        (option) => !option.classList.contains("hidden"),
      );
      const index = visibleOptions.indexOf(target);
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const direction = event.key === "ArrowDown" ? 1 : -1;
        visibleOptions[(index + direction + visibleOptions.length) % visibleOptions.length].focus();
      } else if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectAdminCategory(target);
      } else if (event.key === "Escape") {
        closeAdminCategoryDropdown();
        adminCategorySearch.focus();
      }
    });
    document.addEventListener("click", (event) => {
      const target = event.target;
      if (
        target instanceof Node
        && !adminCategoryDropdown.contains(target)
        && target !== adminCategorySearch
      ) {
        closeAdminCategoryDropdown();
      }
    });
  }

  if (!search || !empty) return;
  const categoryOptions = Array.from(
    categoryDropdown?.querySelectorAll(".category-option") || [],
  );

  const closeCategoryDropdown = () => {
    categoryDropdown?.classList.add("hidden");
    categorySearch?.setAttribute("aria-expanded", "false");
  };

  const filterCategories = () => {
    if (!categorySearch || !categoryDropdown) return;
    const query = normalize(categorySearch.value.trim());
    let visible = 0;
    categoryOptions.forEach((option) => {
      const matches = normalize(option.dataset.name || option.textContent || "").includes(query);
      option.classList.toggle("hidden", !matches);
      option.setAttribute("aria-selected", "false");
      if (matches) visible += 1;
    });
    categoryEmpty?.classList.toggle("hidden", visible > 0);
    categoryDropdown.classList.remove("hidden");
    categorySearch.setAttribute("aria-expanded", "true");
  };

  const selectCategory = (option) => {
    if (!categorySearch || !categoryId) return;
    categorySearch.value = option.dataset.name || option.textContent.trim();
    categoryId.value = option.dataset.id || "";
    option.setAttribute("aria-selected", "true");
    closeCategoryDropdown();
  };

  if (categorySearch && categoryDropdown && categoryId) {
    categorySearch.addEventListener("focus", filterCategories);
    categorySearch.addEventListener("input", () => {
      categoryId.value = "";
      filterCategories();
    });
    categoryDropdown.addEventListener("mousedown", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const option = target.closest(".category-option");
      if (option instanceof HTMLElement && !option.classList.contains("hidden")) {
        event.preventDefault();
        selectCategory(option);
      }
    });
    categorySearch.addEventListener("keydown", (event) => {
      const visibleOptions = categoryOptions.filter((option) => !option.classList.contains("hidden"));
      const activeIndex = visibleOptions.indexOf(document.activeElement);
      if (event.key === "ArrowDown" && visibleOptions.length) {
        event.preventDefault();
        visibleOptions[Math.min(activeIndex + 1, visibleOptions.length - 1)].focus();
      } else if (event.key === "Enter" && visibleOptions.length === 1) {
        event.preventDefault();
        selectCategory(visibleOptions[0]);
      } else if (event.key === "Escape") {
        closeCategoryDropdown();
      }
    });
    categoryDropdown.addEventListener("keydown", (event) => {
      const option = event.target;
      if (!(option instanceof HTMLElement) || !option.classList.contains("category-option")) return;
      const visibleOptions = categoryOptions.filter((item) => !item.classList.contains("hidden"));
      const index = visibleOptions.indexOf(option);
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const direction = event.key === "ArrowDown" ? 1 : -1;
        visibleOptions[(index + direction + visibleOptions.length) % visibleOptions.length].focus();
      } else if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectCategory(option);
        categorySearch.focus();
      } else if (event.key === "Escape") {
        closeCategoryDropdown();
        categorySearch.focus();
      }
    });
    document.addEventListener("click", (event) => {
      const target = event.target;
      if (target instanceof Node && !categoryDropdown.contains(target) && target !== categorySearch) {
        closeCategoryDropdown();
      }
    });
    categorySearch.form?.addEventListener("submit", (event) => {
      if (!categoryId.value) {
        event.preventDefault();
        categorySearch.setCustomValidity("Seleccioná una categoría de la lista.");
        categorySearch.reportValidity();
      } else {
        categorySearch.setCustomValidity("");
      }
    });
    categorySearch.addEventListener("input", () => categorySearch.setCustomValidity(""));
  }

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
