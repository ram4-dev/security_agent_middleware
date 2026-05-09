# Design System — Tranquera

> Sistema · v1.0 · 2026
> Identidad visual del interceptor de prompts del Team 22 · Platanus Hack 26.

---

## 0. Nombre y posicionamiento

**Nombre del producto**: **Tranquera**

> *Tranquera*: en el campo rioplatense, la portera rústica que controla quién entra y quién sale de un terreno. Se abre cuando corresponde, se cierra cuando hay que cerrar — sin alarmas, sin ruido.

**Tagline canónico**:
> Un paso controlado entre la intención y la respuesta.

**Tagline largo (opcional para hero)**:
> Se abre cuando corresponde, se cierra cuando hay que cerrar.

**Frase de posicionamiento (manifesto)**:
> Tranquera intercepta cada prompt antes de que el modelo responda.
> No es un escudo, no es una advertencia: es una **aduana silenciosa** que aplica las reglas de la empresa sin interrumpir el ritmo de quien escribe.

---

## 1. Principios de marca

| # | Principio | Lectura |
|---|---|---|
| 01 | **Preciso** | Reglas explícitas, decisiones reproducibles. Cada veredicto se puede explicar. |
| 02 | **Silencioso** | No interrumpe al usuario que tiene buena intención. La fricción es proporcional al riesgo. |
| 03 | **Permanente** | No es un experimento ni un toggle. Es infraestructura: siempre encendida, siempre auditable. |

> Estos principios se citan textualmente en `Manifesto.html`. Cualquier copy nuevo debe poder mapear a uno de los tres.

---

## 2. Paleta — monocromo cálido

El sistema es **deliberadamente monocromo**: no hay colores de status (verde/rojo) en la marca. Los estados de la UI se diferencian por **jerarquía tipográfica, iconografía y peso**, no por color.

| Token | Hex | RGB | Uso |
|---|---|---|---|
| `--paper`        | `#EFEDE6` | `239, 237, 230` | Background light / texto sobre dark |
| `--ink`          | `#1C1B18` | `28, 27, 24`    | Background dark / texto principal |
| `--graphite`     | `#7C7A72` | `124, 122, 114` | Texto secundario, comments, metadata |
| `--graphite-dark`| `#5C5A52` | `92, 90, 82`    | Bordes, divisores en dark mode |
| `--paper-soft`   | `#D4D0C5` | `212, 208, 197` | Variante de paper para diferencia sutil (uso ocasional) |
| `--black`        | `#000000` | `0, 0, 0`       | Solo para máximo contraste (variante "beam") |
| `--white`        | `#FFFFFF` | `255, 255, 255` | Solo para overlays / casos extremos |

### Variantes de tema (App)

Las pantallas tienen **3 modos** nombrados como herramientas de escritura:

| Tema | Background | Texto principal | Carácter |
|---|---|---|---|
| **beam** | `--paper` | `--black` | Máxima legibilidad. Contraste alto. Para datos densos o pantallas largas. |
| **ink** | `--paper` | `--ink` | Modo default. Contraste cálido. Sensación "papel impreso". |
| **paper** | `--ink` | `--paper` | Dark mode. Para pantallas de admin / monitoreo / demos. |

> El nombre del modo NO es color — es relación: *qué actúa como tinta sobre qué actúa como papel*.

---

## 3. Tipografía

| Rol | Familia | Pesos usados | Fallback |
|---|---|---|---|
| **Display / Headings** | IBM Plex Sans | 600 (semibold), 700 (bold) | `system-ui, sans-serif` |
| **Body / UI** | IBM Plex Sans | 400 (regular), 500 (medium) | `system-ui, sans-serif` |
| **Mono / Code / Tokens** | IBM Plex Mono | 400, 500 | `ui-monospace, monospace` |

**Por qué IBM Plex**: open source (OFL), respaldada por IBM, neutra y técnica. Refuerza el tono "infraestructura institucional", no startup juvenil.

### Comments tipo código

El sistema **adopta el estilo `//` de comentarios de código** como recurso gráfico para títulos secundarios y captions, en `--graphite`:

```
// MANIFESTO
// paleta
// muestra
// construcción · grilla 10x
// T2 · lockup oscuro
```

Renderizar siempre en IBM Plex Mono, peso 400, color `--graphite`.

### Numeración

Listas numeradas usan **número + punto medio + espacio**: `01 · Preciso`, `02 · Silencioso`. Nunca `1.` ni `1)`.

---

## 4. Logo y lockup

### Wordmark

- Texto: **`tranquera`** (todo minúsculas, sin acento gráfico).
- Tipografía: **IBM Plex Sans · 600**.
- Tracking: default (no expandir).
- No abreviar. No usar "Tranq" ni "TQ" en producto.

### Variantes (de los archivos `T2`)

| Variante | Background | Wordmark | Cuándo |
|---|---|---|---|
| **T2 lockup oscuro** | `--paper` | `--ink` | Default. Web pública, docs, decks claros. |
| **T2 graphite (institucional)** | `--ink` | `--paper` | Pitch, slides oscuras, footers. Versión "institucional". |

### Construcción del logo (referencia `Construcción.html`)

- Grilla base: **10 × 10 unidades** (1u = unidad relativa).
- Caja del logo: **8u × 6u**.
- Composición: **2 postes + 2 travesaños** (metáfora literal de la tranquera).
  - Poste: **1u × 6u** (vertical).
  - Travesaño: **5u × 1u** (horizontal).
  - Separación entre postes: **2u**.
- Padding mínimo (clear space): **1u** de aire en los 4 lados.

> No deformar, no agregar sombras, no rotar. Si necesitás versión chica, usar el wordmark sin la marca de tranquera.

---

## 5. Grilla y espaciado

Sistema basado en **unidades "u"** que escalan al tamaño base de la pantalla. Para implementación web:

```css
:root {
  --u: 8px;          /* unidad base, ajustable por breakpoint */
  --u-2: calc(var(--u) * 2);
  --u-4: calc(var(--u) * 4);
  --u-8: calc(var(--u) * 8);
}
```

**Spacing scale recomendada** (múltiplos de 1u = 8px):
`4px · 8px · 16px · 24px · 32px · 48px · 64px · 96px`

**Padding default de cards** (de `Manifesto.html`): 40px (= 5u con base 8). Mantener.

---

## 6. Aplicación en UI (App)

Componentes mínimos a implementar consistentes con la marca:

### Card / Surface

```css
.surface {
  background: var(--paper);
  color: var(--ink);
  border-radius: 2px;        /* casi cuadrado, no pill */
  padding: 40px;
  font-family: 'IBM Plex Sans', system-ui, sans-serif;
}
.surface--paper {              /* dark mode card */
  background: var(--ink);
  color: var(--paper);
  outline: 1px solid var(--graphite-dark);
}
```

### Caption / metadata (graphite)

```css
.caption {
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 12px;
  color: var(--graphite);
  letter-spacing: 0;
}
.caption::before { content: '// '; }   /* comentario opcional */
```

### Action pills (mono)

Las 4 acciones del proxy (ver `specs/00-constitution.md`) se renderizan **en mono, mayúsculas, con prefijo de regla**:

```
LOG     proxy(req) → rule.id = "no-pii"
WARN    proxy(req) → rule.id = "client-name"
REDACT  proxy(req) → rule.id = "redact-pii"
BLOCK   proxy(req) → rule.id = "aws-key"
```

La diferencia visual base: peso (`LOG` 400, `WARN` 500, `REDACT` 600, `BLOCK` 700) y un indicador de 2u de alto a la izquierda (escala `--graphite` → `--ink` por severidad).

> **Nota — tensión funcional**: la marca es monocroma para piezas institucionales (landing, manifesto, logo, decks). En **superficies de monitoreo en vivo** (ej. `/admin/events`), un compliance officer **necesita** distinguir BLOCK de WARN de un vistazo — está OK usar un acento de color **funcional** (un solo amber para WARN, un solo crimson para BLOCK) **siempre y cuando** se respete el resto de la marca (paleta paper/ink/graphite + IBM Plex). El acento es UI-funcional, no decorativo.

---

## 7. Voz y tono

| ✅ Hacer | ❌ Evitar |
|---|---|
| Frases cortas, declarativas | Frases corporativas largas |
| Voz técnica, calma | Voz alarmista ("¡PELIGRO!") |
| "Aduana silenciosa", "punto de control", "tranquera" *(metáfora poética)* | "Escudo", "shield", "muralla", "AI safety" |
| "Firewall de Claude Code" *(categoría B2B aceptada en sales/landing — no en manifesto)* | Mezclar firewall + escudo en el mismo párrafo |
| Español rioplatense neutro | Anglicismos innecesarios ("toggle", "dashboard"→ usar "panel") |
| Comentarios con `//` para metadata | Emojis ⚠️ 🔒 🛡️ |
| Mostrar la regla que disparó | Esconder por qué se decidió algo |

**Frase prohibida**: "AI safety". El producto **no se vende como safety** — se vende como **control y trazabilidad** (en lo institucional/manifesto) o como **firewall corporativo de Claude Code** (en lo B2B/landing). Safety es un subproducto, no la value prop.

---

## 8. Inventario de archivos `identidad/`

| Archivo | Función | Mode |
|---|---|---|
| `T2 _ lockup.html` | Wordmark sobre paper, oscuro institucional | light |
| `T2 _ Graphite.html` | Wordmark sobre ink, con muestras de tipografía y código | dark |
| `Hero _ Graphite.html` | Mockup de hero de landing, modo monocromo graphite | dark |
| `Manifesto.html` | Página de manifiesto con 3 principios | light |
| `App _ beam.html` | UI mockup, tema beam (alto contraste) | light |
| `App _ ink.html` | UI mockup, tema ink (default) | light |
| `App _ paper.html` | UI mockup, tema paper (dark) | dark |
| `Construcci_n.html` | Especificación de grilla y proporciones del logo | dark |

Para abrir cualquier archivo: `open "identidad/Manifesto.html"` (Mac).

---

## 9. Implementación en código (target)

Cuando se code la web (`web/`), traducir esto a CSS variables y un Tailwind config:

```ts
// web/tailwind.config.ts (extracto)
export default {
  theme: {
    extend: {
      colors: {
        paper: '#EFEDE6',
        ink: '#1C1B18',
        graphite: { DEFAULT: '#7C7A72', dark: '#5C5A52' },
        'paper-soft': '#D4D0C5',
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '2px',
      },
    },
  },
}
```

Cargar fuentes vía `next/font/google` para `IBM Plex Sans` y `IBM Plex Mono` con `display: 'swap'`.

---

## 10. Aún por definir

- [ ] Iconografía: ¿conjunto custom o `lucide-react` filtrado a stroke 1.5?
- [ ] Estados de hover / focus / disabled del wordmark.
- [ ] Variante reducida del logo (icon-only) para favicon — proponer en `Construcción.html` ya tiene base.
- [ ] Tono para mensajes de error de API (mantener voz "silencioso, calmo").
- [ ] Foto / ilustración: ¿el sistema permite fotografía o es solo tipográfico? Por ahora, **solo tipográfico**.
