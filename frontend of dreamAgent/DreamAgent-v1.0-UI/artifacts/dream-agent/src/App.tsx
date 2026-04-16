import { Switch, Route, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/not-found";

import Agents from "./pages/agents";
import AgentDetail from "./pages/agent-detail";
import Chat from "./pages/chat";
import Tasks from "./pages/tasks";
import History from "./pages/history";
import Settings from "./pages/settings";
import Monitoring from "./pages/monitoring";
import Connections from "./pages/connections";
import Builder from "./pages/builder";
import BuilderForm from "./pages/builder-form";
import { useAppStore } from "@/store/app.store";
import { useEffect } from "react";
import { useLocation } from "wouter";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function Router() {
  const [location, setLocation] = useLocation();
  const { mode } = useAppStore();

  useEffect(() => {
    if (mode === "Lite") {
      if (location.startsWith("/agents") || location.startsWith("/monitoring")) {
        setLocation("/");
      }
    }
  }, [mode, location, setLocation]);

  return (
    <Switch>
      <Route path="/" component={Chat} />
      <Route path="/agents" component={Agents} />
      <Route path="/agents/:id" component={AgentDetail} />
      <Route path="/chat" component={Chat} />
      <Route path="/builder" component={Builder} />
      <Route path="/builder/new" component={BuilderForm} />
      <Route path="/tasks" component={Tasks} />
      <Route path="/activity" component={History} />
      <Route path="/settings" component={Settings} />
      <Route path="/monitoring" component={Monitoring} />
      <Route path="/connections" component={Connections} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
