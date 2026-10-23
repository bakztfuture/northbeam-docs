<template>
  <svg viewBox="0 0 120 96" aria-hidden="true">
    <!-- A stack of two pages, the front one with text lines and a north star -->
    <rect class="page back" x="34" y="10" width="56" height="72" rx="6" />
    <rect class="page" x="24" y="16" width="56" height="72" rx="6" />
    <rect class="line" x="34" y="30" width="28" height="5" rx="2.5" />
    <rect class="line faint" x="34" y="42" width="36" height="4" rx="2" />
    <rect class="line faint" x="34" y="52" width="32" height="4" rx="2" />
    <rect class="line faint" x="34" y="62" width="22" height="4" rx="2" />
    <circle class="badge" cx="86" cy="70" r="16" />
    <path class="star" d="M86 59 L88 68 L97 70 L88 72 L86 81 L84 72 L75 70 L84 68 Z" />
  </svg>
</template>

<style scoped>
.page {
  fill: var(--color-bg);
  stroke: var(--color-border);
  stroke-width: 2;

  &.back {
    fill: var(--color-surface);
  }
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

.star {
  fill: var(--color-text-inverse);
}
</style>
