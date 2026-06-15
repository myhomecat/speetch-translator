"use client";

import { createContext, useContext } from "react";

export interface AppConfig {
  WS_URL: string;
  API_URL: string;
}

const ConfigContext = createContext<AppConfig>({
  WS_URL: "ws://localhost:8000",
  API_URL: "http://localhost:8000",
});

export function ConfigProvider({
  value,
  children,
}: {
  value: AppConfig;
  children: React.ReactNode;
}) {
  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>;
}

export const useConfig = () => useContext(ConfigContext);
