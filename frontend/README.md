# RISKSETU AI — Frontend

Phase 1: Premium geospatial design system and application shell.

## Quickstart

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173

## Build

```bash
npm run build
npm run preview
```

## Structure

```
src/
  components/
    layout/     Header, StatusIndicator, LayerBar, AppShell
    ui/         Button, Badge, Panel, Metric
  pages/        Dashboard
  styles/       Design tokens, global styles
  types/        Shared TypeScript types
```

## Design Direction

Light cartographic aesthetic — warm ivory surfaces, charcoal typography, muted blues/teals/sage earth tones. Risk colors are reserved for risk states only. The map workspace occupies ~75–80% of the viewport.

## Phase 1 Scope

- Visual foundation and design tokens
- Application shell (header, viewport, layer bar)
- Map workspace placeholder
- Reusable UI components
- Subtle micro-interactions

No API calls, no backend modifications.
