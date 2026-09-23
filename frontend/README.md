# DataSight frontend

The Next.js interface for DataSight: file upload, the dashboard, charts, and the recipe builder.
See the [project README](../README.md) for setup, the walkthrough, and configuration.

## Development

The backend must be running for the app to load data. From this directory:

```bash
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The backend address defaults to
`http://localhost:8000`; to change it, copy [.env.example](.env.example) to `.env.local` and set
`NEXT_PUBLIC_API_URL`.

## Checks

```bash
npm test          # Vitest and React Testing Library, no backend needed
npm run lint
npm run typecheck
npm run build     # downloads Google fonts, so needs network access
```

## Layout

```text
app/          Page, layout, and global styles
components/   Dashboard, charts, and recipe interface
lib/          API client, chart, recipe, and theme helpers
tests/        Interaction tests
```
