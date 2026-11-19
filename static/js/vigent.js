// Comportamentos das telas, ligados por atributos data- no HTML.
// Nenhum template tem script inline nem atributo on...=: a Content-Security-Policy
// (script-src 'self') só permite scripts servidos pelo próprio Vigent.
//
//   data-envio-automatico   <select> que envia o formulário ao trocar a opção (filtros)
//   data-confirmar="texto"  <form> que pede confirmação antes de enviar (exclusões)
//   data-imprimir           botão que abre a impressão da página (certificado)
(function () {
  "use strict";

  document.querySelectorAll("[data-envio-automatico]").forEach(function (campo) {
    campo.addEventListener("change", function () {
      campo.form.submit();
    });
  });

  document.querySelectorAll("form[data-confirmar]").forEach(function (formulario) {
    formulario.addEventListener("submit", function (evento) {
      if (!window.confirm(formulario.dataset.confirmar)) {
        evento.preventDefault();
      }
    });
  });

  document.querySelectorAll("[data-imprimir]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      window.print();
    });
  });
})();
