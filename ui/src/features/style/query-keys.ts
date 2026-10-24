export const styleKeys = {
  all: ["style"] as const,
  samples: (approvedOnly?: boolean) => [...styleKeys.all, "samples", { approvedOnly }] as const,
  profileActive: () => [...styleKeys.all, "profile", "active"] as const,
  profiles: () => [...styleKeys.all, "profiles"] as const,
  profile: (id: string) => [...styleKeys.all, "profile", id] as const,
  notes: () => [...styleKeys.all, "notes"] as const,
  note: (id: string) => [...styleKeys.all, "notes", id] as const,
};
