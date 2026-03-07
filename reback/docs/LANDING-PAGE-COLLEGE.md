# TODO — Landing de Colegio (ICFES Analytics)

Objetivo: mejorar SEO, CTR, estabilidad de indexación y conversión (CTA) en páginas tipo:
`/icfes/colegio/<slug>/`

---

## 1) SEO técnico esencial

### 1.1 Canonical consistente
- [ ] `link rel="canonical"` siempre con URL absoluta y consistente (https + www + trailing slash).
- [ ] Evitar duplicados por variantes (sin slash / con slash).

### 1.2 Meta robots
- [ ] Mantener: `index, follow`.
- [ ] Evitar `noindex` accidental en entornos productivos.
- [ ] Asegurar que no hay headers que contradigan (X-Robots-Tag).

### 1.3 Head correcto (mínimo)
- [ ] `<title>` único por colegio.
- [ ] `<meta name="description">` único y natural (sin keyword stuffing).
- [ ] OG y Twitter completos (`og:title`, `og:description`, `og:image`, `og:url`).

---

## 2) Calidad de contenido (para indexación real)

### 2.1 SSR primero (no depender de JS)
- [ ] El resumen ejecutivo y cifras clave deben estar en HTML SSR (no solo gráficos canvas).
- [ ] Tabla de materias en HTML SSR (ya está OK).

### 2.2 Evitar inconsistencias
- [ ] No repetir una materia en Fortalezas y Áreas de mejora.
- [ ] Fortalezas = top N materias (ej. 3).
- [ ] Mejora = bottom N materias (ej. 3).
- [ ] Validar que el ranking / percentil municipal tenga sentido (no 0.0 por default).

### 2.3 “Colegios similares” con criterio claro
- [ ] Mostrar similares por: municipio + sector (OFICIAL/NO OFICIAL) + rango de puntaje (±10–15 pts).
- [ ] Evitar lista aleatoria o muy larga (máximo 5).
- [ ] Incluir 1–2 enlaces “contextuales” extra:
  - [ ] “Mejor del municipio (mismo sector)”
  - [ ] “Mejor del departamento”

---

## 3) Title y CTR (muy importante)

### 3.1 Reducir longitud del title
Problema: títulos largos se cortan en Google.

- [ ] Nuevo formato recomendado:
  - `NOMBRE DEL COLEGIO (Ciudad) – Resultados ICFES 2024`
- [ ] Mover `#ranking` y `percentil` al H1/H2 o a la descripción, no al title.
- [ ] Evitar caracteres redundantes (`| #6 | P37.5`) en title.

### 3.2 Description persuasiva
- [ ] Incluir: puntaje global + ranking municipal + tendencia (3 años) + CTA suave.
- [ ] Ejemplo:
  - `Resultados ICFES 2024: puntaje 266.5, posición 6/9 en Sopó y mejora de +17.3 en 3 años. Ver brechas por materia y acciones recomendadas.`

---

## 4) Normalización de texto (evitar duplicados invisibles)

### 4.1 Limpiar espacios múltiples
Problema: nombres con doble/triple espacio pueden generar variaciones en title/description/JSON-LD.

- [ ] Normalizar `nombre_colegio` en backend:
  - trim
  - colapsar espacios múltiples a 1
  - opcional: normalizar tildes para slug (solo slug)

**Regla recomendada:** `" ".join(nombre.split())`

### 4.2 Formato de números y separadores
- [ ] UI puede usar coma decimal (266,5), pero:
- [ ] JSON-LD y datos internos deben usar punto decimal (266.5).

---

## 5) Structured Data (JSON-LD) — checklist

### 5.1 School
- [ ] `@type: School`
- [ ] `name`, `url`, `address` completos
- [ ] `additionalProperty` para puntaje global

### 5.2 Article
- [ ] `@type: Article`
- [ ] `headline`, `description`, `url`, `publisher`
- [ ] `about` referenciando el School
- [ ] Fechas coherentes:
  - [ ] `datePublished` = fecha real de publicación (o igual a dateModified si no se conoce)
  - [ ] `dateModified` = fecha real de última actualización

> Evitar `datePublished` inventado muy antiguo con `dateModified` hoy (puede verse raro).

### 5.3 BreadcrumbList
- [ ] `Inicio > Colegios ICFES > Colegio`
- [ ] URLs absolutas y consistentes

### 5.4 FAQPage (a escala)
Riesgo: 22k páginas con FAQ idéntico = Google puede ignorarlo.

- [ ] Mantener 2–3 preguntas máximo.
- [ ] Hacer FAQs más “específicas del colegio”:
  - [ ] puntaje global 2024
  - [ ] brecha municipal
  - [ ] materia con mayor brecha
  - [ ] tendencia 3 años / # estudiantes evaluados
- [ ] Alternar 2 plantillas de FAQ para reducir repetición masiva.

---

## 6) Performance (Core Web Vitals + crawl budget)

### 6.1 CSS inline demasiado grande
Problema: repetir `<style>` grande en 22k páginas aumenta bytes y reduce cache.

- [ ] Mover CSS principal a `/static/css/school.css?v=YYYYMMDD`
- [ ] Dejar inline solo CSS crítico mínimo (si aplica).

### 6.2 JS diferido
- [ ] Mantener `defer` en bootstrap y chart.js (ya OK).
- [ ] Si chart.js no carga, la página debe seguir siendo útil (ya OK).

### 6.3 Cache de HTML
- [ ] Definir estrategia de cache (ej. TTL 6h) para HTML completo.
- [ ] Invalidar cache cuando cambie dataset / lógica de ranking.

---

## 7) Conversión (CTA + tracking)

### 7.1 CTA principal
- [ ] CTA visible arriba y abajo:
  - `Solicitar diagnóstico gratuito`
- [ ] CTA secundario:
  - `Explorar portal ICFES`

### 7.2 UTM y analítica
- [ ] CTA links con UTMs (`utm_source=seo&utm_medium=landing&utm_campaign=school_landing`)
- [ ] Registrar evento (GA4) al hacer click:
  - `cta_click`
  - `lead_start`

### 7.3 Confianza (para rectores)
- [ ] Incluir “Fuente: ICFES (datos públicos)” + aviso de metodología (breve).
- [ ] Incluir “Última actualización: YYYY-MM-DD” visible en el body.

---

## 8) QA y validación

- [ ] Validar HTML / structured data con Rich Results Test / Schema validator.
- [ ] Validar que no haya 500s para bots (logs Railway).
- [ ] Verificar que cada landing:
  - [ ] devuelve 200
  - [ ] carga < 2s promedio
  - [ ] canonical correcto
  - [ ] no tiene contenido duplicado obvio

---

## 9) Backlog de mejoras futuras (nice to have)

- [ ] Añadir sección: “Comparación contra colegios del mismo sector en Cundinamarca”
- [ ] Añadir micro-copys: “¿Qué significa percentil municipal?”
- [ ] Añadir enlaces internos a:
  - [ ] municipio
  - [ ] departamento
  - [ ] ranking nacional por sector
- [ ] Añadir “Top oportunidades”: 2 acciones priorizadas por mayor gap + facilidad.

---

## Priorización recomendada (impacto rápido)

P0 (esta semana)
- [ ] Normalizar espacios múltiples en nombre del colegio.
- [ ] Acortar `<title>` para mejorar CTR.
- [ ] Corregir fechas `datePublished/dateModified` en JSON-LD.
- [ ] Mover CSS grande a archivo estático.

P1 (próxima)
- [ ] Mejorar FAQs (menos repetición, más específicas).
- [ ] Arreglar lógica de fortalezas vs mejoras sin duplicados.
- [ ] Eventos GA4 para CTA.

P2
- [ ] Optimizar “colegios similares” con criterio.
- [ ] Añadir “última actualización” visible + fuente/metodología.