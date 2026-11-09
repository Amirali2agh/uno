import React, { createContext, useContext } from 'react';
import { useUnoSocket } from '../hooks/useUnoSocket';

type SocketApi = ReturnType<typeof useUnoSocket>;

const SocketContext = createContext<SocketApi | null>(null);

/**
 * Owns the single socket client for the whole app: App (queue) and GameRoom (room)
 * used to create independent instances, so `disconnectAll()` in one could not
 * close the socket opened by the other.
 */
export const SocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const socket = useUnoSocket();
  return <SocketContext.Provider value={socket}>{children}</SocketContext.Provider>;
};

export const useSocket = (): SocketApi => {
  const context = useContext(SocketContext);
  if (!context) {
    throw new Error('useSocket must be used inside <SocketProvider>');
  }
  return context;
};
