import { create } from 'zustand';

type AppMode = 'Lite' | 'Standard' | 'Ultra';

interface AppState {
  mode: AppMode;
  setMode: (mode: AppMode) => void;
  activeBotId: string | null;
  setActiveBotId: (id: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  mode: 'Standard',
  setMode: (mode) => set({ mode }),
  activeBotId: null,
  setActiveBotId: (id) => set({ activeBotId: id }),
}));
