import React from "react";
import ReactDOM from "react-dom/client";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import ru from "./locales/ru.json";
import zh from "./locales/zh.json";
import App from "./App";
import "./mobile.css";

const savedLang = localStorage.getItem("lang") || "ru";

i18n.use(initReactI18next).init({
  resources: {
    ru: { translation: ru },
    zh: { translation: zh },
  },
  lng: savedLang,
  fallbackLng: "ru",
  interpolation: { escapeValue: false },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
