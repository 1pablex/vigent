// Dashboard de indicadores do RH (RF-30): busca os números na API (/api/v1/) e monta
// as barras. Fica em arquivo próprio porque a Content-Security-Policy não permite
// script inline. Os endereços da API vêm do JSON gerado por json_script no template.
(function () {
  "use strict";
  const API = JSON.parse(document.getElementById("dash-endpoints").textContent);
  let META = 90;

  // Os nomes de curso e de departamento são digitados pelo RH: o texto entra sempre
  // por textContent, nunca por innerHTML (proteção contra XSS).
  function el(tag, classe, texto) {
    const n = document.createElement(tag);
    if (classe) n.className = classe;
    if (texto !== undefined) n.textContent = texto;
    return n;
  }

  function vazio(alvo, msg) {
    alvo.replaceChildren(el("p", "sub", msg));
  }

  async function buscar(url) {
    const r = await fetch(url, { credentials: "same-origin",
                                 headers: { "Accept": "application/json" } });
    if (!r.ok) throw new Error(url + " respondeu " + r.status);
    return r.json();
  }

  function corDoPercentual(p) {
    if (p >= META) return "var(--teal)";
    if (p >= 50) return "var(--amber)";
    return "var(--red)";
  }

  // Uma linha de barra horizontal: rótulo, trilho com a barra, valor em texto.
  function linhaBarra(rotulo, pct, valorTexto, dica, cor, comMeta) {
    const linha = el("div", "dash-linha");
    linha.title = dica;
    linha.append(el("span", "dash-rotulo", rotulo));
    const trilho = el("div", "dash-trilho");
    const barra = el("i");
    barra.style.width = Math.max(0, Math.min(100, pct)) + "%";
    barra.style.background = cor;
    trilho.append(barra);
    if (comMeta) {
      const marca = el("b", "dash-meta");
      marca.style.left = META + "%";
      trilho.append(marca);
    }
    linha.append(trilho, el("span", "dash-valor", valorTexto));
    return linha;
  }

  function desenharConformidade(alvo, itens, chave) {
    if (!itens.length) return vazio(alvo, "Nenhum dado de conformidade ainda.");
    alvo.replaceChildren(...itens.map(function (i) {
      const dica = i[chave] + ": " + i.conformes + " de " + i.total +
                   " treinamentos em conformidade (" + i.percentual + "%)";
      return linhaBarra(i[chave], i.percentual, i.percentual + "%", dica,
                        corDoPercentual(i.percentual), true);
    }));
  }

  function desenharVencimentos(alvo, faixas) {
    const maior = Math.max(1, ...faixas.map(function (f) { return f.quantidade; }));
    alvo.replaceChildren(...faixas.map(function (f) {
      const dica = f.quantidade + " certificado(s) vencem entre " + f.de_dias +
                   " e " + f.ate_dias + " dias";
      return linhaBarra(f.faixa, f.quantidade / maior * 100, String(f.quantidade), dica,
                        "var(--navy-mid)", false);
    }));
  }

  function desenharReacao(alvo, cursos) {
    if (!cursos.length) return vazio(alvo, "Nenhuma avaliação de reação registrada ainda.");
    alvo.replaceChildren(...cursos.map(function (c) {
      const bloco = el("div", "dash-grupo");
      const titulo = el("div", "dash-grupo-t", c.curso);
      titulo.append(el("span", "dash-n", " · " + c.respostas + " resposta" +
                                         (c.respostas === 1 ? "" : "s")));
      bloco.append(titulo);
      [["Didática", c.media_didatica, "dash-cor-didatica"],
       ["Entendimento", c.media_entendimento, "dash-cor-entendimento"]].forEach(function (s) {
        const linha = linhaBarra(s[0], s[1] * 10, s[1].toFixed(1), c.curso + " - " + s[0] +
                                 ": média " + s[1].toFixed(1) + " de 10", "", false);
        linha.querySelector("i").className = s[2];
        bloco.append(linha);
      });
      return bloco;
    }));
  }

  async function carregar() {
    try {
      const [indice, deps, cursos, venc, reacao, qual] = await Promise.all([
        buscar(API.conformidade), buscar(API.departamentos), buscar(API.cursos),
        buscar(API.vencimentos), buscar(API.reacao), buscar(API.qualidade),
      ]);

      META = indice.meta;
      document.getElementById("dash-meta-pill").textContent = "Meta interna: " + META + "%";
      document.getElementById("ind-percentual").textContent = indice.percentual + "%";
      ["em_dia", "vencendo", "vencido", "pendente"].forEach(function (k) {
        document.getElementById("ind-" + k).textContent = indice[k];
      });
      const status = document.getElementById("ind-status");
      const acima = indice.total > 0 && indice.percentual >= META;
      status.textContent = indice.total === 0 ? "Sem dados"
                         : acima ? "✓ Dentro da meta" : "! Abaixo da meta";
      status.classList.add(acima ? "ok" : "abaixo");
      document.getElementById("ind-detalhe").textContent = indice.total
        ? (indice.em_dia + indice.vencendo) + " de " + indice.total + " treinamentos em conformidade"
        : "";

      desenharConformidade(document.getElementById("graf-departamentos"), deps, "departamento");
      desenharConformidade(document.getElementById("graf-cursos"), cursos, "curso");
      desenharVencimentos(document.getElementById("graf-vencimentos"), venc);
      desenharReacao(document.getElementById("graf-reacao"), reacao);

      document.getElementById("qual-taxa_conclusao").textContent = qual.taxa_conclusao + "%";
      document.getElementById("qual-nota_media_prova").textContent = qual.nota_media_prova;
      document.getElementById("qual-media_reacao").textContent = qual.media_reacao;
    } catch (erro) {
      console.error("[Vigent dashboard]", erro);
      document.getElementById("dash-erro").classList.remove("hide");
    }
  }

  carregar();
})();
