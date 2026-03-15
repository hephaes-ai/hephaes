import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { router } from "./app/routes";
import "./styles.css";
import { FeedbackProvider } from "./state/feedback";
import { InventoryProvider } from "./state/inventory";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <FeedbackProvider>
      <InventoryProvider>
        <RouterProvider router={router} />
      </InventoryProvider>
    </FeedbackProvider>
  </React.StrictMode>,
);
