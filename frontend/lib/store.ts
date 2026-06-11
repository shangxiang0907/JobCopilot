import { create } from "zustand"

interface UIState {
  chatOpen: boolean
  selectedJobId: string | null
  toggleChat: () => void
  openChat: () => void
  closeChat: () => void
  setSelectedJob: (id: string | null) => void
}

export const useUIStore = create<UIState>((set) => ({
  chatOpen: false,
  selectedJobId: null,
  toggleChat: () => set((s) => ({ chatOpen: !s.chatOpen })),
  openChat: () => set({ chatOpen: true }),
  closeChat: () => set({ chatOpen: false }),
  setSelectedJob: (id) => set({ selectedJobId: id }),
}))
