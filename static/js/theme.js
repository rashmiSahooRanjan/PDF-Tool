/* ===================================================================
   DocuFlex — Theme & Toast Notifications Manager
   =================================================================== */

// 1. Theme Initializer
(function initTheme() {
  const savedTheme = localStorage.getItem("docuflex_theme") || 
    (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  document.documentElement.setAttribute("data-theme", savedTheme);
})();

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
  const newTheme = currentTheme === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", newTheme);
  localStorage.setItem("docuflex_theme", newTheme);
  updateThemeIcon();
}

function updateThemeIcon() {
  const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
  const icon = document.getElementById("theme-icon");
  if (icon) {
    if (currentTheme === "dark") {
      icon.innerHTML = `<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>`; // Moon
    } else {
      icon.innerHTML = `<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path>`; // Sun
    }
  }
}

// 2. Toast Notification Manager
function showToast(message, type = "info", duration = 4000) {
  let shelf = document.getElementById("toast-shelf");
  if (!shelf) {
    shelf = document.createElement("div");
    shelf.id = "toast-shelf";
    shelf.className = "toast-shelf";
    document.body.appendChild(shelf);
  }

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  
  let iconSvg = "";
  if (type === "success") {
    iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
  } else if (type === "error") {
    iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F43F5E" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
  } else if (type === "warning") {
    iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2.5"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;
  } else {
    iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6366F1" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
  }

  toast.innerHTML = `
    ${iconSvg}
    <div style="flex:1;">${message}</div>
    <button onclick="this.parentElement.remove()" style="color:var(--text-dim);font-size:1.1rem;cursor:pointer;">&times;</button>
  `;

  shelf.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(30px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// 3. Format bytes utility
function formatBytes(bytes, decimals = 1) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

document.addEventListener("DOMContentLoaded", () => {
  updateThemeIcon();
  const themeBtn = document.getElementById("theme-toggle-btn");
  if (themeBtn) {
    themeBtn.addEventListener("click", toggleTheme);
  }

  // Mega Dropdown Menu Handler
  const megaBtn = document.getElementById("mega-dropdown-btn");
  const megaMenu = document.getElementById("nav-mega-dropdown");
  if (megaBtn && megaMenu) {
    megaBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isActive = megaMenu.classList.contains("active");
      megaMenu.classList.toggle("active", !isActive);
      megaBtn.setAttribute("aria-expanded", !isActive);
    });

    document.addEventListener("click", (e) => {
      if (!megaMenu.contains(e.target) && !megaBtn.contains(e.target)) {
        megaMenu.classList.remove("active");
        megaBtn.setAttribute("aria-expanded", "false");
      }
    });
  }

  // Mobile Navigation Drawer Handlers (iOS & Android)
  const mobileMenuBtn = document.getElementById("mobile-menu-btn");
  const mobileDrawer = document.getElementById("mobile-drawer");
  const mobileOverlay = document.getElementById("mobile-drawer-overlay");
  const mobileCloseBtn = document.getElementById("mobile-drawer-close-btn");

  function openMobileDrawer() {
    if (mobileDrawer && mobileOverlay) {
      mobileDrawer.classList.add("open");
      mobileOverlay.classList.add("active");
      document.body.style.overflow = "hidden";
    }
  }

  function closeMobileDrawer() {
    if (mobileDrawer && mobileOverlay) {
      mobileDrawer.classList.remove("open");
      mobileOverlay.classList.remove("active");
      document.body.style.overflow = "";
    }
  }

  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openMobileDrawer();
    });
  }

  if (mobileCloseBtn) {
    mobileCloseBtn.addEventListener("click", closeMobileDrawer);
  }

  if (mobileOverlay) {
    mobileOverlay.addEventListener("click", closeMobileDrawer);
  }

  // Close mobile drawer when clicking any link inside it
  const mobileNavLinks = document.querySelectorAll(".mobile-nav-link");
  mobileNavLinks.forEach(link => {
    link.addEventListener("click", closeMobileDrawer);
  });
});
