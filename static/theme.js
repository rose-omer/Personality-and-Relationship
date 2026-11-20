// İlk boyamadan önce çalışır: kayıtlı temayı uygular, JS sınıfını ekler.
(function () {
  var root = document.documentElement;
  root.classList.add("js");
  try {
    var saved = localStorage.getItem("tema");
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  } catch (e) {
    /* Depolama kapalıysa sistem teması geçerli kalır. */
  }
})();
