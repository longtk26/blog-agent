export const styleGuideKeys = {
  all: ["style-guide"] as const,
  active: () => [...styleGuideKeys.all, "active"] as const,
};
