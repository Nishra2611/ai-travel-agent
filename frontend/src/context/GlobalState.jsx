import { createContext, useContext, useMemo, useState } from "react";

const GlobalStateContext = createContext();

export function GlobalStateProvider({ children }) {
  const [globalCity, setGlobalCity] = useState("");
  const [currentTrip, setCurrentTrip] = useState(null);
  const [pendingRefinement, setPendingRefinement] = useState(null);

  const value = useMemo(
    () => ({ 
      globalCity, setGlobalCity, 
      currentTrip, setCurrentTrip,
      pendingRefinement, setPendingRefinement 
    }),
    [globalCity, currentTrip, pendingRefinement]
  );

  return (
    <GlobalStateContext.Provider value={value}>
      {children}
    </GlobalStateContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useGlobalState() {
  return useContext(GlobalStateContext);
}
