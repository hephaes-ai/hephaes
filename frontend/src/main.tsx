import React from "react";
import ReactDOM from "react-dom/client";

import { BootstrapApp } from "./bootstrap-app";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BootstrapApp />
  </React.StrictMode>,
);
