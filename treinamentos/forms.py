"""Formulários do RH para cadastro de cursos, aulas, slides e questões da prova."""
from django import forms
from django.db import transaction
from django.db.models import F
from django.forms import inlineformset_factory

from avaliacoes.models import Alternativa, Prova, Questao
from contas.models import Departamento
from treinamentos.models import Aula, Curso, CursoDepartamento, SlideAula


def _estilizar(form):
    """Aplica as classes do painel do RH aos widgets de texto e número."""
    for campo in form.fields.values():
        widget = campo.widget
        if isinstance(widget, (forms.TextInput, forms.NumberInput, forms.EmailInput)):
            widget.attrs.setdefault("class", "txt")


class CursoForm(forms.ModelForm):
    departamentos = forms.ModelMultipleChoiceField(
        queryset=Departamento.objects.all(), required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Os colaboradores desses departamentos passam a ter o curso como obrigatório (RN-02).",
    )

    class Meta:
        model = Curso
        fields = ["nome", "categoria", "carga_horaria", "validade_meses",
                  "nota_minima", "max_tentativas", "imagem_capa"]
        labels = {
            "nome": "Nome do curso", "categoria": "Categoria",
            "carga_horaria": "Carga horária", "validade_meses": "Validade do certificado (meses)",
            "nota_minima": "Nota mínima para aprovação", "max_tentativas": "Tentativas na prova",
            "imagem_capa": "Imagem de capa",
        }
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: LGPD na Prática"}),
            "categoria": forms.TextInput(attrs={"placeholder": "Ex.: Compliance, Segurança"}),
            "carga_horaria": forms.TextInput(attrs={"placeholder": "Ex.: 4 horas"}),
            "nota_minima": forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "10"}),
            "validade_meses": forms.NumberInput(attrs={"min": "1"}),
            "max_tentativas": forms.NumberInput(attrs={"min": "1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar(self)
        if self.instance.pk:
            self.initial["departamentos"] = list(
                self.instance.departamentos.values_list("departamento_id", flat=True))

    def clean_nota_minima(self):
        nota = self.cleaned_data["nota_minima"]
        if not 0 <= nota <= 10:
            raise forms.ValidationError("A nota mínima deve ficar entre 0 e 10.")
        return nota

    def clean_validade_meses(self):
        meses = self.cleaned_data["validade_meses"]
        if meses < 1:
            raise forms.ValidationError("A validade deve ser de pelo menos 1 mês.")
        return meses

    def clean_max_tentativas(self):
        tentativas = self.cleaned_data["max_tentativas"]
        if tentativas < 1:
            raise forms.ValidationError("Permita pelo menos 1 tentativa.")
        return tentativas

    @transaction.atomic
    def save(self, commit=True):
        curso = super().save()
        escolhidos = set(self.cleaned_data["departamentos"])
        curso.departamentos.exclude(departamento__in=escolhidos).delete()
        ja_vinculados = set(curso.departamentos.values_list("departamento_id", flat=True))
        CursoDepartamento.objects.bulk_create(
            CursoDepartamento(curso=curso, departamento=dep)
            for dep in escolhidos if dep.id not in ja_vinculados)
        return curso


class AulaForm(forms.ModelForm):
    class Meta:
        model = Aula
        fields = ["ordem", "titulo"]
        labels = {"ordem": "Ordem", "titulo": "Título da aula"}

    def __init__(self, *args, curso, **kwargs):
        super().__init__(*args, **kwargs)
        self.curso = curso
        _estilizar(self)
        if not self.instance.pk:
            ultima = curso.aulas.order_by("-ordem").values_list("ordem", flat=True).first()
            self.initial.setdefault("ordem", (ultima or 0) + 1)

    def clean_ordem(self):
        ordem = self.cleaned_data["ordem"]
        repetida = self.curso.aulas.filter(ordem=ordem).exclude(pk=self.instance.pk)
        if repetida.exists():
            raise forms.ValidationError("Já existe uma aula com essa ordem neste curso.")
        return ordem

    def save(self, commit=True):
        self.instance.curso = self.curso
        return super().save(commit)


class SlideForm(forms.ModelForm):
    class Meta:
        model = SlideAula
        fields = ["ordem", "titulo", "corpo", "imagem"]
        labels = {"ordem": "Ordem", "titulo": "Título do slide",
                  "corpo": "Texto", "imagem": "Imagem (opcional)"}
        widgets = {"corpo": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilizar(self)

    def validate_unique(self):
        # A ordem é validada no formset inteiro (BaseSlideFormSet.clean); conferir slide
        # a slide contra o banco impediria trocar a ordem de dois slides.
        pass


class BaseSlideFormSet(forms.BaseInlineFormSet):

    def mantidos(self):
        return [f for f in self.forms
                if f.cleaned_data and not f.cleaned_data.get("DELETE")]

    def validate_unique(self):
        # Substituída pela checagem de clean(), com mensagem própria.
        pass

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        ordens = [f.cleaned_data["ordem"] for f in self.mantidos()]
        if len(ordens) != len(set(ordens)):
            raise forms.ValidationError("Dois slides não podem ter a mesma ordem.")

    @transaction.atomic
    def save(self, commit=True):
        """
        Salva os slides permitindo trocar a ordem entre eles. As ordens atuais são
        deslocadas antes, senão a troca de dois slides violaria o unique (aula, ordem).
        """
        for form in self.forms:
            if form.instance.pk and form.cleaned_data.get("DELETE"):
                form.instance.delete()
        self.instance.slides.update(ordem=F("ordem") + 10000)
        salvos = []
        for form in self.mantidos():
            slide = form.save(commit=False)
            slide.aula = self.instance
            slide.save()
            salvos.append(slide)
        return salvos


SlideFormSet = inlineformset_factory(
    Aula, SlideAula, form=SlideForm, formset=BaseSlideFormSet,
    extra=1, can_delete=True)


class QuestaoForm(forms.Form):
    """Enunciado e até 5 alternativas (A a E), com exatamente uma correta."""

    LETRAS = [letra for letra, _ in Alternativa.LETRAS]

    ordem = forms.IntegerField(label="Ordem", min_value=1,
                               widget=forms.NumberInput(attrs={"class": "txt", "min": "1"}))
    enunciado = forms.CharField(label="Enunciado", widget=forms.Textarea(attrs={"rows": 3}))
    correta = forms.ChoiceField(label="Alternativa correta",
                                choices=[(letra, letra) for letra in LETRAS],
                                widget=forms.RadioSelect,
                                error_messages={"required": "Marque qual alternativa é a correta."})

    def __init__(self, *args, prova, questao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.prova = prova
        self.questao = questao
        for letra in self.LETRAS:
            self.fields[f"alt_{letra}"] = forms.CharField(
                label=letra, required=False, max_length=400,
                widget=forms.TextInput(attrs={"class": "txt",
                                              "placeholder": f"Texto da alternativa {letra}"}))
        if questao:
            self.initial.update({"ordem": questao.ordem, "enunciado": questao.enunciado})
            for alt in questao.alternativas.all():
                self.initial[f"alt_{alt.letra}"] = alt.texto
                if alt.correta:
                    self.initial["correta"] = alt.letra
        else:
            ultima = prova.questoes.order_by("-ordem").values_list("ordem", flat=True).first() if prova else None
            self.initial["ordem"] = (ultima or 0) + 1

    def alternativas(self):
        """Pares (letra, campo) para o template montar as linhas."""
        return [(letra, self[f"alt_{letra}"]) for letra in self.LETRAS]

    def clean(self):
        dados = super().clean()
        preenchidas = [letra for letra in self.LETRAS
                       if (dados.get(f"alt_{letra}") or "").strip()]
        if len(preenchidas) < 2:
            raise forms.ValidationError("Preencha pelo menos duas alternativas.")
        correta = dados.get("correta")
        if correta and correta not in preenchidas:
            self.add_error("correta", "A alternativa marcada como correta está em branco.")
        return dados

    @transaction.atomic
    def save(self, curso):
        prova = self.prova or Prova.objects.get_or_create(curso=curso)[0]
        questao = self.questao or Questao(prova=prova)
        questao.ordem = self.cleaned_data["ordem"]
        questao.enunciado = self.cleaned_data["enunciado"].strip()
        questao.save()
        for letra in self.LETRAS:
            texto = self.cleaned_data[f"alt_{letra}"].strip()
            if texto:
                Alternativa.objects.update_or_create(
                    questao=questao, letra=letra,
                    defaults={"texto": texto, "correta": letra == self.cleaned_data["correta"]})
            else:
                questao.alternativas.filter(letra=letra).delete()
        return questao
