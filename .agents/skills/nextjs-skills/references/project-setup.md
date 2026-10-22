# Project Setup & Package Management

## 1. Project Creation

When scaffolding a new Next.js project, ALWAYS use `pnpx`:

```bash
pnpx create-next-app@latest ./ \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --use-pnpm
```

### Flags Breakdown

| Flag | Purpose |
|---|---|
| `./` | Initialize in the current directory |
| `--typescript` | Configure TypeScript out of the box |
| `--tailwind` | Include Tailwind CSS |
| `--eslint` | Setup ESLint configuration |
| `--app` | Use the App Router (`app/` directory) |
| `--src-dir` | Place source code inside `src/` |
| `--import-alias "@/*"` | Set root path alias to `@/` |
| `--use-pnpm` | Force pnpm as the package manager |

---

## 2. Package Manager

- **Strictly use `pnpm`** for all package management in this project.
- **Never** use `npm`, `npx`, `yarn`, or `bun`.

### Command Reference

| Action | Command |
|---|---|
| Install all dependencies | `pnpm install` |
| Add a production package | `pnpm add <package>` |
| Add a dev dependency | `pnpm add -D <package>` |
| Run an executable / CLI tool | `pnpx <tool> [args]` |
| Run a package.json script | `pnpm <script>` (e.g. `pnpm dev`, `pnpm build`) |
