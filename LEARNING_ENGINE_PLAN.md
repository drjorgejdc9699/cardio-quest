# PULSO: Arena — Plan del motor de aprendizaje adaptativo

> **Estado: Fase 1 (Fundamentos) implementada y verificada** — ver §12 al final
> para el detalle de qué se construyó, qué se verificó y qué sigue en Fase 2-4.

Convertir el quiz-RPG actual en un *adaptive learning RPG engine* que estime el
dominio real de artículos científicos, sin romper nada de lo que ya funciona.

---

## 1. Arquitectura actual

**Stack:** un solo archivo `aventura.html` (HTML + CSS + JS vanilla, ~1600 líneas de
JS). Sin build, sin framework, sin tipos, sin dependencias, sin tests, sin git.
Se publica como Artifact a partir de `aventura_fragment.html` (extracto del `<body>`),
lo que **obliga a mantener un único archivo autocontenido**: no puede cargar módulos,
CSS ni imágenes externas.

**Flujo:** `home → avatar → map → battle → review → card → study`, con un
`render()` central que reescribe `#app` y delegación de eventos por `data-action`.

**Datos persistidos** (`localStorage['pulso_aventura_v1']`):

```
DATA = { avatar, campaign{levelsCleared[10], playerHp, usedQuestionIds[],
         failedQuestionIds[], completed, articleTag}, deck{[qid]: SM-2}, pdfStaging }
```

**Modelo de pregunta:** `{id, topic, diff 1-3, kind:'directa'|'caso', vignette,
options[4], correct, exp}`; `article` se inyecta al construir `QUESTIONS`.

**Generación de preguntas: no hay IA en el juego.** El usuario pega el PDF en el
chat, el asistente redacta las preguntas y se escriben a mano en el archivo. Por lo
tanto "actualizar los prompts internos" (#29) se traduce en **un contrato de datos
validado en runtime**, que es lo que sí es verificable desde el código.

---

## 2. Qué se reutiliza, qué se modifica, qué es nuevo

### Se reutiliza intacto
- Combate (100 HP, 20/acierto, 20/error), clases, sprites, mapa, estética.
- `DATA.deck` con SM-2 por tarjeta y la pantalla de estudio.
- `shuffledView`, `esc`, `shuffle`, el modal propio, el sistema de artículos.

### Se modifica
- `QUESTIONS`: se enriquece con metadatos cognitivos (retro-compatible).
- `pickQuestionsForLevel`: pasa de "dificultad + 80/20" a selección por
  `priorityScore` con foco cognitivo por rival y dificultad adaptativa.
- `LEVELS`: cada rival gana un foco cognitivo (#7).
- `handleAnswer`: registra intentos completos (confianza, tiempo, conceptos).
- Cuaderno: gana una vista de conceptos (Codex) sin perder la de preguntas.

### Nuevo
- `CONCEPTS` + mapa de conocimiento por artículo.
- Learning Engine (intentos, mastery, calibración, debilidades).
- Scheduler Engine (repetición espaciada **por concepto**, reemplazable).
- Selection Engine (`priorityScore`, interleaving, dificultad adaptativa).
- Debrief post-combate, panel de debug, self-tests.

---

## 3. Fronteras de módulos (dentro del archivo único)

Cada motor vive en un bloque delimitado, **sin tocar el DOM**, con API explícita:

| Módulo | API pública | No hace |
|---|---|---|
| `ArticleEngine` | `CONCEPTS`, `conceptsOf`, `conceptById`, `articleStructure` | render |
| `QuestionEngine` | `validateQuestion`, `enrichQuestion`, `variantsOf` | render |
| `LearningEngine` | `recordAttempt`, `masteryOf`, `weaknesses`, `calibration` | render |
| `SchedulerEngine` | `schedule`, `dueConcepts`, `nextReviewAt` | render, persistencia directa |
| `SelectionEngine` | `pickForLevel`, `priorityScore`, `interleavedSession` | render |
| Capa de UI | pantallas `screenX()` | lógica de aprendizaje |

Regla: la UI **lee** de los motores, nunca calcula mastery ni intervalos.

---

## 4. Modelo de datos nuevo

### Concepto
```js
{ id, articleId, title, summary, category, importance 1-3, difficulty 1-5,
  sourceRef, prerequisites[], related[], qIds[], topics[] }
```
`qIds`/`topics` permiten **retro-vincular las 91 preguntas existentes** sin
reescribirlas una por una (ver §6).

Las categorías se adaptan al tipo de artículo (`article.kind`): un ensayo clínico
usa `metodo/poblacion/desenlaces/resultados/limitaciones`; una guía usa
`indicaciones/tecnica/cuantificacion/calidad`; un banco temático usa `tema`.

### Metadatos cognitivos de pregunta
```js
knowledgeType: recall|understanding|application|discrimination|reasoning|methodology|transfer
clinicalType : direct|clinical_case|progressive_case|comparison|hypothesis_update
difficulty   : 1-5  (se deriva del diff 1-3 heredado)
conceptIds[] , sourceRef , evidenceScope: 'article'|'principle'
feedback: { why, distractors{i:txt}, keyFact, rule }
```
`evidenceScope` es el control anti-alucinación (#30): `'article'` = afirmable desde
el texto; `'principle'` = pregunta de transferencia construida sobre principios, que
la UI etiqueta como tal y **nunca** presenta como cita del artículo.

### Estado de aprendizaje (nuevo, junto a lo existente)
```js
DATA.learning = {
  v: 1,
  attempts: [{ at, qid, conceptIds[], correct, confidence, ms, difficulty,
               knowledgeType, context:'battle'|'pretest'|'study'|'recall' }],
  concepts: { [cid]: { attempts, correct, incorrect, highConfErrors,
                       sumConf, calibSum, transferOk, transferTried,
                       lastAt, nextAt, ladder, stability, mastery, weakness } }
}
```
`DATA.deck` **no se toca**: sigue siendo la memoria por tarjeta. El estado por
concepto se construye encima.

---

## 5. Fórmula de mastery (heurística interpretable)

```
mastery = accuracy' · difficultyWeight · retention · transferBonus · calibrationAdj
```

- `accuracy'` — acierto suavizado (Laplace, prior 0.5) y **ponderado por recencia**:
  los intentos recientes pesan más (decaimiento exponencial). Evita que 10 aciertos
  viejos escondan 3 fallos nuevos.
- `difficultyWeight` — 0.85–1.15 según la dificultad media de lo acertado. Acertar
  fácil no vale lo mismo que acertar difícil.
- `retention` — `exp(-díasDesdeÚltimo / stability)`, acotado. El dominio **decae** si
  no se repasa: eso es lo que hace que el Codex mida retención y no historia.
- `transferBonus` — 1.10 si hay transferencia acertada, 0.92 si se intentó y falló.
- `calibrationAdj` — penaliza errores con alta confianza (misconceptions).

Normalizado a `[0,1]`. Documentado y testeado (`selfTest`).

**Debilidad:** `mastery < 0.5` con ≥3 intentos y (≥2 fallos o ≥1 error de alta
confianza). **Misconception:** ≥1 fallo con confianza ≥75%.

---

## 6. Migraciones (seguras, sin destruir datos)

1. `DATA.learning` se crea vacío si no existe. Nada más cambia de forma.
2. Las 91 preguntas existentes se enriquecen **en memoria al cargar**:
   - `conceptIds`: explícitos → si no, por `concept.qIds` → si no, por `concept.topics`.
   - `knowledgeType`: heurística sobre `kind`, `diff` y marcadores del enunciado.
   - `difficulty`: `diff 1-3 → 1..5`.
   - `evidenceScope`: `'article'` por defecto.
   - `feedback`: si falta, se sintetiza a partir de `exp` (degradación elegante).
   Ninguna pregunta se reescribe en disco; el enriquecimiento es idempotente.
3. `DATA.deck` intacto. `DATA.campaign` intacto (misma forma).
4. Reconstrucción retroactiva: al migrar, los `failedQuestionIds` existentes siembran
   los contadores por concepto para que el Codex no arranque en blanco.

---

## 7. Progresión cognitiva de los 10 rivales (#7)

| Rival | Foco | Tipos admitidos |
|---|---|---|
| 1 | Reconocimiento | recall |
| 2 | Recuperación | recall, understanding |
| 3 | Comprensión | understanding |
| 4 | Mecanismos | understanding, reasoning |
| 5 | Aplicación | application |
| 6 | Discriminación | discrimination, comparison |
| 7 | Metodología y evidencia | methodology |
| 8 | Razonamiento clínico | reasoning, clinical_case |
| 9 | Integración | reasoning, application, discrimination |
| 10 (Boss) | Transferencia | transfer, progressive_case, hypothesis_update |

Con **degradación**: si el artículo no tiene preguntas del tipo pedido, se cae al
tipo adyacente antes que dejar el nivel vacío.

---

## 8. Selección de preguntas (#37)

```
priority = urgency · weakness · misconception · relevance · interleave · difficultyMatch
```
- `urgency` — vencimiento del concepto según el scheduler.
- `weakness` / `misconception` — multiplicadores para lo que falla y lo que se
  cree saber.
- `relevance` — foco cognitivo del rival actual.
- `interleave` — favorece alternar conceptos y artículos; penaliza bloques del
  mismo concepto seguidos.
- `difficultyMatch` — zona productiva: dificultad objetivo = f(mastery), no f(nivel).

Todo decidido queda en `S.selectionLog` para el panel de debug (#35/#36).

---

## 9. Componentes de UI nuevos

| Pantalla | Nombre en el juego | Fase |
|---|---|---|
| Pre-test | "Reconocimiento del terreno" | 2 |
| Sala de exploración | "Campamento" | 2 |
| Debrief post-combate | "Parte de batalla" | 1 |
| Codex de conceptos | "Codex" (dentro del cuaderno) | 1 |
| Panel de debug | oculto, `?debug=1` | 1 |

Estética existente: mismos `pill`, `card-panel`, `stat-box`, tipografías y paleta.

---

## 10. Riesgos

| Riesgo | Mitigación |
|---|---|
| Romper partidas guardadas | Migración aditiva + `selfTest` de migración |
| Cobertura insuficiente de conceptos | Fallback por topic; el Codex marca conceptos sin datos |
| Fatiga por preguntar confianza siempre | Confianza solo en preguntas que aportan señal |
| Archivo cada vez más grande | Fronteras internas; sprites ya son el 45% del peso |
| Sobrecarga visual del combate | Modificadores en múltiplos de 20; nada nuevo en pantalla salvo la barra de confianza |
| Heurísticas sin validar | `PULSO.selfTest()` con asserts sobre mastery, calibración, scheduler y migración |

---

## 11. Orden de implementación

**Fase 1 — Fundamentos** (mayor beneficio pedagógico por línea escrita)
1. `CONCEPTS` + vinculación concepto↔pregunta
2. Metadatos cognitivos + `validateQuestion`
3. Registro de intentos
4. Confidence rating en combate
5. Mastery por concepto + calibración
6. Debilidades y misconceptions
7. Feedback estructurado
8. Debrief post-combate
9. Codex de conceptos
10. Panel de debug + self-tests + migración

**Fase 2 — Sala de Exploración**: mapa del artículo, pre-test, microlecciones,
active recall, self-explanation.

**Fase 3 — Adaptativo**: scheduler por concepto, interleaving entre artículos,
variantes de pregunta, dificultad adaptativa.

**Fase 4 — Campaña avanzada**: casos progresivos, duelos de hipótesis, memoria del
enemigo, boss de transferencia.

---

## 12. Estado real tras la implementación (Fase 1)

**Construido, en `aventura.html`, verificado con clics reales en el navegador y
con `PULSO.selfTest()` (14/14 casos en verde):**

- **Article Engine**: `CONCEPTS` (40 conceptos: 16 de eco pediátrica, 24 de
  cardio general), `ARTICLE_STRUCTURES` por tipo de artículo, `articleStructure()`.
- **Question Engine**: `enrichQuestion()` retro-vincula las 91 preguntas
  existentes a conceptos (0 huérfanas), les asigna `knowledgeType`/`clinicalType`/
  `difficulty 1-5`/`evidenceScope`/`sourceRef`/`feedback`. `validateQuestion()`
  es el control de alucinación real: rechaza preguntas factuales sin
  `sourceRef` y sin concepto vinculado.
- **Learning Engine**: `recordAttempt()`, fórmula de mastery documentada
  (`accuracy' × difficultyWeight × retention × transferBonus × calibrationAdj`),
  detección de debilidad y de misconception (error con confianza ≥75%).
- **Scheduler Engine**: repetición espaciada por concepto con escalera
  [1,3,7,14,30,60] días, reemplazable sin tocar el resto del juego.
- **Confidence Calibration en combate**: un paso extra (25/50/75/100%) entre
  elegir respuesta y ver el resultado — no una pantalla nueva, un solo toque.
- **Feedback estructurado**: tu respuesta / la correcta / por qué / dato clave
  / regla mental / conceptos evaluados, con degradación elegante en preguntas
  antiguas que no traen esos campos.
- **Debrief post-combate** ("Parte de batalla"): precisión por categoría del
  artículo, conceptos dominados/frágiles, errores de alta confianza — construido
  solo con lo que pasó en ese combate, no con historial global.
- **Codex**: pestaña nueva dentro del cuaderno existente (no lo reemplaza),
  agrupado por artículo, con barra de dominio por concepto y ficha de detalle
  (resumen, dominio, calibración, prerrequisitos/relacionados, próximo repaso,
  preguntas del concepto).
- **Panel de debug** (`?debug=1`, oculto al jugador): tabla cruda de todos los
  conceptos y botón para correr los self-tests desde la UI.
- **Migración**: `migrateLearningState()` crea `DATA.learning` de forma aditiva,
  siembra retroactivamente desde `failedQuestionIds` si existían, y es
  idempotente (verificado explícitamente en un self-test).

**Bug real que atrapó el self-test antes de publicar** (vale la pena dejarlo
anotado): `SchedulerEngine.schedule()` no era idempotente — cada vez que se
llamaba sin un intento nuevo de por medio (por ejemplo, en cada carga de la
página, porque la migración reprograma todos los conceptos con datos) volvía a
avanzar el peldaño de repetición espaciada, alejando el próximo repaso
indefinidamente solo por abrir la app varias veces. Se corrigió atando el
cálculo a un contador entero de intentos (`scheduledAtAttempt`) en vez de
recalcular en cada llamada.

**Decisiones que se desviaron un poco del pedido original, y por qué:**
- No se tocaron los números de daño del combate (100 HP / 20 por acierto /
  20 por error / 40 crítico). El punto 23 del pedido sugería bonus por
  confianza calibrada o "habilidad especial" del enemigo con confianza 100%
  fallida — se dejó fuera de la Fase 1 a propósito para no romper el
  invariante "el HP siempre es múltiplo de 20" que se fijó en la sesión
  anterior. Si se quiere, es un cambio pequeño y aislado para la Fase 4.
- Self-explanation (#6) y "Defiende tu respuesta" (#11) no se implementaron:
  el propio pedido los ubica en Fase 2 y Fase 4 respectivamente, no en Fase 1.

**No implementado todavía (Fase 2-4, según el plan original):** Sala de
Exploración, pre-test diagnóstico, microlecciones, self-explanation, casos
clínicos progresivos (unfolding cases), duelos de hipótesis, "defiende tu
respuesta", interleaving explícito entre artículos en una sesión dedicada,
dificultad adaptativa real (todavía se basa en el nivel, no en el dominio
individual), memoria del enemigo, boss de transferencia cualitativamente
distinto, y el Selection Engine con `priorityScore` completo (§8 del plan).
