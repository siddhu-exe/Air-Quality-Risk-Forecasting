import React from 'react';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-surface font-body-md text-on-surface antialiased flex flex-col">
      <TopBar />
      <Sidebar />
      <div className="pl-64 flex-1">
        <main className="relative pt-[124px] w-full px-margin-desktop bg-surface min-h-screen">
          <div className="flex flex-col w-full pb-space-2xl">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
