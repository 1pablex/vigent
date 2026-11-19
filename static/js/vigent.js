// Comportamentos das telas, ligados por atributos data- no HTML.
// Nenhum template tem script inline nem atributo on...=: a Content-Security-Policy
// (script-src 'self') só permite scripts servidos pelo próprio Vigent.
//
//   data-envio-automatico   <select> que envia o formulário ao trocar a opção (filtros)
//   data-confirmar="texto"  <form> ou botão que pede confirmação antes de enviar
//   data-imprimir           botão que abre a impressão da página (certificado)
(function () {
  "use strict";

  document.querySelectorAll("[data-envio-automatico]").forEach(function (campo) {
    campo.addEventListener("change", function () {
      campo.form.submit();
    });
  });

  // A confirmação pode estar no <form> (vale para qualquer envio) ou num botão (vale só
  // quando aquele botão envia: "Publicar" confirma, "Voltar e editar" não).
  document.querySelectorAll("form").forEach(function (formulario) {
    if (!formulario.matches("[data-confirmar]") && !formulario.querySelector("[data-confirmar]")) {
      return;
    }
    formulario.addEventListener("submit", function (evento) {
      const botao = evento.submitter;
      const mensagem = (botao && botao.dataset.confirmar) || formulario.dataset.confirmar;
      if (mensagem && !window.confirm(mensagem)) {
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
