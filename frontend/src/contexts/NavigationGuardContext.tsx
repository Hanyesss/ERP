import React, { createContext, useContext, useRef } from "react";

type GuardFn = () => Promise<boolean>;

interface GuardCtx {
  registerGuard: (fn: GuardFn) => void;
  unregisterGuard: () => void;
  checkGuard: () => Promise<boolean>;
}

const Ctx = createContext<GuardCtx>({
  registerGuard: () => {},
  unregisterGuard: () => {},
  checkGuard: async () => true,
});

export function NavigationGuardProvider({ children }: { children: React.ReactNode }) {
  const guardRef = useRef<GuardFn | null>(null);

  return (
    <Ctx.Provider value={{
      registerGuard: (fn) => { guardRef.current = fn; },
      unregisterGuard: () => { guardRef.current = null; },
      checkGuard: () => guardRef.current ? guardRef.current() : Promise.resolve(true),
    }}>
      {children}
    </Ctx.Provider>
  );
}

export const useNavigationGuard = () => useContext(Ctx);
