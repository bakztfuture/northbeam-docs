<template>
  <svg viewBox="0 0 120 96" aria-hidden="true">
    <!-- A clock with an arrow sweeping forward around it, and the north star at twelve -->
    <path class="sweep" d="M 88 22 A 38 38 0 0 1 98 60" />
    <path class="arrowhead" d="M 92 58 L 98 66 L 104 57 Z" />
    <circle class="face" cx="60" cy="50" r="32" />
    <rect class="line faint" x="58.5" y="74" width="3" height="5" rx="1.5" />
    <rect class="line faint" x="34" y="48.5" width="5" height="3" rx="1.5" />
    <rect class="line faint" x="81" y="48.5" width="5" height="3" rx="1.5" />
    <rect class="line" x="57.5" y="34" width="5" height="18" rx="2.5" />
    <rect
      class="line"
      x="58"
      y="47.5"
      width="16"
      height="5"
      rx="2.5"
      transform="rotate(30 60 50)"
    />
    <circle class="badge" cx="60" cy="50" r="4" />
    <path
      class="badge"
      d="M60 21 L61.5 26.5 L67 28 L61.5 29.5 L60 35 L58.5 29.5 L53 28 L58.5 26.5 Z"
    />
  </svg>
</template>

<style scoped>
.sweep {
  fill: none;
  stroke: var(--color-primary);
  stroke-width: 4;
  stroke-linecap: round;
}

.arrowhead {
  fill: var(--color-primary);
}

.face {
  fill: var(--color-bg);
  stroke: var(--color-border);
  stroke-width: 2;
}

.line {
  fill: var(--color-text-muted);

  &.faint {
    fill: var(--color-border);
  }
}

.badge {
  fill: var(--color-primary);
}
</style>
