import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./styles/globals.css";

globalThis.__HEPHAES_BACKEND_BASE_URL__ =
  import.meta.env.VITE_BACKEND_BASE_URL?.trim() || undefined;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
