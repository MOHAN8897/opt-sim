import { create } from "zustand";

interface UIState {
  sidebarOpen: boolean;
  orderModalOpen: boolean;
  selectedOption: {
    instrumentKey: string;
    instrumentName: string;
    strike: number;
    optionType: "CE" | "PE";
    ltp: number;
  } | null;
  riskCalculatorOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  openOrderModal: (option: UIState["selectedOption"]) => void;
  closeOrderModal: () => void;
  setRiskCalculatorOpen: (open: boolean) => void;
  initializeFromLocalStorage: () => void; // FIX #2: Add restore action
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  orderModalOpen: false,
  selectedOption: null,
  riskCalculatorOpen: false,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  openOrderModal: (option) => {
    // 🔴 FIX #2: Persist selectedOption to localStorage to prevent loss on re-renders
    set({ orderModalOpen: true, selectedOption: option });
    try {
      localStorage.setItem('uiStore_selectedOption', JSON.stringify(option));
    } catch (e) {
      console.warn('[UIStore] Failed to persist selectedOption', e);
    }
  },
  closeOrderModal: () => set({ orderModalOpen: false, selectedOption: null }),
  // 🔴 FIX #3: Restore selectedOption from localStorage on initialization
  initializeFromLocalStorage: () => {
    try {
      const saved = localStorage.getItem('uiStore_selectedOption');
      if (saved) {
        const option = JSON.parse(saved);
        set({ selectedOption: option });
      }
    } catch (e) {
      console.warn('[UIStore] Failed to restore selectedOption', e);
    }
  },
  setRiskCalculatorOpen: (open) => set({ riskCalculatorOpen: open }),
}));
